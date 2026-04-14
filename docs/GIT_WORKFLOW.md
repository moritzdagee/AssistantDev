# AssistantDev — Git Workflow & Branch-Strategie

Stand: 2026-04-14

---

## Branches

| Branch | Zweck | Wer arbeitet dran? | Schutz |
|---|---|---|---|
| `main` | Stable, produktiv (tagged Releases) | nur Merge-Ziel für Releases | **kein direkter Push** |
| `develop` | Integration aller neuen Features | Alle Dev-Arbeit läuft hier | normale Pushes erlaubt |
| `feature/<name>` | Einzelne Features | Kurzlebig, von develop abgezweigt | — |

---

## Sync-Policy

### Regel 1: Dev-Arbeit läuft auf `develop`

- LaunchAgents zeigen auf `~/AssistantDev/src/` (Working Tree)
- Der Working Tree ist **permanent auf `develop`** gecheckt-out
- `main` wird nie als aktiver Working-Tree-Branch benutzt

### Regel 2: Release-Merges: develop → main

Wenn ein stabiler Stand erreicht ist (Tests grün, App deployed, kein offener Bug):

```bash
git checkout main
git merge --no-ff develop -m "release: <datum> — <kurzer-titel>"
git tag -a v<version> -m "<release-notes>"
git push origin main --tags
git checkout develop   # zurück zur Arbeit
```

- `--no-ff` erzwingt einen expliziten Merge-Commit (bessere Historie)
- Tag dokumentiert Releases, macht Rollback einfach

### Regel 3: Keine Reverse-Merges main → develop

Wenn etwas direkt auf main gepatched wurde (Hotfix), dann:

```bash
git checkout develop
git cherry-pick <commit-sha>   # statt Merge
```

Warum: Merge-Commits "main → develop" verschmutzen die develop-Historie mit Merge-Noise.

### Regel 4: Keine Feature-Branches ohne PR/Review-Bedarf

Für Solo-Projekte: direkt auf develop committen. Feature-Branches nur wenn:
- Mehrere parallele Änderungen, die sich gegenseitig stören könnten
- Experimente, die evtl. verworfen werden
- Review vom User erwünscht

Skripte:
- `scripts/new_feature.sh <name>` — Branch von develop
- `scripts/finish_feature.sh <name>` — Merge in develop + Auto-Deploy (siehe post-merge Hook)

---

## Deploy-Flow

```
develop commit
    ↓
[optional] scripts/finish_feature.sh triggert scripts/deploy.sh
    ↓
git hook .git/hooks/post-merge → deploy.sh
    ↓
cp src/web_server.py → /Applications/Assistant.app/Contents/Resources/
cp src/search_engine.py → /Applications/Assistant.app/Contents/Resources/
pkill -f web_server.py
    ↓
App-Bundle startet Web Server neu (oder User startet manuell)
```

**Wichtig:** `email_watcher.py` und `kchat_watcher.py` werden **nicht** ins App-Bundle kopiert. Diese werden direkt aus `~/AssistantDev/src/` durch LaunchAgents ausgeführt — Änderungen sind sofort aktiv nach `launchctl unload/load`.

---

## Aktueller Zustand (2026-04-14)

### Branch-Divergenz

```
main:     bb586ad → f9c6759? (prüfen)
          └ letzte Commits: Phase 1 Docs
develop:  bb586ad → b65bdaa → 0263697 → f9c6759
          └ Phase 2 (Access Control UI, setup.sh, app.py Watcher-Fix)
```

`develop` ist 3 Commits voraus von `main`. Beide teilen sich `bb586ad` (Initial).

### Nächster Sync-Merge

Empfehlung: Nach diesem Dokumentations-Commit auf develop:

```bash
git checkout main
git merge --no-ff develop -m "release: 2026-04-14 — Phase 1+2 Architecture Consolidation"
git push origin main
git checkout develop
```

Ergebnis:
- main hat alle stabilen Änderungen
- develop bleibt die Arbeits-Basis
- Nächste Feature: `git checkout develop && <arbeiten>` → später wieder Merge

---

## Hotfix-Workflow (falls nötig)

Falls etwas produktives direkt auf main gepatched werden muss (z.B. kritischer Bug, der nicht auf develop warten kann):

```bash
git checkout main
git checkout -b hotfix/<name>
# ... fixen, committen ...
git checkout main
git merge --no-ff hotfix/<name>
git push origin main
# Zurück in develop nachziehen:
git checkout develop
git cherry-pick <commit-sha>   # NICHT git merge main
git branch -d hotfix/<name>
```

---

## Regeln (Kurzfassung)

- ✅ Arbeiten auf `develop`, pushen zu `develop`
- ✅ Releases: `develop` → `main` via `--no-ff` Merge + Tag
- ✅ Hotfixes: `hotfix/*` Branch → main → Cherry-Pick in develop
- ❌ Kein direkter Push auf `main`
- ❌ Kein Merge `main` → `develop` (immer Cherry-Pick)
- ❌ Kein `--force` Push auf `main` oder `develop`
