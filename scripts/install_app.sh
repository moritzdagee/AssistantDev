#!/bin/bash
# AssistantDev — Installiert die native macOS App unter /Applications/AssistantDev.app
# Aufruf: bash scripts/install_app.sh

set -e

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP_PATH="/Applications/AssistantDev.app"

echo "=== AssistantDev App installieren ==="

# Bundle-Struktur
mkdir -p "$APP_PATH/Contents/MacOS"
mkdir -p "$APP_PATH/Contents/Resources"

# Info.plist
cp "$REPO_DIR/macos_app/Info.plist" "$APP_PATH/Contents/Info.plist"

# Launcher
cp "$REPO_DIR/macos_app/AssistantDev" "$APP_PATH/Contents/MacOS/AssistantDev"
chmod +x "$APP_PATH/Contents/MacOS/AssistantDev"

# Icon
if [ -f "$REPO_DIR/resources/AppIcon.icns" ]; then
    cp "$REPO_DIR/resources/AppIcon.icns" "$APP_PATH/Contents/Resources/AppIcon.icns"
fi

# LaunchServices aktualisieren (damit Spotlight und Finder die App finden)
/System/Library/Frameworks/CoreServices.framework/Versions/A/Frameworks/LaunchServices.framework/Versions/A/Support/lsregister -f "$APP_PATH" 2>/dev/null

echo "=== Installation abgeschlossen ==="
echo "App: $APP_PATH"
echo "Starten: open /Applications/AssistantDev.app"
echo "Oder: Finder → Programme → AssistantDev"
