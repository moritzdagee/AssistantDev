#!/usr/bin/env python3
"""
1. Tab key selects first item in slash dropdown (no arrow navigation needed)
2. Add SVG favicon for Chrome tab
"""

SRC = "/Users/moritzcremer/AssistantDev/src/web_server.py"

with open(SRC, 'r') as f:
    code = f.read()

changes = 0

# ═══════════════════════════════════════════════════════════════════════════════
# 1. TAB selects first item when nothing is selected yet
# ═══════════════════════════════════════════════════════════════════════════════

old = """  if ((e.key === 'Enter' || e.key === 'Tab') && _slashAcIdx >= 0) { e.preventDefault(); var selItem = items[_slashAcIdx]; if (selItem) selectSlashCmd(inputEl, selItem.dataset.cmd); return true; }"""

new = """  if (e.key === 'Tab' && items.length > 0) { e.preventDefault(); var idx = _slashAcIdx >= 0 ? _slashAcIdx : 0; var selItem = items[idx]; if (selItem) selectSlashCmd(inputEl, selItem.dataset.cmd); return true; }
  if (e.key === 'Enter' && _slashAcIdx >= 0) { e.preventDefault(); var selItem = items[_slashAcIdx]; if (selItem) selectSlashCmd(inputEl, selItem.dataset.cmd); return true; }"""

if old in code:
    code = code.replace(old, new, 1)
    changes += 1
    print("1. Tab selects first slash dropdown item")
else:
    print("WARN: onSlashAcKey Tab/Enter not found")

# ═══════════════════════════════════════════════════════════════════════════════
# 2. Also fix Tab for type dropdown (find chips) — same pattern
# ═══════════════════════════════════════════════════════════════════════════════

# Find the onTypeAcKey Tab handler
old2 = "  if ((e.key === 'Enter' || e.key === 'Tab') && _typeAcIdx >= 0) { e.preventDefault(); selectTypeCmd(inputEl, _SEARCH_TYPES[_typeAcIdx].key); return true; }"
new2 = "  if (e.key === 'Tab' && items.length > 0) { e.preventDefault(); var tidx = _typeAcIdx >= 0 ? _typeAcIdx : 0; selectTypeCmd(inputEl, _SEARCH_TYPES[tidx].key); return true; }\n  if (e.key === 'Enter' && _typeAcIdx >= 0) { e.preventDefault(); selectTypeCmd(inputEl, _SEARCH_TYPES[_typeAcIdx].key); return true; }"
if old2 in code:
    code = code.replace(old2, new2, 1)
    changes += 1
    print("2. Tab selects first type dropdown item")

# ═══════════════════════════════════════════════════════════════════════════════
# 3. Also fix Tab for find-live dropdown
# ═══════════════════════════════════════════════════════════════════════════════

old3 = "  if (e.key === 'Enter' && _findLiveIdx >= 0) { e.preventDefault(); selectFindLiveItem(_findLiveIdx); return true; }"
new3 = "  if (e.key === 'Tab' && _findLiveResults.length > 0) { e.preventDefault(); selectFindLiveItem(_findLiveIdx >= 0 ? _findLiveIdx : 0); return true; }\n  if (e.key === 'Enter' && _findLiveIdx >= 0) { e.preventDefault(); selectFindLiveItem(_findLiveIdx); return true; }"
if old3 in code:
    code = code.replace(old3, new3, 1)
    changes += 1
    print("3. Tab selects first live search result")

# ═══════════════════════════════════════════════════════════════════════════════
# 4. Add favicon as inline SVG data URI
# ═══════════════════════════════════════════════════════════════════════════════

old_head = """<title>Assistant</title>
<link rel="preconnect" href="https://fonts.googleapis.com">"""

# Simple "A" letter favicon in gold (#f0c060) on dark background — matches the UI theme
favicon_svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="6" fill="%23111"/><text x="16" y="24" text-anchor="middle" font-family="system-ui,sans-serif" font-weight="700" font-size="22" fill="%23f0c060">A</text></svg>'

new_head = f"""<title>Assistant</title>
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,{favicon_svg}">
<link rel="preconnect" href="https://fonts.googleapis.com">"""

if old_head in code:
    code = code.replace(old_head, new_head, 1)
    changes += 1
    print("4. Favicon SVG added")
else:
    print("WARN: <title> block not found")

with open(SRC, 'w') as f:
    f.write(code)

print(f"\\n{changes} changes applied.")
