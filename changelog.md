# Changelog — AssistantDev

Format: [Datum] Änderung | Datei | Grund

---

## 2026-04-14

### Global Search Index aufgebaut
- `GlobalSearchIndex` via `search_engine.py` CLI ausgefuehrt
- **110.555 Dateien indexiert** in 1480s (~24.7 min), 116 MB Datei
- Location: `~/Library/Mobile Documents/com~apple~CloudDocs/Downloads shared/.global_search_index.json` (auf Downloads-shared-Ebene, NICHT in claude_datalake/ — so im Code definiert)
- Verteilung: global=46.288, email_inbox=21.117, privat=29.655, signicat=10.926, trustedcarrier=2.569
- Unblocked: globale Suche ueber alle Agenten via `/global_search_preview` Route

### Debug-Investigation: E-Mail Reply-Suche "sebastian + Follow" liefert []
- **Gemeldetes Symptom:** UI findet keine E-Mail fuer Von=sebastian, Betreff=Follow.
  Erwartet wurde "RE: Follow-up: Neue SOW-Version fuer Ikano" von sebastian.schroeder@ikano.de.
- **Root Cause:** Kein Bug. Die gesuchte E-Mail existiert nicht im Memory.
  - Alle 35+ Dateien mit `sebastian_schroeder@ikano.de` im signicat/memory-Ordner tragen
    einheitlich den Betreff `RE: Signicat - Question regarding IDV for recovery process`.
  - Volltext-grep ueber signicat/memory nach `SOW-Version` liefert 0 Treffer in .txt/.eml
    (nur Referenzen in `conversations.json` / `memories.json`).
  - Eine E-Mail mit Betreff `Follow*` von einem `sebastian*` Absender existiert in keinem Agenten.
- **Such-Logik (web_server.py `/api/email-search`) bereits korrekt:**
  - Sub-Agent-Routing: `get_agent_speicher()` mappt `signicat_outbound` → `signicat/memory` (OK)
  - Content-Matching: `_parse_txt_email` liest Von:/Betreff:/Datum:/An: aus Datei-Inhalt (OK)
  - Case-insensitive via `.lower()`, partial match via `in` (OK)
  - Response enthaelt Von, Betreff, Datum, Message-ID, Dateiname (OK)
- **Verifikation live:**
  - `?agent=signicat&from=sebastian` → 8 Treffer (alle mit Subject "Re: Signicat - Question...")
  - `?agent=signicat&subject=Ikano` → 8 Treffer (Laura Moisi / Simonas Vyšniūnas "Re: New Ikano Bank SOW")
  - `?agent=signicat&from=sebastian&subject=Follow` → `[]` (korrekt, existiert nicht)
- **Keine Code-Aenderung**, kein Deploy, kein Backup noetig.
- `docs/API_REFERENCE.md`: Menschenlesbare Dokumentation aller 12 `/api/*` Routes (Parameter, Response-Format, Konventionen)
- `docs/openapi.yaml`: Maschinenlesbare OpenAPI 3.0 Spec fuer Tooling-Integration (Swagger UI, Postman, Codegen)
- `docs/GIT_WORKFLOW.md`: Branch-Strategie definiert
  * main = stable, develop = Arbeits-Basis, Working Tree permanent auf develop
  * Releases: develop → main via `--no-ff` Merge + Tag
  * Hotfixes: hotfix/* → main → Cherry-Pick in develop (nie Reverse-Merge)
  * Deploy-Flow dokumentiert (web_server via App-Bundle, watcher via LaunchAgent)
- Globaler Search-Index wird aufgebaut (`.global_search_index.json`, im Hintergrund)

### Fix: Rogue email_watcher/kchat_watcher Respawn eliminiert
- **Root Cause gefunden:** `src/app.py` (Menu-Bar-App) registrierte email_watcher und kchat_watcher als Services, die vom Watchdog alle 15s respawnt wurden
- Gleichzeitige LaunchAgents (com.moritz.emailwatcher, com.assistantdev.kchat_watcher) starteten dieselben Skripte → doppelte Prozesse mit Race-Conditions
- **Fix:** Email Watcher + kChat Watcher aus der `self.services` Liste in `app.py` entfernt (LaunchAgents sind authoritativ)
- Assistant.app neu gestartet mit neuem Code, orphaned watcher-Prozesse gekillt
- Finaler Zustand: **je genau 1 Prozess pro Watcher** (beide aus ~/AssistantDev/src/ via LaunchAgent)
- Dateien: `src/app.py`, deployed zu `/Applications/Assistant.app/Contents/Resources/app.py`

### Contact Name-Mismatch Fix (macOS AddressBook)
- **Problem:** 97 Kontakte mit Namen, die zu keiner ihrer E-Mail-Adressen passen (z.B. `Gotberg Paul (Innovalue) ← verena.hinrichs@me.com`, `Arne Hassel (Barclays) ← sean.walsh@marketsgroup.org`). Ursache unklar — vermutl. Apple Mail Auto-Save mit vertauschten Headers.
- **Scanner:** NFD-normalisierter Fuzzy-Match pro Kontakt (Name-Tokens vs. E-Mail-Local-Part + Org-vs-Domain). De-dup ueber 5 Source-DBs.
  - Report: `claude_outputs/contact_namemismatch_20260414_v2.json` + `contact_namemismatch_review_20260414.md`
- **Fix-Regel (User-Entscheidung):** Bei allen KRITISCH-Faellen wird `ZFIRSTNAME=""`, `ZLASTNAME=<email>`, `ZORGANIZATION=<domain>` gesetzt — macht Kontakt self-consistent, keine Loeschung.
- **Angewendet:**
  - 97 Kontakte umbenannt (61 in A42FFC88, 36 in EF91BA64)
  - 14 E-Mail-Eintraege aus PARTIELL-Kontakten entfernt (nur NO-E-Mails, OK-Adressen + Kontakte bleiben)
  - `ZMODIFICATIONDATE` aktualisiert → iCloud-Sync triggert automatisch
- **Backups:**
  - `Sources/A42FFC88.../AddressBook-v22.abcddb.backup_20260414_135523`
  - `Sources/EF91BA64.../AddressBook-v22.abcddb.backup_20260414_135523`
- **Details-Log:** `claude_outputs/contact_fix_applied_20260414.md`
- **User-Action noetig:** Contacts.app und Mail.app einmal neu starten, damit UI-Cache aktualisiert und iCloud-Sync durchlaeuft.

### Contact Mismatch Praeventiv-Check (Zukunftssicherung)
- **Analyse:** User-Aufgabe beschrieb "hunderte E-Mails pro Kontakt" — trifft auf aktuelles Datenmodell nicht zu.
  - Agent-contacts.json (privat/signicat/standard/trustedcarrier, 133 Kontakte total) sind 1:1 Name→Email; keine Listen, keine eigenen E-Mails bei fremden Kontakten, 0 kritische Mismatches.
  - macOS AddressBook (3947 Kontakte, 2382 E-Mails) ist nach `fix_contacts_pollution.py` (2026-04-09) sauber: Sebastian Schroeder Z_PK=238 hat 1 E-Mail (vorher 64). Kein "Bernhard Heinrich" Kontakt existiert.
  - Fazit: keine Bereinigung noetig, `email_watcher.py` ruft `update_contacts_json` bereits nur fuer `not is_own(contact)` auf — Blacklist besteht.
- **Hardening:**
  - `src/email_watcher.py`: Fallback-Liste in `get_own_addresses()` erweitert um 5 fehlende Adressen (moritz@brandshare.me, cremer.moritz@gmx.de, family.cremer@gmail.com, moritz.cremer@trustedcarrier.de, naiaraebertz@gmail.com).
  - `~/.emailwatcher_own_addresses.json` um dieselben Adressen ergaenzt (backup .backup_*).
- **Neu: `scripts/contact_watchdog.py`** — taegliche Pruefung beider Quellen, read-only.
  - macOS AddressBook: warnt bei Kontakten mit ≥5 E-Mails aus ≥3 Domains.
  - Agent contacts.json: warnt bei eigenen E-Mails unter fremdem Namen.
  - Schreibt Warnung nach `claude_outputs/contact_watchdog_warning_YYYYMMDD.txt` NUR bei Fund.
  - Erstrun 2026-04-14: 4 Warnungen (Bitbond/Yalwa-Mitarbeiter mit Mehrfachadressen, eigener Moritz-Cremer-Eintrag) — alles plausibel, keine Action noetig.
- **LaunchAgent `com.assistantdev.contactwatchdog`** — 09:00 daily, Log `logs/contact_watchdog.log`, geladen und aktiv.
- Backups: `src/email_watcher.py` in `backups/2026-04-14_12-59-14/`
- Dateien: `src/email_watcher.py`, `scripts/contact_watchdog.py` (neu), `~/Library/LaunchAgents/com.assistantdev.contactwatchdog.plist` (neu)

### Architektur-Audit Phase 2 — Access Control UI, Watcher-Konsolidierung, setup.sh, Recovery-Test
- **Aufgabe 1: Access Control Web UI**
  - `BASE/config/access_control.json` angelegt mit 9 Agenten (privat, signicat, signicat_lamp, signicat_meddpicc, signicat_outbound, signicat_powerpoint, system ward, trustedcarrier, trustedcarrier_instagramm)
  - 3 neue Routes in `web_server.py`: `GET /admin/access-control` (HTML), `GET /api/access-control` (JSON), `POST /api/access-control` (Speichern + Validierung)
  - Admin-Button (Zahnrad) im Header neben Agent-Button — oeffnet Admin-UI in neuem Tab
  - Dunkles Theme (#1a1a2e) passend zum Haupt-UI, Checkboxen fuer own_memory/shared_memory, Text-Input fuer cross_agent_read
- **Aufgabe 2: email_watcher Konsolidierung**
  - Diagnose: 3 parallele Prozesse (PIDs 5905, 86235 aus /Applications/, PID 57665 aus src/ aber alte Version)
  - Zombies 5905 und 86235 gekillt
  - LaunchAgent neu geladen → neuer Prozess nutzt aktuelle Dual-Write-Version
  - LaunchAgent plist korrekt: zeigt auf `~/AssistantDev/src/email_watcher.py` (kein Fix noetig)
  - Finaler Zustand: **3 Prozesse → 1 Prozess** (nur LaunchAgent)
- **Aufgabe 3: setup.sh Disaster Recovery Skript**
  - Neues `~/AssistantDev/setup.sh` (ausfuehrbar)
  - 5 Stufen: Systemvoraussetzungen → Verzeichnisstruktur → LaunchAgents → App-Deployment → models.json Template
  - Python-Paket-Check mit automatischer Nachinstallation (12 Packages)
  - Legt `BASE/config/models.json.template` an als Referenz fuer API-Keys
- **Aufgabe 4: Dual-Write Recovery-Test**
  - Mirror `BASE/config/email_processed_log.json` angelegt (21.117 Eintraege)
  - Test-Szenario: lokale Datei geloescht → watcher recovered aus iCloud → 21.117 Eintraege wieder da
  - Log-Output: `[WATCHER] Recovered processed log from iCloud mirror (21117 entries)`
  - **Recovery: BESTANDEN**
- Dateien: `src/web_server.py`, `setup.sh`, `scripts/add_access_control_ui.py`, `BASE/config/access_control.json`, `BASE/config/email_processed_log.json`, `BASE/config/models.json.template`

### Architektur-Audit Phase 1 — Abschluss (Git + Docs)
- **git commit + push:** `src/email_watcher.py` Dual-Write Aenderung auf `develop` gepusht
  - Commit `b65bdaa`: "fix: email_watcher dual-write iCloud mirror fuer disaster recovery"
  - Kein Deployment nach /Applications/ noetig — LaunchAgent zeigt auf `~/AssistantDev/src/`
  - ACHTUNG: Laufende email_watcher-Prozesse nutzen noch alte Version; manuelle Neustarts ausstehend
- **TECHNICAL_DOCUMENTATION.md aktualisiert:** 4 neue Abschnitte
  - §13 Services: vollstaendige Tabelle mit Ports, LaunchAgents, Status
  - §14 Bekannte Probleme: email_watcher Mehrfach-Instanz, Global Index fehlt, Access Control fehlt
  - §15 Datalake Struktur: aktuelle Zahlen pro Agent nach Cleanup
  - §16 Disaster Recovery: Dual-Write-Mechanismus dokumentiert
- Dateien: `docs/TECHNICAL_DOCUMENTATION.md`

### Architektur-Audit Phase 1 + Datalake Cleanup
- **Ist-Analyse:** 9 Python-Services in src/, 3 LaunchAgents aktiv (emailwatcher, kchat_watcher, calendar-export)
  - WARNUNG: 3 parallel laufende email_watcher.py Prozesse (PIDs 5905, 86235, 57665) — mischen aus App-Bundle + Dev-Pfad
  - `.global_search_index.json` existiert NICHT (nur pro-Agent Indizes)
  - `config/access_control.json` existiert NICHT — muss fuer Phase 2 angelegt werden
- **contacts.json Deduplizierung:** Alle 4 Agenten gecheckt, 0 Duplikate nach E-Mail gefunden (waren bereits sauber)
  - Backups: `contacts.json.backup_20260414_115713`
- **Attachments-Unterordner angelegt:** `memory/attachments/` in allen 4 Agenten
  - privat: 287 Dateien verschoben (PDFs, CSVs, Bilder)
  - signicat: 1367 Dateien verschoben (UUIDs, RTFs, PPTX, Bilder)
  - standard: 54 Dateien verschoben
  - trustedcarrier: 73 Dateien verschoben
  - Regel: `.eml`/`.txt`/`.json` bleiben, alles andere → attachments/
  - Gesamt: 1781 Dateien verschoben, 0 Fehler
- **email_watcher.py Dual-Write:** Processed-Log wird jetzt zusaetzlich nach `BASE/config/email_processed_log.json` gespiegelt
  - `load_processed()` faellt auf iCloud-Mirror zurueck wenn lokal leer/nicht vorhanden
  - `save_processed()` schreibt nach lokalem Pfad UND iCloud-Mirror (best-effort)
  - Backup: `src/email_watcher.py` in `backups/2026-04-14_11-58-08/`
- Dateien: `src/email_watcher.py`, `scripts/dedupe_contacts.py`, `scripts/create_attachments_folder.py`, `scripts/patch_email_watcher_dualwrite.py`

### Feature: Kalender-Integration — Data Lake Export + Memory fuer alle Agenten
- Neues Skript `scripts/export_calendar.py`: Exportiert alle macOS Kalender (Apple Calendar + Fantastical-Accounts) in den AssistantDev Data Lake
- **Erfolgreiche Methode:** EventKit via PyObjC (icalBuddy nicht installiert — Fallback AppleScript vorhanden)
- **Exportiert:** 1338 Events aus 11 Kalendern (Privat, Calendar, Moritz Cremer, londoncityfox@gmail.com, moritz@demoscapital.co, Übertragen von moritz@cassiopeia-consulting.io, Birthdays, Feiertage in Deutschland, Feiertage in Großbritannien, Feriados, United Kingdom holidays)
- **Zeitraum:** 30 Tage rueckwaerts bis 180 Tage voraus (parametrisierbar via `--days-back`, `--days-forward`, `--calendars`, `--output-dir`)
- **Output (Data Lake):** `claude_datalake/calendar/calendar_events.json` (maschinenlesbar) + `calendar_summary.txt` (human-readable, gruppiert nach Monat + KW)
- **Memory-Integration:** Symlinks fuer alle 5 Agenten (`signicat`, `privat`, `trustedcarrier`, `standard`, `system ward`) — `memory/calendar_events.txt` zeigt auf die zentrale summary-Datei, so dass alle Agenten immer die aktuelle Version sehen
- **Automatisches Update:** launchd Job `com.assistantdev.calendar-export` unter `~/Library/LaunchAgents/` — laeuft taeglich um 06:00 Uhr, Log nach `logs/calendar_export.log`, aktiv geladen
- Search-Index: kein separates Rebuild-Skript vorhanden, Index wird in-process (`src/search_engine.py`) aufgebaut und findet die neuen Symlinks automatisch beim naechsten Build

### Fix: E-Mail Suche — Modal-Diskrepanz, Datumssortierung, Reply-Modal Content
- **Problem 1 (Modal fand nichts):** Root Cause: Modal-Suche filterte nur `.eml` Dateien.
  Signicat hat aber 3178 `.txt` Emails (deutsches Format: Von/An/Betreff/Datum).
  Deshalb fand das Modal "sebastian" nicht, obwohl /find-email 8 Treffer lieferte.
- **Fix:** `_build_email_cache` unterstuetzt jetzt `.eml` UND `.txt`
  - Neuer `_parse_txt_email()` Helper fuer deutsches Header-Format
  - Neuer `_parse_filename_timestamp()` Fallback: extrahiert Datum aus Dateiname (`YYYY-MM-DD_HH-MM-SS_...`)
  - Sortierung: Datum absteigend (neueste zuerst) — `Datum:` Header, dann Dateiname, dann mtime
  - Deduplikation: nicht nur ueber Message-ID, auch ueber (from_email, subject, date_ts) — entfernt iCloud-Duplikate (`_2`, `_2 2`, etc.)
  - From-Email Cleaning: entfernt `<mailto:...>` Wrapper aus .txt Emails
- **Problem 2 (keine Datumssortierung):** `/search_preview` sortierte Emails nach from_person/score
  - **Fix:** Fuer `search_type == 'email'` explizit nach `date` DESC sortieren
- **Problem 3 (Reply-Modal laedt Inhalt nicht):** `/api/email-content` parste nur `.eml`
  - **Fix:** Auch `.txt` Dateien lesen, deutsches Format parsen, Message-ID aus Header extrahieren
- **Performance:** Erster Cache-Aufbau fuer signicat (4788 Dateien): ~80s einmalig, danach jede Suche <20ms
- Alle 453 Tests bestanden
- Dateien: `src/web_server.py`, `scripts/patch_email_search_unify.py`, `scripts/patch_email_search_refine.py`

## 2026-04-13

### Performance Fix: E-Mail Suche + Apple Mail Draft-Erstellung
- **Fix 1: E-Mail Suche** — In-Memory Header Cache statt Filesystem-Scan
  - Root Cause: Bei jeder Suchanfrage wurden 21.000+ .eml Dateien vom Disk gelesen und komplett MIME-geparst (~11s pro Suche)
  - Fix: In-Memory Cache (`_email_header_cache`): liest nur die ersten 40 Zeilen (Header) jeder .eml via `os.scandir()`, cached fuer 5 Minuten
  - Ergebnis: **11.465ms → 17ms** (677x schneller). Erster Aufruf 4.4s (einmaliger Cache-Aufbau), danach <25ms
  - Namens-Normalisierung: Kommas im Von-Feld werden fuer die Suche zu Leerzeichen normalisiert ("Nachname, Vorname" → Token-Match)
  - Frontend-Debounce von 300ms auf 250ms reduziert
- **Fix 2: Apple Mail Draft** — Asynchrone AppleScript-Ausfuehrung
  - Root Cause: `subprocess.run()` blockierte synchron (timeout=10s/30s), besonders langsam bei `send_email_reply` (iteriert alle Mailboxen)
  - Fix: `subprocess.Popen()` (fire-and-forget) — HTTP-Response wird sofort zurueckgegeben
  - Betrifft: `send_email_draft()` (2 Bloecke) + `send_email_reply()` — alle 3 auf async umgestellt
- Alle 453 Tests bestanden
- Dateien: `src/web_server.py`, `scripts/patch_email_perf_v2.py`

### Fix: Portrait-Video (9:16) korrekt im Chat anzeigen
- `generate_video()` gibt jetzt den tatsaechlich verwendeten `aspect` Wert als dritten Return-Wert zurueck
- Portrait-Erkennung: API aspect == "9:16" ODER Prompt-Keywords (portrait, hochformat, vertical, tiktok, reels, shorts, 9:16)
- `addVideoPreview()` im Frontend: Portrait-Videos bekommen max-width 280px, aspect-ratio 9/16, zentriert
- Landscape-Videos bleiben unveraendert (max-width 600px)
- `created_videos` Dict bekommt `is_portrait` Flag das an Frontend durchgereicht wird
- Alle 453 Tests bestanden
- Dateien: `src/web_server.py`, `scripts/patch_portrait_video.py`

### Fix: E-Mail Reply Feature — Such-Modal mit Filtern + Routing-Fix
- **Bug 1 Fix:** E-Mail-Such-Modal mit kategorierten Filtern (Von, Betreff, An/CC, Freitext)
  - Neues Modal (`#email-search-modal`) mit 4 Filterfeldern und Debounce-Suche (300ms)
  - `/create-email-reply` und `/reply` oeffnen jetzt das Such-Modal statt Inline-Chat-Suche
  - Backend `/api/email-search` erweitert: unterstuetzt jetzt `from`, `subject`, `to`, `body` Parameter einzeln
  - Klick auf Suchergebnis laedt E-Mail als Card direkt in den Chat (mit Antworten-Button)
- **Bug 2 Fix:** Sub-Agent-Routing wird bei E-Mail-Reply-Kontext uebersprungen
  - Nachrichten mit `[E-MAIL KONTEXT:...]` Prefix umgehen `detect_delegation()` komplett
  - Verhindert falsches Routing (z.B. signicat_meddpicc statt signicat_outbound) waehrend Reply
- Alle 453 Tests bestanden
- Dateien: `src/web_server.py`, `scripts/patch_email_reply_fixes.py`, `scripts/patch_email_search_filter_fix.py`

### UX-Ueberarbeitung: Chat-nativer E-Mail Reply Flow
- **ERSETZT:** Altes E-Mail Reply Modal komplett entfernt (Formular-Popup mit Von/Betreff/CC/Body Feldern)
- **NEU:** Chat-nativer Flow:
  1. `/reply [suchbegriff]` zeigt E-Mail-Suchergebnisse als klickbare Cards im Chat
  2. Klick auf Card laedt vollstaendige E-Mail als formatierte Email-Card (Von, An, CC, Betreff, Datum, Body mit max-height 400px scrollbar)
  3. "Antworten"-Button setzt E-Mail-Kontext (Message-ID, From, Subject, CC)
  4. Naechste User-Nachricht wird automatisch mit E-Mail-Kontext an den Agent gesendet (einmalig)
- **NEU:** Backend-Route `GET /api/email-content` — laedt vollstaendigen E-Mail-Body aus .eml Dateien (text/plain mit HTML-Fallback, max 5000 Zeichen)
- **NEU:** `/reply` Slash-Command als Kurzbefehl fuer E-Mail-Suche im Chat
- `/create-email-reply` leitet jetzt auf `/reply` weiter statt Modal zu oeffnen
- Alle 453 Tests bestanden
- Dateien: `src/web_server.py`, `scripts/patch_email_chat_flow_v3.py`

### Live-Suche im Email Reply Modal (ersetzt durch Chat-Flow oben)
- **NEU:** Email Reply Modal mit Live-Suche statt einfachem Template-Text
  - `/create-email-reply` oeffnet jetzt ein Modal mit Suchfeld, To, Subject, CC, Body
  - Live-Suche ab 2 Zeichen (300ms Debounce) durchsucht .eml Dateien in Agent-Memory und email_inbox
  - Max. 8 Treffer, neueste zuerst, mit Absender, Betreff, Datum
  - Klick auf Treffer befuellt alle Felder automatisch (To, Subject, CC, Message-ID)
  - CC filtert automatisch eigene Adressen heraus (moritz.cremer@me.com, londoncityfox@gmail.com, moritz.cremer@signicat.com)
  - Pfeiltasten-Navigation und Escape im Dropdown
  - Submit baut Prompt und sendet an Agent
- **NEU:** Backend-Route `GET /api/email-search?agent=X&q=Y` — parst .eml Header (From, Subject, Date, Message-ID, To, Cc)
- Alle 453 Tests bestanden
- Dateien: `src/web_server.py`, `scripts/patch_email_reply_search.py`

### LLM-Modell Audit, API-Tests & models.json Update
- Alle 5 Provider getestet (Anthropic, OpenAI, Mistral, Perplexity, Gemini)
- **Anthropic**: claude-sonnet-4-6, claude-opus-4-6, claude-haiku-4-5 — alle OK (HTTP 200)
- **OpenAI**: gpt-4o, gpt-4o-mini, o1 — alle HTTP 429 (Quota exceeded, Billing pruefen!). o3 und o4-mini als neue Modelle hinzugefuegt
- **Mistral**: mistral-large ✅, mistral-small ✅, mistral-nemo ❌ (invalid model ID entfernt). Neu hinzugefuegt: mistral-medium, magistral-medium (Reasoning), magistral-small (Reasoning), codestral (Code), open-mistral-nemo
- **Perplexity**: sonar ✅, sonar-pro ✅, sonar-reasoning ❌ (deprecated Dez 2025, entfernt), sonar-reasoning-pro ✅, sonar-deep-research ✅
- **Gemini**: gemini-2.5-flash ✅, gemini-2.5-pro ⚠️ (503 high demand), gemini-3-flash-preview ✅, gemini-3-pro-preview ✅, gemini-3.1-pro-preview ✅, gemini-2.0-flash ❌ (deprecated, entfernt)
- Dropdown wird dynamisch aus models.json populiert — alle Aenderungen sofort sichtbar
- Kein Provider-Fallback-Mechanismus vorhanden (nur innerhalb Video/Bild-Generierung)
- Dateien: `config/models.json`

### /create-email-reply Slash-Command im Frontend
- `/create-email-reply` Shortcut im Slash-Command-Menü ergänzt (Gruppe: Kommunikation, direkt nach /create-email)
- Template: "Antworte auf die E-Mail von [Absender] zum Thema [Betreff]: "
- Dateien: `src/web_server.py`
- Alle 453 Tests bestanden

### Copy-Button fuer Code-Bloecke im Chat-Frontend
- `addCodeCopyButtons()` erweitert: behandelt jetzt auch marked.js `<pre><code>` Bloecke (vorher nur custom `code-block-wrapper`)
- Marked.js-Bloecke werden automatisch in `.code-block-wrapper` gewrappt mit Sprach-Label und Copy-Button
- Copy-Buttons erscheinen jetzt auch in User-Nachrichten (nicht nur Assistant)
- Duplikat-Schutz: Buttons werden nicht doppelt eingefuegt
- Bestehende CSS-Klassen (`code-copy-btn`, hover-Effekte, `copied`-Zustand) werden wiederverwendet
- Alle 453 Tests bestanden
- Dateien: `src/web_server.py`, `scripts/patch_code_copy_buttons.py`

### Auto-Deploy bei develop-Merge + Deployment-Audit
- Git Post-Merge Hook erstellt (`.git/hooks/post-merge`): deployed automatisch wenn auf develop gemerged wird
- `finish_feature.sh` deployed jetzt automatisch nach Feature-Merge (mit Fehlertoleranz)
- `deploy.sh` robuster gemacht: logs-Verzeichnis wird angelegt, Timestamps in `logs/deploy.log`, sleep auf 4s erhoeht
- Sofort-Deploy aller ausstehenden Features inkl. CREATE_EMAIL_REPLY verifiziert (Diff war 0 Zeilen — Quellcode und deployed waren bereits identisch)
- Dateien: `scripts/deploy.sh`, `scripts/finish_feature.sh`, `.git/hooks/post-merge`

### CREATE_EMAIL from-Feld Support
- **NEU:** Optionales "from"-Feld in CREATE_EMAIL und CREATE_EMAIL_REPLY implementiert
  - `send_email_draft()`: setzt `sender` im AppleScript wenn "from" angegeben
  - `send_email_reply()`: setzt `sender` im Reply-AppleScript und beiden Fallback-Pfaden
  - System-Prompt: Beispiel-JSON um "from" erweitert, Dokumentation ergaenzt
  - Beide duplizierten Bloecke (Zeile ~278 und ~994) konsistent gepatcht
- **signicat.txt:** Absenderadresse-Block eingefuegt (from: moritz.cremer@signicat.com fuer alle Drafts)
- Dateien: `src/web_server.py`, `config/agents/signicat.txt`
- Alle 453 Tests bestanden

### CREATE_EMAIL_REPLY Feature
- Neuer Trigger `[CREATE_EMAIL_REPLY:json]` fuer E-Mail-Antworten mit korrektem Threading
- JSON-Felder: message_id, to, cc, subject, body, quote_original
- `send_email_reply()` Funktion: AppleScript sucht E-Mail per Message-ID in Apple Mail, oeffnet Reply; Fallback auf neue E-Mail wenn nicht gefunden
- CREATE_EMAIL Parser erkennt und ueberspringt CREATE_EMAIL_REPLY (kein Doppel-Match)
- `/send_email_reply` API-Route fuer direkten Aufruf
- System-Prompt (DATEI-ERSTELLUNG Block) um CREATE_EMAIL_REPLY Anweisung ergaenzt
- Agent-Prompts (privat, signicat, signicat_outbound, trustedcarrier) um CREATE_EMAIL_REPLY Anweisung ergaenzt
- JS-Frontend zeigt "Reply" statt "Draft" bei Reply-E-Mails
- KEINE WIEDERHOLUNG Block um CREATE_EMAIL_REPLY erweitert
- 10 neue Tests in run_tests.py (Stand: 453 Tests)
- Dateien: src/web_server.py, tests/run_tests.py, config/agents/*.txt

### GitHub Integration + Terminal-Workflow eingerichtet
- Git Repository initialisiert in ~/AssistantDev/
- GitHub Repo erstellt: github.com/moritzdagee/AssistantDev (private)
- Branching-Strategie: main (stable/deployed) / develop (integration) / feature/xxx
- Initial Commit + develop Branch gepusht
- 4 Workflow-Skripte erstellt in ~/AssistantDev/scripts/:
  - new_feature.sh [name]: Branch von develop erstellen
  - finish_feature.sh [name]: Feature in develop mergen, Branch loeschen
  - deploy.sh: Deploy + automatischer Git-Commit bei Erfolg
  - claude_task.sh [task] [branch]: Branch + Claude Code in einem Befehl
- .gitignore schuetzt: models.json (API-Keys), config/agents/, memory/*.json, *.backup_*, claude_outputs/
- CLAUDE.md um Abschnitt Git Workflow erweitert
- Claude CLI eingerichtet: ~/.local/bin/claude (v2.1.90), eingeloggt als moritz.cremer@me.com
- Terminal-Workflow: Alle Claude Code Prompts ab sofort als direkt ausfuehrbare Terminal-Commands
- Homebrew installiert, gh CLI installiert und eingeloggt als moritzdagee

---

## 2026-04-13 — GitHub Repository Setup

2026-04-13 | GitHub Repository moritzdagee/AssistantDev private eingerichtet. Branching-Strategie main/develop/feature. Workflow-Skripte new_feature.sh finish_feature.sh deploy.sh claude_task.sh erstellt. | .gitignore, scripts/, CLAUDE.md | Versionskontrolle und strukturierter Workflow

---

## SERVICE-VERZEICHNIS — Alle verwalteten Dienste

> **WICHTIG:** Wenn ein neuer Service/Daemon erstellt wird, MUSS er hier eingetragen UND in `src/app.py` (Menu Bar App) als `Service(...)` Eintrag hinzugefuegt werden, damit er im macOS Menu Bar sichtbar, startbar und stoppbar ist. Ebenso muss das Script ins App Bundle kopiert werden: `cp src/[script].py /Applications/Assistant.app/Contents/Resources/`

| # | Service | Script | Port | Typ | Auto-Restart | Beschreibung |
|---|---------|--------|------|-----|-------------|--------------|
| 1 | **Web Server** | `web_server.py` | 8080 | Background | Ja | Flask UI + Chat API + LLM-Integration |
| 2 | **Email Watcher** | `email_watcher.py` | — | Background | Ja | Importiert E-Mails ins Agent-Memory, extrahiert Kontakte (contacts.json), Signatur-Parsing (Titel, Telefon) |
| 3 | **Web Clipper** | `web_clipper_server.py` | 8081 | Background | Ja | Chrome Extension Backend fuer Web Clips |
| 4 | **kChat Watcher** | `kchat_watcher.py` | — | Background | Ja | Importiert kChat-Nachrichten (Mattermost v4) ins Agent-Memory |
| 5 | **Message Dashboard** | `message_dashboard.py` | — | GUI (PyQt6) | Nein | Native macOS Inbox-App, manueller Start |

**Libraries (kein eigener Prozess):**
- `search_engine.py` — Such-Index + Hybrid-Suche, wird von web_server.py importiert
- `app.py` — die Menu Bar App selbst (rumps), verwaltet alle obigen Services

**Einmal-Skripte (kein Daemon, unter scripts/):**
- `sent_mail_exporter.py` — einmaliger Export gesendeter Mails aus Apple Mail
- `rename_existing_emails.py` — einmaliges Umbenennen alter Email-Dateien
- `contact_mismatch_analyzer.py` — Kontakt-Mismatch-Analyse (macOS Contacts + Datalake)
- `apply_contact_fixes.py` — Wendet Korrekturen auf Apple Contacts an + Datalake-Merge

**Kontakt-Extraktion:** Ist KEIN separater Service — laeuft als Feature innerhalb von `email_watcher.py` (`update_contacts_json()`, Zeile ~281). Jede E-Mail aktualisiert automatisch `[agent]/memory/contacts.json` mit Name, Firma, Titel, Telefon.

---

## EXTERNE API-DOKUMENTATIONEN — Referenz-Verzeichnis

> **WICHTIG:** Bei Fragen zu einer API-Integration **immer zuerst** die hier gelistete offizielle Dokumentation konsultieren, bevor eigene Vermutungen getroffen werden. Neue API-Integrationen muessen ihre Dokumentation ebenfalls hier eintragen.

### Anthropic / Claude API
- **Verwendung im Projekt:** `call_anthropic()` in web_server.py, Python SDK `anthropic`, Sub-Agent-Delegation
- **Offizielle Docs:** https://docs.anthropic.com/en/docs
- **API Reference:** https://docs.anthropic.com/en/api
- **Python SDK:** https://github.com/anthropics/anthropic-sdk-python
- **Models:** https://docs.anthropic.com/en/docs/about-claude/models
- **Genutzte Modelle:** `claude-sonnet-4-6`, `claude-opus-4-6`, `claude-haiku-4-5-20251001`
- **Endpunkt:** via Python SDK (`client.messages.create`)

### OpenAI API
- **Verwendung im Projekt:** `call_openai()` in web_server.py, Bildgenerierung via `gpt-image-1`
- **Offizielle Docs:** https://platform.openai.com/docs
- **API Reference:** https://platform.openai.com/docs/api-reference
- **Image Generation:** https://platform.openai.com/docs/guides/images
- **Genutzte Modelle:** `gpt-4o`, `gpt-4o-mini`, `o1`, `gpt-image-1`
- **Endpunkt Chat:** via Python SDK (`openai.ChatCompletion.create`)
- **Endpunkt Images:** `POST https://api.openai.com/v1/images/generations`
- **Billing:** https://platform.openai.com/account/billing

### Google Gemini API (Generative Language)
- **Verwendung im Projekt:** `call_gemini()` in web_server.py, Bildgenerierung (Imagen 4), Videogenerierung (Veo)
- **Offizielle Docs:** https://ai.google.dev/gemini-api/docs
- **API Reference:** https://ai.google.dev/api
- **Pricing:** https://ai.google.dev/pricing
- **Imagen API (Bildgenerierung):** https://ai.google.dev/gemini-api/docs/imagen
  - Endpunkt: `POST https://generativelanguage.googleapis.com/v1beta/models/{model}:predict`
  - Genutzte Modelle: `imagen-4.0-generate-001`, `imagen-4.0-fast-generate-001`
  - Fallback-Modelle: `gemini-2.5-flash-image`, `gemini-3.1-flash-image-preview`, `gemini-3-pro-image-preview`
- **Veo API (Videogenerierung):** https://ai.google.dev/gemini-api/docs/video
  - Endpunkt: `POST https://generativelanguage.googleapis.com/v1beta/models/{model}:predictLongRunning`
  - Polling: `GET https://generativelanguage.googleapis.com/v1beta/{operation_name}`
  - Genutzte Modelle: `veo-3.1-generate-preview`, Fallback: `veo-2.0-generate-001`
  - Response-Format: `generateVideoResponse.generatedSamples[].video.uri`
  - Content-Filter-Felder: `raiMediaFilteredCount`, `raiMediaFilteredReasons`
- **Gemini Chat:** `POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent`
- **Genutzte Chat-Modelle:** `gemini-2.5-flash`, `gemini-2.5-pro`, `gemini-3-flash-preview`, `gemini-3-pro-preview`, `gemini-3.1-pro-preview`, `gemini-2.0-flash`

### Perplexity API
- **Verwendung im Projekt:** `call_perplexity()` in web_server.py (OpenAI-kompatibles Format)
- **Offizielle Docs:** https://docs.perplexity.ai
- **API Reference:** https://docs.perplexity.ai/api-reference
- **Genutzte Modelle:** `sonar`, `sonar-pro`, `sonar-reasoning`, `sonar-reasoning-pro`, `sonar-deep-research`
- **Endpunkt:** `POST https://api.perplexity.ai/chat/completions`
- **Besonderheiten:** Modellspezifische Timeouts (300s/180s/120s), Message-Alternierung noetig, Citations als Markdown-Links

### Mistral API
- **Verwendung im Projekt:** `call_mistral()` in web_server.py
- **Offizielle Docs:** https://docs.mistral.ai
- **API Reference:** https://docs.mistral.ai/api/
- **Genutzte Modelle:** `mistral-large-latest`, `mistral-small-latest`, `mistral-nemo`
- **Endpunkt:** `POST https://api.mistral.ai/v1/chat/completions`

### Infomaniak kChat API (Mattermost v4 Fork)
- **Verwendung im Projekt:** `kchat_watcher.py` (Inbound Message Watcher)
- **Server:** `https://kyb-group-bv.kchat.infomaniak.com` (Server Version 1.136.0)
- **Mattermost API v4 Docs:** https://api.mattermost.com/
- **Mattermost API Reference:** https://developers.mattermost.com/api-documentation/
- **Infomaniak kChat Source (Webapp):** https://github.com/Infomaniak/kchat-webapp
- **Infomaniak kChat MCP-Server (Referenz-Implementierung):** https://github.com/Infomaniak/mcp-server-kchat
- **Infomaniak API Token Management:** https://www.infomaniak.com/en/support/faq/2582/generate-and-manage-infomaniak-api-tokens
- **Infomaniak Developer Portal:** https://developer.infomaniak.com/docs/api
- **Auth-Header:** `Authorization: Bearer <token>`
- **Genutzte Endpunkte:**
  - `GET /api/v4/users/me` (eigene User-ID ermitteln)
  - `GET /api/v4/users/{id}/channels` (alle Channels des Users)
  - `GET /api/v4/channels/{id}/posts?since={timestamp_ms}` (neue Nachrichten)
  - `GET /api/v4/users/{id}` (User-Details)
  - `GET /api/v4/channels/{id}` (Channel-Details)
  - `GET /api/v4/teams/name/{team_name}` (Team-Lookup)

### PyQt6 (Message Dashboard)
- **Verwendung im Projekt:** `message_dashboard.py` (native macOS Inbox-App)
- **Offizielle Docs:** https://www.riverbankcomputing.com/static/Docs/PyQt6/
- **Qt6 Docs (Referenz):** https://doc.qt.io/qt-6/

### Slack Web API
- **Verwendung im Projekt:** `slack_send_message()`, `slack_list_channels()`, `slack_channel_history()`, etc. in web_server.py
- **Offizielle Docs:** https://api.slack.com/docs
- **API Reference (Methods):** https://docs.slack.dev/reference/methods/
- **chat.postMessage:** https://docs.slack.dev/reference/methods/chat.postMessage/
- **Bot Token Setup:** https://api.slack.com/authentication/token-types#bot
- **Genutzte Scopes:** `chat:write`, `chat:write.public`, `channels:read`, `channels:history`, `users:read`, `im:write`
- **Endpunkte:** `POST/GET https://slack.com/api/{method}` mit `Authorization: Bearer xoxb-...`

### Canva Connect API
- **Verwendung im Projekt:** `canva_list_designs()`, `canva_create_design()`, `canva_export_design()`, etc. in web_server.py
- **Offizielle Docs:** https://www.canva.dev/docs/connect/
- **API Reference:** https://www.canva.dev/docs/connect/api-reference/
- **Authentication:** https://www.canva.dev/docs/connect/authentication/
- **Create Design:** https://www.canva.dev/docs/connect/api-reference/designs/create-design/
- **MCP Server:** https://www.canva.dev/docs/apps/mcp-server/
- **Endpunkt:** `https://api.canva.com/rest/v1/` mit `Authorization: Bearer <access_token>`

### Sonstige
- **Apple Mail Scripting (AppleScript):** email_watcher.py nutzt `osascript` zum Auslesen eigener E-Mail-Adressen aus Apple Mail
  - Apple Mail AppleScript Reference: https://developer.apple.com/library/archive/documentation/AppleScript/Conceptual/AppleScriptLangGuide/
- **macOS Contacts/AddressBook SQLite:** fix_contacts_pollution.py greift direkt auf `~/Library/Application Support/AddressBook/Sources/*/AddressBook-v22.abcddb` zu
  - Keine offizielle API-Doku — reverse-engineered SQLite-Schema
- **macOS LaunchAgents:** email_watcher, kchat_watcher, optional dashboard
  - Referenz: https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html

---

## [2026-04-13] Canva OAuth2 Setup + Token-Refresh — REST API vollstaendig aktiv

**OAuth2-Flow erfolgreich durchgefuehrt:**
- Setup-Skript `scripts/canva_oauth_setup.py` mit PKCE (S256), lokalem Callback-Server (`127.0.0.1:8765`)
- Redirect-URI in Canva Developer Console registriert: `http://127.0.0.1:8765/callback`
- 13 Scopes autorisiert: `design:content:read/write`, `design:meta:read`, `design:permission:read`, `asset:read/write`, `folder:read/write`, `brandtemplate:meta:read/content:read`, `profile:read`, `comment:read/write`
- Access Token (4h) + Refresh Token automatisch in `models.json` gespeichert

