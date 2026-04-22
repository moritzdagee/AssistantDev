#!/bin/bash
# scan_api_todos.sh — Zeigt Backend-Requests die Lovable im Frontend-Code
# als offene TODOs markiert hat.
#
# Konvention: Lovable (oder Claude im Frontend-Repo) markiert fehlende
# Backend-Funktionalitaet mit einem der Marker:
#
#   TODO(API):    normaler TODO, mittlere Prio
#   NEEDS_BACKEND relevant, blockiert ein Feature
#   // @api       Doc-Tag fuer spaetere Abarbeitung
#
# Der Text nach dem Marker beschreibt was am Backend gebaut werden soll —
# idealerweise mit Request/Response-Shape und Route.
#
# Beispiel (im Frontend-Code):
#   // TODO(API): POST /api/chat {session_id, agent, message} -> {reply}
#
# Aufruf:
#   bash ~/AssistantDev/scripts/scan_api_todos.sh

set -u

FRONTEND="$HOME/AssistantDev/frontend/src"
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

if [ ! -d "$FRONTEND" ]; then
    echo "Frontend-Verzeichnis fehlt: $FRONTEND"
    exit 1
fi

cd "$FRONTEND"

total=0
found_any=0

for pattern in "TODO(API):" "NEEDS_BACKEND" "// @api"; do
    out=$(grep -rn --include='*.ts' --include='*.tsx' --include='*.js' \
                  --include='*.jsx' "$pattern" . 2>/dev/null || true)
    if [ -n "$out" ]; then
        count=$(echo "$out" | wc -l | tr -d ' ')
        total=$((total + count))
        found_any=1
        echo -e "\n${BOLD}${YELLOW}== $pattern ==${NC}  ($count)"
        echo "$out" | sed 's/^/  /'
    fi
done

echo ""
if [ "$found_any" = "0" ]; then
    echo -e "${GREEN}✓ Keine offenen Backend-TODOs im Frontend-Code.${NC}"
else
    echo -e "${BLUE}→ Insgesamt $total Marker gefunden.${NC}"
    echo "  Abarbeiten: neue Routes in src/web_server.py implementieren, danach"
    echo "  Marker im Frontend-Code entfernen oder auf 'FIXED(API):' setzen."
fi
