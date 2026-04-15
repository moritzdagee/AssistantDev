#!/usr/bin/env python3
"""
Patch: Sub-Agent Konversationen in History sichtbar machen.

Bug: get_history() sucht in `datalake/<agent_name>/` statt im Parent-Ordner.
     Fuer Sub-Agents wie 'signicat_outbound' existiert der Ordner nicht.
     Zusaetzlich: kein Filtering nach Sub-Agent — Parent-Konversationen und
     Sub-Agent-Konversationen werden vermischt.

Fix:
  1. Nutze get_agent_speicher() (Parent-Ordner) statt direkten Pfad
  2. Filtere Konversationen: Sub-Agent sieht nur eigene (mit _suffix)
  3. Auch load_conversation braucht den gleichen Pfad-Fix

Marker: SUBAGENT_HISTORY_V1
"""
import os, sys

WS = os.path.expanduser("~/AssistantDev/src/web_server.py")

def apply(src, old, new, marker, desc):
    if marker in src:
        print(f"  [skip] {desc}")
        return src, False
    c = src.count(old)
    if c != 1:
        print(f"  [FAIL] {desc}: {c} Vorkommen")
        sys.exit(2)
    print(f"  [OK]   {desc}")
    return src.replace(old, new, 1), True


# ═══════════════════════════════════════════════════════════════════════════
# Patch 1: get_history — Pfad + Filtering fixen
# ═══════════════════════════════════════════════════════════════════════════

OLD_HISTORY = """@app.route('/get_history', methods=['GET'])
def get_history():
    session_id = request.args.get('session_id', 'default')
    state = get_session(session_id)
    agent = request.args.get('agent', '')
    speicher = os.path.join(BASE, agent)
    if not agent or not os.path.exists(speicher):
        return jsonify({'sessions': []})

    # Scan conversation files directly from disk (ignore _index.json for listing)
    conv_files = [
        f for f in os.listdir(speicher)
        if f.startswith('konversation_') and f.endswith('.txt')
    ]"""

NEW_HISTORY = """@app.route('/get_history', methods=['GET'])
def get_history():
    # SUBAGENT_HISTORY_V1: Sub-Agents nutzen Parent-Ordner + Suffix-Filtering
    session_id = request.args.get('session_id', 'default')
    state = get_session(session_id)
    agent = request.args.get('agent', '')
    if not agent:
        return jsonify({'sessions': []})
    # Korrekten Speicher-Pfad verwenden (Sub-Agents → Parent-Ordner)
    speicher = get_agent_speicher(agent)
    if not os.path.exists(speicher):
        return jsonify({'sessions': []})

    # Sub-Agent-Suffix bestimmen (z.B. 'outbound' fuer 'signicat_outbound')
    parent = get_parent_agent(agent)
    sub_suffix = '_' + agent.split('_', 1)[1] if parent else None

    # Scan conversation files directly from disk (ignore _index.json for listing)
    all_conv_files = [
        f for f in os.listdir(speicher)
        if f.startswith('konversation_') and f.endswith('.txt')
    ]
    # Filtern: Sub-Agents sehen nur ihre eigenen Konversationen (mit Suffix)
    # Parent-Agents sehen nur Konversationen OHNE Sub-Agent-Suffix
    if sub_suffix:
        conv_files = [f for f in all_conv_files if sub_suffix + '.txt' in f]
    else:
        # Parent: nur Dateien die KEIN Sub-Agent-Suffix haben
        # Sub-Agent-Suffixe: _outbound.txt, _lamp.txt, _meddpicc.txt, etc.
        conv_files = [f for f in all_conv_files
                      if not any(f.endswith('_' + s + '.txt') for s in
                                 [agent.split('_', 1)[1] for agent in
                                  [n.replace('.txt', '') for n in os.listdir(AGENTS_DIR)
                                   if n.endswith('.txt') and '_' in n and n.startswith(agent + '_')]
                                 ] if True) or not '_' in f.replace('konversation_', '').replace('.txt', '').rsplit('_', 1)[-1].replace('-', '').replace(' ', '').replace('0', '').replace('1', '').replace('2', '').replace('3', '').replace('4', '').replace('5', '').replace('6', '').replace('7', '').replace('8', '').replace('9', '')]
    conv_files = conv_files  # resolved above"""

