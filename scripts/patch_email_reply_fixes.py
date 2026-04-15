#!/usr/bin/env python3
"""Fix: E-Mail Reply Feature - zwei Bugs
Bug 1: E-Mail-Such-Modal mit Filtern + "In Chat laden" Funktion
Bug 2: Sub-Agent-Routing wird bei E-Mail-Kontext-Nachrichten uebersprungen
"""
import sys

path = '/Users/moritzcremer/AssistantDev/src/web_server.py'
with open(path, 'r') as f:
    content = f.read()

def must_replace(label, old, new):
    global content
    if old not in content:
        print(f"FEHLER bei {label}: Suchstring nicht gefunden!", file=sys.stderr)
        sys.exit(1)
    content = content.replace(old, new, 1)
    print(f"OK: {label}")

# ═══════════════════════════════════════════════════════════════
# BUG 2: Skip Sub-Agent-Routing when E-Mail context is active
# ═══════════════════════════════════════════════════════════════
must_replace("Bug2: Skip delegation bei E-Mail-Kontext",
"    # Check for sub-agent delegation (requires user confirmation)\n"
"    if state['agent'] and not kwargs.get('skip_delegation'):\n"
"        deleg_info = detect_delegation(msg, state['agent'])",
"    # Check for sub-agent delegation (requires user confirmation)\n"
"    # Skip delegation check when email reply context is active\n"
"    _skip_deleg = kwargs.get('skip_delegation') or msg.startswith('[E-MAIL KONTEXT:')\n"
"    if state['agent'] and not _skip_deleg:\n"
"        deleg_info = detect_delegation(msg, state['agent'])")

# ═══════════════════════════════════════════════════════════════
# BUG 1: Add Email Search Modal with filters
# ═══════════════════════════════════════════════════════════════

# 1a. Add CSS for the email search modal
must_replace("Bug1: CSS Email-Such-Modal",
"  /* Email Card in Chat */",
"  /* Email Search Modal */\n"
"  #email-search-modal { display:none; position:fixed; inset:0; background:rgba(0,0,0,0.85); z-index:200; align-items:center; justify-content:center; }\n"
"  #email-search-modal.show { display:flex; }\n"
"  #email-search-box { background:#1a1a1a; border:1px solid #333; border-radius:12px; padding:20px; width:600px; max-width:92vw; max-height:85vh; display:flex; flex-direction:column; }\n"
"  #email-search-box h2 { margin:0 0 12px; font-size:16px; color:#e0e0e0; }\n"
"  .esm-filters { display:flex; gap:8px; margin-bottom:10px; flex-wrap:wrap; }\n"
"  .esm-filter { flex:1; min-width:120px; }\n"
"  .esm-filter label { display:block; font-size:10px; color:#666; margin-bottom:3px; text-transform:uppercase; letter-spacing:0.5px; }\n"
"  .esm-filter input { width:100%; background:#111; border:1px solid #333; border-radius:5px; color:#e0e0e0; padding:6px 8px; font-size:13px; font-family:Inter,sans-serif; box-sizing:border-box; }\n"
"  .esm-filter input:focus { border-color:#4a8aca; outline:none; }\n"
"  .esm-filter input::placeholder { color:#555; }\n"
"  #esm-results { flex:1; overflow-y:auto; max-height:50vh; margin-top:8px; }\n"
"  .esm-result { padding:10px 12px; border:1px solid #2a2a3e; border-radius:8px; margin:5px 0; cursor:pointer; transition:background 0.15s, border-color 0.15s; background:#111; }\n"
"  .esm-result:hover { background:#1a1a3a; border-color:#4a8aca; }\n"
"  .esm-result-from { font-size:13px; color:#e0e0e0; }\n"
"  .esm-result-email { font-size:11px; color:#777; margin-left:4px; }\n"
"  .esm-result-subject { font-size:12px; color:#aaa; margin-top:3px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }\n"
"  .esm-result-date { font-size:10px; color:#555; float:right; }\n"
"  .esm-result-meta { font-size:10px; color:#555; margin-top:2px; }\n"
"  .esm-hint { text-align:center; color:#555; font-size:12px; padding:20px 0; }\n"
"  .esm-loading { text-align:center; color:#888; font-size:12px; padding:15px 0; }\n"
"  .esm-footer { display:flex; justify-content:flex-end; margin-top:10px; gap:8px; }\n"
"  .esm-btn { padding:6px 16px; border-radius:6px; border:none; cursor:pointer; font-size:13px; font-family:Inter,sans-serif; }\n"
"  .esm-btn-close { background:#333; color:#aaa; }\n"
"  .esm-btn-close:hover { background:#444; color:#fff; }\n"
"  /* Email Card in Chat */")

