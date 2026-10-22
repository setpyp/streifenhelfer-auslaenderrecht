#!/usr/bin/env bash
# Einrichtung auf Raspberry Pi OS (Bookworm/Trixie, 64-Bit). Im Repository-Ordner ausführen:
#   bash pi/install.sh                              # Programm + Autostart
#   bash pi/install.sh --hotspot NAME PASSWORT      # zusätzlich WLAN-Hotspot für die Handy-Ansicht
set -euo pipefail
cd "$(dirname "$0")/.."
REPO="$(pwd)"
MODELL=vosk-model-small-de-0.15

sudo apt-get update
sudo apt-get install -y alsa-utils espeak-ng nodejs python3-venv python3-gpiozero python3-lgpio unzip wget
# Zugriff auf Headset-Tasten (/dev/input), Audio und GPIO
sudo usermod -aG input,audio,gpio "$USER"

# Python-Umgebung mit Vosk (gpiozero aus dem System mitbenutzen)
python3 -m venv --system-site-packages pi/venv
pi/venv/bin/pip install --upgrade pip vosk

# Deutsches Spracherkennungsmodell (offline, ca. 45 MB)
if [ ! -d pi/modell ]; then
  wget -q --show-progress "https://alphacephei.com/vosk/models/$MODELL.zip" -O "/tmp/$MODELL.zip"
  unzip -q "/tmp/$MODELL.zip" -d /tmp
  mv "/tmp/$MODELL" pi/modell
  rm "/tmp/$MODELL.zip"
fi

# Autostart beim Einschalten
sudo tee /etc/systemd/system/streifenhelfer.service >/dev/null <<EOF
[Unit]
Description=Streifenhelfer Sprachsteuerung (Prototyp)
After=sound.target network.target

[Service]
User=$USER
WorkingDirectory=$REPO
ExecStart=$REPO/pi/venv/bin/python $REPO/pi/streifenhelfer_pi.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now streifenhelfer

if [ "${1:-}" = "--hotspot" ]; then
  sudo nmcli device wifi hotspot ifname wlan0 ssid "$2" password "$3"
  sudo nmcli connection modify Hotspot connection.autoconnect yes
  echo "Hotspot '$2' aktiv. Handy verbinden und http://10.42.0.1:8080/index.html?quelle=pi öffnen."
fi
echo "Fertig. Status: systemctl status streifenhelfer"