**Token-Refresh (`CANVA_TOKEN_REFRESH`):**
- `_canva_refresh_token()` erneuert automatisch via Refresh Token wenn Access Token ablaeuft
- `_canva_api()` erkennt HTTP 401 → Refresh → Retry (transparent fuer alle Canva-Funktionen)
- Tokens werden bei Refresh automatisch in `models.json` aktualisiert

**Live-Test erfolgreich:** `POST /api/canva {action: list}` → 25 Designs geladen (Tangerina Logos, Signicat Presentations, Vega Technology, etc.)

---

## [2026-04-13] Bugfix: Sub-Agent Konversationen nicht sichtbar (SUBAGENT_HISTORY_V1)

**Bug:** Sub-Agents (z.B. `signicat_outbound`) zeigten 0 vergangene Konversationen in der UI, obwohl Dateien existierten.

**Ursache (2 Probleme):**
1. **Falscher Pfad:** `get_history()` (Zeile 5525) nutzte `os.path.join(BASE, agent)` → bei `signicat_outbound` wurde `datalake/signicat_outbound/` gesucht, der **nicht existiert**. Konversationen werden aber korrekt via `get_agent_speicher()` im Parent-Ordner `datalake/signicat/` gespeichert.
2. **Kein Filtering:** Selbst mit korrektem Pfad wuerden Parent- und Sub-Agent-Konversationen vermischt dargestellt.

**Fix:**
- `get_history()`: Nutzt jetzt `get_agent_speicher(agent)` statt direktem `os.path.join(BASE, agent)` → Sub-Agents finden den Parent-Ordner
- **Sub-Agent-Filtering:** Konversationsdateien haben ein Suffix im Namen (`konversation_2026-04-13_07-00_outbound.txt`). Sub-Agents sehen nur Dateien mit ihrem Suffix, Parent-Agents sehen nur Dateien OHNE bekannte Sub-Agent-Suffixe.
- `load_conversation()`: Gleicher Pfad-Fix angewendet (nutzt jetzt auch `get_agent_speicher()`)

**Ergebnis:**
- `signicat_outbound`: 0 → **5 Sessions** sichtbar
- `signicat` (Parent): **141 Sessions**, davon **0 Sub-Agent-Konversationen** (sauber gefiltert)
- Alle anderen Agents: unveraendert

**Patch:** `scripts/patch_subagent_history2.py` | Tests: 360/360 gruen

---

## [2026-04-13] Slack API Outbound + Canva REST API Integration

### Slack API (`SLACK_API_V1`)

**Problem:** Bisherige Slack-Integration war ein Clipboard-Paste-Hack (pbcopy → open Slack → Cmd+V AppleScript). Unzuverlaessig, kein Channel-Routing, keine Lese-Faehigkeiten.

**Loesung: Echte Slack Web API Integration**
- `_slack_api(method, params, json_body)` — generischer Slack API Client mit Bot-Token Auth
- `slack_send_message(channel, text, thread_ts)` — `chat.postMessage`
- `slack_list_channels()` — `conversations.list` (public + private)
- `slack_list_users()` — `users.list`
- `slack_channel_history(channel_id, limit)` — `conversations.history`
- `slack_find_channel_id(name)` — Channel-Name → ID Aufloesung
- `slack_find_user_id(name)` — Display-Name → User-ID Aufloesung
- `send_slack_draft()` **upgraded**: versucht zuerst API, fällt auf Desktop-Clipboard-Hack zurueck wenn kein Token
- DM-Routing: bei Personennamen → `conversations.open` → DM-Channel → `chat.postMessage`
- **Route:** `POST /api/slack` mit `action`: send, channels, history, users

**Setup (Moritz TODO):**
1. https://api.slack.com/apps → Create New App → From Scratch
2. Bot Token Scopes: `chat:write`, `chat:write.public`, `channels:read`, `channels:history`, `users:read`, `im:write`
3. Install to Workspace → Bot User OAuth Token (`xoxb-...`) in `models.json["slack"]["bot_token"]` eintragen

### Canva REST API (`CANVA_API_V1`)

**Canva Connect API Client fuer Design-Operationen direkt aus AssistantDev:**
- `_canva_api(method, path, json_body, params)` — generischer REST Client mit Bearer Auth
- `canva_list_designs(query, count)` — Designs suchen
- `canva_get_design(design_id)` — Design-Details
- `canva_create_design(title, design_type, width, height)` — Neues Design erstellen
- `canva_export_design(design_id, format_type)` — Export als PDF/PNG/JPG
- `canva_list_folders(count)` — Ordner auflisten
- **Route:** `POST /api/canva` mit `action`: list/search, get, create, export, folders

**Setup (Moritz TODO):**
1. https://www.canva.com/developers → Create an App
2. Generate Access Token (oder OAuth Flow)
3. Token in `models.json["canva"]["access_token"]` eintragen

### models.json erweitert
- Neuer `slack` Block: `bot_token`, `workspace`, `default_channel`, `_setup_instructions`
- Neuer `canva` Block: `access_token`, `api_base`, `_setup_instructions`

### Agent-Prompts aktualisiert
3 Agenten (signicat, privat, trustedcarrier) erhielten Slack- und Canva-Faehigkeits-Hinweise.

### Patch-Skript
`scripts/patch_slack_canva_integration.py` — 3 Patches (API-Funktionen, Routen, send_slack_draft Upgrade)

### Tests
- Syntax-Check: OK
- `/api/slack {action: channels}` → `{ok: false}` (erwartetes Verhalten ohne Token)
- `/api/canva {action: list}` → `{ok: false, error: "Kein access_token"}` (erwartetes Verhalten)
- Regression: `/`, `/agents`, `/models` → HTTP 200
- Test Suite: **360/360 gruen**

### API-Dokumentation (→ Referenz-Verzeichnis oben im Changelog)
- **Slack Web API:** https://docs.slack.dev/reference/methods/chat.postMessage/
- **Canva Connect API:** https://www.canva.dev/docs/connect/

---

## [2026-04-13] Kalender-Integration (Fantastical/Apple Calendar)

**Ziel:** Agenten koennen Kalender-Daten abfragen. Fantastical teilt den macOS CalendarStore, deshalb funktioniert Apple Calendar AppleScript direkt mit Fantastical-Daten.

### Neue Funktion: `get_calendar_events()`
- AppleScript-basiert via `osascript` (zuverlaessiger als EventKit/pyobjc, da keine separate macOS-Berechtigung noetig)
- Liest: Titel, Start/End (ISO 8601), Ort, Kalender-Name, Notizen, Ganztaegig-Flag
- Standard-Kalender: Arbeit, Privat, Familie (konfigurierbar via `_CALENDAR_TARGETS`)
- **Caching:** 120 s Gueltigkeitsdauer, Key aus Parametern → zweiter Aufruf innerhalb von 2 min ist sofort
- **Timeout:** 45 s (CalDAV-Kalender brauchen beim Erstaufruf laenger)
- `_parse_applescript_date()`: Parst macOS-Datumsformat ("Monday, 14 April 2026 at 07:30:00") in Python datetime, DE + EN Monatsnamen
- `_has_calendar_intent()`: Keyword-Erkennung (22 DE + 13 EN Keywords: kalender, termin, meeting, heute, morgen, schedule, etc.)
- `format_calendar_context()`: Formatiert Events als Kontext-Block fuer System-Prompt-Injection

### Neue Route: `POST/GET /api/calendar`
- Parameter: `days_back` (int, default 0), `days_ahead` (int, default 7), `calendar_filter` (string), `search` (string)
- Response: `{events: [...], count, range: {from, to}, calendars_found: [...]}`
- Freitext-Suche in Titel/Notes/Location via `search` Parameter
- **Live-Test erfolgreich:** 4 Events gelesen (Growth Weekly, Publicis Sapient, Santander)

### Auto-Inject bei Kalender-Intent im Chat
- In `process_single_message()`: vor dem LLM-Call prüft `_has_calendar_intent(msg)` ob die User-Nachricht nach Kalender fragt
- Bei Treffer: `get_calendar_events(days_back=1, days_ahead=7)` → Ergebnis als `--- KALENDER ---` Block an den Chat-Kontext angehängt
- Logging: `[CALENDAR] N Events injiziert fuer Intent in: ...`
- Kein Overhead wenn kein Kalender-Intent erkannt wird

### Agent-Prompts aktualisiert
6 Agenten erhielten Kalender-Faehigkeits-Hinweis im System-Prompt:
- privat, signicat, signicat_lamp, signicat_meddpicc, signicat_outbound, trustedcarrier
- Text: "Du hast Zugriff auf den Kalender von Moritz (Fantastical/Apple Calendar)..."
- NICHT aktualisiert: system ward, signicat_powerpoint, trustedcarrier_instagramm (kein Kalender-Bezug)