# 1b. Add Modal HTML (before search-overlay)
must_replace("Bug1: HTML Email-Such-Modal",
'<div id="search-overlay">',
'<div id="email-search-modal">\n'
'  <div id="email-search-box">\n'
'    <h2>\\u2709 E-Mail suchen</h2>\n'
'    <div class="esm-filters">\n'
'      <div class="esm-filter"><label>Von</label><input type="text" id="esm-from" placeholder="Absender..." /></div>\n'
'      <div class="esm-filter"><label>Betreff</label><input type="text" id="esm-subject" placeholder="Betreff..." /></div>\n'
'    </div>\n'
'    <div class="esm-filters">\n'
'      <div class="esm-filter"><label>An / CC</label><input type="text" id="esm-to" placeholder="Empfaenger..." /></div>\n'
'      <div class="esm-filter"><label>Freitext</label><input type="text" id="esm-body" placeholder="Inhalt..." /></div>\n'
'    </div>\n'
'    <div id="esm-results"><div class="esm-hint">Mindestens 2 Zeichen in ein Feld eingeben...</div></div>\n'
'    <div class="esm-footer">\n'
'      <button class="esm-btn esm-btn-close" onclick="closeEmailSearchModal()">Schliessen</button>\n'
'    </div>\n'
'  </div>\n'
'</div>\n'
'\n'
'<div id="search-overlay">')

# 1c. Replace old /reply-based JS with new modal-based JS
# We keep the email card display and context injection, but replace the search trigger
old_js_start = content.index('// \u2500\u2500\u2500 EMAIL CHAT FLOW')
old_js_end = content.index("  if (entry && entry.template) {", old_js_start)
old_js = content[old_js_start:old_js_end]

