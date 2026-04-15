# Systemarchitektur

## Überblick

```
                    ┌─────────────────────────────────┐
                    │      Assistant.app (Menu Bar)   │
                    │         src/app.py              │
                    └──────────┬──────────────────────┘
                               │ startet & überwacht
              ┌────────────────┴─────────────────┐
              │                                   │
   ┌──────────▼──────────┐           ┌───────────▼──────────┐
   │   Web Server        │           │   Email Watcher       │
   │   src/web_server.py │           │   src/email_watcher.py│
   │   localhost:8080    │           │   prüft alle 5s       │
   └──────────┬──────────┘           └───────────┬──────────┘
              │                                   │
              │                                   │
   ┌──────────▼───────────────────────────────────▼──────────┐
   │                  iCloud Data Lake                        │
   │   ~/Library/Mobile Documents/…/Downloads shared/        │
   │   claude_datalake/                                       │
   │   ├── config/agents/*.txt   ← System Prompts            │
   │   ├── config/models.json    ← API Keys                  │
   │   ├── [agent]/memory/       ← Dateien, Emails, URLs     │
   │   ├── email_inbox/          ← Eingehende Emails         │
   │   └── claude_outputs/       ← Generierte Dokumente      │
   └──────────────────────────────────────────────────────────┘
```

## Komponenten

### src/app.py
Menu Bar Controller. Startet web_server.py und email_watcher.py als
Subprozesse. Überwacht beide alle 15 Sekunden und startet bei Absturz neu.
Logs gehen nach ~/Library/Logs/assistant_*.log.

### src/web_server.py
Flask-Server auf Port 8080. Stellt das Browser-Interface bereit.
Kernfunktionen:
- Multi-Agent-Framework (ein .txt = ein Agent)
- Memory-System (kompaktes Inhaltsverzeichnis + Suche)
- Datei-Erstellung (Word, Excel, PDF, PowerPoint, Email)
- Web-Suche via Anthropic API Tool
- Vision/Bilder via Base64
- Multi-Provider (Anthropic, OpenAI, Mistral, Gemini)

### src/email_watcher.py
Überwacht email_inbox/ auf neue .eml Dateien.
- Parsed Subject, Sender, Body, Attachments
- Routet per Keyword-Matching zum richtigen Agenten
- Speichert Email-Text und Attachments in agent/memory/
- Processed-Log in ~/.emailwatcher_processed.json (Home, nicht iCloud)

## Sub-Agent System

Sub-Agents sind spezialisierte Varianten eines Parent-Agents mit eigenem System Prompt
aber geteiltem Memory.

Namenskonvention: `[parent]_[spezialisierung].txt`

```
config/agents/
  signicat.txt              ← Parent-Agent
  signicat_outbound.txt     ← Sub-Agent: Outbound-Emails
  signicat_powerpoint.txt   ← Sub-Agent: Praesentationen
  signicat_lamp.txt         ← Sub-Agent: Account Intelligence
  signicat_meddpicc.txt     ← Sub-Agent: Sales Intelligence
```

Verhalten:
- Memory Sharing: Sub-Agent liest/schreibt in `signicat/memory/` (Parent-Ordner)
- _index.json wird geteilt: alle Konversationen aller Sub-Agents sind sichtbar
- Konversationen: `signicat/konversation_2026-04-02_14-23_outbound.txt`
- Kein eigener Ordner: Sub-Agents erstellen keine neuen Verzeichnisse
- Frontend: eingerueckt unter Parent im Agent-Modal, Header zeigt "signicat > outbound"

Neuen Sub-Agent anlegen: `.txt` Datei in `config/agents/` mit dem Muster `parent_name.txt`.

## Sub-Agent Delegation

Nutzer koennen aus einem Parent-Agent heraus an Sub-Agents delegieren,
ohne den Agent manuell wechseln zu muessen.

Trigger-Erkennung (DE/EN/PT):
- Action-Keywords: "nutze", "verwende", "delegate", "use", "usa", ...
- Kombiniert mit: "agent", "spezialist", "specialist", ...
- Gefolgt von einem Namen oder Keyword das fuzzy-gematcht wird

Fuzzy Matching (in Reihenfolge):
1. Exakter Match: `"meddpicc"` in Nachricht → `signicat_meddpicc`
2. Keyword Match: `"Praesentation"` → `signicat_powerpoint` (via `config/subagent_keywords.json`)
3. Partial Match: Substring-Pruefung
4. Levenshtein-Distanz <= 2

Keyword-Mapping anpassen: `config/subagent_keywords.json` editieren — keine Code-Aenderung noetig.

Ablauf bei Delegation:
1. Sub-Agent System Prompt laden
2. Letzte 5 Messages als Kontext mitgeben
3. Parent-Memory laden (geteiltes Memory)
4. API-Call mit Sub-Agent Prompt
5. Antwort mit Header: "Robot Sub-Agent-Name uebernimmt: ..."
6. Im Chat: graue Statusmeldung "Delegiert an ..."

Beispiel-Phrasen:
- "nutze den meddpicc agent fuer eine Analyse"
- "delegate to the outbound specialist for this lead"
- "verwende den Praesentation Spezialisten"
- "usa o agente lamp para analisar a conta"

Route: `GET /available_subagents?agent=signicat` — listet alle Sub-Agents mit Keywords.

## Provider-Adapter

Alle API-Calls laufen über ADAPTERS-Dict in web_server.py:
- anthropic → native SDK + Web Search Tool
- openai    → openai library
- mistral   → REST API
- gemini    → google-generativeai library

## Memory-System

1. Beim Agenten-Start: kompaktes Inhaltsverzeichnis (Titel + Dateinamen)
2. Suche: "memory folder suche [keyword]" → lädt bis zu 3 Dateien
3. Auto-Search: Nachrichten mit Datei-Keywords triggern automatische Suche
4. Cleanup: startup bereinigt alten Memory-Müll aus .txt Dateien

## Datei-Erstellung (CREATE_FILE Syntax)

Claude antwortet mit JSON-Block am Ende:
- [CREATE_FILE:docx:{...}] → python-docx
- [CREATE_FILE:xlsx:{...}] → openpyxl
- [CREATE_FILE:pdf:{...}]  → reportlab
- [CREATE_FILE:pptx:{...}] → python-pptx
- [CREATE_EMAIL:{...}]     → AppleScript öffnet Apple Mail