### Patch-Skripte
- `scripts/patch_calendar_integration.py` — Hauptpatch (Funktion + Route)
- `scripts/patch_calendar_inject.py` — Auto-Inject in process_single_message
- `scripts/patch_calendar_perf.py` — Performance (weniger Kalender, Timeout 45s, 120s Cache)
- `missing value` Fix direkt via Edit (AppleScript gibt 'missing value' statt leeren String)

### Tests
- `python3 -m py_compile web_server.py` → OK
- `curl /api/calendar` → 4 Events, HTTP 200
- Regressions-Check: `/`, `/agents`, `/models` → HTTP 200
- Test Suite: **360/360 gruen**
- AppleScript Kalender-Berechtigung: **erteilt** (Kalender-Namen und Events lesbar)

### Deployment
- Backup: `src/web_server.py.backup_20260413_070246`
- Agent-Prompt Backups: `*.txt.backup_cal` fuer alle 6 aktualisierten Agenten
- Deployed nach `/Applications/Assistant.app/Contents/Resources/`

---

## [2026-04-13] Menu Bar App: Alle Services + Kontakt-Korrekturen angewendet

### Menu Bar App (`app.py`) — Alle 5 Services sichtbar

- Erweitert um **kChat Watcher** und **Message Dashboard** (vorher nur 3: Web Server, Email Watcher, Web Clipper)
- Pro Service jetzt: **Status-Anzeige** (🟢 running / 🔴 stopped / ⏸️ pausiert) + **Start/Pause Toggle** + **Restart**
- `pause()` Funktion: stoppt Service UND verhindert Auto-Restart durch Watchdog (bis `resume()`)
- Dashboard als GUI-Service: manueller Start ueber "Open Dashboard" Button, kein Auto-Restart
- Neue globale Aktionen: "Open Dashboard", "Open Web Interface", "Open Logs", "Restart All Services"
- kChat Watcher von launchd-Verwaltung auf app.py-Verwaltung migriert (launchd plist unloaded)
- Alle Scripts ins App Bundle deployed (`/Applications/Assistant.app/Contents/Resources/`)
- Service-Verzeichnis als permanente Sektion oben im Changelog eingetragen mit Hinweis: **neue Services muessen immer in app.py + App Bundle nachgezogen werden**

### Kontakt-Korrekturen auf Apple Contacts angewendet

**Teil 1: Display-Name-Fixes (776 Kontakte korrigiert)**
- 781 Auto-Korrekturen aus Mismatch-Analyse geladen
- 776 in Apple Contacts aktualisiert (ZFIRSTNAME/ZLASTNAME in 2 AddressBook-DBs)
  - DB A42FFC88: 617 Aenderungen
  - DB EF91BA64: 159 Aenderungen
- Bei klarer Vor-/Nachname-Struktur: extrahierter Name (z.B. `aki.vergidis@` → "Aki" / "Vergidis")
- Bei generischen Adressen: E-Mail als Nachname, Domain als Organisation
- Deutsche Umlaute: `ae/oe/ue` ↔ `ä/ö/ü` Normalisierung (z.B. "Maennel" = "Männel")
- Initial-Matching: `a.roman@` matcht "Astrid Roman" (A = Anfangsbuchstabe)
- Hash/ID-Filter: Booking-IDs, VTEX-Hashes, UUIDs → email als Display-Name statt Muell-Tokens

**Teil 2: Datalake → Apple Contacts Merge (11 neue Kontakte)**
- 91 Kontakte aus `signicat/memory/contacts.json` geladen
- 80 schon im Adressbuch → uebersprungen
- 11 neu eingefuegt mit Name, E-Mail, Firma, Titel, Telefon (Thomas Ewetz, Patrick Spreckelmeyer, Daksh Srivastava etc.)

**Backup:** `~/AssistantDev/backups/addressbook_20260413_063918/` (alle 6 AddressBook-DBs)
**Script:** `scripts/apply_contact_fixes.py`

---

## [2026-04-12] API-Dokumentationen-Verzeichnis + Kontakt-Mismatch-Analyse

**API-Dokumentationen:** Alle externen APIs die im Projekt verwendet werden (Anthropic, OpenAI, Google Gemini/Imagen/Veo, Perplexity, Mistral, Infomaniak kChat/Mattermost, PyQt6, Apple Mail Scripting, macOS LaunchAgents) mit offiziellen Dokumentations-Links, genutzten Endpunkten, Modellnamen und Besonderheiten als permanente Referenz-Sektion oben im Changelog eingetragen. Hinweis ergaenzt: bei API-Fragen immer zuerst diese Doku konsultieren; neue API-Integrationen muessen ihre Doku hier eintragen.

**Kontakt-Mismatch-Analyse (`scripts/contact_mismatch_analyzer.py`):**
- Vergleicht Display-Namen in contacts.json mit aus E-Mail-Adressen extrahierten Namen
- Zusaetzlich: Display-Name im E-Mail-Header (Von: "Name \<email\>") vs. contacts.json
- Name-Extraktion: vorname.nachname, camelCase, Initialen, generische Adressen (info@, no-reply@...)
- Token-basierter Vergleich mit Normalisierung (diakritische Zeichen, Sonderzeichen, Groß/Kleinschreibung)
- Output: Excel-Datei mit 3 Sheets (KLARER_MISMATCH rot, UNKLAR orange, ZUSAMMENFASSUNG blau)
- Ergebnis (Vollanalyse aller Quellen): **4211 unique E-Mail-Adressen analysiert**
  - macOS AddressBook: 4200 Kontakte mit E-Mail (aus 5 Quell-Datenbanken)
  - Datalake contacts.json: 91 Kontakte (signicat)
  - E-Mail-Header Absender: 421 unique Adressen mit Display-Name
  - **Ergebnis: 2367 OK, 678 Mismatches, 1166 Unklar**
  - Top-Domains mit Mismatches: gmail.com (43), mavismail.spd.de (38), hotmail.com (11), check24.de (10), amazon.de (9)
- Excel: `~/Library/.../claude_outputs/contact_mismatch_2026-04-12.xlsx`
  - 4 Sheets: KLARER_MISMATCH (678 rot), UNKLAR (1166 orange), ALLE_OK (2367 gruen), ZUSAMMENFASSUNG (blau)

---

## [2026-04-10] Message Dashboard — Native macOS App (Globaler Posteingang)

**Ziel:** Standalone native macOS-App die alle Nachrichten aus dem Datalake aggregiert, priorisiert und uebersichtlich darstellt. Kein Browser, kein Chrome — echte Mac-App mit Dock-Icon.

### Neue Dateien
- `src/message_dashboard.py` (~880 Zeilen) — PyQt6-App mit Parser, Scoring, 3-Spalten-Layout
- `scripts/start_dashboard.sh` (executable) — Startskript
- `scripts/com.assistantdev.dashboard.plist.optional` — Optional Autostart (NICHT geladen, manuell zu aktivieren via cp + launchctl load)
- `~/.message_dashboard_state.json` — wird beim Start automatisch erstellt (read_messages, last_refresh)

### Installierte Dependency
- **PyQt6 6.10.2** (+ PyQt6-Qt6, PyQt6-sip) via `pip3 install PyQt6` — keine weiteren externen Deps

### Architektur (Zusammenfassung)

**Parser** (`parse_message_file`)
- Liest nur die ersten **8 KB** pro Datei (Performance!) — Volltext wird beim Detail-Klick on-demand nachgeladen
- Erkennt Email-Header (Von, An, Betreff, Datum, Richtung, Kontakt, Agent, Importiert) UND kChat-Header (Quelle, Kanal, Von, Datum)
- Datum-Parsing: RFC 2822 (E-Mail), ISO, `YYYY-MM-DD_HH-MM-SS_` aus Dateinamen, mtime-Fallback
- Filtert eigene Outbound-Nachrichten (`Richtung: OUT` oder Sender in `OWN_EMAILS`)
- Body-Preview auf 150 Zeichen, whitespace-normalisiert
- Robust gegen leere/kaputte Dateien (graceful skip)

**Scanner** (`scan_datalake`)
- Scant `signicat`, `trustedcarrier`, `privat`, `standard`, `system ward` Memory-Ordner
- Akzeptierte Patterns: `YYYY-MM-DD_HH-MM-SS_(IN|OUT)_*.txt`, `kchat_*.txt`, `whatsapp_*.txt`, `email_*.txt`
- Ignoriert `konversation_*.txt`
- **Performance-Optimierung:** `os.scandir()` + mtime-Sortierung, nur die **800 neuesten Dateien pro Agent** werden geparst (`MAX_FILES_PER_AGENT`). 25K+ historische Mails bleiben im Datalake fuer Suche/Memory verfuegbar, sind aber fuer den Inbox-Workflow irrelevant
- **Messung:** 25238 Dateien → 0.93 s (vorher: 10.93 s, weit ueber dem 3-s-Limit)

**Priority Scoring** (`calculate_priority`)
- Alter: heute +20, gestern +10, 2-3 Tage +5
- Source: Email +15, kChat +10, WhatsApp +12
- Keywords: urgent/dringend/asap +30, invoice/rechnung/zahlung +25, contract/vertrag +20, meeting/heute/today +15, offer/angebot +10, follow-up +10
- Firmennamen im Sender (signicat/trustedcarrier/elavon): +10
- Ungelesen: +15
- Score gecappt auf 0-100
- "Ueberfaellig"-Flag bei `age_days > 3` UND `is_read == False`

**State Management**
- Keine Aenderung an .txt Dateien — alle Status-Infos in `~/.message_dashboard_state.json`
- Format: `{"read_messages": [hash1, hash2, ...], "last_refresh": "ISO"}`
- IDs sind sha1-Hashes der absoluten Filepaths (16 Zeichen)
- Neue Dateien seit letztem Start = automatisch ungelesen

### UI / Layout

**Fenster:** 1200×800, dark theme (#1a1a1a / #e0e0e0), passend zu AssistantDev. Dock-Icon, native macOS Look (Fusion-Style + Stylesheet).

**3-Spalten Splitter:**
1. **Sidebar 250 px** — Filter (Alle / Ungelesen / Ueberfaellig / Top Priority) mit Live-Counts in den Button-Labels, Trennlinie, Kanal-Filter pro Agent + kChat/WhatsApp Source-Filter, Aktualisieren-Button, "Zuletzt: HH:MM:SS"
2. **Mittlere Liste 400 px** — Custom `MessageItemWidget` pro Eintrag mit Status-Punkt (gelb=ungelesen), Source-Icon (📧/💬/📱), Sender (fett wenn ungelesen), Subject + Body-Preview, Score-Badge ≥ 70 (gold), "ÜBERFÄLLIG"-Badge in dunkelrot, Alter rechts (z.B. "2h", "3d", "gestern"), Klick → Detail, Rechtsklick → Kontextmenue (Als gelesen/ungelesen, In Finder zeigen)
3. **Detail rechts 550 px** — Subject groß, Meta-Zeile (Von, An, Datum, Quelle, Kanal, Score), scrollbarer `QTextEdit` mit Volltext (on-demand bis 1 MB nachgeladen), 3 Action-Buttons: "✓ Als gelesen markieren" (toggle), "📂 In Finder", "💬 AssistantDev"

**Stats-Bar oben** (40 px) — Gesamt | Ungelesen (gold) | Ueberfaellig | Top Priority | Live-Uhr (Wochentag, Datum, HH:MM)

### Performance & Robustheit

- **Startup-Zeit:** 0.93 s fuer 2228 geparste Nachrichten (von ~26K Dateien im Datalake)
- **Worker-Thread:** Datalake-Scan laeuft in `QThread` → UI bleibt responsiv waehrend Refresh
- **Auto-Refresh:** alle 5 Minuten via QTimer; macOS-Notification via `osascript display notification` wenn neue Nachrichten gefunden
- **Manueller Refresh:** Cmd+R / Ctrl+R Shortcut + Button
- **Live-Uhr:** Update alle 30 Sekunden
- **Memory-Cap:** Max 500 sichtbare Items in der Liste (`LIST_VISIBLE_CAP`), restliche Nachrichten bleiben im Cache fuer Filter-Wechsel
- **Encoding:** UTF-8 ueberall, deutsche Umlaute korrekt
- **Fehlerbehandlung:** kaputte/leere Dateien graceful uebersprungen; Scan-Fehler im QMessageBox angezeigt; State-Save-Fehler nur stderr

### Tests

1. **PyQt6 Import:** OK (PyQt6 6.10.2 installiert)
2. **Syntax-Check:** `python3 -m py_compile src/message_dashboard.py` → OK
3. **Headless GUI-Start:** `QT_QPA_PLATFORM=offscreen` → 2228 Messages geladen, 500 List Items sichtbar, exit_code=0
4. **Parser-Test (7 Sub-Tests):**
   - Fresh state ist leer
   - State Mark-Read persistiert
   - 2 Mark-Read bleiben nach Reload erhalten
   - State-Cleanup OK
   - Leere Datei → None
   - Kaputte Datei → graceful Fallback
   - Urgent-Invoice-Scoring → 100 (max)
5. **Realer GUI-Start:** `python3 src/message_dashboard.py` 4 Sekunden — Fenster oeffnete sich, State-Datei wurde geschrieben (`~/.message_dashboard_state.json`)
6. **Performance:** 25238 .txt Dateien gefunden → 800 pro Agent gescannt → 2228 geparst → **0.93 s** (Ziel: <3 s, erfuellt)
7. **Plist:** `plutil -lint` OK
8. **Regression:** web_server.py + email_watcher.py + kchat_watcher.py Syntax OK, HTTP 200 auf `/`, Test Suite **360/360 gruen** (unveraendert)

### Erste Scan-Ergebnisse beim Test

```
Total: 2228  Unread: 2228  Top Priority (>=70): 102
Channels: signicat=756, trustedcarrier=511, privat=799, standard=162
Sources: email=2228 (kein kChat/WhatsApp im Datalake)
```

Top-5 nach Score (alle Score 100):
- ExFlow invoices for approval (signicat, 0.1 d alt)
- Sv: Appendix 9 Sub-supplier list (signicat, 1.4 d)
- Re: Placeholder Signicat (signicat, 37 d)
- Recall: Monthly Invoice for Consulting Services (signicat)
- Automatic reply: Signicat onboarding prepp! (signicat)

### Start & Dock-Pin

```bash
# Manueller Start
python3 ~/AssistantDev/src/message_dashboard.py
# oder
bash ~/AssistantDev/scripts/start_dashboard.sh
```

**Dock pinnen:** Wenn die App laeuft → Rechtsklick aufs Dock-Icon → "Optionen" → "Im Dock behalten".

**Optional Autostart:**
```bash
cp ~/AssistantDev/scripts/com.assistantdev.dashboard.plist.optional \
   ~/Library/LaunchAgents/com.assistantdev.dashboard.plist
launchctl load ~/Library/LaunchAgents/com.assistantdev.dashboard.plist
```

### Was NICHT geaendert wurde

- `web_server.py` — bleibt unveraendert
- `email_watcher.py` — bleibt unveraendert
- `kchat_watcher.py` — bleibt unveraendert
- Test Suite (360/360 weiter gruen ohne neue Dashboard-Tests, da Dashboard ein eigenstaendiges Programm ist und nicht via web_server.py erreichbar)

---

## [2026-04-10] Video-Retry + Agent-Button-UX + Tooltips

Drei zusammenhaengende UI-/Stabilitaets-Fixes via konsolidiertem Patch-Skript `scripts/patch_video_retry_ui_tooltips.py` (8 String-Replacements, alle idempotent mit Marker).

### Fix 1 — Veo Video Retry-Logik (`VEO_RETRY_V3`)

**Problem:** Gemini Veo schlug mit `code 13: Video generation failed due to an internal server issue` fehl, ohne Retry. Auch transiente Server-Ueberlastung (`code 14`) und Rate Limits (`429`) brachen sofort ab.

**Loesung:**
- **Outer Retry-Schleife** (3 Versuche) um den initialen `predictLongRunning` POST in `generate_video`
- `RETRYABLE_CODES = {13, 14, 429}` plus HTTP 5xx werden retried; alle anderen Fehler bubbeln sofort hoch
- **Exponentielles Backoff:** `BACKOFF = [0, 10, 20]` Sekunden vor Retry 1/2/3
- **Parameter-Fallback je Retry:**
  - Retry 0: `aspectRatio="16:9"`, `durationSeconds=8`, `veo-3.1-generate-preview`
  - Retry 1: `durationSeconds=5` (kuerzer)
  - Retry 2: `aspectRatio="9:16"` flip + `STABLE_FALLBACK_MODEL=veo-2.0-generate-001` (stabiles Veo-2-Modell)
- **User-facing Status je Error-Code** im Progress-Bar:
  - `code 13` → "Gemini Veo Server-Fehler — wird erneut versucht (N/3)..."
  - `code 429` → "Gemini Veo Rate Limit — warte Xs und versuche erneut..."
  - `code 14` → "Gemini Veo kurz nicht verfuegbar — wird erneut versucht..."
  - andere → "Unbekannter Fehler [code] — wird erneut versucht..."
- **Endmeldung** nach 3 Versuchen: `"Video-Generierung nach 3 Versuchen fehlgeschlagen. Bitte spaeter erneut versuchen. Letzter Fehler: ..."`
- **Logging** pro Retry: `[VEO] Retry N/3 (kuerzere Dauer): backoff Xs` + `[VEO] POST model=... aspect=... dur=Xs` + `[VEO] POST-Fehler code=... msg=...`
- Der bestehende `VEO_PATCH_V2` Poll-Loop (6 min, RAI-Filter, detailliertes Logging) bleibt ALLES ERHALTEN — nur der Operation-Start davor wurde gehaertet

### Fix 2 — Agent-Button mit integriertem Namen (`AGENT_BTN_V1`)

**Problem (laut Screenshot):** Aktiver Agent ("privat") als separates Label `<span id="agent-label" style="flex:1;">` LINKS neben einem `[Agent ↓]` Button → wirkt wie zwei verschiedene UI-Elemente.

**Loesung:**
- `<span id="agent-label" style="flex:1;">Kein Agent</span>` aus dem Header entfernt
- Neuer `<div id="header-spacer" style="flex:1;">` als reiner Layout-Spacer (uebernimmt das `flex:1`)
- `agent-label` wandert INS Innere des Agent-Buttons: `<button id="agent-btn" class="hdr-btn" data-tooltip-kind="agent" onclick="showAgentModal()"><span id="agent-label">Kein Agent</span> <span class="shortcut-label">[A]</span></button>`
- `getAgentName()` funktioniert unveraendert (liest weiterhin `agent-label.dataset.agentName`)
- Beim Wechsel via `selectAgent()` aktualisiert sich der Button-Text automatisch (kein Code-Change noetig)
- Stil identisch zu vorher (`hdr-btn`)

### Fix 3 — Tooltip-System (`TOOLTIPS_V1`)

**Was:** Hover-Tooltips auf Provider-Select, Modell-Select und Agent-Button mit dezentem Dark-Theme, 300 ms Delay, Auto-Positionierung (oben/unten je nach Viewport-Platz).

**Backend (`/agents` Route):**
- Neuer Helper `_agent_description(name)` liest erste 800 Zeichen aus `[agent].txt`, schneidet bei `--- GEDAECHTNIS:` etc., gibt die ersten ~180 Zeichen als Snippet zurueck
- `/agents` JSON-Response liefert jetzt fuer jeden Parent-/Sub-Agent ein `description` Feld

**Frontend:**
- **CSS** (`#tt-box`): fixed-positioned, dark-theme, `pointer-events:none`, smooth opacity-Transition, `.tt-title` (gold), `.tt-body` (grau), `box-shadow`
- **HTML:** `<div id="tt-box"><div class="tt-title"></div><div class="tt-body"></div></div>` direkt unter `<body>`
- **JS Maps:**
  - `PROVIDER_TOOLTIPS` mit allen 5 Providern (Anthropic / OpenAI / Google Gemini / Mistral / Perplexity)
  - `MODEL_TOOLTIPS` mit 20 Modellen (Claude Sonnet/Opus/Haiku 4.6, GPT-4o/Mini/o1, Mistral Large/Small/Nemo, Gemini 2.0/2.5 Flash/Pro, Gemini 3 Flash/Pro/3.1 Pro Preview, Sonar/Pro/Reasoning/Pro/Deep Research)
  - `AGENT_DESCRIPTIONS = {}` wird durch `loadAgents()` und durch initiales `loadProviders()` befuellt
- **Funktionen:** `ttShow(el)`, `ttHide()`, `ttAttach(el)`, `ttAttachAll()`, `ttGetContent(el)` (kind-basiert: provider/model/agent)
- **Bindings:** `ttAttachAll()` setzt `data-tooltip-kind` auf provider-select / model-select / agent-btn und verdrahtet `mouseenter` (300 ms Delay) + `mouseleave` + `mousedown` Handler. Wird in `loadProviders()` einmal aufgerufen
- **Auto-Positionierung:** Tooltip erscheint primaer UNTERHALB des Elements mit 8 px Abstand, weicht nach OBEN aus wenn nicht genug Platz, klemmt horizontal an Viewport-Raendern

### Patches & Tests

**Konsolidiertes Patch-Skript:** `scripts/patch_video_retry_ui_tooltips.py`
- 8 String-Replacements mit jeweils eigenem Marker (idempotent)
- Exakt 1 Vorkommen pro Replacement erforderlich, Fail-safe Abbruch sonst
- Zusatz-Patch `scripts/patch_fix_regex_escape.py` ersetzt eine JS-Regex mit `\\u{...}` Unicode-Escapes durch ASCII-only Variante (Python-HTML-Template-Loader scheiterte sonst mit `unicodeescape` SyntaxError beim Server-Start)

**Tests (`tests/run_tests.py`):**
- Neue Sektion "Features 2026-04-10 — Video Retry + Agent Button + Tooltips" mit **42 neuen Tests**:
  - Fix 1 (12 Tests): Marker, MAX_RETRIES, RETRYABLE_CODES, BACKOFF, Stable-Fallback-Modell, durationSeconds=5, aspectRatio flip, alle vier Status-Texte (13/14/429/sonst), Endmeldung, Retry-Label im Progress, payload-Parameter
  - Fix 2 (6 Tests): Marker, agent-btn id, agent-label INSIDE button (HTML-Position-Check), header-spacer, kein altes flex:1 Label, data-tooltip-kind=agent
  - Fix 3 (24 Tests): tt-box, CSS-Klassen, alle drei JS-Maps, Inhalts-Stichproben fuer alle 5 Provider + 4 prominente Modelle, ttShow/Hide/Attach/AttachAll Funktionen, 300 ms Hover-Delay, loadProviders+ttAttachAll wiring, /agents Helper + JSON-Live-Check (description Feld nicht-leer)
- Ergebnis: **360/360 Tests gruen** (+42 neu)

### Deployment

- Backup: `src/web_server.py.backup_20260410_111124`, `changelog.md.backup_<ts>`
- `cp src/web_server.py /Applications/Assistant.app/Contents/Resources/`
- `cp src/search_engine.py /Applications/Assistant.app/Contents/Resources/`
- `pkill -f web_server.py` → automatischer Restart via Assistant.app
- Regressions-Check: `/`, `/agents`, `/models` alle HTTP 200
- Live-Verifikation:
  - `/agents` JSON liefert `description`-Feld fuer alle Agenten und Sub-Agenten (signicat_lamp/meddpicc/outbound/powerpoint)
  - HTML enthaelt `id="tt-box"`, `id="agent-btn"`, `PROVIDER_TOOLTIPS` (2x — Map + Verwendung)
  - generate_video enthaelt `VEO_RETRY_V3`-Marker und `veo-2.0-generate-001` Stable-Fallback (2x referenziert)

**Browser-Cache leeren** (Cmd+Shift+R) damit neue JS/CSS geladen werden.

---

## [2026-04-10] kChat Inbound Watcher (Prioritaet 1)

**Ziel:** Hintergrunddienst der eingehende Infomaniak-kChat-Nachrichten automatisch ins AssistantDev Memory speichert — analog zu email_watcher.py.

**API-Analyse:**
- Getestet: 19 Endpoint-/Auth-Varianten (ksuite.infomaniak.com, api.infomaniak.com, kchat.infomaniak.com, kyb-group-bv.kchat.infomaniak.com mit Bearer/X-Auth-Token/Cookie)
- **Ergebnis:** kChat ist **Mattermost v4** Fork (Server meldet `x-version-id: 1.136.0`). Base URL: `https://kyb-group-bv.kchat.infomaniak.com/api/v4`. Auth-Header: `Authorization: Bearer <token>`
- Der bereitgestellte Token `[REDACTED_KCHAT_TOKEN]` wird vom Server mit HTTP 401 abgelehnt (Endpoint existiert, Token ungueltig/abgelaufen). **Moritz muss einen frischen Bot-Token** in der kChat Integrations-Seite erzeugen und in `models.json['kchat']['auth_token']` eintragen.
- Referenz-Implementierung: https://github.com/Infomaniak/mcp-server-kchat (eigener MCP-Server von Infomaniak)

**Neue Dateien:**
- `src/kchat_watcher.py` — Hintergrunddienst (469 Zeilen)
- `~/Library/LaunchAgents/com.assistantdev.kchat_watcher.plist` — macOS Autostart
- `~/.kchat_watcher_state.json` — Persist-State (last_check_ms, known_channel_ids, processed_post_ids)
- `~/.kchat_watcher_config.json` — Credential-Cache fuer LaunchAgent (mode 0600)

**Geaenderte Dateien:**
- `config/models.json` — Neuer Top-Level-Block `kchat` mit `server_url`, `api_base`, `team_name`, `auth_token`, `poll_interval_seconds`. Bestehende `providers` unveraendert. Backup: `models.json.backup_20260410_110212`

**Watcher-Features:**
- **Poll-Loop** alle 60 s via Mattermost v4 `/users/{id}/channels` + `/channels/{id}/posts?since=<ms>`
- **Erster Lauf:** importiert die letzten **24 Stunden**
- **State-Persistenz:** `last_check_ms` + `processed_post_ids` (max 5000) verhindern Doppel-Imports
- **Keyword-Routing:** hardcoded Liste analog email_watcher.py (signicat/elavon, trustedcarrier, privat, familie). Default-Agent: `privat`
- **Eigene Nachrichten** (user_id == self) werden uebersprungen, System-Nachrichten (Mattermost `type`-Feld gesetzt) ebenfalls
- **User-/Channel-Cache** reduziert API-Aufrufe
- **DMs + Gruppen-DMs + Channels** werden alle gepollt (Mattermost type D/G/O/P)
- **Fehlerbehandlung:** Netzwerk-/5xx → Warnung + weiter. HTTP 401 → Pause **5 Minuten** mit klarer Log-Meldung ("Token abgelaufen, bitte frischen Bot-Token in models.json eintragen"), dann retry
- **Suchindex-Integration:** `search_engine.index_single_file` wird automatisch aufgerufen falls verfuegbar

**Speicherformat:**
- Pfad: `[datalake]/[agent]/memory/kchat_YYYY-MM-DD_HH-MM-SS_<channel>.txt`
- Header: `Quelle: kChat | Kanal | Agent | Importiert | Nachrichten (Anzahl)`
- Pro Nachricht: `Von | Datum | Text`, getrennt durch Separator-Linien
- **Gruppierung:** Mehrere neue Nachrichten im selben Kanal landen chronologisch in einer Datei (nicht N einzelne Dateien)

**iCloud/LaunchAgent-Problem geloest:**
- Beim ersten manuellen Start mit Desktop-Session: liest `models.json` aus iCloud UND legt automatisch `~/.kchat_watcher_config.json` (mode 0600) als Spiegel an
- LaunchAgent (eingeschraenkte macOS Privacy-Sandbox, kein iCloud-Zugriff) nutzt den HOME-Cache als Fallback
- Bei jedem manuellen Run wird der Cache aktualisiert → Token-Wechsel ist nur an einer Stelle (models.json) noetig

**Tests:**
1. `python3 -m py_compile src/kchat_watcher.py` → OK
2. `plutil -lint .../com.assistantdev.kchat_watcher.plist` → OK
3. **Manueller Run:** Credentials aus iCloud geladen, nach HOME gespiegelt, API erreicht, HTTP 401 (Token-Erwartung bestaetigt), Pause-Logik aktiv
4. **LaunchAgent:** `launchctl load` erfolgreich, `launchctl list` zeigt PID 70759, HOME-Cache wird korrekt als Fallback verwendet, Poll-Loop stabil
5. **Regression:** email_watcher.py + web_server.py Syntax OK, HTTP 200 auf `/`, **318/318 Tests gruen** (keine Regression)

**Launchd Befehle:**
```bash
launchctl load   ~/Library/LaunchAgents/com.assistantdev.kchat_watcher.plist
launchctl unload ~/Library/LaunchAgents/com.assistantdev.kchat_watcher.plist
launchctl list | grep kchat
tail -f /tmp/kchat_watcher.log
```

**Verbleibender Action-Item fuer Moritz:**
- Frischen Bot-Token in kChat Integrations-Seite erzeugen (https://kyb-group-bv.kchat.infomaniak.com/kyb-group-bv/integrations/incoming_webhooks)
- In `config/models.json` unter `kchat.auth_token` eintragen
- `python3 ~/AssistantDev/src/kchat_watcher.py` einmal manuell starten → Cache wird automatisch aktualisiert
- Watcher laeuft dann ohne weiteres Zutun autonom

**Kein Deployment von web_server.py noetig** — diese Aufgabe hat web_server.py nicht angefasst.

---

## [2026-04-10] Veo Timeout Fix — 6 min Polling, Logging, Content-Filter-Erkennung

**Problem:** Video-Generierung (Gemini Veo) schlug regelmaessig nach ca. 60 s mit der generischen Meldung "Gemini Veo: Kein Video generiert" fehl, obwohl laut Dokumentation bis zu 5 Minuten Wartezeit normal sind. Ursachenanalyse war unmoeglich, da keinerlei Logging im Poll-Loop existierte.

**Befund:**
- `generate_video` Poll-Loop: `MAX_ATTEMPTS=60` x `sleep(5)` = **5 min** (nicht 60 s — der sichtbare 60 s-Abbruch kam NICHT vom Timeout)
- Die Fehlermeldung "Kein Video generiert" stammte aus Zeile 1754: wird geworfen sobald `done=true` aber `generatedSamples`/`predictions`/`generatedVideos` alle leer → d.h. die Veo API antwortete schnell mit `done=true` plus leerer Response. Wahrscheinlichste Ursache: **Content-/RAI-Filter** (`raiMediaFilteredCount > 0`) der nicht als Content-Filter erkannt wurde.
- Kein Frontend-Fetch-Timeout (`AbortController` nicht vorhanden), kein `socket.setdefaulttimeout`, kein Flask-Request-Timeout — die Ursache war rein serverseitig.

**Fix (`src/web_server.py`, Funktion `generate_video`, via `scripts/patch_veo_timeout.py`):**

**A) Polling-Zeitraum erhoeht:**
- `MAX_ATTEMPTS = 72` (statt 60)
- `POLL_INTERVAL = 5` als Konstante
- Gesamtdauer: **72 x 5 = 360 s = 6 Minuten** (+1 min gegenueber vorher)
- `TOTAL_SECS` wird dynamisch in der Fehlermeldung ausgegeben ("Timeout nach 6 Minuten (72 Versuche * 5s)")

**B) Detailliertes Logging in jedem Poll-Versuch:**
- Start-Log: `[VEO] Poll gestartet: op=... max_attempts=72 interval=5s total=360s`
- Pro Versuch: `[VEO] Poll #N/72 done=<bool> err=<bool> keys=[...]`
- Bei API-Fehler: `[VEO] API-Fehler code=<code>: <msg>`
- Bei Netzwerk-Fehler: `[VEO] Poll #N/72 Netzwerk-Fehler: ...` (und `continue` — transiente Fehler brechen die Operation nicht mehr ab)
- Bei leeren Samples: `[VEO] done=true aber keine samples gefunden. Response: <preview>`
- Bei unbekanntem Sample-Format: `[VEO] Sample-Format nicht erkannt. Erstes Sample: <preview>`
- Bei Erfolg: `[VEO] Video gespeichert: <path> (<bytes>)`
- Bei Timeout: `[VEO] TIMEOUT nach 360s (letzte API-Snapshot: ...)`
- `last_api_snapshot` haelt die letzte Response fest und wird in die Timeout-Exception integriert

