# AssistantDev - Technische Dokumentation

Stand: 2026-04-06

---

## 1. Uebersicht

AssistantDev ist ein lokaler, Multi-Agent AI-Assistent mit Web-Interface. Die Applikation laeuft als Flask-Server auf `localhost:8080`, wird als macOS `.app` Bundle ueber py2app paketiert und speichert alle Daten in iCloud (`~/Library/Mobile Documents/com~apple~CloudDocs/Downloads shared/claude_datalake/`).

**Kernfunktionen:**
- Multi-Agent-System mit hierarchischen Sub-Agenten
- 4 LLM-Provider (Anthropic, OpenAI, Mistral, Gemini)
- Intelligente Memory-Suche mit natuerlicher Sprache (DE/EN/PT)
- Globale Suche ueber alle Agenten und Dateien
- Quellen-Taxonomie mit hierarchischen Dateitypen
- Datei-Erstellung (Word, Excel, PDF, PowerPoint, E-Mail-Drafts)
- Chrome Extension fuer Web Clipping (Salesforce, Slack, beliebige Webseiten)
- E-Mail-Integration mit Apple Mail
- Vision-Support (Screenshots als Base64)

---

## 2. Architektur

### 2.1 Projektstruktur

```
~/AssistantDev/
├── src/
│   ├── web_server.py          (3731 Zeilen) — Haupt-Server mit Routes, HTML, JS, CSS
│   ├── search_engine.py       (1711 Zeilen) — Such-System mit Index, Parser, Hybrid-Suche
│   ├── web_clipper_server.py  (108 Zeilen)  — Chrome Extension Backend (Port 8081)
│   ├── email_watcher.py       (200 Zeilen)  — E-Mail-Ueberwachung
│   └── app.py                 (181 Zeilen)  — macOS Menu Bar App (py2app Entry Point)
├── chrome_extension/
│   └── assistant_clipper/
│       ├── manifest.json       — Chrome Manifest v3
│       ├── background.js       — Service Worker
│       └── content_script.js   — Seiten-Extraktion + UI
├── scripts/
│   ├── backup.sh               — Backup-Skript
│   ├── extract_contacts.py     — Kontakt-Extraktion aus E-Mails
│   └── ...
├── config/                     — (leer, Config liegt in iCloud)
├── docs/
├── backups/                    — Automatische Backups
├── CLAUDE.md                   — Regeln fuer Claude Code
├── changelog.md                — Aenderungsprotokoll
└── setup.py                    — py2app Build-Konfiguration
```

### 2.2 Datenspeicherung (iCloud)

```
~/Library/Mobile Documents/com~apple~CloudDocs/Downloads shared/
├── claude_datalake/
│   ├── config/
│   │   ├── agents/             — Agent-Definitionen (*.txt)
│   │   ├── models.json         — Provider/Modell-Konfiguration mit API-Keys
│   │   └── subagent_keywords.json — Keyword-Routing fuer Sub-Agenten
│   ├── signicat/               — Agent-Ordner
│   │   ├── memory/             — Agent Memory (Dateien, E-Mails, Clips)
│   │   ├── konversationen/     — Gespeicherte Chat-Verlaeufe
│   │   └── .search_index.json  — Such-Index pro Agent
│   ├── privat/
│   ├── trustedcarrier/
│   └── ...
├── webclips/                   — Globale Web Clips (Dual Save)
├── email_inbox/                — Eingehende E-Mails (Apple Mail Regel)
└── .global_search_index.json   — Globaler Such-Index
```

### 2.3 Deployment

Die App wird als macOS Bundle betrieben:

```
/Applications/Assistant.app/Contents/Resources/
├── web_server.py               — Kopie aus src/
├── search_engine.py            — Kopie aus src/
├── app.py                      — Entry Point
└── ...
```

**Deployment-Prozess:**
```bash
cp src/web_server.py /Applications/Assistant.app/Contents/Resources/
cp src/search_engine.py /Applications/Assistant.app/Contents/Resources/
pkill -f web_server.py   # App startet automatisch neu
```

### 2.4 Ports

| Port | Service | Datei |
|------|---------|-------|
| 8080 | Web Server (Haupt-Applikation) | `src/web_server.py` |
| 8081 | Web Clipper Server (Chrome Extension API) | `src/web_clipper_server.py` |

---

