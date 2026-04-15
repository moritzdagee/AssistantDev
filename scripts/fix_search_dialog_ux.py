#!/usr/bin/env python3
"""
Such-Dialog UX-Verbesserungen:
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

# ═══════════════════════════════════════════════════════════════
# Aenderung 1: Trefferanzahl prominent + Aenderung 3: Toggle-Button
# Im HTML: nach search-subfilter-bar, vor search-results-list
# ═══════════════════════════════════════════════════════════════

old_html_section = '''    <div id="search-subfilter-bar"></div>
    <div id="search-results-list"></div>'''

new_html_section = '''    <div id="search-subfilter-bar"></div>
    <div id="search-info-bar" style="padding:4px 18px;display:flex;align-items:center;gap:12px;font-size:13px;color:#aaa;">
      <span id="search-hit-count" style="font-weight:600;color:#e0e0e0;"></span>
      <button id="search-toggle-all-btn" onclick="toggleAllSearchCheckboxes()" style="background:none;border:1px solid #555;color:#ccc;padding:3px 10px;border-radius:4px;font-size:12px;cursor:pointer;font-family:Inter,sans-serif;">Alle markieren</button>
    </div>
    <div id="search-results-list"></div>'''

if old_html_section in code:
    code = code.replace(old_html_section, new_html_section)
    changes += 1
    print("✓ Aenderung 1+3: Trefferanzahl-Bar + Toggle-Button HTML eingefuegt")
else:
    print("✗ HTML Section Pattern nicht gefunden")
    sys.exit(1)

# ═══════════════════════════════════════════════════════════════
# Aenderung 2a: Footer Counter-Label 5 → 50
# ═══════════════════════════════════════════════════════════════

old_counter = '0 / 5 ausgewaehlt'
new_counter = '0 / 50 ausgewaehlt'

if old_counter in code:
    code = code.replace(old_counter, new_counter)
    changes += 1
    print("✓ Aenderung 2a: Counter-Label 5 → 50")
else:
    print("✗ Counter-Label Pattern nicht gefunden")
    sys.exit(1)

# ═══════════════════════════════════════════════════════════════
# Aenderung 2b: "Alle laden"-Button Label
# ═══════════════════════════════════════════════════════════════

old_all_btn = "Alle laden (max 5)"
new_all_btn = "Alle laden (max 50)"

if old_all_btn in code:
    code = code.replace(old_all_btn, new_all_btn)
    changes += 1
    print("✓ Aenderung 2b: Alle-laden Button Label 5 → 50")
else:
    print("✗ Alle-laden Button Pattern nicht gefunden")
    sys.exit(1)

# ═══════════════════════════════════════════════════════════════
# Aenderung 2c: updateSelectionCounter JS – max 5 → max 50
# ═══════════════════════════════════════════════════════════════

old_counter_js = "if (counter) counter.textContent = checked + ' ausgewaehlt (max 5)';"
new_counter_js = "if (counter) counter.textContent = checked + ' ausgewaehlt (max 50)';"

if old_counter_js in code:
    code = code.replace(old_counter_js, new_counter_js)
    changes += 1
    print("✓ Aenderung 2c: JS Counter 5 → 50")
else:
    print("✗ JS Counter Pattern nicht gefunden")
    sys.exit(1)

# ═══════════════════════════════════════════════════════════════
# Aenderung 2d: Checkbox-Limit in onSearchCheckboxChange – 5 → 50
# ═══════════════════════════════════════════════════════════════

old_checkbox_limit = "if (cb.checked && checked > 5) { cb.checked = false; return; }"
new_checkbox_limit = "if (cb.checked && checked > 50) { cb.checked = false; return; }"

if old_checkbox_limit in code:
    code = code.replace(old_checkbox_limit, new_checkbox_limit)
    changes += 1
    print("✓ Aenderung 2d: Checkbox-Limit 5 → 50")
else:
    print("✗ Checkbox-Limit Pattern nicht gefunden")
    sys.exit(1)

# ═══════════════════════════════════════════════════════════════
# Aenderung 2e: loadAllResults – slice(0, 5) → slice(0, 50)
# ═══════════════════════════════════════════════════════════════

old_load_all = "const paths = _searchResults.filter(r => !r.is_notification).slice(0, 5).map(r => r.path);"
new_load_all = "const paths = _searchResults.filter(r => !r.is_notification).slice(0, 50).map(r => r.path);"

if old_load_all in code:
    code = code.replace(old_load_all, new_load_all)
    changes += 1
    print("✓ Aenderung 2e: loadAllResults slice 5 → 50")
else:
    print("✗ loadAllResults Pattern nicht gefunden")
    sys.exit(1)

# ═══════════════════════════════════════════════════════════════
# Aenderung 2f: loadSelectedResults – paths.length < 5 → < 50
# ═══════════════════════════════════════════════════════════════

old_selected_limit = "if (_searchResults[idx] && paths.length < 5) paths.push(_searchResults[idx].path);"
new_selected_limit = "if (_searchResults[idx] && paths.length < 50) paths.push(_searchResults[idx].path);"

if old_selected_limit in code:
    code = code.replace(old_selected_limit, new_selected_limit)
    changes += 1
    print("✓ Aenderung 2f: loadSelectedResults Limit 5 → 50")
else:
    print("✗ loadSelectedResults Pattern nicht gefunden")
    sys.exit(1)

# ═══════════════════════════════════════════════════════════════
# Aenderung 2g: Backend /load_selected_files – [:5] → [:50]
# ═══════════════════════════════════════════════════════════════

old_backend_limit = "paths = request.json.get('paths', [])[:5]  # Max 5 files"
new_backend_limit = "paths = request.json.get('paths', [])[:50]  # Max 50 files"

if old_backend_limit in code:
    code = code.replace(old_backend_limit, new_backend_limit)
    changes += 1
    print("✓ Aenderung 2g: Backend Limit 5 → 50")
else:
    print("✗ Backend Limit Pattern nicht gefunden")
    sys.exit(1)

# ═══════════════════════════════════════════════════════════════
# Aenderung 3: toggleAllSearchCheckboxes JS-Funktion +
# Aenderung 1: Trefferanzahl Update in showSearchDialog +
# Aenderung 4: Escape-Handler
# Einfuegen nach closeSearchDialog
# ═══════════════════════════════════════════════════════════════

old_close_fn = '''function closeSearchDialog(sendAnyway) {
  document.getElementById('search-overlay').classList.remove('show');
  if (sendAnyway && _pendingSearchMsg) {
    doSendChat(_pendingSearchMsg);
  }
  _pendingSearchMsg = null;
  _searchResults = [];
}'''

new_close_fn = '''function closeSearchDialog(sendAnyway) {
  document.getElementById('search-overlay').classList.remove('show');
  document.removeEventListener('keydown', _searchEscHandler);
  if (sendAnyway && _pendingSearchMsg) {
    doSendChat(_pendingSearchMsg);
  }
  _pendingSearchMsg = null;
  _searchResults = [];
}

function _searchEscHandler(e) {
  if (e.key === 'Escape') { e.preventDefault(); closeSearchDialog(true); }
}

function toggleAllSearchCheckboxes() {
  const cbs = document.querySelectorAll('#search-results-list input[type=checkbox]');
  const allChecked = Array.from(cbs).filter(cb => !cb.dataset.notif).every(cb => cb.checked);
  let count = 0;
  cbs.forEach(cb => {
    if (cb.dataset.notif) return;
    if (allChecked) { cb.checked = false; }
    else if (count < 50) { cb.checked = true; count++; }
  });
  updateSelectionCounter();
  updateToggleAllBtn();
}

function updateToggleAllBtn() {
  const btn = document.getElementById('search-toggle-all-btn');
  if (!btn) return;
  const cbs = document.querySelectorAll('#search-results-list input[type=checkbox]');
  const nonNotif = Array.from(cbs).filter(cb => !cb.dataset.notif);
  const allChecked = nonNotif.length > 0 && nonNotif.every(cb => cb.checked);
  btn.textContent = allChecked ? 'Alle abwaehlen' : 'Alle markieren';
}'''

if old_close_fn in code:
    code = code.replace(old_close_fn, new_close_fn)
    changes += 1
    print("✓ Aenderung 3+4: toggleAllSearchCheckboxes + Escape-Handler eingefuegt")
else:
    print("✗ closeSearchDialog Pattern nicht gefunden")
    sys.exit(1)

# ═══════════════════════════════════════════════════════════════
# Aenderung 1b + 4b: showSearchDialog – Trefferanzahl + Escape-Listener
# ═══════════════════════════════════════════════════════════════

old_show_dialog = "function showSearchDialog(results, query, isGlobal) {\n  _searchResults = results;\n  _isGlobalSearch = isGlobal || false;\n  _currentSearchFilter = 'all';\n  const overlay = document.getElementById('search-overlay');\n  if (isGlobal) {\n    document.getElementById('search-panel-title').textContent = '\U0001f310 Globale Suche \\\\u2014 ' + results.length + ' Datei(en)';\n  } else {\n    document.getElementById('search-panel-title').textContent = '\U0001f50d ' + results.length + ' Datei(en) gefunden';\n  }\n  document.getElementById('search-panel-count').textContent = 'Suche: ' + query;\n  document.querySelectorAll('.search-filter-btn').forEach(b => b.classList.toggle('active', b.dataset.filter === 'all'));\n  document.getElementById('search-subfilter-bar').classList.remove('show');\n  rerenderSearchResults();\n  overlay.classList.add('show');\n}"

new_show_dialog = "function showSearchDialog(results, query, isGlobal) {\n  _searchResults = results;\n  _isGlobalSearch = isGlobal || false;\n  _currentSearchFilter = 'all';\n  const overlay = document.getElementById('search-overlay');\n  if (isGlobal) {\n    document.getElementById('search-panel-title').textContent = '\U0001f310 Globale Suche \\\\u2014 ' + results.length + ' Datei(en)';\n  } else {\n    document.getElementById('search-panel-title').textContent = '\U0001f50d ' + results.length + ' Datei(en) gefunden';\n  }\n  document.getElementById('search-panel-count').textContent = 'Suche: ' + query;\n  var hitCount = document.getElementById('search-hit-count');\n  if (hitCount) hitCount.textContent = results.length + ' Dateien gefunden';\n  document.querySelectorAll('.search-filter-btn').forEach(b => b.classList.toggle('active', b.dataset.filter === 'all'));\n  document.getElementById('search-subfilter-bar').classList.remove('show');\n  rerenderSearchResults();\n  overlay.classList.add('show');\n  document.addEventListener('keydown', _searchEscHandler);\n}"

if old_show_dialog in code:
    code = code.replace(old_show_dialog, new_show_dialog)
    changes += 1
    print("✓ Aenderung 1b+4b: Trefferanzahl + Escape-Listener in showSearchDialog")
else:
    print("✗ showSearchDialog Pattern nicht gefunden – versuche Unicode-Variante...")
    # Die Emojis koennten als raw characters statt Unicode escapes vorliegen
    sys.exit(1)

# ═══════════════════════════════════════════════════════════════
# Aenderung 3b: updateSelectionCounter soll auch Toggle-Button updaten
# ═══════════════════════════════════════════════════════════════

old_update_counter = """function updateSelectionCounter() {
  const checked = document.querySelectorAll('#search-results-list input[type=checkbox]:checked').length;
  const counter = document.getElementById('search-selection-counter');
  if (counter) counter.textContent = checked + ' ausgewaehlt (max 50)';
}"""

new_update_counter = """function updateSelectionCounter() {
  const checked = document.querySelectorAll('#search-results-list input[type=checkbox]:checked').length;
  const counter = document.getElementById('search-selection-counter');
  if (counter) counter.textContent = checked + ' ausgewaehlt (max 50)';
  updateToggleAllBtn();
}"""

if old_update_counter in code:
    code = code.replace(old_update_counter, new_update_counter)
    changes += 1
    print("✓ Aenderung 3b: updateSelectionCounter ruft updateToggleAllBtn auf")
else:
    print("✗ updateSelectionCounter Pattern nicht gefunden")
    sys.exit(1)

# ═══════════════════════════════════════════════════════════════
# Aenderung 3c: Checkbox-Items muessen data-notif Attribut haben fuer Notifikationen
# Suche nach der Stelle wo Checkboxen erstellt werden
# ═══════════════════════════════════════════════════════════════

old_checkbox_create = "cb.onchange = function() { onSearchCheckboxChange(this); };"
new_checkbox_create = "cb.onchange = function() { onSearchCheckboxChange(this); };\n    if (r.is_notification) cb.dataset.notif = '1';"

if old_checkbox_create in code:
    code = code.replace(old_checkbox_create, new_checkbox_create)
    changes += 1
    print("✓ Aenderung 3c: Notifikation-Checkboxen mit data-notif markiert")
else:
    print("✗ Checkbox-Create Pattern nicht gefunden")
    sys.exit(1)

# ═══════════════════════════════════════════════════════════════
# Schreiben
# ═══════════════════════════════════════════════════════════════

with open(WEB_SERVER, "w", encoding="utf-8") as f:
    f.write(code)

print(f"\n{'='*50}")
print(f"Gesamt: {changes} Aenderungen geschrieben")
