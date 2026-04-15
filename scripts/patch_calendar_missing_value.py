#!/usr/bin/env python3
"""Fix: 'missing value' aus AppleScript-Output entfernen."""
import os, sys
WS = os.path.expanduser("~/AssistantDev/src/web_server.py")
src = open(WS).read()

OLD = "        notes = parts[6].strip() if len(parts) > 6 else ''"
NEW = """        notes = parts[6].strip() if len(parts) > 6 else ''
        # AppleScript gibt 'missing value' statt leer zurueck
        if location == 'missing value': location = ''
        if notes == 'missing value': notes = ''"""

if 'missing value' in src and "location == 'missing value'" not in src:
    if src.count(OLD) == 1:
        src = src.replace(OLD, NEW)
        open(WS, 'w').write(src)
        print("OK: missing value fix")
    else:
        print(f"SKIP: {src.count(OLD)} Vorkommen")
else:
    print("SKIP: schon gefixt oder nicht noetig")
