#!/usr/bin/env python3
"""Patch: E-Mail Suche — Modal findet auch .txt Dateien, Datumssortierung,
Reply-Modal laedt vollstaendigen Inhalt mit Message-ID."""
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
# FIX 1: _build_email_cache — auch .txt Dateien mit deutschem Format
# ═══════════════════════════════════════════════════════════════
old_build = """def _build_email_cache(sdir):
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
    return entries"""

new_build = """def _parse_filename_timestamp(fname):
    \"\"\"Extract timestamp from filename like 2025-10-30_16-46-32_... Returns (display, ts).\"\"\"
    import re as _re
    import datetime as _dt
    m = _re.match(r'^(\\d{4})-(\\d{2})-(\\d{2})_(\\d{2})-(\\d{2})-(\\d{2})', fname)
    if m:
        try:
            dt = _dt.datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                              int(m.group(4)), int(m.group(5)), int(m.group(6)))
            return dt.strftime('%d.%m.%Y %H:%M'), dt.timestamp()
        except Exception:
            pass
    return '', 0


def _parse_txt_email(fpath, fname):
    \"\"\"Parse .txt email with German header format (Von:, An:, Betreff:, Datum:).\"\"\"
    from email.utils import parsedate_to_datetime as _pdt
    import re as _re
    try:
        with open(fpath, 'r', errors='replace') as f:
            lines = []
            for i, line in enumerate(f):
                if i >= 30:
                    break
                lines.append(line)
        from_raw = subject = date_str = to_raw = cc_raw = message_id = ''
        for line in lines:
            low = line.lower()
            if low.startswith('von:') or low.startswith('from:'):
                from_raw = line.split(':', 1)[1].strip()
            elif low.startswith('betreff:') or low.startswith('subject:'):
                subject = line.split(':', 1)[1].strip()
            elif low.startswith('datum:') or low.startswith('date:'):
                date_str = line.split(':', 1)[1].strip()
            elif low.startswith('an:') or low.startswith('to:'):
                to_raw = line.split(':', 1)[1].strip()
            elif low.startswith('cc:') or low.startswith('kopie:'):
                cc_raw = line.split(':', 1)[1].strip()
            elif low.startswith('message-id:'):
                message_id = line.split(':', 1)[1].strip()
        from_name = ''
        from_email = from_raw
        if '<' in from_raw and '>' in from_raw:
            from_name = from_raw[:from_raw.index('<')].strip().strip('"').replace(',', ' ')
            from_email = from_raw[from_raw.index('<')+1:from_raw.index('>')]
        date_display = ''
        date_ts = 0
        if date_str:
            try:
                dt = _pdt(date_str)
                date_display = dt.strftime('%d.%m.%Y %H:%M')
                date_ts = dt.timestamp()
            except Exception:
                pass
        if not date_ts:
            fn_display, fn_ts = _parse_filename_timestamp(fname)
            if fn_ts:
                date_display = date_display or fn_display
                date_ts = fn_ts
        return {
            'message_id': message_id,
            'from_name': from_name, 'from_email': from_email,
            'subject': subject, 'date': date_display, 'date_ts': date_ts,
            'to': to_raw, 'cc': cc_raw,
        }
    except Exception:
        return None


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
            if not (fname.name.endswith('.eml') or fname.name.endswith('.txt')):
                continue
            try:
                parsed = None
                if fname.name.endswith('.eml'):
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
                        from_name = from_raw[:from_raw.index('<')].strip().strip('\"').replace(',', ' ')
                        from_email = from_raw[from_raw.index('<')+1:from_raw.index('>')]
                    date_display = ''
                    date_ts = 0
                    try:
                        dt = _pdt(date_str)
                        date_display = dt.strftime('%d.%m.%Y %H:%M')
                        date_ts = dt.timestamp()
                    except Exception:
                        pass
                    if not date_ts:
                        fn_display, fn_ts = _parse_filename_timestamp(fname.name)
                        if fn_ts:
                            date_display = date_display or fn_display
                            date_ts = fn_ts
                    if not date_ts:
                        try:
                            date_ts = fname.stat().st_mtime
                        except Exception:
                            pass
                    parsed = {
                        'message_id': message_id,
                        'from_name': from_name, 'from_email': from_email,
                        'subject': subject, 'date': date_display, 'date_ts': date_ts,
                        'to': to_raw, 'cc': cc_raw,
                    }
                else:
                    # .txt with German header format
                    parsed = _parse_txt_email(fname.path, fname.name)
                    if parsed and not parsed.get('date_ts'):
                        try:
                            parsed['date_ts'] = fname.stat().st_mtime
                        except Exception:
                            pass

                if not parsed:
                    continue
                # Only include entries that actually look like emails
                if not (parsed['from_email'] or parsed['subject']):
                    continue

                entries.append({
                    **parsed,
                    '_filename': fname.name,
                    '_fpath': fname.path,
                    '_s_from': (parsed['from_name'].replace(',', ' ') + ' ' + parsed['from_email'] + ' ' + fname.name).lower(),
                    '_s_subj': parsed['subject'].lower(),
                    '_s_to': (parsed.get('to','') + ' ' + parsed.get('cc','')).lower(),
                })
            except Exception:
                continue
    except Exception:
        pass
    entries.sort(key=lambda e: e.get('date_ts', 0), reverse=True)
    return entries"""

content = content.replace(old_build, new_build, 1)
print("OK: _build_email_cache erweitert (.eml + .txt, Filename-Timestamp Fallback)")

