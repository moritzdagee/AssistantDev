#!/usr/bin/env python3
"""
Add type-filtered search dropdown + NLP keyword extraction to web_server.py.
Backend: type parameter on search endpoints
Frontend: type sub-dropdown after /find, sendMessage parsing
"""

SRC = "/Users/moritzcremer/AssistantDev/src/web_server.py"

with open(SRC, 'r') as f:
    code = f.read()

changes = 0

# ═══════════════════════════════════════════════════════════════════════════════
# 1. FRONTEND: Type dropdown CSS (insert after existing slash-ac-dropdown CSS)
# ═══════════════════════════════════════════════════════════════════════════════

OLD_SLASH_CSS = """  .slash-ac-item:hover, .slash-ac-item.active { background:#252525; color:#fff; }"""

NEW_SLASH_CSS = """  .slash-ac-item:hover, .slash-ac-item.active { background:#252525; color:#fff; }
  #type-ac-dropdown { display:none; position:absolute; bottom:100%; left:0; right:0; background:#1a1a1a; border:1px solid #333; border-radius:8px; margin-bottom:4px; max-height:220px; overflow-y:auto; z-index:201; font-family:Inter,sans-serif; font-size:13px; }
  .type-ac-item { padding:8px 14px; cursor:pointer; display:flex; justify-content:space-between; align-items:center; color:#ccc; transition:background 0.1s; }
  .type-ac-item:hover, .type-ac-item.active { background:#252525; color:#fff; }
  .type-ac-item .type-shortcut { color:#555; font-size:11px; font-weight:600; min-width:18px; text-align:center; }"""

if OLD_SLASH_CSS in code:
    code = code.replace(OLD_SLASH_CSS, NEW_SLASH_CSS, 1)
    changes += 1
    print("1. Type dropdown CSS eingefuegt")
else:
    print("WARN: slash-ac-item CSS nicht gefunden")

# ═══════════════════════════════════════════════════════════════════════════════
# 2. FRONTEND: Type dropdown JS (insert after onSlashAcKey function)
# ═══════════════════════════════════════════════════════════════════════════════

OLD_AFTER_SLASH = """// ─── SEARCH DIALOG ──────────────────────────────────────────────────────────
let _pendingSearchMsg = null;"""

NEW_AFTER_SLASH = """// ─── TYPE FILTER DROPDOWN ────────────────────────────────────────────────────
const _SEARCH_TYPES = [
  {key: 'all', label: '\\uD83D\\uDD0D Alles', shortcut: 'A'},
  {key: 'email', label: '\\u2709 E-Mail', shortcut: 'E'},
  {key: 'webclip', label: '\\uD83C\\uDF10 Web Clip', shortcut: 'W'},
  {key: 'screenshot', label: '\\uD83D\\uDCF8 Screenshot', shortcut: 'S'},
  {key: 'contact', label: '\\uD83D\\uDC64 Kontakt', shortcut: 'K'},
  {key: 'document', label: '\\uD83D\\uDCC4 Dokument', shortcut: 'D'},
  {key: 'conversation', label: '\\uD83D\\uDCAC Konversation', shortcut: 'G'},
];
let _typeAcIdx = -1;
let _typeAcVisible = false;

function showTypeAutocomplete(inputEl) {
  let dd = document.getElementById('type-ac-dropdown');
  if (!dd) {
    dd = document.createElement('div');
    dd.id = 'type-ac-dropdown';
    inputEl.parentElement.style.position = 'relative';
    inputEl.parentElement.appendChild(dd);
  }
  dd.innerHTML = '';
  _typeAcIdx = -1;
  _typeAcVisible = true;
  _SEARCH_TYPES.forEach((t, i) => {
    const item = document.createElement('div');
    item.className = 'type-ac-item';
    item.innerHTML = '<span>' + t.label + '</span><span class="type-shortcut">' + t.shortcut + '</span>';
    item.onmousedown = (e) => { e.preventDefault(); selectTypeCmd(inputEl, t.key); };
    dd.appendChild(item);
  });
  dd.style.display = 'block';
}

function hideTypeAutocomplete() {
  const dd = document.getElementById('type-ac-dropdown');
  if (dd) dd.style.display = 'none';
  _typeAcIdx = -1;
  _typeAcVisible = false;
}

function selectTypeCmd(inputEl, typeKey) {
  const val = inputEl.value;
  // Find the /find or /find_global prefix
  const prefix = val.match(/^\\/find_global\\s*|\\/find\\s*/);
  if (prefix) {
    if (typeKey === 'all') {
      inputEl.value = prefix[0];
    } else {
      inputEl.value = prefix[0] + typeKey + ' ';
    }
  }
  hideTypeAutocomplete();
  inputEl.focus();
}

function onTypeAcKey(e, inputEl) {
  if (!_typeAcVisible) return false;
  const dd = document.getElementById('type-ac-dropdown');
  if (!dd || dd.style.display === 'none') return false;
  const items = dd.querySelectorAll('.type-ac-item');

  if (e.key === 'ArrowDown') { e.preventDefault(); _typeAcIdx = Math.min(_typeAcIdx+1, items.length-1); items.forEach((it,i) => it.classList.toggle('active', i===_typeAcIdx)); return true; }
  if (e.key === 'ArrowUp') { e.preventDefault(); _typeAcIdx = Math.max(_typeAcIdx-1, 0); items.forEach((it,i) => it.classList.toggle('active', i===_typeAcIdx)); return true; }
  if ((e.key === 'Enter' || e.key === 'Tab') && _typeAcIdx >= 0) { e.preventDefault(); selectTypeCmd(inputEl, _SEARCH_TYPES[_typeAcIdx].key); return true; }
  if (e.key === 'Escape') { hideTypeAutocomplete(); return true; }

  // Shortcut keys
  const key = e.key.toUpperCase();
  const match = _SEARCH_TYPES.find(t => t.shortcut === key);
  if (match && key.length === 1) { e.preventDefault(); selectTypeCmd(inputEl, match.key); return true; }

  return false;
}

// ─── SEARCH DIALOG ──────────────────────────────────────────────────────────
let _pendingSearchMsg = null;"""

