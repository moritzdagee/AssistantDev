#!/usr/bin/env python3
"""
UX improvements for web_server.py:
1. Sidebar default visible + Alt+P toggle
2. Category chips + realtime search for /find
3. Remove "Datei aus Memory suchen" field
4. Empty search → recent files
5. (Fulltext search already works — no change needed)
6. Keyboard shortcuts
"""

SRC = "/Users/moritzcremer/AssistantDev/src/web_server.py"

with open(SRC, 'r') as f:
    code = f.read()

changes = 0

# ═══════════════════════════════════════════════════════════════════════════════
# 1. SIDEBAR DEFAULT VISIBLE
# ═══════════════════════════════════════════════════════════════════════════════

# 1a: CSS — sidebar starts with width instead of 0
old = "  #sidebar { width:0; min-width:0; background:#141414;"
new = "  #sidebar { width:30%; min-width:280px; background:#141414;"
if old in code:
    code = code.replace(old, new, 1)
    changes += 1
    print("1a. Sidebar CSS: default visible")
else:
    print("WARN: sidebar CSS not found")

# 1b: JS — sidebarOpen default true
old = "let sidebarOpen = false;"
new = "let sidebarOpen = true;"
if old in code:
    code = code.replace(old, new, 1)
    changes += 1
    print("1b. sidebarOpen = true")
else:
    print("WARN: sidebarOpen not found")

# 1c: Prompt button — add shortcut label
old = """<button id="prompt-btn" onclick="toggleSidebar()">\u2630 Prompt</button>"""
new = """<button id="prompt-btn" onclick="toggleSidebar()">\u2630 Prompt <span class="shortcut-label">[P]</span></button>"""
if old in code:
    code = code.replace(old, new, 1)
    changes += 1
    print("1c. Prompt button shortcut label")
else:
    print("WARN: prompt-btn not found")

# ═══════════════════════════════════════════════════════════════════════════════
# 2. SHORTCUT LABELS ON ALL BUTTONS
# ═══════════════════════════════════════════════════════════════════════════════

# New conversation button
old = """onclick="newSession()" style="background:#2a3a2a;border-color:#4a6a4a;color:#a0d090;">+ Neu</button>"""
new = """onclick="newSession()" style="background:#2a3a2a;border-color:#4a6a4a;color:#a0d090;">+ Neu <span class="shortcut-label">[N]</span></button>"""
if old in code:
    code = code.replace(old, new, 1)
    changes += 1
    print("2a. Neu button shortcut label")

# Agent button
old = """onclick="showAgentModal()">Agent wechseln</button>"""
new = """onclick="showAgentModal()">Agent <span class="shortcut-label">[A]</span></button>"""
if old in code:
    code = code.replace(old, new, 1)
    changes += 1
    print("2b. Agent button shortcut label")

# Send button (Ctrl+Enter)
old = """<button id="send-btn" """
new = """<button id="send-btn" title="Ctrl+Enter" """
if old in code:
    code = code.replace(old, new, 1)
    changes += 1
    print("2c. Send button title")

# File upload button
old = """class="tool-btn" onclick="document.getElementById('file-input').click()">+ Datei</button>"""
new = """class="tool-btn" onclick="document.getElementById('file-input').click()">+ Datei <span class="shortcut-label">[U]</span></button>"""
if old in code:
    code = code.replace(old, new, 1)
    changes += 1
    print("2d. File upload shortcut label")

# ═══════════════════════════════════════════════════════════════════════════════
# 3. ADD SHORTCUT-LABEL CSS
# ═══════════════════════════════════════════════════════════════════════════════

