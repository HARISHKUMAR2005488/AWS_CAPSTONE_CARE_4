#!/bin/bash
# =============================================================
# Care_4_U — EC2 Amazon Linux Setup Script
# Run this script ONCE after SSH-ing into a fresh EC2 instance
# Usage: bash setup_ec2.sh
# =============================================================

set -e  # Stop on any error

PROJECT_DIR="/home/ec2-user/AWS_CAPSTONE_CARE_4"
VENV_DIR="$PROJECT_DIR/venv"
SERVICE_NAME="care4u"

echo "============================================"
echo " Care_4_U EC2 Setup — Starting..."
echo "============================================"

# ---- 1. System packages ----
echo "[1/7] Installing system packages..."
sudo dnf update -y
sudo dnf install -y python3 python3-pip git nginx

# ---- 2. Create logs directory ----
echo "[2/7] Creating logs directory..."
mkdir -p "$PROJECT_DIR/logs"

# ---- 3. Python virtual environment ----
echo "[3/7] Setting up Python virtual environment..."
cd "$PROJECT_DIR"
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

# ---- 4. Install Python dependencies ----
echo "[4/7] Installing Python packages from requirements.txt..."
pip install --upgrade pip
pip install -r requirements.txt

# ---- 5. Copy systemd service file ----
echo "[5/7] Installing systemd service..."
sudo cp "$PROJECT_DIR/deploy/care4u.service" /etc/systemd/system/care4u.service
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl start "$SERVICE_NAME"
echo "  Service status:"
sudo systemctl status "$SERVICE_NAME" --no-pager

# ---- 6. Copy Nginx config ----
echo "[6/7] Configuring Nginx..."
sudo cp "$PROJECT_DIR/deploy/care4u.conf" /etc/nginx/conf.d/care4u.conf
sudo nginx -t
sudo systemctl enable nginx
sudo systemctl start nginx
sudo systemctl reload nginx

# ---- 7. Initialize database (for app_aws.py using DynamoDB — skip if not needed) ----
echo "[7/7] Done!"
echo ""
echo "============================================"
echo " Setup Complete!"
echo " Your app should now be live at:"
echo " http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)"
echo "============================================"
echo ""
echo "Useful commands:"
echo "  View logs:    sudo journalctl -u care4u -f"
echo "  Restart app:  sudo systemctl restart care4u"
echo "  Nginx logs:   sudo tail -f /var/log/nginx/error.log"
