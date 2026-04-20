# AssistantDev Frontend

React + Vite + TypeScript + Tailwind + shadcn/ui Neubau des bisher in
`src/web_server.py` inline eingebetteten HTML/CSS/JS.

## Stack

- **React 18** (StrictMode) + **react-router-dom** fuer Routing
- **Vite 5** als Dev- und Build-Tool, Output nach `frontend/dist/`
- **TypeScript 5** strict, mit `@/*` Alias auf `src/*`
- **Tailwind CSS 3** + shadcn/ui-kompatible CSS-Variablen (dark-mode default)
- **@tanstack/react-query** fuer Server-State
- **lucide-react** fuer Icons

## Setup

```bash
cd frontend
npm install
npm run dev       # http://localhost:5173 mit Proxy auf Backend :8080
npm run build     # erzeugt frontend/dist/
npm run preview   # statischer Preview
```

Sobald `frontend/dist/` existiert, serviert `src/web_server.py` diese Assets
(siehe `serve_static_frontend` in der Python-Quelle). Solange `dist/` fehlt,
bleibt das alte Legacy-HTML aktiv — der Umstieg ist also reversibel.

## Struktur

```
frontend/
├── index.html                    Mount-Point (#root)
├── package.json                  Dependencies + Scripts
├── vite.config.ts                Build- und Dev-Proxy-Config
├── tailwind.config.ts            Design-Tokens + shadcn-Variablen
├── tsconfig.json                 strict mode + path-Alias
├── components.json               shadcn/ui-Konfiguration
└── src/
    ├── main.tsx                  React-Root, Router, QueryClient
    ├── App.tsx                   Router-Definitionen
    ├── index.css                 Tailwind-Layer + CSS-Variablen
    ├── components/
    │   ├── layout/
    │   │   ├── Shell.tsx         Sidebar + Content-Bereich
    │   │   ├── Sidebar.tsx       Navigation
    │   │   └── PageHeader.tsx    Titel / Aktionen
    │   ├── ui/                   shadcn-Primitives (Button, Card, Separator)
    │   └── MigrationNotice.tsx   Platzhalter fuer offene Ports
    ├── pages/
    │   ├── Dashboard.tsx         /
    │   ├── Messages.tsx          /messages
    │   ├── Admin.tsx             /admin
    │   ├── AdminDocs.tsx         /admin/docs
    │   ├── AdminChangelog.tsx    /admin/changelog
    │   ├── AdminPermissions.tsx  /admin/permissions
    │   ├── Memory.tsx            /memory, /memory/:agent
    │   └── NotFound.tsx          *
    ├── lib/
    │   ├── api.ts                fetch-Wrapper + pywebview-Bridge
    │   ├── endpoints.ts          zentrale Endpunkt-Strings
    │   └── utils.ts              cn()-Helper fuer shadcn
    └── types/                    (vorbereitet fuer Domain-Typen)
```

## Migrationsstand

Die bisherige UI ist in vier Triple-Quoted-Strings in
[`src/web_server.py`](../src/web_server.py) implementiert:

| Template                | Zeilen-Range      | Ziel-Page                              | Status    |
| ----------------------- | ----------------- | -------------------------------------- | --------- |
| `HTML`                  | 3423 – 11526      | `Dashboard`, `Memory`-Teile            | ausstehend |
| `_MEMORY_PAGE_HTML`     | 11527 – 13386     | `Memory`                               | ausstehend |
| `_MSG_DASHBOARD_HTML`   | 13387 – 14240     | `Messages`                             | ausstehend |
| `_MSG_VIEW_HTML`        | 14241 – Ende      | `Messages` (Detail)                    | ausstehend |

Aktuell liefert das Frontend nur die Shell (Sidebar, Routing, Theme) plus
einen funktionsfaehigen API-Query am `/agents`-Endpunkt im Dashboard.
Alle weiteren Views zeigen einen `MigrationNotice`, der auf den zu
portierenden Legacy-Zeilenbereich verweist.

## Portierungs-Reihenfolge (Vorschlag)

1. **Chat-Flow im Dashboard** — Agent-Auswahl, Message-Stream, Send-Handler.
2. **Konversations-Sidebar** — Liste, Wechsel, Suche, Loeschen.
3. **Kontext-Panel** — Anhaenge, Working-Memory, Delegations-Hinweis.
4. **Posteingang** — Liste + Filter, danach Detail-Ansicht.
5. **Admin-Seiten** — Docs-Renderer, Changelog, Permissions-Status.
6. **Memory-Browser** — File-Tree + Editor pro Agent.

Pro Feature-PR: Komponenten unter `src/components/<feature>/`, Hooks unter
`src/hooks/`, Domain-Typen unter `src/types/`. Endpunkt-Strings nur aus
`lib/endpoints.ts` verwenden.

## pywebview-Bridge

`window.pywebview.api.*` ist in `src/lib/api.ts` ueber `pywebviewApi()` und
`isPywebview()` gekapselt. Im regulaeren Browser (Vite-Dev) bleibt die
Bridge `null` — die fetch-Routen funktionieren identisch, da das native
Fenster per HTTP mit dem gleichen `web_server.py` spricht.
