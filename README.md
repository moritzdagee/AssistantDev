# AssistantDev

Persönliches KI-System — Codebase und Entwicklungsumgebung.

## Struktur

```
AssistantDev/
├── src/
│   ├── app.py            ← Menu Bar App (Einstiegspunkt)
│   ├── web_server.py     ← Flask Web Interface (localhost:8080)
│   └── email_watcher.py  ← Email → Agent Memory Routing
├── docs/
│   ├── architecture.md   ← Systemarchitektur
│   ├── changelog.md      ← Entwicklungslog
│   └── troubleshooting.md
├── build/                ← py2app Output (nicht in Git)
├── setup.py              ← App Builder
└── README.md
```

## Starten (Entwicklung)

```bash
# Web Server
python3 ~/AssistantDev/src/web_server.py

# Email Watcher
python3 ~/AssistantDev/src/email_watcher.py

# Menu Bar App (ohne zu bauen)
python3 ~/AssistantDev/src/app.py
```

## App bauen

```bash
cd ~/AssistantDev
python3 setup.py py2app --dist-dir build
cp -r build/Assistant.app /Applications/
```

## Logs

```
~/Library/Logs/assistant_web.log   ← Web Server
~/Library/Logs/assistant_mail.log  ← Email Watcher
```

## Konfiguration

Alle Konfigurationen liegen in iCloud:
```
~/Library/Mobile Documents/com~apple~CloudDocs/Downloads shared/claude_datalake/
├── config/
│   ├── agents/*.txt     ← Agent System Prompts
│   └── models.json      ← API Keys + Modelle
├── [agent]/
│   ├── memory/          ← Dateien, Emails, URLs
│   └── _index.json      ← Konversationsindex
├── email_inbox/         ← Eingehende Emails von Apple Mail
└── claude_outputs/      ← Generierte Word/Excel/PDF/PPTX Dateien
```
