#!/usr/bin/env bash
#Then it’s a PCManFM setting, not your file.
#Open File Manager → go to:
#Edit → Preferences → General
#Set:
# “Don’t ask options on launch executable file”
set -euo pipefail

# --- Paths ---
BASE_DIR="/home/pi/magic"
REPO_DIR="${BASE_DIR}/Magic_Story"
VENV_DIR="${BASE_DIR}/venv"

# --- Config (edit these once and forget) ---
# Choose STT provider: "google" or "whisper" if google is commented out it's only using the specified whisper server
#Note that this google version struggles with a full classroom trying to use it
#: "${STT_PROVIDER:=google}" 
: "${STT_PROVIDER:=whisper}"

# Whisper server URL (only used if STT_PROVIDER=whisper)
#: "${WHISPER_BASE_URL:=http://10.110.5.182:9000}"
: "${WHISPER_BASE_URL:=http://10.110.65.183:9000}"
# Optional Ollama override (if you want to change later)
# : "${OLLAMA_BASE_URL:=http://10.110.5.182:11434}"

# --- Go to repo ---
cd "${REPO_DIR}"

# --- Activate venv ---
source "${VENV_DIR}/bin/activate"

# --- Export environment variables for the app ---
export STT_PROVIDER
export WHISPER_BASE_URL
# export OLLAMA_BASE_URL

# If you want to force the LCD X display explicitly:
export DISPLAY=:0

echo "Launching with STT_PROVIDER=$STT_PROVIDER"

# --- Launch ---
exec python magic_ui.py
