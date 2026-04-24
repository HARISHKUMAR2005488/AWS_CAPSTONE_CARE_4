#!/usr/bin/env bash
# ===========================================================================
# Production bootstrap for Amazon Linux 2023 / Amazon Linux 2 on EC2
# ===========================================================================
#
# Usage:
#   REPO_URL="https://github.com/HARISHKUMAR2005488/AWS_CAPSTONE_CARE_4.git" \
#   bash deploy/setup_ec2.sh
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
APP_USER="ec2-user"
APP_GROUP="nginx"
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
    echo "Example: REPO_URL='https://github.com/HARISHKUMAR2005488/AWS_CAPSTONE_CARE_4.git' bash deploy/setup_ec2.sh"
    exit 1
fi

# Detect Amazon Linux version
if grep -q "Amazon Linux 2023" /etc/os-release 2>/dev/null; then
    PKG_MGR="dnf"
    AL_VERSION="AL2023"
elif grep -q "Amazon Linux 2" /etc/os-release 2>/dev/null; then
    PKG_MGR="yum"
    AL_VERSION="AL2"
else
    PKG_MGR="dnf"
    AL_VERSION="unknown"
fi

echo "=========================================="
echo "  Care_4_U Hospital — EC2 Setup (HTTPS)"
echo "=========================================="
echo "  OS:        ${AL_VERSION}"
echo "  Pkg Mgr:   ${PKG_MGR}"
echo "  SSL Mode:  ${SSL_MODE}"
echo "  Domain:    ${DOMAIN:-<not set>}"
echo "=========================================="

echo "[1/11] Installing system packages..."
sudo ${PKG_MGR} update -y

if [[ "${AL_VERSION}" == "AL2023" ]]; then
    sudo dnf install -y python3 python3-pip python3-devel nginx git gcc openssl
elif [[ "${AL_VERSION}" == "AL2" ]]; then
    sudo yum install -y python3 python3-pip python3-devel git gcc openssl
    sudo amazon-linux-extras install nginx1 -y
else
    sudo dnf install -y python3 python3-pip python3-devel nginx git gcc openssl
fi

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

echo "[5/11] Creating .env file if missing..."
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
FLASK_SSL=0

# AWS
AWS_REGION=us-east-1
USERS_TABLE=Users
DOCTORS_TABLE=Doctors
APPOINTMENTS_TABLE=Appointments
MEDICAL_RECORDS_TABLE=MedicalRecords
SNS_TOPIC_ARN=arn:aws:sns:us-east-1:455322615378:Healthcarenotifications
EOF
    echo "Created ${APP_DIR}/.env — update values before production traffic."
fi

echo "[6/11] Installing systemd service..."
# Update service file for Amazon Linux (ec2-user instead of ubuntu)
sudo cp "${APP_DIR}/deploy/care4u.service" /etc/systemd/system/care4u.service
sudo sed -i "s|User=ubuntu|User=${APP_USER}|g" /etc/systemd/system/care4u.service
sudo sed -i "s|Group=www-data|Group=${APP_GROUP}|g" /etc/systemd/system/care4u.service
sudo sed -i "s|\${APP_MODULE:-app_aws:app}|${APP_MODULE}|g" /etc/systemd/system/care4u.service
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
            echo "  Installing certbot..."
            if [[ "${AL_VERSION}" == "AL2023" ]]; then
                sudo dnf install -y certbot python3-certbot-nginx
            else
                sudo pip3 install certbot certbot-nginx
            fi

            # Install HTTP-only Nginx config first for ACME challenge
            sudo mkdir -p /var/www/certbot
            sudo cp "${APP_DIR}/deploy/care4u.conf" /etc/nginx/conf.d/care4u.conf
            sudo rm -f /etc/nginx/conf.d/default.conf
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
        fi
        ;;
    alb)
        echo "  SSL is handled by AWS ALB / ACM certificate."
        sudo cp "${APP_DIR}/deploy/care4u_alb.conf" /etc/nginx/conf.d/care4u.conf
        sudo rm -f /etc/nginx/conf.d/default.conf
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
        ;;
esac

# Install Nginx config
if [[ "${SSL_MODE}" == "selfsigned" ]]; then
    echo "[8/11] Installing Nginx site (HTTPS)..."
    sudo cp "${APP_DIR}/deploy/care4u.conf" /etc/nginx/conf.d/care4u.conf
    sudo rm -f /etc/nginx/conf.d/default.conf
    sudo nginx -t
    sudo systemctl enable nginx
    sudo systemctl restart nginx
else
    echo "[8/11] Nginx already configured."
fi

echo "[9/11] Creating upload directories..."
sudo mkdir -p "${APP_DIR}/instance/uploads"
sudo mkdir -p /var/www/certbot
sudo chown -R "${APP_USER}:${APP_GROUP}" "${APP_DIR}/instance"

echo "[10/11] Hardening permissions..."
sudo chown -R "${APP_USER}:${APP_GROUP}" "${APP_DIR}"
sudo chmod 640 "${APP_DIR}/.env" || true

echo "[11/11] Opening firewall ports..."
# Amazon Linux uses iptables or security groups (SG handled in AWS Console)
# Just make sure SELinux allows Nginx proxy if enabled
if command -v setsebool &>/dev/null; then
    sudo setsebool -P httpd_can_network_connect 1 2>/dev/null || true
fi

echo ""
echo "=========================================="
echo "  ✅ Deployment Complete"
echo "=========================================="

PUBLIC_IP=$(curl -s --connect-timeout 3 http://169.254.169.254/latest/meta-data/public-ipv4 || echo '<ec2-public-ip>')

echo "  SSL Mode:  ${SSL_MODE}"
echo "  Public IP: ${PUBLIC_IP}"
if [[ "${SSL_MODE}" == "alb" ]]; then
    echo "  URL:       https://${DOMAIN:-$PUBLIC_IP}  (via ALB)"
else
    echo "  URL:       https://${PUBLIC_IP}"
fi
echo ""
echo "  Useful commands:"
echo "    sudo systemctl status care4u"
echo "    sudo journalctl -u care4u -f"
echo "    sudo tail -f /var/log/nginx/error.log"
echo ""
