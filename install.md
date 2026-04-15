# Installation — AssistantDev

## Einmalig: Libraries installieren

```bash
pip3 install anthropic flask requests beautifulsoup4 PyPDF2 \
     python-docx openpyxl reportlab python-pptx \
     rumps py2app google-generativeai --break-system-packages
```

## Ordner einrichten

```bash
cp -r ~/Downloads/AssistantDev ~/AssistantDev
```

## App bauen

```bash
cd ~/AssistantDev
python3 setup.py py2app --dist-dir build
```

## App installieren

```bash
cp -r ~/AssistantDev/build/Assistant.app /Applications/
```

## Alten LaunchAgent entfernen

```bash
launchctl bootout gui/$(id -u)/com.moritz.emailwatcher 2>/dev/null
rm -f ~/Library/LaunchAgents/com.moritz.emailwatcher.plist
```

## Full Disk Access

**System Settings → Privacy & Security → Full Disk Access → + → /Applications/Assistant.app**

## Login Item

**System Settings → General → Login Items & Extensions → + → Assistant.app**

## Starten

```bash
open /Applications/Assistant.app
```

🤖 erscheint in der Menu Bar. Web Server und Email Watcher starten automatisch.

---

## Assistant Memory Clipper (Chrome Extension)

Ersetzt alle bisherigen Bookmarklets (Salesforce, Slack, Web Clipper).
Erkennt automatisch den Seitentyp und extrahiert die relevanten Daten.

1. `chrome://extensions/` oeffnen
2. Entwicklermodus aktivieren (Schalter oben rechts)
3. "Entpackte Erweiterung laden" klicken
4. Ordner auswaehlen: `~/AssistantDev/chrome_extension/assistant_clipper/`
5. Extension-Icon in der Chrome Toolbar anpinnen (Puzzle-Icon → Pin)

**Benutzung:** Auf beliebiger Seite das Extension-Icon klicken → Agent waehlen → Speichern.

**Voraussetzung:** Web Clipper Server laeuft (Port 8081).
Die Assistant.app startet den Server automatisch beim Login.

**Unterstuetzte Seiten:**
- Salesforce Lightning (Lead/Account/Opportunity/Contact/Case)
- Slack (Kanal-Nachrichten)
- Alle anderen Webseiten (Hauptinhalt extrahiert)

---

## Entwicklung (ohne App zu bauen)

```bash
python3 ~/AssistantDev/src/web_server.py     # Web Interface
python3 ~/AssistantDev/src/email_watcher.py  # Email Watcher
python3 ~/AssistantDev/src/app.py            # Menu Bar App direkt
```

Änderungen an web_server.py oder email_watcher.py wirken sofort — kein Rebuild nötig.
Nur bei Änderungen an app.py oder setup.py muss die App neu gebaut werden.