new_js = (
'// \u2500\u2500\u2500 EMAIL SEARCH MODAL + CHAT FLOW \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n'
'let _emailContext = null;\n'
'let _esmDebounce = null;\n'
'\n'
'function showEmailSearchModal() {\n'
"  document.getElementById('esm-from').value = '';\n"
"  document.getElementById('esm-subject').value = '';\n"
"  document.getElementById('esm-to').value = '';\n"
"  document.getElementById('esm-body').value = '';\n"
"  document.getElementById('esm-results').innerHTML = '<div class=\"esm-hint\">Mindestens 2 Zeichen in ein Feld eingeben...</div>';\n"
"  var m = document.getElementById('email-search-modal');\n"
"  m.classList.add('show'); m.style.display = 'flex';\n"
"  setTimeout(function() { document.getElementById('esm-from').focus(); }, 100);\n"
'}\n'
'\n'
'function closeEmailSearchModal() {\n'
"  var m = document.getElementById('email-search-modal');\n"
"  m.classList.remove('show'); m.style.display = 'none';\n"
'}\n'
'\n'
'function _esmDoSearch() {\n'
"  var from = document.getElementById('esm-from').value.trim();\n"
"  var subj = document.getElementById('esm-subject').value.trim();\n"
"  var to = document.getElementById('esm-to').value.trim();\n"
"  var body = document.getElementById('esm-body').value.trim();\n"
'  // Need at least 2 chars in any field\n'
'  var q = from || subj || to || body;\n'
"  if (!q || q.length < 2) { document.getElementById('esm-results').innerHTML = '<div class=\"esm-hint\">Mindestens 2 Zeichen in ein Feld eingeben...</div>'; return; }\n"
"  document.getElementById('esm-results').innerHTML = '<div class=\"esm-loading\">Suche...</div>';\n"
'  var agent = getAgentName();\n'
"  var params = 'agent=' + encodeURIComponent(agent);\n"
"  if (from) params += '&from=' + encodeURIComponent(from);\n"
"  if (subj) params += '&subject=' + encodeURIComponent(subj);\n"
"  if (to) params += '&to=' + encodeURIComponent(to);\n"
"  if (body) params += '&body=' + encodeURIComponent(body);\n"
"  // Also send combined q for backwards compat\n"
"  params += '&q=' + encodeURIComponent([from, subj, to, body].filter(Boolean).join(' '));\n"
"  fetch('/api/email-search?' + params)\n"
'    .then(function(r) { return r.json(); })\n'
'    .then(function(results) {\n'
"      var container = document.getElementById('esm-results');\n"
'      if (!results || results.length === 0) {\n'
"        container.innerHTML = '<div class=\"esm-hint\">Keine E-Mails gefunden</div>';\n"
'        return;\n'
'      }\n'
"      container.innerHTML = '';\n"
'      results.forEach(function(item, idx) {\n'
"        var div = document.createElement('div');\n"
"        div.className = 'esm-result';\n"
"        div.innerHTML = '<div><span class=\"esm-result-from\">' + escHtml(item.from_name || item.from_email) + '</span>'\n"
"          + (item.from_name ? '<span class=\"esm-result-email\">&lt;' + escHtml(item.from_email) + '&gt;</span>' : '')\n"
"          + '<span class=\"esm-result-date\">' + escHtml(item.date) + '</span></div>'\n"
"          + '<div class=\"esm-result-subject\">' + escHtml(item.subject || '(kein Betreff)') + '</div>'\n"
"          + (item.to ? '<div class=\"esm-result-meta\">An: ' + escHtml(item.to).substring(0,60) + '</div>' : '');\n"
'        div.onclick = function() { _esmSelectEmail(item); };\n'
"        container.appendChild(div);\n"
'      });\n'
'    })\n'
"    .catch(function(e) { document.getElementById('esm-results').innerHTML = '<div class=\"esm-hint\">Fehler: ' + escHtml(e.message) + '</div>'; });\n"
'}\n'
'\n'
'function _esmSelectEmail(item) {\n'
'  closeEmailSearchModal();\n'
'  _openEmailInChat(item);\n'
'}\n'
'\n'
'// Attach search listeners on DOMContentLoaded\n'
"document.addEventListener('DOMContentLoaded', function() {\n"
"  ['esm-from','esm-subject','esm-to','esm-body'].forEach(function(id) {\n"
"    var el = document.getElementById(id);\n"
'    if (el) {\n'
"      el.addEventListener('input', function() {\n"
'        clearTimeout(_esmDebounce);\n'
'        _esmDebounce = setTimeout(_esmDoSearch, 300);\n'
'      });\n'
"      el.addEventListener('keydown', function(e) {\n"
"        if (e.key === 'Escape') closeEmailSearchModal();\n"
'      });\n'
'    }\n'
'  });\n'
"  var modal = document.getElementById('email-search-modal');\n"
"  if (modal) modal.addEventListener('click', function(e) { if (e.target === modal) closeEmailSearchModal(); });\n"
'});\n'
'\n'
'function _openEmailInChat(emailMeta) {\n'
"  addStatusMsg('Lade E-Mail...');\n"
'  var agent = getAgentName();\n'
"  fetch('/api/email-content?agent=' + encodeURIComponent(agent) + '&message_id=' + encodeURIComponent(emailMeta.message_id || '') + '&from_email=' + encodeURIComponent(emailMeta.from_email || '') + '&subject=' + encodeURIComponent(emailMeta.subject || ''))\n"
'    .then(function(r) { return r.json(); })\n'
'    .then(function(data) {\n'
"      if (!data.ok) { addStatusMsg('E-Mail konnte nicht geladen werden: ' + (data.error || 'unbekannt')); return; }\n"
'      _showEmailCard(data);\n'
'    })\n'
"    .catch(function(e) { addStatusMsg('Fehler: ' + e.message); });\n"
'}\n'
'\n'
'function _showEmailCard(email) {\n'
"  var msgs = document.getElementById('messages');\n"
"  var div = document.createElement('div');\n"
"  div.className = 'msg assistant';\n"
"  var time = new Date().toLocaleTimeString('de-DE', {hour:'2-digit', minute:'2-digit'});\n"
"  var fromDisplay = email.from_name ? escHtml(email.from_name) + ' &lt;' + escHtml(email.from_email) + '&gt;' : escHtml(email.from_email);\n"
"  var bodyText = email.body || '(kein Inhalt)';\n"
"  var ccDisplay = email.cc ? escHtml(email.cc) : '';\n"
"  var cardId = 'ec-' + Date.now();\n"
"  var html = '<div class=\"bubble\"><div class=\"email-card\">'\n"
"    + '<div class=\"email-card-header\">'\n"
"    + '<div class=\"email-card-label\">\\\\u2709 E-Mail</div>'\n"
"    + '<div class=\"email-card-subject\">' + escHtml(email.subject || '(kein Betreff)') + '</div>'\n"
"    + '<div class=\"email-card-row\"><strong>Von:</strong> ' + fromDisplay + '</div>'\n"
"    + '<div class=\"email-card-row\"><strong>An:</strong> ' + escHtml(email.to || '') + '</div>'\n"
"    + (ccDisplay ? '<div class=\"email-card-row\"><strong>CC:</strong> ' + ccDisplay + '</div>' : '')\n"
"    + '<div class=\"email-card-date\">' + escHtml(email.date || '') + '</div>'\n"
"    + '</div>'\n"
"    + '<div class=\"email-card-body\">' + escHtml(bodyText) + '</div>'\n"
"    + (email.message_id ? '<div class=\"email-card-msgid\">Message-ID: ' + escHtml(email.message_id) + '</div>' : '')\n"
"    + '<div class=\"email-card-actions\">'\n"
"    + '<button class=\"email-card-btn email-card-btn-reply\" data-card=\"' + cardId + '\">Antworten</button>'\n"
"    + '<button class=\"email-card-btn email-card-btn-close\" data-card=\"' + cardId + '\">Schliessen</button>'\n"
"    + '</div>'\n"
"    + '</div></div><div class=\"meta\">' + time + '</div>';\n"
'  div.innerHTML = html;\n'
'  div.id = cardId;\n'
'  msgs.appendChild(div);\n'
'  scrollDown();\n'
'\n'
"  div.querySelector('.email-card-btn-reply').onclick = function() {\n"
"    var ownAddrs = ['moritz.cremer@me.com', 'londoncityfox@gmail.com', 'moritz.cremer@signicat.com'];\n"
'    var ccParts = [];\n'
"    [email.to || '', email.cc || ''].forEach(function(field) {\n"
'      if (!field) return;\n'
"      field.split(',').forEach(function(addr) {\n"
'        addr = addr.trim();\n'
"        var em = addr.includes('<') ? addr.substring(addr.indexOf('<')+1, addr.indexOf('>')) : addr;\n"
'        if (em && !ownAddrs.includes(em.toLowerCase().trim())) ccParts.push(addr);\n'
'      });\n'
'    });\n'
'    _emailContext = {\n'
"      from_email: email.from_email || '',\n"
"      from_name: email.from_name || '',\n"
"      subject: email.subject || '',\n"
"      message_id: email.message_id || '',\n"
"      cc: ccParts.join(', ')\n"
'    };\n'
"    addStatusMsg('E-Mail-Kontext gesetzt. Schreibe jetzt deine Antwort-Anweisung.');\n"
"    document.getElementById('msg-input').focus();\n"
"    this.textContent = '\\\\u2713 Kontext gesetzt';\n"
"    this.style.background = '#2a5a2a';\n"
'    this.onclick = null;\n'
'  };\n'
"  div.querySelector('.email-card-btn-close').onclick = function() { div.remove(); };\n"
'}\n'
'\n'
'function _getAndClearEmailContext() {\n'
'  if (!_emailContext) return null;\n'
'  var ctx = _emailContext;\n'
'  _emailContext = null;\n'
'  return ctx;\n'
'}\n'
'\n'
'function selectSlashCmd(inputEl, cmd) {\n'
'  var entry = _SLASH_COMMANDS.find(c => c.cmd === cmd);\n'
"  if (cmd === '/create-email-reply' || cmd === '/reply') {\n"
"    inputEl.value = '';\n"
'    hideSlashAutocomplete();\n'
'    showEmailSearchModal();\n'
'    return;\n'
'  }\n'
)