## 3. Backend: web_server.py

### 3.1 Single-File-Architektur

`web_server.py` ist eine einzelne Datei mit ~3731 Zeilen, die alles enthaelt:
- Python-Backend (Flask Routes, API-Adapter, State Management)
- HTML-Template (inline)
- CSS-Styles (inline)
- JavaScript (inline, 57 Funktionen)

**Bekanntes Problem:** Die Datei enthaelt duplizierte Code-Bloecke (~Zeilen 1-500 sind bei ~570-1100 wiederholt). Edits in diesen Bereichen muessen mit Python-Skripten statt dem Edit-Tool erfolgen.

### 3.2 State Management

Globaler `state` Dict (Zeilen 1137-1144):

```python
state = {
    "agent": None,              # Aktueller Agent-Name
    "system_prompt": None,      # System Prompt (Basis + Memory-Index)
    "speicher": None,           # Pfad zum Memory-Ordner
    "verlauf": [],              # Konversations-Verlauf [{role, content}]
    "dateiname": None,          # Aktueller Konversations-Dateiname
    "kontext_items": [],        # Geladene Kontext-Dateien/URLs
    "provider": "anthropic",    # LLM Provider
    "model_id": "claude-sonnet-4-6",  # Modell-ID
    "session_files": [],        # In dieser Session erstellte Dateien
    "queue": [],                # Nachrichten-Warteschlange
    "processing": False,        # Verarbeitungs-Flag
    "stop_requested": False,    # Stop-Flag fuer Warteschlange
    "completed_responses": [],  # Fertige Antworten zum Abholen
    "current_prompt": "",       # Aktuell verarbeitete Nachricht
}
```

### 3.3 LLM-Provider (ADAPTERS Pattern)

```python
ADAPTERS = {
    "anthropic": call_anthropic,
    "openai":    call_openai,
    "mistral":   call_mistral,
    "gemini":    call_gemini,
}
```

Jeder Adapter folgt derselben Signatur und gibt den Antwort-Text zurueck. Die Konfiguration (API-Keys, Modelle) liegt in `config/models.json`.

**Unterstuetzte Provider und Modelle:**

| Provider | Modelle |
|----------|---------|
| Anthropic | Claude Sonnet 4.6, Claude Opus 4.6, Claude Haiku 4.5 |
| OpenAI | GPT-4o, GPT-4o Mini, o1 |
| Mistral | Mistral Large, Mistral Small, Mistral Nemo |
| Gemini | Gemini 2.0 Flash, Gemini 2.5 Pro, Gemini 2.5 Flash |

### 3.4 API Routes (28 Endpunkte)

#### Kern-Routes

| Route | Methode | Funktion |
|-------|---------|----------|
| `/` | GET | Haupt-HTML-Seite ausliefern |
| `/chat` | POST | Chat-Nachricht verarbeiten (LLM Call) |
| `/models` | GET | Provider und Modelle zurueckgeben |
| `/select_model` | POST | Modell wechseln |

#### Agent-Management

| Route | Methode | Funktion |
|-------|---------|----------|
| `/agents` | GET | Hierarchische Agent-Liste (Parent + Sub-Agents) |
| `/select_agent` | POST | Agent auswaehlen, Memory + Index laden |
| `/create_agent` | POST | Neuen Agent anlegen |
| `/close_session` | POST | Session beenden |
| `/available_subagents` | GET | Sub-Agenten mit Keywords auflisten |

#### Konversation

| Route | Methode | Funktion |
|-------|---------|----------|
| `/new_conversation` | POST | Neue Konversation starten |
| `/get_history` | GET | Konversations-Liste fuer Agent |
| `/load_conversation` | POST | Gespeicherte Konversation laden |
| `/get_prompt` | GET | System Prompt anzeigen |
| `/save_prompt` | POST | Basis-Prompt speichern |

#### Warteschlange (Message Queue)

| Route | Methode | Funktion |
|-------|---------|----------|
| `/stop_queue` | POST | Warteschlange stoppen und leeren |
| `/queue_status` | GET | Status der Warteschlange |
| `/poll_responses` | GET | Fertige Antworten abholen |

#### Suche

| Route | Methode | Funktion |
|-------|---------|----------|
| `/search_memory` | POST | Memory durchsuchen (Legacy) |
| `/search_preview` | POST | Such-Vorschau mit Ergebnis-Details |
| `/global_search_preview` | POST | Globale Suche ueber alle Agenten |

