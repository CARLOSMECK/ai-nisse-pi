#!/bin/bash
# ============================================================================
#  AI-Nisse Installationsskript för Raspberry Pi
# ============================================================================

set -e

echo "🎄🎄🎄🎄🎄🎄🎄🎄🎄🎄🎄🎄🎄🎄🎄🎄🎄🎄🎄🎄"
echo "     AI-NISSE INSTALLATION"
echo "🎄🎄🎄🎄🎄🎄🎄🎄🎄🎄🎄🎄🎄🎄🎄🎄🎄🎄🎄🎄"
echo ""

# Kontrollera att vi kör som root för systeminstallationer
if [ "$EUID" -ne 0 ]; then 
    echo "Kör detta skript med sudo: sudo ./install.sh"
    exit 1
fi

INSTALL_DIR="/home/pi/ai-nisse-pi"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Installerar systemberoenden..."
apt update
apt install -y python3-pip python3-venv mpg123

echo ""
echo "Kopierar filer till $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"
cp "$SCRIPT_DIR/nisse.py" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/requirements.txt" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/.env" "$INSTALL_DIR/" 2>/dev/null || echo ".env saknas - skapa den manuellt!"

echo ""
echo "Skapar Python virtual environment..."
cd "$INSTALL_DIR"
python3 -m venv venv
source venv/bin/activate

echo ""
echo "Installerar Python-paket..."
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "Installerar systemd-service..."
cp "$SCRIPT_DIR/nisse.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable nisse.service

echo ""
echo "Sätter rättigheter..."
chown -R pi:pi "$INSTALL_DIR"
chmod +x "$INSTALL_DIR/nisse.py"

echo ""
echo "Installation klar!"
echo ""
echo "För att starta Nisse:"
echo "   sudo systemctl start nisse"
echo ""
echo "För att se loggar:"
echo "   sudo journalctl -u nisse -f"
echo ""
echo "För att stoppa:"
echo "   sudo systemctl stop nisse"
echo ""
echo "GPIO-koppling:"
echo "   PIR OUT  → GPIO17 (fysisk pin 11)"
echo "   PIR VCC  → 5V (fysisk pin 2 eller 4)"
echo "   PIR GND  → GND (fysisk pin 6)"
echo ""
echo "🎄 God jul! 🎄"