old = "  .section-copy-btn:hover { opacity:1; color:#f0c060; border-color:#f0c060; }"
new = """  .section-copy-btn:hover { opacity:1; color:#f0c060; border-color:#f0c060; }
  .shortcut-label { opacity:0.35; font-size:9px; font-weight:400; margin-left:2px; }
  #find-chips-bar { display:none; padding:6px 0 4px; gap:6px; flex-wrap:wrap; align-items:center; }
  #find-chips-bar.visible { display:flex; }
  .find-chip { padding:4px 10px; background:#222; border:1px solid #444; border-radius:14px; font-size:12px; color:#aaa; cursor:pointer; font-family:Inter,sans-serif; transition:all 0.15s; white-space:nowrap; }
  .find-chip:hover { border-color:#f0c060; color:#f0c060; }
  .find-chip.active { border-color:#f0c060; color:#f0c060; background:#2a2a1a; }
  .find-chip .chip-shortcut { opacity:0.4; font-size:9px; margin-left:3px; }
  #find-live-dropdown { display:none; position:absolute; bottom:100%; left:0; right:0; background:#1a1a1a; border:1px solid #333; border-radius:8px; margin-bottom:4px; max-height:280px; overflow-y:auto; z-index:202; font-family:Inter,sans-serif; }
  .find-live-item { padding:8px 14px; cursor:pointer; color:#ccc; font-size:13px; border-bottom:1px solid #222; display:flex; justify-content:space-between; }
  .find-live-item:hover, .find-live-item.active { background:#252525; color:#fff; }
  .find-live-item .flr-name { flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .find-live-item .flr-type { font-size:10px; color:#666; margin-left:8px; white-space:nowrap; }"""
if old in code:
    code = code.replace(old, new, 1)
    changes += 1
    print("3. Shortcut-label + find-chips CSS")
else:
    print("WARN: section-copy-btn CSS not found")

# ═══════════════════════════════════════════════════════════════════════════════
# 4. REMOVE "Datei aus Memory suchen" FIELD (HTML)
# ═══════════════════════════════════════════════════════════════════════════════

old = """        <div id="file-ac-wrap">
          <input type="text" id="file-ac-input" placeholder="Datei aus Memory suchen..." oninput="onFileAcInput(this.value)" onkeydown="onFileAcKey(event)" autocomplete="off" />
          <div id="file-ac-dropdown"></div>
        </div>"""
new = ""  # Remove entirely
if old in code:
    code = code.replace(old, new, 1)
    changes += 1
    print("4. file-ac-wrap HTML removed")
else:
    print("WARN: file-ac-wrap HTML not found")

# ═══════════════════════════════════════════════════════════════════════════════
# 5. ADD FIND-CHIPS-BAR AND FIND-LIVE-DROPDOWN (HTML)
# ═══════════════════════════════════════════════════════════════════════════════

# Insert the chips bar and live dropdown right before the input row
old = """      <div id="input-row">"""
new = """      <div id="find-chips-bar">
        <span style="font-size:10px;color:#555;margin-right:4px;">Typ:</span>
        <span class="find-chip" data-cat="email" onclick="toggleFindChip('email')">\u2709 E-Mail<span class="chip-shortcut">[1]</span></span>
        <span class="find-chip" data-cat="webclip" onclick="toggleFindChip('webclip')">\U0001f310 Web Clip<span class="chip-shortcut">[2]</span></span>
        <span class="find-chip" data-cat="document" onclick="toggleFindChip('document')">\U0001f4c4 Dokument<span class="chip-shortcut">[3]</span></span>
        <span class="find-chip" data-cat="conversation" onclick="toggleFindChip('conversation')">\U0001f4ac Konversation<span class="chip-shortcut">[4]</span></span>
        <span class="find-chip" data-cat="screenshot" onclick="toggleFindChip('screenshot')">\U0001f4f8 Screenshot<span class="chip-shortcut">[5]</span></span>
      </div>
      <div id="input-row" style="position:relative;">
        <div id="find-live-dropdown"></div>"""
if old in code:
    code = code.replace(old, new, 1)
    changes += 1
    print("5. find-chips-bar + find-live-dropdown HTML added")
else:
    print("WARN: input-row HTML not found")

# ═══════════════════════════════════════════════════════════════════════════════
# 6. ADD KEYBOARD SHORTCUTS + FIND CHIPS JS (after onKey function)
# ═══════════════════════════════════════════════════════════════════════════════

old = """// \u2500\u2500\u2500 SEND \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"""

