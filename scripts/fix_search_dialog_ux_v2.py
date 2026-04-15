#!/usr/bin/env python3
"""
Such-Dialog UX-Verbesserungen v2:
1. Trefferanzahl im Dialog prominent anzeigen
2. Datei-Limit 5 → 50 (Frontend + Backend)
3. "Alle markieren / Alle abwaehlen"-Toggle
4. Escape schliesst Such-Dialog
"""

import sys

WEB_SERVER = "/Users/moritzcremer/AssistantDev/src/web_server.py"

with open(WEB_SERVER, "r", encoding="utf-8") as f:
    code = f.read()

changes = 0
errors = []

def do_replace(old, new, label):
    global code, changes
    if old in code:
        code = code.replace(old, new)
        changes += 1
        print(f"\u2713 {label}")
        return True
    else:
        errors.append(label)
        print(f"\u2717 {label} – Pattern nicht gefunden!")
        return False

# ═══════════════════════════════════════════════════════════════
# 1+3: HTML – Trefferanzahl-Bar + Toggle-Button
# ═══════════════════════════════════════════════════════════════

do_replace(
    '    <div id="search-subfilter-bar"></div>\n    <div id="search-results-list"></div>',
    '    <div id="search-subfilter-bar"></div>\n    <div id="search-info-bar" style="padding:4px 18px;display:flex;align-items:center;gap:12px;font-size:13px;color:#aaa;">\n      <span id="search-hit-count" style="font-weight:600;color:#e0e0e0;"></span>\n      <button id="search-toggle-all-btn" onclick="toggleAllSearchCheckboxes()" style="background:none;border:1px solid #555;color:#ccc;padding:3px 10px;border-radius:4px;font-size:12px;cursor:pointer;font-family:Inter,sans-serif;">Alle markieren</button>\n    </div>\n    <div id="search-results-list"></div>',
    "1+3: Trefferanzahl-Bar + Toggle-Button HTML"
)

# ═══════════════════════════════════════════════════════════════
# 2a: Footer Counter-Label
# ═══════════════════════════════════════════════════════════════

do_replace('0 / 5 ausgewaehlt', '0 / 50 ausgewaehlt', "2a: Counter-Label 5->50")

# ═══════════════════════════════════════════════════════════════
# 2b: "Alle laden" Button Label
# ═══════════════════════════════════════════════════════════════

do_replace('Alle laden (max 5)', 'Alle laden (max 50)', "2b: Alle-laden Button 5->50")

# ═══════════════════════════════════════════════════════════════
# 2c: updateSelectionCounter JS
# ═══════════════════════════════════════════════════════════════

do_replace(
    "if (counter) counter.textContent = checked + ' ausgewaehlt (max 5)';",
    "if (counter) counter.textContent = checked + ' ausgewaehlt (max 50)';",
    "2c: JS Counter max 5->50"
)

# ═══════════════════════════════════════════════════════════════
# 2d: Checkbox-Limit
# ═══════════════════════════════════════════════════════════════

do_replace(
    "if (cb.checked && checked > 5) { cb.checked = false; return; }",
    "if (cb.checked && checked > 50) { cb.checked = false; return; }",
    "2d: Checkbox-Limit 5->50"
)

# ═══════════════════════════════════════════════════════════════
# 2e: loadAllResults slice
# ═══════════════════════════════════════════════════════════════

do_replace(
    ".filter(r => !r.is_notification).slice(0, 5).map(r => r.path);",
    ".filter(r => !r.is_notification).slice(0, 50).map(r => r.path);",
    "2e: loadAllResults slice 5->50"
)

# ═══════════════════════════════════════════════════════════════
# 2f: loadSelectedResults limit
# ═══════════════════════════════════════════════════════════════

do_replace(
    "if (_searchResults[idx] && paths.length < 5) paths.push(_searchResults[idx].path);",
    "if (_searchResults[idx] && paths.length < 50) paths.push(_searchResults[idx].path);",
    "2f: loadSelectedResults Limit 5->50"
)

# ═══════════════════════════════════════════════════════════════
# 2g: Backend limit
# ═══════════════════════════════════════════════════════════════

do_replace(
    "paths = request.json.get('paths', [])[:5]  # Max 5 files",
    "paths = request.json.get('paths', [])[:50]  # Max 50 files",
    "2g: Backend Limit 5->50"
)

# ═══════════════════════════════════════════════════════════════
# 3+4: closeSearchDialog erweitern + neue Funktionen
# ═══════════════════════════════════════════════════════════════

