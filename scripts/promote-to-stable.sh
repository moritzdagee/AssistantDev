#!/bin/bash
# promote-to-stable.sh
# Kopiert den aktuellen Beta-Code (~/AssistantDev/) nach ~/AssistantDev-Stable/.
#
# Vorgehen:
# 1. Stable-Server auf :8090 sauber stoppen (SIGTERM, Wait, ggf. SIGKILL)
# 2. rsync src/, frontend/dist/, scripts/, config/, resources/, chrome_extensions/
#    Datalake + Logs + Backups bleiben unangetastet (geteilt bzw. instanz-spezifisch)
# 3. Stable-Server wieder starten
# 4. Healthcheck auf :8090
#
# Nicht-destruktiv: Vor dem rsync wird ein Snapshot des Stable-Source unter
# ~/AssistantDev-Stable/backups/promote_<ts>/ angelegt — falls die Promotion
# das Stable-Setup zerschiesst, kannst du via rollback_stable.sh zurueck.

set -e

BETA_DIR="$HOME/AssistantDev"
STABLE_DIR="$HOME/AssistantDev-Stable"
STABLE_PORT="8090"
TS="$(date +%Y-%m-%d_%H-%M-%S)"

if [ ! -d "$BETA_DIR" ]; then
    echo "FEHLER: $BETA_DIR existiert nicht."
    exit 1
fi
if [ ! -d "$STABLE_DIR" ]; then
    echo "FEHLER: $STABLE_DIR existiert nicht. Initial-Setup zuerst laufen lassen."
    exit 1
fi

echo "=== Promote Beta -> Stable ($TS) ==="
echo "From: $BETA_DIR"
echo "To:   $STABLE_DIR"
echo

# --- 1) Stable-Server stoppen ---
STABLE_PID="$(lsof -nP -iTCP:${STABLE_PORT} -sTCP:LISTEN -t 2>/dev/null | head -1)"
if [ -n "$STABLE_PID" ]; then
    echo "[STOP] Stable-Server (PID $STABLE_PID) auf :${STABLE_PORT} -> SIGTERM"
    kill -TERM "$STABLE_PID" 2>/dev/null || true
    for i in 1 2 3 4 5 6 7 8 9 10; do
        sleep 1
        if ! kill -0 "$STABLE_PID" 2>/dev/null; then
            break
        fi
    done
    if kill -0 "$STABLE_PID" 2>/dev/null; then
        echo "[STOP] Hartes SIGKILL nach 10s"
        kill -KILL "$STABLE_PID" 2>/dev/null || true
        sleep 1
    fi
fi

# --- 2) Snapshot des Stable-Source vor Ueberschreibung ---
SNAP="$STABLE_DIR/backups/promote_${TS}"
mkdir -p "$SNAP"
echo "[SNAPSHOT] Aktuellen Stable-Stand sichern -> backups/promote_${TS}/"
for d in src frontend/dist scripts config resources chrome_extensions; do
    if [ -e "$STABLE_DIR/$d" ]; then
        mkdir -p "$SNAP/$(dirname "$d")"
        cp -R "$STABLE_DIR/$d" "$SNAP/$d"
    fi
done

# --- 3) rsync von Beta nach Stable ---
echo "[SYNC] rsync Beta-Source -> Stable"
rsync -a --delete \
    "$BETA_DIR/src/" "$STABLE_DIR/src/"
rsync -a --delete \
    "$BETA_DIR/frontend/dist/" "$STABLE_DIR/frontend/dist/" 2>/dev/null || true
rsync -a --delete \
    "$BETA_DIR/scripts/" "$STABLE_DIR/scripts/"
rsync -a --delete \
    "$BETA_DIR/resources/" "$STABLE_DIR/resources/" 2>/dev/null || true
rsync -a --delete \
    "$BETA_DIR/chrome_extensions/" "$STABLE_DIR/chrome_extensions/" 2>/dev/null || true
# Konfiguration: nicht delete, damit Stable-spezifische Files erhalten bleiben
rsync -a "$BETA_DIR/config/" "$STABLE_DIR/config/" 2>/dev/null || true
# Top-level Docs
for f in CLAUDE.md README.md changelog.md; do
    if [ -f "$BETA_DIR/$f" ]; then
        cp "$BETA_DIR/$f" "$STABLE_DIR/$f"
    fi
done

# --- 4) Stable-Server wieder starten ---
echo "[START] Stable-Server (:${STABLE_PORT})"
cd "$STABLE_DIR/src"
ASSISTANTDEV_PORT="$STABLE_PORT" /usr/bin/python3 -u web_server.py \
    >> "$STABLE_DIR/logs/web_server.log" 2>&1 &

# --- 5) Healthcheck ---
echo "[HEALTH] Warte auf :${STABLE_PORT}/api/health ..."
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
    sleep 1
    HTTP="$(curl -s -m 2 -o /dev/null -w '%{http_code}' "http://127.0.0.1:${STABLE_PORT}/api/health" || echo 000)"
    if [ "$HTTP" = "200" ]; then
        echo "[HEALTH] OK (HTTP 200) nach ${i}s"
        echo
        echo "=== Promote erfolgreich ==="
        echo "Stable laeuft jetzt mit dem aktuellen Beta-Code-Stand."
        echo "Snapshot des vorherigen Stable: $SNAP"
        exit 0
    fi
done

echo "[HEALTH] FEHLER: Stable-Server antwortet nicht nach 15s."
echo "Snapshot zum Rollback: $SNAP"
echo "Log: $STABLE_DIR/logs/web_server.log"
exit 2
