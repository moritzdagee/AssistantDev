#!/usr/bin/env python3
"""
Feature 2: Replace keyword-based search triggers with /find and /find_global commands.
- Remove frontend keyword detection (detectSearchIntent, _SEARCH_ACTIONS_JS, etc.)
- Remove backend keyword triggers (auto_search_memory, deep-search fallback triggers)
- Add /find and /find_global command parsing in sendMessage()
- Add slash-command autocomplete dropdown when user types '/'
- Commands are intercepted and NOT sent to the AI model
"""

import os

path = os.path.expanduser("~/AssistantDev/src/web_server.py")
with open(path, 'r') as f:
    content = f.read()

original = content

# ============================================================================
# 1. FRONTEND: Replace keyword detection block + sendMessage search intercept
#    with /find and /find_global command handling
# ============================================================================

# 1a. Replace the entire keyword detection block (lines 2351-2375) with slash-command autocomplete
old_search_block = """// ─── SEARCH TRIGGER DETECTION (client-side) ─────────────────────────────────
const _SEARCH_ACTIONS_JS = ['finde','suche','such','zeig','zeige','hol','hole','find','search','show','get','load','encontra','encontre','procura','procure','mostra','mostre','busca','busque'];
const _SEARCH_PHRASES_JS = ['wo ist','hast du','gibt es','schau nach','zeig mir','hol mir','look for','show me','where is','do you have','look up','get me','onde est','tem algum'];
const _SEARCH_OBJECTS_JS = ['email','mail','e-mail','nachricht','message','datei','dokument','file','document','brief','letter','excel','tabelle','spreadsheet','word','pdf','anhang','attachment','rechnung','invoice','vertrag','contract','angebot','offer','notiz','note','memo','protokoll','praesentation','presentation','powerpoint','slides','deck','zusammenfassung','summary','gestern','yesterday','heute','today','letzte','letzten','last','recent'];

const _GLOBAL_TRIGGERS_JS = ['erweitertes gedaechtnis','erweitertem gedaechtnis','ueberall suchen','ueberall','global suchen','alle agenten','allen agenten','gesamtes memory','gesamten memory','alles durchsuchen','extended memory','global search','search everywhere','all agents','everywhere','search all','across all','memoria extendida','busca global','procura tudo','em tudo','todos os agentes','pesquisa global'];

function detectGlobalTrigger(text) {
  const lower = text.toLowerCase().replace(/[\\u00e4]/g,'ae').replace(/[\\u00f6]/g,'oe').replace(/[\\u00fc]/g,'ue');
  return _GLOBAL_TRIGGERS_JS.some(t => lower.includes(t));
}

function detectSearchIntent(text) {
  // Global trigger always counts as search intent
  if (detectGlobalTrigger(text)) return true;
  const lower = text.toLowerCase();
  const words = lower.split(/\\s+/);
  const hasAction = words.some(w => _SEARCH_ACTIONS_JS.includes(w.replace(/[.,;:!?]/g,''))) || _SEARCH_PHRASES_JS.some(p => lower.includes(p));
  if (!hasAction) return false;
  const hasObject = words.some(w => _SEARCH_OBJECTS_JS.includes(w.replace(/[.,;:!?]/g,'')));
  // Check for proper nouns (capitalized words after first word)
  const origWords = text.split(/\\s+/);
  const hasProperNoun = origWords.slice(1).some(w => { const c = w.replace(/[.,;:!?]/g,''); return c.length >= 2 && c[0] === c[0].toUpperCase() && c[0] !== c[0].toLowerCase(); });
  return hasObject || hasProperNoun;
}"""

