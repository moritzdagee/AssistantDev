#!/usr/bin/env python3
"""Fix: Allow field-specific filters to bypass q length check."""
import sys

path = '/Users/moritzcremer/AssistantDev/src/web_server.py'
with open(path, 'r') as f:
    content = f.read()

old = ("    q = request.args.get('q', '').strip().lower()\n"
       "    if len(q) < 2:\n"
       "        return jsonify([])")

new = ("    q = request.args.get('q', '').strip().lower()\n"
       "    from_filter = request.args.get('from', '').strip().lower()\n"
       "    subj_filter = request.args.get('subject', '').strip().lower()\n"
       "    to_filter = request.args.get('to', '').strip().lower()\n"
       "    body_filter = request.args.get('body', '').strip().lower()\n"
       "    has_field_filter = bool(from_filter or subj_filter or to_filter or body_filter)\n"
       "    if len(q) < 2 and not has_field_filter:\n"
       "        return jsonify([])")

if old not in content:
    print("FEHLER: Suchstring nicht gefunden!", file=sys.stderr)
    sys.exit(1)

content = content.replace(old, new, 1)

# Also fix the inner filter logic to use the outer variables instead of re-reading request.args
old_inner = ("                # Check if query matches (supports field-specific filters)\n"
             "                from_filter = request.args.get('from', '').strip().lower()\n"
             "                subj_filter = request.args.get('subject', '').strip().lower()\n"
             "                to_filter = request.args.get('to', '').strip().lower()\n"
             "                body_filter = request.args.get('body', '').strip().lower()\n")

new_inner = ("                # Check if query matches (supports field-specific filters)\n")

if old_inner not in content:
    print("FEHLER: Inner filter block nicht gefunden!", file=sys.stderr)
    sys.exit(1)

content = content.replace(old_inner, new_inner, 1)

with open(path, 'w') as f:
    f.write(content)

print("Fix angewendet: field-spezifische Filter umgehen q-Laengencheck")
