#!/bin/zsh
# Neuen Feature-Branch von develop erstellen
set -e

if [ -z "$1" ]; then
    echo "Fehler: Feature-Name fehlt. Verwendung: $0 <feature-name>"
    exit 1
fi

FEATURE="$1"

cd ~/AssistantDev
git checkout develop
git pull origin develop
git checkout -b "feature/${FEATURE}"

echo "Feature-Branch feature/${FEATURE} erstellt und ausgecheckt."
echo "Basis: develop (aktuell)"
git status
