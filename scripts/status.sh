#!/bin/bash
# status.sh — Schneller Überblick über AssistantDev-System
# Zeigt Status aller Server, Git, Logs und Backups

SRC="$HOME/AssistantDev/src"
LOG_DIR="$HOME/Library/Logs/Assistant"

check_port() {
    local port="$1"
    if lsof -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
        return 0
    fi
    return 1
}

check_proc() {
    # Matches either a Python script path OR the compiled app-bundle binary name.
    # After commit 508796a, services run as "AssistantDev <Name>" binaries rather
    # than `python *.py`, so pgrep -f on the .py name misses them.
    local name="$1"
    local bundle_name="$2"  # optional, e.g. "AssistantDev WebServer"
    if pgrep -f "$name" >/dev/null 2>&1; then
        return 0
    fi
    if [ -n "$bundle_name" ] && pgrep -f "$bundle_name" >/dev/null 2>&1; then
        return 0
    fi
    return 1
}

print_service() {
    local label="$1"
    local port="$2"
    local proc="$3"
    local bundle="$4"  # optional app-bundle process name
    local port_ok=1
    local proc_ok=1
    check_port "$port" && port_ok=0
    check_proc "$proc" "$bundle" && proc_ok=0

    if [ $port_ok -eq 0 ] && [ $proc_ok -eq 0 ]; then
        echo "  ✅ $label  (Port $port: offen, Prozess: läuft)"
    elif [ $port_ok -eq 0 ]; then
        echo "  ⚠️  $label  (Port $port: offen, Prozess: NICHT gefunden)"
    elif [ $proc_ok -eq 0 ]; then
        echo "  ⚠️  $label  (Port $port: geschlossen, Prozess: läuft)"
    else
        echo "  ❌ $label  (Port $port: geschlossen, Prozess: nicht gefunden)"
    fi
}

echo "╔════════════════════════════════════════════════════╗"
echo "║         AssistantDev — System Status               ║"
echo "╚════════════════════════════════════════════════════╝"
echo ""
echo "🔌 Services:"
print_service "web_server.py       " "8080" "web_server.py"         "AssistantDev WebServer"
print_service "web_clipper_server  " "8081" "web_clipper_server.py" "AssistantDev WebClipper"

if check_proc "email_watcher.py" "AssistantDev EmailWatcher"; then
    echo "  ✅ email_watcher.py   (Prozess: läuft)"
else
    echo "  ❌ email_watcher.py   (Prozess: nicht gefunden)"
fi

if check_proc "kchat_watcher.py" "AssistantDev kChatWatcher"; then
    echo "  ✅ kchat_watcher.py   (Prozess: läuft)"
else
    echo "  ❌ kchat_watcher.py   (Prozess: nicht gefunden)"
fi

echo ""
echo "🌿 Git:"
cd "$HOME/AssistantDev" 2>/dev/null || { echo "  ❌ AssistantDev-Verzeichnis nicht gefunden"; exit 1; }
BRANCH=$(git branch --show-current 2>/dev/null)
LAST_COMMIT=$(git log -1 --pretty=format:"  %h  %s  (%cr)" 2>/dev/null)
DIRTY_COUNT=$(git status --short 2>/dev/null | wc -l | tr -d ' ')
echo "  Branch: $BRANCH"
echo "  Letzter Commit:"
echo "$LAST_COMMIT"
if [ "$DIRTY_COUNT" -gt 0 ]; then
    echo "  ⚠️  $DIRTY_COUNT uncommitted Änderung(en)"
else
    echo "  ✅ Working tree sauber"
fi

echo ""
echo "📜 Server-Log (letzte 20 Zeilen von $LOG_DIR/assistant.log):"
if [ -f "$LOG_DIR/assistant.log" ]; then
    tail -20 "$LOG_DIR/assistant.log" | sed 's/^/  /'
else
    echo "  (Log nicht gefunden)"
fi

echo ""
echo "💾 Backups (src/*.backup_*):"
BACKUPS=$(ls -1t "$SRC"/*.backup_* 2>/dev/null)
if [ -z "$BACKUPS" ]; then
    echo "  (keine Backups gefunden)"
else
    COUNT=0
    echo "$BACKUPS" | while read -r f; do
        COUNT=$((COUNT + 1))
        BASE=$(basename "$f")
        DATE=$(echo "$BASE" | sed -E 's/.*backup_([0-9]{8}_[0-9]{6}).*/\1/')
        # Format date: 20260415_065442 → 2026-04-15 06:54:42
        PRETTY=$(echo "$DATE" | sed -E 's/([0-9]{4})([0-9]{2})([0-9]{2})_([0-9]{2})([0-9]{2})([0-9]{2})/\1-\2-\3 \4:\5:\6/')
        echo "  • $BASE  ($PRETTY)"
    done | head -15
    TOTAL=$(echo "$BACKUPS" | wc -l | tr -d ' ')
    if [ "$TOTAL" -gt 15 ]; then
        echo "  … und $((TOTAL - 15)) weitere"
    fi
fi

echo ""
echo "────────────────────────────────────────────────────"
echo "Stand: $(date '+%Y-%m-%d %H:%M:%S')"
