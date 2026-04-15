#!/bin/zsh
# Claude Code mit einer Aufgabe starten, optional auf neuem Feature-Branch
set -e

if [ -z "$1" ]; then
    echo "Fehler: Aufgabe fehlt. Verwendung: $0 \"<aufgabe>\" [branch-name]"
    exit 1
fi

AUFGABE="$1"
BRANCH="$2"

cd ~/AssistantDev

if [ -n "$BRANCH" ]; then
    echo "Erstelle Feature-Branch: ${BRANCH}"
    ~/AssistantDev/scripts/new_feature.sh "$BRANCH"
fi

echo "$AUFGABE" > /tmp/ct.md
/Users/moritzcremer/.local/bin/claude --allowedTools Edit,Write,Bash,Read --print < /tmp/ct.md
