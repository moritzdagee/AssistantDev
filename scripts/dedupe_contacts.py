#!/usr/bin/env python3
"""Deduplicate contacts.json files per agent.
Merge rule: newest last_contact wins, all name variants concatenated, counts summed."""
import json
import os
import datetime
import shutil

BASE = os.path.expanduser("~/Library/Mobile Documents/com~apple~CloudDocs/Downloads shared/claude_datalake")
AGENTS = ['privat', 'signicat', 'standard', 'trustedcarrier']
TS = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')

report = []

for agent in AGENTS:
    cf = os.path.join(BASE, agent, 'memory', 'contacts.json')
    if not os.path.exists(cf):
        continue
    # Backup
    backup = f"{cf}.backup_{TS}"
    shutil.copy2(cf, backup)

    with open(cf, 'r') as f:
        data = json.load(f)
    contacts = data.get('contacts', [])
    orig_len = len(contacts)

    merged = {}  # email_lower -> contact dict
    for c in contacts:
        email = (c.get('email') or '').strip().lower()
        if not email:
            # Keep entries without email as-is (by name)
            key = '__name__' + (c.get('name') or '')
        else:
            key = email

        if key not in merged:
            merged[key] = dict(c)
            # Track name variants
            merged[key]['_name_variants'] = {c.get('name', '')} if c.get('name') else set()
        else:
            m = merged[key]
            # Merge: sum counts
            m['total_contacts'] = (m.get('total_contacts', 0) or 0) + (c.get('total_contacts', 0) or 0)
            m['sent'] = (m.get('sent', 0) or 0) + (c.get('sent', 0) or 0)
            m['received'] = (m.get('received', 0) or 0) + (c.get('received', 0) or 0)
            # Newest last_contact wins
            last_m = m.get('last_contact') or ''
            last_c = c.get('last_contact') or ''
            if last_c > last_m:
                m['last_contact'] = last_c
                # Prefer non-null fields from newer entry
                for k in ('name', 'company', 'title', 'phone'):
                    if c.get(k):
                        m[k] = c[k]
            # Earliest first_contact
            first_m = m.get('first_contact') or '9999'
            first_c = c.get('first_contact') or '9999'
            if first_c < first_m:
                m['first_contact'] = first_c
            # Collect name variants
            if c.get('name'):
                m['_name_variants'].add(c['name'])
            # Fill missing company/title/phone if empty in merged
            for k in ('company', 'title', 'phone'):
                if not m.get(k) and c.get(k):
                    m[k] = c[k]

    # Convert sets back + keep list of name variants if > 1
    deduped = []
    for m in merged.values():
        variants = m.pop('_name_variants', set())
        if len(variants) > 1:
            # Keep most common/longest name as primary, store others in _aka
            variants_list = sorted([v for v in variants if v], key=lambda x: -len(x))
            if variants_list:
                m['name'] = variants_list[0]
                m['name_variants'] = variants_list
        deduped.append(m)

    removed = orig_len - len(deduped)
    data['contacts'] = deduped
    data['total_contacts'] = len(deduped)
    data['deduped_at'] = datetime.datetime.now().isoformat()

    with open(cf, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    report.append(f"{agent}: {orig_len} -> {len(deduped)} ({removed} Duplikate entfernt)")
    print(f"{agent}: {orig_len} -> {len(deduped)} ({removed} Duplikate entfernt), backup={os.path.basename(backup)}")

print("\n=== SUMMARY ===")
for line in report:
    print(line)