if old not in code:
    # Try to find the line differently
    old = "// ─── SEND "
    new_js_block = """// ─── KEYBOARD SHORTCUTS (GLOBAL) ─────────────────────────────────────────────
let _findActiveChip = null;
let _findDebounceTimer = null;
let _findLiveIdx = -1;
let _findLiveResults = [];

document.addEventListener('keydown', function(e) {
  // Skip if inside input fields (except for our specific shortcuts)
  const tag = document.activeElement.tagName;
  const inInput = (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT');

  if (e.altKey && !e.ctrlKey && !e.metaKey) {
    switch(e.key.toLowerCase()) {
      case 'p': e.preventDefault(); toggleSidebar(); return;
      case 'n': e.preventDefault(); newSession(); return;
      case 'a': e.preventDefault(); showAgentModal(); return;
      case 'm': e.preventDefault(); document.getElementById('model-select').focus(); return;
      case 'f': e.preventDefault(); var inp=document.getElementById('msg-input'); inp.focus(); inp.value='/find '; onInputHandler(inp); return;
      case 'u': e.preventDefault(); document.getElementById('file-input').click(); return;
      case 'c': e.preventDefault(); copyLastAssistantMessage(); return;
      case 's': e.preventDefault(); saveConversation(); return;
      case '1': if (isFindChipsVisible()) { e.preventDefault(); toggleFindChip('email'); } return;
      case '2': if (isFindChipsVisible()) { e.preventDefault(); toggleFindChip('webclip'); } return;
      case '3': if (isFindChipsVisible()) { e.preventDefault(); toggleFindChip('document'); } return;
      case '4': if (isFindChipsVisible()) { e.preventDefault(); toggleFindChip('conversation'); } return;
      case '5': if (isFindChipsVisible()) { e.preventDefault(); toggleFindChip('screenshot'); } return;
    }
  }
  // Ctrl+Enter to send from anywhere
  if (e.ctrlKey && e.key === 'Enter' && !e.altKey && !e.metaKey) {
    e.preventDefault();
    sendMessage();
  }
});

function copyLastAssistantMessage() {
  var msgs = document.querySelectorAll('.msg.assistant .bubble');
  if (msgs.length) {
    var last = msgs[msgs.length-1];
    navigator.clipboard.writeText(last.innerText).catch(function(){});
    addStatusMsg('Letzte Antwort kopiert');
  }
}

function isFindChipsVisible() {
  var bar = document.getElementById('find-chips-bar');
  return bar && bar.classList.contains('visible');
}

function showFindChips() {
  var bar = document.getElementById('find-chips-bar');
  if (bar) bar.classList.add('visible');
}

function hideFindChips() {
  var bar = document.getElementById('find-chips-bar');
  if (bar) bar.classList.remove('visible');
  _findActiveChip = null;
  document.querySelectorAll('.find-chip').forEach(c => c.classList.remove('active'));
  hideFindLiveDropdown();
}

function toggleFindChip(cat) {
  if (_findActiveChip === cat) {
    _findActiveChip = null;
    document.querySelectorAll('.find-chip').forEach(c => c.classList.remove('active'));
  } else {
    _findActiveChip = cat;
    document.querySelectorAll('.find-chip').forEach(c => {
      c.classList.toggle('active', c.dataset.cat === cat);
    });
  }
  // Update the input if in /find mode
  var inp = document.getElementById('msg-input');
  var val = inp.value;
  var m = val.match(/^\\/find(?:_global)?/);
  if (m) {
    var prefix = m[0];
    var knownTypes = ['email','webclip','screenshot','contact','document','conversation'];
    var rest = val.substring(prefix.length).trim();
    var firstWord = rest.split(/\\s+/)[0]||'';
    if (knownTypes.includes(firstWord.toLowerCase())) rest = rest.substring(firstWord.length).trim();
    inp.value = prefix + (_findActiveChip ? ' ' + _findActiveChip : '') + (rest ? ' ' + rest : ' ');
    inp.focus();
    triggerFindLiveSearch();
  }
}

function hideFindLiveDropdown() {
  var dd = document.getElementById('find-live-dropdown');
  if (dd) dd.style.display = 'none';
  _findLiveIdx = -1;
  _findLiveResults = [];
}

function triggerFindLiveSearch() {
  clearTimeout(_findDebounceTimer);
  _findDebounceTimer = setTimeout(doFindLiveSearch, 300);
}

async function doFindLiveSearch() {
  var inp = document.getElementById('msg-input');
  var val = inp.value;
  var m = val.match(/^\\/find(_global)?\\s+(\\S+\\s+)?(.*)/i);
  if (!m) { hideFindLiveDropdown(); return; }
  var isGlobal = !!m[1];
  var typePart = (m[2]||'').trim();
  var queryPart = (m[3]||'').trim();
  if (!queryPart || queryPart.length < 2) { hideFindLiveDropdown(); return; }

  try {
    var agent = getAgentName();
    var url = '/api/memory-files-search?q=' + encodeURIComponent(queryPart) + '&agent=' + encodeURIComponent(agent);
    var r = await fetch(url);
    var data = await r.json();
    if (!data || !data.length) { hideFindLiveDropdown(); return; }

    _findLiveResults = data.slice(0, 8);
    _findLiveIdx = -1;
    var dd = document.getElementById('find-live-dropdown');
    dd.innerHTML = '<div style="padding:4px 14px;font-size:10px;color:#555;">' + _findLiveResults.length + ' Treffer | \u2191\u2193 navigieren, Enter auswaehlen, Esc schliessen</div>';
    _findLiveResults.forEach(function(item, i) {
      var div = document.createElement('div');
      div.className = 'find-live-item';
      div.innerHTML = '<span class="flr-name">' + escHtml(item.filename || item.name || '') + '</span><span class="flr-type">' + escHtml(item.snippet || '').substring(0,40) + '</span>';
      div.onmousedown = function(e) { e.preventDefault(); selectFindLiveItem(i); };
      dd.appendChild(div);
    });
    dd.style.display = 'block';
  } catch(e) {
    hideFindLiveDropdown();
  }
}

function selectFindLiveItem(idx) {
  if (idx < 0 || idx >= _findLiveResults.length) return;
  var item = _findLiveResults[idx];
  var inp = document.getElementById('msg-input');
  var val = inp.value;
  var m = val.match(/^\\/find(?:_global)?/);
  var prefix = m ? m[0] : '/find';
  var typePart = _findActiveChip ? ' ' + _findActiveChip : '';
  inp.value = prefix + typePart + ' ' + (item.filename || item.name || '');
  hideFindLiveDropdown();
  inp.focus();
}

function onFindLiveKey(e) {
  var dd = document.getElementById('find-live-dropdown');
  if (!dd || dd.style.display === 'none' || !_findLiveResults.length) return false;
  var items = dd.querySelectorAll('.find-live-item');
  if (e.key === 'ArrowDown') { e.preventDefault(); _findLiveIdx = Math.min(_findLiveIdx+1, items.length-1); items.forEach(function(it,i){it.classList.toggle('active', i===_findLiveIdx);}); return true; }
  if (e.key === 'ArrowUp') { e.preventDefault(); _findLiveIdx = Math.max(_findLiveIdx-1, 0); items.forEach(function(it,i){it.classList.toggle('active', i===_findLiveIdx);}); return true; }
  if (e.key === 'Enter' && _findLiveIdx >= 0) { e.preventDefault(); selectFindLiveItem(_findLiveIdx); return true; }
  if (e.key === 'Escape') { hideFindLiveDropdown(); return true; }
  return false;
}

// ─── SEND """

    if old in code:
        idx = code.index(old)
        code = code[:idx] + new_js_block + code[idx + len(old):]
        changes += 1
        print("6. Keyboard shortcuts + find chips JS added")
    else:
        print("WARN: SEND marker not found")

