#!/usr/bin/env bash
# =============================================
# ONE-COMMAND SETUP for Care_4_U on Amazon Linux
# =============================================
# Just run this after SSH into your EC2:
#   bash setup.sh
# =============================================

set -e

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║   Care_4_U Hospital — Auto Setup     ║"
echo "  ║   Amazon Linux + HTTPS               ║"
echo "  ╚══════════════════════════════════════╝"
echo ""

APP_DIR="/var/www/care4u"
REPO="https://github.com/HARISHKUMAR2005488/AWS_CAPSTONE_CARE_4.git"

# ---- Step 1: Install packages ----
echo "📦 [1/7] Installing packages..."
sudo dnf update -y -q
sudo dnf install -y -q python3 python3-pip python3-devel nginx git gcc openssl

# ---- Step 2: Clone project ----
echo "📂 [2/7] Setting up project..."
sudo mkdir -p "$APP_DIR"
sudo chown -R ec2-user:ec2-user "$APP_DIR"

if [ -d "$APP_DIR/.git" ]; then
    echo "   Project exists, pulling latest..."
    git -C "$APP_DIR" pull --ff-only
else
    git clone "$REPO" "$APP_DIR"
fi

# ---- Step 3: Python setup ----
echo "🐍 [3/7] Installing Python dependencies..."
cd "$APP_DIR"
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q

# ---- Step 4: Create .env ----
echo "⚙️  [4/7] Creating config..."
SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
cat > "$APP_DIR/.env" <<EOF
FLASK_ENV=production
FLASK_DEBUG=0
FLASK_SECRET_KEY=${SECRET}
APP_MODULE=app_aws:app
PREFERRED_URL_SCHEME=https
SESSION_COOKIE_SECURE=1
FORCE_HTTPS=1
FLASK_SSL=0
AWS_REGION=us-east-1
USERS_TABLE=Users
DOCTORS_TABLE=Doctors
APPOINTMENTS_TABLE=Appointments
MEDICAL_RECORDS_TABLE=MedicalRecords
SNS_TOPIC_ARN=arn:aws:sns:us-east-1:455322615378:Healthcarenotifications
EOF
sudo chmod 640 "$APP_DIR/.env"

# ---- Step 5: SSL Certificate ----
echo "🔒 [5/7] Generating SSL certificate..."
sudo mkdir -p /etc/nginx/ssl
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /etc/nginx/ssl/key.pem \
    -out /etc/nginx/ssl/cert.pem \
    -subj "/C=IN/ST=State/L=City/O=Care4U/CN=localhost" 2>/dev/null
sudo chmod 600 /etc/nginx/ssl/key.pem

# ---- Step 6: Nginx ----
echo "⚡ [6/7] Configuring Nginx..."
sudo cp "$APP_DIR/deploy/care4u.conf" /etc/nginx/conf.d/care4u.conf
sudo rm -f /etc/nginx/conf.d/default.conf
# Allow Nginx to connect to Gunicorn (SELinux)
if command -v setsebool &>/dev/null; then
    sudo setsebool -P httpd_can_network_connect 1 2>/dev/null || true
fi
sudo nginx -t
sudo systemctl enable nginx
sudo systemctl start nginx

# ---- Step 7: Gunicorn service ----
echo "🦄 [7/7] Starting application..."
sudo cp "$APP_DIR/deploy/care4u.service" /etc/systemd/system/care4u.service
sudo systemctl daemon-reload
sudo systemctl enable care4u
sudo systemctl start care4u

# ---- Create upload directories ----
sudo mkdir -p "$APP_DIR/instance/uploads"
sudo chown -R ec2-user:nginx "$APP_DIR"

# ---- Done! ----
PUBLIC_IP=$(curl -s --connect-timeout 3 http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo '<your-ec2-ip>')

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║      ✅ SETUP COMPLETE!              ║"
echo "  ╚══════════════════════════════════════╝"
echo ""
echo "  🌐 Open in browser:"
echo "     https://${PUBLIC_IP}"
echo ""
echo "  📋 Useful commands:"
echo "     sudo systemctl status care4u     # Check app"
echo "     sudo systemctl restart care4u    # Restart app"
echo "     sudo journalctl -u care4u -f     # View logs"
echo ""
