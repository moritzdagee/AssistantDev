#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Patch web_server.py:
1. Fix double-period in image/video error messages
2. Improve error messages with provider-specific hints
3. Add CREATE_IMAGE/VIDEO hint to system prompt
"""

filepath = '/Users/moritzcremer/AssistantDev/src/web_server.py'

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

changes = 0

# =============================================================
# 1. Fix generate_image error message (remove trailing period)
# =============================================================

old_img_err = """            f"Bildgenerierung nicht verfuegbar mit {provider_name}. "
            f"Wechsle zu Google Gemini oder OpenAI fuer Bildgenerierung."
        )"""

new_img_err = """            f"Bildgenerierung nicht verfuegbar mit {provider_name}. "
            f"Wechsle zu Google Gemini oder OpenAI fuer Bildgenerierung"
        )"""

count = content.count(old_img_err)
if count > 0:
    content = content.replace(old_img_err, new_img_err)
    print(f"1a. Fixed trailing period in image error ({count})")
    changes += count

# =============================================================
# 2. Fix generate_video error message (remove trailing period)
# =============================================================

old_vid_err = """            f"Videogenerierung ist nur mit Google Gemini verfuegbar. "
            f"Bitte wechsle zu Gemini fuer Videogenerierung."
        )"""

new_vid_err = """            f"Videogenerierung ist nur mit Google Gemini verfuegbar. "
            f"Bitte wechsle zu Gemini fuer Videogenerierung"
        )"""

count = content.count(old_vid_err)
if count > 0:
    content = content.replace(old_vid_err, new_vid_err)
    print(f"1b. Fixed trailing period in video error ({count})")
    changes += count

# =============================================================
# 3. Add CREATE_IMAGE/VIDEO capability hint to system prompt
# =============================================================

old_prompt_section = """--- WEITERE FAEHIGKEITEN ---
- Web-Suche: Du kannst aktuelle Informationen aus dem Internet abrufen. Nutze dies automatisch wenn der Nutzer nach aktuellen Infos, Preisen, Nachrichten oder Website-Inhalten fragt.
- Bilder lesen: Hochgeladene Screenshots und Fotos kannst du analysieren und beschreiben.
- Dateien lesen: PDF, Word, Excel werden automatisch extrahiert und stehen als Kontext zur Verfuegung.
--- ENDE DATEI-ERSTELLUNG ---"""

new_prompt_section = """--- WEITERE FAEHIGKEITEN ---
- Web-Suche: Du kannst aktuelle Informationen aus dem Internet abrufen. Nutze dies automatisch wenn der Nutzer nach aktuellen Infos, Preisen, Nachrichten oder Website-Inhalten fragt.
- Bilder lesen: Hochgeladene Screenshots und Fotos kannst du analysieren und beschreiben.
- Dateien lesen: PDF, Word, Excel werden automatisch extrahiert und stehen als Kontext zur Verfuegung.
- Bilder erstellen: Wenn der Nutzer ein Bild moechte, verwende CREATE_IMAGE. Das System wechselt automatisch auf das passende Bildmodell des aktiven Anbieters (Imagen 4 bei Google Gemini, gpt-image-1 bei OpenAI). Sage NIEMALS dass du keine Bilder erstellen kannst.
- Videos erstellen: Wenn der Nutzer ein Video moechte, verwende CREATE_VIDEO. Das System nutzt automatisch Google Veo. Sage NIEMALS dass du keine Videos erstellen kannst.
--- ENDE DATEI-ERSTELLUNG ---"""

count = content.count(old_prompt_section)
if count > 0:
    content = content.replace(old_prompt_section, new_prompt_section)
    print(f"2. Added CREATE_IMAGE/VIDEO capability to system prompt ({count})")
    changes += count
else:
    print("WARNING: WEITERE FAEHIGKEITEN section not found")

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"\nTotal changes: {changes}")
print("DONE")
