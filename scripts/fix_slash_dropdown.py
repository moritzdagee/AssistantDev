#!/usr/bin/env python3
"""Fix slash dropdown max-height to show all commands."""

WEB_SERVER = "/Users/moritzcremer/AssistantDev/src/web_server.py"

with open(WEB_SERVER, "r", encoding="utf-8") as f:
    code = f.read()

changes = 0

# 1. Slash dropdown max-height: 120px -> 400px (shows ~10 items)
old = "  #slash-ac-dropdown {\n  display:none; position:absolute; bottom:100%; left:0; right:0;\n  background:#1a1a1a; border:1px solid #333; border-radius:8px;\n  max-height:120px; overflow-y:auto; z-index:200; margin-bottom:4px;"
new = "  #slash-ac-dropdown {\n  display:none; position:absolute; bottom:100%; left:0; right:0;\n  background:#1a1a1a; border:1px solid #333; border-radius:8px;\n  max-height:400px; overflow-y:auto; z-index:200; margin-bottom:4px;"

if old in code:
    code = code.replace(old, new)
    changes += 1
    print("✓ Slash dropdown max-height 120px -> 400px")
else:
    print("✗ Slash dropdown pattern nicht gefunden")
    import sys; sys.exit(1)

with open(WEB_SERVER, "w", encoding="utf-8") as f:
    f.write(code)

print(f"Gesamt: {changes} Aenderungen")
