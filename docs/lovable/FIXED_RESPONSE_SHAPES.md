# FIXED — Response-Shapes an Backend angleichen

**Status:** ✅ erledigt am 2026-04-25
**Von:** Claude (Backend)
**Datum:** 2026-04-22
**Betrifft:** mehrere Pages in `src/pages/*.tsx`

## Erledigung (2026-04-25)
Verifikation per Greps gegen `frontend/src/pages/*.tsx`:

- **AdminHealth.tsx** — Service-Record nutzt `name`/`status`/`detail`/`since`,
  Restart per Mutation an `POST /api/health/<name>/restart`. Alte Felder
  (`uptimeSeconds`, `cpu`, `mem`, `lastRestart`, `warn`/`error`) entfernt.
- **AdminPermissions.tsx** — flache Liste vom Backend wird clientseitig
  per `filter(p => p.category === 'oauth' | 'api_key' | 'macos_automation')`
  gruppiert. Option A umgesetzt; Option B (gruppiertes Endpoint) nicht nötig.
- **AdminChangelog.tsx** — `Array.isArray(data)` statt `data.entries`,
  Rendering via `body_markdown` (markdownPreview/react-markdown).
- **Messages.tsx** — Field-Mapping zu `/api/messages` umgesetzt:
  `sender_name → from`, `preview → snippet`, `timestamp → updatedAt`,
  `read=false → unread=1`, Channel aus `source`-Prefix. Konzeptuelle
  Trennung Messages vs Conversations sauber.
- **Memory.tsx** — `fileToEntry()` transformiert Backend-Files zu
  `MemoryEntry` Pseudo-Records (Vorschlag aus dem TODO §5).

TS-Check (`tsc --noEmit`): grün.

---

## Original-Briefing (Stand 2026-04-22)


Nach Deployment des Batches aus `FIXED_LIVE_API_QA_2026-04-22.md` sind die
Endpoints live, aber einige Frontend-Pages erwarten einen **anderen JSON-Shape**
als das Backend tatsächlich liefert. Hier die konkreten Diffs — bitte im
Frontend angleichen (Backend-Shape ist die Referenz, weil `api.bios.love` live
produktive Daten liefert).

---

## 1. `src/pages/AdminHealth.tsx`

**Frontend erwartet aktuell:**
```ts
interface HealthResponse {
  uptimeSeconds: number;
  version: string;
  lastCheck: string;
  services: Service[];
}
interface Service {
  id: string; label: string;
  status: 'ok' | 'warn' | 'error';
  pid: number | null; cpu: number; mem: number; port: number | null;
  lastRestart: string; note?: string;
}
```

**Backend liefert aktuell unter `GET /api/health`:**
```json
{
  "services": [
    { "name": "web_server", "label": "Web Server",
      "status": "ok",  // "ok" | "down" | "warning"
      "detail": "Port 8080", "since": "2026-04-22T..Z" }
  ],
  "overall": "ok",
  "checked_at": "2026-04-22T..Z"
}
```

**Bitte anpassen:**
- `name` statt `id` im Service-Record lesen
- `status` kann `'ok' | 'warning' | 'down'` sein (nicht `warn`/`error`)
- `since` und `detail` statt `lastRestart`/`note`
- `cpu`/`mem`/`pid`/`port` fehlen im Backend — Backend ergänzt das bei Bedarf,
  aber erstmal als optional behandeln
- `uptimeSeconds`/`version`/`lastCheck` fehlen im Backend — durch `checked_at`
  ersetzen, Rest optional ausblenden
- `endpoints.serviceRestart` gibt's noch nicht — aktuell kein Restart-Endpoint
  vorhanden, Button deaktivieren oder Mutation ausblenden, bis
  `POST /api/health/<service>/restart` separat gebaut wird (TODO setzen mit
  `TODO(API):`)

---

## 2. `src/pages/AdminPermissions.tsx`

**Frontend erwartet aktuell:**
```ts
interface PermissionsResponse {
  oauth: { provider, label, connected, account, scopes[] }[];
  apiKeys: { name, set, lastUsed }[];
  macOs: { name, granted }[];
}
```

**Backend liefert aktuell unter `GET /api/permissions`:**
```json
[
  { "id": "anthropic_api_key", "label": "Anthropic API Key",
    "status": "ok"|"missing"|"unknown",
    "category": "api_key"|"oauth"|"macos_automation",
    "fix_kind": "docs"|"open_url"|"open_settings",
    "fix_target": "...",
    "instructions_markdown": "..." }
]
```

**Option A (empfohlen, schneller):** Frontend parst die flache Liste und
gruppiert selbst nach `category`. Wenn du `.filter(p => p.category === 'oauth')`
machst, kriegst du die OAuth-Items; gleich für `api_key` und `macos_automation`.

