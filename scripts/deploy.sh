#!/bin/bash
# deploy.sh — Graceful Deployment fuer AssistantDev Web Server
# Sendet SIGTERM und wartet auf sauberes Ende, bevor der neue Prozess startet.

set -e

RESOURCES="/Applications/Assistant.app/Contents/Resources"
SRC="$HOME/AssistantDev/src"

echo "=== AssistantDev Deploy ==="

# 1. Dateien kopieren
echo "[DEPLOY] Kopiere Source-Dateien..."
cp "$SRC/web_server.py" "$RESOURCES/"
cp "$SRC/search_engine.py" "$RESOURCES/"
echo "[DEPLOY] Dateien kopiert nach $RESOURCES/"

# 2. Graceful Shutdown: SIGTERM senden und auf Ende warten
PID=$(pgrep -f "web_server.py" 2>/dev/null || true)
if [ -n "$PID" ]; then
    echo "[DEPLOY] Sende SIGTERM an PID $PID..."
    kill -TERM "$PID" 2>/dev/null || true

    for i in $(seq 1 35); do
        if ! pgrep -f "web_server.py" > /dev/null 2>&1; then
            echo "[DEPLOY] Prozess sauber beendet nach ${i}s"
            break
        fi
        if [ "$i" -eq 35 ]; then
            echo "[DEPLOY] Timeout nach 35s — sende SIGKILL"
            kill -KILL "$PID" 2>/dev/null || true
            sleep 1
        fi
        sleep 1
    done
else
    echo "[DEPLOY] Kein laufender web_server.py Prozess gefunden"
fi

# 3. Neuen Prozess starten
echo "[DEPLOY] Starte neuen Server..."
open /Applications/Assistant.app
sleep 3

# 4. Healthcheck
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/api/agents 2>/dev/null || echo "000")
if [ "$HTTP_STATUS" = "200" ]; then
    echo "[DEPLOY] Healthcheck OK (HTTP $HTTP_STATUS)"
    echo "=== Deploy erfolgreich ==="
else
    echo "[DEPLOY] WARNUNG: Healthcheck fehlgeschlagen (HTTP $HTTP_STATUS)"
    echo "=== Deploy moeglicherweise fehlgeschlagen — Server pruefen ==="
    exit 1
fi