**C) Content-Filter-Erkennung:**
- `raiMediaFilteredCount` + `raiMediaFilteredReasons` werden ausgelesen
- Eigene Fehlermeldung: `"Gemini Veo: Video wurde vom Content-Filter blockiert (<Gruende>). Bitte Prompt anpassen."`
- Statt der bisherigen generischen "Kein Video generiert" — Nutzer weiss jetzt warum und was zu tun ist

**D) Bessere Fehlerdiagnose:**
- API-Fehler werden mit Fehlercode und -Message geloggt und im Exception-Text uebernommen
- Bei leeren Samples: die ersten 200 Zeichen der Response werden in die Exception aufgenommen
- Bei unerkanntem Sample-Format: erstes Sample (500 Zeichen) wird geloggt, 200 Zeichen in Exception
- Bei Timeout: letzter API-Snapshot (150 Zeichen) in Exception

**E) Download-Timeout erhoeht:** `requests.get(dl_url, timeout=180)` (statt 120) — grosse Videos haben mehr Puffer

**Implementierung:**
- Patch-Skript: `scripts/patch_veo_timeout.py`
  - Idempotent (`VEO_PATCH_V2` Marker)
  - Exakter Blockvergleich (genau 1 Vorkommen erwartet, sicher gegen duplizierte Bloecke in 1-1358)
  - Fail-safe Abbruch bei unerwarteten Vorkommen
- Backup: `src/web_server.py.backup_20260410_084008`
- Changelog-Backup: `changelog.md.backup_<timestamp>`

**Tests (`tests/run_tests.py` — Sektion "Features 2026-04-10 — Veo Timeout Fix"):**
- 17 neue Tests: VEO_PATCH_V2 Marker, MAX_ATTEMPTS=72, POLL_INTERVAL=5, alle Log-Patterns, Content-Filter-Erkennung (raiMediaFilteredCount/Reasons + user-friendly Error), Transient-Error-Handling, Download-Timeout 180s, debug-Logs, Signatur-Kompatibilitaet mit Progress Bar System
- Ergebnis: **318/318 Tests gruen** (+17 neu)

**Deployment:**
- `cp src/web_server.py /Applications/Assistant.app/Contents/Resources/`
- `pkill -f web_server.py` → automatischer Restart via Assistant.app
- Regressions-Check: `/`, `/agents`, `/models`, `/task_status/<id>` alle HTTP 200 / 404 wie erwartet

**Beobachtbarkeit ab sofort:**
Wenn Videos fehlschlagen kann man jetzt via `tail -f` der Server-Stdout (oder Console.app) genau sehen:
- wie lange gepollt wurde
- was die API bei jedem Versuch zurueckgab
- ob es ein Content-Filter war
- welches Response-Format nicht erkannt wurde
- was die letzte API-Antwort vor einem Timeout war

---

## [2026-04-10] Progress Bar / Live Status fuer Video- und Bildgenerierung

**Problem:** Bei Video-Generierung (Gemini Veo, bis zu 5 Minuten) und Bild-Generierung war im Frontend nur der generische Typing-Indicator sichtbar. Der Nutzer hatte keinen Anhaltspunkt ueber Fortschritt, verstrichene Zeit oder erwartete Restdauer.

**Loesung:**

**Backend (`src/web_server.py`):**
- Neues Task-Status-System mit `TASK_STATUS` Dict + `threading.Lock()`
- Helper-Funktionen: `task_create`, `task_update`, `task_done`, `task_error`, `task_get`, `tasks_for_session`, `tasks_cleanup`
- `generate_video(..., task_id=None)`: erzeugt Progress-Updates im Poll-Loop (5→95% simulated progress, Phasen-Text "Initialisiert/Rendert/Fast fertig/Letzte Schritte"), `task_done` bei Erfolg
- `generate_image(..., task_id=None)`: einfachere Progress-Updates, `task_done` bei Erfolg
- `process_single_message`: erzeugt Task-IDs vor CREATE_IMAGE / CREATE_VIDEO und reicht sie durch, `task_error` bei Ausnahmen, `task_id` im `created_images` / `created_videos` Response
- Neue Route `GET /task_status/<task_id>` liefert `status`, `progress`, `message`, `elapsed_seconds`, `eta_seconds`, `estimated_total_seconds`, `kind`; 404 bei unbekannter ID
- `GET /queue_status` erweitert um `active_tasks` Liste — Frontend kann neue Tasks ohne separaten Endpoint entdecken

**Frontend (HTML/CSS/JS inline in web_server.py):**
- Neue CSS-Klassen `.task-progress`, `.tp-head`, `.tp-pulse`, `.tp-label`, `.tp-times`, `.tp-bar-outer`, `.tp-bar-inner` (+ `.done` / `.error` States), `@keyframes tpPulse` + `tpShimmer` — dezentes Dark-Theme, passt zum Akzentgelb `#f0c060`
- JS: `progressBars` Registry, `createProgressBar`, `updateProgressBar`, `removeProgressBar`, `pollTaskStatus` (alle 2s pro Task), `fmtDuration` Helper
- `discoverTasksOnce` + `startTaskDiscovery` / `stopTaskDiscovery`: laeuft waehrend `/chat` blockiert, pollt `/queue_status` und erzeugt Progress Bars fuer neue Task-IDs
- `doSendChat` startet/stoppt Task-Discovery automatisch
- Bestehende `startPolling`-Loop (Queue) erweitert: erkennt aktive Tasks ebenfalls und spawnt Progress Bars
- Abgeschlossene Tasks: Bar verbleibt kurz in Done-State, dann Fade-Out (800ms), das eigentliche Preview (addVideoPreview / addImagePreview) erscheint via Chat-Response

**Tests (`tests/run_tests.py`):**
- Neue Sektion "Features 2026-04-10 — Progress Bar / Task Status" mit 39 Tests:
  - Backend: TASK_STATUS, Lock, alle Helper-Funktionen, generate_video/image Signaturen, task_id-Durchreichung in process_single_message, task_done/task_error Aufrufe
  - Routes: `/task_status/<id>` Existenz, 404 JSON Response, `/queue_status` active_tasks Feld + leer bei frischer Session
  - Frontend: CSS-Klassen + Keyframes, alle JS-Funktionen, doSendChat Integration, Polling-Loop Erkennung, "verbleibend" ETA-Text

**Test-Ergebnis:** 301/301 Tests gruen (+39 neu)

**Deployment:**
- Backup: `src/web_server.py.backup_20260410_070013`
- Deployed nach `/Applications/Assistant.app/Contents/Resources/web_server.py`
- Server via `pkill -f web_server.py` neu gestartet
- Regressions-Check: `/`, `/agents`, `/models` alle HTTP 200

**Technische Details:**
- Task-IDs sind globale UUIDs, gespeichert per Session
- Task-Cleanup: finished Tasks aelter als 3600s werden opportunistisch entfernt
- Done-Tasks bleiben 15s im `/queue_status` active_tasks sichtbar, damit Frontend finalen State darstellen kann
- Video-Estimated-Total: 180s, Image-Estimated-Total: 30s
- Progress Bar wird waehrend `/chat`-Request angezeigt — Polling laeuft waehrend der Request blockiert, da Flask im Threading-Modus parallele Requests erlaubt

---

## BACKUP-ROUTINE (Standard-Vorgehen vor jeder Aenderung)

Vor JEDER Aenderung an Code-Dateien wird ein Backup erstellt:
```bash
cp ~/AssistantDev/src/web_server.py ~/AssistantDev/src/web_server.py.backup_$(date +%Y%m%d_%H%M%S)
```
Weitere Dateien die regelmaessig gesichert werden:
- `src/search_engine.py` → `.backup_YYYYMMDD_HHMMSS`
- `tests/run_tests.py` → `.backup_YYYYMMDD_HHMMSS`
- `changelog.md` → `.backup_YYYYMMDD_HHMMSS`
- `config/models.json` → Backup im gleichen Verzeichnis
- `contacts.json` → `.backup_YYYYMMDD_HHMMSS` im memory/-Ordner

Alle Aenderungen an web_server.py werden via Python-Skript durchgefuehrt (wegen duplizierter Bloecke in Zeilen 1-500 ≈ 570-1100). Skripte liegen unter `scripts/patch_*.py`.

Nach jeder Aenderung: `python3 -m py_compile src/web_server.py` + `python3 tests/run_tests.py`

---

## BUG-TRACKER — Bekannte Bugs & Status

| # | Status | Bug | Fix-Datum | Details |
|---|--------|-----|-----------|---------|
| 1 | ✅ GEFIXT | CREATE_WHATSAPP oeffnet WhatsApp ohne Chat | 2026-04-09 | 3-Stufen Kontakt-Lookup (contacts.json → Cross-Agent → macOS Contacts) |
| 2 | ✅ GEFIXT | Context-Bleeding: LLM wiederholt Actions aus vorherigen Turns | 2026-04-09 | Execution-Marker + KEINE WIEDERHOLUNG Anweisung |
| 3 | ✅ GEFIXT | Gemini Veo: numberOfVideos Parameter nicht unterstuetzt | 2026-04-09 | Parameter entfernt |
| 4 | ✅ GEFIXT | Perplexity Output abgeschnitten (max_tokens=4096) | 2026-04-09 | max_tokens auf 8000 erhoeht |
| 5 | ✅ GEFIXT | Perplexity Citations nicht klickbar | 2026-04-09 | Citations als Markdown-Links angehaengt |
| 6 | ✅ GEFIXT | LLM-Signatur fehlt (kein Provider/Modell sichtbar) | 2026-04-09 | PROVIDER_DISPLAY + MODEL_DISPLAY Mappings + Frontend |
| 7 | ✅ GEFIXT | Konversation geht verloren bei Session-Wechsel | 2026-04-09 | Sofort-Save + Atomic Writes |
| 8 | ✅ GEFIXT | Perplexity Message-Alternierung fehlerhaft | 2026-04-09 | Perplexity-spezifische Message-Normalisierung |
| 9 | ✅ GEFIXT | Perplexity Timeout bei Deep Research (120s) | 2026-04-09 | Modellspezifische Timeouts (300s/180s/120s) |
| 10 | ✅ GEFIXT | CREATE_FILE:docx erzeugt Markdown statt Word | 2026-04-09 | sanitize_llm_json fuer Single Quotes / Trailing Commas |
| 11 | ✅ GEFIXT | Gemini Image-Generierung: "only supports text output" | 2026-04-09 | Imagen 4 als primaeres Modell + Fallback-Chain |
| 12 | ✅ GEFIXT | Kontext-Dateien gehen verloren beim Konversations-Wechsel | 2026-04-09 | KONTEXT_DATEIEN Block in Konversationsdatei |
| 13 | ✅ GEFIXT | Sub-Agenten werden automatisch ohne Rueckfrage delegiert | 2026-04-09 | Confirmation-Banner mit Ja/Nein Buttons |
| 14 | ✅ GEFIXT | Veo Video-Download fehlt API-Key | 2026-04-09 | API-Key als Query-Parameter an Download-URL |
| 15 | ✅ GEFIXT | macOS Contacts: Sebastian Schroeder mit 64 falschen E-Mails | 2026-04-09 | AddressBook SQLite-DB bereinigt |
| 16 | ✅ GEFIXT | Doppel-Punkt in Bild/Video-Fehlermeldungen | 2026-04-09 | Trailing Period entfernt |
| 17 | ✅ GEFIXT | Agenten sagen "Ich kann keine Bilder erstellen" | 2026-04-09 | System-Prompt um CREATE_IMAGE/VIDEO Capability erweitert |
| 18 | ✅ GEFIXT | **KRITISCH:** JS SyntaxError blockierte gesamte App | 2026-04-09 | Escaped Quotes in onclick-Handler → &apos; statt \\' |

---

## SYSTEMDOKUMENTATION — Memory & Zugriffs-Matrix
*(Permanent — wird bei Aenderungen aktualisiert, nicht geloescht)*

### Basis-Pfad (iCloud)
`~/Library/Mobile Documents/com~apple~CloudDocs/Downloads shared/claude_datalake/`

### Lokales Agent-Memory (Lesen + Schreiben)
Jeder Agent hat exklusiven Schreibzugriff auf seinen eigenen Ordner.
Sub-Agenten (z.B. `signicat_outbound`) teilen den Ordner des Parent-Agenten.

| Pfad | Inhalt |
|------|--------|
| `[agent]/memory/` | Dateien, E-Mails, Web Clips des Agenten |
| `[agent]/konversation_*.txt` | Gespeicherte Chatverlaeufe (direkt im Agent-Ordner) |
| `[agent]/_index.json` | Session-Zusammenfassungen (max 50 Eintraege) |
| `[agent]/.search_index.json` | Such-Index des Agenten |

Bekannte Agenten: `signicat` (+ Sub-Agents: outbound, powerpoint, lamp, meddpicc), `privat`, `trustedcarrier`, `standard`, `system ward`

### Globales Memory (Lesen via Globale Suche)
Alle Agenten koennen via "erweitertes gedaechtnis" / globale Suche lesen:

| Pfad | Inhalt |
|------|--------|
| `claude_datalake/email_inbox/` | Eingehende E-Mails (Apple Mail Regel) |
| `Downloads shared/webclips/` | Web Clips aller Agenten (Dual Save) |
| `Downloads shared/claude_outputs/` | Von Claude erstellte Dateien |
| `Downloads shared/.global_search_index.json` | Globaler Such-Index |
| `Downloads shared/*.pdf, *.docx, ...` | Alle Dateien im Downloads shared |

### Globales Memory (Schreiben)
| Trigger | Ziel |
|---------|------|
| Chrome Extension Web Clip | `webclips/[agent]_[filename]` (Dual Save) |
| Datei-Erstellung (CREATE_FILE) | `[agent]/memory/[dateiname]` |
| E-Mail-Import (Email Watcher) | `[agent]/memory/email_[datum].txt` |

### AssistantDev System-Dateien (kein Agent-Zugriff)
Diese Dateien sind nur fuer Moritz / Claude Code zugaenglich:

| Pfad | Inhalt |
|------|--------|
| `src/web_server.py` | Haupt-App (Flask Server + Frontend) |
| `src/search_engine.py` | Such-System (Index, Parser, Hybrid-Suche) |
| `src/web_clipper_server.py` | Chrome Extension Backend (Port 8081) |
| `src/email_watcher.py` | E-Mail-Ueberwachung |
| `src/app.py` | macOS Menu Bar App |
| `config/models.json` | API-Keys + Modell-Konfiguration |
| `config/subagent_keywords.json` | Keyword-Routing fuer Sub-Agenten |
| `CLAUDE.md` | Regeln fuer Claude Code |
| `changelog.md` | Systemdokumentation |

---

## 2026-04-09

### Tagesuebersicht: 17 Bugfixes + 5 Features in einer Session
**Teststand:** 219 → 262 Tests (43 neue Unit-Tests fuer alle heutigen Aenderungen)
**Backups:** 12+ Backups von web_server.py erstellt (alle unter `src/web_server.py.backup_20260409_*`)
**Patch-Skripte erstellt:** 11 Skripte unter `scripts/patch_*.py`
**Geaenderte Dateien:** `src/web_server.py`, `config/models.json`, `CLAUDE.md`, `tests/run_tests.py`, `changelog.md`

#### Zusammenfassung der Aenderungen (chronologisch):
1. CREATE_WHATSAPP: 3-Stufen Kontakt-Lookup (contacts.json → Cross-Agent → macOS Contacts)
2. Context-Bleeding: Execution-Marker + KEINE WIEDERHOLUNG Anweisung
3. Gemini Veo: numberOfVideos Parameter entfernt
4. CLAUDE.md: Autonomes Arbeiten dokumentiert
5. Perplexity: max_tokens 4096 → 8000
6. Perplexity: Citations als klickbare Markdown-Links
7. LLM-Signatur: Provider + Modell in jeder Antwort (PROVIDER_DISPLAY/MODEL_DISPLAY)
8. Konversations-Sicherheit: Sofort-Save + Atomic Writes
9. Perplexity: Modellspezifische Timeouts (300s/180s/120s)
10. Perplexity: Message-Alternierung (Merge consecutive same-role)
11. CREATE_FILE: sanitize_llm_json fuer Single Quotes / Trailing Commas
12. Gemini: Imagen 4 als primaeres Bildmodell + Fallback-Chain
13. Gemini: 4 neue Chat-Modelle im Dropdown (Gemini 3 Flash/Pro, 3.1 Pro, 2.0 Flash)
14. macOS Contacts: Sebastian Schroeder Pollution bereinigt (64 → 1 E-Mail)
15. Kontext-Dateien: Persistenz bei Konversations-Wechsel (KONTEXT_DATEIEN Block)
16. CREATE_IMAGE/VIDEO: Fehlermeldungen verbessert + System-Prompt Capability
17. Sub-Agent Delegation: User-Confirmation statt automatischer Weiterleitung
18. Veo Video-Download: API-Key als Query-Parameter
19. Unit-Tests: 43 neue Tests fuer alle heutigen Aenderungen (219 → 262)

---

### Unit-Tests: 43 neue Tests fuer Features 2026-04-09
- WhatsApp 3-Stufen Lookup (2 Tests)
- Context-Bleeding Fix (2 Tests)
- Veo numberOfVideos (1 Test)
- LLM-Signatur Provider/Model Display (5 Tests)
- Konversations-Sicherheit Atomic Writes (2 Tests)
- Perplexity Fixes: max_tokens, Citations, Timeouts, Alternierung (5 Tests)
- CREATE_FILE JSON Sanitizer: Funktion + 3 Funktionstests (5 Tests)
- Gemini Bild/Video: Imagen 4, Veo URI, models.json (5 Tests)
- System-Prompt Capabilities (2 Tests)
- Kontext-Dateien Persistenz (4 Tests)
- Sub-Agent Confirmation: Route, Frontend, Pending-Dict (7 Tests)
- Fix-Skripte existieren (2 Tests)
- **Teststand: 262/262 bestanden**

---