# ═══════════════════════════════════════════════════════════════════════════════
# 7. UPDATE onKey TO INCLUDE FIND-LIVE KEY HANDLER
# ═══════════════════════════════════════════════════════════════════════════════

old = """function onKey(e) {
  const input = document.getElementById('msg-input');
  // Slash-command autocomplete navigation
  if (onTypeAcKey(e, input)) return;
  if (onSlashAcKey(e, input)) return;
  if (e.key==='Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
}"""

new = """function onKey(e) {
  const input = document.getElementById('msg-input');
  if (onFindLiveKey(e)) return;
  if (onTypeAcKey(e, input)) return;
  if (onSlashAcKey(e, input)) return;
  if (e.key==='Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
}"""

if old in code:
    code = code.replace(old, new, 1)
    changes += 1
    print("7. onKey updated with find-live handler")
else:
    print("WARN: onKey function not found")

# ═══════════════════════════════════════════════════════════════════════════════
# 8. UPDATE onInputHandler TO SHOW FIND CHIPS + TRIGGER LIVE SEARCH
# ═══════════════════════════════════════════════════════════════════════════════

old = """function onInputHandler(el) {
  autoResize(el);
  const val = el.value;
  // Show slash dropdown when user types just "/"
  if (val === '/') { showSlashAutocomplete(el); hideTypeAutocomplete(); return; }
  // Show type dropdown after "/find " or "/find_global " (with trailing space, no type yet)
  const findPrefixMatch = val.match(/^\\/find(?:_global)?\\s+$/);
  if (findPrefixMatch) { hideSlashAutocomplete(); showTypeAutocomplete(el); return; }
  // While typing a partial type (e.g. "/find em"), filter type dropdown
  const partialTypeMatch = val.match(/^\\/find(?:_global)?\\s+(\\S+)$/);
  if (partialTypeMatch && _typeAcVisible) {
    const partial = partialTypeMatch[1].toLowerCase();
    const knownTypes = _SEARCH_TYPES.map(t => t.key);
    if (!knownTypes.includes(partial)) {
      // Partial match — keep dropdown visible for shortcut keys
      return;
    }
  }
  // Hide dropdowns when not in slash/type context
  if (!val.startsWith('/')) { hideSlashAutocomplete(); hideTypeAutocomplete(); }
  // If user has typed past the type selection, hide type dropdown
  const hasTypeAndQuery = val.match(/^\\/find(?:_global)?\\s+\\S+\\s+/);
  if (hasTypeAndQuery) { hideTypeAutocomplete(); }
}"""

