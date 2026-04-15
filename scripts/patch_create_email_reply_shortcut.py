#!/usr/bin/env python3
"""Add /create-email-reply slash command shortcut to the frontend menu."""

FILE = 'src/web_server.py'

with open(FILE, 'r') as f:
    content = f.read()

OLD = "  {cmd: '/create-email', label: '/create-email', desc: 'E-Mail Draft erstellen', template: 'Erstelle eine E-Mail an [Empfaenger] zum Thema: ', group: 'Kommunikation'},"

NEW = """  {cmd: '/create-email', label: '/create-email', desc: 'E-Mail Draft erstellen', template: 'Erstelle eine E-Mail an [Empfaenger] zum Thema: ', group: 'Kommunikation'},
  {cmd: '/create-email-reply', label: '/create-email-reply', desc: 'E-Mail Antwort erstellen', template: 'Antworte auf die E-Mail von [Absender] zum Thema [Betreff]: ', group: 'Kommunikation'},"""

count = content.count(OLD)
print(f"Matches found: {count}")
if count == 0:
    print("ERROR: Pattern not found!")
    exit(1)

content = content.replace(OLD, NEW)

with open(FILE, 'w') as f:
    f.write(content)

print(f"Done. {count} replacement(s) made.")