#### Dateien & Kontext

| Route | Methode | Funktion |
|-------|---------|----------|
| `/load_selected_files` | POST | Dateien in Kontext laden (max 5) |
| `/add_url` | POST | URL in Kontext laden |
| `/add_file` | POST | Datei hochladen |
| `/remove_ctx` | POST | Kontext-Item entfernen |
| `/create_file` | POST | Datei erstellen (Word/Excel/PDF/PPTX) |
| `/download_file` | GET | Erstellte Datei herunterladen |
| `/open_in_finder` | POST | Datei im Finder oeffnen |
| `/send_email_draft` | POST | E-Mail-Draft in Apple Mail oeffnen |

### 3.5 Chat-Verarbeitung

Der `/chat` Endpunkt verarbeitet Nachrichten in folgenden Schritten:

1. **Auto-Search**: Erkennung von Such-Intent via Action-Keywords + Object-Keywords/Eigennamen
2. **Memory-Index**: Agent-Memory als Inhaltsverzeichnis im System Prompt
3. **Kontext aufbauen**: System Prompt + Kontext-Items + Verlauf + neue Nachricht
4. **LLM-Call**: Ueber ADAPTERS-Pattern zum konfigurierten Provider
5. **Response Parsing**: Erkennung von `CREATE_FILE` und `CREATE_EMAIL` Bloecken
6. **Verlauf speichern**: Automatisch in `konversationen/konversation_[datum].txt`

**Warteschlange:** Wenn eine Nachricht verarbeitet wird und eine neue eingeht:
- Nachricht wird in `state['queue']` eingereiht
- Frontend zeigt Placeholder mit Position
- Worker-Thread verarbeitet Queue sequentiell
- `/poll_responses` liefert fertige Antworten

### 3.6 Sub-Agent Delegation

Agenten koennen Aufgaben an Sub-Agenten delegieren:

- **Namenskonvention:** `[parent]_[spezialisierung].txt` (z.B. `signicat_outbound.txt`)
- **Memory Sharing:** Sub-Agents nutzen Memory und Index des Parent-Agents
- **Keyword-Routing:** `config/subagent_keywords.json` definiert Keywords pro Sub-Agent
- **Matching:** Exakt → Keyword-basiert → Partial → Levenshtein (Fuzzy)
- **Kontext:** Sub-Agent erhaelt eigenen System Prompt + Parent Memory + letzte 5 Messages

### 3.7 Datei-Erstellung

Die Applikation kann Dateien aus LLM-Antworten erstellen:

| Format | Library | Trigger |
|--------|---------|---------|
| Word (.docx) | python-docx | `CREATE_FILE:docx` |
| Excel (.xlsx) | openpyxl | `CREATE_FILE:xlsx` |
| PDF (.pdf) | reportlab | `CREATE_FILE:pdf` |
| PowerPoint (.pptx) | python-pptx | `CREATE_FILE:pptx` |
| E-Mail Draft | AppleScript | `CREATE_EMAIL` |

---

## 4. Such-System: search_engine.py

### 4.1 Architektur

Das Such-System besteht aus vier Kernklassen:

```
SearchIndex          — JSON-Index pro Agent (.search_index.json)
QueryParser          — Natuerliche Sprache → strukturierte Query
HybridSearch         — 4-stufige Suche (Zeit → BM25 → Volltext → Ranking)
GlobalSearchIndex    — Uebergreifender Index (alle Agenten + Downloads)
```

### 4.2 SearchIndex

Pro Agent wird ein JSON-Index angelegt (`.search_index.json`), der folgende Felder pro Datei speichert:

- `path`, `filename`, `folder`
- `type` / `source_type` (aus SOURCE_TAXONOMY)
- `date`, `mtime`, `size`
- `from`, `subject` (bei E-Mails/Konversationen)
- `preview` (erste 300 Zeichen)
- `is_notification` (automatisch erkannt)
- `keywords` (Top-10 extrahiert)

**Delta-Update:** Nur neue/geaenderte Dateien werden re-indexiert (Vergleich ueber `mtime`).

### 4.3 QueryParser

Versteht natuerliche Sprache in Deutsch, Englisch und Portugiesisch:

