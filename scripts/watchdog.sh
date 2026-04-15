#!/bin/bash
# watchdog.sh — Einmaliger Check + Auto-Restart von web_server.py
# Wird vom LaunchAgent com.assistantdev.watchdog alle 60s aufgerufen.

SRC="$HOME/AssistantDev/src"
LOG_DIR="$HOME/AssistantDev/logs"
WATCHDOG_LOG="$LOG_DIR/watchdog.log"

mkdir -p "$LOG_DIR"

ts() { date '+%Y-%m-%d %H:%M:%S'; }

port_open() {
    lsof -iTCP:8080 -sTCP:LISTEN >/dev/null 2>&1
}

proc_running() {
    pgrep -f "web_server.py" >/dev/null 2>&1
}

if port_open && proc_running; then
    # Alles gut — kein Log-Eintrag (sonst wächst das Log endlos)
    exit 0
fi

echo "[$(ts)] web_server.py nicht gesund — starte neu" >> "$WATCHDOG_LOG"
echo "[$(ts)]   Port 8080 offen: $(port_open && echo JA || echo NEIN)" >> "$WATCHDOG_LOG"
echo "[$(ts)]   Prozess läuft:   $(proc_running && echo JA || echo NEIN)" >> "$WATCHDOG_LOG"

# Sauber alte Prozess-Reste killen
pkill -f "web_server.py" 2>/dev/null || true
sleep 2

# Neu starten
cd "$SRC" || { echo "[$(ts)]   FEHLER: $SRC nicht gefunden" >> "$WATCHDOG_LOG"; exit 1; }
nohup /usr/bin/python3 -u "$SRC/web_server.py" >> "$WATCHDOG_LOG" 2>&1 &
disown
echo "[$(ts)]   Neustart ausgelöst (PID $!)" >> "$WATCHDOG_LOG"
