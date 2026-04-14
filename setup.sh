#!/bin/bash
# AssistantDev Setup-Skript — Disaster Recovery für neue Maschinen
# Usage: ./setup.sh
#
# Voraussetzung: Repository ist bereits geclont
# Ziel: alle Abhängigkeiten installieren, iCloud-Struktur anlegen, LaunchAgents registrieren

set -e

BASE="$HOME/Library/Mobile Documents/com~apple~CloudDocs/Downloads shared/claude_datalake"
OUTPUTS="$HOME/Library/Mobile Documents/com~apple~CloudDocs/Downloads shared/claude_outputs"
ASSISTANT_DIR="$HOME/AssistantDev"

GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m'

ok() { echo -e "${GREEN}✓${NC} $1"; }
warn() { echo -e "${YELLOW}⚠${NC} $1"; }
err() { echo -e "${RED}✗${NC} $1"; }
info() { echo "  $1"; }

echo "======================================"
echo "  AssistantDev Setup"
echo "======================================"
echo ""

# ─── 3a: Systemvoraussetzungen ──────────────────────────────────────────────
echo "[1/5] Systemvoraussetzungen prüfen..."

if ! command -v brew >/dev/null 2>&1; then
    warn "Homebrew nicht gefunden."
    info "Bitte manuell installieren:"
    info '  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
    BREW_MISSING=1
else
    ok "Homebrew: $(brew --version | head -1)"
fi

if ! command -v python3 >/dev/null 2>&1; then
    err "python3 nicht gefunden! Bitte Python 3.9+ installieren (via brew: brew install python@3.12)"
    exit 1
else
    ok "Python: $(python3 --version)"
fi

# Python-Pakete
REQUIRED_PKGS=(
    "python-docx"
    "openpyxl"
    "reportlab"
    "python-pptx"
    "anthropic"
    "openai"
    "google-generativeai"
    "mistralai"
    "requests"
    "pillow"
    "beautifulsoup4"
    "flask"
)

MISSING_PKGS=()
for pkg in "${REQUIRED_PKGS[@]}"; do
    # Convert package names to import names
    import_name="$pkg"
    case "$pkg" in
        "python-docx") import_name="docx" ;;
        "python-pptx") import_name="pptx" ;;
        "google-generativeai") import_name="google.generativeai" ;;
        "beautifulsoup4") import_name="bs4" ;;
        "pillow") import_name="PIL" ;;
    esac
    if ! python3 -c "import $import_name" >/dev/null 2>&1; then
        MISSING_PKGS+=("$pkg")
    fi
done

