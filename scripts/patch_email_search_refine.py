#!/usr/bin/env python3
"""Refinement: bessere From-Parsing bei .txt, Deduplikation ohne Message-ID."""
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

# Fix: Clean up mailto: wrappers in from/to/cc fields (common in .txt emails)
# and dedup by (from_email, subject, date_ts) when message_id is missing

old_search_loop = """    results = []
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

new_search_loop = """    def _clean_email(s):
        # Strip mailto: wrappers and angle brackets
        import re as _re
        if not s: return ''
        # Common pattern in .txt files: "user@domain.de<mailto:user@domain.de>"
        m = _re.search(r'([\\w\\.\\-]+@[\\w\\.\\-]+)', s)
        return m.group(1) if m else s

    results = []
    seen_ids = set()
    seen_dedup = set()
    for entry in all_entries:
        if len(results) >= 8:
            break
        mid = entry['message_id']
        # Primary dedup: message_id
        if mid and mid in seen_ids:
            continue
        # Secondary dedup: (clean_from_email, subject, date_ts) — handles iCloud duplicates
        clean_from = _clean_email(entry['from_email']).lower()
        dedup_key = (clean_from, entry['subject'].strip(), entry.get('date_ts', 0))
        if dedup_key in seen_dedup:
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
            seen_dedup.add(dedup_key)
            results.append({
                'message_id': entry['message_id'],
                'from_name': entry['from_name'],
                'from_email': _clean_email(entry['from_email']),
                'subject': entry['subject'], 'date': entry['date'],
                'date_ts': entry['date_ts'],
                'to': entry['to'], 'cc': entry['cc'],
                'file': entry.get('_filename', ''),
                'fpath': entry.get('_fpath', ''),
            })
    return jsonify(results[:8])"""

content = content.replace(old_search_loop, new_search_loop, 1)
print("OK: Deduplikation + From-Email Cleaning")

# Write
with open(path, 'w') as f:
    f.write(content)

print("\nRefinement angewendet!")
