#!/usr/bin/env python3
"""
Fuegt den standardisierten Memory-Beschreibungsblock in alle Parent-Agent System Prompts ein.
Sub-Agenten (mit _ im Namen) und system ward.txt werden uebersprungen.
"""

import os
import shutil
from datetime import datetime

AGENTS_DIR = os.path.expanduser(
    "~/Library/Mobile Documents/com~apple~CloudDocs/Downloads shared/claude_datalake/config/agents"
)

MEMORY_BLOCK = """

## DEIN GEDAECHTNIS & DATEIZUGRIFF

Du hast Zugriff auf ein persistentes Memory mit Dateien die Moritz fuer dich abgelegt hat oder die automatisch importiert wurden. Das System indexiert dein Memory und ermoeglicht gezielte Suche.

### Was liegt in deinem Memory

| Typ | Erkennbar an | Inhalt |
|-----|-------------|--------|
| E-Mails | IN_ oder OUT_ im Dateinamen | Eingehende/ausgehende E-Mails, automatisch importiert vom Email Watcher. Format: DATUM_RICHTUNG_ABSENDER_BETREFF.txt |
| Web Clips | web_ im Dateinamen | Geclippte Webseiten via Chrome Extension. Quellen: Salesforce Records, Slack Channels, beliebige Webseiten. Format: .txt (alt) oder .json + .png (neu) |
| Dokumente | .docx .xlsx .pdf .pptx Endung | Word, Excel, PDF, PowerPoint – manuell von Moritz abgelegt. Werden automatisch extrahiert und lesbar gemacht. |
| Konversationen | konversation_ im Dateinamen | Alle vergangenen Chats mit dir, automatisch nach jeder Session gespeichert. |
| Screenshots | .png .jpg Endung (ohne web_ Prefix) | Screenshots – du kannst sie direkt visuell analysieren (Vision). |
| Kontakte | contacts.json | Extrahierte Personen aus E-Mails: Name, E-Mail-Adresse, Haeufigkeit des Kontakts. |

### Suche im Memory

Die Suche wird vom System (Frontend) gesteuert. Du musst nichts aktiv tun.

Moritz loest Suche aus mit:
- `\\find [suchbegriff]` – sucht in deinem Memory, zeigt interaktiven Auswahl-Dialog
- `/search [suchbegriff]` – identisch zu \\find
- Natuerliche Sprache die Suchintent signalisiert (z.B. "finde die E-Mail von...", "such mir...")
- Fuer globale Suche ueber alle Agenten: "suche ueberall", "erweitertes Gedaechtnis", "global search"

Wenn Dateien in deinen Kontext geladen wurden, siehst du sie als --- KONTEXT --- Block in deiner Nachricht.

### Was du mit Memory-Dateien tun kannst

- E-Mails lesen, zusammenfassen, darauf antworten (mit CREATE_EMAIL Draft)
- Dokumente analysieren – Word/Excel/PDF/PPTX werden automatisch als Text extrahiert
- Screenshots visuell analysieren – du siehst das Bild direkt (Vision-faehig)
- Auf vergangene Konversationen zurueckgreifen und Kontext herstellen
- Kontakte nachschlagen aus contacts.json
- Salesforce-Daten aus Web Clips lesen (Account-Felder, Opportunities, Activity Timeline)
"""

MARKER = "DEIN GEDAECHTNIS & DATEIZUGRIFF"

# Sub-Agent Erkennung: Underscore im Dateinamen (vor .txt)
SKIP_FILES = {"system ward.txt"}


def is_subagent(filename):
    """Sub-Agenten haben _ im Dateinamen vor .txt (z.B. signicat_outbound.txt)"""
    name_without_ext = filename.rsplit(".txt", 1)[0]
    return "_" in name_without_ext


def main():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    changed = []
    skipped = []

    txt_files = sorted(f for f in os.listdir(AGENTS_DIR) if f.endswith(".txt") and not f.endswith(f".backup_{timestamp[:8]}"))
    # Filter out backup files
    txt_files = [f for f in txt_files if ".backup_" not in f]

    for filename in txt_files:
        filepath = os.path.join(AGENTS_DIR, filename)

        # Skip sub-agents
        if is_subagent(filename):
            skipped.append((filename, "Sub-Agent"))
            continue

        # Skip system ward.txt
        if filename in SKIP_FILES:
            skipped.append((filename, "Manuell uebersprungen"))
            continue

        # Check if block already exists
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        if MARKER in content:
            skipped.append((filename, "Block bereits vorhanden"))
            continue

        # Create backup
        backup_path = f"{filepath}.backup_{timestamp}"
        shutil.copy2(filepath, backup_path)

        # Append block
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(MEMORY_BLOCK)

        changed.append(filename)
        print(f"✓ {filename} – Block hinzugefuegt")

    print(f"\n--- Zusammenfassung ---")
    print(f"Geaendert: {len(changed)} Dateien")
    for f in changed:
        print(f"  ✓ {f}")
    print(f"Uebersprungen: {len(skipped)} Dateien")
    for f, reason in skipped:
        print(f"  ⊘ {f} ({reason})")


if __name__ == "__main__":
    main()