if OLD_AFTER_SLASH in code:
    code = code.replace(OLD_AFTER_SLASH, NEW_AFTER_SLASH, 1)
    changes += 1
    print("2. Type dropdown JS eingefuegt")
else:
    print("WARN: SEARCH DIALOG marker nicht gefunden")

# ═══════════════════════════════════════════════════════════════════════════════
# 3. FRONTEND: Update oninput handler to show type dropdown after /find
# ═══════════════════════════════════════════════════════════════════════════════

OLD_ONINPUT = """oninput="autoResize(this); if(this.value==='/')showSlashAutocomplete(this); else if(!this.value.startsWith('/'))hideSlashAutocomplete();\""""

NEW_ONINPUT = """oninput="autoResize(this); onInputHandler(this);\""""

if OLD_ONINPUT in code:
    code = code.replace(OLD_ONINPUT, NEW_ONINPUT, 1)
    changes += 1
    print("3. oninput handler ersetzt")
else:
    print("WARN: oninput handler nicht gefunden")

# ═══════════════════════════════════════════════════════════════════════════════
# 4. FRONTEND: Add onInputHandler function (before showSlashAutocomplete)
# ═══════════════════════════════════════════════════════════════════════════════

OLD_SHOW_SLASH = "function showSlashAutocomplete(inputEl) {"

NEW_SHOW_SLASH = """function onInputHandler(el) {
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
}

function showSlashAutocomplete(inputEl) {"""

if OLD_SHOW_SLASH in code:
    code = code.replace(OLD_SHOW_SLASH, NEW_SHOW_SLASH, 1)
    changes += 1
    print("4. onInputHandler eingefuegt")
else:
    print("WARN: showSlashAutocomplete nicht gefunden")

# ═══════════════════════════════════════════════════════════════════════════════
# 5. FRONTEND: Update onKey to route to type dropdown handler
# ═══════════════════════════════════════════════════════════════════════════════

OLD_ONSLASH_CALL = "  if (onSlashAcKey(e, input)) return;"

NEW_ONSLASH_CALL = "  if (onTypeAcKey(e, input)) return;\n  if (onSlashAcKey(e, input)) return;"

# Find within onKey function
if OLD_ONSLASH_CALL in code:
    code = code.replace(OLD_ONSLASH_CALL, NEW_ONSLASH_CALL, 1)
    changes += 1
    print("5. onKey: type dropdown routing eingefuegt")
else:
    print("WARN: onSlashAcKey call in onKey nicht gefunden")

# ═══════════════════════════════════════════════════════════════════════════════
# 6. FRONTEND: Update sendMessage to parse /find [type] [query] and send type
# ═══════════════════════════════════════════════════════════════════════════════

OLD_SEND_FIND = """  // /find and /find_global commands — intercept, do NOT send to AI
  const findGlobalMatch = text.match(/^\\/find_global\\s+(.+)/i);
  const findMatch = text.match(/^\\/find\\s+(.+)/i);
  if ((findGlobalMatch || findMatch) && getAgentName() !== 'Kein Agent') {
    const isGlobal = !!findGlobalMatch;
    const query = isGlobal ? findGlobalMatch[1] : findMatch[1];
    addMessage('user', text);
    scrollDown();
    startTyping(isGlobal ? 'Globale Suche...' : 'Suche...');
    try {
      let r;
      if (isGlobal) {
        r = await fetch('/global_search_preview', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({query:query, requesting_agent:getAgentName(), session_id:SESSION_ID})});
      } else {
        r = await fetch('/search_preview', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({query:query, agent:getAgentName(), session_id:SESSION_ID})});
      }"""