- **Zeitfilter:** "gestern", "letzte Woche", "02.04.", "last month", "ontem"
- **Feldfilter:** "von Max", "from Anna", "de João"
- **Typfilter:** "emails", "dokumente", "PDFs", "screenshots"
- **Eigennamen:** Grossgeschriebene Woerter nach Trigger-Keywords
- **Unicode-Normalisierung:** "Simonäs" → "simonas"

### 4.4 HybridSearch

4-stufiger Such-Algorithmus:

1. **Zeitfilter:** Einschraenkung auf Index-Eintraege im Zeitraum
2. **BM25-Scoring:** Ranking auf Index-Daten (Dateiname, Keywords, Subject, From)
3. **Volltext:** Top-20 Kandidaten werden vollstaendig gelesen und gescored
4. **Ranking:** Endgueltiges Ranking mit Bonus fuer Person-Match

**Ergebnis-Limit:** 50 Ergebnisse, davon max. 5 selektierbar. Notifikationen erhalten Score-Malus (`*= 0.1`).

### 4.5 SOURCE_TAXONOMY (Quellen-Taxonomie)

Hierarchisches Typen-System mit 13 Typen:

```
email (✉)
└── notification (📢)         — Auto-detect via NOTIFICATION_PATTERNS

webclip (🌐)
├── webclip_salesforce        — Salesforce CRM Daten
├── webclip_slack             — Slack Nachrichten
└── webclip_general           — Allgemeine Webseiten

document (📄)
├── document_word             — .docx, .doc
├── document_excel            — .xlsx, .xls, .csv
├── document_pdf              — .pdf
└── document_pptx             — .pptx

conversation (💬)             — konversation_*.txt

screenshot (📸)               — .png, .jpg (als Vision geladen)
```

Jeder Typ hat:
- `label`: Menschenlesbarer Name
- `icon`: Emoji-Symbol
- `patterns`: Dateiname-Muster zur Erkennung
- `keywords`: Multi-linguale Such-Keywords
- `subcategories`: Kind-Typen (optional)
- `parent`: Eltern-Typ (optional)
- `auto_detect`: Pattern-Liste fuer automatische Erkennung (bei Notifikationen)

### 4.6 GlobalSearchIndex

Indexiert den gesamten iCloud-Ordner:

**Scan-Bereiche:**
- Alle Agent `memory/` Ordner in `claude_datalake/`
- Gesamter `Downloads shared/` Ordner (inkl. `webclips/`, `email_inbox/`)

**Datei-Extraktion:**
| Format | Library |
|--------|---------|
| .txt, .eml, .csv, .md | Direkt lesen |
| .pdf | PyPDF2 |
| .docx | python-docx |
| .xlsx | openpyxl |
| .pptx | python-pptx |

**Skip-Listen:**
- Ordner: `backups`, `build`, `dist`, `__pycache__`, `.git`, `node_modules`
- Endungen: `.pyc`, `.pyo`, `.class`, `.o`, `.so`, `.dylib`

**GLOBAL_TRIGGERS** (~25 Phrasen):
- DE: "erweitertes gedaechtnis", "globale suche", "alle agenten durchsuchen"
- EN: "extended memory", "global search", "search everywhere"
- PT: "busca global", "todos os agentes", "memoria estendida"

**Index-Datei:** `Downloads shared/.global_search_index.json`
**Startup:** Index wird beim Server-Start im Hintergrund-Thread gebaut.

---

## 5. Frontend

### 5.1 Aufbau

Das Frontend ist vollstaendig in `web_server.py` eingebettet (Single-File). Dark Theme mit Inter-Font.

**Layout:**
```
┌─────────────┬──────────────────────────────────┐
│  Sidebar    │  Header (Provider, Model, Agent)  │
│             ├──────────────────────────────────┤
│  - Prompt   │  Chat-Bereich                     │
│  - History  │  (Messages, Status, Downloads)    │
│             │                                    │
│             ├──────────────────────────────────┤
│             │  Kontext-Bar (geladene Dateien)   │
│             ├──────────────────────────────────┤
│             │  Queue-Display                    │
│             ├──────────────────────────────────┤
│             │  Input-Area + Send/Stop/Attach    │
└─────────────┴──────────────────────────────────┘
```

### 5.2 JavaScript-Funktionen (57 total)

