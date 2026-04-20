# AssistantDev — Regeln fuer Claude Code

## ⚠️ ARBEITSWEISE: VOLLSTÄNDIG AUTONOM

Du arbeitest IMMER autonom und ohne Rueckfragen. Das gilt absolut.

**Niemals fragen:**
- "Soll ich X machen?"
- "Darf ich Y aendern?"
- "Moechtest du, dass ich Z?"
- "Soll ich fortfahren?"
- "Bist du sicher?"

**Immer direkt:**
- Aufgabe lesen → analysieren → umsetzen → berichten
- Bei Unklarheiten: die wahrscheinlichste Interpretation waehlen und handeln
- Am Ende kurz berichten was gemacht wurde – nicht vorher fragen

**Einzige Ausnahme:** Wenn eine Aktion IRREVERSIBEL und DESTRUKTIV waere (z.B. Daten unwiderruflich loeschen ohne Backup). Dann einmal kurz flaggen, aber keinen Workflow-Stop.

## PFLICHT VOR JEDER AENDERUNG: BACKUP

Bevor du eine Datei aenderst, MUSST du ein Backup anlegen. Ohne Ausnahme. Auch bei kleinen Fixes.

Backup-Befehl:
```
bash ~/AssistantDev/scripts/backup.sh [datei1] [datei2]
```

Pflicht-Reihenfolge bei JEDER Aufgabe:
1. BACKUP der betroffenen Dateien
2. Aenderung vornehmen
3. Syntax pruefen: `python3 -m py_compile [datei]`
4. Changelog-Eintrag in `changelog.md`

Dateien die IMMER gesichert werden muessen:
- src/web_server.py
- src/email_watcher.py
- src/app.py
- src/web_clipper_server.py
- src/search_engine.py
- config/models.json
- config/subagent_keywords.json

## SYNTAX CHECK

Nach jeder Python-Aenderung:
```
python3 -m py_compile [datei]
```
Falls Fehler: sofort melden, nicht weitermachen.

## FRONTEND-CHECK (PFLICHT bei web_server.py Aenderungen)

web_server.py enthaelt inline HTML/CSS/JS in einem Python triple-quoted String.
JEDE Aenderung an JS-Code darin kann die gesamte App zerstoeren (ein JS-SyntaxError
blockiert ALLE Funktionen inkl. Agent-Auswahl).

**BEKANNTES PROBLEM:** `\n` in Python triple-quoted Strings wird zum echten Newline.
Wenn du JS-Strings mit Newlines brauchst, verwende `\\\\n` im Python-Source
(damit Python `\\n` ausgibt, was JS als Escape-Sequence interpretiert).

**NACH JEDEM DEPLOY von web_server.py MUSS der Test laufen:**
```
python3 tests/run_tests.py
```
Die Test-Suite prueft automatisch:
- Keine offenen JS-Strings (unterminated string literals)
- Keine Python-Escape-Artefakte in JS-Strings
- Alle kritischen JS-Funktionen vorhanden (showAgentModal, selectAgent, etc.)
- Agent-Modal HTML-Struktur intakt

## CHANGELOG

Jede Aenderung in `changelog.md` dokumentieren.

## KEINE DATEIEN LOESCHEN

Niemals loeschen — nur ins backups/ verschieben.

## PORTS

- 8080: Web Server (web_server.py)
- 8081: Web Clipper Server (web_clipper_server.py)

Nicht aendern ohne explizite Anweisung.

## PFLICHT: Tests nach jeder Aenderung

Nach JEDER Aenderung an web_server.py MUSS folgendes ausgefuehrt werden:

1. Syntax pruefen: `python3 -m py_compile src/web_server.py`
2. Tests ausfuehren: `python3 ~/AssistantDev/tests/run_tests.py`
3. Deploy via `bash scripts/deploy.sh` (SIGTERM an alten Server, Neustart aus `src/`, Healthcheck auf :8080)
4. Nur wenn alle Tests gruen + Healthcheck OK: changelog.md aktualisieren
5. Bei roten Tests oder fehlgeschlagenem Healthcheck: Fehler beheben, dann nochmal

NIEMALS deployen ohne gruene Tests!

## PFLICHT: Unit Tests fuer neue Features

Fuer JEDES neue Feature oder jeden Bugfix MUESSEN neue Unit Tests in `tests/run_tests.py` ergaenzt werden:

- Neue HTML-Elemente: pruefen ob sie im HTML vorhanden sind
- Neue CSS-Klassen: pruefen ob sie im HTML vorhanden sind
- Neue JS-Funktionen: pruefen ob Funktionsname im HTML vorhanden ist
- Neue Backend-Routen: mit curl/requests testen (Response-Format, Status-Code)
- Neue search_engine Funktionen: Import-Test + Basis-Funktionstest
- Entfernte Elemente: pruefen ob sie NICHT mehr im HTML sind
- Geaenderte Defaults: pruefen ob der neue Default-Wert korrekt ist

Tests gehoeren in die passende Sektion oder eine neue `section("Features YYYY-MM-DD")`.
Testsuite MUSS nach jeder Aenderung grueen bleiben. Aktueller Stand: 453 Tests.

