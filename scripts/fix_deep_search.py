#!/usr/bin/env python3
"""Fix deep_memory_search to handle .json webclip files."""

SRC = "/Users/moritzcremer/AssistantDev/src/web_server.py"

with open(SRC, 'r') as f:
    code = f.read()

# Fix 1: Extension filter — add .json
old_filter = "        if not fname.endswith('.txt') and not fname.endswith('.eml'):"
new_filter = "        if not fname.endswith(('.txt', '.eml', '.json')):"

if old_filter in code:
    code = code.replace(old_filter, new_filter)
    print("Fix 1: Extension filter erweitert um .json")
else:
    print("WARN: Extension filter nicht gefunden")

# Fix 2: Content reading — handle JSON webclips
old_read = """        try:
            with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read(5000)
        except Exception:
            continue

        content_lower = content.lower()"""

new_read = """        try:
            with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
                raw = f.read(30000)
            # For JSON webclips: extract searchable text fields
            if fname.endswith('.json'):
                try:
                    parsed = json.loads(raw)
                    content = (parsed.get('title', '') + '\\n' +
                              parsed.get('url', '') + '\\n' +
                              parsed.get('full_text', ''))[:5000]
                except (json.JSONDecodeError, TypeError):
                    content = raw[:5000]
            else:
                content = raw[:5000]
        except Exception:
            continue

        content_lower = content.lower()"""

if old_read in code:
    code = code.replace(old_read, new_read)
    print("Fix 2: JSON-aware Content Reading eingefuegt")
else:
    print("WARN: Content Reading Pattern nicht gefunden")

with open(SRC, 'w') as f:
    f.write(code)

print("Fertig.")
