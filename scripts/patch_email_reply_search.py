#!/usr/bin/env python3
"""Patch: Email Reply Modal mit Live-Suche."""

import sys

path = '/Users/moritzcremer/AssistantDev/src/web_server.py'
with open(path, 'r') as f:
    content = f.read()

# ── PATCH 1: Backend Route /api/email-search ──
# Insert after /send_email_reply route

route_anchor = """@app.route('/send_email_reply', methods=['POST'])
def send_email_reply_route():
    try:
        spec = request.json
        send_email_reply(spec)
        return jsonify({'ok': True, 'subject': spec.get('subject',''), 'to': spec.get('to','')})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})"""

email_search_route = """@app.route('/send_email_reply', methods=['POST'])
def send_email_reply_route():
    try:
        spec = request.json
        send_email_reply(spec)
        return jsonify({'ok': True, 'subject': spec.get('subject',''), 'to': spec.get('to','')})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


@app.route('/api/email-search')
def email_search_route():
    \"\"\"Search emails in agent memory and email_inbox for reply autocomplete.\"\"\"
    import email
    from email.header import decode_header as _decode_hdr
    agent = request.args.get('agent', 'standard')
    q = request.args.get('q', '').strip().lower()
    if len(q) < 2:
        return jsonify([])

    def _dec(val):
        if not val:
            return ''
        parts = _decode_hdr(val)
        decoded = []
        for part, charset in parts:
            if isinstance(part, bytes):
                decoded.append(part.decode(charset or 'utf-8', errors='replace'))
            else:
                decoded.append(part)
        return ' '.join(decoded)

    def _parse_eml(fpath):
        try:
            with open(fpath, 'r', errors='replace') as f:
                msg = email.message_from_file(f)
            from_raw = _dec(msg.get('From', ''))
            subject = _dec(msg.get('Subject', ''))
            date_str = msg.get('Date', '')
            message_id = msg.get('Message-ID', '').strip()
            to_raw = _dec(msg.get('To', ''))
            cc_raw = _dec(msg.get('Cc', ''))
            # Parse From into name + email
            from_name = ''
            from_email = from_raw
            if '<' in from_raw and '>' in from_raw:
                from_name = from_raw[:from_raw.index('<')].strip().strip('"')
                from_email = from_raw[from_raw.index('<')+1:from_raw.index('>')]
            # Parse date for sorting
            date_display = ''
            date_ts = 0
            try:
                from email.utils import parsedate_to_datetime
                dt = parsedate_to_datetime(date_str)
                date_display = dt.strftime('%d.%m.%Y %H:%M')
                date_ts = dt.timestamp()
            except Exception:
                date_display = date_str[:20] if date_str else ''
            return {
                'message_id': message_id,
                'from_name': from_name,
                'from_email': from_email,
                'subject': subject,
                'date': date_display,
                'date_ts': date_ts,
                'to': to_raw,
                'cc': cc_raw,
            }
        except Exception:
            return None

    results = []
    seen_ids = set()

    # Search directories: agent memory + email_inbox
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
            files = [f for f in os.listdir(sdir) if f.endswith('.eml')]
            # Sort by mtime descending (newest first)
            files.sort(key=lambda f: os.path.getmtime(os.path.join(sdir, f)), reverse=True)
            for fname in files:
                if len(results) >= 8:
                    break
                fpath = os.path.join(sdir, fname)
                parsed = _parse_eml(fpath)
                if not parsed:
                    continue
                # Deduplicate by message_id
                mid = parsed['message_id']
                if mid and mid in seen_ids:
                    continue
                if mid:
                    seen_ids.add(mid)
                # Check if query matches
                searchable = (parsed['from_name'] + ' ' + parsed['from_email'] + ' ' + parsed['subject']).lower()
                if q in searchable:
                    results.append(parsed)
        except Exception:
            continue

    # Sort by date_ts descending
    results.sort(key=lambda r: r.get('date_ts', 0), reverse=True)
    return jsonify(results[:8])"""

if route_anchor not in content:
    print("FEHLER: send_email_reply Route nicht gefunden!", file=sys.stderr)
    sys.exit(1)

content = content.replace(route_anchor, email_search_route)
print("Patch 1: /api/email-search Route eingefuegt")

# ── PATCH 2: CSS fuer Email Reply Modal ──
css_anchor = '  .code-copy-btn { position:absolute;'
css_new = """  /* Email Reply Modal */
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
  """ + css_anchor

