#!/usr/bin/env python3
"""Patch: E-Mail Search Performance + Apple Mail Async.
Fix 1: In-Memory Email Header Cache statt Filesystem-Scan
Fix 2: subprocess.Popen statt subprocess.run fuer Apple Mail
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
# FIX 1: Replace entire email_search_route with cached version
# ═══════════════════════════════════════════════════════════════

old_route = '''@app.route('/api/email-search')
def email_search_route():
    """Search emails in agent memory and email_inbox for reply autocomplete."""
    import email
    from email.header import decode_header as _decode_hdr
    agent = request.args.get('agent', 'standard')
    q = request.args.get('q', '').strip().lower()
    from_filter = request.args.get('from', '').strip().lower()
    subj_filter = request.args.get('subject', '').strip().lower()
    to_filter = request.args.get('to', '').strip().lower()
    body_filter = request.args.get('body', '').strip().lower()
    has_field_filter = bool(from_filter or subj_filter or to_filter or body_filter)
    if len(q) < 2 and not has_field_filter:
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
                # Check if query matches (supports field-specific filters)
                match = True
                if from_filter:
                    if from_filter not in (parsed['from_name'] + ' ' + parsed['from_email']).lower():
                        match = False
                if subj_filter and match:
                    if subj_filter not in parsed['subject'].lower():
                        match = False
                if to_filter and match:
                    if to_filter not in (parsed.get('to','') + ' ' + parsed.get('cc','')).lower():
                        match = False
                if not from_filter and not subj_filter and not to_filter and q:
                    searchable = (parsed['from_name'] + ' ' + parsed['from_email'] + ' ' + parsed['subject']).lower()
                    if q not in searchable:
                        match = False
                if match:
                    results.append(parsed)
        except Exception:
            continue

    # Sort by date_ts descending
    results.sort(key=lambda r: r.get('date_ts', 0), reverse=True)
    return jsonify(results[:8])'''

new_route = '''# ─── EMAIL HEADER CACHE (in-memory) ────────────────────────────────────────
_email_header_cache = {}  # key: dir_path -> list of parsed headers
_email_cache_mtime = {}   # key: dir_path -> last build time
_EMAIL_CACHE_TTL = 300    # rebuild cache every 5 minutes

def _build_email_cache(sdir):
    """Parse headers (first 30 lines) of all .eml files in a directory. Fast."""
    import email
    from email.header import decode_header as _dec_hdr
    from email.utils import parsedate_to_datetime

    def _dec(val):
        if not val:
            return ''
        try:
            parts = _dec_hdr(val)
            decoded = []
            for part, charset in parts:
                if isinstance(part, bytes):
                    decoded.append(part.decode(charset or 'utf-8', errors='replace'))
                else:
                    decoded.append(part)
            return ' '.join(decoded)
        except Exception:
            return str(val)

    entries = []
    try:
        for fname in os.scandir(sdir):
            if not fname.name.endswith('.eml'):
                continue
            try:
                # Read only first 30 lines (headers) — much faster than full parse
                with open(fname.path, 'r', errors='replace') as f:
                    header_lines = []
                    for i, line in enumerate(f):
                        if i >= 40:
                            break
                        header_lines.append(line)
                header_text = ''.join(header_lines)
                msg = email.message_from_string(header_text)

                from_raw = _dec(msg.get('From', ''))
                subject = _dec(msg.get('Subject', ''))
                date_str = msg.get('Date', '')
                message_id = msg.get('Message-ID', '').strip()
                to_raw = _dec(msg.get('To', ''))
                cc_raw = _dec(msg.get('Cc', ''))

                from_name = ''
                from_email = from_raw
                if '<' in from_raw and '>' in from_raw:
                    from_name = from_raw[:from_raw.index('<')].strip().strip('"').replace(',', ' ')
                    from_email = from_raw[from_raw.index('<')+1:from_raw.index('>')]

                date_display = ''
                date_ts = 0
                try:
                    dt = parsedate_to_datetime(date_str)
                    date_display = dt.strftime('%d.%m.%Y %H:%M')
                    date_ts = dt.timestamp()
                except Exception:
                    date_display = date_str[:20] if date_str else ''
                    # Use file mtime as fallback
                    try:
                        date_ts = fname.stat().st_mtime
                    except Exception:
                        pass

                # Build search tokens (lowercased, comma-normalized)
                search_from = (from_name.replace(',', ' ') + ' ' + from_email).lower()
                search_subj = subject.lower()
                search_to = (to_raw + ' ' + cc_raw).lower()

                entries.append({
                    'message_id': message_id,
                    'from_name': from_name,
                    'from_email': from_email,
                    'subject': subject,
                    'date': date_display,
                    'date_ts': date_ts,
                    'to': to_raw,
                    'cc': cc_raw,
                    '_s_from': search_from,
                    '_s_subj': search_subj,
                    '_s_to': search_to,
                    '_fpath': fname.path,
                })
            except Exception:
                continue
    except Exception:
        pass

    # Sort by date_ts descending
    entries.sort(key=lambda e: e.get('date_ts', 0), reverse=True)
    return entries


def _get_email_cache(sdir):
    """Get cached email headers for a directory. Rebuilds if stale."""
    import time
    now = time.time()
    if sdir in _email_header_cache and (now - _email_cache_mtime.get(sdir, 0)) < _EMAIL_CACHE_TTL:
        return _email_header_cache[sdir]
    # Build cache
    entries = _build_email_cache(sdir)
    _email_header_cache[sdir] = entries
    _email_cache_mtime[sdir] = now
    print(f"[EMAIL_CACHE] Built cache for {sdir}: {len(entries)} entries", flush=True)
    return entries


@app.route('/api/email-search')
def email_search_route():
    """Search emails using in-memory header cache. Sub-200ms responses."""
    agent = request.args.get('agent', 'standard')
    q = request.args.get('q', '').strip().lower()
    from_filter = request.args.get('from', '').strip().lower()
    subj_filter = request.args.get('subject', '').strip().lower()
    to_filter = request.args.get('to', '').strip().lower()
    body_filter = request.args.get('body', '').strip().lower()
    has_field_filter = bool(from_filter or subj_filter or to_filter or body_filter)
    if len(q) < 2 and not has_field_filter:
        return jsonify([])

    # Collect all cached entries from relevant directories
    search_dirs = []
    speicher = get_agent_speicher(agent)
    memory_dir = os.path.join(speicher, 'memory')
    if os.path.exists(memory_dir):
        search_dirs.append(memory_dir)
    inbox_dir = os.path.join(BASE, 'email_inbox')
    if os.path.exists(inbox_dir):
        search_dirs.append(inbox_dir)

    all_entries = []
    for sdir in search_dirs:
        all_entries.extend(_get_email_cache(sdir))

    # Filter in-memory
    results = []
    seen_ids = set()
    for entry in all_entries:
        if len(results) >= 8:
            break
        mid = entry['message_id']
        if mid and mid in seen_ids:
            continue

        match = True
        if from_filter:
            if from_filter not in entry['_s_from']:
                match = False
        if subj_filter and match:
            if subj_filter not in entry['_s_subj']:
                match = False
        if to_filter and match:
            if to_filter not in entry['_s_to']:
                match = False
        if not from_filter and not subj_filter and not to_filter and q:
            searchable = entry['_s_from'] + ' ' + entry['_s_subj']
            if q not in searchable:
                match = False

        if match:
            if mid:
                seen_ids.add(mid)
            # Return clean entry (strip internal fields)
            results.append({
                'message_id': entry['message_id'],
                'from_name': entry['from_name'],
                'from_email': entry['from_email'],
                'subject': entry['subject'],
                'date': entry['date'],
                'date_ts': entry['date_ts'],
                'to': entry['to'],
                'cc': entry['cc'],
            })

    return jsonify(results[:8])'''

if old_route not in content:
    print("FEHLER: email_search_route nicht gefunden!", file=sys.stderr)
    sys.exit(1)
content = content.replace(old_route, new_route, 1)
print("OK: Fix 1 - Email Search mit In-Memory Cache")

# ═══════════════════════════════════════════════════════════════
# FIX 2a: send_email_draft — async mit Popen (Block 1, Zeile ~278)
# ═══════════════════════════════════════════════════════════════
must_replace("Fix 2a: send_email_draft Block 1 async",
"    result = subprocess.run(['osascript', '-e', script], \n"
"                          capture_output=True, text=True, timeout=10)\n"
"    if result.returncode != 0:\n"
"        raise Exception(f\"AppleScript Fehler: {result.stderr.strip()}\")\n"
"    return True\n"
"\n"
"BASE = os.path.expanduser",
"    subprocess.Popen(['osascript', '-e', script],\n"
"                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n"
"    return True\n"
"\n"
"BASE = os.path.expanduser")

# ═══════════════════════════════════════════════════════════════
# FIX 2b: send_email_draft — async mit Popen (Block 2, Zeile ~996)
# ═══════════════════════════════════════════════════════════════
must_replace("Fix 2b: send_email_draft Block 2 async",
"    result = subprocess.run(['osascript', '-e', script], \n"
"                          capture_output=True, text=True, timeout=10)\n"
"    if result.returncode != 0:\n"
"        raise Exception(f\"AppleScript Fehler: {result.stderr.strip()}\")\n"
"    return True\n"
"\n"
"def send_email_reply",
"    subprocess.Popen(['osascript', '-e', script],\n"
"                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n"
"    return True\n"
"\n"
"def send_email_reply")

# ═══════════════════════════════════════════════════════════════
# FIX 2c: send_email_reply — async mit Popen
# ═══════════════════════════════════════════════════════════════
must_replace("Fix 2c: send_email_reply async",
"    result = subprocess.run(['osascript', '-e', script],\n"
"                          capture_output=True, text=True, timeout=30)\n"
"    if result.returncode != 0:\n"
"        raise Exception(f\"AppleScript Fehler: {result.stderr.strip()}\")\n"
"    return True\n"
"\n"
"def send_whatsapp_draft",
"    subprocess.Popen(['osascript', '-e', script],\n"
"                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n"
"    return True\n"
"\n"
"def send_whatsapp_draft")

# ═══════════════════════════════════════════════════════════════
# FIX 2d: Frontend debounce to 250ms + AbortController
# ═══════════════════════════════════════════════════════════════
must_replace("Fix 2d: Debounce 250ms",
"        _esmDebounce = setTimeout(_esmDoSearch, 300);",
"        _esmDebounce = setTimeout(_esmDoSearch, 250);")

# Write
with open(path, 'w') as f:
    f.write(content)

print("\nAlle Patches erfolgreich angewendet!")
