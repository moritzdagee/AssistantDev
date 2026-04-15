#!/bin/bash
# rollback.sh — Interaktives Rollback von web_server.py oder search_engine.py
# Listet Backups, fragt Auswahl ab, kompiliert, deployt, startet Server neu.

set -e

SRC="$HOME/AssistantDev/src"
RESOURCES="/Applications/Assistant.app/Contents/Resources"

echo "╔════════════════════════════════════════════════════╗"
echo "║           AssistantDev — Rollback                  ║"
echo "╚════════════════════════════════════════════════════╝"
echo ""

# Sammle Backups
BACKUPS=()
while IFS= read -r f; do
    [ -f "$f" ] && BACKUPS+=("$f")
done < <(ls -1t "$SRC"/web_server.py.backup_* "$SRC"/search_engine.py.backup_* 2>/dev/null)

if [ ${#BACKUPS[@]} -eq 0 ]; then
    echo "❌ Keine Backups gefunden in $SRC"
    exit 1
fi

echo "Verfügbare Backups:"
echo ""
i=1
for f in "${BACKUPS[@]}"; do
    BASE=$(basename "$f")
    DATE=$(echo "$BASE" | sed -E 's/.*backup_([0-9]{8}_[0-9]{6}).*/\1/')
    PRETTY=$(echo "$DATE" | sed -E 's/([0-9]{4})([0-9]{2})([0-9]{2})_([0-9]{2})([0-9]{2})([0-9]{2})/\1-\2-\3 \4:\5:\6/')
    printf "  [%2d]  %-55s  %s\n" "$i" "$BASE" "$PRETTY"
    i=$((i + 1))
done

echo ""
printf "Backup-Nummer wählen (oder 'q' zum Abbrechen): "
read -r CHOICE

if [ "$CHOICE" = "q" ] || [ "$CHOICE" = "Q" ] || [ -z "$CHOICE" ]; then
    echo "Abgebrochen."
    exit 0
fi

if ! [[ "$CHOICE" =~ ^[0-9]+$ ]] || [ "$CHOICE" -lt 1 ] || [ "$CHOICE" -gt ${#BACKUPS[@]} ]; then
    echo "❌ Ungültige Auswahl."
    exit 1
fi

SELECTED="${BACKUPS[$((CHOICE - 1))]}"
BASENAME=$(basename "$SELECTED")
# Zielname: alles vor .backup_
TARGET_NAME=$(echo "$BASENAME" | sed -E 's/\.backup_[0-9]+_[0-9]+.*$//')
TARGET="$SRC/$TARGET_NAME"

echo ""
echo "→ Backup:  $SELECTED"
echo "→ Ziel:    $TARGET"
printf "Wiederherstellen? [j/N] "
read -r CONFIRM

if [ "$CONFIRM" != "j" ] && [ "$CONFIRM" != "J" ] && [ "$CONFIRM" != "y" ] && [ "$CONFIRM" != "Y" ]; then
    echo "Abgebrochen."
    exit 0
fi

# 1. Sicherheits-Backup der aktuellen Datei
if [ -f "$TARGET" ]; then
    SAFETY="$TARGET.backup_$(date +%Y%m%d_%H%M%S)_prerollback"
    cp "$TARGET" "$SAFETY"
    echo "💾 Sicherheits-Backup: $(basename "$SAFETY")"
fi

# 2. Restore
cp "$SELECTED" "$TARGET"
echo "✅ Datei wiederhergestellt: $TARGET_NAME"

# 3. Syntax-Check
echo ""
echo "🔍 Syntax-Check..."
if ! python3 -m py_compile "$TARGET"; then
    echo "❌ Syntax-Fehler in wiederhergestellter Datei. Rollback abgebrochen."
    echo "   Sicherheits-Backup liegt in $SAFETY"
    exit 1
fi
echo "✅ Syntax OK"

# 4. Deploy ins App-Bundle
if [ -d "$RESOURCES" ]; then
    cp "$TARGET" "$RESOURCES/"
    echo "✅ Deployed nach $RESOURCES/"
else
    echo "⚠️  App-Bundle nicht gefunden, Deploy übersprungen"
fi

# 5. Server neu starten
echo ""
echo "🔄 Server wird neu gestartet..."
pkill -f web_server.py 2>/dev/null || true
sleep 3

# 6. Healthcheck
HTTP_STATUS="000"
for _ in $(seq 1 10); do
    HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/ 2>/dev/null || echo "000")
    [ "$HTTP_STATUS" != "000" ] && break
    sleep 1
done

echo ""
if [ "$HTTP_STATUS" != "000" ]; then
    echo "╔════════════════════════════════════════════════════╗"
    echo "║  ✅ ROLLBACK ERFOLGREICH                           ║"
    echo "╠════════════════════════════════════════════════════╣"
    printf "║  Datei:  %-42s║\n" "$TARGET_NAME"
    printf "║  HTTP:   %-42s║\n" "$HTTP_STATUS (Port 8080)"
    echo "╚════════════════════════════════════════════════════╝"
else
    echo "╔════════════════════════════════════════════════════╗"
    echo "║  ⚠️  ROLLBACK MIT WARNUNG                           ║"
    echo "╠════════════════════════════════════════════════════╣"
    echo "║  Datei wurde wiederhergestellt, aber Port 8080     ║"
    echo "║  antwortet nicht. Server manuell prüfen:           ║"
    echo "║    bash ~/AssistantDev/scripts/status.sh           ║"
    echo "╚════════════════════════════════════════════════════╝"
    exit 1
fi
