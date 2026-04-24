#!/usr/bin/env bash
# ===========================================================================
# Production bootstrap for Ubuntu 22.04 EC2 — with HTTPS support
# ===========================================================================
#
# Usage:
#   REPO_URL="https://github.com/<org>/<repo>.git" bash deploy/setup_ec2.sh
#
# Environment variables:
#   REPO_URL        (required) Git repository URL
#   APP_MODULE      (optional) Gunicorn module (default: app_aws:app)
#   DOMAIN          (optional) Domain name for Let's Encrypt SSL cert
#   SSL_EMAIL       (optional) Email for Let's Encrypt registration
#   SSL_MODE        (optional) "letsencrypt", "selfsigned", or "alb" (default: selfsigned)
# ===========================================================================

set -euo pipefail

APP_NAME="care4u"
APP_USER="ubuntu"
APP_GROUP="www-data"
APP_DIR="/var/www/${APP_NAME}"
VENV_DIR="${APP_DIR}/.venv"
SERVICE_NAME="care4u"

REPO_URL="${REPO_URL:-}"
APP_MODULE="${APP_MODULE:-app_aws:app}"
DOMAIN="${DOMAIN:-}"
SSL_EMAIL="${SSL_EMAIL:-}"
SSL_MODE="${SSL_MODE:-selfsigned}"

if [[ -z "${REPO_URL}" ]]; then
	echo "ERROR: REPO_URL is required."
	echo "Example: REPO_URL='https://github.com/your-org/your-repo.git' bash deploy/setup_ec2.sh"
	exit 1
fi

echo "=========================================="
echo "  Care_4_U Hospital — EC2 Setup (HTTPS)"
echo "=========================================="
echo "  SSL Mode: ${SSL_MODE}"
echo "  Domain:   ${DOMAIN:-<not set>}"
echo "=========================================="

echo "[1/11] Installing system packages..."
sudo apt update -y
sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv nginx git

echo "[2/11] Preparing application directory..."
sudo mkdir -p "${APP_DIR}"
sudo chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}"

echo "[3/11] Cloning repository..."
if [[ -d "${APP_DIR}/.git" ]]; then
	git -C "${APP_DIR}" pull --ff-only
