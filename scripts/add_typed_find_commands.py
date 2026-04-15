#!/usr/bin/env python3
"""Add /find-email, /find-webclip, etc. slash commands with autocomplete."""

SRC = "/Users/moritzcremer/AssistantDev/src/web_server.py"

with open(SRC, 'r') as f:
    code = f.read()

changes = 0

# ═══════════════════════════════════════════════════════════════════════════════
# 1. Expand _SLASH_COMMANDS with typed find commands
# ═══════════════════════════════════════════════════════════════════════════════

old = """const _SLASH_COMMANDS = [
  {cmd: '/find', label: '/find [query]', desc: 'Memory des aktuellen Agenten durchsuchen'},
  {cmd: '/find_global', label: '/find_global [query]', desc: 'Alle Agenten durchsuchen (globale Suche)'},
];"""

new = """const _SLASH_COMMANDS = [
  {cmd: '/find', label: '/find [query]', desc: 'Alle Dateien im Agent-Memory durchsuchen'},
  {cmd: '/find-email', label: '/find-email [query]', desc: 'Nur E-Mails durchsuchen'},
  {cmd: '/find-webclip', label: '/find-webclip [query]', desc: 'Nur Web Clips durchsuchen'},
  {cmd: '/find-document', label: '/find-document [query]', desc: 'Nur Dokumente (Word/Excel/PDF/PPTX)'},
  {cmd: '/find-conversation', label: '/find-conversation [query]', desc: 'Nur Konversationen durchsuchen'},
  {cmd: '/find-screenshot', label: '/find-screenshot [query]', desc: 'Nur Screenshots durchsuchen'},
  {cmd: '/find_global', label: '/find_global [query]', desc: 'Alle Agenten durchsuchen'},
  {cmd: '/find_global-email', label: '/find_global-email [query]', desc: 'E-Mails in allen Agenten'},
  {cmd: '/find_global-webclip', label: '/find_global-webclip [query]', desc: 'Web Clips in allen Agenten'},
  {cmd: '/find_global-document', label: '/find_global-document [query]', desc: 'Dokumente in allen Agenten'},
  {cmd: '/find_global-conversation', label: '/find_global-conversation [query]', desc: 'Konversationen in allen Agenten'},
  {cmd: '/find_global-screenshot', label: '/find_global-screenshot [query]', desc: 'Screenshots in allen Agenten'},
];"""

if old in code:
    code = code.replace(old, new, 1)
    changes += 1
    print("1. _SLASH_COMMANDS erweitert mit typed find commands")
else:
    print("WARN: _SLASH_COMMANDS not found")

# ═══════════════════════════════════════════════════════════════════════════════
# 2. Update showSlashAutocomplete to filter commands based on input
# ═══════════════════════════════════════════════════════════════════════════════

# Currently shows ALL commands when "/" is typed. Need to filter as user types more.
# The oninput handler already calls onInputHandler — we need to update it to
# also filter the slash dropdown when user types e.g. "/find-"