new = """function onInputHandler(el) {
  autoResize(el);
  const val = el.value;
  // Show slash dropdown when user types just "/"
  if (val === '/') { showSlashAutocomplete(el); hideTypeAutocomplete(); hideFindChips(); return; }
  // Show find chips after "/find" or "/find_global" (with or without trailing space)
  const isFindMode = /^\\/find(?:_global)?(?:\\s|$)/i.test(val);
  if (isFindMode) {
    hideSlashAutocomplete();
    hideTypeAutocomplete();
    showFindChips();
    // Trigger live search if there's query text after the type
    const queryMatch = val.match(/^\\/find(?:_global)?\\s+(?:email|webclip|screenshot|contact|document|conversation)?\\s*(.*)/i);
    if (queryMatch && queryMatch[1] && queryMatch[1].length >= 2) {
      triggerFindLiveSearch();
    } else {
      hideFindLiveDropdown();
    }
    return;
  }
  // Hide everything when not in slash/find context
  if (!val.startsWith('/')) { hideSlashAutocomplete(); hideTypeAutocomplete(); hideFindChips(); }
}"""

if old in code:
    code = code.replace(old, new, 1)
    changes += 1
    print("8. onInputHandler rewritten for find chips + live search")
else:
    print("WARN: onInputHandler not found")

# ═══════════════════════════════════════════════════════════════════════════════
# 9. UPDATE sendMessage TO HANDLE EMPTY /find QUERIES (RECENT FILES)
# ═══════════════════════════════════════════════════════════════════════════════

old = """    const query = rawQuery;
    if (!query) { addStatusMsg('Bitte Suchbegriff eingeben'); return; }"""

