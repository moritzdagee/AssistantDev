#!/usr/bin/env python3
"""Patch v3: Replace Email Reply Modal with chat-native email flow.
All patches applied atomically in memory, single file write at end.
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
# 1. Replace old modal CSS with email-card CSS
# ═══════════════════════════════════════════════════════════════
must_replace("CSS: Modal -> Email-Card",
"  /* Email Reply Modal */\n"
"  #email-reply-modal { display:none; position:fixed; inset:0; background:rgba(0,0,0,0.85); z-index:200; align-items:center; justify-content:center; }\n"
"  #email-reply-modal.show { display:flex; }\n"
"  #email-reply-box { background:#1a1a1a; border:1px solid #333; border-radius:12px; padding:24px; width:560px; max-width:90vw; max-height:85vh; overflow-y:auto; }\n"
"  #email-reply-box h2 { margin:0 0 16px; font-size:18px; color:#e0e0e0; }\n"
"  .er-field { margin-bottom:12px; }\n"
"  .er-field label { display:block; font-size:12px; color:#888; margin-bottom:4px; font-family:Inter,sans-serif; }\n"
"  .er-field input, .er-field textarea { width:100%; background:#111; border:1px solid #333; border-radius:6px; color:#e0e0e0; padding:8px 10px; font-size:14px; font-family:Inter,sans-serif; box-sizing:border-box; }\n"
"  .er-field input:focus, .er-field textarea:focus { border-color:#4a8aca; outline:none; }\n"
"  .er-field textarea { min-height:120px; resize:vertical; }\n"
"  .er-field-row { position:relative; }\n"
"  .er-search-dropdown { position:absolute; top:100%; left:0; right:0; background:#1e1e1e; border:1px solid #444; border-radius:6px; max-height:320px; overflow-y:auto; z-index:300; margin-top:2px; display:none; }\n"
"  .er-search-dropdown.visible { display:block; }\n"
"  .er-search-item { padding:8px 12px; cursor:pointer; border-bottom:1px solid #2a2a2a; transition:background 0.1s; }\n"
"  .er-search-item:hover, .er-search-item.active { background:#2a2a5a; }\n"
"  .er-search-item:last-child { border-bottom:none; }\n"
"  .er-search-from { font-size:13px; color:#e0e0e0; }\n"
"  .er-search-email { font-size:11px; color:#888; margin-left:6px; }\n"
"  .er-search-subject { font-size:12px; color:#aaa; margin-top:2px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }\n"
"  .er-search-date { font-size:10px; color:#666; float:right; margin-top:2px; }\n"
"  .er-search-hint { padding:10px 12px; color:#666; font-size:12px; text-align:center; }\n"
"  .er-search-loading { padding:10px 12px; color:#888; font-size:12px; text-align:center; }\n"
"  .er-btn-row { display:flex; gap:10px; margin-top:16px; }\n"
"  .er-btn { padding:8px 20px; border-radius:6px; border:none; cursor:pointer; font-size:14px; font-family:Inter,sans-serif; }\n"
"  .er-btn-primary { background:#4a8aca; color:#fff; }\n"
"  .er-btn-primary:hover { background:#5a9ada; }\n"
"  .er-btn-secondary { background:#333; color:#ccc; }\n"
"  .er-btn-secondary:hover { background:#444; }\n"
"  .er-msg-id { font-size:10px; color:#555; margin-top:2px; word-break:break-all; }\n"
"  ",
# NEW CSS
"  /* Email Card in Chat */\n"
"  .email-card { background:#1a1a2e; border:1px solid #334; border-radius:10px; margin:8px 0; overflow:hidden; font-family:Inter,sans-serif; }\n"
"  .email-card-header { padding:12px 16px 8px; border-bottom:1px solid #2a2a3e; }\n"
"  .email-card-label { font-size:10px; color:#6a8aca; text-transform:uppercase; letter-spacing:1px; font-weight:600; margin-bottom:8px; }\n"
"  .email-card-row { font-size:12px; color:#bbb; margin:3px 0; line-height:1.5; }\n"
"  .email-card-row strong { color:#e0e0e0; font-weight:500; min-width:60px; display:inline-block; }\n"
"  .email-card-subject { font-size:14px; color:#e8e8e8; font-weight:600; margin:6px 0 2px; }\n"
"  .email-card-date { font-size:11px; color:#666; }\n"
"  .email-card-body { padding:12px 16px; max-height:400px; overflow-y:auto; font-size:13px; color:#ccc; line-height:1.6; white-space:pre-wrap; word-wrap:break-word; border-top:1px solid #2a2a3e; }\n"
"  .email-card-body::-webkit-scrollbar { width:6px; }\n"
"  .email-card-body::-webkit-scrollbar-thumb { background:#444; border-radius:3px; }\n"
"  .email-card-msgid { padding:4px 16px 8px; font-size:10px; color:#444; word-break:break-all; }\n"
"  .email-card-actions { padding:8px 16px 12px; display:flex; gap:8px; border-top:1px solid #2a2a3e; }\n"
"  .email-card-btn { padding:6px 16px; border-radius:6px; border:none; cursor:pointer; font-size:12px; font-family:Inter,sans-serif; transition:background 0.15s; }\n"
"  .email-card-btn-reply { background:#4a8aca; color:#fff; }\n"
"  .email-card-btn-reply:hover { background:#5a9ada; }\n"
"  .email-card-btn-close { background:#333; color:#aaa; }\n"
"  .email-card-btn-close:hover { background:#444; color:#fff; }\n"
"  .email-search-card { background:#1a1a2e; border:1px solid #334; border-radius:8px; padding:10px 14px; margin:6px 0; cursor:pointer; transition:background 0.15s, border-color 0.15s; }\n"
"  .email-search-card:hover { background:#22224a; border-color:#4a8aca; }\n"
"  .email-search-card-from { font-size:13px; color:#e0e0e0; }\n"
"  .email-search-card-email { font-size:11px; color:#888; margin-left:4px; }\n"
"  .email-search-card-subject { font-size:12px; color:#aaa; margin-top:3px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }\n"
"  .email-search-card-date { font-size:10px; color:#555; float:right; }\n"
"  ")

# ═══════════════════════════════════════════════════════════════
# 2. Remove old modal HTML
# ═══════════════════════════════════════════════════════════════
old_modal = '<div id="email-reply-modal">'
end_modal = '</div>\n\n<div id="search-overlay">'
start_idx = content.index(old_modal)
end_idx = content.index(end_modal, start_idx) + len(end_modal)
old_block = content[start_idx:end_idx]
content = content.replace(old_block, '<div id="search-overlay">')
print("OK: HTML: Modal entfernt")

# ═══════════════════════════════════════════════════════════════
# 3. Replace entire old Modal JS block
# ═══════════════════════════════════════════════════════════════
js_start_marker = '// \u2500\u2500\u2500 EMAIL REPLY MODAL'
js_end_marker = '  if (entry && entry.template) {'
js_start = content.index(js_start_marker)
js_end = content.index(js_end_marker, js_start)
old_js = content[js_start:js_end]

new_js = (
'// \u2500\u2500\u2500 EMAIL CHAT FLOW (replaces old modal) \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n'
'let _emailContext = null;\n'
'\n'
'function _emailSearchInChat(query) {\n'
'  if (!query || query.length < 2) return;\n'
'  addStatusMsg(\'Suche E-Mails: \' + query + \'...\');\n'
'  var agent = getAgentName();\n'
'  fetch(\'/api/email-search?agent=\' + encodeURIComponent(agent) + \'&q=\' + encodeURIComponent(query))\n'
'    .then(function(r) { return r.json(); })\n'
'    .then(function(results) {\n'
'      if (!results || results.length === 0) {\n'
'        addStatusMsg(\'Keine E-Mails gefunden fuer: \' + query);\n'
'        return;\n'
'      }\n'
'      var msgs = document.getElementById(\'messages\');\n'
'      var div = document.createElement(\'div\');\n'
'      div.className = \'msg assistant\';\n'
'      var time = new Date().toLocaleTimeString(\'de-DE\', {hour:\'2-digit\', minute:\'2-digit\'});\n'
'      var html = \'<div class="bubble"><div style="margin:4px 0;">\';\n'
"      html += '<div style=\"font-size:12px;color:#6a8aca;margin-bottom:8px;font-weight:600;\">\\\\u2709 ' + results.length + ' E-Mail(s) gefunden \\\\u2014 klicke zum Oeffnen</div>';\n"
'      results.forEach(function(item, idx) {\n'
"        html += '<div class=\"email-search-card\" data-eidx=\"' + idx + '\">'\n"
"          + '<div><span class=\"email-search-card-from\">' + escHtml(item.from_name || item.from_email) + '</span>'\n"
"          + (item.from_name ? '<span class=\"email-search-card-email\">&lt;' + escHtml(item.from_email) + '&gt;</span>' : '')\n"
"          + '<span class=\"email-search-card-date\">' + escHtml(item.date) + '</span></div>'\n"
"          + '<div class=\"email-search-card-subject\">' + escHtml(item.subject || '(kein Betreff)') + '</div>'\n"
"          + '</div>';\n"
'      });\n'
'      html += \'</div></div><div class="meta">\' + time + \'</div>\';\n'
'      div.innerHTML = html;\n'
'      msgs.appendChild(div);\n'
'      scrollDown();\n'
'      div.querySelectorAll(\'.email-search-card\').forEach(function(card) {\n'
'        card.onclick = function() {\n'
'          var idx = parseInt(card.dataset.eidx);\n'
'          _openEmailInChat(results[idx]);\n'
'        };\n'
'      });\n'
'    })\n'
'    .catch(function(e) { addStatusMsg(\'E-Mail-Suche fehlgeschlagen: \' + e.message); });\n'
'}\n'
'\n'
'function _openEmailInChat(emailMeta) {\n'
'  addStatusMsg(\'Lade E-Mail...\');\n'
'  var agent = getAgentName();\n'
'  fetch(\'/api/email-content?agent=\' + encodeURIComponent(agent) + \'&message_id=\' + encodeURIComponent(emailMeta.message_id || \'\') + \'&from_email=\' + encodeURIComponent(emailMeta.from_email || \'\') + \'&subject=\' + encodeURIComponent(emailMeta.subject || \'\'))\n'
'    .then(function(r) { return r.json(); })\n'
'    .then(function(data) {\n'
'      if (!data.ok) { addStatusMsg(\'E-Mail konnte nicht geladen werden: \' + (data.error || \'unbekannt\')); return; }\n'
'      _showEmailCard(data);\n'
'    })\n'
'    .catch(function(e) { addStatusMsg(\'Fehler: \' + e.message); });\n'
'}\n'
'\n'
'function _showEmailCard(email) {\n'
'  var msgs = document.getElementById(\'messages\');\n'
'  var div = document.createElement(\'div\');\n'
'  div.className = \'msg assistant\';\n'
'  var time = new Date().toLocaleTimeString(\'de-DE\', {hour:\'2-digit\', minute:\'2-digit\'});\n'
'  var fromDisplay = email.from_name ? escHtml(email.from_name) + \' &lt;\' + escHtml(email.from_email) + \'&gt;\' : escHtml(email.from_email);\n'
'  var bodyText = email.body || \'(kein Inhalt)\';\n'
'  var ccDisplay = email.cc ? escHtml(email.cc) : \'\';\n'
'  var cardId = \'ec-\' + Date.now();\n'
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
'  div.querySelector(\'.email-card-btn-reply\').onclick = function() {\n'
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
"  if (cmd === '/create-email-reply') {\n"
"    inputEl.value = '/reply ';\n"
'    hideSlashAutocomplete();\n'
'    inputEl.focus();\n'
'    return;\n'
'  }\n'
)

content = content.replace(old_js, new_js)
print("OK: JS: Modal -> Chat-native Email Flow")

# ═══════════════════════════════════════════════════════════════
# 4. /reply intercept in sendMessage
# ═══════════════════════════════════════════════════════════════
must_replace("sendMessage: /reply Intercept",
"  addMessage('user', text);\n"
"  scrollDown();\n"
"  doSendChat(text);\n"
"}",
"  addMessage('user', text);\n"
"  scrollDown();\n"
"  // EMAIL_CHAT_FLOW: /reply triggers email search in chat\n"
"  if (text.startsWith('/reply ')) {\n"
"    var emailQuery = text.substring(7).trim();\n"
"    if (emailQuery.length >= 2) { _emailSearchInChat(emailQuery); return; }\n"
"  }\n"
"  doSendChat(text);\n"
"}")

# ═══════════════════════════════════════════════════════════════
# 5. Inject email context into doSendChat
# ═══════════════════════════════════════════════════════════════
must_replace("doSendChat: Email-Kontext",
"async function doSendChat(text) {\n"
"  startTyping(text.substring(0,50));",
"async function doSendChat(text) {\n"
"  // Inject email context if set (one-time use)\n"
"  var ectx = _getAndClearEmailContext();\n"
"  if (ectx) {\n"
"    var ctxBlock = '[E-MAIL KONTEXT: Von: ' + ectx.from_email + (ectx.from_name ? ' (' + ectx.from_name + ')' : '') + ', Betreff: ' + ectx.subject + ', Message-ID: ' + ectx.message_id + (ectx.cc ? ', CC: ' + ectx.cc : '') + ']\\\\n\\\\nUser-Anweisung: ';\n"
"    text = ctxBlock + text;\n"
"  }\n"
"  startTyping(text.substring(0,50));")

# ═══════════════════════════════════════════════════════════════
# 6. Add /reply slash command
# ═══════════════════════════════════════════════════════════════
must_replace("Slash: /reply",
"  {cmd: '/create-email-reply', label: '/create-email-reply', desc: 'E-Mail Antwort erstellen', template: 'Antworte auf die E-Mail von [Absender] zum Thema [Betreff]: ', group: 'Kommunikation'},",
"  {cmd: '/create-email-reply', label: '/create-email-reply', desc: 'E-Mail Antwort erstellen', template: 'Antworte auf die E-Mail von [Absender] zum Thema [Betreff]: ', group: 'Kommunikation'},\n"
"  {cmd: '/reply', label: '/reply [suche]', desc: 'E-Mail suchen und im Chat oeffnen', template: '/reply ', group: 'Kommunikation'},")

# ═══════════════════════════════════════════════════════════════
# 7. Backend route /api/email-content
# ═══════════════════════════════════════════════════════════════
email_content_route = '''


@app.route('/api/email-content')
def email_content_route():
    \\'\\'\\'Load full email content for display in chat.\\'\\'\\'
    import email as _email_mod
    from email.header import decode_header as _dec_hdr
    agent = request.args.get('agent', 'standard')
    target_mid = request.args.get('message_id', '').strip()
    target_from = request.args.get('from_email', '').strip().lower()
    target_subj = request.args.get('subject', '').strip().lower()

    if not target_mid and not target_from:
        return jsonify({'ok': False, 'error': 'message_id or from_email required'})

    def _dec(val):
        if not val:
            return ''
        parts = _dec_hdr(val)
        decoded = []
        for part, charset in parts:
            if isinstance(part, bytes):
                decoded.append(part.decode(charset or 'utf-8', errors='replace'))
            else:
                decoded.append(part)
        return ' '.join(decoded)

    def _get_body(msg):
        if msg.is_multipart():
            for part in msg.walk():
                ct = part.get_content_type()
                if ct == 'text/plain':
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or 'utf-8'
                        return payload.decode(charset, errors='replace')
            for part in msg.walk():
                ct = part.get_content_type()
                if ct == 'text/html':
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or 'utf-8'
                        import re as _re
                        html = payload.decode(charset, errors='replace')
                        return _re.sub(r'<[^>]+>', '', html)[:3000]
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or 'utf-8'
                return payload.decode(charset, errors='replace')
        return ''

    search_dirs = []
    speicher = get_agent_speicher(agent)
    memory_dir = os.path.join(speicher, 'memory')
    if os.path.exists(memory_dir):
        search_dirs.append(memory_dir)
    inbox_dir = os.path.join(BASE, 'email_inbox')
    if os.path.exists(inbox_dir):
        search_dirs.append(inbox_dir)

    for sdir in search_dirs:
        try:
            for fname in os.listdir(sdir):
                if not fname.endswith('.eml'):
                    continue
                fpath = os.path.join(sdir, fname)
                try:
                    with open(fpath, 'r', errors='replace') as f:
                        msg = _email_mod.message_from_file(f)
                    mid = msg.get('Message-ID', '').strip()
                    if target_mid and mid == target_mid:
                        pass
                    elif target_from:
                        from_raw = _dec(msg.get('From', '')).lower()
                        subj_raw = _dec(msg.get('Subject', '')).lower()
                        if target_from not in from_raw:
                            continue
                        if target_subj and target_subj not in subj_raw:
                            continue
                    else:
                        continue

                    from_raw = _dec(msg.get('From', ''))
                    from_name = ''
                    from_email = from_raw
                    if '<' in from_raw and '>' in from_raw:
                        from_name = from_raw[:from_raw.index('<')].strip().strip('"')
                        from_email = from_raw[from_raw.index('<')+1:from_raw.index('>')]

                    date_display = ''
                    try:
                        from email.utils import parsedate_to_datetime
                        dt = parsedate_to_datetime(msg.get('Date', ''))
                        date_display = dt.strftime('%d.%m.%Y %H:%M')
                    except Exception:
                        date_display = (msg.get('Date', '') or '')[:30]

                    body = _get_body(msg)
                    if len(body) > 5000:
                        body = body[:5000] + '\\n\\n[... gekuerzt, ' + str(len(body)) + ' Zeichen gesamt]'

                    return jsonify({
                        'ok': True,
                        'from_name': from_name,
                        'from_email': from_email,
                        'to': _dec(msg.get('To', '')),
                        'cc': _dec(msg.get('Cc', '')),
                        'subject': _dec(msg.get('Subject', '')),
                        'date': date_display,
                        'message_id': mid,
                        'body': body,
                        'file': fname,
                    })
                except Exception:
                    continue
        except Exception:
            continue

    return jsonify({'ok': False, 'error': 'E-Mail nicht gefunden'})'''

# Fix the escaped quotes in docstring
email_content_route = email_content_route.replace("\\'\\'\\'", '"""')

must_replace("Backend: /api/email-content",
"    # Sort by date_ts descending\n"
"    results.sort(key=lambda r: r.get('date_ts', 0), reverse=True)\n"
"    return jsonify(results[:8])",
"    # Sort by date_ts descending\n"
"    results.sort(key=lambda r: r.get('date_ts', 0), reverse=True)\n"
"    return jsonify(results[:8])" + email_content_route)

# Write once
with open(path, 'w') as f:
    f.write(content)

print("\nAlle Patches erfolgreich angewendet!")
