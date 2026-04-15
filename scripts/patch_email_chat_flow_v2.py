#!/usr/bin/env python3
"""Patch v2: Replace Email Reply Modal with chat-native email flow.
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
        # Show nearby context for debugging
        words = old[:60].strip()
        idx = content.find(words)
        if idx >= 0:
            print(f"  Teilmatch '{words}' gefunden bei Position {idx}", file=sys.stderr)
        sys.exit(1)
    content = content.replace(old, new, 1)
    print(f"OK: {label}")

# ══════════════════════════════════════════════════════════════════════
# 1. Replace old modal CSS with email-card CSS
# ══════════════════════════════════════════════════════════════════════
must_replace("CSS: Modal -> Email-Card",
# OLD
"""  /* Email Reply Modal */
  #email-reply-modal { display:none; position:fixed; inset:0; background:rgba(0,0,0,0.85); z-index:200; align-items:center; justify-content:center; }
  #email-reply-modal.show { display:flex; }
  #email-reply-box { background:#1a1a1a; border:1px solid #333; border-radius:12px; padding:24px; width:560px; max-width:90vw; max-height:85vh; overflow-y:auto; }
  #email-reply-box h2 { margin:0 0 16px; font-size:18px; color:#e0e0e0; }
  .er-field { margin-bottom:12px; }
  .er-field label { display:block; font-size:12px; color:#888; margin-bottom:4px; font-family:Inter,sans-serif; }
  .er-field input, .er-field textarea { width:100%; background:#111; border:1px solid #333; border-radius:6px; color:#e0e0e0; padding:8px 10px; font-size:14px; font-family:Inter,sans-serif; box-sizing:border-box; }
  .er-field input:focus, .er-field textarea:focus { border-color:#4a8aca; outline:none; }
  .er-field textarea { min-height:120px; resize:vertical; }
  .er-field-row { position:relative; }
  .er-search-dropdown { position:absolute; top:100%; left:0; right:0; background:#1e1e1e; border:1px solid #444; border-radius:6px; max-height:320px; overflow-y:auto; z-index:300; margin-top:2px; display:none; }
  .er-search-dropdown.visible { display:block; }
  .er-search-item { padding:8px 12px; cursor:pointer; border-bottom:1px solid #2a2a2a; transition:background 0.1s; }
  .er-search-item:hover, .er-search-item.active { background:#2a2a5a; }
  .er-search-item:last-child { border-bottom:none; }
  .er-search-from { font-size:13px; color:#e0e0e0; }
  .er-search-email { font-size:11px; color:#888; margin-left:6px; }
  .er-search-subject { font-size:12px; color:#aaa; margin-top:2px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .er-search-date { font-size:10px; color:#666; float:right; margin-top:2px; }
  .er-search-hint { padding:10px 12px; color:#666; font-size:12px; text-align:center; }
  .er-search-loading { padding:10px 12px; color:#888; font-size:12px; text-align:center; }
  .er-btn-row { display:flex; gap:10px; margin-top:16px; }
  .er-btn { padding:8px 20px; border-radius:6px; border:none; cursor:pointer; font-size:14px; font-family:Inter,sans-serif; }
  .er-btn-primary { background:#4a8aca; color:#fff; }
  .er-btn-primary:hover { background:#5a9ada; }
  .er-btn-secondary { background:#333; color:#ccc; }
  .er-btn-secondary:hover { background:#444; }
  .er-msg-id { font-size:10px; color:#555; margin-top:2px; word-break:break-all; }
  """,
# NEW
"""  /* Email Card in Chat */
  .email-card { background:#1a1a2e; border:1px solid #334; border-radius:10px; margin:8px 0; overflow:hidden; font-family:Inter,sans-serif; }
  .email-card-header { padding:12px 16px 8px; border-bottom:1px solid #2a2a3e; }
  .email-card-label { font-size:10px; color:#6a8aca; text-transform:uppercase; letter-spacing:1px; font-weight:600; margin-bottom:8px; }
  .email-card-row { font-size:12px; color:#bbb; margin:3px 0; line-height:1.5; }
  .email-card-row strong { color:#e0e0e0; font-weight:500; min-width:60px; display:inline-block; }
  .email-card-subject { font-size:14px; color:#e8e8e8; font-weight:600; margin:6px 0 2px; }
  .email-card-date { font-size:11px; color:#666; }
  .email-card-body { padding:12px 16px; max-height:400px; overflow-y:auto; font-size:13px; color:#ccc; line-height:1.6; white-space:pre-wrap; word-wrap:break-word; border-top:1px solid #2a2a3e; }
  .email-card-body::-webkit-scrollbar { width:6px; }
  .email-card-body::-webkit-scrollbar-thumb { background:#444; border-radius:3px; }
  .email-card-msgid { padding:4px 16px 8px; font-size:10px; color:#444; word-break:break-all; }
  .email-card-actions { padding:8px 16px 12px; display:flex; gap:8px; border-top:1px solid #2a2a3e; }
  .email-card-btn { padding:6px 16px; border-radius:6px; border:none; cursor:pointer; font-size:12px; font-family:Inter,sans-serif; transition:background 0.15s; }
  .email-card-btn-reply { background:#4a8aca; color:#fff; }
  .email-card-btn-reply:hover { background:#5a9ada; }
  .email-card-btn-close { background:#333; color:#aaa; }
  .email-card-btn-close:hover { background:#444; color:#fff; }
  .email-search-card { background:#1a1a2e; border:1px solid #334; border-radius:8px; padding:10px 14px; margin:6px 0; cursor:pointer; transition:background 0.15s, border-color 0.15s; }
  .email-search-card:hover { background:#22224a; border-color:#4a8aca; }
  .email-search-card-from { font-size:13px; color:#e0e0e0; }
  .email-search-card-email { font-size:11px; color:#888; margin-left:4px; }
  .email-search-card-subject { font-size:12px; color:#aaa; margin-top:3px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .email-search-card-date { font-size:10px; color:#555; float:right; }
  """)

# ══════════════════════════════════════════════════════════════════════
# 2. Remove old modal HTML
# ══════════════════════════════════════════════════════════════════════
must_replace("HTML: Modal entfernen",
"""<div id="email-reply-modal">
  <div id="email-reply-box">
    <h2>E-Mail Antwort</h2>
    <div class="er-field er-field-row">
      <label>Von / Betreff suchen</label>
      <input type="text" id="er-search-input" placeholder="Name, E-Mail oder Betreff eingeben..." autocomplete="off" />
      <div id="er-search-dropdown" class="er-search-dropdown"></div>
    </div>
    <div class="er-field">
      <label>An (Absender der Original-Mail)</label>
      <input type="text" id="er-to" placeholder="empfaenger@example.com" />
    </div>
    <div class="er-field">
      <label>Betreff</label>
      <input type="text" id="er-subject" placeholder="Re: ..." />
    </div>
    <div class="er-field">
      <label>CC</label>
      <input type="text" id="er-cc" placeholder="Optional" />
    </div>
    <div class="er-field">
      <label>Antwort-Anweisung</label>
      <textarea id="er-body" placeholder="Was soll in der Antwort stehen? (Der Agent schreibt den Text)"></textarea>
    </div>
    <div id="er-msg-id-display" class="er-msg-id"></div>
    <input type="hidden" id="er-message-id" />
    <div class="er-btn-row">
      <button class="er-btn er-btn-primary" onclick="submitEmailReply()">Antwort erstellen</button>
      <button class="er-btn er-btn-secondary" onclick="closeEmailReplyModal()">Abbrechen</button>
    </div>
  </div>
</div>

<div id="search-overlay">""",
# NEW
"""<div id="search-overlay">""")

# ══════════════════════════════════════════════════════════════════════
# 3. Replace entire old Modal JS block + selectSlashCmd intercept
# ══════════════════════════════════════════════════════════════════════
# Find the full block from "// ─── EMAIL REPLY MODAL" to just before "  if (entry && entry.template)"
old_js_block = content[content.index('// \u2500\u2500\u2500 EMAIL REPLY MODAL'):content.index("  if (entry && entry.template) {")]

new_js_block = """// ─── EMAIL CHAT FLOW (replaces old modal) ────────────────────────────────
let _emailContext = null;

function _emailSearchInChat(query) {
  if (!query || query.length < 2) return;
  addStatusMsg('Suche E-Mails: ' + query + '...');
  var agent = getAgentName();
  fetch('/api/email-search?agent=' + encodeURIComponent(agent) + '&q=' + encodeURIComponent(query))
    .then(function(r) { return r.json(); })
    .then(function(results) {
      if (!results || results.length === 0) {
        addStatusMsg('Keine E-Mails gefunden fuer: ' + query);
        return;
      }
      var msgs = document.getElementById('messages');
      var div = document.createElement('div');
      div.className = 'msg assistant';
      var time = new Date().toLocaleTimeString('de-DE', {hour:'2-digit', minute:'2-digit'});
      var html = '<div class="bubble"><div style="margin:4px 0;">';
      html += '<div style="font-size:12px;color:#6a8aca;margin-bottom:8px;font-weight:600;">\\u2709 ' + results.length + ' E-Mail(s) gefunden — klicke zum Oeffnen</div>';
      results.forEach(function(item, idx) {
        html += '<div class="email-search-card" data-eidx="' + idx + '">'
          + '<div><span class="email-search-card-from">' + escHtml(item.from_name || item.from_email) + '</span>'
          + (item.from_name ? '<span class="email-search-card-email">&lt;' + escHtml(item.from_email) + '&gt;</span>' : '')
          + '<span class="email-search-card-date">' + escHtml(item.date) + '</span></div>'
          + '<div class="email-search-card-subject">' + escHtml(item.subject || '(kein Betreff)') + '</div>'
          + '</div>';
      });
      html += '</div></div><div class="meta">' + time + '</div>';
      div.innerHTML = html;
      msgs.appendChild(div);
      scrollDown();
      div.querySelectorAll('.email-search-card').forEach(function(card) {
        card.onclick = function() {
          var idx = parseInt(card.dataset.eidx);
          _openEmailInChat(results[idx]);
        };
      });
    })
    .catch(function(e) { addStatusMsg('E-Mail-Suche fehlgeschlagen: ' + e.message); });
}

function _openEmailInChat(emailMeta) {
  addStatusMsg('Lade E-Mail...');
  var agent = getAgentName();
  fetch('/api/email-content?agent=' + encodeURIComponent(agent) + '&message_id=' + encodeURIComponent(emailMeta.message_id || '') + '&from_email=' + encodeURIComponent(emailMeta.from_email || '') + '&subject=' + encodeURIComponent(emailMeta.subject || ''))
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (!data.ok) { addStatusMsg('E-Mail konnte nicht geladen werden: ' + (data.error || 'unbekannt')); return; }
      _showEmailCard(data);
    })
    .catch(function(e) { addStatusMsg('Fehler: ' + e.message); });
}

function _showEmailCard(email) {
  var msgs = document.getElementById('messages');
  var div = document.createElement('div');
  div.className = 'msg assistant';
  var time = new Date().toLocaleTimeString('de-DE', {hour:'2-digit', minute:'2-digit'});
  var fromDisplay = email.from_name ? escHtml(email.from_name) + ' &lt;' + escHtml(email.from_email) + '&gt;' : escHtml(email.from_email);
  var bodyText = email.body || '(kein Inhalt)';
  var ccDisplay = email.cc ? escHtml(email.cc) : '';

  var cardId = 'ec-' + Date.now();
  var html = '<div class="bubble"><div class="email-card">'
    + '<div class="email-card-header">'
    + '<div class="email-card-label">\\u2709 E-Mail</div>'
    + '<div class="email-card-subject">' + escHtml(email.subject || '(kein Betreff)') + '</div>'
    + '<div class="email-card-row"><strong>Von:</strong> ' + fromDisplay + '</div>'
    + '<div class="email-card-row"><strong>An:</strong> ' + escHtml(email.to || '') + '</div>'
    + (ccDisplay ? '<div class="email-card-row"><strong>CC:</strong> ' + ccDisplay + '</div>' : '')
    + '<div class="email-card-date">' + escHtml(email.date || '') + '</div>'
    + '</div>'
    + '<div class="email-card-body">' + escHtml(bodyText) + '</div>'
    + (email.message_id ? '<div class="email-card-msgid">Message-ID: ' + escHtml(email.message_id) + '</div>' : '')
    + '<div class="email-card-actions">'
    + '<button class="email-card-btn email-card-btn-reply" data-card="' + cardId + '">Antworten</button>'
    + '<button class="email-card-btn email-card-btn-close" data-card="' + cardId + '">Schliessen</button>'
    + '</div>'
    + '</div></div><div class="meta">' + time + '</div>';
  div.innerHTML = html;
  div.id = cardId;
  msgs.appendChild(div);
  scrollDown();

  div.querySelector('.email-card-btn-reply').onclick = function() {
    var ownAddrs = ['moritz.cremer@me.com', 'londoncityfox@gmail.com', 'moritz.cremer@signicat.com'];
    var ccParts = [];
    [email.to || '', email.cc || ''].forEach(function(field) {
      if (!field) return;
      field.split(',').forEach(function(addr) {
        addr = addr.trim();
        var em = addr.includes('<') ? addr.substring(addr.indexOf('<')+1, addr.indexOf('>')) : addr;
        if (em && !ownAddrs.includes(em.toLowerCase().trim())) ccParts.push(addr);
      });
    });
    _emailContext = {
      from_email: email.from_email || '',
      from_name: email.from_name || '',
      subject: email.subject || '',
      message_id: email.message_id || '',
      cc: ccParts.join(', ')
    };
    addStatusMsg('E-Mail-Kontext gesetzt. Schreibe jetzt deine Antwort-Anweisung.');
    document.getElementById('msg-input').focus();
    this.textContent = '\\u2713 Kontext gesetzt';
    this.style.background = '#2a5a2a';
    this.onclick = null;
  };
  div.querySelector('.email-card-btn-close').onclick = function() { div.remove(); };
}

function _getAndClearEmailContext() {
  if (!_emailContext) return null;
  var ctx = _emailContext;
  _emailContext = null;
  return ctx;
}

function selectSlashCmd(inputEl, cmd) {
  var entry = _SLASH_COMMANDS.find(c => c.cmd === cmd);
  if (cmd === '/create-email-reply') {
    inputEl.value = '/reply ';
    hideSlashAutocomplete();
    inputEl.focus();
    return;
  }
"""

content = content.replace(old_js_block, new_js_block)
print("OK: JS: Modal -> Chat-native Email Flow")

# ══════════════════════════════════════════════════════════════════════
# 4. Intercept /reply in sendMessage (before doSendChat)
# ══════════════════════════════════════════════════════════════════════
must_replace("sendMessage: /reply Intercept",
"""  addMessage('user', text);
  scrollDown();
  doSendChat(text);
}""",
"""  addMessage('user', text);
  scrollDown();
  // EMAIL_CHAT_FLOW: /reply triggers email search in chat
  if (text.startsWith('/reply ')) {
    var emailQuery = text.substring(7).trim();
    if (emailQuery.length >= 2) { _emailSearchInChat(emailQuery); return; }
  }
  doSendChat(text);
}""")

# ══════════════════════════════════════════════════════════════════════
# 5. Inject email context into doSendChat
# ══════════════════════════════════════════════════════════════════════
must_replace("doSendChat: Email-Kontext",
"""async function doSendChat(text) {
  startTyping(text.substring(0,50));""",
"""async function doSendChat(text) {
  // Inject email context if set (one-time use)
  var ectx = _getAndClearEmailContext();
  if (ectx) {
    var ctxBlock = '[E-MAIL KONTEXT: Von: ' + ectx.from_email + (ectx.from_name ? ' (' + ectx.from_name + ')' : '') + ', Betreff: ' + ectx.subject + ', Message-ID: ' + ectx.message_id + (ectx.cc ? ', CC: ' + ectx.cc : '') + ']\\n\\nUser-Anweisung: ';
    text = ctxBlock + text;
  }
  startTyping(text.substring(0,50));""")

# ══════════════════════════════════════════════════════════════════════
# 6. Add /reply slash command
# ══════════════════════════════════════════════════════════════════════
must_replace("Slash: /reply hinzufuegen",
"  {cmd: '/create-email-reply', label: '/create-email-reply', desc: 'E-Mail Antwort erstellen', template: 'Antworte auf die E-Mail von [Absender] zum Thema [Betreff]: ', group: 'Kommunikation'},",
"""  {cmd: '/create-email-reply', label: '/create-email-reply', desc: 'E-Mail Antwort erstellen', template: 'Antworte auf die E-Mail von [Absender] zum Thema [Betreff]: ', group: 'Kommunikation'},
  {cmd: '/reply', label: '/reply [suche]', desc: 'E-Mail suchen und im Chat oeffnen', template: '/reply ', group: 'Kommunikation'},""")

# ══════════════════════════════════════════════════════════════════════
# 7. Backend route /api/email-content
# ══════════════════════════════════════════════════════════════════════
email_content_route_code = '''

@app.route('/api/email-content')
def email_content_route():
    """Load full email content for display in chat."""
    import email as _email_mod'''

must_replace("Backend: /api/email-content",
"""    # Sort by date_ts descending
    results.sort(key=lambda r: r.get('date_ts', 0), reverse=True)
    return jsonify(results[:8])""",
"""    # Sort by date_ts descending
    results.sort(key=lambda r: r.get('date_ts', 0), reverse=True)
    return jsonify(results[:8])""" + email_content_route_code + """
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
                        body = body[:5000] + '\n\n[... gekuerzt, ' + str(len(body)) + ' Zeichen gesamt]'

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

    return jsonify({'ok': False, 'error': 'E-Mail nicht gefunden'})""")

# Write once
with open(path, 'w') as f:
    f.write(content)

print("\nAlle Patches erfolgreich angewendet!")
