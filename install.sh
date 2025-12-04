#!/bin/bash
# AI-Nisse Installationsskript för Raspberry Pi 5

set -e

echo "=================================================="
echo "     AI-NISSE INSTALLATION"
echo "=================================================="
echo ""

# Kontrollera att vi kör som root
if [ "$EUID" -ne 0 ]; then 
    echo "Kör detta skript med sudo: sudo ./install.sh"
    exit 1
fi

# Hämta aktuell användare (inte root)
REAL_USER="${SUDO_USER:-$USER}"
INSTALL_DIR="/home/$REAL_USER/dev/ai-nisse-pi"

echo "Användare: $REAL_USER"
echo "Installationsdir: $INSTALL_DIR"
echo ""

echo "Installerar systemberoenden..."
apt update
apt install -y python3-pip python3-venv python3-lgpio mpg123

echo ""
echo "Skapar Python virtual environment med system-paket..."
cd "$INSTALL_DIR"
sudo -u "$REAL_USER" python3 -m venv venv --system-site-packages

echo ""
echo "Installerar Python-paket..."
sudo -u "$REAL_USER" ./venv/bin/pip install --upgrade pip
sudo -u "$REAL_USER" ./venv/bin/pip install -r requirements.txt

echo ""
echo "Skapar systemd-service..."
cat > /etc/systemd/system/nisse.service << EOF
[Unit]
Description=AI Nisse - Magisk nissedörr
After=network.target sound.target
Wants=network.target

[Service]
Type=simple
User=$REAL_USER
Group=$REAL_USER
WorkingDirectory=$INSTALL_DIR
Environment=PYTHONUNBUFFERED=1
ExecStart=$INSTALL_DIR/venv/bin/python3 $INSTALL_DIR/nisse.py
Restart=always
RestartSec=10
SupplementaryGroups=gpio audio
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable nisse.service

echo ""
echo "Sätter rättigheter..."
chown -R "$REAL_USER:$REAL_USER" "$INSTALL_DIR"
chmod +x "$INSTALL_DIR/nisse.py"

echo ""
echo "=================================================="
echo "     INSTALLATION KLAR!"
echo "=================================================="
echo ""
echo "Starta Nisse:"
echo "   sudo systemctl start nisse"
echo ""
echo "Se loggar:"
echo "   sudo journalctl -u nisse -f"
echo ""
echo "Stoppa:"
echo "   sudo systemctl stop nisse"
echo ""
echo "GPIO-koppling:"
echo "   PIR OUT -> GPIO17 (pin 11)"
echo "   PIR VCC -> 5V (pin 2/4)"
echo "   PIR GND -> GND (pin 6)"
echo ""
echo "God jul!"
