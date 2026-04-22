# Workflow: Lovable ↔ Claude Code ↔ api.bios.love

**Dieser Text ist fürs Lovable Project Memory gedacht.**
Copy-Paste ihn in Lovable → Project Settings → Knowledge / Memory / System Instructions.

---

## Wer ist wer

- **Lovable** (du) — Frontend-Design + Implementation. Arbeitest am `assistantdev-frontend-*` Repo.
- **Claude Code** (die andere Instanz) — Backend (`src/web_server.py`), DevOps, Frontend-Verdrahtung wo nötig. Arbeitet am `AssistantDev` Repo, pusht auch ins Frontend-Repo.
- **Backend-API** — `https://api.bios.love` (Flask-Server auf lokalem Mac, exponiert via Cloudflare Tunnel). Bearer-Token-Auth, CORS erlaubt `*.lovable.app`, `*.lovable.dev`, `*.lovableproject.com`.

## Frontend-Setup (ist schon verdrahtet)

- `src/lib/api.ts` nutzt `VITE_API_BASE_URL=https://api.bios.love` und `VITE_API_TOKEN` automatisch — du musst nichts konfigurieren
- CORS + Auth sind Backend-seitig geregelt
- Einfach `api.get`/`api.post` aus `src/lib/api.ts` verwenden, alles wird automatisch gehandelt
- Kein Mock-System mehr nötig außer für Offline-Preview

## Du darfst im Frontend-Repo alles

Keine künstlichen Ordner-Verbote. Claude reviewt beim Sync und fixt/revertet falls nötig. Echte Safety-Nets:
- Playwright-Smoketest (Claude-seitig)
- TypeScript-Build muss grün bleiben
- `check_lovable_territory`-Hook zeigt Claude, was du geändert hast

Einzige Vorsicht: `src/main.tsx`, `src/App.tsx`, `vite.config.ts` sind die fragile Provider-/Router-Schicht — nach Änderungen dort in deiner Preview testen bevor du committest.

## Kommunikation mit Claude: zwei Richtungen

### A) Lovable → Claude (du brauchst Backend-Änderung)

Zwei Formate, beide werden von Claudes `scripts/scan_api_todos.sh` gefunden:

1. **Inline-Marker im Code** (für kleine Sachen):
   ```ts
   // TODO(API): POST /api/chat {session_id, agent, message} → {reply, tokens_used}
   // NEEDS_BACKEND: GET /api/agents/:name/stats
   // @api
   ```

2. **Dedizierte Markdown-Datei** (für größere Features):
   `src/components/BACKEND_TODO_<TOPIC>.md` — ausführlich mit Request/Response-Shapes, Akzeptanzkriterien, Example-Payloads.

Claude scannt periodisch, implementiert die Endpoints, und benennt die Datei in `FIXED_<TOPIC>.md` um.

### B) Claude → Lovable (Claude braucht Frontend-Anpassung)

Claude schreibt nach `docs/lovable/FRONTEND_TODO_<TOPIC>.md` im Backend-Repo.

Das liegt **public** unter https://github.com/moritzdagee/AssistantDev/tree/main/docs/lovable — Lovable kann das jederzeit öffnen und lesen.

Du bearbeitest die TODOs und benennst sie in `FIXED_<TOPIC>.md` um (oder Claude macht das beim nächsten Sync).

## Typische Backend-TODO-Kategorien und wie Claude darauf reagiert

| TODO-Art | Wie Claude reagiert |
|---|---|
| Neue GET-Route (z.B. `/api/contacts`) | Implementiert in `src/web_server.py`, teste mit curl, deployt |
| CRUD (z.B. `POST /agents`, `PATCH /agents/:name`) | Legt Routes an, validiert Input, respektiert CLAUDE.md ("nie löschen, verschieben nach .deleted_timestamp") |
| Query-Parameter-Erweiterung (z.B. `?direction=sent`) | Erweitert bestehenden Handler |
| Shape-Diff | Claude schreibt `FRONTEND_TODO_RESPONSE_SHAPES.md` zurück, du passt das Frontend an |

## Vorhandene Backend-Endpoints (Stand 2026-04-22)