new = """    const query = rawQuery;
    // Empty query — show recent files instead
    if (!query) {
      addMessage('user', text);
      scrollDown();
      const typeLabels2 = {email:'E-Mail',webclip:'Web Clip',screenshot:'Screenshot',document:'Dokument',conversation:'Konversation'};
      const typeInfo2 = searchType ? ' | Typ: ' + (typeLabels2[searchType]||searchType) : '';
      startTyping('Lade neueste Dateien' + typeInfo2 + '...');
      try {
        const payload2 = {query:'', session_id:SESSION_ID, recent:true};
        if (searchType) payload2.type = searchType;
        if (isGlobal) { payload2.requesting_agent = getAgentName(); }
        else { payload2.agent = getAgentName(); }
        const endpoint2 = isGlobal ? '/global_search_preview' : '/search_preview';
        const r2 = await fetch(endpoint2, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload2)});
        const data2 = await r2.json();
        stopTyping();
        if (data2.ok && data2.results && data2.results.length > 0) {
          _pendingSearchMsg = null;
          showSearchDialog(data2.results, 'Neueste' + typeInfo2, isGlobal);
        } else {
          addStatusMsg('Keine Dateien gefunden' + typeInfo2);
        }
      } catch(e2) { stopTyping(); addStatusMsg('Fehler: '+e2.message); }
      return;
    }"""

if old in code:
    code = code.replace(old, new, 1)
    changes += 1
    print("9. sendMessage: empty /find → recent files")
else:
    print("WARN: empty query guard not found")

# Also need to handle /find with ONLY a type and no additional query
# Currently regex requires (.+) after /find — change to allow optional match
old = """  const findGlobalMatch = text.match(/^\\/find_global\\s+(.+)/i);
  const findMatch = text.match(/^\\/find\\s+(.+)/i);
  if ((findGlobalMatch || findMatch) && getAgentName() !== 'Kein Agent') {"""
new = """  const findGlobalMatch = text.match(/^\\/find_global(?:\\s+(.*))?$/i);
  const findMatch = text.match(/^\\/find(?:\\s+(.*))?$/i);
  if ((findGlobalMatch || findMatch) && getAgentName() !== 'Kein Agent') {"""
if old in code:
    code = code.replace(old, new, 1)
    changes += 1
    print("9b. /find regex allows empty query")
else:
    print("WARN: find regex not found")

# Fix rawQuery to handle undefined group
old = "    let rawQuery = isGlobal ? findGlobalMatch[1] : findMatch[1];"
new = "    let rawQuery = (isGlobal ? findGlobalMatch[1] : findMatch[1]) || '';"
if old in code:
    code = code.replace(old, new, 1)
    changes += 1
    print("9c. rawQuery null safety")

# ═══════════════════════════════════════════════════════════════════════════════
# 10. BACKEND: /search_preview HANDLE EMPTY QUERY WITH RECENT FILES
# ═══════════════════════════════════════════════════════════════════════════════

old = """    if not state.get('speicher') or not query:
        return jsonify({'ok': False, 'results': []})
    try:
        from search_engine import QueryParser, HybridSearch, SearchIndex, normalize_unicode, get_or_build_index, extract_search_keywords, search_contacts"""

new = """    is_recent = request.json.get('recent', False)
    if not state.get('speicher'):
        return jsonify({'ok': False, 'results': []})
    if not query and not is_recent:
        return jsonify({'ok': False, 'results': []})
    try:
        from search_engine import QueryParser, HybridSearch, SearchIndex, normalize_unicode, get_or_build_index, extract_search_keywords, search_contacts, get_recent_files

        # Empty query with recent flag — return latest files
        if is_recent and not query:
            if search_type:
                recent = get_recent_files(state['speicher'], category=search_type, limit=10)
            else:
                recent = get_recent_files(state['speicher'], per_category=True, limit=3)
            items = []
            for r in recent:
                items.append({
                    'name': r['name'], 'path': r['path'], 'type': r.get('source_type','file'),
                    'source_type': r.get('source_type','file'), 'date': r.get('date',''),
                    'from': r.get('from',''), 'subject': r.get('subject',''),
                    'preview': r.get('preview',''), 'score': 0,
                    'from_person': False, 'is_notification': False,
                })
            return jsonify({'ok': True, 'results': items, 'query': 'Neueste Dateien', 'feedback': None})"""

if old in code:
    code = code.replace(old, new, 1)
    changes += 1
    print("10. Backend: /search_preview empty query → recent files")
else:
    print("WARN: search_preview empty query guard not found")

# ═══════════════════════════════════════════════════════════════════════════════
# WRITE
# ═══════════════════════════════════════════════════════════════════════════════

with open(SRC, 'w') as f:
    f.write(code)

print(f"\n{changes} Aenderungen geschrieben.")