content = content.replace(old_js, new_js)
print("OK: JS: Chat-Flow -> Modal mit Filtern + Chat-Card")

# 1d. Update /reply slash command to open modal
# Already handled in selectSlashCmd above

# 1e. Remove /reply intercept from sendMessage (no longer needed, modal handles it)
must_replace("Bug1: /reply Intercept entfernen",
"  // EMAIL_CHAT_FLOW: /reply triggers email search in chat\n"
"  if (text.startsWith('/reply ')) {\n"
"    var emailQuery = text.substring(7).trim();\n"
"    if (emailQuery.length >= 2) { _emailSearchInChat(emailQuery); return; }\n"
"  }\n"
"  doSendChat(text);",
"  doSendChat(text);")

# 1f. Update backend /api/email-search to support field-specific filters
must_replace("Bug1: Backend Suchfilter erweitern",
"                # Check if query matches\n"
"                searchable = (parsed['from_name'] + ' ' + parsed['from_email'] + ' ' + parsed['subject']).lower()\n"
"                if q in searchable:\n"
"                    results.append(parsed)",
"                # Check if query matches (supports field-specific filters)\n"
"                from_filter = request.args.get('from', '').strip().lower()\n"
"                subj_filter = request.args.get('subject', '').strip().lower()\n"
"                to_filter = request.args.get('to', '').strip().lower()\n"
"                body_filter = request.args.get('body', '').strip().lower()\n"
"                match = True\n"
"                if from_filter:\n"
"                    if from_filter not in (parsed['from_name'] + ' ' + parsed['from_email']).lower():\n"
"                        match = False\n"
"                if subj_filter and match:\n"
"                    if subj_filter not in parsed['subject'].lower():\n"
"                        match = False\n"
"                if to_filter and match:\n"
"                    if to_filter not in (parsed.get('to','') + ' ' + parsed.get('cc','')).lower():\n"
"                        match = False\n"
"                if not from_filter and not subj_filter and not to_filter and q:\n"
"                    searchable = (parsed['from_name'] + ' ' + parsed['from_email'] + ' ' + parsed['subject']).lower()\n"
"                    if q not in searchable:\n"
"                        match = False\n"
"                if match:\n"
"                    results.append(parsed)")

# Write once
with open(path, 'w') as f:
    f.write(content)

print("\nAlle Patches erfolgreich angewendet!")