### KRITISCHER Bugfix: JavaScript SyntaxError blockierte gesamte App
- **Problem:** Nach dem Sub-Agent-Confirmation-Patch oeffnete sich das Agent-Modal nicht mehr. Gesamtes JavaScript brach ab — App war unbenutzbar ("Kein Agent aktiv")
- **Root Cause:** `confirmSubagent(\\'' + data.confirmation_id + '\\',true)` — die escaped Single Quotes `\\'` wurden im HTML als `''` (leerer String + unerwarteter String) gerendert → **SyntaxError: Unexpected string** auf HTML-Zeile 1068 → blockierte das gesamte `<script>`-Tag
- **Fix:** `\\'` ersetzt durch `&apos;` (HTML-Entity) — korrekte Escape-Sequenz fuer Single Quotes in HTML onclick-Attributen
- **Verifiziert:** Agent-Modal oeffnet sich, Agent "privat" geladen mit Memory + Konversationshistorie
- **Dateien:** `src/web_server.py` | via `scripts/patch_confirm_quotes.py`
- **Tests:** 262/262 bestanden

### Bugfix: Veo Video-Download fehlte API-Key
- **Problem:** `generate_video` lud das fertige Video von der Gemini URI ohne API-Key herunter → HTTP 403
- **Fix:** API-Key wird jetzt als Query-Parameter an die Download-URL angehaengt + HTTP-Status-Check
- **Verifiziert:** Testvideo (10.6 MB, Golden Retriever, Veo 3.1) erfolgreich generiert und heruntergeladen in 60s
- **Dateien:** `src/web_server.py` | via `scripts/patch_veo_uri.py`
- **Tests:** 219/219 bestanden

### Feature: Sub-Agent Delegation mit User-Confirmation
- **Problem:** Tasks wurden automatisch an Sub-Agenten delegiert ohne den User zu fragen
- **Fix:** Keyword-Match loest jetzt Confirmation-Banner aus statt sofortiger Weiterleitung
- **Backend:** `detect_delegation` gibt jetzt dict mit score+matched_keywords zurueck. Neue Route `POST /api/subagent_confirm` fuer Bestaetigung/Ablehnung. Pending Requests werden 5 Min im Memory gehalten
- **Frontend:** Confirmation als Chat-Nachricht (kein Modal): "Sub-Agent erkannt: [name] | Keywords: [...] | [Ja] [Nein]". Nach Klick: Buttons verschwinden, Status bleibt. Timeout 5 Min → automatisch Nein
- **Edge Cases:** Neue Nachricht waehrend Confirmation → alte verfaellt automatisch. Mehrere Matches → hoechster Score gewinnt
- **handleChatResponse:** Response-Handling in wiederverwendbare Funktion extrahiert (fuer Confirmation-Flow)
- **Dateien:** `src/web_server.py` | via `scripts/patch_subagent_confirm.py`
- **Tests:** 219/219 bestanden

### Fix: CREATE_IMAGE/VIDEO Fehlermeldungen + System-Prompt Capability
- **Doppel-Punkt Fix:** Fehlermeldungen bei Bildgenerierung hatten doppelten Punkt ("verfuegbar.. Du kannst") — trailing Period aus `generate_image` und `generate_video` entfernt
- **System-Prompt:** Bild/Video-Erstellungs-Capability in den "WEITERE FAEHIGKEITEN"-Block eingefuegt — Agenten wissen jetzt dass CREATE_IMAGE (Imagen 4 / gpt-image-1) und CREATE_VIDEO (Veo) verfuegbar sind und sagen nie mehr "Ich kann keine Bilder erstellen"
- **Image-Routing bereits korrekt:** Gemini nutzt Imagen 4 → Gemini-Native Fallback-Chain, OpenAI nutzt gpt-image-1 — das Chat-Modell wird NICHT fuer Bildgenerierung verwendet (fruehere Session bereits gefixt)
- **Dateien:** `src/web_server.py` | via `scripts/patch_image_error_prompts.py`
- **Tests:** 219/219 bestanden

### Feature: Kontext-Dateien Persistenz bei Konversations-Wechsel
- **Problem:** Explizit geladene Kontext-Dateien (Drag&Drop, Suche) gingen beim Schliessen einer Konversation verloren
- **Fix auto_save:** Kontext-Dateien werden als `[KONTEXT_DATEIEN:[...]]` JSON-Block am Ende der konversation_*.txt gespeichert
- **Fix load_conversation:** Beim Laden einer Konversation wird der Block geparst, existierende Dateien automatisch in den Kontext geladen
- **Fehlende Dateien:** Werden als Warnung angezeigt ("X Kontext-Datei(en) nicht mehr verfuegbar: ...")
- **UX:** Dateinamen in Kontext-Leiste auf 40 Zeichen erweitert, Tooltip mit vollem Namen bei Hover
- **Dateien:** `src/web_server.py` | via `scripts/patch_context_persistence.py`
- **Tests:** 219/219 bestanden

### Bugfix: CREATE_FILE JSON-Parsing — LLM-Output Sanitizer
- **Problem:** CREATE_FILE:docx schlug fehl mit "Expecting property name enclosed in double quotes" — LLMs (besonders Gemini) erzeugten JSON mit Single Quotes statt Double Quotes
- **Root Cause:** `json.loads()` ist strikt und akzeptiert keine Single Quotes, Trailing Commas oder Markdown Code-Fences. Die Datei-Erstellungsfunktionen (docx, xlsx, pdf) waren korrekt — nur das JSON-Parsing vorher scheiterte
- **Fix:** Neue `sanitize_llm_json()` Funktion die 4 Parsing-Strategien versucht:
  1. Standard `json.loads()` (strict)
  2. `ast.literal_eval()` (Python-Syntax mit Single Quotes)
  3. Trailing-Comma-Entfernung + Quote-Replacement
  4. Original-Fehler weiterwerfen
- **Fehlermeldung verbessert:** Statt rohem Python-Traceback jetzt "JSON-Format ungueltig. Bitte versuche es erneut."
- **Libraries:** python-docx ✓, openpyxl ✓, reportlab ✓ (alle installiert)
- **Test:** `scripts/test_file_creation.py` — alle 5 JSON-Formate + DOCX/XLSX/PDF Erstellung bestanden
- **Dateien:** `src/web_server.py` | via `scripts/patch_json_sanitizer.py`
- **Tests:** 219/219 bestanden

### Fix: Gemini Bild/Video-Generierung + Modell-Dropdown
- **Image-Fix:** Imagen 4 (`imagen-4.0-generate-001`) als primaeres Bildmodell fuer Google Gemini. Fallback-Chain: Imagen 4 → Imagen 4 Fast → Gemini 2.5 Flash Image → Gemini 3.1 Flash Image → Gemini 3 Pro Image
- **Kein Provider-Wechsel:** Bildgenerierung bleibt immer beim gewahlten LLM-Anbieter. Andere Anbieter: OpenAI nutzt `gpt-image-1`, Mistral/Perplexity/Anthropic: Fehlermeldung
- **Video:** Veo 3.1 bleibt (war bereits korrekt konfiguriert)
- **Neue Gemini Chat-Modelle im Dropdown:** Gemini 3 Flash, Gemini 3 Pro, Gemini 3.1 Pro, Gemini 2.0 Flash (4 neue)
- **MODEL_DISPLAY:** Alle neuen Modelle mit human-readable Namen
- **MODEL_CAPABILITIES:** Alle Gemini-Modelle mit image+video Tags
- **models.json:** Gemini-Sektion aktualisiert (6 Chat-Modelle, image_model → imagen-4.0-generate-001)
- **Dateien:** `src/web_server.py`, `config/models.json` | via `scripts/patch_gemini_models.py`
- **Tests:** 219/219 bestanden

### Fix: macOS Contacts Pollution — Sebastian Schroeder (64 → 1 E-Mail)
- **Problem:** Apple Mail Autocomplete zeigte bei "Sebastian Schroeder" 64 voellig unzusammenhaengende E-Mails (eigene Adressen, PayPal, Amazon, Shopify, Signicat-Kollegen etc.)
- **Root Cause:** macOS Contacts-Datenbank (iCloud Source A42FFC88) hatte einen Kontakt "Sebastian Schroeder / Brandshares" mit 64 E-Mails aus 42 Domains. Das ist ein iCloud/CardDAV Sync-Problem — NICHT die AssistantDev contacts.json
- **Fix:** 63 falsche E-Mails aus der macOS AddressBook SQLite-DB entfernt, nur sebastian.schroeder@ikano.de behalten
- **Backup:** AddressBook-v22.abcddb.backup_20260409_131433
- **Fix-Skript:** `scripts/fix_contacts_pollution.py` (wiederverwendbar mit --fix Flag)
- **WICHTIG:** Apple Mail neu starten damit Aenderungen wirksam werden

### Analyse: contacts.json Korruptions-Check
- **Ergebnis:** contacts.json ist NICHT korrupt (Score: 0, Bewertung: OK)
- 91 Kontakte, jeder mit genau 1 E-Mail — keine Anomalien, keine Duplikate
- Sebastian Schroeder hat nur sebastian.schroeder@ikano.de — keine fremden E-Mails
- Code-Review: Beide Systeme (analyze_contacts.py + email_watcher.py) verwenden E-Mail als Primary Key — Name-basierte Merge-Kollisionen sind ausgeschlossen
- **Backup:** contacts.json.backup_20260409_*
- **Report:** claude_outputs/contact_corruption_report_20260409.md
- **Analyse-Skript:** scripts/analyze_contact_corruption.py

### Bugfix: Perplexity Message-Alternierung
- **Problem:** Perplexity API warf "user or tool messages should alternate with assistant messages" — die Message-Array-Struktur verletzte die strenge Alternierungsanforderung
- **Ursache:** `state['verlauf']` kann nicht-alternierende Rollen enthalten durch: MEMORY_SEARCH Re-Queries (injiziert assistant+user Messages), geladene Konversationen mit Luecken, Vision-Messages mit list-content
- **Fix:** Perplexity-spezifische Message-Normalisierung vor dem API-Call:
  1. Leere Messages entfernen
  2. List-Content (Vision) zu Text flattenen
  3. Aufeinanderfolgende gleiche Rollen zusammenfuehren (merge mit `\n\n`)
  4. Sicherstellen dass erste Message nach system = `user` und letzte = `user`
- **Provider-spezifisch:** Nur fuer Perplexity — Anthropic, OpenAI, Gemini, Mistral bleiben unveraendert
- **2 Vorkommen** gefixt (duplizierter Block: Zeilen ~324 und ~1317)
- **Dateien:** `src/web_server.py` | via `scripts/patch_perplexity_alternation.py`
- **Tests:** 217/217 bestanden

### Bugfix: Perplexity Connection Timeout — modellspezifische Timeouts
- **Problem:** Sonar Deep Research schlug bei komplexen Anfragen mit Timeout nach 120s fehl
- **Fix:** Modellspezifische Timeouts mit tuple (connect, read):
  - `sonar-deep-research`: 300s (5 Min)
  - `sonar-reasoning` / `sonar-reasoning-pro`: 180s (3 Min)
  - `sonar` / `sonar-pro`: 120s (2 Min — wie bisher)
- **Error-Handling:** Benutzerfreundliche Fehlermeldungen statt roher Python-Fehler:
  - Timeout: "Perplexity Sonar Deep Research hat zu lange gebraucht (Timeout nach 300s). Versuche es erneut oder waehle ein schnelleres Modell."
  - ConnectionError: "Verbindung zu Perplexity fehlgeschlagen. Pruefe deine Internetverbindung."
- **2 Vorkommen** gefixt (duplizierter Block: Zeilen ~324 und ~1285)
- **Dateien:** `src/web_server.py` | via `scripts/patch_perplexity_timeout.py`
- **Tests:** 217/217 bestanden

### Feature: LLM Provider + Modell in Antwort-Signatur (#kritisch)
- Jede Assistant-Antwort zeigt jetzt: `Zeit · Provider / Modell` (z.B. "08:27 · Anthropic / Claude Sonnet 4.6")
- Backend liefert `provider_display` + `model_display` im Response-JSON
- Human-readable Mapping fuer alle 5 Provider (Anthropic, OpenAI, Mistral, Google, Perplexity)
- Human-readable Mapping fuer ~17 Modelle (Claude, GPT, Gemini, Sonar, Mistral)
- Frontend: Provider/Modell in grau-kursiv unter jeder Assistant-Nachricht
- Fallback: unbekannte Modell-IDs werden direkt angezeigt
- **Dateien:** `src/web_server.py` | via `scripts/patch_signature_save.py`

### Bugfix: Absolute Konversations-Sicherheit (#kritisch)
- **Problem:** Konversation ueber AI-Identitaeten ging verloren — nicht wiederherstellbar
- **Sofort-Save:** User-Nachricht wird SOFORT nach Empfang gespeichert (vor der LLM-Antwort)
- **Atomic Writes:** Alle Konversations-Dateien werden via `.tmp` + `os.replace()` geschrieben — keine korrupten/leeren Dateien bei Absturz
- **Betroffene Stellen:** auto_save_session, new_conversation, agent_init (3 Schreib-Pfade auf Atomic umgestellt)
- **Dateinamen:** Format `konversation_YYYY-MM-DD_HH-MM.txt` bleibt unveraendert, wird beim ersten Speichern festgelegt
- **Load-Schutz:** Session-Datei wird durch /find oder Sidebar-Load nicht ueberschrieben (war bereits korrekt implementiert)
- **Recovery-Status:** Konversation ueber AI-Identitaeten NICHT WIEDERHERSTELLBAR — in keiner Datei im Datalake gefunden
- **Dateien:** `src/web_server.py` | via `scripts/patch_signature_save.py`
- **Backup:** `src/web_server.py.backup_20260409_*`
- **Tests:** 217/217 bestanden

### Bugfix: Perplexity max_tokens auf 8000 erhoeht
- **Problem:** Perplexity Sonar Deep Research Output wurde mittendrin abgeschnitten (max_tokens=4096 zu niedrig)
- **Fix:** max_tokens von 4096 auf 8000 erhoeht fuer alle Perplexity Sonar-Modelle
- **Alter Wert:** 4096 | **Neuer Wert:** 8000
- **2 Vorkommen** gefixt (duplizierter Block: Zeilen ~324 und ~1229)
- **Dateien:** `src/web_server.py` | via `scripts/patch_perplexity.py`

### Feature: Perplexity Citations als klickbare Links
- **Problem:** Perplexity API gibt Citations (Quellen-URLs) in separatem `citations`-Feld zurueck. Diese wurden ignoriert — im Chat nur nackte [1][2][3] ohne URLs
- **Fix:** `call_perplexity` umgebaut: nutzt jetzt raw requests statt openai SDK um auf `citations`-Feld zuzugreifen. Citations werden als Markdown-Links angehaengt:
  ```
  **Quellen:**
  [1] [example.com](https://example.com/article)
  [2] [docs.example.org](https://docs.example.org/page)
  ```
- Domain wird fuer Lesbarkeit extrahiert, volle URL als Link-Ziel
- **2 Vorkommen** gefixt (duplizierter Block)
- **Dateien:** `src/web_server.py` | via `scripts/patch_perplexity.py`
- **Backup:** `src/web_server.py.backup_20260409_*`
- **Tests:** 217/217 bestanden (2 Warnungen: /find Timeout + WebClipper 404 — infrastrukturell)

### CLAUDE.md: Autonomes Arbeiten als Pflichtverhalten dokumentiert
- Neuer Abschnitt "ARBEITSWEISE: VOLLSTAENDIG AUTONOM" ganz oben eingefuegt
- Keine Rueckfragen mehr — direkt analysieren, umsetzen, berichten
- Einzige Ausnahme: irreversible destruktive Aktionen
- **Dateien:** `CLAUDE.md`

### Bugfix: Gemini Veo — numberOfVideos Parameter entfernt
- **Problem:** Veo API-Call schlug fehl mit "numberOfVideos isn't supported by this model"
- **Fix:** Parameter `numberOfVideos: 1` aus dem Veo predictLongRunning API-Call entfernt (Zeile 1410)
- **1 Vorkommen** gefixt
- **Dateien:** `src/web_server.py` | via `scripts/patch_video_context.py`

### Bugfix: Context-Bleeding — Action-Wiederholung verhindert
- **Problem:** Wenn User zuerst z.B. WhatsApp anfragt und danach Video, feuerte das LLM erneut CREATE_WHATSAPP statt die neue Anfrage zu verarbeiten
- **Ursache:** CREATE_WHATSAPP/EMAIL/SLACK-Bloecke wurden aus der Assistant-Response **spurlos entfernt** bevor sie in den `verlauf` gespeichert wurde. Das LLM sah nur den umgebenden Text (z.B. "Ich schicke Renata eine Nachricht") ohne Hinweis dass die Aktion bereits ausgefuehrt wurde — und erzeugte sie erneut
- **Fix (zweiteilig):**
  1. **Execution-Marker:** Statt stiller Entfernung werden CREATE_*-Bloecke durch `[WhatsApp an X vorbereitet — Aktion ausgefuehrt]` ersetzt. Das LLM sieht im naechsten Turn klar, dass die Aktion bereits durchgefuehrt wurde
  2. **System-Prompt Erweiterung:** Neue Anweisung "KEINE WIEDERHOLUNG" — Actions duerfen nur einmal pro expliziter Nutzer-Anfrage erzeugt werden
- **8 Stellen** gepatcht: CREATE_EMAIL (ok+err), CREATE_WHATSAPP (ok+err), CREATE_SLACK (ok+err), System-Prompt, Veo API
- **Dateien:** `src/web_server.py` | via `scripts/patch_video_context.py`
- **Backup:** `src/web_server.py.backup_20260409_*`
- **Tests:** 219/219 bestanden

### Bugfix: CREATE_WHATSAPP — 3-Stufen Kontakt-Lookup
- **Problem:** WhatsApp oeffnete sich ohne Chat, weil Kontakt-Lookup nur in der contacts.json des eigenen Agenten suchte. Kontakte wie "Renata" waren dort nicht vorhanden.
- **Fix:** 3-stufiger Telefonnummer-Lookup implementiert:
  1. contacts.json des eigenen Agenten (wie bisher)
  2. NEU: Cross-Agent-Suche in allen contacts.json Dateien
  3. NEU: macOS Contacts App via AppleScript (`tell application "Contacts"`)
- **Fallback:** Wenn keine Nummer gefunden: WhatsApp oeffnen + Text in Clipboard + klare Fehlermeldung mit Kontaktname
- **Frontend:** Statusmeldungen verbessert — zeigen jetzt ob Chat geoeffnet oder Nummer nicht gefunden
- **URL-Schema:** `whatsapp://send?phone=+NUMMER&text=NACHRICHT` (unveraendert, funktioniert korrekt wenn Nummer vorhanden)
- **Dateien:** `src/web_server.py` | Aenderung via `scripts/patch_whatsapp.py`
- **Backup:** `src/web_server.py.backup_20260409_*`
- **Tests:** 219/219 bestanden

---

## 2026-04-08

### Feature: CREATE_SLACK — Slack Desktop Draft
- Neuer Trigger `[CREATE_SLACK:{"channel":"#name","message":"text"}]` analog zu CREATE_EMAIL/WHATSAPP
- Auch DM moeglich: `[CREATE_SLACK:{"to":"Vorname","message":"text"}]`
- Oeffnet Slack Desktop App, fuegt Text via Clipboard + Cmd+V ein
- Kein automatisches Senden — User muss manuell absenden
- Neue Route `POST /open_slack_draft`
- Neuer Slash-Command `/create-slack`
- System Prompt fuer alle Agenten erweitert
- Backup: backups/2026-04-08_21-48-34/

### Fix: send_whatsapp_draft war als Funktion nicht definiert (Critical Bug)
- Problem: Zweiter `send_email_draft` Block hatte unclosed triple-quoted f-string
- Die gesamte `send_whatsapp_draft` Funktion war im String verschluckt (seit WhatsApp Integration)
- AST-Analyse bestaetigte: Funktion existierte nicht als Python-Funktion
- Fix: `end tell'''` korrekt geschlossen, `send_whatsapp_draft` als eigenstaendige Funktion wiederhergestellt
- Tests: AST-basierte Verifikation fuer beide Funktionen hinzugefuegt

### Fix: Video-Generierung Veo 3.1 API-Endpunkt
- Problem: CREATE_VIDEO rief gemini-2.0-flash auf (deprecated, 404)
- Fix: VIDEO_PROVIDERS aktualisiert auf `veo-3.1-generate-preview`
- MODEL_CAPABILITIES: Video-Tag von gemini-2.0-flash auf gemini-2.5-flash verschoben
- generate_video: Response-Parsing an aktuelle Veo API angepasst (generateVideoResponse.generatedSamples)
- models.json: gemini-2.0-flash entfernt, video_model auf veo-3.1-generate-preview aktualisiert
- agent_model_preferences.json: gespeicherte Referenz auf gemini-2.0-flash korrigiert
- Backup: backups/2026-04-08_21-31-33/

### Fix: Provider/Modell-Persistenz pro Agent (synchron)
- Problem: Agent-Wechsel lud Preference async (fire-and-forget), Race Condition moeglich
- Fix: Backend select_agent() laedt jetzt gespeicherte Preference und setzt state + gibt sie in Response zurueck
- Frontend selectAgent() nutzt die Response-Daten synchron (await) statt separatem async Fetch
- Status-Meldung zeigt jetzt korrektes Modell nach Agent-Wechsel

### WhatsApp Integration + Model Fixes + Sticky Preferences

#### CREATE_WHATSAPP Handler (Feature)
- Neuer `[CREATE_WHATSAPP:{"to":"Name","message":"Text"}]` Block analog zu CREATE_EMAIL
- Name-Lookup in contacts.json des aktiven Agents (phone-Feld)
- Oeffnet WhatsApp Desktop mit vorausgefuellter Nachricht via `whatsapp://send?phone=...`
- Kein automatisches Senden — nur Draft
- Frontend-Bestaetigung im Chat
- API-Route `/send_whatsapp_draft`

#### Gemini Model Fixes (Bug Fix)
- `gemini-2.0-flash-lite` entfernt (deprecated), ersetzt durch `gemini-2.0-flash`
- trustedcarrier_instagramm System Prompt: Video-Faehigkeit (CREATE_VIDEO) dokumentiert, Agent darf nicht mehr sagen "ich kann keine Videos erstellen"

#### Model Dropdown Bug Fix
- Dark-mode CSS fuer `<select>` options (waren unsichtbar: dunkler Text auf dunklem Hintergrund)
- `appearance:menulist` + `min-width:120px` fuer konsistentes Dropdown-Verhalten

#### Capability-Tags im Dropdown (Feature)
- Emoji-Tags hinter Modellnamen: Video, Bild, Reasoning
- Backend-Dictionary `MODEL_CAPABILITIES` + `CAPABILITY_EMOJI` (leicht wartbar)
- Tags werden dynamisch im `/models` Response mitgegeben

#### Per-Agent Sticky Model Selection (Feature)
- Neue Datei `config/agent_model_preferences.json`
- API: `GET/POST /api/agent-model-preference`
- Frontend: Speichert bei jeder manuellen Model-Aenderung, laedt bei Agent-Wechsel
- Jeder Agent merkt sich seinen Provider + Modell

#### Veo 2 → Veo 3.1 Migration (Bug Fix)
- `veo-2.0-generate-001` deprecated (Deadline: 30.06.2026), ersetzt durch `veo-3.1-generate-001`
- VIDEO_PROVIDERS Dict und generate_video() aktualisiert
- Model-ID wird jetzt aus VIDEO_PROVIDERS gelesen statt hardcoded

#### WhatsApp Clipboard-Fallback (Feature)
- Wenn kein Kontakt/Telefonnummer gefunden: Nachricht wird in Zwischenablage kopiert (pbcopy) und WhatsApp ohne spezifischen Chat geoeffnet
- Frontend zeigt angepasste Meldung ("Nachricht in Zwischenablage kopiert")
- Kein Abbruch mehr bei fehlendem Kontakt

#### /create Slash Commands (Feature)
- Neue Slash-Commands fuer alle Erstell-Aktionen: `/create-email`, `/create-whatsapp`, `/create-image`, `/create-video`, `/create-file-docx`, `/create-file-xlsx`, `/create-file-pdf`, `/create-file-pptx`
- Bei `/` im Input erscheinen jetzt alle Befehle (Create + Find + Find Global)
- Create-Commands fuellen ein Template in den Input ein (z.B. "Erstelle eine E-Mail an [Empfaenger] zum Thema: ")
- Template wird als normaler Chat an die KI gesendet — kein spezielles Routing noetig

#### Tests: 219/219 bestanden

### Contacts Cleanup — Falsche Zuordnungen repariert

#### analyze_contacts.py — 3 Bugs behoben:
1. **Signatur-Cross-Contamination behoben**: Signaturen aus weitergeleiteten/zitierten E-Mails wurden faelschlich dem Absender zugeordnet (z.B. Farooq Rashids Titel bei Arne Vidar Haug). Fix: `extract_sender_section()` schneidet Forward/Quote-Inhalte ab, Signatur wird gegen Absendernamen validiert.
2. **Notification-Filter**: 17+ Muster (Teams, Slack, Outlook, Confluence, HiBob, etc.) werden jetzt rausgefiltert. Kontakte: 105 → 91.
3. **Telefon-Deduplizierung**: Gleiche Nummer bei mehreren Kontakten → nur beim haeufigsten behalten. (+4917622973647 war bei 3 verschiedenen Kontakten)

#### Apple Contacts DB — Analyse:
- 23 Signicat-Kontakte mit vertauschten Namen/Emails gefunden (z.B. Peter Kleman → simonas.vysniunas@signicat.com)
- 58 weitere Geschaeftskontakte betroffen
- Report: `reports/apple_contacts_mismatches_20260408.md`

#### Validierung: 20/20 Kontakte korrekt (Stichprobe)

### WhatsApp Integration – 2-Phasen-Architektur