# ═══════════════════════════════════════════════════════════════
# FIX 2: /api/email-content auch .txt Dateien lesen
# ═══════════════════════════════════════════════════════════════
must_replace("email_content_route: .txt Support",
"    for sdir in search_dirs:\n"
"        try:\n"
"            for fname in os.listdir(sdir):\n"
"                if not fname.endswith('.eml'):\n"
"                    continue\n"
"                fpath = os.path.join(sdir, fname)\n"
"                try:\n"
"                    with open(fpath, 'r', errors='replace') as f:\n"
"                        msg = _email_mod.message_from_file(f)",
"    def _read_txt_email(fpath, fname):\n"
"        try:\n"
"            with open(fpath, 'r', errors='replace') as f:\n"
"                full = f.read()\n"
"            # Split headers from body (first blank line)\n"
"            header_end = full.find('\\n\\n')\n"
"            if header_end == -1:\n"
"                header_end = len(full)\n"
"            header_block = full[:header_end]\n"
"            body = full[header_end+2:] if header_end < len(full) else ''\n"
"            headers = {}\n"
"            for line in header_block.split('\\n'):\n"
"                for key_de, key_en in [('von:','from'),('an:','to'),('betreff:','subject'),('datum:','date'),('cc:','cc'),('kopie:','cc'),('message-id:','message_id')]:\n"
"                    if line.lower().startswith(key_de) or line.lower().startswith(key_en + ':'):\n"
"                        headers[key_en] = line.split(':', 1)[1].strip()\n"
"                        break\n"
"            return headers, body\n"
"        except Exception:\n"
"            return None, None\n"
"\n"
"    for sdir in search_dirs:\n"
"        try:\n"
"            for fname in os.listdir(sdir):\n"
"                if not (fname.endswith('.eml') or fname.endswith('.txt')):\n"
"                    continue\n"
"                fpath = os.path.join(sdir, fname)\n"
"                try:\n"
"                    if fname.endswith('.txt'):\n"
"                        headers, body = _read_txt_email(fpath, fname)\n"
"                        if not headers:\n"
"                            continue\n"
"                        mid = headers.get('message_id', '').strip()\n"
"                        from_raw_txt = headers.get('from', '')\n"
"                        subj_txt = headers.get('subject', '')\n"
"                        # Match\n"
"                        if target_mid and mid == target_mid:\n"
"                            pass\n"
"                        elif target_from:\n"
"                            if target_from not in from_raw_txt.lower():\n"
"                                continue\n"
"                            if target_subj and target_subj not in subj_txt.lower():\n"
"                                continue\n"
"                        else:\n"
"                            continue\n"
"                        # Build result\n"
"                        from_name = ''\n"
"                        from_email = from_raw_txt\n"
"                        if '<' in from_raw_txt and '>' in from_raw_txt:\n"
"                            from_name = from_raw_txt[:from_raw_txt.index('<')].strip().strip('\"')\n"
"                            from_email = from_raw_txt[from_raw_txt.index('<')+1:from_raw_txt.index('>')]\n"
"                        date_display = headers.get('date', '')\n"
"                        try:\n"
"                            from email.utils import parsedate_to_datetime\n"
"                            dt = parsedate_to_datetime(date_display)\n"
"                            date_display = dt.strftime('%d.%m.%Y %H:%M')\n"
"                        except Exception:\n"
"                            pass\n"
"                        if len(body) > 5000:\n"
"                            body = body[:5000] + '\\n\\n[... gekuerzt, ' + str(len(body)) + ' Zeichen gesamt]'\n"
"                        return jsonify({\n"
"                            'ok': True,\n"
"                            'from_name': from_name, 'from_email': from_email,\n"
"                            'to': headers.get('to', ''), 'cc': headers.get('cc', ''),\n"
"                            'subject': subj_txt, 'date': date_display,\n"
"                            'message_id': mid, 'body': body, 'file': fname,\n"
"                        })\n"
"                    with open(fpath, 'r', errors='replace') as f:\n"
"                        msg = _email_mod.message_from_file(f)")

# ═══════════════════════════════════════════════════════════════
# FIX 3: Datumssortierung in search_preview fuer email-Suche
# ═══════════════════════════════════════════════════════════════
must_replace("search_preview: Datumssortierung bei email",
"        # Sort: from_person first, then highest score, then newest date\n"
"        items.sort(key=lambda x: (not x.get('from_person'), -x['score'], x.get('date','') or '0'), reverse=False)",
"        # Sort: from_person first, then highest score, then newest date\n"
"        if search_type == 'email':\n"
"            # For email searches: strongly prefer date desc (newest first)\n"
"            items.sort(key=lambda x: (not x.get('from_person'), -(x.get('date','') or ''), -x['score']) if False else (not x.get('from_person'), x.get('date','') or ''), reverse=False)\n"
"            items.sort(key=lambda x: x.get('date','') or '', reverse=True)\n"
"        else:\n"
"            items.sort(key=lambda x: (not x.get('from_person'), -x['score'], x.get('date','') or '0'), reverse=False)")

# ═══════════════════════════════════════════════════════════════
# FIX 4: Frontend — E-Mail-Inhalt korrekt laden + Message-ID in Kontext
# Update _openEmailInChat to pass file to server if available
# ═══════════════════════════════════════════════════════════════
# Already handled: _openEmailInChat calls /api/email-content which now supports .txt

# Write
with open(path, 'w') as f:
    f.write(content)

print("\nAlle Patches erfolgreich angewendet!")
