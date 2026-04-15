# Troubleshooting

## Web Server

### Port 8080 belegt
```bash
lsof -ti:8080 | xargs kill -9
python3 ~/AssistantDev/src/web_server.py
```

### Browser zeigt 404
Ursache: `@app.route('/')` oder HTML-Template fehlt.
Log prüfen: `tail ~/Library/Logs/assistant_web.log`

### Rate Limit (429)
Anthropic-Limit: 30.000 Input-Tokens/Minute.
- Neue Session mit + Neu starten
- Memory Folder Suche mit spezifischen Keywords statt alles laden
- Rate Limit erhöhen: console.anthropic.com → Account → Limits

### Agent-Modal erscheint nicht
1. Hard Reload: ⌘+Shift+R
2. DevTools → Console auf JS-Fehler prüfen
3. Server neu starten

### CREATE_EMAIL öffnet Apple Mail nicht
AppleScript braucht Accessibility-Rechte für Terminal/App.
Fallback: "✉ In Apple Mail öffnen" Button (mailto: Link) funktioniert immer.

---

## Email Watcher

### PermissionError auf iCloud-Ordner
Ursache: LaunchAgent hat keine iCloud-Berechtigung.
Lösung: Assistant.app statt LaunchAgent verwenden → App bekommt volle Rechte.

### Emails werden nicht geroutet
1. `ROUTING` Liste in `src/email_watcher.py` prüfen
2. Agent-Ordner muss in `claude_datalake/config/agents/` existieren
3. Log: `tail ~/Library/Logs/assistant_mail.log`

### Processed-Log korrupt
```bash
rm ~/.emailwatcher_processed.json
```
Alle Emails werden beim nächsten Start neu verarbeitet.

---

## Assistant.app

### App startet nicht
```bash
# Test direkt
python3 ~/AssistantDev/src/app.py

# Neu bauen
cd ~/AssistantDev
python3 setup.py py2app --dist-dir build
cp -r build/Assistant.app /Applications/
```

### Services starten nicht aus der App
Full Disk Access prüfen:
System Settings → Privacy & Security → Full Disk Access → Assistant.app ✓

### App neu bauen nach Code-Änderungen
Nur nötig wenn `src/app.py` oder `setup.py` geändert wurden.
Änderungen in `web_server.py` oder `email_watcher.py` wirken sofort.

---

## Historische E-Mails exportieren

Das Script `export_existing_emails.applescript` exportiert alle E-Mails der letzten 12 Monate aus Apple Mail in den `email_inbox/`-Ordner, damit der Email Watcher sie verarbeiten kann.

### Ausfuehren
```bash
osascript ~/AssistantDev/scripts/export_existing_emails.applescript
```

Das Script durchsucht alle Mailboxen (Inbox, Sent, Unterordner) ausser Trash und Junk. Duplikate werden automatisch uebersprungen (gleicher Dateiname = gleicher Tag + Betreff).

### Nach dem Export
- Der Email Watcher laeuft normal drueber und routet alle exportierten E-Mails zu den passenden Agenten
- Duplikat-Schutz ueber `~/.emailwatcher_processed.json` ist automatisch aktiv — bereits verarbeitete Mails werden nicht doppelt geroutet

### Empfehlung
- Am besten abends starten — bei 1000+ Mails kann der Export einige Minuten dauern
- Fortschritt wird im Terminal angezeigt: `Exportiere Mail X von Y: [Betreff]`
- Am Ende erscheint eine Zusammenfassung: `X exportiert, Y uebersprungen (Duplikate)`

---

## Kontakte aus E-Mails extrahieren

Das Script `extract_contacts.py` liest alle E-Mails im `email_inbox/` Ordner und extrahiert Kontaktdaten.

### Ausfuehren
```bash
python3 ~/AssistantDev/scripts/extract_contacts.py
```

### Was passiert
1. Liest die neuesten 500 `.eml` Dateien aus `email_inbox/`
2. Extrahiert Absender-Name und Email aus dem Header
3. Analysiert die E-Mail-Signatur via Claude API (Haiku — guenstig und schnell)
4. Findet: Name, Email, Telefon, Mobil, Unternehmen, Jobtitel, Website, Adresse
5. Dedupliziert nach Email-Adresse (vollstaendigster Datensatz gewinnt)
6. Ueberspringt automatisierte Absender (noreply, notifications, etc.)

### Output
- **Excel:** `claude_outputs/contacts_[datum].xlsx` — wird automatisch geoeffnet
- **vCard:** `claude_outputs/contacts_[datum].vcf` — direkt importierbar in Apple Contacts

### API-Kosten
Nutzt Claude Haiku (guenstigstes Modell). Bei 500 E-Mails ca. $0.10-0.20.
Limit auf 500 E-Mails pro Durchlauf eingestellt.

### Troubleshooting
- **"anthropic nicht installiert":** `pip3 install anthropic`
- **"openpyxl nicht installiert":** `pip3 install openpyxl` (fuer Excel-Export)
- **Wenige Kontakte gefunden:** Viele E-Mails haben keine Signatur. Header-Extraktion findet trotzdem Name + Email.

---

## Python Libraries

### Fehlende Library
```bash
pip3 install anthropic flask requests beautifulsoup4 PyPDF2 \
     python-docx openpyxl reportlab python-pptx \
     rumps py2app google-generativeai --break-system-packages
```

### py2app Build-Fehler
```bash
rm -rf ~/AssistantDev/build ~/AssistantDev/dist
cd ~/AssistantDev && python3 setup.py py2app --dist-dir build
```