**Option B:** Wir bauen zusätzlich `GET /api/permissions/grouped` das die
aktuell erwartete Shape liefert. Sag Bescheid in einem
`BACKEND_TODO_PERMISSIONS_GROUPED.md`, dann mache ich das.

---

## 3. `src/pages/AdminChangelog.tsx`

**Frontend erwartet aktuell:**
```ts
{ entries: ChangelogEntry[] }
// ChangelogEntry: { date, version, changes: string[] }
```

**Backend liefert aktuell unter `GET /api/changelog`:**
```json
[
  { "id": "cl-1", "version": "2026-04-22", "date": "2026-04-22",
    "title": "Feature-X", "body_markdown": "...ganze Section...",
    "type": "feature"|"fix"|"security"|"chore" }
]
```

**Bitte anpassen:**
- Direkt `Array.isArray(data)` statt `data.entries` — das Response ist eine
  flache Liste (wie in `BACKEND_TODO_LIVE_API_QA_2026-04-22.md` §9 spezifiziert)
- `changes: string[]` existiert nicht; stattdessen `body_markdown` (mit
  `react-markdown` rendern) oder die ersten 3 Zeilen extrahieren

---

## 4. `src/pages/Messages.tsx`

**Frontend erwartet aktuell:**
```ts
{ conversations: Conversation[] }
// Conversation: { id, channel, account, subject, snippet, from, unread, updatedAt, agent }
```

**Backend liefert unter `GET /api/messages`:**
```json
{
  "count": 5, "messages": [...]
}
// message: { id, source (z.B. "email_privat"), type, sender_name, sender_address,
//            subject, preview, timestamp, read, is_junk, is_archived, ... }
```

**Backend liefert unter `GET /api/conversations`** (neu, siehe FIXED-TODO):
```json
[
  { "id": "konversation_2026-04-22_...", "agent": "privat",
    "title": "...", "file": "...", "modified": "2026-04-22T..Z",
    "size": 12345 }
]
```

**Bitte anpassen:**
- Unterscheidung klar machen zwischen **Messages** (einzelne E-Mails/Chats aus
  Posteingang, via `/api/messages`) und **Conversations** (Chat-Sessions mit
  Agent, via `/api/conversations`)
- Aktueller `Messages.tsx` mischt das Konzept — vermutlich wolltest du
  Messages aus `/api/messages` anzeigen, nicht Conversations
- Field-Mapping:
  - `source` enthält schon `"email_"`/`"whatsapp"`/`"imessage"`/`"kchat"` Prefix → daraus
    `channel` ableiten
  - Für E-Mail-Account (tangerina/signicat/trusted_carrier/other) das Suffix
    nach `"email_"` nutzen
  - `sender_name` → `from`, `preview` → `snippet`, `timestamp` → `updatedAt`,
    `read=false` → `unread=1`

---

## 5. `src/pages/Memory.tsx`

**Frontend erwartet aktuell:**
```ts
{ entries: MemoryEntry[] }
// MemoryEntry: { id, agent, key, value, priority, updatedAt }
```

**Backend liefert unter `GET /api/memory/list/<agent>`:**
```json
[
  { "path": "...", "name": "...", "size": 123, "modified": "..." }
]
```

**Das ist ein konzeptioneller Mismatch.** Backend liefert Memory als **Dateien**
(pfad-basiert, was im Datalake tatsächlich liegt). Frontend erwartet Memory als
**Key-Value-Paare** mit Prioritäten.

**Vorschlag:** Backend-Shape bleibt authoritativ (Dateien sind die Realität
im Datalake). Frontend-Hook `useMemory()` transformiert File-Listen zu
pseudo-entries:
```ts
const entries = files.map(f => ({
  id: f.path, agent: f.agent ?? 'unknown',
  key: f.name, value: '(Datei — klick zum Öffnen)',
  priority: 'medium' as const, updatedAt: f.modified,
}));
```

Falls du echte Key-Value-Memory willst, brauchen wir ein separates Backend —
sag Bescheid via `BACKEND_TODO_MEMORY_KV.md`.

---

## Zusammenfassung

| Datei | Aufwand | Dringlichkeit |
|---|---|---|
| AdminHealth.tsx | Mittel — Shape umbauen, `serviceRestart` maskieren | hoch (Page zeigt sonst Mock) |
| AdminPermissions.tsx | Klein — `filter` nach `category` | hoch |
| AdminChangelog.tsx | Klein — `data` direkt als Array, `body_markdown` nutzen | hoch |
| Messages.tsx | Mittel — Field-Mapping neu | hoch |
| Memory.tsx | Klein — Files → Pseudo-Entries transformieren | mittel |

Wenn du eine Page fertig hast, diesen Abschnitt aus der TODO entfernen.
Wenn alle erledigt: Datei umbenennen zu `FIXED_RESPONSE_SHAPES.md`.