**Chat & Messaging:**
- `sendMessage()` — Haupt-Sendefunktion mit Search-Intent-Erkennung
- `doSendChat(text)` — Eigentlicher Chat-API-Call
- `handleResponse(data)` — Response-Verarbeitung (Text, Downloads, E-Mails)
- `addMessage(role, text, modelName)` — Nachricht zum Chat hinzufuegen
- `addStatusMsg(text)` / `addMemoryMsg(text)` — System-Nachrichten

**Suche:**
- `detectSearchIntent(text)` — Prueft ob Nachricht eine Suchanfrage ist
- `detectGlobalTrigger(text)` — Prueft ob globale Suche gemeint ist
- `showSearchDialog(results, query, isGlobal)` — Such-Dialog anzeigen
- `applySearchFilter(filter)` — Typ-Filter anwenden
- `getFilteredResults()` / `rerenderSearchResults()` — Ergebnis-Filterung
- `loadAllResults()` / `loadSelectedResults()` — Dateien in Kontext laden

**Agent-Management:**
- `loadAgents()` — Agent-Liste mit Expand/Collapse fuer Sub-Agenten
- `selectAgent(name)` — Agent auswaehlen
- `showAgentModal()` / `createAgent()` — Agent-Modal

**Warteschlange:**
- `startPolling()` / `stopPolling()` — Polling fuer Queue-Responses (2s Intervall)
- `addQueuedMessage(text, position, queueId)` — Placeholder fuer queued Messages
- `updateQueueDisplay(count)` / `showStopBtn(show)` — UI-Updates
- `stopQueue()` — Warteschlange stoppen

**Kontext:**
- `addCtxItem(name, type, autoLoaded)` — Kontext-Item in Bar anzeigen
- `removeCtx(name, el)` — Kontext-Item entfernen
- `addUrl()` / `addFileFromInput()` — URL/Datei hinzufuegen

**UI-Hilfen:**
- `toggleSidebar()` / `updateSidebar(agentName, prompt)` — Sidebar
- `loadHistory(agentName)` / `loadConversation(session, btn)` — Verlauf
- `scrollDown()` / `autoResize(el)` / `escHtml(t)` — Utilities
- `startTyping(prompt)` / `stopTyping()` — Typing-Indicator

### 5.3 Such-Dialog

Der Such-Dialog erscheint automatisch, wenn eine Suchanfrage erkannt wird:

1. **Trigger-Erkennung:** `detectSearchIntent()` prueft Action + Object Keywords
2. **Globale vs. lokale Suche:** `detectGlobalTrigger()` entscheidet
3. **Ergebnis-Anzeige:** Max 50 Ergebnisse mit Typ-Icons und Agent-Tags
4. **Filter-Buttons:** Alle | E-Mail | Web Clip | Dokument | Konversation | Screenshot
5. **Unterfilter:** Bei Web Clip (Salesforce/Slack/Web), bei Dokument (Word/Excel/PDF/PPTX)
6. **Notifikationen:** Grau/kursiv, am Ende, mit `[Notif]` Prefix
7. **Auswahl:** Checkboxen, max 5 selektierbar, Counter-Anzeige
8. **Aktionen:** "Alle laden" (max 5), "Auswahl laden", "Abbrechen" (sendet trotzdem)

### 5.4 Agent-Modal

Hierarchische Darstellung mit Parent/Sub-Agent-Gruppen:

- Parent-Agenten: Volle Breite, Klick waehlt Agent
- Expand-Pfeil: Klick zeigt/versteckt Sub-Agenten (Akkordeon-Verhalten)
- Sub-Agenten: Eingerueckt (16px), kleinere Schrift (11px), gedimmte Farbe
- Expand-State: In `localStorage` persistiert

---

## 6. Chrome Extension: Assistant Memory Clipper

### 6.1 Architektur

Chrome Manifest v3 Extension mit drei Komponenten:

```
manifest.json      — Berechtigungen, Content Script Registrierung
background.js      — Service Worker (API-Calls zu localhost:8081)
content_script.js  — Seiten-Extraktion + Floating Panel UI
```

### 6.2 Ablauf

1. User klickt Extension-Icon
2. `background.js` sendet `{action: 'clip'}` an Content Script
3. `content_script.js` erkennt Seitentyp (Salesforce/Slack/Web)
4. Passende Extraktion wird ausgefuehrt
5. Floating Panel zeigt Vorschau + Agent-Dropdown + Dateiname
6. User klickt "Speichern"
7. `background.js` sendet POST an `localhost:8081/save`
8. `web_clipper_server.py` speichert an zwei Orte (Dual Save)

