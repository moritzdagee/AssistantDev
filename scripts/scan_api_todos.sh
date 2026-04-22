#!/bin/bash
# scan_api_todos.sh — Zeigt alle Backend-Requests die Lovable im Frontend-Repo
# offen gelassen hat. Zwei Formate:
#
#   1. Inline-Marker im Code: TODO(API): / NEEDS_BACKEND / // @api
#      (idealerweise mit Request/Response-Shape)
#   2. Dedizierte Markdown-Dateien: src/components/BACKEND_TODO_*.md
#      (Lovables neuer Standard fuer umfangreichere TODOs)
#
# Aufruf:
#   bash ~/AssistantDev/scripts/scan_api_todos.sh

set -u

FRONTEND_SRC="$HOME/AssistantDev/frontend/src"
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

if [ ! -d "$FRONTEND_SRC" ]; then
    echo "Frontend-Verzeichnis fehlt: $FRONTEND_SRC"
    exit 1
fi

cd "$FRONTEND_SRC"

total_inline=0
total_md=0
found_any=0

# ── 1. Inline-Marker im Code ────────────────────────────────────────────────
echo -e "${BOLD}─── Inline-Marker im Code ───${NC}"
for pattern in "TODO(API):" "NEEDS_BACKEND" "// @api"; do
    out=$(grep -rn --include='*.ts' --include='*.tsx' --include='*.js' \
                  --include='*.jsx' "$pattern" . 2>/dev/null || true)
    if [ -n "$out" ]; then
        count=$(echo "$out" | wc -l | tr -d ' ')
        total_inline=$((total_inline + count))
        found_any=1
        echo -e "\n${YELLOW}== $pattern ==${NC}  ($count)"
        echo "$out" | sed 's/^/  /'
    fi
done
[ "$total_inline" = "0" ] && echo "  (keine)"

# ── 2. BACKEND_TODO_*.md Dateien ────────────────────────────────────────────
echo ""
echo -e "${BOLD}─── Backend-TODO-Dateien (src/components/BACKEND_TODO_*.md) ───${NC}"
shopt -s nullglob 2>/dev/null || true
todos=( components/BACKEND_TODO_*.md )
if [ ${#todos[@]} -eq 0 ] || [ ! -f "${todos[0]}" ]; then
    echo "  (keine)"
else
    for f in "${todos[@]}"; do
        total_md=$((total_md + 1))
        found_any=1
        lines=$(wc -l < "$f" | tr -d ' ')
        # erste Ueberschrift (# ...) als Titel, sonst erste Zeile
        title=$(grep -m1 '^#' "$f" 2>/dev/null | sed 's/^#\+\s*//' || head -1 "$f")
        [ -z "$title" ] && title=$(head -1 "$f")
        echo ""
        echo -e "${CYAN}▸ ${BOLD}${f#components/}${NC}  (${lines} Zeilen)"
        echo -e "  ${title}"
        # Erste ~8 Zeilen nicht-leer zeigen, eingerueckt
        grep -v '^$' "$f" 2>/dev/null | head -8 | sed 's/^/    /' 2>/dev/null
    done
fi

# ── 3. Claude → Lovable TODOs (im AssistantDev-Repo) ────────────────────────
echo ""
echo -e "${BOLD}─── Claude → Lovable TODOs (docs/lovable/FRONTEND_TODO_*.md) ───${NC}"
LOVABLE_DIR="$HOME/AssistantDev/docs/lovable"
total_c2l=0
if [ -d "$LOVABLE_DIR" ]; then
    shopt -s nullglob 2>/dev/null || true
    c2l_files=( "$LOVABLE_DIR"/FRONTEND_TODO_*.md )
    if [ ${#c2l_files[@]} -eq 0 ] || [ ! -f "${c2l_files[0]}" ]; then
        echo "  (keine)"
    else
        for f in "${c2l_files[@]}"; do
            total_c2l=$((total_c2l + 1))
            found_any=1
            lines=$(wc -l < "$f" | tr -d ' ')
            title=$(grep -m1 '^#' "$f" 2>/dev/null | sed 's/^#\+\s*//')
            [ -z "$title" ] && title=$(head -1 "$f")
            echo ""
            echo -e "${CYAN}▸ ${BOLD}$(basename "$f")${NC}  (${lines} Zeilen)"
            echo -e "  ${title}"
        done
    fi
else
    echo "  (Ordner fehlt — docs/lovable/ nicht angelegt)"
fi

# ── Summary ──────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}─── Zusammenfassung ───${NC}"
if [ "$found_any" = "0" ]; then
    echo -e "${GREEN}✓ Keine offenen TODOs in beide Richtungen.${NC}"
else
    echo -e "  Lovable → Claude (Inline):      ${total_inline}"
    echo -e "  Lovable → Claude (TODO-Files):  ${total_md}"
    echo -e "  Claude → Lovable (FRONTEND):    ${total_c2l}"
    echo ""
    echo "  Lovable → Claude abarbeiten (Backend-Arbeit):"
    echo "    • TODO-Datei lesen → Route in src/web_server.py implementieren"
    echo "    • deploy.sh + testen + committen"
    echo "    • Datei umbenennen in FIXED_*.md (Frontend-Repo)"
    echo ""
    echo "  Claude → Lovable abarbeiten (Frontend-Arbeit, von Lovable):"
    echo "    • Datei liegt public in docs/lovable/ auf github.com/moritzdagee/AssistantDev"
    echo "    • Nach Fix: umbenennen in FIXED_*.md (docs/lovable/)"
fi
