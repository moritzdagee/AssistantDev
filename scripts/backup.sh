#!/bin/bash
# backup.sh — Backup von AssistantDev-Dateien vor Aenderungen
# Nutzung: bash ~/AssistantDev/scripts/backup.sh src/web_server.py src/app.py

TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
BACKUP_DIR="$HOME/AssistantDev/backups/$TIMESTAMP"

if [ $# -eq 0 ]; then
    echo "Nutzung: backup.sh [datei1] [datei2] ..."
    echo "Beispiel: backup.sh src/web_server.py config/models.json"
    exit 1
fi

for file in "$@"; do
    src="$HOME/AssistantDev/$file"
    dst="$BACKUP_DIR/$file"
    mkdir -p "$(dirname "$dst")"
    if [ -f "$src" ]; then
        cp "$src" "$dst"
        echo "✓ Backup: $file → backups/$TIMESTAMP/$file"
    else
        echo "⚠ Nicht gefunden: $file"
    fi
done

echo ""
echo "Backup gespeichert: backups/$TIMESTAMP"