### 6.3 Seiten-Erkennung

| Seite | Erkennung | Extraktion |
|-------|-----------|------------|
| Salesforce | `salesforce.com` / `force.com` in Hostname | Felder aus `.slds-form-element`, `dt/dd`, `records-highlights` |
| Slack | `slack.com` in Hostname | Messages aus `.c-message_kit__message` |
| Web (Default) | Alles andere | `<article>` / `<main>` / `.content` Text |

### 6.4 Dual Save

Jeder Clip wird an zwei Orte gespeichert:

1. **Agent Memory:** `claude_datalake/[agent]/memory/[filename]`
2. **Globale Webclips:** `Downloads shared/webclips/[agent]_[filename]`

Der `webclips/` Ordner wird automatisch vom GlobalSearchIndex erfasst.

### 6.5 Agent-Dropdown

- Laedt Agenten von `GET localhost:8081/agents`
- Zeigt nur Parent-Agenten (keine Sub-Agenten mit `_` im Namen)
- Fallback bei Verbindungsfehler: Hardcoded Liste

---

## 7. E-Mail-Integration

### 7.1 Eingehende E-Mails

1. **Apple Mail Regel:** Speichert eingehende E-Mails als `.eml` in `email_inbox/`
2. **Email Watcher** (`email_watcher.py`): Ueberwacht `email_inbox/`, routet nach Keywords zu Agenten
3. **Junk-Filter:** Apple Mail Regel filtert Junk VOR dem Speichern
4. **Attachments:** Werden automatisch extrahiert

### 7.2 E-Mail-Draft Erstellung

LLM-Antworten mit `CREATE_EMAIL` Block oeffnen Apple Mail via AppleScript. Fallback: `mailto:` Link.

---

## 8. Konfiguration

### 8.1 models.json

Liegt in `claude_datalake/config/models.json`. Struktur:

```json
{
  "providers": {
    "anthropic": {
      "name": "Anthropic",
      "api_key": "...",
      "models": [
        {"id": "claude-sonnet-4-6", "name": "Claude Sonnet 4.6"},
        ...
      ]
    },
    "openai": { ... },
    "mistral": { ... },
    "gemini": { ... }
  }
}
```

### 8.2 Agent-Definitionen

Pro Agent eine `.txt` Datei in `claude_datalake/config/agents/`:
- `signicat.txt` — System Prompt fuer Signicat-Agent
- `signicat_outbound.txt` — Sub-Agent (Namenskonvention: `parent_sub.txt`)
- `privat.txt` — Privater Agent
- ...

### 8.3 subagent_keywords.json

Keyword-Routing fuer Sub-Agent-Delegation:

```json
{
  "signicat_outbound": ["outbound", "kaltakquise", "cold"],
  "signicat_powerpoint": ["praesentation", "slides", "deck"],
  ...
}
```

---

## 9. Memory & Zugriffs-Matrix

### 9.1 Basis-Pfad (iCloud)

```
~/Library/Mobile Documents/com~apple~CloudDocs/Downloads shared/claude_datalake/
```

### 9.2 Lokales Agent-Memory (Lesen + Schreiben)

Jeder Agent hat exklusiven Schreibzugriff auf seinen eigenen Ordner. Sub-Agenten (z.B. `signicat_outbound`) teilen den Ordner des Parent-Agenten (`get_agent_speicher()` in web_server.py).

| Pfad | Inhalt |
|------|--------|
| `[agent]/memory/` | Dateien, E-Mails, Web Clips des Agenten |
| `[agent]/konversation_*.txt` | Gespeicherte Chatverlaeufe (direkt im Agent-Ordner) |
| `[agent]/_index.json` | Session-Zusammenfassungen (max 50 Eintraege) |
| `[agent]/.search_index.json` | Such-Index des Agenten (SearchIndex Klasse) |

**Bekannte Agenten:** `signicat` (+ Sub-Agents: outbound, powerpoint, lamp, meddpicc), `privat`, `trustedcarrier`, `standard`, `system ward`

Agent-Definitionen liegen in `config/agents/*.txt`.