#### Phase 1a: Direkter SQLite-Import (scripts/whatsapp_db_import.py) ★ EMPFOHLEN
- Liest direkt aus WhatsApp Mac App SQLite-DB (ChatStorage.sqlite) – kein manueller Export noetig
- Importiert alle Chats automatisch mit einem Befehl
- CLI: `python3 whatsapp_db_import.py --agent privat` (alle Chats) oder `--contact "Name"` (einzeln)
- Optionen: --min-messages, --since, --list (nur auflisten)
- Sender-Erkennung: ZPUSHNAME mit Fallback auf Chatname (Direktchats) bzw. JID (Gruppen)
- Erkennt Medientypen (Bild, Video, Sprachnachricht, Sticker, Dokument, etc.)
- Filtert archivierte Gruppen (ZMESSAGECOUNTER=3003 Artefakt) automatisch aus
- Read-only Zugriff (Kopie der DB wird verwendet)
- Triggert automatisch Such-Index-Rebuild

#### FIX: Slash-Dropdown zeigt alle Commands + Gemini Bildgenerierung repariert
- Slash-Command Dropdown max-height von 120px auf 400px erhoeht (zeigte nur 3 Items)
- Gemini Bildgenerierung: korrektes Modell gemini-2.5-flash-image (vorher: nicht-existierendes Modell)
- Fallback-Modelle: gemini-3.1-flash-image-preview, gemini-3-pro-image-preview
- E2E-Test: Bild erfolgreich generiert via Gemini
- Veo 2 Videogenerierung: funktioniert (Operation wird gestartet)

#### Such-Limit 500 + erweiterte Slash-Commands
- Suchergebnisse: max_results von 50 auf 500 erhoeht (Anzeige 500, Selektion bleibt max 50)
- Neue Slash-Commands: /find-whatsapp, /find-slack, /find-salesforce
- Regex und knownTypes fuer /find-TYPE erweitert (9 Typen total)
- Type-Aliases: slack->webclip_slack, salesforce->webclip_salesforce (Backend-Mapping)
- typeLabels um WhatsApp, Slack, Salesforce erweitert

#### CRITICAL FIX: Duplikat-Filterung im Index
- macOS-Duplikate (_2.txt, _2 2.txt, _2 3.txt) werden beim Indexing uebersprungen
- Vorher: 4.715 Dateien (2.389 Duplikate = 51%!), Suche lieferte 17 unique von 50 Treffern
- Nachher: 2.149 Dateien (alle unique), 50 Treffer = 50 einzigartige Ergebnisse

#### CRITICAL FIX: E-Mail-Erkennung (search_engine.py)
- detect_source_type erkennt jetzt DATUM_IN/OUT_absender Format (email_watcher)
- Vorher: 225 E-Mails erkannt, 3000+ als 'file' fehlklassifiziert
- Nachher: 3.250 E-Mails korrekt erkannt mit from/to/subject Feldern
- Notification-Penalty (-15 Score) damit echte E-Mails vor Notifications ranken
- Email-Header-Matching prueft jetzt source_type statt nur type-Feld

#### QueryParser: force_search Modus
- Neuer Parameter force_search=True fuer /find und Such-Dialog
- Bei force_search: alle Woerter werden als Keywords UND Person-Names behandelt
- Loest das Problem dass "arne vidar" ohne Aktionswort keine Keywords erzeugte
- web_server.py: /search_preview nutzt jetzt force_search=True

#### Fuzzy Search (search_engine.py)
- Levenshtein-Distanz fuer Personennamen (Tippfehler: Nayara→Naiara, Marco→Marcio)
- Prefix-Matching fuer Keywords ab 3 Zeichen (Simona findet Simonas)
- Bigram-Overlap fuer laengere Woerter ab 5 Zeichen (Renate findet Renata)
- Fuzzy in: Dateinamen, E-Mail-Feldern (von/an/betreff), Preview, und Full-Text-Suche
- Threshold: 75% Aehnlichkeit fuer Edit-Distance, 40% fuer Bigram-Overlap
- Kurze Woerter (<3 Zeichen) werden nicht fuzzy gematcht (keine False Positives)

#### Unit Tests: 24 neue Tests (181 total)
- WhatsApp: Filter-Button, Subtypes, Sublabels, Parents im HTML
- WhatsApp: SOURCE_TAXONOMY, detect_source_type fuer direct/group
- WhatsApp: Parser DE-Format, Timestamp, Media-Erkennung
- WhatsApp: /whatsapp/sync Route
- Such-Dialog: Limit 50 (Counter, Button, Checkbox)
- Such-Dialog: Trefferanzahl, Toggle-Button, Escape-Handler
- Backend: /load_selected_files akzeptiert 6+ Pfade
- Provider: kein stiller Fallback

#### Globale Spiegelung (Downloads shared/whatsapp/)
- WhatsApp DB Import: spiegelt Dateien nach Downloads shared/whatsapp/[agent]_[datei].txt
- WhatsApp Sync-Route: spiegelt automatisch nach Downloads shared/whatsapp/
- Konsistent mit bestehender Webclip-Spiegelung in Downloads shared/webclips/

#### SearchIndex: Unterordner-Support (search_engine.py)
- _get_all_indexable_files() scannt jetzt auch Unterordner von memory/ (z.B. whatsapp/)
- _resolve_file_path() unterstuetzt relative Pfade mit Unterordnern
- detect_source_type() wird mit basename aufgerufen fuer korrekte Typ-Erkennung
- 56 WhatsApp-Dateien erfolgreich indexiert und durchsuchbar

#### Phase 1b: Nativer Export-Parser (scripts/whatsapp_import.py)
- Liest WhatsApp-native ZIP-Exports (_chat.txt Format)
- Parser mit Regex fuer DE/EN Datumsformat, Multiline-Support, Media-Erkennung
- Speichert in [agent]/memory/whatsapp/whatsapp_chat_[kontakt]_[datum].txt
- CLI: `python3 whatsapp_import.py --zip ... --agent ...` oder `--folder ...`
- Triggert Such-Index-Update nach Import
- Metadata-Tracking via whatsapp_metadata.json

#### Phase 2: Chrome Extension (chrome_extensions/whatsapp_watcher/)
- MutationObserver auf WhatsApp Web fuer neue Nachrichten
- Stabile ARIA/data-testid Selektoren (nicht CSS-Klassen)
- Popup mit Agent-Auswahl, Status, Sync-Button, Pause
- Background Worker mit 60s Alarm-Check
- Rate-Limit: max 50 Nachrichten pro 5s-Batch

#### Phase 2: Backend-Route /whatsapp/sync (web_clipper_server.py)
- POST /whatsapp/sync: Empfaengt Nachrichten-Batches von Extension
- Appended zu Tagesdatei oder erstellt neue
- Agent-Validierung, Metadata-Update, Duplikat-Filterung

#### SOURCE_TAXONOMY Integration (search_engine.py)
- Neue Kategorie 'whatsapp' mit Subcategories 'whatsapp_direct' + 'whatsapp_group'
- detect_source_type() erkennt whatsapp_chat_*.txt Dateien
- TOP_CATEGORIES erweitert fuer Such-Gruppierung
- Keywords: whatsapp, wa nachricht, wa chat, whatsapp gruppe, etc.

#### Such-Dialog (web_server.py)
- Neuer Filter-Button "WhatsApp" im Such-Dialog
- Subfilter: Direktnachricht / Gruppenchat
- _SOURCE_SUBTYPES, _SOURCE_SUBLABELS, _SOURCE_PARENTS erweitert

---

### REFERENZ: /find und /find_global — Suchbereiche

**`/find [query]` — Lokale Suche (nur eigener Agent)**

| Durchsucht | Pfad |
|-----------|------|
| Agent Memory | `claude_datalake/[agent]/memory/` (inkl. Unterordner wie whatsapp/) |
| Konversationen | `claude_datalake/[agent]/konversation_*.txt` |

**`/find_global [query]` — Globale Suche (alle Agenten + Shared)**

| Durchsucht | Pfad |
|-----------|------|
| Alle Agent Memories | `claude_datalake/*/memory/` (signicat, privat, trustedcarrier, etc.) |
| Email Inbox (global) | `claude_datalake/email_inbox/` (20.897 E-Mails) |
| Claude Outputs | `claude_datalake/claude_outputs/` |
| Downloads shared (komplett) | `~/...Downloads shared/` (Dokumente, Webclips, WhatsApp, etc.) |

**`/find-TYPE` — Typisierte Suche (lokal, gefiltert nach Datenquelle)**

| Command | Sucht in | SOURCE_TAXONOMY Key |
|---------|----------|---------------------|
| `/find-email` | E-Mails | email + notification |
| `/find-whatsapp` | WhatsApp Chats | whatsapp + whatsapp_direct + whatsapp_group |
| `/find-webclip` | Alle Web Clips | webclip + webclip_salesforce + webclip_slack + webclip_linkedin + webclip_general |
| `/find-slack` | Nur Slack | webclip_slack |
| `/find-salesforce` | Nur Salesforce | webclip_salesforce |
| `/find-document` | Dokumente | document + document_word + document_excel + document_pdf + document_pptx |
| `/find-conversation` | Konversationen | conversation |
| `/find-screenshot` | Screenshots | screenshot |

Alle `/find-TYPE` Commands existieren auch als `/find_global-TYPE` fuer globale typisierte Suche.

---

### REFERENZ: Memory-Pfade und Agent-Zugriff

**Basispfad:** `~/Library/Mobile Documents/com~apple~CloudDocs/Downloads shared/claude_datalake/`

| Agent | Subagents | Memory-Pfad | Dateien | Groesse |
|-------|-----------|-------------|---------|---------|
| signicat | outbound, lamp, meddpicc, powerpoint | signicat/memory/ | ~2.149 (dedupliziert) | 890 MB |
| privat | – | privat/memory/ + privat/memory/whatsapp/ | ~22.249 | 2,4 GB |
| trustedcarrier | – | trustedcarrier/memory/ | 604 | 251 MB |
| system ward | – | system ward/memory/ | 38 | 23 MB |

Subagents teilen das Memory des Parent-Agents (kein eigener Ordner).

**Globale Speicherorte (Read-only via /find_global):**

| Pfad | Inhalt |
|------|--------|
| claude_datalake/email_inbox/ | 20.897 E-Mails (alle Accounts) |
| Downloads shared/webclips/ | Gespiegelte Web Clips |
| Downloads shared/whatsapp/ | Gespiegelte WhatsApp Chats |

**Zugriffs-Matrix:**

| Memory-Bereich | Eigener Agent | Andere Agents | /find_global |
|---------------|:---:|:---:|:---:|
| Eigenes memory/ | RW | – | R |
| email_inbox/ (global) | R | R | R |
| Downloads shared/ | – | – | R |

---

### REFERENZ: LLM-Provider und Modelle

Konfiguration: `config/models.json`

| Provider | Modell-ID | Anzeigename | Chat | Bild | Video | Status |
|----------|-----------|-------------|:----:|:----:|:-----:|--------|
| **Anthropic** | claude-sonnet-4-6 | Claude Sonnet 4.6 | ✓ | – | – | ✓ OK |
| | claude-opus-4-6 | Claude Opus 4.6 | ✓ | – | – | (nicht getestet, teuer) |
| | claude-haiku-4-5-20251001 | Claude Haiku 4.5 | ✓ | – | – | (nicht getestet) |
| **OpenAI** | gpt-4o | GPT-4o | ✓ | – | – | ✗ Quota ueberschritten |
| | gpt-4o-mini | GPT-4o Mini | ✓ | – | – | (Quota) |
| | o1 | o1 | ✓ | – | – | (Quota) |
| | gpt-image-1 | (Bildgenerierung) | – | ✓ | – | (Quota) |
| **Gemini** | gemini-2.5-flash | Gemini 2.5 Flash | ✓ | – | – | ✓ OK |
| | gemini-2.5-pro | Gemini 2.5 Pro | ✓ | – | – | (nicht getestet) |
| | gemini-2.0-flash-lite | Gemini 2.0 Flash Lite | ✓ | – | – | (nicht getestet) |
| | gemini-2.0-flash-preview-image-generation | (Bildgenerierung) | – | ✓ | – | (gemini-2.5-flash als Fallback) |
| | veo-2.0-generate-001 | (Videogenerierung) | – | – | ✓ | (nicht getestet) |
| **Perplexity** | sonar | Sonar | ✓ | – | – | ✓ OK |
| | sonar-pro | Sonar Pro | ✓ | – | – | (nicht getestet) |
| | sonar-reasoning | Sonar Reasoning | ✓ | – | – | (nicht getestet) |
| | sonar-reasoning-pro | Sonar Reasoning Pro | ✓ | – | – | (nicht getestet) |
| | sonar-deep-research | Sonar Deep Research | ✓ | – | – | (nicht getestet) |
| **Mistral** | mistral-large-latest | Mistral Large | ✓ | – | – | ✓ OK |
| | mistral-small-latest | Mistral Small | ✓ | – | – | (nicht getestet) |
| | mistral-nemo | Mistral Nemo | ✓ | – | – | (nicht getestet) |

**Bildgenerierung:** Nur Gemini und OpenAI (OpenAI aktuell Quota-Problem)
**Videogenerierung:** Nur Gemini (Veo 2)
**Kein stiller Fallback:** Bei nicht-unterstuetztem Provider kommt klare Fehlermeldung

**OpenAI Quota-Problem:** API-Key hat Billing-Limit erreicht. Moritz muss auf platform.openai.com Billing pruefen.

---

### Such-Dialog UX-Verbesserungen
- Trefferanzahl wird oben im Such-Dialog angezeigt ("X Dateien gefunden") als prominenter Header
- Datei-Limit von 5 auf 50 erhoeht (7 Stellen: Checkbox-Limit, Counter-Label, JS-Counter, loadAllResults, loadSelectedResults, Alle-laden-Button, Backend /load_selected_files)
- "Alle markieren / Alle abwaehlen"-Toggle im Such-Dialog (ueberspringt Notifikationen, max 50)
- Escape-Taste schliesst Such-Dialog (sendet Prompt ohne Dateien, Listener wird sauber entfernt)
- Alle 157 Tests bestanden
- Python-Skript: scripts/fix_search_dialog_ux_v2.py

### Strikte Provider-Auswahl – kein stiller Fallback
- Provider-Auswahl wird jetzt korrekt durchgereicht (Perplexity -> Perplexity, etc.)
- Kein automatischer Fallback auf Anthropic mehr wenn anderer Provider gewaehlt
- Bildgenerierung: nutzt jetzt gewaehlten Provider, kein heimlicher Wechsel
- Gemini Bildgenerierung: korrektes Modell (gemini-2.0-flash-preview-image-generation)
- Klare Fehlermeldungen wenn Provider Bild/Video nicht unterstuetzt
- Python-Skript: scripts/fix_provider_fallback.py

### Memory-Beschreibungsblock in Agent System Prompts
- Standardisierten Block "DEIN GEDAECHTNIS & DATEIZUGRIFF" in alle Parent-Agent Prompts eingefuegt
- Beschreibt Dateitypen (E-Mail, Web Clip, Dokument, Konversation, Screenshot, Kontakte)
- Erklaert wie Suche funktioniert (\find, /search, natuerliche Sprache, global)
- Betroffene Agenten: signicat.txt, privat.txt, trustedcarrier.txt
- Sub-Agents (signicat_outbound, signicat_powerpoint, signicat_lamp, signicat_meddpicc) und system ward uebersprungen
- Python-Skript: scripts/add_memory_block.py (wiederverwendbar fuer neue Agenten)

### Strikte Provider-Auswahl – kein stiller Fallback
- generate_image(): Fallback-Kette entfernt – nutzt jetzt ausschliesslich den gewaehlten Provider
- Bildgenerierung mit nicht-unterstuetztem Provider gibt klare Fehlermeldung statt stillem Wechsel
- CREATE_IMAGE Handler: Provider wird direkt aus Session durchgereicht (Default korrigiert: 'openai' -> 'anthropic')
- Gemini Bildgenerierung: Modell-Fallback innerhalb Gemini (gemini-2.0-flash-preview-image-generation -> gemini-2.5-flash)
- generate_video(): Stiller Fallback auf Gemini entfernt – klare Fehlermeldung wenn Provider kein Video kann
- CREATE_VIDEO Handler: Provider aus Session wird jetzt durchgereicht (fehlte vorher komplett)
- Alle 157 Tests bestanden
- Python-Skript: scripts/fix_provider_fallback.py

---

## 2026-04-07

### Typed /find Commands: /find-email, /find-document, etc.

- 12 neue Slash-Commands: `/find-email`, `/find-webclip`, `/find-document`, `/find-conversation`, `/find-screenshot` + jeweils `/find_global-*` Varianten
- Autocomplete-Dropdown filtert live beim Tippen: `/find-` zeigt nur die 5 Typ-Commands
- Tab-Vervollstaendigung: `/find-e` + Tab → `/find-email `
- Alte Syntax weiterhin unterstuetzt: `/find email query` und `/find document query`
- `sendMessage()`: neue Regex `/find(_global)?(?:-(email|webclip|...))?` parst beide Formate
- Live-Search und Find-Chips funktionieren mit allen Command-Varianten
- 6 neue Unit Tests, Testsuite 151 → 157

**Datei:** `src/web_server.py` (via `scripts/add_typed_find_commands.py`)

### Bugfix: Search Dialog Checkbox-Default + Volltext-Pfad-Aufloesung

**Checkbox-Default:**
- Suchergebnisse werden nicht mehr automatisch vorausgewaehlt (vorher: erste 5 Nicht-Notifikationen checked)
- User muss manuell auswaehlen oder "Alle laden" klicken
- Counter zeigt "X ausgewaehlt (max 5)" statt "X / 5 ausgewaehlt"

**HybridSearch Pfad-Aufloesung:**
- Step 3 + Step 4 in HybridSearch.search() nutzten nur `memory/` Pfad — Konversationen im Agent-Root wurden nicht gelesen
- Fix: `entry.get('path')` aus Index nutzen, Fallback auf Agent-Root
- Ergebnis: "change" liefert jetzt 11 statt 2 Treffer fuer System Ward

**Unit Tests:**
- 35+ neue Tests in `tests/run_tests.py` Sektion "Features 2026-04-07"
- Testet: Markdown (marked.js, renderMarkdown), Layout (900px, 72%), Shortcuts (Alt+keys), Find-Chips, Live-Search, Sidebar-Default, File-AC entfernt, Checkbox-Default, search_engine Funktionen (get_recent_files, extract_search_keywords), Backend-Routen (/search_preview type, recent), Web Clipper (legacy + JSON)

**Dateien:** `src/web_server.py`, `src/search_engine.py`, `tests/run_tests.py`

### UX-Verbesserungen Chat-Interface (6 Aenderungen)

**1. System-Prompt Panel: Default eingeblendet**
- Sidebar startet mit `width:30%; min-width:280px` (vorher 0)
- `sidebarOpen = true` als Default
- Toggle mit Alt+P, Button zeigt Shortcut-Label

**2. /find und /find_global: Kategorien-Chips + Echtzeit-Suche**
- Horizontale Chips unter Eingabefeld: E-Mail [1], Web Clip [2], Dokument [3], Konversation [4], Screenshot [5]
- Chips erscheinen sobald `/find` getippt wird, Shortcuts Alt+1 bis Alt+5
- Echtzeit-Suche nach 300ms Debounce: Treffer als Dropdown (max 8), Pfeiltasten navigierbar
- Bestehendes vertikales Type-Dropdown wird durch Chips ersetzt

**3. "Datei aus Memory suchen"-Feld entfernt**
- `#file-ac-wrap` mit Input + Dropdown komplett entfernt
- Funktionalitaet durch /find Echtzeit-Suche ersetzt

**4. Leere Suche → Letzte Dateien**
- `/find` + Enter: zeigt je 3 neueste Dateien pro Kategorie
- `/find email` + Enter: zeigt 10 neueste E-Mails
- Neue Backend-Funktion `get_recent_files()` in search_engine.py
- `/search_preview` Route: `recent=true` Parameter fuer leere Queries

**5. Volltext-Suche**
- Bereits implementiert (max 50 Treffer), keine Aenderung noetig

**6. Keyboard-Shortcuts fuer alle UI-Elemente**
- Zentraler `document.addEventListener('keydown')` Handler
- Alt+P (Prompt), Alt+N (Neu), Alt+A (Agent), Alt+M (Modell), Alt+F (/find), Alt+U (Upload), Alt+C (Kopieren), Alt+S (Speichern), Ctrl+Enter (Senden)
- Alt+1-5 fuer Kategorie-Chips (nur wenn sichtbar)
- Sichtbare `[X]` Labels an allen Buttons (CSS `.shortcut-label`)

**Dateien:** `src/web_server.py` (via `scripts/ux_improvements.py`, 17 Aenderungen), `src/search_engine.py` (`get_recent_files()`)
**Backup:** `backups/2026-04-07_15-05-07/`
**Tests:** 121/121 bestanden

### Bugfix: Such-System — Typ-Filter, Konversations-Indexierung, MEMORY_SEARCH

**Bug A — Typ-Filter lieferte 0 Ergebnisse bei `/find document price`:**
- Root Cause: `QueryParser.parse()` setzte `is_search=False` und `keywords=[]` fuer kurze Queries ohne Aktionswoerter ("finde", "suche")
- Der Backend-Code forcierte `is_search=True` und befuellte `keywords` korrekt, aber der Fix war im letzten Deployment nicht aktiv gewesen (alter Server-Prozess)
- Verifiziert: Nach Neustart funktioniert Typ-Filter korrekt (2 Dokument-Ergebnisse fuer "price")

**Bug B — Konversationen nicht indexiert (55 Dateien fehlten):**
- Root Cause: `SearchIndex.build_index()` und `update_index()` scannten nur `memory/` Unterordner
- `konversation_*.txt` Dateien liegen aber im Agent-Root-Ordner (z.B. `signicat/konversation_2026-04-07.txt`)
- Fix: Neue Hilfsmethoden `_get_all_indexable_files()` und `_resolve_file_path()` in SearchIndex
- `_get_all_indexable_files()` sammelt Dateien aus `memory/` UND `konversation_*.txt` aus dem Root
- `_resolve_file_path()` loest Dateipfade auf (memory/ zuerst, dann Root)
- `_index_file()`, `build_index()`, `update_index()` nutzen jetzt diese Methoden
- Re-Indexierung: signicat +93 Konversationen, privat +61, trustedcarrier +35, system ward +55

**Bug C — MEMORY_SEARCH nicht verarbeitet:**
- MEMORY_SEARCH Code in web_server.py ist funktional korrekt
- Problem war indirekt: `deep_memory_search()` suchte nur in `memory/`, Konversationen im Root fehlten
- Durch Bug B Fix werden Konversationen jetzt gefunden, MEMORY_SEARCH liefert Ergebnisse

**Dateien:** `src/search_engine.py` (3 neue Methoden, 3 angepasste Methoden)
**Backup:** `backups/2026-04-07_13-53-00/`
**Tests:** 121/121 bestanden
**Re-Indexierung:** Alle 4 Agenten neu indexiert (signicat 4646, privat 22310, trustedcarrier 635, system ward 88)

### Intelligentes Such-Menue mit Typ-Filterung und NLP-Keyword-Extraktion

**Frontend (web_server.py):**
- Neues Typ-Dropdown nach `/find ` Eingabe: 7 Kategorien (E-Mail, Web Clip, Screenshot, Kontakt, Dokument, Konversation, Alles)
- Pfeiltasten-Navigation + Shortcut-Tasten (E/W/S/K/D/G/A) im Dropdown
- Zweistufiger Flow: `/` zeigt Slash-Commands → `/find ` zeigt Typ-Auswahl → `/find email query` sucht
- Typ wird an Backend als `type` Parameter mitgesendet
- neuer `onInputHandler()` steuert wann welches Dropdown erscheint

**Backend (web_server.py + search_engine.py):**
- `/search_preview` + `/global_search_preview`: neuer optionaler `type` Parameter
- NLP-Keyword-Extraktion bei Freitext > 5 Woerter: Stopword-Filter (DE+EN), max 6 Keywords
- Contact-Suche (`type=contact`): Spezialbehandlung, durchsucht contacts.json nach Name/E-Mail/Firma/Titel
- `HybridSearch.search()`: neuer `forced_type` Parameter fuer explizite Typ-Filterung
- Sortierung verbessert: single sort mit from_person > score > date Tiebreaker
- `extract_search_keywords()` neue Funktion in search_engine.py
- `search_contacts()` neue Funktion in search_engine.py

**Dateien:** `src/web_server.py` (via `scripts/add_search_types.py`), `src/search_engine.py`
**Backup:** `backups/2026-04-07_10-02-26/`
**Tests:** 121/121 bestanden

### Chat UI — Markdown Rendering + Layout Fix

