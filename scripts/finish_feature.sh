#!/bin/zsh
# Feature-Branch in develop mergen und aufraeumen
set -e

if [ -z "$1" ]; then
    echo "Fehler: Feature-Name fehlt. Verwendung: $0 <feature-name>"
    exit 1
fi

FEATURE="$1"

cd ~/AssistantDev
git checkout develop
git merge "feature/${FEATURE}"
git branch -d "feature/${FEATURE}"
git push origin develop

echo "Feature ${FEATURE} in develop gemerged."
git log --oneline -3