else
	rm -rf "${APP_DIR:?}"/*
	git clone "${REPO_URL}" "${APP_DIR}"
fi

echo "[4/11] Creating virtual environment and installing dependencies..."
python3 -m venv "${VENV_DIR}"
source "${VENV_DIR}/bin/activate"
pip install --upgrade pip
pip install -r "${APP_DIR}/requirements.txt"

echo "[5/11] Creating .env template if missing..."
if [[ ! -f "${APP_DIR}/.env" ]]; then
	cat > "${APP_DIR}/.env" <<EOF
# Flask runtime
FLASK_ENV=production
FLASK_DEBUG=0
FLASK_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
APP_MODULE=${APP_MODULE}

# HTTPS / Security
PREFERRED_URL_SCHEME=https
SESSION_COOKIE_SECURE=1
FORCE_HTTPS=1

# AWS
AWS_REGION=us-east-1
USERS_TABLE=Users
DOCTORS_TABLE=Doctors
APPOINTMENTS_TABLE=Appointments
MEDICAL_RECORDS_TABLE=MedicalRecords
SNS_TOPIC_ARN=arn:aws:sns:us-east-1:455322615378:Healthcarenotifications
EOF
	echo "Created ${APP_DIR}/.env. Update values before production traffic."
fi

echo "[6/11] Installing systemd service..."
sudo cp "${APP_DIR}/deploy/care4u.service" /etc/systemd/system/care4u.service
sudo sed -i "s|\${APP_MODULE:-app:app}|${APP_MODULE}|g" /etc/systemd/system/care4u.service
sudo systemctl daemon-reload
sudo systemctl enable "${SERVICE_NAME}"
sudo systemctl restart "${SERVICE_NAME}"

echo "[7/11] Setting up SSL certificate..."
case "${SSL_MODE}" in
	letsencrypt)
		if [[ -z "${DOMAIN}" ]]; then
			echo "ERROR: DOMAIN is required for Let's Encrypt. Falling back to self-signed."
			SSL_MODE="selfsigned"
		else
			echo "  Installing certbot for Let's Encrypt..."
			sudo apt install -y certbot python3-certbot-nginx

			# Install the HTTP-only Nginx config first for ACME challenge
			sudo mkdir -p /var/www/certbot
			sudo cp "${APP_DIR}/deploy/care4u.conf" /etc/nginx/sites-available/app
			sudo rm -f /etc/nginx/sites-enabled/default
			sudo ln -sf /etc/nginx/sites-available/app /etc/nginx/sites-enabled/app
			sudo nginx -t
			sudo systemctl restart nginx

			# Obtain certificate
			CERTBOT_FLAGS="--nginx -d ${DOMAIN} --non-interactive --agree-tos"
			if [[ -n "${SSL_EMAIL}" ]]; then
				CERTBOT_FLAGS="${CERTBOT_FLAGS} --email ${SSL_EMAIL}"
			else
				CERTBOT_FLAGS="${CERTBOT_FLAGS} --register-unsafely-without-email"
			fi
			sudo certbot ${CERTBOT_FLAGS}
			echo "  Let's Encrypt certificate installed for ${DOMAIN}!"
			echo "  Auto-renewal is enabled via systemd timer."
		fi
		;;
	alb)
		echo "  SSL is handled by AWS ALB / ACM certificate."
		echo "  Using ALB-optimized Nginx config (HTTP only, no local SSL)."
		sudo cp "${APP_DIR}/deploy/care4u_alb.conf" /etc/nginx/sites-available/app
		sudo rm -f /etc/nginx/sites-enabled/default
		sudo ln -sf /etc/nginx/sites-available/app /etc/nginx/sites-enabled/app
		sudo nginx -t
		sudo systemctl enable nginx
		sudo systemctl restart nginx
		;;
	selfsigned|*)
		echo "  Generating self-signed SSL certificate..."
		sudo mkdir -p /etc/nginx/ssl
		sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
			-keyout /etc/nginx/ssl/key.pem \
			-out /etc/nginx/ssl/cert.pem \
			-subj "/C=IN/ST=Dev/L=Localhost/O=Care4U/CN=${DOMAIN:-localhost}"
		sudo chmod 600 /etc/nginx/ssl/key.pem

		echo "  Self-signed certificate generated."
		echo "  WARNING: Browsers will show a security warning. Use Let's Encrypt for production."
		;;
esac

# Install Nginx config (skip if already done by letsencrypt or alb mode)
if [[ "${SSL_MODE}" == "selfsigned" ]]; then
	echo "[8/11] Installing Nginx site (HTTPS)..."
	sudo cp "${APP_DIR}/deploy/care4u.conf" /etc/nginx/sites-available/app
	sudo rm -f /etc/nginx/sites-enabled/default
	sudo ln -sf /etc/nginx/sites-available/app /etc/nginx/sites-enabled/app
	sudo nginx -t
	sudo systemctl enable nginx
	sudo systemctl restart nginx
else
	echo "[8/11] Nginx already configured in step 7."
fi

echo "[9/11] Creating certbot renewal directory..."
sudo mkdir -p /var/www/certbot

echo "[10/11] Hardening permissions..."
sudo chown -R "${APP_USER}:${APP_GROUP}" "${APP_DIR}"
sudo chmod 640 "${APP_DIR}/.env" || true

echo "[11/11] Completed!"
echo ""
echo "=========================================="
echo "  ✅ Deployment Complete"
echo "=========================================="

PUBLIC_IP=$(curl -s --connect-timeout 3 http://169.254.169.254/latest/meta-data/public-ipv4 || echo '<ec2-public-ip>')

if [[ "${SSL_MODE}" == "alb" ]]; then
	echo "  SSL Mode:  ALB (ACM certificate)"
	echo "  Note:      Configure ALB target group to point to this instance on port 80"
	echo "  URL:       https://${DOMAIN:-$PUBLIC_IP}  (via ALB)"
else
	echo "  SSL Mode:  ${SSL_MODE}"
	echo "  URL:       https://${DOMAIN:-$PUBLIC_IP}"
fi

echo ""
echo "  Useful commands:"
echo "    sudo systemctl status care4u"
echo "    sudo journalctl -u care4u -f"
echo "    sudo tail -f /var/log/nginx/error.log"
if [[ "${SSL_MODE}" == "letsencrypt" ]]; then
	echo "    sudo certbot renew --dry-run    # Test renewal"
	echo "    sudo certbot certificates       # List certificates"
fi
echo ""