### 9.3 Globales Memory (Lesen via Globale Suche)

Der `GlobalSearchIndex` (search_engine.py) indexiert zwei Quellen:
1. Alle Agent `memory/` Ordner + `email_inbox/` + `claude_outputs/` in `DATALAKE_BASE`
2. Den gesamten `DOWNLOADS_SHARED` Ordner rekursiv

| Pfad | Inhalt |
|------|--------|
| `claude_datalake/email_inbox/` | Eingehende E-Mails (Apple Mail Regel) |
| `Downloads shared/webclips/` | Web Clips aller Agenten (Dual Save) |
| `Downloads shared/claude_outputs/` | Von Claude erstellte Dateien |
| `Downloads shared/.global_search_index.json` | Globaler Such-Index |
| `Downloads shared/*.pdf, *.docx, ...` | Alle Dateien im Downloads shared |

Globale Suche wird durch `GLOBAL_TRIGGERS` (~25 Phrasen DE/EN/PT) ausgeloest.

### 9.4 Schreib-Zugriff ins globale Memory

| Trigger | Ziel |
|---------|------|
| Chrome Extension Web Clip (Port 8081) | `webclips/[agent]_[filename]` + `[agent]/memory/[filename]` |
| Datei-Erstellung (`CREATE_FILE` Block) | `[agent]/memory/[dateiname]` |
| E-Mail-Import (Email Watcher) | `[agent]/memory/email_[datum].txt` (keyword-basiertes Routing) |
| URL hinzufuegen (`/add_url`) | `[agent]/memory/[safe_title].txt` |
| Datei hochladen (`/add_file`) | `[agent]/memory/[filename]` |

### 9.5 AssistantDev System-Dateien (kein Agent-Zugriff)

| Pfad | Inhalt |
|------|--------|
| `src/web_server.py` | Haupt-App (Flask Server + Frontend, ~3800 Zeilen) |
| `src/search_engine.py` | Such-System (~1711 Zeilen) |
| `src/web_clipper_server.py` | Chrome Extension Backend (Port 8081) |
| `src/email_watcher.py` | E-Mail-Ueberwachung |
| `src/app.py` | macOS Menu Bar App (py2app Entry Point) |
| `config/models.json` | API-Keys + Modell-Konfiguration (iCloud) |
| `config/subagent_keywords.json` | Keyword-Routing (iCloud) |
| `CLAUDE.md` | Regeln fuer Claude Code |
| `changelog.md` | Systemdokumentation + Memory-Matrix |

---

## 10. Bekannte Eigenheiten

### 10.1 Duplizierter Code in web_server.py

Die Datei enthaelt duplizierte Code-Bloecke (~Zeilen 1-500 bei ~570-1100). Edits mit dem Edit-Tool schlagen fehl ("Found 2 matches"). Workaround: Python-Skripte mit `content.replace()`.

### 10.2 App Bundle Deployment

Aenderungen an `src/*.py` muessen manuell nach `/Applications/Assistant.app/Contents/Resources/` kopiert werden. Der laufende Server laedt von dort, nicht aus `src/`.

### 10.3 iCloud Sync

Dateien liegen in iCloud. Operationen auf grossen Verzeichnissen (z.B. GlobalSearchIndex Build) koennen langsam sein, wenn Dateien noch nicht lokal synchronisiert sind.

### 10.4 Unicode in Templates

JavaScript im Python-HTML-Template: ES6 Unicode-Escapes (`\u{1F310}`) verursachen Python SyntaxErrors. Loesung: Direkte Unicode-Zeichen verwenden.

---

## 11. Abhaengigkeiten

### Python
- Flask
- anthropic (Anthropic SDK)
- openai (OpenAI SDK)
- python-docx, openpyxl, reportlab, python-pptx (Datei-Erstellung)
- PyPDF2 (PDF-Extraktion im GlobalSearchIndex)
- py2app (macOS App Bundle)

### Chrome Extension
- Chrome Manifest v3
- Keine externen Abhaengigkeiten

---

## 12. Offene Punkte

- [ ] Perplexity AI als 5. Provider integrieren
- [ ] Gemini API Key eintragen
- [ ] Rate Limit bei Anthropic erhoehen
- [ ] Web Clipper Bookmarklet reaktivieren auf Port 8081
- [ ] Message Queue Plan fertigstellen (Plan liegt vor)
