#!/usr/bin/env python3
"""
Fix: Such-Limit 500, Slash-Commands erweitern.
1. max_results=50 -> 500 fuer Anzeige
2. Slash-Commands: /find-whatsapp, /find-slack, /find-salesforce
3. Regex fuer /find-TYPE erweitern
4. knownTypes Liste erweitern
5. typeLabels erweitern
"""

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
        print(f"\u2717 {label}")
        return False

# 1. max_results=50 -> 500 (local search)
do_replace(
    "results, feedback = HybridSearch.search(intent, state['speicher'], max_results=50, forced_type=search_type)",
    "results, feedback = HybridSearch.search(intent, state['speicher'], max_results=500, forced_type=search_type)",
    "1a: HybridSearch max_results 50->500"
)

# 1b. max_results=50 -> 500 (global search)
do_replace(
    "results, feedback = global_search(effective_query, max_results=50)",
    "results, feedback = global_search(effective_query, max_results=500)",
    "1b: global_search max_results 50->500"
)

# 2. Slash Commands erweitern
do_replace(
    "  {cmd: '/find-email', label: '/find-email [query]', desc: 'Nur E-Mails durchsuchen'},\n"
    "  {cmd: '/find-webclip', label: '/find-webclip [query]', desc: 'Nur Web Clips durchsuchen'},\n"
    "  {cmd: '/find-document', label: '/find-document [query]', desc: 'Nur Dokumente (Word/Excel/PDF/PPTX)'},\n"
    "  {cmd: '/find-conversation', label: '/find-conversation [query]', desc: 'Nur Konversationen durchsuchen'},\n"
    "  {cmd: '/find-screenshot', label: '/find-screenshot [query]', desc: 'Nur Screenshots durchsuchen'},",

    "  {cmd: '/find-email', label: '/find-email [query]', desc: 'Nur E-Mails durchsuchen'},\n"
    "  {cmd: '/find-whatsapp', label: '/find-whatsapp [query]', desc: 'Nur WhatsApp Chats durchsuchen'},\n"
    "  {cmd: '/find-webclip', label: '/find-webclip [query]', desc: 'Alle Web Clips (Salesforce, Slack, etc.)'},\n"
    "  {cmd: '/find-slack', label: '/find-slack [query]', desc: 'Nur Slack Nachrichten'},\n"
    "  {cmd: '/find-salesforce', label: '/find-salesforce [query]', desc: 'Nur Salesforce Records'},\n"
    "  {cmd: '/find-document', label: '/find-document [query]', desc: 'Nur Dokumente (Word/Excel/PDF/PPTX)'},\n"
    "  {cmd: '/find-conversation', label: '/find-conversation [query]', desc: 'Nur Konversationen durchsuchen'},\n"
    "  {cmd: '/find-screenshot', label: '/find-screenshot [query]', desc: 'Nur Screenshots durchsuchen'},",
    "2: Slash Commands erweitert"
)

# 3. Regex fuer /find-TYPE erweitern
do_replace(
    "const typedFindMatch = text.match(/^\\/find(_global)?(?:-(email|webclip|screenshot|contact|document|conversation))?(?:\\s+(.*))?$/i);",
    "const typedFindMatch = text.match(/^\\/find(_global)?(?:-(email|whatsapp|webclip|slack|salesforce|screenshot|contact|document|conversation))?(?:\\s+(.*))?$/i);",
    "3: Regex /find-TYPE erweitert"
)

# 4. knownTypes Liste erweitern
do_replace(
    "const knownTypes = ['email','webclip','screenshot','contact','document','conversation'];",
    "const knownTypes = ['email','whatsapp','webclip','slack','salesforce','screenshot','contact','document','conversation'];",
    "4: knownTypes erweitert"
)

# 5. typeLabels erweitern
do_replace(
    "const typeLabels2 = {email:'E-Mail',webclip:'Web Clip',screenshot:'Screenshot',document:'Dokument',conversation:'Konversation'};",
    "const typeLabels2 = {email:'E-Mail',whatsapp:'WhatsApp',webclip:'Web Clip',slack:'Slack',salesforce:'Salesforce',screenshot:'Screenshot',document:'Dokument',conversation:'Konversation'};",
    "5: typeLabels erweitert"
)

# 5b. Check if there's another typeLabels object
# Search for other label mappings
if "provider_names = {" in code:
    pass  # That's the provider names, not search labels

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
