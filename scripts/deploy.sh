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
# Identify web server PID: either renamed bundle process ("AssistantDev WebServer")
# or direct invocation of web_server.py. Prefer the listener on :8080.
PID=$(lsof -tiTCP:8080 -sTCP:LISTEN 2>/dev/null | head -1)
if [ -z "$PID" ]; then
    PID=$(pgrep -f "web_server.py" 2>/dev/null | head -1 || true)
fi
if [ -n "$PID" ]; then
    echo "[DEPLOY] Sende SIGTERM an PID $PID..."
    kill -TERM "$PID" 2>/dev/null || true

    for i in $(seq 1 35); do
        if ! kill -0 "$PID" 2>/dev/null; then
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
    echo "[DEPLOY] Kein laufender Web-Server gefunden"
fi

# 3. Neuen Prozess starten — via system python weil das Bundle-Python
# setproctitle nicht installiert hat (bricht beim Import).
echo "[DEPLOY] Starte neuen Server..."
LOG="$HOME/Library/Logs/Assistant/assistant.log"
nohup /usr/bin/python3 -u "$SRC/app.py" >> "$LOG" 2>&1 &
disown
sleep 2

# 4. Healthcheck mit Retry (Server braucht 1-5s bis er Requests annimmt)
HTTP_STATUS="000"
for i in $(seq 1 15); do
    HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/agents 2>/dev/null || echo "000")
    [ "$HTTP_STATUS" = "200" ] && break
    sleep 1
done
if [ "$HTTP_STATUS" = "200" ]; then
    echo "[DEPLOY] Healthcheck OK (HTTP $HTTP_STATUS)"
    echo "=== Deploy erfolgreich ==="
else
    echo "[DEPLOY] WARNUNG: Healthcheck fehlgeschlagen (HTTP $HTTP_STATUS)"
    echo "=== Deploy moeglicherweise fehlgeschlagen — Server pruefen ==="
    exit 1
fi