new_search_block = """// ─── SLASH COMMAND AUTOCOMPLETE ──────────────────────────────────────────────
const _SLASH_COMMANDS = [
  {cmd: '/find', label: '/find [query]', desc: 'Memory des aktuellen Agenten durchsuchen'},
  {cmd: '/find_global', label: '/find_global [query]', desc: 'Alle Agenten durchsuchen (globale Suche)'},
];
let _slashAcIdx = -1;

function showSlashAutocomplete(inputEl) {
  let dd = document.getElementById('slash-ac-dropdown');
  if (!dd) {
    dd = document.createElement('div');
    dd.id = 'slash-ac-dropdown';
    inputEl.parentElement.style.position = 'relative';
    inputEl.parentElement.appendChild(dd);
  }
  dd.innerHTML = '';
  _slashAcIdx = -1;
  _SLASH_COMMANDS.forEach((c, i) => {
    const item = document.createElement('div');
    item.className = 'slash-ac-item';
    item.innerHTML = '<strong>' + c.label + '</strong><span style="margin-left:8px;color:#888;font-size:12px">' + c.desc + '</span>';
    item.onmousedown = (e) => { e.preventDefault(); selectSlashCmd(inputEl, c.cmd); };
    dd.appendChild(item);
  });
  dd.style.display = 'block';
}

function hideSlashAutocomplete() {
  const dd = document.getElementById('slash-ac-dropdown');
  if (dd) dd.style.display = 'none';
  _slashAcIdx = -1;
}

function selectSlashCmd(inputEl, cmd) {
  inputEl.value = cmd + ' ';
  hideSlashAutocomplete();
  inputEl.focus();
}

function onSlashAcKey(e, inputEl) {
  const dd = document.getElementById('slash-ac-dropdown');
  if (!dd || dd.style.display === 'none') return false;
  const items = dd.querySelectorAll('.slash-ac-item');
  if (e.key === 'ArrowDown') { e.preventDefault(); _slashAcIdx = Math.min(_slashAcIdx+1, items.length-1); items.forEach((it,i) => it.classList.toggle('active', i===_slashAcIdx)); return true; }
  if (e.key === 'ArrowUp') { e.preventDefault(); _slashAcIdx = Math.max(_slashAcIdx-1, 0); items.forEach((it,i) => it.classList.toggle('active', i===_slashAcIdx)); return true; }
  if ((e.key === 'Enter' || e.key === 'Tab') && _slashAcIdx >= 0) { e.preventDefault(); selectSlashCmd(inputEl, _SLASH_COMMANDS[_slashAcIdx].cmd); return true; }
  if (e.key === 'Escape') { hideSlashAutocomplete(); return true; }
  return false;
}"""

assert old_search_block in content, "Could not find old_search_block in content"
content = content.replace(old_search_block, new_search_block)

# 1b. Update onKey to handle slash autocomplete
old_onkey = "function onKey(e) { if (e.key==='Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); } }"
new_onkey = """function onKey(e) {
  const input = document.getElementById('msg-input');
  // Slash-command autocomplete navigation
  if (onSlashAcKey(e, input)) return;
  if (e.key==='Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
}"""
assert old_onkey in content, "Could not find old_onkey"
content = content.replace(old_onkey, new_onkey)

# 1c. Update oninput on textarea to show/hide slash autocomplete
old_textarea = 'oninput="autoResize(this)"'
new_textarea = "oninput=\"autoResize(this); if(this.value==='/')showSlashAutocomplete(this); else if(!this.value.startsWith('/'))hideSlashAutocomplete();\""
assert old_textarea in content, "Could not find old_textarea"
content = content.replace(old_textarea, new_textarea)

# 1d. Replace the sendMessage search intercept with /find command handling
old_send = """// ─── SEND MESSAGE ───────────────────────────────────────────────────────────
async function sendMessage() {
  const input = document.getElementById('msg-input');
  const text = input.value.trim();
  if (!text) return;
  input.value = ''; input.style.height = 'auto';

  // Check for search intent — show preview dialog before sending
  if (detectSearchIntent(text) && getAgentName() !== 'Kein Agent') {
    addMessage('user', text);
    scrollDown();
    const isGlobal = detectGlobalTrigger(text);
    startTyping(isGlobal ? 'Globale Suche...' : 'Suche...');
    try {
      let r;
      if (isGlobal) {
        r = await fetch('/global_search_preview', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({query:text, requesting_agent:getAgentName(), session_id:SESSION_ID})});
      } else {
        r = await fetch('/search_preview', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({query:text, agent:getAgentName(), session_id:SESSION_ID})});
      }
      const data = await r.json();
      stopTyping();
      if (data.ok && data.results && data.results.length > 0) {
        _pendingSearchMsg = text;
        showSearchDialog(data.results, data.query || text, isGlobal || data.global);
        return;
      }
    } catch(e) { stopTyping(); }
    // No results or error — send directly
    doSendChat(text);
    return;
  }

  addMessage('user', text);
  scrollDown();
  doSendChat(text);
}"""

new_send = """// ─── SEND MESSAGE ───────────────────────────────────────────────────────────
async function sendMessage() {
  const input = document.getElementById('msg-input');
  const text = input.value.trim();
  if (!text) return;
  input.value = ''; input.style.height = 'auto';
  hideSlashAutocomplete();

  // /find and /find_global commands — intercept, do NOT send to AI
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
      }
      const data = await r.json();
      stopTyping();
      if (data.ok && data.results && data.results.length > 0) {
        _pendingSearchMsg = null;  // /find results stay in dialog, no auto-send to AI
        showSearchDialog(data.results, data.query || query, isGlobal || data.global);
        return;
      } else {
        addStatusMsg('Keine Ergebnisse fuer: ' + query);
      }
    } catch(e) { stopTyping(); addStatusMsg('Suchfehler: ' + e.message); }
    return;
  }

  addMessage('user', text);
  scrollDown();
  doSendChat(text);
}"""

