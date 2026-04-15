#!/bin/bash
# Message Dashboard - native macOS App
# Aufruf: bash ~/AssistantDev/scripts/start_dashboard.sh
#         oder direkt: python3 ~/AssistantDev/src/message_dashboard.py
set -e
cd "$HOME/AssistantDev"
exec /usr/bin/python3 "$HOME/AssistantDev/src/message_dashboard.py" "$@"
