#!/usr/bin/env python3
"""Fix: Die JS-Regex in ttGetContent enthaelt Unicode-Escapes \\u{...} die
Python beim Laden der HTML-String-Template (triple-quoted) als Unicode-Escape
interpretiert und mit SyntaxError abbricht. Ersatz durch ASCII-only Regex."""
import os, sys
WS = os.path.expanduser("~/AssistantDev/src/web_server.py")
OLD = "    var name = txt.replace(/[\\s\\u{1f3ac}\\u{1f5bc}\\ufe0f\\u{1f9e0}]+$/u, '').trim();"
NEW = "    var name = txt.replace(/[^a-zA-Z0-9().\\s-]+$/g, '').trim();"
src = open(WS).read()
if NEW in src:
    print("Schon gepatcht.")
    sys.exit(0)
c = src.count(OLD)
if c != 1:
    print(f"FEHLER: {c} Vorkommen gefunden (erwarte 1)")
    # Zeige erste 300 Zeichen rund um die vermutete Stelle
    idx = src.find("var name = txt.replace(/")
    if idx != -1:
        print("Snippet:", repr(src[idx:idx+120]))
    sys.exit(2)
open(WS, 'w').write(src.replace(OLD, NEW))
print("OK")
