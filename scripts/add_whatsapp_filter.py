#!/usr/bin/env python3
"""Add WhatsApp filter button + JS mappings to web_server.py search dialog."""

import sys

WEB_SERVER = "/Users/moritzcremer/AssistantDev/src/web_server.py"

with open(WEB_SERVER, "r", encoding="utf-8") as f:
    code = f.read()

changes = 0
errors = []

def do_replace(old, new, label):
    global code, changes
    if old in code:
        code = code.replace(old, new)
        changes += 1
        print(f"\u2713 {label}")
        return True
    else:
        errors.append(label)
        print(f"\u2717 {label} – Pattern nicht gefunden!")
        return False

# 1. HTML: Add WhatsApp filter button after Screenshot button
do_replace(
    """      <button class="search-filter-btn" data-filter="screenshot" onclick="applySearchFilter('screenshot')">&#128248; Screenshot</button>""",
    """      <button class="search-filter-btn" data-filter="screenshot" onclick="applySearchFilter('screenshot')">&#128248; Screenshot</button>\n      <button class="search-filter-btn" data-filter="whatsapp" onclick="applySearchFilter('whatsapp')">&#128172; WhatsApp</button>""",
    "1: WhatsApp Filter-Button HTML"
)

# 2. JS: _SOURCE_SUBTYPES — add whatsapp
do_replace(
    "  'document': ['document_word', 'document_excel', 'document_pdf', 'document_pptx'],",
    "  'document': ['document_word', 'document_excel', 'document_pdf', 'document_pptx'],\n  'whatsapp': ['whatsapp_direct', 'whatsapp_group'],",
    "2: _SOURCE_SUBTYPES whatsapp"
)

# 3. JS: _SOURCE_SUBLABELS — add whatsapp subtypes
do_replace(
    "  'document_word': 'Word', 'document_excel': 'Excel', 'document_pdf': 'PDF', 'document_pptx': 'PowerPoint',",
    "  'document_word': 'Word', 'document_excel': 'Excel', 'document_pdf': 'PDF', 'document_pptx': 'PowerPoint',\n  'whatsapp_direct': 'Direktnachricht', 'whatsapp_group': 'Gruppenchat',",
    "3: _SOURCE_SUBLABELS whatsapp"
)

# 4. JS: _SOURCE_PARENTS — add whatsapp subtypes
do_replace(
    "  'document_pdf': 'document', 'document_pptx': 'document',",
    "  'document_pdf': 'document', 'document_pptx': 'document',\n  'whatsapp_direct': 'whatsapp', 'whatsapp_group': 'whatsapp',",
    "4: _SOURCE_PARENTS whatsapp"
)

if errors:
    print(f"\nFEHLER: {len(errors)} Patterns nicht gefunden:")
    for e in errors:
        print(f"  - {e}")
    print("Datei wird NICHT geschrieben!")
    sys.exit(1)

with open(WEB_SERVER, "w", encoding="utf-8") as f:
    f.write(code)

print(f"\n{'='*50}")
print(f"Gesamt: {changes} Aenderungen geschrieben")
