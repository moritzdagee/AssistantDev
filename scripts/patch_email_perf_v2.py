#!/usr/bin/env python3
"""Patch v2: E-Mail Search Performance + Apple Mail Async."""
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
# FIX 1: Replace email_search_route with cached version
# ═══════════════════════════════════════════════════════════════
# Find the route by its unique markers
route_start = content.index("@app.route('/api/email-search')\ndef email_search_route():")
route_end = content.index("    return jsonify(results[:8])", route_start) + len("    return jsonify(results[:8])")
old_route = content[route_start:route_end]

new_route = """# ─── EMAIL HEADER CACHE (in-memory) ────────────────────────────────────────
_email_header_cache = {}  # key: dir_path -> list of parsed headers
_email_cache_mtime = {}   # key: dir_path -> last build time
_EMAIL_CACHE_TTL = 300    # rebuild cache every 5 minutes

def _build_email_cache(sdir):
    import email as _eml
    from email.header import decode_header as _dh
    from email.utils import parsedate_to_datetime as _pdt

    def _dec(val):
        if not val:
            return ''
        try:
            parts = _dh(val)
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
                with open(fname.path, 'r', errors='replace') as f:
                    header_lines = []
                    for i, line in enumerate(f):
                        if i >= 40:
                            break
                        header_lines.append(line)
                msg = _eml.message_from_string(''.join(header_lines))
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
                    dt = _pdt(date_str)
                    date_display = dt.strftime('%d.%m.%Y %H:%M')
                    date_ts = dt.timestamp()
                except Exception:
                    date_display = date_str[:20] if date_str else ''
                    try:
                        date_ts = fname.stat().st_mtime
                    except Exception:
                        pass
                entries.append({
                    'message_id': message_id,
                    'from_name': from_name, 'from_email': from_email,
                    'subject': subject, 'date': date_display, 'date_ts': date_ts,
                    'to': to_raw, 'cc': cc_raw,
                    '_s_from': (from_name.replace(',', ' ') + ' ' + from_email).lower(),
                    '_s_subj': subject.lower(),
                    '_s_to': (to_raw + ' ' + cc_raw).lower(),
                })
            except Exception:
                continue
    except Exception:
        pass
    entries.sort(key=lambda e: e.get('date_ts', 0), reverse=True)
    return entries


def _get_email_cache(sdir):
    import time
    now = time.time()
    if sdir in _email_header_cache and (now - _email_cache_mtime.get(sdir, 0)) < _EMAIL_CACHE_TTL:
        return _email_header_cache[sdir]
    entries = _build_email_cache(sdir)
    _email_header_cache[sdir] = entries
    _email_cache_mtime[sdir] = now
    print(f"[EMAIL_CACHE] Built cache for {sdir}: {len(entries)} entries", flush=True)
    return entries


@app.route('/api/email-search')
def email_search_route():
    agent = request.args.get('agent', 'standard')
    q = request.args.get('q', '').strip().lower()
    from_filter = request.args.get('from', '').strip().lower()
    subj_filter = request.args.get('subject', '').strip().lower()
    to_filter = request.args.get('to', '').strip().lower()
    body_filter = request.args.get('body', '').strip().lower()
    has_field_filter = bool(from_filter or subj_filter or to_filter or body_filter)
    if len(q) < 2 and not has_field_filter:
        return jsonify([])

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
    # Re-sort merged list
    all_entries.sort(key=lambda e: e.get('date_ts', 0), reverse=True)

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
            if q not in (entry['_s_from'] + ' ' + entry['_s_subj']):
                match = False
        if match:
            if mid:
                seen_ids.add(mid)
            results.append({
                'message_id': entry['message_id'],
                'from_name': entry['from_name'], 'from_email': entry['from_email'],
                'subject': entry['subject'], 'date': entry['date'],
                'date_ts': entry['date_ts'], 'to': entry['to'], 'cc': entry['cc'],
            })
    return jsonify(results[:8])"""

content = content.replace(old_route, new_route, 1)
print("OK: Fix 1 - Email Search mit In-Memory Cache")

# ═══════════════════════════════════════════════════════════════
# FIX 2a: send_email_draft Block 1 (line ~305)
# ═══════════════════════════════════════════════════════════════
must_replace("Fix 2a: draft Block 1",
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
# FIX 2b: send_email_draft Block 2 (line ~1023)
# ═══════════════════════════════════════════════════════════════
must_replace("Fix 2b: draft Block 2",
"    result = subprocess.run(['osascript', '-e', script],\n"
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
# FIX 2c: send_email_reply (line ~1098)
# ═══════════════════════════════════════════════════════════════
must_replace("Fix 2c: reply async",
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
# FIX 2d: Frontend debounce 250ms
# ═══════════════════════════════════════════════════════════════
must_replace("Fix 2d: debounce 250ms",
"        _esmDebounce = setTimeout(_esmDoSearch, 300);",
"        _esmDebounce = setTimeout(_esmDoSearch, 250);")

# Write
with open(path, 'w') as f:
    f.write(content)

print("\nAlle Patches erfolgreich angewendet!")