assert old_send in content, "Could not find old_send"
content = content.replace(old_send, new_send)

# 1e. Add CSS for slash-command autocomplete dropdown
old_css_anchor = "#file-ac-dropdown {"
new_css_with_slash = """#slash-ac-dropdown {
  display:none; position:absolute; bottom:100%; left:0; right:0;
  background:#1a1a1a; border:1px solid #333; border-radius:8px;
  max-height:120px; overflow-y:auto; z-index:200; margin-bottom:4px;
  box-shadow: 0 -4px 12px rgba(0,0,0,0.4);
}
.slash-ac-item {
  padding:10px 14px; cursor:pointer; font-size:13px; color:#ccc;
  font-family:Inter,system-ui,sans-serif; border-bottom:1px solid #252525;
}
.slash-ac-item:last-child { border-bottom:none; }
.slash-ac-item:hover, .slash-ac-item.active { background:#252525; color:#fff; }

#file-ac-dropdown {"""

assert old_css_anchor in content, "Could not find #file-ac-dropdown CSS"
content = content.replace(old_css_anchor, new_css_with_slash, 1)  # Only first occurrence

# ============================================================================
# 2. BACKEND: Remove keyword-based auto_search_memory function body
#    Replace with a simple pass-through that only triggers on explicit requests
# ============================================================================

# 2a. Replace the auto_search_memory function - make it only respond to explicit "memory folder" legacy trigger
old_auto_search = """def auto_search_memory(msg, speicher):
    \"\"\"Auto-detect file search intent in message and load matching files.
    Triggers on multilingual action+object keyword combinations or 'memory folder'.\"\"\"
    try:
        import re
        msg_lower = msg.lower()

        # --- Legacy trigger: "memory folder" / "memory ordner" ---
        if 'memory folder' in msg_lower or 'memory ordner' in msg_lower:
            memory_dir = os.path.join(speicher, 'memory')
            if not os.path.exists(memory_dir):
                return []
            after = re.split(r'memory folder|memory ordner', msg_lower, maxsplit=1)[-1]
            after = re.split(r'\\bnach\\b|\\bfor\\b|\\bafter\\b', after)[-1]
            keywords = parse_search_keywords(after)
            if not keywords:
                return []
            return scored_memory_search(memory_dir, keywords, max_results=3)

        # --- New trigger: action verb/phrase + object keyword ---
        words = msg_lower.split()
        has_action = any(w.rstrip('.,;:!?') in _SEARCH_ACTIONS for w in words)
        if not has_action:
            has_action = any(phrase in msg_lower for phrase in _SEARCH_PHRASES)
        if not has_action:
            return []

        has_object = any(w.rstrip('.,;:!?') in _SEARCH_OBJECTS for w in words)
        if not has_object:
            return []

        memory_dir = os.path.join(speicher, 'memory')
        if not os.path.exists(memory_dir):
            return []

        # Extract search query: remove action verbs, object words, and stopwords
        # Keep only the meaningful terms (names, subjects, etc.)
        all_trigger_words = _SEARCH_ACTIONS | _SEARCH_OBJECTS | SEARCH_STOPWORDS
        # Also strip multi-word phrases from the message
        query_text = msg_lower
        for phrase in _SEARCH_PHRASES:
            query_text = query_text.replace(phrase, ' ')
        # Remove single-word triggers
        query_tokens = []
        for w in query_text.split():
            w_clean = w.rstrip('.,;:!?')
            if w_clean in all_trigger_words:
                continue
            if len(w_clean) < 3:
                continue
            query_tokens.append(w_clean)

        # If no meaningful keywords remain, use object words as search terms
        if not query_tokens:
            query_tokens = [w.rstrip('.,;:!?') for w in words if w.rstrip('.,;:!?') in _SEARCH_OBJECTS]

        keywords = parse_search_keywords(' '.join(query_tokens))
        if not keywords:
            return []

        return scored_memory_search(memory_dir, keywords, max_results=3)

    except Exception as e:
        print("auto_search_memory error: " + str(e))
        return []"""

new_auto_search = """def auto_search_memory(msg, speicher):
    \"\"\"Auto-search memory. Only triggers on legacy 'memory folder/ordner' keyword.
    All other searches now use explicit /find and /find_global commands.\"\"\"
    try:
        import re
        msg_lower = msg.lower()

        # --- Legacy trigger: "memory folder" / "memory ordner" ---
        if 'memory folder' in msg_lower or 'memory ordner' in msg_lower:
            memory_dir = os.path.join(speicher, 'memory')
            if not os.path.exists(memory_dir):
                return []
            after = re.split(r'memory folder|memory ordner', msg_lower, maxsplit=1)[-1]
            after = re.split(r'\\bnach\\b|\\bfor\\b|\\bafter\\b', after)[-1]
            keywords = parse_search_keywords(after)
            if not keywords:
                return []
            return scored_memory_search(memory_dir, keywords, max_results=3)

        return []

    except Exception as e:
        print("auto_search_memory error: " + str(e))
        return []"""