old = """function onInputHandler(el) {
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

new = """function onInputHandler(el) {
  autoResize(el);
  const val = el.value;
  // Show/filter slash dropdown when typing "/"
  if (val.startsWith('/') && !val.includes(' ')) {
    showSlashAutocomplete(el, val);
    hideTypeAutocomplete();
    hideFindChips();
    return;
  }
  // Show find chips after any /find variant (with trailing space)
  const isFindMode = /^\\/find(?:_global)?(?:-\\w+)?(?:\\s|$)/i.test(val);
  if (isFindMode) {
    hideSlashAutocomplete();
    hideTypeAutocomplete();
    showFindChips();
    // Trigger live search if there's query text
    const queryMatch = val.match(/^\\/find(?:_global)?(?:-\\w+)?\\s+(.*)/i);
    if (queryMatch && queryMatch[1] && queryMatch[1].trim().length >= 2) {
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
    print("2. onInputHandler updated for typed commands + filtered dropdown")
else:
    print("WARN: onInputHandler not found")

# ═══════════════════════════════════════════════════════════════════════════════
# 3. Update showSlashAutocomplete to accept filter parameter
# ═══════════════════════════════════════════════════════════════════════════════

old = """function showSlashAutocomplete(inputEl) {
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
}"""

new = """function showSlashAutocomplete(inputEl, filterText) {
  let dd = document.getElementById('slash-ac-dropdown');
  if (!dd) {
    dd = document.createElement('div');
    dd.id = 'slash-ac-dropdown';
    inputEl.parentElement.style.position = 'relative';
    inputEl.parentElement.appendChild(dd);
  }
  dd.innerHTML = '';
  _slashAcIdx = -1;
  const filter = (filterText || '/').toLowerCase();
  const filtered = _SLASH_COMMANDS.filter(c => c.cmd.toLowerCase().startsWith(filter));
  if (!filtered.length) { dd.style.display = 'none'; return; }
  filtered.forEach((c, i) => {
    const item = document.createElement('div');
    item.className = 'slash-ac-item';
    item.dataset.cmd = c.cmd;
    item.innerHTML = '<strong>' + c.label + '</strong><span style="margin-left:8px;color:#888;font-size:12px">' + c.desc + '</span>';
    item.onmousedown = (e) => { e.preventDefault(); selectSlashCmd(inputEl, c.cmd); };
    dd.appendChild(item);
  });
  dd.style.display = 'block';
}"""

if old in code:
    code = code.replace(old, new, 1)
    changes += 1
    print("3. showSlashAutocomplete now filters commands")
else:
    print("WARN: showSlashAutocomplete not found")

# ═══════════════════════════════════════════════════════════════════════════════
# 4. Update onSlashAcKey — use filtered commands for Tab/Enter selection
# ═══════════════════════════════════════════════════════════════════════════════

old = """  if ((e.key === 'Enter' || e.key === 'Tab') && _slashAcIdx >= 0) { e.preventDefault(); selectSlashCmd(inputEl, _SLASH_COMMANDS[_slashAcIdx].cmd); return true; }"""
new = """  if ((e.key === 'Enter' || e.key === 'Tab') && _slashAcIdx >= 0) { e.preventDefault(); var selItem = items[_slashAcIdx]; if (selItem) selectSlashCmd(inputEl, selItem.dataset.cmd); return true; }"""

if old in code:
    code = code.replace(old, new, 1)
    changes += 1
    print("4. onSlashAcKey uses filtered item dataset.cmd")
else:
    print("WARN: onSlashAcKey Tab/Enter not found")

# ═══════════════════════════════════════════════════════════════════════════════
# 5. Update sendMessage — parse /find-TYPE and /find_global-TYPE commands
# ═══════════════════════════════════════════════════════════════════════════════

old = """  // /find and /find_global commands — intercept, do NOT send to AI
  hideTypeAutocomplete();
  const findGlobalMatch = text.match(/^\\/find_global(?:\\s+(.*))?$/i);
  const findMatch = text.match(/^\\/find(?:\\s+(.*))?$/i);
  if ((findGlobalMatch || findMatch) && getAgentName() !== 'Kein Agent') {
    const isGlobal = !!findGlobalMatch;
    let rawQuery = (isGlobal ? findGlobalMatch[1] : findMatch[1]) || '';
    // Extract optional type prefix: /find email some query
    const knownTypes = ['email','webclip','screenshot','contact','document','conversation'];
    let searchType = null;
    const firstWord = rawQuery.split(/\\s+/)[0].toLowerCase();
    if (knownTypes.includes(firstWord)) {
      searchType = firstWord;
      rawQuery = rawQuery.substring(firstWord.length).trim();
    }"""

new = """  // /find and /find_global commands — intercept, do NOT send to AI
  hideTypeAutocomplete();
  hideFindChips();
  // Match: /find-TYPE query, /find_global-TYPE query, /find query, /find_global query
  const typedFindMatch = text.match(/^\\/find(_global)?(?:-(email|webclip|screenshot|contact|document|conversation))?(?:\\s+(.*))?$/i);
  if (typedFindMatch && getAgentName() !== 'Kein Agent') {
    const isGlobal = !!typedFindMatch[1];
    let searchType = typedFindMatch[2] ? typedFindMatch[2].toLowerCase() : null;
    let rawQuery = (typedFindMatch[3] || '').trim();
    // Also check for old-style /find email query (type as first word)
    if (!searchType) {
      const knownTypes = ['email','webclip','screenshot','contact','document','conversation'];
      const firstWord = rawQuery.split(/\\s+/)[0].toLowerCase();
      if (knownTypes.includes(firstWord)) {
        searchType = firstWord;
        rawQuery = rawQuery.substring(firstWord.length).trim();
      }
    }"""

if old in code:
    code = code.replace(old, new, 1)
    changes += 1
    print("5. sendMessage: parse /find-TYPE and /find_global-TYPE")
else:
    print("WARN: sendMessage /find block not found")

# ═══════════════════════════════════════════════════════════════════════════════
# 6. Update live search to handle /find-TYPE pattern
# ═══════════════════════════════════════════════════════════════════════════════

old = """  var m = val.match(/^\\/find(_global)?\\s+(\\S+\\s+)?(.*)/i);"""
new = """  var m = val.match(/^\\/find(_global)?(?:-(email|webclip|screenshot|document|conversation))?\\s+(.*)/i);"""

if old in code:
    code = code.replace(old, new, 1)
    changes += 1
    print("6. Live search regex updated for /find-TYPE")
else:
    print("WARN: live search regex not found")

# Also fix the match group references
old = """  var isGlobal = !!m[1];
  var typePart = (m[2]||'').trim();
  var queryPart = (m[3]||'').trim();"""
new = """  var isGlobal = !!m[1];
  var typePart = (m[2]||'').trim();
  var queryPart = (m[3]||'').trim();
  // Strip old-style type prefix from query if present
  var knTypes = ['email','webclip','screenshot','contact','document','conversation'];
  var qFirst = queryPart.split(/\\s+/)[0];
  if (knTypes.includes(qFirst.toLowerCase())) queryPart = queryPart.substring(qFirst.length).trim();"""

if old in code:
    code = code.replace(old, new, 1)
    changes += 1
    print("6b. Live search: strip old-style type from query")

with open(SRC, 'w') as f:
    f.write(code)

print(f"\n{changes} changes applied.")
