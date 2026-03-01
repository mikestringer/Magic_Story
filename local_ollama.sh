#!/usr/bin/env bash
export OLLAMA_BASE_URL="http://127.0.0.1:11434"
export OLLAMA_MODEL="gemma2:2b"
DISPLAY=:0 python magic_ui.py --rotation 90