# Hmm the parent-filtering is too complex. Let me simplify.

OLD_HISTORY_2 = """@app.route('/get_history', methods=['GET'])
def get_history():
    session_id = request.args.get('session_id', 'default')
    state = get_session(session_id)
    agent = request.args.get('agent', '')
    speicher = os.path.join(BASE, agent)
    if not agent or not os.path.exists(speicher):
        return jsonify({'sessions': []})

    # Scan conversation files directly from disk (ignore _index.json for listing)
    conv_files = [
        f for f in os.listdir(speicher)
        if f.startswith('konversation_') and f.endswith('.txt')
    ]"""

NEW_HISTORY_2 = """@app.route('/get_history', methods=['GET'])
def get_history():
    # SUBAGENT_HISTORY_V1: Sub-Agents nutzen Parent-Ordner + Suffix-Filtering
    session_id = request.args.get('session_id', 'default')
    state = get_session(session_id)
    agent = request.args.get('agent', '')
    if not agent:
        return jsonify({'sessions': []})
    # Korrekten Speicher-Pfad (Sub-Agents → Parent-Ordner)
    speicher = get_agent_speicher(agent)
    if not os.path.exists(speicher):
        return jsonify({'sessions': []})

    # Sub-Agent-Suffix bestimmen (z.B. '_outbound' fuer 'signicat_outbound')
    parent = get_parent_agent(agent)
    sub_suffix = '_' + agent.split('_', 1)[1] if parent else None

    # Alle Konversations-Dateien im Ordner
    all_conv = [f for f in os.listdir(speicher)
                if f.startswith('konversation_') and f.endswith('.txt')]

    if sub_suffix:
        # Sub-Agent: nur Dateien mit diesem Suffix (z.B. *_outbound.txt)
        conv_files = [f for f in all_conv if f.endswith(sub_suffix + '.txt')]
    else:
        # Parent-Agent: alle Dateien die KEINEN bekannten Sub-Agent-Suffix haben
        # Bekannte Suffixe aus den Agent-Dateien ableiten
        known_subs = set()
        for afile in os.listdir(AGENTS_DIR):
            if afile.endswith('.txt') and '_' in afile:
                aname = afile.replace('.txt', '')
                if get_parent_agent(aname) == agent:
                    known_subs.add('_' + aname.split('_', 1)[1] + '.txt')
        if known_subs:
            conv_files = [f for f in all_conv
                          if not any(f.endswith(s) for s in known_subs)]
        else:
            conv_files = all_conv"""


src = open(WS).read()

if 'SUBAGENT_HISTORY_V1' in src:
    print("Schon gepatcht.")
    sys.exit(0)

c = src.count(OLD_HISTORY_2)
if c != 1:
    print(f"FEHLER: get_history Block nicht exakt gefunden ({c})")
    sys.exit(2)

src = src.replace(OLD_HISTORY_2, NEW_HISTORY_2, 1)
print("[OK] get_history gepatcht")

# ═══════════════════════════════════════════════════════════════════════════
# Patch 2: load_conversation — gleicher Pfad-Fix
# ═══════════════════════════════════════════════════════════════════════════

# Suche load_conversation Route
OLD_LOAD = """@app.route('/load_conversation', methods=['POST'])"""

import re
# Finde den Block nach @app.route('/load_conversation')
idx = src.find(OLD_LOAD)
if idx == -1:
    print("[SKIP] load_conversation nicht gefunden")
else:
    # Suche nach "speicher = os.path.join(BASE, agent)" innerhalb der naechsten 30 Zeilen
    block = src[idx:idx+1500]
    old_line = "    speicher = os.path.join(BASE, agent)"
    if old_line in block and "get_agent_speicher" not in block[:block.find(old_line)+100]:
        new_line = "    speicher = get_agent_speicher(agent)  # SUBAGENT_HISTORY_V1: Parent-Ordner"
        src = src[:idx] + block.replace(old_line, new_line, 1) + src[idx+len(block):]
        print("[OK] load_conversation Pfad gefixt")
    else:
        print("[SKIP] load_conversation: schon gefixt oder anders strukturiert")

open(WS, 'w').write(src)
print(f"Fertig ({len(src)} bytes)")