if css_anchor not in content:
    print("FEHLER: CSS Anker nicht gefunden!", file=sys.stderr)
    sys.exit(1)

content = content.replace(css_anchor, css_new)
print("Patch 2: CSS fuer Email Reply Modal eingefuegt")

# ── PATCH 3: HTML fuer Email Reply Modal (nach agent-modal div) ──
html_anchor = '<div id="search-overlay">'
html_new = """<div id="email-reply-modal">
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

<div id="search-overlay">"""

if html_anchor not in content:
    print("FEHLER: HTML Anker nicht gefunden!", file=sys.stderr)
    sys.exit(1)

content = content.replace(html_anchor, html_new)
print("Patch 3: HTML fuer Email Reply Modal eingefuegt")

# ── PATCH 4: JavaScript fuer Email Reply Modal ──
js_anchor = "function selectSlashCmd(inputEl, cmd) {"
js_new = """// ─── EMAIL REPLY MODAL ─────────────────────────────────────────────────────
let _erDebounce = null;
let _erDropdownIdx = -1;
let _erResults = [];

function showEmailReplyModal() {
  document.getElementById('er-search-input').value = '';
  document.getElementById('er-to').value = '';
  document.getElementById('er-subject').value = '';
  document.getElementById('er-cc').value = '';
  document.getElementById('er-body').value = '';
  document.getElementById('er-message-id').value = '';
  document.getElementById('er-msg-id-display').textContent = '';
  document.getElementById('er-search-dropdown').classList.remove('visible');
  _erResults = [];
  _erDropdownIdx = -1;
  const m = document.getElementById('email-reply-modal');
  m.classList.add('show');
  m.style.display = 'flex';
  setTimeout(() => document.getElementById('er-search-input').focus(), 100);
}

function closeEmailReplyModal() {
  const m = document.getElementById('email-reply-modal');
  m.classList.remove('show');
  m.style.display = 'none';
}

function _erSearch(query) {
  const dd = document.getElementById('er-search-dropdown');
  if (query.length < 2) { dd.classList.remove('visible'); return; }
  dd.innerHTML = '<div class="er-search-loading">Suche...</div>';
  dd.classList.add('visible');
  const agent = document.getElementById('agent-label').textContent.trim();
  fetch('/api/email-search?agent=' + encodeURIComponent(agent) + '&q=' + encodeURIComponent(query))
    .then(r => r.json())
    .then(results => {
      _erResults = results;
      _erDropdownIdx = -1;
      if (results.length === 0) {
        dd.innerHTML = '<div class="er-search-hint">Keine E-Mails gefunden</div>';
        return;
      }
      dd.innerHTML = '';
      results.forEach((item, idx) => {
        const div = document.createElement('div');
        div.className = 'er-search-item';
        div.dataset.idx = idx;
        div.innerHTML = '<div><span class="er-search-from">' + escHtml(item.from_name || item.from_email) + '</span>'
          + (item.from_name ? '<span class="er-search-email">&lt;' + escHtml(item.from_email) + '&gt;</span>' : '')
          + '<span class="er-search-date">' + escHtml(item.date) + '</span></div>'
          + '<div class="er-search-subject">' + escHtml(item.subject) + '</div>';
        div.onmousedown = function(e) { e.preventDefault(); _erSelectItem(idx); };
        dd.appendChild(div);
      });
    })
    .catch(() => { dd.innerHTML = '<div class="er-search-hint">Fehler bei der Suche</div>'; });
}

function _erSelectItem(idx) {
  const item = _erResults[idx];
  if (!item) return;
  document.getElementById('er-to').value = item.from_email;
  const subj = item.subject || '';
  document.getElementById('er-subject').value = subj.startsWith('Re:') ? subj : 'Re: ' + subj;
  // CC: all To/Cc except own addresses
  const ownAddrs = ['moritz.cremer@me.com', 'londoncityfox@gmail.com', 'moritz.cremer@signicat.com'];
  let ccParts = [];
  [item.to, item.cc].forEach(field => {
    if (!field) return;
    field.split(',').forEach(addr => {
      addr = addr.trim();
      const email = addr.includes('<') ? addr.substring(addr.indexOf('<')+1, addr.indexOf('>')) : addr;
      if (email && !ownAddrs.includes(email.toLowerCase().trim())) {
        ccParts.push(addr);
      }
    });
  });
  document.getElementById('er-cc').value = ccParts.join(', ');
  document.getElementById('er-message-id').value = item.message_id || '';
  document.getElementById('er-msg-id-display').textContent = item.message_id ? 'Message-ID: ' + item.message_id : '';
  document.getElementById('er-search-dropdown').classList.remove('visible');
  document.getElementById('er-body').focus();
}

document.addEventListener('DOMContentLoaded', function() {
  const searchInput = document.getElementById('er-search-input');
  if (searchInput) {
    searchInput.addEventListener('input', function() {
      clearTimeout(_erDebounce);
      _erDebounce = setTimeout(() => _erSearch(this.value.trim()), 300);
    });
    searchInput.addEventListener('keydown', function(e) {
      const dd = document.getElementById('er-search-dropdown');
      if (!dd.classList.contains('visible') || _erResults.length === 0) return;
      const items = dd.querySelectorAll('.er-search-item');
      if (e.key === 'ArrowDown') { e.preventDefault(); _erDropdownIdx = Math.min(_erDropdownIdx+1, items.length-1); items.forEach((it,i) => it.classList.toggle('active', i===_erDropdownIdx)); }
      if (e.key === 'ArrowUp') { e.preventDefault(); _erDropdownIdx = Math.max(_erDropdownIdx-1, 0); items.forEach((it,i) => it.classList.toggle('active', i===_erDropdownIdx)); }
      if (e.key === 'Enter' && _erDropdownIdx >= 0) { e.preventDefault(); _erSelectItem(_erDropdownIdx); }
      if (e.key === 'Escape') { dd.classList.remove('visible'); }
    });
  }
  // Close dropdown on outside click
  document.addEventListener('click', function(e) {
    const dd = document.getElementById('er-search-dropdown');
    if (dd && !dd.contains(e.target) && e.target.id !== 'er-search-input') {
      dd.classList.remove('visible');
    }
  });
  // Close modal on backdrop click
  const modal = document.getElementById('email-reply-modal');
  if (modal) {
    modal.addEventListener('click', function(e) { if (e.target === modal) closeEmailReplyModal(); });
  }
});

function submitEmailReply() {
  const to = document.getElementById('er-to').value.trim();
  const subject = document.getElementById('er-subject').value.trim();
  const body = document.getElementById('er-body').value.trim();
  const cc = document.getElementById('er-cc').value.trim();
  const messageId = document.getElementById('er-message-id').value.trim();
  if (!to) { document.getElementById('er-to').focus(); return; }
  if (!body) { document.getElementById('er-body').focus(); return; }
  // Build prompt for agent
  let prompt = 'Antworte auf die E-Mail';
  if (subject) prompt += ' zum Betreff "' + subject + '"';
  prompt += ' von ' + to;
  if (messageId) prompt += ' (Message-ID: ' + messageId + ')';
  if (cc) prompt += ', CC: ' + cc;
  prompt += '.\\n\\nInhalt der Antwort:\\n' + body;
  closeEmailReplyModal();
  const input = document.getElementById('input');
  input.value = prompt;
  input.focus();
  // Auto-submit
  sendMessage();
}

function selectSlashCmd(inputEl, cmd) {"""

if js_anchor not in content:
    print("FEHLER: selectSlashCmd nicht gefunden!", file=sys.stderr)
    sys.exit(1)

content = content.replace(js_anchor, js_new)
print("Patch 4: JavaScript fuer Email Reply Modal eingefuegt")

# ── PATCH 5: Intercept /create-email-reply to open modal instead of template ──
old_select = """  if (entry && entry.template) {
    inputEl.value = entry.template;
    hideSlashAutocomplete();
    inputEl.focus();
    onInputHandler(inputEl);
  } else {"""

new_select = """  if (cmd === '/create-email-reply') {
    inputEl.value = '';
    hideSlashAutocomplete();
    showEmailReplyModal();
    return;
  }
  if (entry && entry.template) {
    inputEl.value = entry.template;
    hideSlashAutocomplete();
    inputEl.focus();
    onInputHandler(inputEl);
  } else {"""

if old_select not in content:
    print("FEHLER: selectSlashCmd body nicht gefunden!", file=sys.stderr)
    sys.exit(1)

content = content.replace(old_select, new_select)
print("Patch 5: /create-email-reply oeffnet jetzt Modal statt Template")

with open(path, 'w') as f:
    f.write(content)

print("\nAlle Patches erfolgreich angewendet!")