do_replace(
    "function closeSearchDialog(sendAnyway) {\n  document.getElementById('search-overlay').classList.remove('show');\n  if (sendAnyway && _pendingSearchMsg) {\n    doSendChat(_pendingSearchMsg);\n  }\n  _pendingSearchMsg = null;\n  _searchResults = [];\n}",
    "function closeSearchDialog(sendAnyway) {\n  document.getElementById('search-overlay').classList.remove('show');\n  document.removeEventListener('keydown', _searchEscHandler);\n  if (sendAnyway && _pendingSearchMsg) {\n    doSendChat(_pendingSearchMsg);\n  }\n  _pendingSearchMsg = null;\n  _searchResults = [];\n}\n\nfunction _searchEscHandler(e) {\n  if (e.key === 'Escape') { e.preventDefault(); closeSearchDialog(true); }\n}\n\nfunction toggleAllSearchCheckboxes() {\n  var cbs = document.querySelectorAll('#search-results-list input[type=checkbox]');\n  var nonNotif = Array.from(cbs).filter(function(cb) { return !cb.dataset.notif; });\n  var allChecked = nonNotif.length > 0 && nonNotif.every(function(cb) { return cb.checked; });\n  var count = 0;\n  nonNotif.forEach(function(cb) {\n    if (allChecked) { cb.checked = false; }\n    else if (count < 50) { cb.checked = true; count++; }\n  });\n  updateSelectionCounter();\n}\n\nfunction updateToggleAllBtn() {\n  var btn = document.getElementById('search-toggle-all-btn');\n  if (!btn) return;\n  var cbs = document.querySelectorAll('#search-results-list input[type=checkbox]');\n  var nonNotif = Array.from(cbs).filter(function(cb) { return !cb.dataset.notif; });\n  var allChecked = nonNotif.length > 0 && nonNotif.every(function(cb) { return cb.checked; });\n  btn.textContent = allChecked ? 'Alle abwaehlen' : 'Alle markieren';\n}",
    "3+4: closeSearchDialog + Escape + Toggle-Funktionen"
)

# ═══════════════════════════════════════════════════════════════
# 1b+4b: showSearchDialog – Trefferanzahl + Escape-Listener
# Use the exact text from the file
# ═══════════════════════════════════════════════════════════════

old_show = "  document.getElementById('search-panel-count').textContent = 'Suche: ' + query;\n  document.querySelectorAll('.search-filter-btn').forEach(b => b.classList.toggle('active', b.dataset.filter === 'all'));\n  document.getElementById('search-subfilter-bar').classList.remove('show');\n  rerenderSearchResults();\n  overlay.classList.add('show');\n}"

new_show = "  document.getElementById('search-panel-count').textContent = 'Suche: ' + query;\n  var hitCount = document.getElementById('search-hit-count');\n  if (hitCount) hitCount.textContent = results.length + ' Dateien gefunden';\n  document.querySelectorAll('.search-filter-btn').forEach(b => b.classList.toggle('active', b.dataset.filter === 'all'));\n  document.getElementById('search-subfilter-bar').classList.remove('show');\n  rerenderSearchResults();\n  overlay.classList.add('show');\n  document.addEventListener('keydown', _searchEscHandler);\n}"

do_replace(old_show, new_show, "1b+4b: Trefferanzahl + Escape-Listener in showSearchDialog")

# ═══════════════════════════════════════════════════════════════
# 3b: updateSelectionCounter → auch updateToggleAllBtn aufrufen
# ═══════════════════════════════════════════════════════════════

do_replace(
    "  if (counter) counter.textContent = checked + ' ausgewaehlt (max 50)';\n}",
    "  if (counter) counter.textContent = checked + ' ausgewaehlt (max 50)';\n  updateToggleAllBtn();\n}",
    "3b: updateSelectionCounter ruft updateToggleAllBtn auf"
)

# ═══════════════════════════════════════════════════════════════
# 3c: Checkboxen mit data-notif fuer Notifikationen markieren
# ═══════════════════════════════════════════════════════════════

do_replace(
    "cb.onchange = function() { onSearchCheckboxChange(this); };",
    "cb.onchange = function() { onSearchCheckboxChange(this); };\n    if (r.is_notification) cb.dataset.notif = '1';",
    "3c: Notifikation-Checkboxen mit data-notif markiert"
)

# ═══════════════════════════════════════════════════════════════
# Schreiben
# ═══════════════════════════════════════════════════════════════

if errors:
    print(f"\n{'='*50}")
    print(f"FEHLER: {len(errors)} Patterns nicht gefunden:")
    for e in errors:
        print(f"  - {e}")
    print("Datei wird NICHT geschrieben!")
    sys.exit(1)

with open(WEB_SERVER, "w", encoding="utf-8") as f:
    f.write(code)

print(f"\n{'='*50}")
print(f"Gesamt: {changes} Aenderungen erfolgreich geschrieben")
