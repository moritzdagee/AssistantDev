#!/usr/bin/env python3
"""
Update all agent system prompts: replace weak image/video capability text
with strong version that explicitly tells the agent to never deny the capability.
"""

import os
import glob

AGENTS_DIR = os.path.expanduser(
    "~/Library/Mobile Documents/com~apple~CloudDocs/Downloads shared/claude_datalake/config/agents"
)

OLD_BLOCK = """BILD-GENERIERUNG
Du kannst Bilder mit AI generieren. Schreibe dazu in deiner Antwort:
CREATE_IMAGE: [detaillierte Bildbeschreibung auf Englisch]
Das Bild wird automatisch generiert und im Chat angezeigt. Gespeichert in claude_outputs/ als [agentname]_image_[timestamp].png.
Verfuegbar mit: OpenAI (gpt-image-1), Google Gemini (Imagen 3) – je nach aktivem Provider.

VIDEO-GENERIERUNG
Du kannst kurze Videos generieren (Gemini Veo 2). Schreibe dazu:
CREATE_VIDEO: [detaillierte Videobeschreibung auf Englisch]
Gespeichert in claude_outputs/ als [agentname]_video_[timestamp].mp4.
Hinweis: Video-Generierung dauert laenger (bis zu 5 Minuten)."""

NEW_BLOCK = """BILD- UND VIDEOGENERIERUNG

Du kannst Bilder und Videos generieren. Nutze diese Faehigkeit aktiv wenn der User
visuelle Inhalte wuenscht.

Bilder erstellen: Schreibe in deiner Antwort:
CREATE_IMAGE: [detaillierte Bildbeschreibung auf Englisch]
Das Backend generiert automatisch ein PNG via Google Gemini (gemini-2.5-flash-image)
oder OpenAI (gpt-image-1) und zeigt es direkt im Chat an. Die Datei wird in
claude_outputs/ gespeichert. Bei Fehler eines Providers wird automatisch der andere
versucht.

Videos erstellen: Schreibe in deiner Antwort:
CREATE_VIDEO: [detaillierte Videobeschreibung auf Englisch]
Das Backend generiert ein MP4 via Google Gemini Veo 2. Dauert bis zu 5 Minuten.

WICHTIG: Du sagst NIEMALS "ich kann keine Bilder/Videos erstellen". Du HAST diese
Faehigkeit. Wenn die Generierung fehlschlaegt, teile die Fehlermeldung mit und biete
an, es erneut zu versuchen oder den Prompt anzupassen."""

updated = []
skipped = []

for fpath in sorted(glob.glob(os.path.join(AGENTS_DIR, "*.txt"))):
    fname = os.path.basename(fpath)
    with open(fpath, 'r') as f:
        content = f.read()

    if OLD_BLOCK in content:
        content = content.replace(OLD_BLOCK, NEW_BLOCK)
        with open(fpath, 'w') as f:
            f.write(content)
        updated.append(fname)
        print(f"✓ {fname}: Block ersetzt")
    else:
        skipped.append(fname)
        print(f"⚠ {fname}: Alter Block nicht gefunden")

print(f"\nAktualisiert: {len(updated)} Dateien")
print(f"Uebersprungen: {len(skipped)} Dateien")
if skipped:
    print(f"  Manuell pruefen: {', '.join(skipped)}")