NEW_SEND_FIND = """  // /find and /find_global commands — intercept, do NOT send to AI
  hideTypeAutocomplete();
  const findGlobalMatch = text.match(/^\\/find_global\\s+(.+)/i);
  const findMatch = text.match(/^\\/find\\s+(.+)/i);
  if ((findGlobalMatch || findMatch) && getAgentName() !== 'Kein Agent') {
    const isGlobal = !!findGlobalMatch;
    let rawQuery = isGlobal ? findGlobalMatch[1] : findMatch[1];
    // Extract optional type prefix: /find email some query
    const knownTypes = ['email','webclip','screenshot','contact','document','conversation'];
    let searchType = null;
    const firstWord = rawQuery.split(/\\s+/)[0].toLowerCase();
    if (knownTypes.includes(firstWord)) {
      searchType = firstWord;
      rawQuery = rawQuery.substring(firstWord.length).trim();
    }
    const query = rawQuery;
    if (!query) { addStatusMsg('Bitte Suchbegriff eingeben'); return; }
    addMessage('user', text);
    scrollDown();
    const typeLabels = {email:'E-Mail',webclip:'Web Clip',screenshot:'Screenshot',contact:'Kontakt',document:'Dokument',conversation:'Konversation'};
    const typeInfo = searchType ? ' | Typ: ' + (typeLabels[searchType]||searchType) : '';
    startTyping((isGlobal ? 'Globale Suche' : 'Suche') + typeInfo + '...');
    try {
      let r;
      const payload = {query:query, session_id:SESSION_ID};
      if (searchType) payload.type = searchType;
      if (isGlobal) {
        payload.requesting_agent = getAgentName();
        r = await fetch('/global_search_preview', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
      } else {
        payload.agent = getAgentName();
        r = await fetch('/search_preview', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
      }"""

if OLD_SEND_FIND in code:
    code = code.replace(OLD_SEND_FIND, NEW_SEND_FIND, 1)
    changes += 1
    print("6. sendMessage /find parsing mit type erweitert")
else:
    print("WARN: sendMessage /find block nicht gefunden")

# ═══════════════════════════════════════════════════════════════════════════════
# 7. FRONTEND: Update search result status line to show extracted keywords
# ═══════════════════════════════════════════════════════════════════════════════

OLD_NO_RESULTS = "        addStatusMsg('Keine Ergebnisse fuer: ' + query);"
NEW_NO_RESULTS = "        addStatusMsg('Keine Ergebnisse fuer: ' + query + typeInfo);"

if OLD_NO_RESULTS in code:
    code = code.replace(OLD_NO_RESULTS, NEW_NO_RESULTS, 1)
    changes += 1
    print("7. Keine-Ergebnisse Meldung mit typeInfo erweitert")

# ═══════════════════════════════════════════════════════════════════════════════
# 8. BACKEND: /search_preview — add type + NLP extraction
# ═══════════════════════════════════════════════════════════════════════════════

OLD_SEARCH_PREVIEW = """    session_id = request.json.get('session_id', 'default')
    state = get_session(session_id)
    query = request.json.get('query', '')
    if not state.get('speicher') or not query:
        return jsonify({'ok': False, 'results': []})
    try:
        from search_engine import QueryParser, HybridSearch, SearchIndex, normalize_unicode, get_or_build_index
        intent = QueryParser.parse(query)
        if not intent.is_search:
            return jsonify({'ok': False, 'results': [], 'reason': 'no_search_intent'})
        # Ensure index
        idx = get_or_build_index(state['speicher'])
        idx.update_index()
        results, feedback = HybridSearch.search(intent, state['speicher'], max_results=50)"""

