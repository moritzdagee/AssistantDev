#!/bin/bash
# sync-frontend.sh
# Pull Lovable-Frontend-Updates + lokal neu bauen + Beta-Server respawn.
# Nach Aufruf laden Beta (:8080) UND die native Beta-App im Dock den
# aktuellen Lovable-Stand.
#
# Stable wird NICHT automatisch mit-promoted (Features auto-promoten
# zerstoert den Stable-Fallback-Sinn — siehe Memory). Wenn der User Stable
# auch nachziehen will, muss er separat scripts/promote-to-stable.sh
# laufen lassen.

set -e

FRONTEND="$HOME/AssistantDev/frontend"
BACKEND="$HOME/AssistantDev"

if [ ! -d "$FRONTEND" ]; then
    echo "FEHLER: $FRONTEND existiert nicht."
    exit 1
fi

echo "=== Frontend Sync (Lovable -> lokales Beta) ==="
echo

# 1) Pull
echo "[1/3] git pull --rebase im frontend/"
cd "$FRONTEND"
git pull --rebase origin main
echo

# 2) Build
if ! command -v npm > /dev/null; then
    echo "FEHLER: npm nicht im PATH. Installation: brew install node"
    exit 1
fi

if [ ! -d "$FRONTEND/node_modules" ] || [ "$FRONTEND/package.json" -nt "$FRONTEND/node_modules/.package-lock.json" ]; then
    echo "[2/3a] npm install (Dependencies fehlen oder veraltet)"
    cd "$FRONTEND"
    npm install --no-audit --no-fund
fi

echo "[2/3b] npm run build"
cd "$FRONTEND"
npm run build
echo

# 3) Beta-Server respawn — laedt neuen dist
echo "[3/3] Beta-Server respawn"
cd "$BACKEND"
bash scripts/deploy.sh
echo

echo "=== Sync erfolgreich ==="
echo "Beta auf :8080 laedt jetzt den aktuellen Lovable-Frontend-Stand."
echo "Stable auf :8090 bleibt unveraendert — bei Bedarf separat:"
echo "  bash scripts/promote-to-stable.sh"
