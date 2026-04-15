#!/usr/bin/env python3
"""Fix: Sub-Agent History Pfad + Filtering."""
import os, sys

WS = os.path.expanduser("~/AssistantDev/src/web_server.py")
src = open(WS).read()
MARKER = 'SUBAGENT_HISTORY_V1'

if MARKER in src:
    print("Schon gepatcht.")
    sys.exit(0)

# Fix 1: get_history — ersetze den direkten Pfad + fuege Filtering ein
OLD1 = "    agent = request.args.get('agent', '')\n    speicher = os.path.join(BASE, agent)\n    if not agent or not os.path.exists(speicher):\n        return jsonify({'sessions': []})"

NEW1 = """    agent = request.args.get('agent', '')
    if not agent:
        return jsonify({'sessions': []})
    # SUBAGENT_HISTORY_V1: Sub-Agents nutzen Parent-Ordner
    speicher = get_agent_speicher(agent)
    if not os.path.exists(speicher):
        return jsonify({'sessions': []})"""

# Diese Zeile kommt 2x vor (get_history + load_conversation)
# Ersetze nur die erste (get_history)
idx1 = src.find(OLD1)
if idx1 == -1:
    print("FEHLER: get_history Block nicht gefunden")
    sys.exit(2)
src = src[:idx1] + NEW1 + src[idx1+len(OLD1):]
print("[OK] get_history: Pfad gefixt")

# Jetzt Filtering einfuegen — ersetze den conv_files Block
OLD_CONV = """    conv_files = [
        f for f in os.listdir(speicher)
        if f.startswith('konversation_') and f.endswith('.txt')
    ]"""

NEW_CONV = """    # Sub-Agent-Suffix (z.B. '_outbound' fuer 'signicat_outbound')
    parent = get_parent_agent(agent)
    sub_suffix = '_' + agent.split('_', 1)[1] if parent else None
    all_conv = [f for f in os.listdir(speicher)
                if f.startswith('konversation_') and f.endswith('.txt')]
    if sub_suffix:
        # Sub-Agent: nur eigene Konversationen (mit Suffix im Dateinamen)
        conv_files = [f for f in all_conv if f.endswith(sub_suffix + '.txt')]
    else:
        # Parent: Konversationen ohne bekannte Sub-Agent-Suffixe
        known_subs = set()
        for afile in os.listdir(AGENTS_DIR):
            if afile.endswith('.txt') and '_' in afile:
                aname = afile.replace('.txt', '')
                if get_parent_agent(aname) == agent:
                    known_subs.add('_' + aname.split('_', 1)[1] + '.txt')
        conv_files = [f for f in all_conv
                      if not any(f.endswith(s) for s in known_subs)] if known_subs else all_conv"""

# Ersetze erste Vorkommen (in get_history)
idx2 = src.find(OLD_CONV)
if idx2 == -1:
    print("FEHLER: conv_files Block nicht gefunden")
    sys.exit(2)
src = src[:idx2] + NEW_CONV + src[idx2+len(OLD_CONV):]
print("[OK] get_history: Filtering eingefuegt")

# Fix 2: load_conversation — gleicher Pfad-Fix
OLD_LOAD = "    speicher = os.path.join(BASE, agent)"
# Es gibt jetzt noch 1 Vorkommen (load_conversation), da get_history schon gefixt
if src.count(OLD_LOAD) >= 1:
    # Finde es im Kontext von load_conversation
    idx3 = src.find("@app.route('/load_conversation'")
    if idx3 > 0:
        block_start = idx3
        local_idx = src.find(OLD_LOAD, block_start)
        if local_idx > 0 and local_idx < block_start + 500:
            new_load = "    speicher = get_agent_speicher(agent)  # SUBAGENT_HISTORY_V1"
            src = src[:local_idx] + new_load + src[local_idx+len(OLD_LOAD):]
            print("[OK] load_conversation: Pfad gefixt")

open(WS, 'w').write(src)
print(f"Fertig ({len(src)} bytes)")
