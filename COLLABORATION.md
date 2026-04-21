# AssistantDev Frontend-Collaboration — Setup-Übersicht

Wie Lovable, GitHub und Claude Code zusammenarbeiten, um am selben Produkt zu bauen — Lovable für Design, Claude für Engineering, ohne dass sich die beiden gegenseitig überfahren.

## Die drei Spieler

- **Lovable** (lovable.dev) — visuelles Design-Tool. Du klickst „Publish", Lovable committet.
- **GitHub** — zwei **getrennte** öffentliche Repos:
  - [`moritzdagee/AssistantDev`](https://github.com/moritzdagee/AssistantDev) — Backend (Python/Flask, Port 8080) + Ops-Skripte
  - [`moritzdagee/assistantdev-frontend`](https://github.com/moritzdagee/assistantdev-frontend) — Frontend (React/Vite/Tailwind, served unter `/app`)
- **Claude Code** (dieser CLI) — liest/schreibt beide Repos lokal, verdrahtet UI mit Backend.

## Arbeitsteilung im Frontend-Repo

Festgeschrieben in [`frontend/ARCHITECTURE.md`](https://github.com/moritzdagee/assistantdev-frontend/blob/main/ARCHITECTURE.md):

| Ordner | Wer | Was |
|---|---|---|
| `src/components/` | **Lovable** | Reine UI — Props rein → JSX raus. Keine API-Calls. |
| `src/pages/` | Claude | Container, ruft Hooks, reicht Props durch |
| `src/hooks/` | Claude | Data-Hooks (`useAgents`, später `useMessages`, …) mit API-Adaptern |
| `src/lib/` | Claude | API-Client, Endpoint-Konstanten |
| `src/main.tsx`, `App.tsx` | Claude | Provider-Hierarchie, Router |

**Referenz-Implementierung:** `Dashboard.tsx` (13 Zeilen Container) + `DashboardView.tsx` (pure UI) + `useAgents.ts` (Hook mit Backend-Adapter). Beim Bauen neuer Pages daran orientieren.

## Typischer Zyklus

1. **Design in Lovable** — Prompt-Baustein: *„Halte dich an ARCHITECTURE.md, baue nur in `src/components/`, keine API-Calls, keine Änderungen in `pages/` oder `hooks/`."*
2. **„Publish" klicken** — Lovable pusht auf `main` als Author `gpt-engineer-app[bot]`.
3. **„sync alles" an Claude** → `bash scripts/sync_all.sh` macht automatisch:
   - fetch/pull/push beider Repos
   - `develop → main` Merge im Backend
   - **Territorium-Guard**: warnt bei Lovable-Commits außerhalb `components/`
   - `bun run build` wenn Frontend-Commits neu sind
   - `scripts/deploy.sh` — Backend-Neustart
   - **Playwright-Smoketest**: lädt `/app` headless, prüft `#root` gefüllt + Console-Errors + 404s
   - Status-Report (Commit-SHAs, offene PRs)
4. **Claude verdrahtet** neue Lovable-Components mit Hook + Page-Container.
5. **App öffnen** aus Dock → Launcher → `/app` → React-UI mit echten Backend-Daten.

## Safety-Nets

| Schutz | Was er verhindert |
|---|---|
| 2 getrennte Repos | Lovable kann Backend nicht aus Versehen kaputtmachen |
| `ARCHITECTURE.md` + Territorium-Guard | Lovable-Commits in `pages/` rutschen nicht still durch |
| Playwright-Smoketest | Schwarzes Fenster (JS-Crash, 404, Router-Fehler) wird vor Release erkannt |
| `pywebview debug=True` | Rechtsklick → „Element untersuchen" → Console für Live-Debugging |
| Python-Grep-Tests (`tests/run_tests.py`) | Textregressionen (Route fehlt, Flag geändert, Launcher-Default) |
| Feature-Branches für Claude-Arbeit | Lovable trifft nie auf halbfertigen Claude-Stand |
| Auto-Backup in `backups/` vor jeder Änderung | Reversibel auch ohne Git |

## Wenn was schiefgeht

- **Schwarzes Fenster** → Rechtsklick im Dashboard → „Element untersuchen" → Console → Screenshot an Claude
- **Territorium-Warnung beim Sync** → `git show <range> -- <datei>` prüfen, mit Claude entscheiden: revert oder übernehmen
- **Backend offline** → `bash scripts/status.sh` + ggf. `bash scripts/deploy.sh`
- **Git-Konflikt nach Lovable-Push** → Claude fragen, nicht von Hand mergen

## Wichtige Kommandos

```bash
bash scripts/sync_all.sh              # Sync beider Repos + Build + Smoketest
bash scripts/status.sh                # Service-Health, offene Backups
bash scripts/deploy.sh                # Backend-Restart aus src/
python3 tests/run_tests.py            # Python-Grep-Tests
python3 tests/test_frontend_smoke.py  # Browser-Smoketest (Chromium headless)
```

## Kern-Idee in einem Satz

Lovable macht Design, Claude macht Engineering, zwei separate Repos halten beide Welten unabhängig, und `sync_all.sh` + Playwright-Smoketest + Territorium-Guard sorgen dafür, dass Regelverstöße sofort sichtbar sind statt still in einem schwarzen Fenster zu enden.
