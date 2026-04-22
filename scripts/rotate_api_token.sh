#!/bin/bash
# rotate_api_token.sh — Rotiert den Backend-API-Token und synchronisiert ihn
# mit der .env.production im Frontend-Repo.
#
# Nutzung:
#   bash ~/AssistantDev/scripts/rotate_api_token.sh
#
# Was passiert:
#   1. Neuer urlsafe 43-Char-Token generieren
#   2. config/api_auth.json im Backend updaten
#   3. frontend/.env.production updaten
#   4. Backend deployen (Server neu starten -> uebernimmt neuen Token)
#   5. Frontend-Repo committen + pushen (Lovable baut automatisch mit neuem Token)
#
# Bricht ab, wenn einer der Schritte fehlschlaegt — die Datei bleibt in
# konsistentem Zustand.

set -eu

BACKEND="$HOME/AssistantDev"
FRONTEND="$BACKEND/frontend"
AUTH_JSON="$BACKEND/config/api_auth.json"
ENV_FILE="$FRONTEND/.env.production"

[ -f "$AUTH_JSON" ] || { echo "✗ $AUTH_JSON fehlt"; exit 1; }
[ -f "$ENV_FILE" ]  || { echo "✗ $ENV_FILE fehlt"; exit 1; }

# 1. neuer Token
NEW_TOKEN=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
echo "  neuer Token: ${NEW_TOKEN:0:8}…${NEW_TOKEN: -8}"

# 2. Backend-Config updaten
python3 -c "
import json
p = '$AUTH_JSON'
d = json.load(open(p))
d['api_token'] = '$NEW_TOKEN'
d['rotated'] = '$(date +%Y-%m-%d)'
json.dump(d, open(p, 'w'), indent=2)
"
echo "  ✓ $AUTH_JSON aktualisiert"

# 3. .env.production im Frontend updaten
#    sed -i '' funktioniert auf macOS (BSD sed)
sed -i '' "s|^VITE_API_TOKEN=.*|VITE_API_TOKEN=$NEW_TOKEN|" "$ENV_FILE"
grep -q "^VITE_API_TOKEN=$NEW_TOKEN" "$ENV_FILE" || {
    echo "✗ .env.production Update fehlgeschlagen"; exit 1;
}
echo "  ✓ $ENV_FILE aktualisiert"

# 4. Backend neu deployen
bash "$BACKEND/scripts/deploy.sh" >/dev/null 2>&1
echo "  ✓ Backend redeployed"

# 5. Frontend-Repo committen + pushen (Lovable baut automatisch)
cd "$FRONTEND"
git add .env.production
git commit -m "chore: API-Token rotiert ($(date +%Y-%m-%d))"
git push
echo "  ✓ Frontend committed + gepushed (Lovable rebuildet)"

echo ""
echo "Token-Rotation abgeschlossen."
