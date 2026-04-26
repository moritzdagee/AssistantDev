# FIXED — UI-Feature-Batch (11 TODOs, natives Lovable-Terrain)

**Status:** ✅ erledigt am 2026-04-22 via Lovable-Commit `1d17f63`
("Density-Sweep und Messages neu") + Claude-Commit `b191ac7`
**Von:** Claude
**Datum:** 2026-04-22

## Erledigung (2026-04-22)
Aus Changelog-Eintrag `[2026-04-22] FEATURE: Lovable Messages-Batch`:

1. ✅ **PER_COLUMN_SEARCH** + 6 Varianten — Per-Spalten-Suche via
   `/api/messages/search`, 250ms debounce via `useDebounced`, Counter
   `n/total`, X-Button + Esc, Loading/Empty/Error-States, QA-Pass.
2. ✅ **PER_COLUMN_SORT** + Dropdown-Variante — Sort-Dropdown mit
   3 Optionen (newest/oldest/unread-first) pro Spalte.
3. ✅ **MESSAGES_LAYOUT** — Flex → Grid `[auto-fit,minmax(220px,1fr)]`,
   alle 7 Quellen ohne H-Scroll auf 1280px.
4. ✅ **DENSITY_WHITESPACE** — Shell `p-6 → p-4/p-6`, PageHeader
   `mb-8 → mb-5`, Dashboard-Cards `p-5 → p-4`, `h-11 → h-9`,
   `text-2xl → text-xl`, Chat.tsx PageHeader durch 1-Zeiler-Strip ersetzt.
5. ✅ **PINNED_MESSAGES_TAB** — `ensureSystemTab('messages')` +
   `setPinned(TAB_MESSAGES_ID, true)` beim Shell-Mount.

Build grün. 11 zugehörige `BACKEND_TODO_*.md`-Dateien im Frontend-Repo
wurden zu `FIXED_*.md` umbenannt.

---

## Original-Briefing (Stand 2026-04-22)

**Kontext:** Lovables `BACKEND_TODO_*`-Sammlung enthält 11 Dateien, die laut
Inhalt reine Frontend-UI-Features sind — keine Backend-Endpoints nötig. Der
Backend-Stand deckt bereits alles Nötige:

- **Suche:** `GET /api/messages/search?source=X&q=Y` — pro-Source-Filter mit
  Highlighting.
- **Sortierung:** `/api/messages` liefert Messages mit `timestamp_epoch`,
  Client-seitig sortierbar.
- **Gruppierung:** `/api/messages?group=conversation` liefert Chat-Threads.
- **Supports-Read-Flag:** `/api/messages/sources[].supports_read` zeigt pro
  Quelle, ob Unread-Badge + Read-Toggle gerendert werden sollen (kommt seit
  heute).

Alle folgenden TODOs sollte Lovable selbst umsetzen. Claude kümmert sich
wenn dabei ein Backend-Bedarf auftaucht (→ neue `BACKEND_TODO_*.md` anlegen).

---

## 1. `BACKEND_TODO_PER_COLUMN_SEARCH.md` (+6 Varianten)

Searchbar pro Kanal-Spalte im Message-Dashboard. **Backend ist ready:**
`GET /api/messages/search?source=<key>&q=<text>&sort=date_desc&limit=50`
liefert `{total, results[]}` mit `<mark>`-Highlighting.

Varianten (alle Frontend-State + UX):
- `PER_COLUMN_SEARCH_COUNT` — Counter `X / Y` pro Spalte (nutze `total`-Feld
  der Response)
- `PER_COLUMN_SEARCH_RESET` — X-Button + Esc-Key + Reset-Shortcut
- `PER_COLUMN_SEARCH_SORT` — Sort-Dropdown in der Suche (nutze `sort=`-Param)
- `PER_COLUMN_SEARCH_STATES` — Loading / Empty / Error States pro Spalte
- `PER_COLUMN_SEARCH_QA` — QA-Checkliste (nach Implementation durcharbeiten)

**Empfohlenes Hook-Schema:**
```ts
function useColumnSearch(source: string) {
  const [q, setQ] = useState('');
  const debounced = useDebounce(q, 250);
  const query = useQuery({
    queryKey: ['messages-search', source, debounced],
    queryFn: () => api.get(`/api/messages/search?source=${source}&q=${debounced}`),
    enabled: debounced.length > 0,
  });
  return { q, setQ, ...query };
}
```

## 2. `BACKEND_TODO_PER_COLUMN_SORT.md` + `PER_COLUMN_SORT_DROPDOWN.md`

Sort-UI pro Spalte. Backend liefert Messages mit `timestamp_epoch`, `read`-Flag —
Client-seitig sortierbar. Zwei Varianten in den TODOs dokumentiert; **wähle
eine**:
- Icon-Popover (kompakter)
- Dropdown (expliziter)

Empfehlung Icon-Popover — weniger Screen-Fläche.

## 3. `BACKEND_TODO_MESSAGES_LAYOUT.md` — 2-Zeilen-Grid

Grid `auto-fit minmax(280px, 1fr)` mit `grid-template-rows` + reduzierten
Card-Höhen, damit alle 7 Quellen auf 1280px ohne Scroll sichtbar sind.
Reines CSS. Backend-Daten unverändert.

## 4. `BACKEND_TODO_DENSITY_WHITESPACE.md` — Spacing-Sweep

`Shell.tsx`, `PageHeader.tsx`, `Dashboard.tsx`, `Chat.tsx` — Padding/Gap
reduzieren (statt `p-8` → `p-6`, Headline `text-3xl` → `text-2xl`). Reines
Tailwind-Tuning.

## 5. `BACKEND_TODO_PINNED_MESSAGES_TAB.md` — Message-Dashboard als Pin-Tab

TabStore-Erweiterung: einen permanenten `pinned` Tab mit `kind:'messages'`
registrieren. Shell mounted ihn beim Start. Keine Backend-Arbeit —
Messages-Data kommt schon über `useQuery(endpoints.conversations)`.

---

## Was Claude noch bauen würde (falls Bedarf entsteht)

- Search-Performance: falls Client-seitige Filter zu langsam werden, Backend
  könnte FTS-Index bekommen (aktuell in-memory fast genug).
- Sort-State-Persistence: wenn Sort-Settings serverseitig synchronisiert
  werden sollen, braucht es `user_settings`-Tabelle. Aktuell reicht
  `localStorage`.

## Wenn du (Lovable) einen dieser TODOs umsetzt

- `BACKEND_TODO_<TOPIC>.md` in deinem Repo umbenennen zu `FIXED_<TOPIC>.md`
- Bei neuem Backend-Bedarf: neue `BACKEND_TODO_<TOPIC>.md` schreiben,
  Claude sieht das beim nächsten Scan

Nach Fix dieser Datei: `FIXED_UI_FEATURE_BATCH.md`.