NEW_SEARCH_PREVIEW = """    session_id = request.json.get('session_id', 'default')
    state = get_session(session_id)
    query = request.json.get('query', '')
    search_type = request.json.get('type', None)
    if not state.get('speicher') or not query:
        return jsonify({'ok': False, 'results': []})
    try:
        from search_engine import QueryParser, HybridSearch, SearchIndex, normalize_unicode, get_or_build_index, extract_search_keywords, search_contacts

        # Contact search — special case
        if search_type == 'contact':
            contact_results = search_contacts(query, state['speicher'])
            items = []
            for c in contact_results:
                items.append({
                    'name': c['name'], 'path': '', 'type': 'contact', 'source_type': 'contact',
                    'date': '', 'from': '', 'subject': c['name'].replace('contact_','').replace('_',' '),
                    'preview': c['content'][:150], 'score': c['score'],
                    'from_person': False, 'is_notification': False,
                })
            return jsonify({'ok': True, 'results': items, 'query': query, 'feedback': {'query': query}})

        # NLP keyword extraction for long queries
        extracted_keywords = None
        effective_query = query
        words = query.split()
        if len(words) > 5:
            extracted_keywords = extract_search_keywords(query, search_type)
            if extracted_keywords:
                effective_query = ' '.join(extracted_keywords)

        intent = QueryParser.parse(effective_query)
        if not intent.is_search:
            # Force search intent for explicit /find commands
            intent.is_search = True
            intent.keywords = [kw.lower() for kw in effective_query.split() if len(kw) >= 2]
        # Ensure index
        idx = get_or_build_index(state['speicher'])
        idx.update_index()
        results, feedback = HybridSearch.search(intent, state['speicher'], max_results=50, forced_type=search_type)
        if extracted_keywords and feedback:
            feedback['extracted_keywords'] = extracted_keywords"""

if OLD_SEARCH_PREVIEW in code:
    code = code.replace(OLD_SEARCH_PREVIEW, NEW_SEARCH_PREVIEW, 1)
    changes += 1
    print("8. /search_preview Backend mit type + NLP erweitert")
else:
    print("WARN: /search_preview block nicht gefunden")

# ═══════════════════════════════════════════════════════════════════════════════
# 9. BACKEND: Sorting fix — date descending as tiebreaker
# ═══════════════════════════════════════════════════════════════════════════════

OLD_SORT = "        items.sort(key=lambda x: (not x['from_person'], -x['score'], x['date']), reverse=False)"

NEW_SORT = "        items.sort(key=lambda x: (not x['from_person'], -x['score'], x.get('date','') if x.get('date','') else ''), reverse=False)"

# Actually let's fix sorting to be newest first at same score
OLD_SORT2 = "        items.sort(key=lambda x: (not x['from_person'],))"
NEW_SORT2 = "        items.sort(key=lambda x: (not x['from_person'], -x['score'], '~' if not x.get('date') else x['date']), reverse=False)"

# The double-sort is redundant. Replace both with a single good sort.
# Let's find and replace the two sort lines together
OLD_DOUBLE_SORT = """        # Sort: from_person first, then score, then date
        items.sort(key=lambda x: (not x['from_person'], -x['score'], x['date']), reverse=False)
        items.sort(key=lambda x: (not x['from_person'],))"""

NEW_DOUBLE_SORT = """        # Sort: from_person first, then highest score, then newest date
        items.sort(key=lambda x: (not x.get('from_person'), -x['score'], x.get('date','') or '0'), reverse=False)"""

if OLD_DOUBLE_SORT in code:
    code = code.replace(OLD_DOUBLE_SORT, NEW_DOUBLE_SORT, 1)
    changes += 1
    print("9. Sortierung verbessert (single sort, date tiebreaker)")
else:
    print("WARN: Double sort pattern nicht gefunden")

# ═══════════════════════════════════════════════════════════════════════════════
# 10. BACKEND: /global_search_preview — add type parameter
# ═══════════════════════════════════════════════════════════════════════════════

OLD_GLOBAL = """    query = request.json.get('query', '')
    if not query:
        return jsonify({'ok': False, 'results': []})
    try:
        from search_engine import global_search, normalize_unicode, QueryParser
        results, feedback = global_search(query, max_results=50)"""

NEW_GLOBAL = """    query = request.json.get('query', '')
    search_type = request.json.get('type', None)
    if not query:
        return jsonify({'ok': False, 'results': []})
    try:
        from search_engine import global_search, normalize_unicode, QueryParser, extract_search_keywords
        # NLP keyword extraction for long queries
        effective_query = query
        extracted_keywords = None
        if len(query.split()) > 5:
            extracted_keywords = extract_search_keywords(query, search_type)
            if extracted_keywords:
                effective_query = ' '.join(extracted_keywords)
        results, feedback = global_search(effective_query, max_results=50)
        if extracted_keywords and feedback:
            feedback['extracted_keywords'] = extracted_keywords"""

if OLD_GLOBAL in code:
    code = code.replace(OLD_GLOBAL, NEW_GLOBAL, 1)
    changes += 1
    print("10. /global_search_preview mit type + NLP erweitert")
else:
    print("WARN: global_search_preview block nicht gefunden")


# ═══════════════════════════════════════════════════════════════════════════════
# WRITE
# ═══════════════════════════════════════════════════════════════════════════════

with open(SRC, 'w') as f:
    f.write(code)

print(f"\n{changes} Aenderungen geschrieben.")
