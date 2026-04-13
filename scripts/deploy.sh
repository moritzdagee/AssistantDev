#!/bin/zsh
# Deploy: Dateien ins App-Bundle kopieren, Server neustarten, testen, committen
set -e

cd ~/AssistantDev

echo "Kopiere Dateien ins App-Bundle..."
cp src/web_server.py /Applications/Assistant.app/Contents/Resources/
cp src/search_engine.py /Applications/Assistant.app/Contents/Resources/

echo "Server neustarten..."
pkill -f web_server.py || true
sleep 3

echo "Teste API..."
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/api/agents)

if [ "$RESPONSE" = "200" ]; then
    echo "API antwortet OK (200). Deploy erfolgreich."
    DATUM=$(date +%Y-%m-%d_%H%M)
    git add -A
    git commit -m "deploy-${DATUM}"
    git push
    echo "Commit und Push erledigt."
else
    echo "FEHLER: API antwortet mit Status ${RESPONSE}. Deploy fehlgeschlagen!"
    exit 1
fi
