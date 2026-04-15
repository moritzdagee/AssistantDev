#!/usr/bin/env python3
"""Fix empty /find and /find_global: always use /search_preview for recent files."""

SRC = "/Users/moritzcremer/AssistantDev/src/web_server.py"

with open(SRC, 'r') as f:
    code = f.read()

changes = 0

# Fix 1: For empty queries, always use /search_preview (not global)
# because recent files are per-agent anyway
old = """        const payload2 = {query:'', session_id:SESSION_ID, recent:true};
        if (searchType) payload2.type = searchType;
        if (isGlobal) { payload2.requesting_agent = getAgentName(); }
        else { payload2.agent = getAgentName(); }
        const endpoint2 = isGlobal ? '/global_search_preview' : '/search_preview';"""

new = """        const payload2 = {query:'', session_id:SESSION_ID, recent:true};
        if (searchType) payload2.type = searchType;
        payload2.agent = getAgentName();
        const endpoint2 = '/search_preview';"""

if old in code:
    code = code.replace(old, new, 1)
    changes += 1
    print("1. Empty query always uses /search_preview")
else:
    print("WARN: empty query endpoint not found")

# Fix 2: Also handle /find (without _global) when sent bare
# The issue is the regex now matches /find and /find_global with optional query
# but if user types just "/find" or "/find_global", rawQuery = '' and searchType = null
# Let's also make sure the status shows correctly
old = """        } else {
          addStatusMsg('Keine Dateien gefunden' + typeInfo2);"""
new = """        } else {
          addStatusMsg('Keine Dateien gefunden' + typeInfo2 + ' (Index leer oder nicht aufgebaut)');"""
if old in code:
    code = code.replace(old, new, 1)
    changes += 1
    print("2. Better empty result message")

with open(SRC, 'w') as f:
    f.write(code)

print(f"\n{changes} fixes applied.")