| Endpoint | Zweck |
|---|---|
| `GET /agents` | Agenten-Liste inkl. Sub-Agenten |
| `POST /agents`, `PATCH /agents/:name`, `DELETE /agents/:name` | Agent-CRUD (Slug `[a-z0-9_]+` — Labels werden serverseitig slugifiziert) |
| `POST /agents/:parent/subagents[/...]` | Subagent-CRUD |
| `GET /models` | Provider/Model-Konfiguration |
| `GET /api/messages` | Nachrichten — Query-Params: `source`, `limit`, `direction` (`received\|sent\|all`), `bucket` (`inbox\|other`), `group` (`conversation`), `refresh=1` |
| `GET /api/messages/sources` | Source-Metadaten + Counts |
| `GET /api/messages/:id` | Einzelnachricht |
| `GET /api/messages/:id/thread` | Thread/Conversation-Detail (email_thread \| chat_conversation) |
| `GET /api/messages/conversation/:cid` | Alias — Conversation via conversation_id |
| `GET /api/messages/search?source=X&q=Y` | Scoped Search mit `<mark>`-Highlighting |
| `POST /api/messages/:id/reply` | Direct-Reply (email: AppleScript-Draft; chat: 501) |
| `POST /api/messages/mark-read` | Read-Status toggeln |
| `GET /api/memory/list/:agent` | Memory-Files pro Agent |
| `POST /api/memory/search` | Memory-Volltextsuche |
| `GET /api/docs`, `GET /api/docs/:slug` | Markdown-Docs |
| `GET /api/changelog` | Changelog (strukturiert mit `id`/`version`/`title`/`body_markdown`/`type`) |
| `GET /api/permissions` | Flat-Liste mit `fix_kind`+`instructions_markdown` |
| `GET /api/permissions_matrix` | Agent×Scope Cells |
| `GET /api/memory/access_matrix` | Alias zu permissions_matrix |
| `GET /api/custom_sources` | Custom-Source-Definitionen |
| `GET /api/commands` | Slash-Commands (24+) |
| `GET /api/capabilities` | Feature-Flags |
| `GET /api/system_prompt/:agent[/:sub]` | System-Prompt-Text |
| `GET /api/health`, `GET /api/health-status` | Service-Health + Git-Stand |
| `GET /api/contacts` | Adressbuch aus E-Mail-Absendern — `?view=recent\|all`, `?q=search` |
| `GET /api/conversations[?agent=X]`, `GET /api/conversations/:id/messages` | Agent-Session-Historie |
| `POST /api/agents/:name/sessions` | Neue Agent-Session (optional mit `intent:"reply_to_message"` + `source_message_id` für Reply-Flow mit Thread-Kontext) |
| `POST /select_agent`, `POST /new_conversation`, `POST /chat` | Legacy Chat-Flow |
| `GET /api/access-control`, `POST /api/access-control` | Agent-Access-Matrix |
| `GET /api/oauth-status` | OAuth + API-Key-Config |

## Spezielle Backend-Konventionen

- **`conversation_id`**: WhatsApp/iMessage/kChat-Messages haben eine stabile Conversation-ID. Nutze `?group=conversation` wenn du Chats als Konversations-Liste willst, nicht flat.
- **`direction`**: Bei E-Mail-Sources liefert Backend per Default `received`. Für Sent-Ordner brauchts zusätzlichen Sync (noch nicht implementiert — Count wird aktuell 0 sein).
- **`bucket=other`**: Filtert E-Mails wo **kein** Empfänger auf `@tangerina.me`, `@signicat.com`, `@trustedcarrier.net` sitzt. Die Domain-Liste ist aktuell hartcoded (Konstante `_EMAIL_WORK_DOMAINS` in `web_server.py`), später per User-Setting editierbar.
- **Reply-Draft**: `POST /api/messages/:id/reply` erzeugt einen AppleScript-Draft in Apple Mail (öffnet den Compose-Editor mit vorausgefüllten Feldern). Der User muss dann manuell absenden. Fire-and-forget.

## Wenn Claude nicht reagiert

Wenn deine `BACKEND_TODO_*.md` nach 24h nicht in `FIXED_*.md` umbenannt ist:
- Evtl. ist die Datei nicht im Lovable-GitHub-Sync angekommen → `git log` im Repo checken
- User kann manuell `bash scripts/scan_api_todos.sh` anstoßen

## Bekannte Limitationen

- Sent-E-Mails sind noch nicht indexiert (`direction=sent` liefert 0)
- WhatsApp/iMessage-Write-API noch nicht implementiert (Reply nur für E-Mail)
- Contacts ist aus Message-Cache abgeleitet, kein separater DB-Table (OK für <10k Kontakte)