assert old_auto_search in content, "Could not find old_auto_search"
content = content.replace(old_auto_search, new_auto_search)

# 2b. Remove the deep-search fallback keyword triggers
old_deep_fallback = """    # Fallback: deep_memory_search if auto_search found nothing but message looks like a search
    if not auto_loaded_names and state.get('speicher') and not kontext_override:
        msg_lower = msg.lower()
        search_triggers = ['such', 'find', 'zeig', 'schau', 'was steht', 'gibt es', 'hast du',
                           'search', 'look', 'show me', '/search', 'email', 'mail von', 'mail an']
        if any(t in msg_lower for t in search_triggers):"""

new_deep_fallback = """    # Fallback: deep_memory_search only for explicit /find command (passed through from frontend)
    if not auto_loaded_names and state.get('speicher') and not kontext_override:
        msg_lower = msg.lower()
        if msg_lower.startswith('/find '):"""

assert old_deep_fallback in content, "Could not find old_deep_fallback"
content = content.replace(old_deep_fallback, new_deep_fallback)

# ============================================================================
# 3. Remove backend _SEARCH_ACTIONS, _SEARCH_PHRASES, _SEARCH_OBJECTS dicts
#    (keep SEARCH_STOPWORDS as it's used by parse_search_keywords)
# ============================================================================

old_search_dicts = """# --- Auto-search trigger words ---
# Action verbs that indicate search intent
_SEARCH_ACTIONS = {
    # Deutsch
    'finde', 'suche', 'such', 'zeig', 'zeige', 'nachschlagen', 'lookup',
    # EN
    'find', 'search', 'retrieve', 'fetch', 'check', 'get',
    # PT
    'encontra', 'encontre', 'procura', 'procure', 'acha', 'ache',
    'mostra', 'mostre', 'busca', 'busque', 'localiza', 'localize',
}
# Multi-word action phrases (checked as substrings)
_SEARCH_PHRASES = [
    # Deutsch
    'wo ist', 'hast du', 'gibt es', 'schau nach', 'zeig mir',
    # EN
    'look for', 'show me', 'where is', 'do you have', 'look up', 'get me',
    # PT
    'onde está', 'onde esta', 'tem algum', 'tem alguma',"""

# Need to find the full extent of these dicts - read more
assert old_search_dicts in content, "Could not find old_search_dicts start"

# Find the full _SEARCH_OBJECTS block end - it ends before BINARY_EXTS
idx = content.index(old_search_dicts)
# Find the next line that starts with BINARY_EXTS
binary_idx = content.index("BINARY_EXTS = {", idx)
# The block to remove is from old_search_dicts start to just before BINARY_EXTS
full_old_block = content[idx:binary_idx]

new_block = """# Note: _SEARCH_ACTIONS, _SEARCH_PHRASES, _SEARCH_OBJECTS removed.
# Search is now triggered only by explicit /find and /find_global commands.
"""

content = content[:idx] + new_block + content[binary_idx:]

# ============================================================================
# 4. Verify all replacements were made
# ============================================================================
changes = []
if 'detectSearchIntent' not in content:
    changes.append("✅ detectSearchIntent removed")
else:
    changes.append("❌ detectSearchIntent still present!")

if '_SEARCH_ACTIONS_JS' not in content:
    changes.append("✅ _SEARCH_ACTIONS_JS removed")
else:
    changes.append("❌ _SEARCH_ACTIONS_JS still present!")

if '_SEARCH_ACTIONS = {' not in content:
    changes.append("✅ _SEARCH_ACTIONS backend removed")
else:
    changes.append("❌ _SEARCH_ACTIONS backend still present!")

if 'search_triggers' not in content:
    changes.append("✅ search_triggers list removed")
else:
    changes.append("❌ search_triggers still present!")

if '/find_global' in content:
    changes.append("✅ /find_global command added")
else:
    changes.append("❌ /find_global missing!")

if 'slash-ac-dropdown' in content:
    changes.append("✅ Slash autocomplete added")
else:
    changes.append("❌ Slash autocomplete missing!")

if 'showSlashAutocomplete' in content:
    changes.append("✅ showSlashAutocomplete function added")
else:
    changes.append("❌ showSlashAutocomplete missing!")

# Write the file
with open(path, 'w') as f:
    f.write(content)

for c in changes:
    print(c)

print(f"\nDatei geschrieben: {path}")
print(f"Originallaenge: {len(original)} Zeichen")
print(f"Neue Laenge: {len(content)} Zeichen")
print(f"Differenz: {len(content) - len(original)} Zeichen")
