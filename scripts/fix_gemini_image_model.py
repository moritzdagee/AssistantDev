#!/usr/bin/env python3
"""Fix Gemini image model list to use actually available models."""

WEB_SERVER = "/Users/moritzcremer/AssistantDev/src/web_server.py"

with open(WEB_SERVER, "r", encoding="utf-8") as f:
    code = f.read()

changes = 0

old = '        # Gemini Bildgenerierung: primaer gemini-2.0-flash-preview-image-generation,\n        # Fallback auf gemini-2.5-flash (nur innerhalb Gemini)\n        gemini_models = ["gemini-2.0-flash-preview-image-generation", "gemini-2.5-flash"]'
new = '        # Gemini Bildgenerierung: verfuegbare Image-Modelle in Prioritaetsreihenfolge\n        gemini_models = ["gemini-2.5-flash-image", "gemini-3.1-flash-image-preview", "gemini-3-pro-image-preview"]'

if old in code:
    code = code.replace(old, new)
    changes += 1
    print("✓ Gemini Image-Modelle korrigiert")
else:
    print("✗ Pattern nicht gefunden")
    import sys; sys.exit(1)

with open(WEB_SERVER, "w", encoding="utf-8") as f:
    f.write(code)
print(f"Gesamt: {changes}")