**Markdown Rendering (marked.js):**
- `marked.js` CDN eingebunden (vor `</head>`)
- Neue `renderMarkdown()` Funktion: nutzt `marked.parse()` mit GFM + breaks, Fallback auf `renderCodeBlocks()`
- `renderMessageContent()` angepasst: normaler Text wird durch Markdown gerendert, `<output>` Block weiterhin als Code
- Nur AI-Antworten (`.bubble.markdown-rendered`) erhalten Markdown-Rendering, User-Nachrichten bleiben plain text
- Links bekommen `target="_blank" rel="noopener"` fuer neuen Tab
- CSS fuer Markdown-Elemente: Headings H1-H4, Listen, Links, Code (inline + Block), Tabellen, Blockquotes, HR, Images
- Code-Bloecke in Markdown: `<pre><code>` mit dunklem Hintergrund (#0d0d0d), Border, Rundung

**Chat-Bubble Layout:**
- `#messages` Container: `max-width:900px; margin:0 auto` — zentriert im Fenster
- `.msg` max-width von 820px auf 72% geaendert — Bubbles nehmen max 72% der Containerbreite ein
- Bubble-Padding: 10px vertikal, 16px horizontal
- Vertikaler Abstand zwischen Bubbles: 12px (gap im Flexbox)
- iMessage/WhatsApp-aehnliches Layout: User rechts, AI links, nicht am aeussersten Rand klebend

**Datei:** `src/web_server.py` (via Python-Skript `scripts/add_markdown_and_layout.py`)
**Backup:** `backups/2026-04-07_07-50-07/src/web_server.py`
**Tests:** 121/121 bestanden

### Web Clipper v2 — Full Extraction + Full-Page Screenshot

**Chrome Extension (v2.0):**
- Komplett neues `content_script.js`: strukturierte JSON-Extraktion statt flachem Text
- `extractPageMetadata()`: Meta-Tags, Headings H1-H6, Links, Images, Tables, Forms, Timestamps fuer alle Seiten
- `queryShadowAll()`: Shadow DOM Traversal fuer Salesforce Lightning Web Components
- Salesforce: Record-Felder, Related Lists, Activity Timeline, Chatter Feed, Record-ID
- Slack: Channel-Name/Topic, Messages mit Autor/Timestamp/Reactions, Thread-Replies
- Neu: LinkedIn-Extraktion (Profile + Posts) mit Name, Headline, Experience
- Web (Default): Strukturierte Sections (article/main/section/aside)
- Neues `background.js`: Full-Page Screenshot via `chrome.debugger` API (Page.captureScreenshot mit captureBeyondViewport), Fallback auf captureVisibleTab
- Lazy-Load Trigger vor Screenshot (scrollt Seite durch), max 15000px Hoehe
- `manifest.json`: `"debugger"` Permission hinzugefuegt, Version 2.0
- Popup-UI: Status-Anzeige waehrend Screenshot, Screenshot-Info im Toast

**Backend (web_clipper_server.py):**
- Neues Speicherformat: JSON (strukturierte Daten) + PNG (Screenshot) statt TXT
- Backward-kompatibel: erkennt altes Format (content String) vs. neues (extracted_data)
- Dual Save beibehalten: Agent Memory + globale webclips/
- Dateinamen-Sanitization, MAX_CONTENT_LENGTH 50MB fuer Screenshots
- `import json, base64` ergaenzt

**Search Engine (search_engine.py):**
- SOURCE_TAXONOMY: `.json` Varianten zu allen webclip-Patterns hinzugefuegt
- Neue Subkategorie `webclip_linkedin` mit Patterns und Keywords
- `detect_source_type()`: LinkedIn-Prefix erkennt
- `_extract_text_from_file()`: JSON-Webclips extrahieren `full_text` + `title` statt raw JSON

**web_server.py (deep_memory_search):**
- Extension-Filter erweitert um `.json` (via Python-Skript `scripts/fix_deep_search.py`)
- JSON-Webclips: `full_text` Feld fuer Keyword-Matching statt raw JSON Scan

**Tests:** 121/121 bestanden. Backend getestet: altes TXT-Format, neues JSON-Format, JSON+PNG mit Screenshot.

**Betroffene Dateien:**
- `chrome_extension/assistant_clipper/content_script.js` (komplett neu)
- `chrome_extension/assistant_clipper/background.js` (komplett neu)
- `chrome_extension/assistant_clipper/manifest.json` (v2.0, debugger Permission)
- `src/web_clipper_server.py`
- `src/search_engine.py`
- `src/web_server.py` (deep_memory_search)
- Backups: `backups/2026-04-07_07-26-30/`

### Bugfix: Bild-Generierung Provider-Fallback + Agent-Feedback

**Problem 1 — Gemini Imagen Modellname:**
- Alter Name `imagen-3.0-generate-002` war bereits in vorheriger Session korrigiert zu `gemini-2.5-flash-image`
- Agent-Prompt-Referenz "Imagen 3" durch "gemini-2.5-flash-image" ersetzt in allen Agent-Dateien

**Problem 2 — Provider-Fallback + Feedback:**
- `generate_image()` aufgeteilt in `_generate_image_single()` (ein Provider) und `generate_image()` (mit Fallback)
- Automatischer Provider-Fallback: wenn erster Provider fehlschlaegt (z.B. OpenAI Billing-Limit), wird naechster versucht
- Provider-Reihenfolge: Gemini (primaer) → OpenAI (Fallback)
- Erfolgs-Nachricht im Chat: `*Bild erfolgreich generiert: [datei]. Das Bild wird unten angezeigt.*`
- Fehler-Nachricht: `*Bild-Generierung fehlgeschlagen: [fehler]. Du kannst es erneut versuchen.*`
- Gleiche Verbesserung fuer Video-Nachrichten
- Fallback-Info wird transparent angezeigt: "(Fallback von openai auf gemini)"

**Problem 3 — Agent System Prompts:**
- Alle 8 Agent-Dateien: Bild/Video-Block von "BILD-GENERIERUNG" zu "BILD- UND VIDEOGENERIERUNG" umbenannt
- Neue Anweisung: "Du sagst NIEMALS ich kann keine Bilder/Videos erstellen. Du HAST diese Faehigkeit."
- Provider-Namen aktualisiert: "Imagen 3" → "gemini-2.5-flash-image"
- system ward.txt: SYSTEM-FÄHIGKEITEN um Provider-Fallback und "niemals verneinen" ergaenzt

**Betroffene Dateien:**
- `src/web_server.py` (via Python-Skript `scripts/fix_image_gen.py`)
- Alle 8 Agent .txt Dateien (via Python-Skript `scripts/fix_agent_prompts.py` + manuell system ward.txt)
- Backup: `backups/2026-04-07_06-39-59/src/web_server.py`
- Tests: 121/121 bestanden

---

## 2026-04-06

### Bild- & Video-Generierung fuer alle Agenten

**Backend (web_server.py):**
- Neuer Trigger `CREATE_IMAGE: [beschreibung]` in LLM-Antworten — generiert Bild via API
- Neuer Trigger `CREATE_VIDEO: [beschreibung]` — generiert Video via Gemini Veo 2 (async polling)
- Image-Provider: Gemini (`gemini-2.5-flash-image` via generateContent) und OpenAI (`gpt-image-1`)
- Video-Provider: Gemini (`veo-2.0-generate-001` via predictLongRunning)
- Automatischer Provider-Fallback: wenn aktiver Provider keine Bilder unterstuetzt, wird auf verfuegbaren Image-Provider ausgewichen
- Bilder gespeichert als PNG, Videos als MP4 in `claude_outputs/` mit Dateiname `[agent]_image/video_[timestamp].[ext]`
- Frontend: Inline-Bildanzeige (max 600px) mit Download-Button, Video-Player mit Download-Button
- Response-Format erweitert um `created_images` und `created_videos` Arrays

**models.json:**
- OpenAI: `image_model: gpt-image-1` hinzugefuegt
- Gemini: `image_model: gemini-2.5-flash-image`, `video_model: veo-2.0-generate-001` hinzugefuegt
- Hinweis: OpenAI Billing Limit aktiv — Bilder werden aktuell ueber Gemini generiert

**Agent System Prompts:**
- Alle 8 Agent-Dateien um BILD-GENERIERUNG und VIDEO-GENERIERUNG im Faehigkeiten-Block ergaenzt
- system ward.txt: SYSTEM-FÄHIGKEITEN Abschnitt um Bild/Video-Details erweitert

### Standardisierter Capabilities Block in allen Agent System Prompts

- Neuer `--- FÄHIGKEITEN ---` Block am Ende aller 8 Agent-Dateien eingefuegt
- Dokumentiert: Datei-Erstellung (Word/Excel/PDF/PPTX/E-Mail), Memory & Suche (lokal + global + contacts.json), E-Mail Integration, Web Clipping, Datei-Kontext (Vision)
- Agentname im Dateinamen-Beispiel passt zum jeweiligen Agent/Sub-Agent
- Sub-Agents (lamp, meddpicc, outbound, powerpoint) mit Hinweis auf geteiltes Signicat Parent-Memory
- Block steht vor GEDÄCHTNIS-Abschnitt (signicat.txt, system ward.txt) bzw. am Dateiende (alle anderen)
- Betroffene Dateien: privat.txt, signicat.txt, signicat_lamp.txt, signicat_meddpicc.txt, signicat_outbound.txt, signicat_powerpoint.txt, system ward.txt, trustedcarrier.txt
- analyze_contacts.py nach ~/AssistantDev/scripts/ kopiert (Pfad in allen Prompts: ~/AssistantDev/scripts/analyze_contacts.py)

### Kontakt-Analyse System

**analyze_contacts.py (neu):**
- Einmaliges/retroaktives Analyse-Skript: liest alle E-Mail-Dateien im Agent-Memory ein
- Konfigurierbarer Zeitraum per `--months N` (Default: 3 Monate), Agent per `--agent`
- Extrahiert pro Kontakt: Name, E-Mail, Firma (aus Domain), Titel, Telefon (aus Signatur), Kontakthaeufigkeit (gesamt/gesendet/empfangen), erstes/letztes Kontaktdatum
- Eigene E-Mail-Adressen werden ignoriert
- Zwei Outputs: `contacts.json` (maschinenlesbar, ins Agent-Memory) + `contact_report_DATUM.md` (menschenlesbar, nach Firma gruppiert, nach `claude_outputs/`)
- Erster Lauf: 105 Kontakte aus 1846 E-Mails (3 Monate), 2996 E-Mail-Dateien total
- Datei: `~/analyze_contacts.py`

**email_watcher.py — Automatisches Kontakt-Tracking:**
- Bei jeder verarbeiteten E-Mail wird `contacts.json` im Agent-Memory aktualisiert
- Absender (Name, E-Mail, Firma aus Domain) wird eingetragen, Kontaktzaehler hochgezaehlt
- Titel und Telefon aus Signatur extrahiert (wenn noch nicht vorhanden)
- Kompatibles Format mit analyze_contacts.py
- Datei: `src/email_watcher.py`

**Signicat Agent System Prompt:**
- Neuer Abschnitt "KONTAKTDATENBANK" beschreibt die contacts.json und moegliche Abfragen
- Agent kann Fragen zu Kontakten, Haeufigkeit, Firmen beantworten
- Datei: `config/agents/signicat.txt`

### Bugfix: Section Copy Buttons JS-Escaping + Neue Tests

- **Bugfix**: `addSectionCopyButtons` verwendete `'\n'` statt `'\\n'` im Python HTML-Template, was zu einem JavaScript-Syntaxfehler fuehrte, der den gesamten `<script>`-Block blockierte. Folge: Agent-Modal oeffnete nicht, keine JS-Funktion funktionierte.
- Fix: `split('\n')` und `join('\n')` durch `split('\\n')` und `join('\\n')` ersetzt (3 Stellen)
- 15 neue Unit-Tests in `tests/run_tests.py` (Sektion "Features 2026-04-06"):
  - Section-Copy-Button CSS + JS im HTML
  - Per-Konversation Modell-State (provider/model_id in load_conversation)
  - GET /api/memory-files-search Endpoint + Minimum-Length-Check
  - search_engine: update_all_indexes() + index_single_file() existieren
  - /find Command ueber POST /chat
  - Slash-Commands /find + /find_global im HTML
  - Alte Trigger (detectSearchIntent, detectGlobalTrigger) entfernt
- Testsuite: 106 → 121 Tests

### Section Copy Buttons in AI-Antworten

- Neue "↓ Kopieren"-Buttons an jeder `##`-Ueberschrift in AI-Antworten
- Klick kopiert alles ab dieser Ueberschrift bis zum Ende der Nachricht (plain text)
- Bestehender "Kopieren"/"Alles"-Button bleibt unveraendert
- Buttons nur sichtbar bei Antworten mit `##`-Abschnitten, kurze Antworten ohne `##` bleiben unberuehrt
- Unauffaelliges Design: klein, transparent, wird bei Hover hervorgehoben (#f0c060)
- Code-Bloecke werden korrekt uebersprungen (keine falschen `##` in Code)
- Datei: `src/web_server.py` (CSS + JS addSectionCopyButtons)

### Per-Konversation Modell-State + /find Commands

**Per-Konversation Modell-State:**
- Backend `load_conversation` parst `[provider/model_id]` aus Konversationsdatei
- Beim Laden einer Konversation wird der Provider+Model-Selector automatisch auf den gespeicherten Stand gesetzt
- Session-State wird aktualisiert: `state['provider']` und `state['model_id']`

**Explizite /find und /find_global Commands:**
- Alle Keyword-Trigger fuer die Suche entfernt (frontend + backend)
- Entfernt: `detectSearchIntent()`, `_SEARCH_ACTIONS_JS/PHRASES/OBJECTS`, `_GLOBAL_TRIGGERS_JS`, `detectGlobalTrigger()`
- Entfernt: Backend `_SEARCH_ACTIONS`, `_SEARCH_PHRASES`, `_SEARCH_OBJECTS` Dicts
- Entfernt: Deep-Search Fallback `search_triggers` Liste
- Suche laeuft jetzt nur noch durch: `/find [query]` (aktueller Agent) oder `/find_global [query]` (alle Agenten)
- Slash-Command Autocomplete: Dropdown erscheint wenn User `/` tippt, mit Pfeiltasten navigierbar
- Commands werden nicht als normale Nachrichten ans AI-Modell gesendet
- Legacy-Trigger "memory folder/ordner" bleibt erhalten fuer Abwaertskompatibilitaet
- `auto_search_memory()` vereinfacht: nur noch Legacy-Trigger aktiv

**Automatische Index-Aktualisierung:**
- Neuer Background-Thread im Web Server: alle 5 Minuten `update_all_indexes()` fuer alle Agenten + globalen Index
- `search_engine.py`: Neue Funktion `update_all_indexes()` — scannt alle Agent-Ordner, fuehrt inkrementelles `update_index()` aus (nur neue/geaenderte Dateien)
- `search_engine.py`: Neue Funktion `index_single_file()` — indexiert einzelne Datei sofort
- `email_watcher.py`: Ruft nach jedem verarbeiteten .eml sofort `index_single_file()` auf — neue E-Mails sind sofort suchbar
- Kein manueller Batch-Rebuild mehr noetig — alle neuen Dateien werden automatisch erfasst
- Alle Agent-Indexe synchron: signicat 4525, privat 22249, trustedcarrier 594, standard 98, system ward 25

### Datei-Autocomplete + Autonomes Memory-Loading + Provider-Fix

**Datei-Autocomplete (Feature 1):**
- URL-Input auf 160px reduziert, neues Suchfeld "Datei aus Memory suchen..." daneben
- Ab 2 Zeichen: Dropdown mit bis zu 8 Treffern aus `.search_index.json`
- Pfeiltasten-Navigation, Enter zum Auswaehlen, Escape zum Schliessen
- Auswahl laedt Datei direkt als Kontext-Chip
- Neue API: `GET /api/memory-files-search?q=...&agent=...`

**Autonomes File-Loading (Feature 2):**
- Deep-Search Fallback wenn auto_search keine Ergebnisse liefert
- Trigger-Woerter: "such", "find", "zeig", "schau", "email", "/search" etc.
- ≤5 Treffer: automatisch laden, User informieren
- 6-15 Treffer: Dateiliste als Hinweis an die AI
- >15 Treffer: User auffordern den Suchbegriff zu praezisieren
- Max 50.000 Zeichen pro Datei

**Gemini Provider Fix (Feature 3):**
- Problem: `google.generativeai` SDK deprecated, `gemini-2.0-flash` fuer neue User gesperrt
- Fix: `call_gemini` komplett auf REST API umgestellt (kein SDK mehr noetig)
- Modelle aktualisiert: `gemini-2.5-flash`, `gemini-2.5-pro`, `gemini-2.0-flash-lite`
- OpenAI: Quota erschoepft (kein Code-Bug, Billing-Problem)
- Anthropic, Mistral, Perplexity: funktionieren einwandfrei

### Email System v2 + Deep Search + Token Manager

**email_watcher.py v2:**
- Neues Dateinamen-Schema: `YYYY-MM-DD_HH-MM-SS_IN/OUT_KONTAKT_BETREFF.txt`
- Richtung (IN/OUT) automatisch via eigene E-Mail-Adressen (aus Apple Mail, gecacht in `~/.emailwatcher_own_addresses.json`)
- Erweiterter Dateiinhalt mit Richtung, Kontakt, Agent, Importiert-Timestamp
- 7 eigene Adressen erkannt (me.com, icloud.com, signicat.com, gmail.com, demoscapital.co, vegatechnology.com.br, trustedcarrier.net)

**sent_mail_exporter.py (neu):**
- Exportiert gesendete Mails aus Apple Mail Sent-Folder via AppleScript
- State in `~/.sent_mail_exporter_state.json` (kein Doppel-Import)
- Gleiche Routing-Logik und Dateinamen-Schema wie email_watcher v2

**rename_existing_emails.py (neu):**
- Benennt alle bestehenden `email_*.txt` und `.eml` Dateien in Memory-Ordnern um
- Liest Von/An/Betreff/Datum aus Header, bestimmt IN/OUT + Kontakt
- Trockenlauf mit `--dry-run`

**Deep Search API (`POST /api/memory/search`):**
- 3-stufig: Dateiname-Filter (Datum, Richtung, Kontakt) -> Inhalt-Scan -> Score-Sortierung
- Filtert nach `date_from`/`date_to`, `direction` (IN/OUT), `contact`
- Agent-seitig: MEMORY_SEARCH-Instruktion im System-Prompt, automatischer Re-Query bei Fund

**Token/Kontext-Manager:**
- `GET /api/context-info`: Token-Schaetzung fuer System-Prompt, Konversation, Memory-Dateien
- UI: Token-Anzeige im Header (klickbar), Dropdown mit geladenen Dateien + Token-Zaehler
- "Slim Mode" Button: entfernt alle Memory-Dateien aus dem Kontext
- Warnung ab 25k Tokens (orange Anzeige)
- `POST /remove_all_ctx`: entfernt alle Kontext-Items auf einmal

### E-Mail Memory Verteilung

### Output-Block Konvention: Kopieren-Button kopiert nur den Output
- `<output>...</output>` Tags in AI-Antworten werden als visueller Block gerendert (gruener Rahmen links, abgehobener Hintergrund)
- Der Tag selbst wird NICHT als Text angezeigt — nur der Inhalt
- Eigener gruener "Kopieren"-Button auf dem Output-Block kopiert nur den Output-Inhalt
- Kleiner "Alles"-Button oben rechts kopiert die gesamte Nachricht (Fallback)
- Ohne `<output>`-Tag: bisheriges Verhalten (gesamter Text)
- `renderMessageContent()` aufgeteilt: `renderCodeBlocks()` (Code-Bloecke) + Output-Block-Parser
- CSS: `.output-block`, `.output-copy-btn` mit Dark-Theme-kompatiblem Gruen
- Alle 8 Agenten-System-Prompts um "OUTPUT-BLOCK KONVENTION" Abschnitt ergaenzt
- Agenten wissen jetzt: E-Mails, Skripte, Prompts etc. in `<output>` wrappen

### Konversations-Sidebar: Sortierung nach Aktivitaet + leere Sessions gefiltert
- **Problem**: Konversationen wurden nach Dateiname (= Erstellungszeitpunkt) sortiert — fortgesetzte Konversationen blieben unten
- **Problem**: Leere Header-Dateien (41 bytes, nur `Agent:` Header) und Sessions ohne User-Nachrichten verstopften die Liste
- **Fix**: `get_history` scannt jetzt direkt die Dateien statt `_index.json`:
  - Sortierung nach `mtime` (letzte Dateiänderung) — fortgesetzte Konversationen rutschen nach oben
  - Dateien <= 50 bytes werden übersprungen (leere Sessions)
  - Dateien ohne `Du: ` Zeile werden übersprungen (keine echten Konversationen)
  - Datum zeigt letzte Aktivitaet statt Erstellungszeitpunkt
- Test Suite um 11 Konversations-Tests erweitert (load, resume, format, disk-check)
- Ergebnis: 34 statt 60 Eintraege fuer signicat (Artefakte gefiltert)

### E-Mail Memory Verteilung
- 20.804 Emails aus `email_inbox/` in Agent-Memory-Ordner kopiert
- Routing nach Empfaenger-Adresse: `@signicat.com` → signicat, `@trustedcarrier.net` → trustedcarrier, Rest → privat
- Ergebnis: signicat +644, trustedcarrier +161, privat +19.999
- Suchindexe aller 3 Agenten neu gebaut (signicat 3.565, trustedcarrier 1.107, privat 23.578 Eintraege)
- Globaler Suchindex wird im Hintergrund aktualisiert
- Backup: `memory_backup_20260406_111727`

### Konversations-Navigation & Autosave Fix
- **Problem 1**: Zuruecknavigieren zu alter Konversation war read-only — neue Nachrichten landeten in der aktuellen Datei statt in der angezeigten
- **Problem 2**: Redundanter Dual-Write (Append + Overwrite) bei jeder Nachricht
- **Root Cause**: `load_conversation` hat `state['dateiname']` und `state['verlauf']` nicht aktualisiert — war nur eine Anzeigefunktion
- **Fix Backend**: `load_conversation` setzt bei `resume: true` den Session-State auf die geladene Datei (dateiname, verlauf)
- **Fix Frontend**: `loadConversation()` sendet `resume: true`, Status-Nachricht geaendert von "neue Session" zu "wird hier fortgesetzt"
- **Cleanup**: Redundanten `with open(dateiname, 'a')` Append-Write entfernt — `auto_save_session()` ueberschreibt ohnehin die gesamte Datei
- Alte Konversationen koennen jetzt nahtlos fortgesetzt werden

### Bug Fix: JS SyntaxError durch falsche Newline-Escapes
- **Problem**: `renderMessageContent()` enthielt `split('\\n')` das im Python-Triple-Quote-String als echtes Newline gerendert wurde
- **Fix**: `'\\n'` → `'\\\\n'` (doppeltes Backslash fuer korrekte JS-String-Ausgabe)
- Ursache: web_server.py JS-Code liegt in `HTML = \"\"\"...\"\"\"` — Python interpretiert Escape-Sequenzen

### Bug Fix: Kopieren-Button auf Code-Bloecke beschraenkt
- **Problem**: Kopieren-Button kopierte die gesamte AI-Nachricht inkl. Erklaerungstext
- **Fix**: Code-Bloecke (``` delimitiert) werden als eigene Box gerendert, jeder mit eigenem "Kopieren"-Button
- `renderMessageContent()`: parst Markdown-Code-Bloecke, erkennt Sprach-Label (```python etc.)
- `.code-block-wrapper`: dunkler Rahmen, eigener "Kopieren"-Button oben rechts
- `.code-copy-btn`: kopiert nur den Code-Inhalt dieses Blocks
- Globaler "Alles"-Button bleibt als kleines Label oben rechts (kopiert gesamte Nachricht)
- Nachrichten ohne Code-Bloecke: normaler "Kopieren"-Button wie bisher
- `copyToClipboard()`: shared Helper fuer alle Copy-Buttons

### Bug Fix: Leerer Bereich unter KONVERSATIONEN im Sidebar
- **Problem**: `history-list` war Geschwister- statt Kind-Element von `history-section`
- Beide hatten `flex:1`, wodurch `history-section` leeren Platz beanspruchte
- **Fix**: `history-list` in `history-section` verschoben (als Kind-Element)
- Konversationsliste beginnt jetzt direkt unter der Ueberschrift

### Test Suite eingefuehrt
- Neu: `tests/run_tests.py` — 95 Tests in 9 Kategorien
- Abgedeckt: Server-Erreichbarkeit, UI-Elemente, GET/POST Endpoints, Dateisystem, Session-Isolation, App-Bundle-Konsistenz, Chat Smoke Test, Web Clipper
- Alle 27 Routes getestet (non-destructive — keine echten Daten veraendert)
- Test-Sessions isoliert via `test_` Prefix (keine Kollision mit echten Sessions)
- CLAUDE.md: Test-Pflicht nach jeder Aenderung dokumentiert
- Aufruf: `python3 ~/AssistantDev/tests/run_tests.py`

### Konversations-Sidebar verbessert
- Sortierung: neueste Konversation zuerst (vorher: aelteste zuerst wegen `index[-10:]`)
- Kein Limit mehr: alle Konversationen werden angezeigt (vorher: nur letzte 10)
- Auto-Titel: erste User-Nachricht wird als Titel angezeigt (max. 60 Zeichen), Datum als Fallback
- Lesbare Datumsformate: `06.04.2026 09:13` statt `2026-04-06 09:13`
- History-Liste scrollbar ohne feste max-height, fuellt verfuegbaren Sidebar-Platz
- `migrate_old_conversations()` wird bei jedem History-Abruf aufgerufen (catch-up)

### Snippet Copy Button
- `addCopyButton(msgDiv, rawText)` Funktion: fuegt "Kopieren"-Button in Assistant-Bubbles ein
- Button erscheint bei Antworten mit 80+ Zeichen (Arbeitsergebnisse, nicht kurze Rueckfragen)
- Immer sichtbar (kein Hover noetig), oben rechts in der Bubble positioniert
- Klick kopiert reinen Text ohne HTML in die Zwischenablage
- Feedback: "Kopieren" → "Kopiert" (2s, gruen) mit CSS-Transition
- Clipboard API mit `execCommand('copy')` Fallback
- Wird automatisch bei neuen Antworten UND beim Laden alter Konversationen aufgerufen
- CSS: `.snippet-copy-btn` mit absolutem Positioning, Dark-Theme-kompatibel

### Auto-Save verifiziert und getestet
- `auto_save_session(session_id)` war bereits implementiert (vorherige Session) — Funktionstest bestanden
- Eine Session = eine Datei: Overwrite (nicht Append), enthält immer den vollständigen Verlauf
- 5 Aufrufstellen: nach normaler Antwort, nach Delegation, nach Queue-Item, bei Session-Cleanup, bei Shutdown
- Format kompatibel mit `load_conversation()` Parser: `[provider/model]\nDu: ...\nAssistant: ...\n\n`
- Getestet: 2 Nachrichten → dieselbe Datei aktualisiert (41 → 156 → 400 bytes), keine neue Datei erstellt

### Projektstruktur aufgeraeumt
- Veraltete Dateien aus `~/` in `backups/cleanup_20260406_090515/` archiviert:
  - `claude_web.py` (alte Haupt-App) → ersetzt durch `web_server.py`
  - `email_watcher.py` (Home-Version) → `src/email_watcher.py` ist neuer (Apr 2 11:50 vs. 08:55)
  - `verify_version.py` (altes Diagnose-Skript) → nicht mehr relevant
  - `slack_memory_server.py` (alter Port-8081-Server) → ersetzt durch `web_clipper_server.py`
- LaunchAgent `com.moritz.emailwatcher.plist` Pfad aktualisiert: `~/email_watcher.py` → `~/AssistantDev/src/email_watcher.py`
- LaunchAgent neu geladen via `launchctl unload/load`
- `models.json` geprueft: Perplexity-Block vorhanden, aktuell (Apr 6)

### Auto-Save Session nach jeder Nachricht
- `auto_save_session(session_id)` implementiert — sichert vollstaendigen Verlauf als Overwrite
- Wird nach jeder vollstaendig verarbeiteten Antwort automatisch aufgerufen (3 Stellen: normal, delegation, queue)
- Ueberschreibt bestehende Konversationsdatei (kompletter Verlauf, kein Datenverlust bei Neustart)
- `atexit` + `SIGTERM` Handler: alle Sessions werden bei pkill/Ctrl+C gesichert
- Session-Cleanup loescht inaktive Sessions nach 24h, sichert sie vorher per auto_save
- Backup: `backups/2026-04-06_08-45-41/`

### Memory & Zugriffs-Matrix dokumentiert
- Permanenter Abschnitt in changelog.md (oben, nach Header)
- Abschnitt in docs/TECHNICAL_DOCUMENTATION.md aktualisiert
- Matrix basiert auf verifiziertem Code-Stand (web_server.py + search_engine.py)

### Multi-Session Support (Parallel-Windows Fix)
- Globaler `state` Dict durch session-basiertes `sessions` Dict ersetzt
- Jedes Browser-Tab erhaelt isolierte Session via `sessionStorage` (neue Tab-ID pro Tab)
- `get_session(session_id)` Funktion: erstellt/liefert Session mit `last_active` Tracking
- Session-Cleanup: Hintergrund-Thread entfernt Sessions nach 24h Inaktivitaet
- 21 Routes auf `session_id` Parameter umgestellt (POST: JSON-Body, GET: Query-Param)
- `process_single_message`, `process_queue_worker`, `close_current_session`, `execute_delegation` erhalten `state` als Parameter
- Frontend: `SESSION_ID` via `sessionStorage`, alle `fetch()`-Aufrufe senden `session_id` mit
- Bug Fix: Konversationen zwischen parallelen Browser-Fenstern vermischen sich nicht mehr
- `add_file` (Multipart): `session_id` via `FormData.append()`
- Backup: `backups/2026-04-06_08-17-06/`

### Perplexity AI als 5. Provider
- `call_perplexity()` Adapter in web_server.py hinzugefuegt (OpenAI-kompatible API mit `base_url="https://api.perplexity.ai"`)
- `ADAPTERS` Dict um `"perplexity": call_perplexity` erweitert (beide Duplikat-Stellen)
- `models.json` um Perplexity-Block erweitert: Sonar, Sonar Pro, Sonar Reasoning, Sonar Reasoning Pro, Sonar Deep Research
- API Key muss manuell in `models.json` eingetragen werden (`PERPLEXITY_API_KEY_HERE` ersetzen)
- Provider erscheint automatisch im Frontend-Dropdown (keine JS-Aenderung noetig)

---

## 2026-04-03

### Bug Fix: Such-Dialog "Abbrechen" schickt Prompt jetzt trotzdem
- **Problem**: "Abbrechen" im Such-Dialog hat den gesamten Prompt verworfen — Nachricht wurde nicht an Claude geschickt
- **Fix**: `closeSearchDialog(false)` → `closeSearchDialog(true)` — Prompt wird jetzt ohne Dateien an Claude gesendet
- **Button-Label**: "Abbrechen" → "Ohne Dateien senden" (klarere Beschreibung der Aktion)
- Drei Aktionen im Dialog: [Auswahl laden] [Alle laden (max 5)] [Ohne Dateien senden]

### Chrome Extension Debug + Dual Save
- **Debug-Logging**: Umfangreiches `console.log`/`console.error` in background.js und content_script.js fuer jeden Schritt (Icon-Klick, Agent-Fetch, Save-Request/Response, Fehler)
- **`chrome.runtime.lastError`** Check im Save-Handler der content_script.js
- **Surrogate-Pair Fix**: `\uD83C\uDFE2` etc. durch ES6 `\u{1F3E2}` ersetzt (korrekte Unicode-Syntax)
- **Sub-Agent Filter**: `/agents` Route in web_clipper_server.py gibt nur Parent-Agenten zurueck (keine Sub-Agents mit `_` im Namen)
- **Dual Save** in `/save` Route: speichert jetzt in BEIDE Orte:
  - `[agent]/memory/[filename]` (Agent Memory, wie bisher)
  - `webclips/[agent]_[filename]` (globales Web Clip Memory)
- `GLOBAL_WEBCLIPS` Ordner: `~/Library/Mobile Documents/com~apple~CloudDocs/Downloads shared/webclips/`
- Response enthaelt `saved_to_agent` und `saved_to_global` Pfade
- Toast-Meldung: "Gespeichert in [agent] + globales Memory"
- webclips/ automatisch im globalen Such-Index enthalten (Downloads shared wird rekursiv indexiert)

### Agent-Modal: Expandierbare Subagenten
- `/agents` Route gibt jetzt hierarchische Struktur zurueck: `{name, label, has_subagents, subagents: [{name, label}]}`
- Parent-Agenten mit Subagenten: Klick auf Name waehlt Parent, Klick auf Pfeil expandiert/kollabiert
- Subagenten eingerueckt (16px), kleinere Schrift (11px), gedimmte Farbe (#999)
- CSS Pfeil-Animation: \u25B6 rotiert zu \u25BC bei expand (0.2s transition)
- Smooth height-Animation (max-height transition) fuer expand/collapse
- Nur ein Parent kann gleichzeitig expandiert sein (andere kollabieren automatisch)
- Expand-State in localStorage gespeichert (`agent_expanded`)

### Quellen-Taxonomie (Source Taxonomy)
- **SOURCE_TAXONOMY** Dict mit hierarchischen Quellen-Typen: email, notification, webclip (salesforce/slack/general), document (word/excel/pdf/pptx), conversation, screenshot
- `detect_source_type(filename, preview)`: erkennt Quellen-Typ aus Dateiname und Vorschau-Text
- `detect_source_filter(query)`: erkennt Quellen-Filter aus natuerlicher Sprache, spezifischerer Typ gewinnt
- `extract_conversation_meta(text)`: parst konversation_*.txt Format (Agent, Datum, User-Messages)
- `get_source_label(type)`: menschenlesbares Label mit Icon
- QueryParser nutzt jetzt `source_types_effective` (inkl. Unterkategorien) fuer Typ-Filter
- HybridSearch filtert nach `source_type` statt nur `type`, Parent-Filter schliesst Unterkategorien ein
- Such-Dialog: Filter-Buttons [Alle] [E-Mail] [Web Clip] [Dokument] [Konversation] [Screenshot]
- Unterfilter bei Web Clip (Salesforce/Slack/Web) und Dokument (Word/Excel/PDF/PowerPoint)
- "Alle" Filter blendet Notifikationen aus, E-Mail Filter zeigt sie ganz unten
- Screenshots werden als Base64-Bild in Kontext geladen (Vision-faehig)
- Ergebnis-Items zeigen Typ-Icons: \u2709 E-Mail, \U0001f310 Web Clip, \U0001f4c4 Dokument, \U0001f4ac Konversation, \U0001f4f8 Screenshot

### Erweitertes Memory / Globale Suche
- **GlobalSearchIndex** in `search_engine.py`: indexiert alle Agent-Memory-Ordner + gesamten Downloads shared Ordner
- Dateityp-Extraktion: PDF (PyPDF2), DOCX (python-docx), XLSX (openpyxl), PPTX (python-pptx), plain text
- Delta-Update: nur neue/geaenderte Dateien re-indexieren, geloeschte entfernen
- **GLOBAL_TRIGGERS**: ~25 Phrasen (DE/EN/PT) — "erweitertes gedaechtnis", "global search", "search everywhere", "todos os agentes"
- Client-seitig: `detectGlobalTrigger()` prueft vor Server-Call ob globaler Trigger vorliegt
- `POST /global_search_preview` Route: sucht im globalen Index, liefert bis zu 50 Ergebnisse mit Agent-Tag
- Such-Dialog gruppiert bei globaler Suche nach Agent (signicat, privat, inbox, global)
- Ergebnis-Items zeigen Agent-Herkunft: `[signicat]`, `[privat]`, `[inbox]`, `[global]`
- Globaler Index wird beim Server-Start im Hintergrund-Thread gebaut
- Index-Datei: `Downloads shared/.global_search_index.json`

### Such-Dialog: Notifikations-Filter, 50 Ergebnisse, 5-Datei-Limit
- **NOTIFICATION_PATTERNS**: ~35 Muster (noreply, newsletter, mailchimp, jira, github, slack, etc.) erkennen automatisierte E-Mails
- Notifikationen: `score *= 0.1`, `is_notification` Flag, grau/kursiv/opacity im Dialog, `[Notif]` Prefix
- Ergebnisse von 10 auf **50** erhoeht, gruppierte Anzeige mit Trennern ("── E-Mails & Dateien ──" / "── Notifikationen ──")
- **Checkbox-Limit auf 5**: Erste 5 Nicht-Notifikationen auto-ausgewaehlt, Counter "2 / 5 ausgewaehlt", 6. Checkbox wird blockiert
- Backend `/load_selected_files` limitiert auf max 5 Pfade
- "Alle laden" laedt max 5 Nicht-Notifikationen

### Interaktive Such-Auswahl im Chat
- Neuer Dialog bei Such-Anfragen: zeigt bis zu 10 Ergebnisse mit Checkbox-Auswahl
- Client-seitige Trigger-Erkennung (`detectSearchIntent()`) prueft vor dem Chat-Senden ob Such-Intent vorliegt
- `POST /search_preview` Route: liefert reichhaltige Vorschau (Name, Typ, Datum, Von, Betreff, Preview, Score, from_person Flag)
- `POST /load_selected_files` Route: laedt ausgewaehlte Dateien in state['kontext_items']
- Ablauf: User schreibt Suchanfrage -> Dialog erscheint -> User waehlt Dateien -> Dateien werden geladen -> Chat wird gesendet
- E-Mails VON der gesuchten Person werden gruen hervorgehoben und oben sortiert
- Drei Buttons: "Alle laden", "Auswahl laden", "Abbrechen" (sendet trotzdem an Claude)
- Dunkles Overlay-Design passend zum Dark Theme

### Bug Fix: Internal Server Error auf GET /
- Ursache: Surrogate-Pair `\uD83D\uDD0D` im HTML-Template (addCtxItem JS) verursachte UnicodeEncodeError
- Fix: Durch direktes Unicode-Zeichen ersetzt
- Backup vor Fix angelegt: `backups/2026-04-03_08-59-42/`

### Backup-System + CLAUDE.md Regeln
- `scripts/backup.sh` erstellt: Backup beliebiger Dateien nach `backups/[datum_uhrzeit]/[pfad]`
- `CLAUDE.md` erstellt: Pflichtregeln fuer Claude Code — Backup vor jeder Aenderung, Syntax-Check, Changelog, keine Dateien loeschen, Port-Konventionen, App-Bundle-Deployment
- `backups/` Ordner angelegt, erstes Backup aller Source-Dateien erstellt
- Regel: Ab sofort IMMER Backup vor Code-Aenderungen

### Auto-Search laedt Dateien jetzt in Kontext
- Auto-gefundene Dateien werden automatisch in `state['kontext_items']` geladen bevor der API-Call erfolgt
- Claude erhaelt die Datei-Inhalte als Kontext und antwortet basierend auf dem tatsaechlichen Inhalt
- Context-Bar zeigt auto-geladene Dateien mit gruener Umrandung und Lupe-Icon statt Datei-Icon
- CSS-Klasse `.ctx-item.auto-loaded` mit gruener Border (#4a8a4a) und dunklem Gruen-Hintergrund (#1a2a1a)
- Dateien werden bei Agent-Wechsel oder neuer Konversation automatisch entfernt

### Search Engine — Neues Such-System
- `src/search_engine.py` erstellt: eigenstaendiges Modul mit 3 Klassen
- **SearchIndex**: JSON-Index pro Agent (`.search_index.json`), erkennt Dateitypen (email/salesforce/web/document/image/conversation), extrahiert Email-Header (Von/An/Betreff), Auto-Keywords, Vorschau (300 Zeichen). Delta-Update statt komplett neu bauen.
- **QueryParser**: Versteht natuerliche Sprache (DE/EN/PT). Erkennt Zeitfilter (gestern, letzte Woche, 02.04.), Feldfilter (von/from/de, an/to/para), Dateitypen, Eigennamen. Unicode-Normalisierung (Simonas = Simonas).
- **HybridSearch**: 4-stufig — Zeitfilter auf Index, BM25-Scoring auf Index-Daten, Volltext Top-20, Ranking. Kein Fallback auf zufaellige Dateien.
- Integriert in web_server.py: auto_search() ersetzt auto_search_memory(), Index wird bei Agent-Wechsel im Hintergrund gebaut
- Chat-Feedback: "Suche: [query] | Typ: Email | Zeitraum: gestern | Gefunden: 3 | Index: 2889 Dateien"
- Erstindizierung: 7.410 Dateien in 4.2s
- CLI: `python3 search_engine.py` baut Index fuer alle Agenten

### Auto-Search Object Keywords massiv erweitert
- `_SEARCH_OBJECTS` von ~30 auf ~70+ Keywords erweitert
- Neue Kategorien: Word (word, brief, schreiben, carta), Excel (tabelle, spreadsheet, planilha, auswertung, analysis), PowerPoint (praesentation, slides, deck, folie, pitch, vortrag), PDF, Vertraege/Rechnungen (agreement, billing, quote, bestellung, order, pedido), Notizen (memo, protokoll, minutes, ata, zusammenfassung, summary, resumo)
- Spanisch ergaenzt: correo, calculo

### Bug Fix: Auto-Search triggert nicht
- `auto_search_memory()` erkennt jetzt auch Eigennamen (Grossbuchstabe nach Trigger-Keyword) als Suchausloeser
- Trigger: Action-Keyword + Object-Keyword ODER Action-Keyword + Eigenname
- Temporal/Datums-Keywords ergaenzt: gestern, heute, yesterday, today, ontem, hoje, letzte, recent
- Neue Object-Keywords: angebot, praesentation, proposal, presentation, proposta
- Such-Feedback im Chat: "Memory-Suche: X Datei(en) gefunden fuer 'query'" oder "nichts gefunden"
- `auto_search_memory()` gibt jetzt `(results, query_string)` Tuple zurueck fuer Feedback

### Bug Fix: Sidebar zeigt nicht den vollen System Prompt
- `/get_prompt` gibt jetzt `state['system_prompt']` zurueck (volles Prompt inkl. Memory + Capabilities)
- Gilt nur fuer den aktiven Agenten — inaktive Agenten zeigen weiterhin nur Basis-Prompt
- Sidebar-Hinweis aktualisiert: erklaert dass 'Basis speichern' nur den oberen Teil speichert

### OpenAI Library + Gemini Error Handling
- `openai` Python Library installiert
- `call_gemini()`: 429/Quota/Rate-Limit Fehler gibt jetzt klare Meldung mit Upgrade-Link zurueck

### Kontakt-Extraktion komplett ueberarbeitet
- `scripts/extract_contacts.py` neu geschrieben mit sauberer zweistufiger Logik
- **Stufe 1** (kein API-Call): Alle E-Mails scannen, From-Header parsen, automatisierte Absender filtern (noreply, newsletter, etc. + Massenversender-Domains wie mailchimp, sendgrid, hubspot), Duplikate zusammenfuehren (laengsten Body merken), Vorschau-Excel mit Name+Email
- **Stufe 2** (Claude Haiku API): Nur eindeutige Kontakte, letzte 60 Zeilen als Signatur-Kandidat, Batches von 20 Signaturen pro API-Call, Fortschrittsanzeige mit ETA
- Checkpoint-Datei `~/.extract_contacts_progress.json` fuer Fortsetzbarkeit (`--continue` Flag)
- Kostenvoranschlag vor Stufe 2 Start
- Kein MAX_EMAILS Limit mehr — alle E-Mails werden gescannt
- Finaler Output: Excel + vCard, optionaler Apple Contacts Import

---

## 2026-04-02

### Kontakt-Extraktion aus E-Mails
- `scripts/extract_contacts.py` erstellt: extrahiert Kontakte aus allen E-Mails in email_inbox/
- Header-Extraktion (Name, Email) + Claude API Signatur-Analyse (Telefon, Firma, Titel, etc.)
- Output: Excel (.xlsx) + vCard (.vcf) — direkt importierbar in Apple Contacts
- Deduplizierung nach Email-Adresse, automatisierte Absender werden uebersprungen
- Limit: 500 E-Mails pro Durchlauf (API-Kosten ca. $0.10-0.20 mit Haiku)

### Assistant Memory Clipper (Chrome Extension)
- Universelle Chrome Extension ersetzt alle Bookmarklets (Salesforce, Slack, Web)
- Smart Extraction: erkennt Salesforce Lightning, Slack, beliebige Webseiten automatisch
- Background Service Worker: kein CSP-Problem, direkter fetch() zu localhost:8081
- Floating Panel UI mit Agent-Dropdown, Dateiname-Editor, Vorschau
- Alte Bookmarklets als deprecated markiert

### Salesforce Clipper Fix
- Nur Parent-Agenten im Dropdown (Sub-Agents und Agenten ohne Memory-Ordner ausgeschlossen)
- 3-Stufen Fallback-Strategie gegen Salesforce CSP:
  1. data: URI iframe (schnellste Option)
  2. Direkter XHR falls iframe blockiert (3s Timeout)
  3. Zwischenablage-Kopie falls alles blockiert
- Klares Feedback welche Strategie verwendet wurde

### Salesforce Clipper Bookmarklet
- `scripts/salesforce_clipper.js` erstellt: Ein-Klick Export von Salesforce Lightning Daten
- Extrahiert alle sichtbaren Felder (Labels + Values) aus Lead/Account/Opportunity/Contact/Case
- CSP-Workaround via about:blank Tab fuer fetch() zu localhost:8081
- Agenten-Liste hardcoded im Bookmarklet (kein fetch fuer /agents noetig)
- `scripts/generate_salesforce_bookmarklet.py` generiert Bookmarklet mit aktueller Agenten-Liste
- Installationsanleitung: `docs/salesforce_clipper_install.md`

### Sub-Agent Delegation
- Agent-zu-Agent Delegation via natuerliche Sprache (DE/EN/PT Trigger)
- Fuzzy Matching: exakt, Keyword-basiert (`config/subagent_keywords.json`), partial, Levenshtein
- Delegation laedt Sub-Agent System Prompt + Parent Memory + letzte 5 Messages als Kontext
- Frontend zeigt Delegations-Status im Chat
- Route `GET /available_subagents` listet Sub-Agents mit Keywords

### Sub-Agent System
- Namenskonvention: `[parent]_[spezialisierung].txt` (z.B. `signicat_outbound.txt`)
- Memory Sharing: Sub-Agents nutzen Memory und _index.json des Parent-Agents
- Konversationen im Parent-Ordner mit Sub-Agent-Suffix gespeichert
- Frontend: Sub-Agents eingerueckt unter Parent im Agent-Modal, Header zeigt "parent > sub"
- Erstellt: signicat_outbound, signicat_powerpoint, signicat_lamp, signicat_meddpicc

### Auto-Search Trigger multilingual
- DE/EN/PT Action-Keywords (finde, search, procura, ...) + Object-Keywords (email, datei, contrato, ...) triggern automatische Memory-Suche
- Kein "memory folder" mehr noetig — natuerliche Sprache genuegt
- Keyword-Extraktion entfernt Trigger-Woerter und Stoppwoerter, behaelt nur suchrelevante Begriffe
- PT Stoppwoerter hinzugefuegt (de, da, do, para, com, ...)

### Memory-Suche verbessert
- Multi-Keyword-Parsing mit Stoppwoerter-Filter (DE+EN), Keywords unter 3 Zeichen ignoriert
- Scoring-System: Dateiname +3/Keyword, alle Keywords +5 Bonus, Inhalt +1/+2 pro Keyword, alle im Inhalt +3 Bonus
- Inhaltssuche auf neueste 1000 Dateien beschraenkt (nach Aenderungsdatum sortiert)
- Kein Fallback auf zufaellige Dateien mehr — klare "Nichts gefunden" Meldung

### Konsolidierung zu AssistantDev
- Alle losen Skripte in `~/` zusammengeführt zu `~/AssistantDev/src/`
- `claude_web.py` → `src/web_server.py`
- `email_watcher.py` → `src/email_watcher.py`
- Neue Menu Bar App `src/app.py` als zentraler Controller
- `PROCESSED_LOG` in `~/.emailwatcher_processed.json` (Home statt iCloud) → behebt Permission-Fehler bei App/LaunchAgent

### Gemini API Integration
- `call_gemini()` Adapter in web_server.py hinzugefügt
- `models.json` um Gemini-Block erweitert
- `/models` Route gibt korrektes Format für Frontend zurück

### Historischer E-Mail Export
- `export_existing_emails.applescript` erstellt: exportiert alle E-Mails der letzten 12 Monate rueckwirkend in `email_inbox/` zur Verarbeitung durch den Email Watcher
- Durchsucht alle Mailboxen (Inbox, Sent, Unterordner) ausser Trash/Junk
- Duplikat-Schutz: ueberspringt Dateien die bereits existieren
- Fortschrittsanzeige und Abschlussmeldung

### Bug Fixes
- Doppelte `build_memory_context()` Funktion entfernt (zweite überschrieb erste)
- `@app.route('/')` fehlte — HTML-Template neu injiziert
- JS SyntaxError in `addCtxItem()` — onclick-String durch DOM-API ersetzt
- Agent-Modal: `classList.remove('show')` ergänzt durch `style.display='none'`
- `CREATE_EMAIL` Parser getrennt von `CREATE_FILE` Parser (unterschiedliches Format)

---

## 2026-04-01

### Email Integration
- Apple Mail Regel + AppleScript für automatisches .eml Speichern
- Email Watcher mit Keyword-Routing zu Agenten
- Junk-Filter via Apple Mail Regel (Reihenfolge: Junk → Stop, dann Save)
- Attachments werden automatisch extrahiert

### Memory System (Compact)
- Startup-Cleanup: entfernt alten Memory-Müll aus .txt Agenten-Dateien
- Memory-Inhaltsverzeichnis statt voller Dateiinhalte im System Prompt
- "memory folder suche [keyword]" Trigger für gezielte Suche
- Finder-Buttons: "Im Finder zeigen" und "Memory Ordner öffnen"

### Interface
- Sidebar mit System Prompt (editierbar) + Konversationsliste
- Typing-Indicator mit rotierendem Text
- Drag & Drop auf gesamtes Browser-Fenster
- Vision: PNG/JPG als Base64 an Anthropic API
- Web-Suche via Anthropic API Tool

### Datei-Erstellung
- Word (.docx) via python-docx
- Excel (.xlsx) via openpyxl
- PDF (.pdf) via reportlab
- PowerPoint (.pptx) via python-pptx
- Email-Draft öffnet Apple Mail via AppleScript + mailto Fallback

### Multi-Provider
- Anthropic, OpenAI, Mistral, Gemini
- Provider/Modell-Dropdown im Header
- ADAPTERS-Pattern für einfaches Hinzufügen neuer Provider

---

## Offen / Geplant

- [ ] Gemini API Key eintragen (aistudio.google.com/app/apikey)
- [ ] Web Clipper Bookmarklet reaktivieren auf Port 8081
- [ ] Rate Limit erhöhen bei Anthropic (console.anthropic.com)
- [ ] Assistant.app in /Applications installieren + Full Disk Access
