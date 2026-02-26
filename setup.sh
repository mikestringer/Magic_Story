#how to use
#cd ~
#curl -fsSL "https://raw.githubusercontent.com/mikestringer/Magic_Story/main/setup.sh?$(date +%s)" -o setup.sh
#chmod +x setup.sh
#./setup.sh

#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/mikestringer/Magic_Story.git"
BASE_DIR="/home/pi/magic"
REPO_DIR="${BASE_DIR}/Magic_Story"
VENV_DIR="${BASE_DIR}/venv"

echo "== Magic Story Pi Setup =="

if [[ "$(id -u)" -eq 0 ]]; then
  echo "Run as user 'pi' (not root)."
  exit 1
fi

echo "== 1) System packages =="
sudo apt-get update
sudo apt-get install -y \
  git python3 python3-pip python3-venv \
  alsa-utils \
  portaudio19-dev python3-pyaudio libasound2-dev \
  build-essential \
  libsdl2-2.0-0 libsdl2-image-2.0-0 libsdl2-mixer-2.0-0 libsdl2-ttf-2.0-0 \
  libfreetype6 libportmidi0 libjpeg-dev libpng-dev \
  i2c-tools

echo "== 2) Create base dir + venv =="
mkdir -p "${BASE_DIR}"
if [[ ! -d "${VENV_DIR}" ]]; then
  python3 -m venv "${VENV_DIR}"
fi

# shellcheck disable=SC1090
source "${VENV_DIR}/bin/activate"
pip install --upgrade pip setuptools wheel

echo "== 3) Clone or update repo =="
if [[ ! -d "${REPO_DIR}/.git" ]]; then
  git clone "${REPO_URL}" "${REPO_DIR}"
else
  git -C "${REPO_DIR}" pull
fi

echo "== 4) Python deps (venv) =="
pip install --upgrade \
  requests \
  pygame \
  rpi-backlight \
  SpeechRecognition \
  pyaudio \
  adafruit-blinka \
  adafruit-circuitpython-neopixel \
  adafruit-circuitpython-led-animation

echo "== 5) Force USB mic as default ALSA device =="
# Find the first USB mic card number (works well for identical hardware)
USB_CARD_NUM="$(arecord -l 2>/dev/null | awk '/USB/ {gsub("card ",""); print $2; exit}' | tr -d ':')"

if [[ -n "${USB_CARD_NUM}" ]]; then
  echo "Found USB mic at ALSA card ${USB_CARD_NUM}"
  cat > /tmp/asound.conf <<EOF
pcm.!default {
  type plug
  slave.pcm "hw:${USB_CARD_NUM},0"
}
ctl.!default {
  type hw
  card ${USB_CARD_NUM}
}
EOF
  sudo mv /tmp/asound.conf /etc/asound.conf
else
  echo "WARNING: Could not auto-detect USB mic via arecord -l. Leaving ALSA defaults unchanged."
fi

echo "== 6) Disable screen blanking (LXDE session autostart) =="
AUTOSTART_FILE="/etc/xdg/lxsession/LXDE-pi/autostart"
if [[ -f "${AUTOSTART_FILE}" ]]; then
  sudo sed -i '/xset s off/d;/xset -dpms/d;/xset s noblank/d' "${AUTOSTART_FILE}"
  echo "@xset s off" | sudo tee -a "${AUTOSTART_FILE}" >/dev/null
  echo "@xset -dpms" | sudo tee -a "${AUTOSTART_FILE}" >/dev/null
  echo "@xset s noblank" | sudo tee -a "${AUTOSTART_FILE}" >/dev/null
else
  echo "NOTE: autostart file not found at ${AUTOSTART_FILE} (may vary by OS image)."
fi

echo "== 7) Quick sanity checks =="
python -c "import speech_recognition, pygame, requests; print('Python imports OK')"
echo "Repo: ${REPO_DIR}"
echo "Venv: ${VENV_DIR}"
echo
echo "Setup complete."
echo "Test next:"
echo "  cd ${REPO_DIR}"
echo "  source ${VENV_DIR}/bin/activate"
echo "  python test_listener.py"
