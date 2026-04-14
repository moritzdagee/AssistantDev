# AssistantDev — API Reference

Stand: 2026-04-14 · Base URL: `http://localhost:8080`

Alle `/api/*` Routes geben JSON zurück. Nicht-`/api/*` Routes geben HTML zurück (Haupt-UI, Admin, /agents mit JSON).

---

## Access Control

### `GET /api/access-control`
Lädt die Access-Control-Konfiguration.

**Response:**
```json
{
  "agents": {
    "privat": {
      "own_memory": true,
      "shared_memory": ["webclips"],
      "cross_agent_read": [],
      "description": "..."
    }
  },
  "last_modified": "2026-04-14T12:58:55.166732",
  "version": "1.0"
}
```

### `POST /api/access-control`
Speichert Access-Control-Änderungen. Validiert dass alle referenzierten Agenten existieren.

**Request Body:** wie GET Response

**Response:** `{"success": true, "saved_at": "..."}` oder `{"success": false, "error": "..."}`

---

## E-Mail

### `GET /api/email-search`
Sucht E-Mails (`.eml` + `.txt`) im Agent-Memory und `email_inbox/`. Antwort <25ms nach erstem Cache-Aufbau.

**Query-Parameter:**
- `agent` (required): Agent-Name
- `q` (optional): Freitext-Suche über Von+Subject. Min. 2 Zeichen.
- `from` (optional): Filter auf Von-Feld
- `subject` (optional): Filter auf Betreff
- `to` (optional): Filter auf An/CC-Feld
- `body` (optional): Filter auf Body

**Response:** Array max. 8 Einträge, nach Datum DESC sortiert.
```json
[{
  "message_id": "<id>",
  "from_name": "Max", "from_email": "max@example.com",
  "subject": "...", "date": "14.04.2026 12:00", "date_ts": 1776000000,
  "to": "...", "cc": "..."
}]
```

### `GET /api/email-content`
Lädt den vollständigen E-Mail-Inhalt (Body, Header). Unterstützt `.eml` (MIME) und `.txt` (deutsches Header-Format).

**Query-Parameter:**
- `agent` (required)
- `message_id` ODER `from_email` (mind. eins required)
- `subject` (optional, für Disambiguierung)

**Response:** `{"ok": true, "from_name": "...", "from_email": "...", "to": "...", "cc": "...", "subject": "...", "date": "...", "message_id": "...", "body": "...", "file": "..."}` oder `{"ok": false, "error": "..."}`

---

## Memory / Suche

### `GET /api/memory-files-search`
Autocomplete-Suche nach Dateinamen im Agent-Memory.

**Query-Parameter:**
- `agent` (required)
- `q` (required, min. 2 Zeichen)

### `POST /api/memory/search`
Deep Memory Search mit Dateiname- und Content-Filtern.

**Request Body:** `{"agent": "...", "query": "...", "filename_filter": "...", ...}`

### `GET /api/context-info`
Token-Estimates für aktive Session (System Prompt, History, Memory).

**Query-Parameter:**
- `session_id` (required)

---

## Session / Agent

### `GET|POST /api/agent-model-preference`
Liest oder speichert Modell-Präferenz pro Agent.

**Query/Body-Parameter:**
- `agent` (required)
- `provider`, `model` (POST)

### `POST /api/subagent_confirm`
Bestätigt (oder lehnt ab) einen Sub-Agent-Routing-Vorschlag.

**Request Body:**
```json
{
  "session_id": "...",
  "confirmation_id": "...",
  "confirmed": true
}
```

---

## Externe Integrationen

### `GET|POST /api/calendar`
Gibt Kalender-Events zurück (Apple Calendar + Fantastical).

**Parameter:**
- `days_back`, `days_ahead` (int)
- `search` (optional, Filter auf Event-Title)

### `POST /api/slack`
Slack-API-Proxy (send, channels, history, users).

**Request Body:** `{"action": "send|channels|history|users", ...}`

### `POST /api/canva`
Canva Connect API Proxy (designs, create, export, folders).

**Request Body:** `{"action": "...", ...}`

---

## Admin (HTML, nicht JSON)

### `GET /admin/access-control`
Admin-Web-UI für Access Control (dunkles Theme). Lädt `/api/access-control` und bietet Speichern via POST.

---

## Konventionen

- **Ports:** 8080 (Haupt-Server), 8081 (Web Clipper Server — separate Instanz)
- **Error-Format:** `{"ok": false, "error": "message"}` oder HTTP 400/500
- **Datum-Format:** `DD.MM.YYYY HH:MM` (deutsch), intern `date_ts` als Unix-Timestamp
- **Pagination:** Max. 8 Ergebnisse bei Such-APIs (hardcoded, nicht konfigurierbar)
- **Auth:** Keine — localhost-only, kein Login
- **Caching:** `_email_header_cache` TTL = 5 Minuten für `/api/email-search`

---

## OpenAPI 3.0 Spec

Für Tooling-Integration liegt zusätzlich eine maschinenlesbare Version als `openapi.yaml` vor (siehe unten in diesem Ordner).
