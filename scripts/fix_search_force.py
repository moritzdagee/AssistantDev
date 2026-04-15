#!/usr/bin/env python3
"""Fix search to use force_search=True for explicit search commands."""

WEB_SERVER = "/Users/moritzcremer/AssistantDev/src/web_server.py"

with open(WEB_SERVER, "r", encoding="utf-8") as f:
    code = f.read()

old = """        intent = QueryParser.parse(effective_query)
        if not intent.is_search:
            # Force search intent for explicit /find commands
            intent.is_search = True
            intent.keywords = [kw.lower() for kw in effective_query.split() if len(kw) >= 2]"""

new = """        intent = QueryParser.parse(effective_query, force_search=True)"""

if old in code:
    code = code.replace(old, new)
    with open(WEB_SERVER, "w", encoding="utf-8") as f:
        f.write(code)
    print("✓ QueryParser.parse mit force_search=True")
else:
    print("✗ Pattern nicht gefunden")
    import sys; sys.exit(1)