## CLAUDE CODE PROMPTS — STIL-REGEL

Claude Code ist kompetent. Schreibe Prompts die **Was** und **Warum** erklaeren, nicht **Wie**.

**Richtig:**
- Beschreibe das gewuenschte Verhalten und die Anforderungen
- Nenne Fallstricke und Constraints (z.B. duplizierte Bloecke, keine direkten Edits)
- Definiere klare Akzeptanzkriterien fuer die Tests

**Falsch:**
- Fertige Code-Snippets vorschreiben
- Regex-Pattern oder JavaScript-Funktionen bereits ausformulieren
- Claude Code erklaeren wie er Strings ersetzen soll

Claude Code liest die Dateien selbst, versteht den Kontext selbst, und schreibt den Code selbst. Deine Aufgabe ist es, praezise Anforderungen zu formulieren — nicht, die Loesung vorwegzunehmen.

## LAUFZEIT & DEPLOYMENT

Der Web Server laeuft **direkt aus `src/web_server.py`** — es gibt keinen App-Bundle-Copy-Schritt mehr.

- Deploy ausschliesslich via `bash scripts/deploy.sh`:
  sendet SIGTERM an den auf :8080 lauschenden Prozess, wartet bis zu 35s auf sauberes Ende,
  startet `/usr/bin/python3 -u web_server.py` aus `src/`, macht Healthcheck auf `/agents`.
- Watchdog-LaunchAgent `com.assistantdev.watchdog` startet den Server bei Crash neu (`logs/watchdog.log`).
- `/Applications/AssistantDev.app/` ist nur noch ein Launcher-Wrapper fuer das native
  Dashboard-Fenster (pywebview) — enthaelt KEINE Python-Quellen mehr. Niemals dorthin kopieren.

## Entwicklungs-Workflow (PFLICHT)

Historisch wurden Aenderungen an `src/web_server.py` und `src/search_engine.py` ueber
`patch_*.py`-Skripte in `scripts/` gemacht, die per Text-Suche-und-Ersetzen arbeiten.
Das ist ab sofort **verboten**. Text-Replacement ist fragil, hat zu JS-Breakage gefuehrt
und macht Aenderungen nicht nachvollziehbar.

**Regeln:**
- Alle Aenderungen an `src/web_server.py` und `src/search_engine.py` passieren DIREKT
  mit dem Edit-Tool im jeweiligen Feature-Branch.
- NIEMALS neue `patch_*.py`-Skripte in `scripts/` erstellen.
- NIEMALS Text-Replacement-Skripte schreiben, die Source-Dateien suchen und ersetzen.
- Vor jeder Aenderung: Feature-Branch via `scripts/new_feature.sh <name>` erstellen.
- Backup der Datei via `scripts/backup.sh` (wie bisher Pflicht).
- Aenderungen direkt in `src/web_server.py` bzw. `src/search_engine.py`.
- Nach Aenderung: Syntax-Check, Tests (`python3 tests/run_tests.py`), Deploy via
  `scripts/deploy.sh`, Abschluss via `scripts/finish_feature.sh <name>`.

**Ausnahme fuer `web_server.py`:** Die Datei enthaelt duplizierte Blocke
(Zeilen 1-500 entsprechen ungefaehr 570-1100). Wenn beide Blocke synchron geaendert
werden muessen, darf ein Python-Skript helfen — aber nur durch **strukturiertes
Parsen** (AST / Zeilen-Ranges), nicht durch Text-Replacement. Fuer normale Bugfixes
ist Edit-Tool am richtigen Block erste Wahl.

## Stabilitaets-Tools (Selbsthilfe)

Drei Skripte in `scripts/` ermoeglichen schnelle Diagnose und Recovery ohne Claude:

- `bash scripts/status.sh` — Uebersicht: laufende Prozesse, Ports, Git, letzte Logs, Backups
- `bash scripts/rollback.sh` — interaktives Rollback auf ein Backup von web_server.py / search_engine.py
- `scripts/watchdog.sh` — laeuft alle 60s via LaunchAgent `com.assistantdev.watchdog`,
  startet `web_server.py` automatisch neu bei Ausfall. Log: `logs/watchdog.log`.

## Git Workflow

Repository: github.com/moritzdagee/AssistantDev (private)
Branches: main (stable), develop (integration), feature/* (Arbeit)

**Branching-Regeln:**
- Neue Features immer von `develop` abzweigen: `scripts/new_feature.sh <name>`
- Feature fertig: `scripts/finish_feature.sh <name>` (merged in develop)
- Deploy: `scripts/deploy.sh` (stoppt alten Server, startet neu aus `src/`, Healthcheck)
- Claude-Aufgabe starten: `scripts/claude_task.sh "<aufgabe>" [branch-name]`

**Workflow:**
1. `scripts/new_feature.sh mein-feature` — erstellt feature/mein-feature von develop
2. Aenderungen vornehmen, testen, committen
3. `scripts/finish_feature.sh mein-feature` — merged in develop, loescht Feature-Branch
4. Bei Release: develop in main mergen

**Commits:**
- Aussagekraeftige Commit-Messages auf Deutsch oder Englisch
- Kein force-push auf main oder develop