if [ ${#MISSING_PKGS[@]} -gt 0 ]; then
    warn "Fehlende Python-Pakete: ${MISSING_PKGS[*]}"
    info "Installiere..."
    pip3 install --user "${MISSING_PKGS[@]}" 2>&1 | tail -5
    ok "Python-Pakete installiert"
else
    ok "Alle Python-Pakete vorhanden"
fi

echo ""

# ─── 3b: Verzeichnisstruktur ────────────────────────────────────────────────
echo "[2/5] Verzeichnisstruktur anlegen..."

DIRS_TO_CREATE=(
    "$BASE/config/agents"
    "$BASE/webclips"
    "$BASE/email_inbox"
    "$OUTPUTS"
)

for dir in "${DIRS_TO_CREATE[@]}"; do
    if [ ! -d "$dir" ]; then
        mkdir -p "$dir"
        ok "Angelegt: $(basename "$dir")"
    else
        info "Existiert: $(basename "$dir")"
    fi
done

# Per Agent: memory/attachments/
if [ -d "$BASE/config/agents" ]; then
    for agent_file in "$BASE/config/agents/"*.txt; do
        [ -f "$agent_file" ] || continue
        basename=$(basename "$agent_file" .txt)
        [[ "$basename" == *".backup_"* ]] && continue
        mem_att="$BASE/$basename/memory/attachments"
        if [ ! -d "$mem_att" ]; then
            mkdir -p "$mem_att"
            ok "Angelegt: $basename/memory/attachments/"
        fi
    done
fi

echo ""

# ─── 3c: LaunchAgents registrieren ──────────────────────────────────────────
echo "[3/5] LaunchAgents prüfen..."

LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
ACTIVE_COUNT=0
if [ -d "$LAUNCH_AGENTS_DIR" ]; then
    for plist in "$LAUNCH_AGENTS_DIR"/com.moritz.* "$LAUNCH_AGENTS_DIR"/com.assistantdev.*; do
        [ -f "$plist" ] || continue
        label=$(basename "$plist" .plist)
        if launchctl list 2>/dev/null | grep -q "$label"; then
            ok "Aktiv: $label"
            ACTIVE_COUNT=$((ACTIVE_COUNT + 1))
        else
            info "Lade: $label"
            if launchctl load "$plist" 2>&1; then
                ok "Geladen: $label"
                ACTIVE_COUNT=$((ACTIVE_COUNT + 1))
            else
                warn "Fehler beim Laden von $label"
            fi
        fi
    done
fi

if [ $ACTIVE_COUNT -eq 0 ]; then
    warn "Keine LaunchAgents gefunden. Bitte manuell unter ~/Library/LaunchAgents/ anlegen."
fi

echo ""

# ─── 3d: App-Deployment ─────────────────────────────────────────────────────
echo "[4/5] Assistant.app prüfen..."

APP_RES="/Applications/Assistant.app/Contents/Resources"
if [ -d "$APP_RES" ]; then
    ok "Assistant.app gefunden"
    cp "$ASSISTANT_DIR/src/web_server.py" "$APP_RES/" 2>/dev/null && info "web_server.py deployed"
    cp "$ASSISTANT_DIR/src/search_engine.py" "$APP_RES/" 2>/dev/null && info "search_engine.py deployed"
else
    warn "Assistant.app nicht gefunden in /Applications/"
    info "Bitte manuell mit py2app bauen: cd ~/AssistantDev && python3 setup.py py2app"
fi

echo ""

# ─── 3e: models.json Template ───────────────────────────────────────────────
echo "[5/5] Config prüfen..."

TEMPLATE="$BASE/config/models.json.template"
if [ ! -f "$TEMPLATE" ]; then
    cat > "$TEMPLATE" << 'EOF'
{
  "providers": {
    "anthropic": {
      "api_key": "YOUR_ANTHROPIC_KEY",
      "default_model": "claude-sonnet-4-6"
    },
    "openai": {
      "api_key": "YOUR_OPENAI_KEY",
      "default_model": "gpt-4o"
    },
    "gemini": {
      "api_key": "YOUR_GEMINI_KEY",
      "default_model": "gemini-2.0-flash"
    },
    "mistral": {
      "api_key": "YOUR_MISTRAL_KEY",
      "default_model": "mistral-large-latest"
    },
    "perplexity": {
      "api_key": "YOUR_PERPLEXITY_KEY",
      "default_model": "sonar"
    }
  }
}
EOF
    ok "Template erstellt: config/models.json.template"
fi

MODELS_JSON="$BASE/config/models.json"
if [ ! -f "$MODELS_JSON" ]; then
    MODELS_STATUS="FEHLT — bitte Template kopieren und API-Keys eintragen:"
    MODELS_OK=0
else
    MODELS_STATUS="vorhanden"
    MODELS_OK=1
fi

ACCESS_CONTROL="$BASE/config/access_control.json"
if [ ! -f "$ACCESS_CONTROL" ]; then
    AC_STATUS="FEHLT — wird beim ersten Web-UI Öffnen angelegt"
else
    AC_STATUS="vorhanden"
fi

echo ""
echo "======================================"
echo "  SETUP ABGESCHLOSSEN"
echo "======================================"
if [ ${#MISSING_PKGS[@]} -gt 0 ]; then
    echo "- Python packages: installiert (${#MISSING_PKGS[@]} nachinstalliert)"
else
    echo "- Python packages: OK"
fi
echo "- Verzeichnisse: angelegt/vorhanden"
echo "- LaunchAgents: $ACTIVE_COUNT aktiv"
echo "- models.json: $MODELS_STATUS"
[ $MODELS_OK -eq 0 ] && echo "    cp $TEMPLATE $MODELS_JSON"
echo "- access_control.json: $AC_STATUS"
echo ""
echo "Nächste Schritte:"
if [ $MODELS_OK -eq 0 ]; then
    echo "  1. cp '$TEMPLATE' '$MODELS_JSON'"
    echo "  2. API-Keys in $MODELS_JSON eintragen"
    echo "  3. Web Server starten: launchctl load ~/Library/LaunchAgents/com.moritz.*"
    echo "  4. http://localhost:8080 öffnen"
else
    echo "  1. Web Server testen: curl http://localhost:8080/agents"
    echo "  2. http://localhost:8080 öffnen"
fi
echo ""
[ -n "${BREW_MISSING:-}" ] && echo "⚠  Homebrew fehlt — bitte vorher installieren (siehe oben)"
