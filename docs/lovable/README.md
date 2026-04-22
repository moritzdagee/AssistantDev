# Claude → Lovable — TODOs & Nachrichten

Dies ist der **Claude-zu-Lovable**-Kommunikationskanal. Das Gegenstück zu den
`BACKEND_TODO_*.md`-Dateien, die Lovable im Frontend-Repo ablegt.

## Workflow

Zwei Richtungen, beide public-readable:

| Richtung | Ort | Wer legt an | Wer liest |
|---|---|---|---|
| **Frontend → Backend** (Lovable braucht neuen Endpoint) | `assistantdev-frontend-*`-Repo, `src/components/BACKEND_TODO_*.md` | Lovable | Claude (via `scripts/scan_api_todos.sh`) |
| **Backend → Frontend** (Claude braucht Frontend-Anpassung, Shape-Änderung, neue Page etc.) | `AssistantDev`-Repo, `docs/lovable/FRONTEND_TODO_*.md` | Claude | Lovable (liest das Repo, weil es `public` ist) |

## Konventionen

- **Datei-Präfix**: `FRONTEND_TODO_<TOPIC>.md` — klar erkennbar als Nachricht an Lovable
- **Erledigt**: Dateien umbenennen auf `FIXED_<TOPIC>.md` (nicht löschen, damit History nachvollziehbar bleibt)
- **Format**: Markdown mit klarer Überschrift, Request/Response-Shapes wenn relevant, konkrete Datei-Pfade falls bekannt

## Typische Anwendungsfälle

1. **Shape-Diff**: Lovables Frontend erwartet einen anderen JSON-Shape als das Backend liefert → Claude dokumentiert den Diff, Lovable passt den Hook oder Component an
2. **Neue Backend-Daten verfügbar**: Claude baut einen neuen Endpoint und will, dass Lovable ihn verwendet (z.B. statt Mock)
3. **Deprecation-Warnings**: Claude ändert/entfernt einen Endpoint → Lovable muss das im Frontend berücksichtigen
4. **UX-Requests**: Claude bemerkt beim Debuggen eine Gelegenheit für Frontend-Verbesserung → dokumentiert sie hier

## Für Lovable

Wenn du (Lovable) das liest: vor jeder Frontend-Iteration einmal in diesen Ordner schauen
und die `FRONTEND_TODO_*.md`-Dateien abarbeiten. Fertige Sachen in `FIXED_*.md` umbenennen
(macht Claude beim nächsten Sync ggf. auch).

Erreichbar auch via: https://github.com/moritzdagee/AssistantDev/tree/main/docs/lovable
