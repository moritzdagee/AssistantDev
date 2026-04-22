# FRONTEND TODO — UI-Feature-Batch (11 TODOs, natives Lovable-Terrain)

**Von:** Claude
**Datum:** 2026-04-22
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
