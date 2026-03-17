#!/usr/bin/env bash
# Production bootstrap for Ubuntu 22.04 EC2
# Usage:
#   REPO_URL="https://github.com/<org>/<repo>.git" APP_MODULE="app:app" bash deploy/setup_ec2.sh

set -euo pipefail

APP_NAME="care4u"
APP_USER="ubuntu"
APP_GROUP="www-data"
APP_DIR="/var/www/${APP_NAME}"
VENV_DIR="${APP_DIR}/.venv"
SERVICE_NAME="care4u"

REPO_URL="${REPO_URL:-}"
APP_MODULE="${APP_MODULE:-app:app}"

if [[ -z "${REPO_URL}" ]]; then
	echo "ERROR: REPO_URL is required."
	echo "Example: REPO_URL='https://github.com/your-org/your-repo.git' bash deploy/setup_ec2.sh"
	exit 1
fi

echo "[1/9] Installing system packages..."
sudo apt update -y
sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv nginx git

echo "[2/9] Preparing application directory..."
sudo mkdir -p "${APP_DIR}"
sudo chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}"

echo "[3/9] Cloning repository..."
if [[ -d "${APP_DIR}/.git" ]]; then
	git -C "${APP_DIR}" pull --ff-only
else
	rm -rf "${APP_DIR:?}"/*
	git clone "${REPO_URL}" "${APP_DIR}"
fi

echo "[4/9] Creating virtual environment and installing dependencies..."
python3 -m venv "${VENV_DIR}"
source "${VENV_DIR}/bin/activate"
pip install --upgrade pip
pip install -r "${APP_DIR}/requirements.txt"

echo "[5/9] Creating .env template if missing..."
if [[ ! -f "${APP_DIR}/.env" ]]; then
	cat > "${APP_DIR}/.env" <<EOF
FLASK_ENV=production
FLASK_DEBUG=0
SECRET_KEY=replace-me
APP_MODULE=${APP_MODULE}
SQLALCHEMY_DATABASE_URI=postgresql+psycopg2://dbuser:dbpass@db-endpoint:5432/care4u
AWS_REGION=us-east-1
AWS_S3_BUCKET=replace-me
EOF
	echo "Created ${APP_DIR}/.env. Update values before production traffic."
fi

echo "[6/9] Installing systemd service..."
sudo cp "${APP_DIR}/deploy/care4u.service" /etc/systemd/system/care4u.service
sudo sed -i "s|\${APP_MODULE:-app:app}|${APP_MODULE}|g" /etc/systemd/system/care4u.service
sudo systemctl daemon-reload
sudo systemctl enable "${SERVICE_NAME}"
sudo systemctl restart "${SERVICE_NAME}"

echo "[7/9] Installing Nginx site..."
sudo cp "${APP_DIR}/deploy/care4u.conf" /etc/nginx/sites-available/app
sudo rm -f /etc/nginx/sites-enabled/default
sudo ln -sf /etc/nginx/sites-available/app /etc/nginx/sites-enabled/app
sudo nginx -t
sudo systemctl enable nginx
sudo systemctl restart nginx

echo "[8/9] Hardening permissions..."
sudo chown -R "${APP_USER}:${APP_GROUP}" "${APP_DIR}"
sudo chmod 640 "${APP_DIR}/.env" || true

echo "[9/9] Completed."
echo "Public URL: http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 || echo '<ec2-public-ip>')"
echo "Useful commands:"
echo "  sudo systemctl status care4u"
echo "  sudo journalctl -u care4u -f"
echo "  sudo tail -f /var/log/nginx/error.log"
