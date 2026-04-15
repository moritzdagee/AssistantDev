#!/usr/bin/env python3
"""CRITICAL FIX: JS string literals in the HTML template use \\n which Python's
triple-quoted string renders as actual newlines. Need \\\\n so Python outputs
literal \\n that JS interprets as escape sequence."""
import os
WS = os.path.expanduser("~/AssistantDev/src/web_server.py")

with open(WS, 'rb') as f:
    raw = f.read()

# The issue: inside the HTML template (triple-quoted Python string),
# we have bytes like: msg += '\\n...' which Python's string processing
# turns into a real newline. We need: msg += '\\\\n...'
# In the raw file bytes, \\n is 0x5c 0x6e.

# Find all occurrences of \\n inside JS msg string operations
# Pattern in bytes: msg followed by \\n inside a quote context

count = 0
# Specific patterns to fix (bytes):
replacements = [
    # Calendar handler
    (b"d.count + ' Termine)\\n';", b"d.count + ' Termine)\\\\n';"),
    (b"msg += '\\nKeine Termine gefunden.';", b"msg += '\\\\nKeine Termine gefunden.';"),
    (b"msg += '\\n**' + dateOnly + '**';", b"msg += '\\\\n**' + dateOnly + '**';"),
    (b"msg += '\\n- ' + time +", b"msg += '\\\\n- ' + time +"),
    # Canva handler
    (b"' : '') + ':**\\n';", b"' : '') + ':**\\\\n';"),
    (b"msg += '\\n- **' + (it.title", b"msg += '\\\\n- **' + (it.title"),
    (b"msg += '\\nKeine Designs gefunden.';", b"msg += '\\\\nKeine Designs gefunden.';"),
    (b"msg += '\\n[Design oeffnen](' +", b"msg += '\\\\n[Design oeffnen](' +"),
    (b"Brand Templates:**\\n';", b"Brand Templates:**\\\\n';"),
    (b"msg += '\\n- **' + (it.title || it.id)", b"msg += '\\\\n- **' + (it.title || it.id)"),
    (b"msg += '\\nKeine Brand Templates", b"msg += '\\\\nKeine Brand Templates"),
]

for old, new in replacements:
    if old in raw:
        raw = raw.replace(old, new, 1)
        count += 1

if count > 0:
    with open(WS, 'wb') as f:
        f.write(raw)
    print(f"OK: {count} JS-Newline-Escapes repariert")
else:
    print("Keine Matches gefunden — prüfe manuell")
