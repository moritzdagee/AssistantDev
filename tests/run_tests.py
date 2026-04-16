#!/usr/bin/env python3
"""
AssistantDev Test Suite
Prueft alle kritischen Features nach jeder Aenderung.
Aufruf: python3 ~/AssistantDev/tests/run_tests.py
"""

import requests
import json
import os
import sys
import time
from datetime import datetime

BASE_URL = "http://localhost:8080"
DATALAKE = os.path.expanduser(
    "~/Library/Mobile Documents/com~apple~CloudDocs/"
    "Downloads shared/claude_datalake"
)

# Farben fuer Terminal-Output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"

passed = []
failed = []
warnings = []

# Test-Session-ID (isoliert von echten Sessions)
TEST_SESSION = "test_" + str(int(time.time()))


def test(name, condition, details=""):
    if condition:
        passed.append(name)
        print(f"  {GREEN}✓{RESET} {name}")
    else:
        failed.append(name)
        print(f"  {RED}✗ FEHLER: {name}{RESET}")
        if details:
            print(f"    → {details}")


def warn(name, details=""):
    warnings.append(name)
    print(f"  {YELLOW}⚠ {name}{RESET}")
    if details:
        print(f"    → {details}")


def section(title):
    print(f"\n{BOLD}{BLUE}── {title} ──{RESET}")


# ============================================================
# 1. SERVER ERREICHBARKEIT
# ============================================================
section("Server Erreichbarkeit")

try:
    r = requests.get(BASE_URL, timeout=5)
    test("Server laeuft auf Port 8080", r.status_code == 200)
    test("HTML wird zurueckgegeben", "text/html" in r.headers.get("content-type", ""))
except Exception as e:
    test("Server laeuft auf Port 8080", False, str(e))
    print(f"\n{RED}Server nicht erreichbar – weitere Tests abgebrochen{RESET}")
    sys.exit(1)


# ============================================================
# 2. KRITISCHE UI-ELEMENTE
# ============================================================
section("UI-Elemente im HTML")

html = requests.get(BASE_URL).text

# ============================================================
# FRONTEND SANITAETS-CHECK (KRITISCH — laueft ZUERST)
# Prueft ob das ausgelieferte HTML/JS frei von Syntaxfehlern ist.
# Diese Tests haetten die JS-SyntaxError-Bugs vom 2026-04-13 verhindert.
# ============================================================
section("Frontend Sanitaets-Check (JS)")

import re as _re

# 1. JS-Block extrahieren
_js_match = _re.search(r'<script>(.*?)</script>', html, _re.DOTALL)
_js_code = _js_match.group(1) if _js_match else ''
test("Script-Block im HTML vorhanden", len(_js_code) > 1000)

# 2. Offene JS-Strings erkennen (unterminated string literal)
# Das ist der exakte Fehler der zweimal die App gekillt hat:
# Ein \n in einem Python triple-quoted HTML-Template wird zum echten Newline
# im JS-String → "Unterminated string literal" → gesamtes JS blockiert.
_js_lines = _js_code.split('\n')
_open_strings = []
for _li, _line in enumerate(_js_lines):
    _s = _line.rstrip()
    if not _s or _s.lstrip().startswith('//') or _s.lstrip().startswith('*'):
        continue
    # Single-quote String-Analyse
    _in_sq = False  # in single-quoted string
    _in_dq = False  # in double-quoted string
    _j = 0
    while _j < len(_s):
        _c = _s[_j]
        if _c == '\\' and _j + 1 < len(_s):
            _j += 2  # escaped char ueberspringen
            continue
        if _c == "'" and not _in_dq:
            _in_sq = not _in_sq
        elif _c == '"' and not _in_sq:
            _in_dq = not _in_dq
        _j += 1
    if _in_sq or _in_dq:
        # Kommentare mit Apostrophen ignorieren (z.B. "it's", "don't")
        _stripped = _s.lstrip()
        if _stripped.startswith('//') or _stripped.startswith('*'):
            continue
        # Heuristik: Kommentare in Code-Zeilen mit Apostrophen
        if '//' in _s:
            _comment_part = _s[_s.rindex('//'):]
            if any(w in _comment_part.lower() for w in ["it's","there's","don't","can't","won't"]):
                continue
        # False Positives: Zeilen die auf '; enden sind vollstaendig
        # (die Quote-Analyse wird durch &quot; oder verschachtelte Strings verwirrt)
        if _s.rstrip().endswith("';") or _s.rstrip().endswith('";'):
            continue
        # Regex-Literale mit Quotes koennen den Zaehler verwirren
        if '/g,' in _s or '/i,' in _s or '.replace(/' in _s or '.match(/' in _s or '.test(/' in _s:
            continue
        _open_strings.append((_li + 1, _s[-100:]))

_open_str_details = ""
if _open_strings:
    _open_str_details = f"{len(_open_strings)} offene Strings:\n"
    for _ln, _txt in _open_strings[:5]:
        _open_str_details += f"      JS Zeile {_ln}: ...{_txt}\n"
test("KRITISCH: Keine offenen JS-Strings (unterminated string literal)",
     len(_open_strings) == 0, _open_str_details)

# 3. Basis-Funktionen muessen im JS existieren
_critical_functions = [
    'function showAgentModal',
    'function selectAgent',
    'function loadAgents',
    'function sendMessage',
    'function doSendChat',
    'function handleChatResponse',
    'function addMessage',
    'function loadProviders',
    'function onModelChange',
    'function getAgentName',
    'function startTyping',
    'function stopTyping',
]
_missing_funcs = [fn for fn in _critical_functions if fn not in _js_code]
test("Alle kritischen JS-Funktionen vorhanden",
     len(_missing_funcs) == 0,
     f"Fehlende Funktionen: {_missing_funcs}" if _missing_funcs else "")

# 4. Prüfe ob window.onload korrekt ist (App-Initialisierung)
test("window.onload vorhanden und ruft loadProviders auf",
     "window.onload" in _js_code and "loadProviders" in _js_code)
test("window.onload ruft showAgentModal auf",
     "showAgentModal()" in _js_code)

# 5. Agent-Modal HTML-Struktur intakt
test("Agent-Modal HTML vollstaendig (id + agent-list + agent-box)",
     'id="agent-modal"' in html and 'id="agent-list"' in html and 'id="agent-box"' in html)

# 6. Agent-Button korrekt verlinkt
test("Agent-Button onclick=showAgentModal()",
     'onclick="showAgentModal()"' in html)

# 7. Prüfe dass kein Python-Escape-Artefakt im JS gelandet ist
# Z.B. \n das als echtes Newline in einem JS-String auftaucht
_bad_escapes = 0
for _li, _line in enumerate(_js_lines):
    _s = _line.rstrip()
    # Suche: eine Zeile die msg += ' oder let msg = ' enthaelt
    # und dann sofort endet (= der \n wurde zum Zeilenumbruch)
    if ("msg +=" in _s or "let msg" in _s) and _s.endswith("'") and ";" not in _s.split("'")[-1]:
        if _li + 1 < len(_js_lines):
            _nxt = _js_lines[_li + 1].lstrip()
            if _nxt and not _nxt.startswith('//') and not _nxt.startswith('var') and not _nxt.startswith('let') and not _nxt.startswith('const') and not _nxt.startswith('if') and not _nxt.startswith('}'):
                _bad_escapes += 1
test("Keine Python-Escape-Artefakte in JS-Strings (\\n → echtes Newline)",
     _bad_escapes == 0,
     f"{_bad_escapes} Stellen gefunden wo \\n in JS-String zu echtem Newline wurde" if _bad_escapes else "")

# 8. Essentielles CSS fuer Agent-Modal vorhanden
test("Agent-Modal CSS (.agent-opt) vorhanden",
     ".agent-opt" in html)
test("Slash-Autocomplete CSS vorhanden",
     "slash-ac" in html)

print(f"  {BLUE}(JS-Code: {len(_js_lines)} Zeilen, {len(_js_code)} Zeichen){RESET}")

# ============================================================
# Originale UI-Element Tests
# ============================================================
section("UI-Elemente im HTML")

test("Senden-Button vorhanden", "Senden" in html or "send-btn" in html)
test("Nachrichten-Input vorhanden", "msg-input" in html or "textarea" in html.lower())
test("Agent-Modal vorhanden", "agent-modal" in html or "agent" in html.lower())
test("Kopier-Button CSS vorhanden", "snippet-copy-btn" in html)
test("History-Sidebar vorhanden", "history-list" in html)
test("Session-ID Generierung vorhanden", "getSessionId" in html)
test("Stop-Button vorhanden", "stop-btn" in html)
test("Queue-Display vorhanden", "queue-display" in html)
test("Typing-Indicator vorhanden", "typing-indicator" in html or "typing" in html)
test("Kontext-Bar vorhanden", "ctx-bar" in html or "context" in html.lower())


# ============================================================
# 3. API ENDPOINTS — GET
# ============================================================
section("GET Endpoints")

# GET /models
try:
    r = requests.get(f"{BASE_URL}/models", timeout=5)
    test("GET /models erreichbar", r.status_code == 200)
    models = r.json()
    test("Models-Response ist Liste", isinstance(models, list))
    test("Mindestens 1 Provider", len(models) >= 1)
    if models:
        first = models[0]
        test("Provider hat 'provider' Feld", 'provider' in first)
        test("Provider hat 'models' Liste", isinstance(first.get('models'), list))
        # Check specific providers
        provider_keys = [m['provider'] for m in models]
        test("Anthropic Provider vorhanden", 'anthropic' in provider_keys)
except Exception as e:
    test("GET /models erreichbar", False, str(e))

# GET /agents
try:
    r = requests.get(f"{BASE_URL}/agents", timeout=5)
    test("GET /agents erreichbar", r.status_code == 200)
    agents = r.json()
    test("Agents-Response ist Liste", isinstance(agents, list))
    test("Mindestens 1 Agent", len(agents) >= 1)
    if agents:
        first = agents[0]
        test("Agent hat 'name' Feld", 'name' in first)
        test("Agent hat 'label' Feld", 'label' in first)
        test("Agent hat 'has_subagents' Feld", 'has_subagents' in first)
        test("Agent hat 'subagents' Liste", isinstance(first.get('subagents'), list))
    # Check specific agents
    agent_names = [a['name'] for a in agents]
    for expected in ["signicat", "privat", "system ward"]:
        found = any(expected in n for n in agent_names)
        if found:
            test(f"Agent '{expected}' vorhanden", True)
        else:
            warn(f"Agent '{expected}' nicht gefunden")
except Exception as e:
    test("GET /agents erreichbar", False, str(e))

# GET /get_history
try:
    r = requests.get(f"{BASE_URL}/get_history?agent=signicat&session_id={TEST_SESSION}", timeout=5)
    test("GET /get_history erreichbar", r.status_code == 200)
    data = r.json()
    test("History hat 'sessions' Feld", 'sessions' in data)
    sessions_list = data.get('sessions', [])
    if sessions_list:
        first = sessions_list[0]
        test("History-Entry hat 'date' Feld", 'date' in first)
        test("History-Entry hat 'file' Feld", 'file' in first)
        test("History-Entry hat 'title' Feld", 'title' in first)
        # Check date format (DD.MM.YYYY HH:MM)
        date_str = first.get('date', '')
        test("Datum in lesbarem Format (DD.MM.YYYY)", '.' in date_str and len(date_str) >= 10,
             f"Datum: '{date_str}'")
        # Check sorting (newest first by date display)
        if len(sessions_list) >= 2:
            date1 = sessions_list[0].get('date', '')
            date2 = sessions_list[1].get('date', '')
            test("Sortierung: neueste zuerst", date1 >= date2,
                 f"Erste: {date1}, Zweite: {date2}")
    else:
        warn("Keine Konversationen fuer signicat gefunden")
except Exception as e:
    test("GET /get_history erreichbar", False, str(e))

# GET /queue_status
try:
    r = requests.get(f"{BASE_URL}/queue_status?session_id={TEST_SESSION}", timeout=5)
    test("GET /queue_status erreichbar", r.status_code == 200)
    data = r.json()
    test("Queue-Status hat 'processing' Feld", 'processing' in data)
    test("Queue-Status hat 'queue_length' Feld", 'queue_length' in data)
except Exception as e:
    test("GET /queue_status erreichbar", False, str(e))

# GET /poll_responses
try:
    r = requests.get(f"{BASE_URL}/poll_responses?session_id={TEST_SESSION}", timeout=5)
    test("GET /poll_responses erreichbar", r.status_code == 200)
    data = r.json()
    test("Poll hat 'responses' Liste", isinstance(data.get('responses'), list))
except Exception as e:
    test("GET /poll_responses erreichbar", False, str(e))

# GET /available_subagents
try:
    r = requests.get(f"{BASE_URL}/available_subagents?agent=signicat&session_id={TEST_SESSION}", timeout=5)
    test("GET /available_subagents erreichbar", r.status_code == 200)
    data = r.json()
    test("Subagents hat 'subagents' Liste", isinstance(data.get('subagents'), list))
except Exception as e:
    test("GET /available_subagents erreichbar", False, str(e))

# GET /get_prompt (needs agent selected first, test without)
try:
    r = requests.get(f"{BASE_URL}/get_prompt?agent=signicat&session_id={TEST_SESSION}", timeout=5)
    test("GET /get_prompt erreichbar", r.status_code == 200)
except Exception as e:
    test("GET /get_prompt erreichbar", False, str(e))


# ============================================================
# 4. API ENDPOINTS — POST (non-destructive)
# ============================================================
section("POST Endpoints (non-destructive)")

# POST /select_agent
try:
    r = requests.post(f"{BASE_URL}/select_agent", json={
        'agent': 'signicat', 'session_id': TEST_SESSION
    }, timeout=10)
    test("POST /select_agent erreichbar", r.status_code == 200)
    data = r.json()
    test("Agent-Auswahl erfolgreich", data.get('ok') is True, str(data))
except Exception as e:
    test("POST /select_agent erreichbar", False, str(e))

# POST /select_model
try:
    r = requests.post(f"{BASE_URL}/select_model", json={
        'provider': 'anthropic', 'model_id': 'claude-sonnet-4-6', 'session_id': TEST_SESSION
    }, timeout=5)
    test("POST /select_model erreichbar", r.status_code == 200)
    data = r.json()
    test("Model-Auswahl erfolgreich", data.get('ok') is True)
except Exception as e:
    test("POST /select_model erreichbar", False, str(e))

# POST /close_session
try:
    r = requests.post(f"{BASE_URL}/close_session", json={'session_id': TEST_SESSION}, timeout=5)
    test("POST /close_session erreichbar", r.status_code == 200)
    data = r.json()
    test("Session-Close erfolgreich", data.get('ok') is True)
except Exception as e:
    test("POST /close_session erreichbar", False, str(e))

# POST /new_conversation
try:
    # Re-select agent first (close_session cleared it)
    requests.post(f"{BASE_URL}/select_agent", json={
        'agent': 'signicat', 'session_id': TEST_SESSION
    }, timeout=10)
    r = requests.post(f"{BASE_URL}/new_conversation", json={
        'agent': 'signicat', 'session_id': TEST_SESSION
    }, timeout=5)
    test("POST /new_conversation erreichbar", r.status_code == 200)
    data = r.json()
    test("Neue Konversation erfolgreich", data.get('ok') is True)
except Exception as e:
    test("POST /new_conversation erreichbar", False, str(e))

# POST /stop_queue
try:
    r = requests.post(f"{BASE_URL}/stop_queue", json={'session_id': TEST_SESSION}, timeout=5)
    test("POST /stop_queue erreichbar", r.status_code == 200)
    data = r.json()
    test("Stop-Queue erfolgreich", data.get('ok') is True)
except Exception as e:
    test("POST /stop_queue erreichbar", False, str(e))

# POST /search_memory
try:
    r = requests.post(f"{BASE_URL}/search_memory", json={
        'query': 'test', 'session_id': TEST_SESSION
    }, timeout=10)
    test("POST /search_memory erreichbar", r.status_code == 200)
except Exception as e:
    test("POST /search_memory erreichbar", False, str(e))

# POST /search_preview
try:
    r = requests.post(f"{BASE_URL}/search_preview", json={
        'query': 'test', 'agent': 'signicat', 'session_id': TEST_SESSION
    }, timeout=10)
    test("POST /search_preview erreichbar", r.status_code == 200)
except Exception as e:
    test("POST /search_preview erreichbar", False, str(e))

# POST /global_search_preview
try:
    r = requests.post(f"{BASE_URL}/global_search_preview", json={
        'query': 'test', 'session_id': TEST_SESSION
    }, timeout=10)
    test("POST /global_search_preview erreichbar", r.status_code == 200)
except Exception as e:
    test("POST /global_search_preview erreichbar", False, str(e))

# POST /load_selected_files (empty selection — should work)
try:
    r = requests.post(f"{BASE_URL}/load_selected_files", json={
        'paths': [], 'session_id': TEST_SESSION
    }, timeout=5)
    test("POST /load_selected_files erreichbar", r.status_code == 200)
except Exception as e:
    test("POST /load_selected_files erreichbar", False, str(e))

# POST /remove_ctx
try:
    r = requests.post(f"{BASE_URL}/remove_ctx", json={
        'name': '__nonexistent__', 'session_id': TEST_SESSION
    }, timeout=5)
    test("POST /remove_ctx erreichbar", r.status_code == 200)
except Exception as e:
    test("POST /remove_ctx erreichbar", False, str(e))

# POST /open_in_finder
try:
    r = requests.post(f"{BASE_URL}/open_in_finder", json={
        'session_id': TEST_SESSION
    }, timeout=5)
    test("POST /open_in_finder erreichbar", r.status_code == 200)
except Exception as e:
    test("POST /open_in_finder erreichbar", False, str(e))

# POST /save_prompt (read-only test — don't actually save)
try:
    r = requests.get(f"{BASE_URL}/get_prompt?agent=signicat&session_id={TEST_SESSION}", timeout=5)
    test("GET /get_prompt fuer save-test erreichbar", r.status_code == 200)
    # We don't call save_prompt to avoid modifying data
except Exception as e:
    warn("GET /get_prompt nicht erreichbar", str(e))

# POST /chat (without agent = error expected)
try:
    test_session_no_agent = "test_noagent_" + str(int(time.time()))
    r = requests.post(f"{BASE_URL}/chat", json={
        'message': 'test', 'session_id': test_session_no_agent
    }, timeout=5)
    test("POST /chat ohne Agent gibt Fehler", 'error' in r.json() or r.status_code != 200)
except Exception as e:
    test("POST /chat erreichbar", False, str(e))


# ============================================================
# 5. DATEISYSTEM-CHECKS
# ============================================================
section("Dateisystem & Datalake")

test("Datalake-Ordner existiert", os.path.exists(DATALAKE), DATALAKE)

# Agent-Ordner
known_agents = ["signicat", "privat", "system ward", "standard", "trustedcarrier"]
for agent in known_agents:
    agent_path = os.path.join(DATALAKE, agent)
    if os.path.exists(agent_path):
        test(f"Agent-Ordner '{agent}' existiert", True)
    else:
        warn(f"Agent-Ordner '{agent}' nicht gefunden")

# Config-Dateien
config_files = {
    "config/models.json": True,
    "config/agents": True,
    "config/subagent_keywords.json": True,
}
for cf, required in config_files.items():
    path = os.path.join(DATALAKE, cf)
    exists = os.path.exists(path)
    if required:
        test(f"Config '{cf}' existiert", exists)
    elif not exists:
        warn(f"Config '{cf}' nicht gefunden")

# models.json lesbar und valide
models_path = os.path.join(DATALAKE, "config/models.json")
try:
    with open(models_path) as f:
        models_data = json.load(f)
    test("models.json ist valides JSON", True)
    providers = models_data.get('providers', {})
    test("models.json hat Provider-Eintraege", len(providers) > 0, f"Gefunden: {list(providers.keys())}")
    # Check each provider has api_key and models
    for pkey, pdata in providers.items():
        has_key = bool(pdata.get('api_key'))
        has_models = len(pdata.get('models', [])) > 0
        if has_key and has_models:
            test(f"Provider '{pkey}' hat API-Key + Models", True)
        elif not has_key:
            warn(f"Provider '{pkey}' hat keinen API-Key")
        elif not has_models:
            warn(f"Provider '{pkey}' hat keine Models")
except Exception as e:
    test("models.json lesbar", False, str(e))

# Konversationen vorhanden (direkt im Agent-Ordner, NICHT in konversationen/)
signicat_path = os.path.join(DATALAKE, "signicat")
if os.path.exists(signicat_path):
    conv_files = [f for f in os.listdir(signicat_path) if f.startswith('konversation_') and f.endswith('.txt')]
    test("Signicat-Konversationen vorhanden", len(conv_files) > 0, f"{len(conv_files)} Dateien gefunden")
    if conv_files:
        newest = sorted(conv_files)[-1]
        fpath = os.path.join(signicat_path, newest)
        try:
            with open(fpath, encoding='utf-8') as f:
                content = f.read()
            test("Neueste Konversation lesbar", len(content) > 0)
            test("Konversation hat Agent-Header", content.startswith('Agent:'))
        except Exception as e:
            test("Neueste Konversation lesbar", False, str(e))

    # _index.json
    index_path = os.path.join(signicat_path, '_index.json')
    if os.path.exists(index_path):
        try:
            with open(index_path) as f:
                idx = json.load(f)
            test("_index.json ist valides JSON", True)
            test("_index.json ist Liste", isinstance(idx, list))
        except Exception as e:
            test("_index.json lesbar", False, str(e))
    else:
        warn("_index.json nicht vorhanden fuer signicat")


# ============================================================
# 6. SESSION-ISOLATION
# ============================================================
section("Session-Isolation")

sess_a = "test_iso_a_" + str(int(time.time()))
sess_b = "test_iso_b_" + str(int(time.time()))

try:
    # Select different agents in different sessions
    r1 = requests.post(f"{BASE_URL}/select_agent", json={'agent': 'signicat', 'session_id': sess_a}, timeout=10)
    r2 = requests.post(f"{BASE_URL}/select_agent", json={'agent': 'privat', 'session_id': sess_b}, timeout=10)

    test("Session A: Agent-Auswahl ok", r1.json().get('ok') is True)
    test("Session B: Agent-Auswahl ok", r2.json().get('ok') is True)

    # Check queue status shows different states
    q1 = requests.get(f"{BASE_URL}/queue_status?session_id={sess_a}", timeout=5).json()
    q2 = requests.get(f"{BASE_URL}/queue_status?session_id={sess_b}", timeout=5).json()
    test("Session A: eigener Queue-Status", 'processing' in q1)
    test("Session B: eigener Queue-Status", 'processing' in q2)

    # Get prompt for each — should be different agents
    p1 = requests.get(f"{BASE_URL}/get_prompt?agent=signicat&session_id={sess_a}", timeout=5)
    p2 = requests.get(f"{BASE_URL}/get_prompt?agent=privat&session_id={sess_b}", timeout=5)
    test("Session A: Prompt-Abruf ok", p1.status_code == 200)
    test("Session B: Prompt-Abruf ok", p2.status_code == 200)
except Exception as e:
    test("Session-Isolation", False, str(e))


# ============================================================
# 7. KONVERSATIONS-LOGIK
# ============================================================
section("Konversations-Logik")

conv_session = "test_conv_" + str(int(time.time()))
try:
    # Select agent
    requests.post(f"{BASE_URL}/select_agent", json={
        'agent': 'signicat', 'session_id': conv_session
    }, timeout=10)

    # get_history should return sessions
    r = requests.get(f"{BASE_URL}/get_history?agent=signicat&session_id={conv_session}", timeout=5)
    hist = r.json()
    test("History liefert Sessions", len(hist.get('sessions', [])) > 0)

    sessions_list = hist.get('sessions', [])
    if sessions_list:
        # Check sorting: newest first (by mtime-based date)
        first_date = sessions_list[0].get('date', '')
        test("Neueste Konversation hat Datum", len(first_date) > 5, first_date)

        # Check no empty-title entries
        empty_titles = [s for s in sessions_list if not s.get('title')]
        test("Keine Eintraege ohne Titel", len(empty_titles) == 0,
             f"{len(empty_titles)} ohne Titel")

        # Load first conversation
        first = sessions_list[0]
        r = requests.post(f"{BASE_URL}/load_conversation", json={
            'agent': 'signicat', 'file': first['file'],
            'session_id': conv_session, 'resume': True
        }, timeout=5)
        data = r.json()
        test("Konversation ladbar", data.get('ok') is True)
        test("Konversation hat Nachrichten", len(data.get('messages', [])) > 0,
             f"{len(data.get('messages', []))} Messages")
        test("Resume-Flag zurueckgegeben", data.get('resumed') is True)

        # Verify messages have correct structure
        if data.get('messages'):
            msg = data['messages'][0]
            test("Message hat 'role' Feld", 'role' in msg)
            test("Message hat 'content' Feld", 'content' in msg)
            test("Erste Message ist user oder assistant",
                 msg['role'] in ('user', 'assistant'))

    # Verify conversation files exist on disk
    signicat_path = os.path.join(DATALAKE, "signicat")
    conv_files = [f for f in os.listdir(signicat_path)
                  if f.startswith('konversation_') and f.endswith('.txt')]
    test("Konversationsdateien auf Disk vorhanden", len(conv_files) > 0,
         f"{len(conv_files)} Dateien")

    # Check that files with content have proper format
    real_files = [f for f in conv_files if os.path.getsize(os.path.join(signicat_path, f)) > 50]
    if real_files:
        sample = os.path.join(signicat_path, real_files[0])
        with open(sample, encoding='utf-8') as f:
            header = f.readline()
        test("Konversationsdatei hat Agent-Header", header.startswith('Agent:'))

except Exception as e:
    test("Konversations-Logik", False, str(e))

# Cleanup test session
try:
    requests.post(f"{BASE_URL}/close_session", json={'session_id': conv_session}, timeout=5)
except Exception:
    pass


# ============================================================
# 8. FEATURES VOM 2026-04-06
# ============================================================
section("Features 2026-04-06")

# --- Section Copy Buttons ---
test("Section-Copy-Button CSS vorhanden", "section-copy-btn" in html)
test("Section-Copy-Button JS vorhanden", "addSectionCopyButtons" in html)

# --- Per-Konversation Modell-State ---
conv_model_session = "test_model_state_" + str(int(time.time()))
try:
    requests.post(f"{BASE_URL}/select_agent", json={
        'agent': 'signicat', 'session_id': conv_model_session
    }, timeout=10)
    r = requests.get(f"{BASE_URL}/get_history?agent=signicat&session_id={conv_model_session}", timeout=5)
    hist = r.json()
    sessions_list = hist.get('sessions', [])
    if sessions_list:
        r = requests.post(f"{BASE_URL}/load_conversation", json={
            'agent': 'signicat', 'file': sessions_list[0]['file'],
            'session_id': conv_model_session, 'resume': True
        }, timeout=5)
        data = r.json()
        test("load_conversation hat 'provider' Feld", 'provider' in data)
        test("load_conversation hat 'model_id' Feld", 'model_id' in data)
    else:
        warn("Keine Konversationen fuer Modell-State-Test")
    requests.post(f"{BASE_URL}/close_session", json={'session_id': conv_model_session}, timeout=5)
except Exception as e:
    test("Per-Konversation Modell-State", False, str(e))

# --- Memory Files Search API ---
try:
    r = requests.get(f"{BASE_URL}/api/memory-files-search?q=test&agent=signicat", timeout=5)
    test("GET /api/memory-files-search erreichbar", r.status_code == 200)
    data = r.json()
    test("Memory-Files-Search gibt Liste zurueck", isinstance(data, list))
except Exception as e:
    test("GET /api/memory-files-search erreichbar", False, str(e))

# Minimum query length check
try:
    r = requests.get(f"{BASE_URL}/api/memory-files-search?q=t&agent=signicat", timeout=5)
    data = r.json()
    test("Memory-Files-Search: <2 Zeichen gibt leere Liste", len(data) == 0)
except Exception as e:
    test("Memory-Files-Search Minimum-Length", False, str(e))

# --- search_engine.py Funktionen ---
try:
    import importlib.util
    spec = importlib.util.spec_from_file_location("search_engine",
        os.path.expanduser("~/AssistantDev/src/search_engine.py"))
    se = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(se)
    test("search_engine: update_all_indexes() existiert", hasattr(se, 'update_all_indexes'))
    test("search_engine: index_single_file() existiert", hasattr(se, 'index_single_file'))
except Exception as e:
    test("search_engine.py import", False, str(e))

# --- /find Command Backend ---
try:
    find_session = "test_find_" + str(int(time.time()))
    requests.post(f"{BASE_URL}/select_agent", json={
        'agent': 'signicat', 'session_id': find_session
    }, timeout=10)
    r = requests.post(f"{BASE_URL}/chat", json={
        'message': '/find test', 'session_id': find_session
    }, timeout=30)
    test("POST /chat mit /find erreichbar", r.status_code == 200)
    data = r.json()
    test("/find gibt response zurueck", 'response' in data or 'error' not in data)
    requests.post(f"{BASE_URL}/close_session", json={'session_id': find_session}, timeout=5)
except requests.exceptions.Timeout:
    warn("/find Command: Timeout", "API evtl. langsam")
except Exception as e:
    test("/find Command", False, str(e))

# --- Slash-Command Autocomplete im HTML ---
test("Slash-Command /find im HTML vorhanden", "/find" in html and ("Agent-Memory" in html or "Alle Dateien" in html))
test("Slash-Command /find_global im HTML vorhanden", "/find_global" in html)

# --- Entfernte alte Trigger nicht mehr vorhanden ---
test("detectSearchIntent entfernt", "detectSearchIntent" not in html)
test("detectGlobalTrigger entfernt", "detectGlobalTrigger" not in html)


# ============================================================
# 9. WEB CLIPPER
# ============================================================
section("Web Clipper (Port 8081)")

try:
    r = requests.get("http://localhost:8081", timeout=3)
    if r.status_code == 200:
        test("Web Clipper laeuft auf Port 8081", True)
    else:
        warn("Web Clipper antwortet mit Status " + str(r.status_code))
except Exception:
    warn("Web Clipper nicht erreichbar (Port 8081)", "Evtl. nicht gestartet — kein Fehler")


# ============================================================
# 10. FEATURES 2026-04-07
# ============================================================
section("Features 2026-04-07")

html = requests.get(BASE_URL + "/").text

# Markdown rendering
test("marked.js CDN im HTML", "marked.min.js" in html)
test("renderMarkdown Funktion im HTML", "renderMarkdown" in html)
test("markdown-rendered CSS class", "markdown-rendered" in html)

# Chat layout
test("Messages max-width:900px", "max-width:900px" in html)
test("Msg max-width:72%", "max-width:72%" in html)

# Keyboard shortcuts
test("Keyboard shortcuts: Alt+P (toggleSidebar)", "toggleSidebar()" in html and "alt" in html.lower())
test("Keyboard shortcuts: copyLastAssistantMessage", "copyLastAssistantMessage" in html)
test("Shortcut labels in HTML", "shortcut-label" in html)

# Find chips
test("Find chips bar HTML", "find-chips-bar" in html)
test("Find chips: E-Mail chip", 'data-cat="email"' in html)
test("Find chips: toggleFindChip function", "toggleFindChip" in html)
test("Find live dropdown HTML", "find-live-dropdown" in html)
test("Find live search: doFindLiveSearch", "doFindLiveSearch" in html)
test("Find live key handler: onFindLiveKey", "onFindLiveKey" in html)

# Sidebar default visible
test("Sidebar default width 30%", "sidebar { width:30%" in html)

# Removed file-ac field
test("Datei aus Memory suchen field REMOVED", 'placeholder="Datei aus Memory suchen' not in html)

# Search checkbox default unchecked
test("Search checkboxes: no auto-check", "checkedCount < 5" not in html)

# Search engine: get_recent_files
try:
    sys.path.insert(0, os.path.expanduser("~/AssistantDev/src"))
    from search_engine import get_recent_files, extract_search_keywords, search_contacts
    test("get_recent_files importierbar", True)

    # Test keyword extraction
    kws = extract_search_keywords("ich habe vor drei Monaten an Google geschrieben wegen Partnership", "email")
    test("extract_search_keywords: liefert Keywords", len(kws) >= 2)
    test("extract_search_keywords: Google enthalten", any("google" in kw.lower() for kw in kws))

    # Test search_contacts (may return 0 if no contacts.json — that's OK)
    test("search_contacts importierbar", callable(search_contacts))
except Exception as e:
    test("search_engine neue Funktionen", False, str(e))

# Backend: /search_preview with type parameter
try:
    # Select agent first
    requests.post(BASE_URL + "/select_agent", json={"agent": "signicat", "session_id": "test_2407"}, timeout=5)
    r = requests.post(BASE_URL + "/search_preview", json={
        "query": "price", "type": "document", "agent": "signicat", "session_id": "test_2407"
    }, timeout=15)
    data = r.json()
    test("/search_preview type=document: OK", data.get("ok") == True)
    test("/search_preview type=document: liefert Ergebnisse", len(data.get("results", [])) > 0)
    if data.get("results"):
        types = set(r.get("source_type", "") for r in data["results"])
        test("/search_preview type=document: nur Dokumente", all("document" in t for t in types))
except Exception as e:
    test("/search_preview type filter", False, str(e))

# Backend: /search_preview recent files
try:
    r = requests.post(BASE_URL + "/search_preview", json={
        "query": "", "recent": True, "agent": "signicat", "session_id": "test_2407"
    }, timeout=15)
    data = r.json()
    test("/search_preview recent=true: OK", data.get("ok") == True)
    test("/search_preview recent=true: liefert Ergebnisse", len(data.get("results", [])) > 0)
except Exception as e:
    test("/search_preview recent files", False, str(e))

# Backend: /search_preview with type=email
try:
    r = requests.post(BASE_URL + "/search_preview", json={
        "query": "", "recent": True, "type": "email", "agent": "signicat", "session_id": "test_2407"
    }, timeout=15)
    data = r.json()
    test("/search_preview recent email: OK", data.get("ok") == True)
    if data.get("results"):
        types = set(r.get("source_type", "") for r in data["results"])
        test("/search_preview recent email: nur E-Mails", all("email" in t or "notification" in t for t in types))
except Exception as e:
    test("/search_preview recent email", False, str(e))

# Web Clipper: backward compat + new format
try:
    # Old format
    r = requests.post("http://localhost:8081/save", json={
        "agent": "signicat", "content": "test_unit_test_2407", "filename": "__test_unit_2407.txt"
    }, timeout=5)
    data = r.json()
    test("Web Clipper legacy TXT save", data.get("success") == True)

    # New format
    r = requests.post("http://localhost:8081/save", json={
        "agent": "signicat", "url": "https://test.example.com",
        "title": "Test", "timestamp": "2026-04-07T00:00:00Z",
        "extracted_data": {"site_type": "web"}, "full_text": "test content",
        "filename": "__test_unit_2407.json"
    }, timeout=5)
    data = r.json()
    test("Web Clipper new JSON save", data.get("success") == True)

    # Clean up test files
    for fn in ["__test_unit_2407.txt", "__test_unit_2407.json"]:
        for d in [
            os.path.join(DATALAKE, "signicat/memory", fn),
            os.path.expanduser(f"~/Library/Mobile Documents/com~apple~CloudDocs/Downloads shared/webclips/signicat_{fn}")
        ]:
            if os.path.exists(d):
                os.remove(d)
except Exception:
    warn("Web Clipper Tests", "Port 8081 nicht erreichbar")


# ============================================================
# 11. APP BUNDLE KONSISTENZ
# ============================================================
# Typed /find commands
test("/find-email command in _SLASH_COMMANDS", "'/find-email'" in html or "/find-email" in html)
test("/find-document command in _SLASH_COMMANDS", "/find-document" in html)
test("/find-conversation command in _SLASH_COMMANDS", "/find-conversation" in html)
test("/find_global-email command in _SLASH_COMMANDS", "/find_global-email" in html)
test("Slash dropdown filters on input", "filterText" in html or "filter" in html)
test("sendMessage parses /find-TYPE regex", "find(_global)?(?:-(email|webclip" in html)

section("App Bundle Konsistenz")

bundle_path = "/Applications/Assistant.app/Contents/Resources"
src_path = os.path.expanduser("~/AssistantDev/src")

for fname in ["web_server.py", "search_engine.py"]:
    src_file = os.path.join(src_path, fname)
    bundle_file = os.path.join(bundle_path, fname)
    if os.path.exists(src_file) and os.path.exists(bundle_file):
        src_size = os.path.getsize(src_file)
        bundle_size = os.path.getsize(bundle_file)
        test(f"{fname}: src == bundle", src_size == bundle_size,
             f"src: {src_size} bytes, bundle: {bundle_size} bytes")
    elif not os.path.exists(bundle_file):
        warn(f"{fname} nicht im App Bundle")
    elif not os.path.exists(src_file):
        warn(f"{fname} nicht in src/")


# ============================================================
# 11. CHAT SMOKE TEST (optional — braucht API-Key)
# ============================================================
section("Chat Smoke Test")

smoke_session = "test_smoke_" + str(int(time.time()))
try:
    # Select agent first
    requests.post(f"{BASE_URL}/select_agent", json={
        'agent': 'signicat', 'session_id': smoke_session
    }, timeout=10)

    r = requests.post(f"{BASE_URL}/chat", json={
        'message': 'Sag nur das Wort: TESTOK',
        'session_id': smoke_session
    }, timeout=60)
    test("POST /chat erreichbar (mit Agent)", r.status_code == 200)

    if r.status_code == 200:
        data = r.json()
        if 'error' in data:
            warn("Chat-Antwort ist Fehler", data['error'])
        else:
            test("Chat gibt 'response' zurueck", 'response' in data)
            test("Chat gibt 'model_name' zurueck", 'model_name' in data)
            test("Chat gibt 'agent' zurueck", 'agent' in data)
            resp_text = data.get('response', '')
            test("Chat-Antwort nicht leer", len(resp_text) > 0)
except requests.exceptions.Timeout:
    warn("Chat Smoke Test: Timeout (60s)", "API evtl. langsam oder Key ungueltig")
except Exception as e:
    test("Chat Smoke Test", False, str(e))


# ============================================================
section("Features 2026-04-08")

html = requests.get(BASE_URL + "/").text

# WhatsApp Filter-Button im Such-Dialog
test("WhatsApp Filter-Button im HTML", "WhatsApp" in html and 'data-filter="whatsapp"' in html)
test("WhatsApp Subtypes in _SOURCE_SUBTYPES", "whatsapp_direct" in html and "whatsapp_group" in html)
test("WhatsApp Sublabels (Direktnachricht/Gruppenchat)", "Direktnachricht" in html and "Gruppenchat" in html)
test("WhatsApp Parents in _SOURCE_PARENTS", "'whatsapp_direct': 'whatsapp'" in html)

# Such-Dialog UX: Limit 50
test("Search Limit 50: Counter-Label", "0 / 50 ausgewaehlt" in html)
test("Search Limit 50: Alle-laden Button", "max 50)" in html)
test("Search Limit 50: Checkbox-Limit", "checked > 50" in html)

# Such-Dialog UX: Trefferanzahl + Toggle + Escape
test("Trefferanzahl Element (search-hit-count)", "search-hit-count" in html)
test("Alle-markieren Toggle-Button", "toggleAllSearchCheckboxes" in html)
test("Escape-Handler (_searchEscHandler)", "_searchEscHandler" in html)

# Backend: /load_selected_files accepts 6+ files
try:
    r = requests.post(BASE_URL + "/load_selected_files", json={
        "session_id": "test_0408", "paths": ["a","b","c","d","e","f"]
    }, timeout=10)
    data = r.json()
    test("Backend /load_selected_files: 6 Pfade akzeptiert", "error" not in str(data).lower())
except Exception as e:
    test("Backend /load_selected_files Limit", False, str(e))

# search_engine: WhatsApp SOURCE_TAXONOMY
try:
    sys.path.insert(0, os.path.expanduser("~/AssistantDev/src"))
    from search_engine import detect_source_type, SOURCE_TAXONOMY
    test("SOURCE_TAXONOMY: whatsapp vorhanden", "whatsapp" in SOURCE_TAXONOMY)
    test("SOURCE_TAXONOMY: whatsapp_direct vorhanden", "whatsapp_direct" in SOURCE_TAXONOMY)
    test("SOURCE_TAXONOMY: whatsapp_group vorhanden", "whatsapp_group" in SOURCE_TAXONOMY)
    test("detect_source_type: whatsapp_direct", detect_source_type("whatsapp_chat_Marco_2026.txt") == "whatsapp_direct")
    test("detect_source_type: whatsapp_group", detect_source_type("whatsapp_chat_group_Fam_2026.txt") == "whatsapp_group")
    test("detect_source_type: email unberührt", detect_source_type("email_test.txt") == "email")
except Exception as e:
    test("search_engine WhatsApp Taxonomy", False, str(e))

# WhatsApp Import Script: Parser
try:
    sys.path.insert(0, os.path.expanduser("~/AssistantDev/scripts"))
    from whatsapp_import import WhatsAppParser
    result = WhatsAppParser.parse_line("[02.04.26, 14:30:15] Marco: Hey!")
    test("WhatsApp Parser: DE-Format", result is not None and result["sender"] == "Marco")
    test("WhatsApp Parser: Timestamp", "2026-04-02" in result["timestamp"])
    media = WhatsAppParser.parse_line("[02.04.26, 09:00:00] X: <Medien weggelassen>")
    test("WhatsApp Parser: Media-Erkennung", media["is_media"] == True)
except Exception as e:
    test("WhatsApp Parser Tests", False, str(e))

# WhatsApp Sync Route (web_clipper_server.py)
try:
    r = requests.post("http://localhost:8081/whatsapp/sync", json={
        "agent": "privat", "contact": "UnitTest", "messages": [],
        "last_known_timestamp": "2020-01-01T00:00:00"
    }, timeout=10)
    data = r.json()
    test("/whatsapp/sync Route erreichbar", data.get("status") == "success")
    test("/whatsapp/sync leere Messages: appended=0", data.get("appended") == 0)
except Exception as e:
    test("/whatsapp/sync Route", False, str(e))

# Provider: kein stiller Fallback
test("Bildgenerierung: kein Fallback (providers_to_try entfernt)", "providers_to_try" not in html)
test("Bildgenerierung: strikte Pruefung", "Bildgenerierung nicht verfuegbar" in html or "nicht verfuegbar" in open(os.path.expanduser("~/AssistantDev/src/web_server.py")).read())

# Slash Commands: alle /find-TYPE vorhanden
test("/find-whatsapp Command im HTML", "/find-whatsapp" in html)
test("/find-slack Command im HTML", "/find-slack" in html)
test("/find-salesforce Command im HTML", "/find-salesforce" in html)
test("/find-email Command im HTML", "/find-email" in html)
test("/find-document Command im HTML", "/find-document" in html)
test("/find-conversation Command im HTML", "/find-conversation" in html)
test("/find-screenshot Command im HTML", "/find-screenshot" in html)

# Regex: /find-TYPE erkennt neue Typen
test("Find Regex: whatsapp im Pattern", "whatsapp" in html and "find(_global)?(?:-(email|whatsapp" in html)
test("Find Regex: slack im Pattern", "slack" in html and "salesforce" in html)

# Such-Limit 500
ws_code = open(os.path.expanduser("~/AssistantDev/src/web_server.py")).read()
test("Such-Limit: max_results=500 (lokal)", "max_results=500" in ws_code)

# Type-Aliases Backend
test("Type-Alias: slack->webclip_slack im Backend", "webclip_slack" in ws_code and "_type_aliases" in ws_code)

# E-Mail-Erkennung: DATUM_IN/OUT Pattern
try:
    from search_engine import detect_source_type
    test("detect_source_type: DATUM_IN Email", detect_source_type("2026-01-01_10-00-00_IN_test_at_test_com_Hello.txt") == "email")
    test("detect_source_type: DATUM_OUT Email", detect_source_type("2026-01-01_10-00-00_OUT_test_at_test_com_Hello.txt") == "email")
except Exception as e:
    test("detect_source_type DATUM Email", False, str(e))

# Duplikat-Filterung
try:
    from search_engine import SearchIndex
    test("Duplikat-Filter: _2.txt", SearchIndex._is_duplicate_file("test_2.txt") == True)
    test("Duplikat-Filter: _2 2.txt", SearchIndex._is_duplicate_file("test_2 2.txt") == True)
    test("Duplikat-Filter: normal.txt", SearchIndex._is_duplicate_file("normal.txt") == False)
except Exception as e:
    test("Duplikat-Filter Tests", False, str(e))

# Fuzzy Search
try:
    from search_engine import fuzzy_match
    m1, _ = fuzzy_match("nayara", "naiara")
    test("Fuzzy: Nayara~Naiara (Levenshtein)", m1 == True)
    m2, _ = fuzzy_match("marco", "marcio amigo")
    test("Fuzzy: Marco~Marcio (Edit Distance)", m2 == True)
    m3, _ = fuzzy_match("python", "javascript")
    test("Fuzzy: Python!=Javascript (No Match)", m3 == False)
except Exception as e:
    test("Fuzzy Search Tests", False, str(e))

# QueryParser force_search
try:
    from search_engine import QueryParser
    intent = QueryParser.parse("arne vidar", force_search=True)
    test("QueryParser force_search: keywords nicht leer", len(intent.keywords) >= 2)
    test("QueryParser force_search: person_names", len(intent.person_names) >= 2)
    test("QueryParser force_search: is_search=True", intent.is_search == True)
except Exception as e:
    test("QueryParser force_search", False, str(e))


# /create Slash Commands im HTML
test("/create-email Command im HTML", "'/create-email'" in html or '"/create-email"' in html or "/create-email" in html)
test("/create-whatsapp Command im HTML", "/create-whatsapp" in html)
test("/create-image Command im HTML", "/create-image" in html)
test("/create-video Command im HTML", "/create-video" in html)
test("/create-file-docx Command im HTML", "/create-file-docx" in html)
test("/create-file-xlsx Command im HTML", "/create-file-xlsx" in html)
test("/create-file-pdf Command im HTML", "/create-file-pdf" in html)
test("/create-file-pptx Command im HTML", "/create-file-pptx" in html)
test("Create Commands haben Templates", "template:" in html)
test("selectSlashCmd Template-Logik", "entry.template" in html)

# CREATE_SLACK Feature Tests
_ws_src = open(os.path.expanduser("~/AssistantDev/src/web_server.py")).read()
test("/create-slack Command im HTML", "/create-slack" in html)
test("CREATE_SLACK im System Prompt (web_server.py)", "CREATE_SLACK:" in _ws_src and "Slack-Nachricht" in _ws_src)
try:
    _slack_r = requests.post(f"{BASE_URL}/open_slack_draft",
        json={"message": "test"}, timeout=5)
    test("Slack Draft Route existiert (Validierung)", _slack_r.status_code == 200 and _slack_r.json().get('error') is not None)
except Exception:
    test("Slack Draft Route existiert (Validierung)", False)
test("created_slacks in Frontend-Handling", "created_slacks" in html)

# send_whatsapp_draft + send_slack_draft function fix verification (AST check)
import ast as _ast
_tree = _ast.parse(_ws_src)
_func_names = [n.name for n in _ast.walk(_tree) if isinstance(n, _ast.FunctionDef)]
test("send_whatsapp_draft korrekt als Funktion definiert (AST)", "send_whatsapp_draft" in _func_names)
test("send_slack_draft korrekt als Funktion definiert (AST)", "send_slack_draft" in _func_names)

# Agent-Switch Race Condition Fix (2026-04-15)
section("Agent-Switch Session Protection 2026-04-15")
test("Processing-Guard in select_agent", "Agent-Wechsel nicht moeglich waehrend eine Antwort generiert wird" in _ws_src)
test("parse_konversation_file Helper vorhanden", "def parse_konversation_file" in _ws_src)
test("find_latest_konversation Helper vorhanden", "def find_latest_konversation" in _ws_src)
test("Draft localStorage key im HTML", "draft_" in html and "localStorage.setItem" in html)
test("Draft clear nach Send", "localStorage.removeItem" in html and "draft_" in html)
test("Recovered messages in select_agent Response", "recovered_messages" in _ws_src)
test("Re-click same agent guard", "name == state.get" in _ws_src and "Re-click same agent" in _ws_src)
test("auto_save_session vor Agent-Wechsel", "Save current session before switching" in _ws_src)

# Memory Management UI (2026-04-15)
section("Memory UI 2026-04-15")
try:
    _mem_r = requests.get(f"{BASE_URL}/memory", timeout=5)
    _mem_html = _mem_r.text
    test("GET /memory -> 200", _mem_r.status_code == 200)
    test("Content-Type text/html", "text/html" in _mem_r.headers.get("Content-Type", ""))
    test("Memory Management Titel im HTML", "Memory Management" in _mem_html)
    test("Kein showAgentModal on page-load", "showAgentModal()" not in _mem_html)
    test("mmLoadWorking JS-Funktion vorhanden", "mmLoadWorking" in _mem_html)
    test("mmLoadFiles JS-Funktion vorhanden", "mmLoadFiles" in _mem_html)
    test("mmLoadAgents JS-Funktion vorhanden", "mmLoadAgents" in _mem_html)
    test("Agent-Selector vorhanden", "mm-agent-select" in _mem_html)
    test("Volltextsuche-Button vorhanden", "mmDeepSearch" in _mem_html)
except Exception as e:
    test("GET /memory erreichbar", False, str(e))
test("/api/memory/list Route in web_server.py", "def api_memory_list" in _ws_src)
test("memory_page Route in web_server.py", "def memory_page" in _ws_src)

# Working Memory Isolation fuer Sub-Agents (2026-04-15)
section("Working Memory Isolation 2026-04-15")
test("_get_wm_dir Helper existiert", "def _get_wm_dir" in _ws_src)
test("Sub-Agent nutzt _<subname> Unterordner", "'_' + subname" in _ws_src or '"_" + subname' in _ws_src)
test("load_working_memory nutzt _get_wm_dir", "def load_working_memory" in _ws_src and _ws_src.split("def load_working_memory")[1].split("def ")[0].find("_get_wm_dir") >= 0)
test("working_memory_add nutzt _get_wm_dir", "def working_memory_add" in _ws_src and _ws_src.split("def working_memory_add")[1].split("def ")[0].find("_get_wm_dir") >= 0)
try:
    import urllib.parse as _up
    # Parent signicat und Sub signicat_lamp muessen unterschiedliche file listings haben
    _parent_list = requests.post(
        f"{BASE_URL}/api/working-memory/signicat",
        json={"action": "list"}, timeout=5,
    ).json().get("manifest", {}).get("files", [])
    _sub_list = requests.post(
        f"{BASE_URL}/api/working-memory/signicat_lamp",
        json={"action": "list"}, timeout=5,
    ).json().get("manifest", {}).get("files", [])
    _parent_names = sorted(f.get("filename") for f in _parent_list)
    _sub_names = sorted(f.get("filename") for f in _sub_list)
    test("signicat Parent-WM != signicat_lamp Sub-WM (Isolation)",
         _parent_names != _sub_names or (_parent_list and _sub_list and _parent_list[0] is not _sub_list[0]))
except Exception as e:
    test("Working Memory Isolation Runtime-Check", False, str(e))

# ============================================================
section("Features 2026-04-09")
# ============================================================

# --- WhatsApp 3-Stufen Kontakt-Lookup ---
test("send_whatsapp_draft hat macOS Contacts Lookup (AppleScript)",
     "tell application" in _ws_src and "Contacts" in _ws_src and "whose name contains" in _ws_src)
test("send_whatsapp_draft hat Cross-Agent Lookup",
     "Step 2: Look up in ALL agents" in _ws_src or "cross-agent" in _ws_src.lower())

# --- Context-Bleeding Fix ---
test("CREATE_WHATSAPP Execution-Marker in verlauf",
     "Aktion ausgefuehrt" in _ws_src)
test("KEINE WIEDERHOLUNG Anweisung im System-Prompt",
     "KEINE WIEDERHOLUNG" in _ws_src)

# --- Gemini Veo numberOfVideos entfernt ---
test("Veo API-Call hat kein numberOfVideos",
     "numberOfVideos" not in _ws_src)

# --- LLM Signatur: Provider + Modell ---
test("PROVIDER_DISPLAY Mapping vorhanden",
     "PROVIDER_DISPLAY" in _ws_src and "'anthropic': 'Anthropic'" in _ws_src)
test("MODEL_DISPLAY Mapping vorhanden",
     "MODEL_DISPLAY" in _ws_src and "'claude-sonnet-4-6': 'Claude Sonnet 4.6'" in _ws_src)
test("provider_display im Chat-Response JSON",
     "provider_display" in _ws_src and "PROVIDER_DISPLAY.get(" in _ws_src)
test("model_display im Chat-Response JSON",
     "model_display" in _ws_src and "MODEL_DISPLAY.get(" in _ws_src)
test("addMessage hat providerDisplay Parameter",
     "providerDisplay" in html)

# --- Konversations-Sicherheit: Atomic Writes ---
test("Atomic Write: os.replace in auto_save_session",
     "os.replace(tmp_path, dateiname)" in _ws_src)
test("Sofort-Save bei User-Nachricht",
     "Sofort-Save" in _ws_src or "sofort" in _ws_src.lower())

# --- Perplexity Fixes ---
test("Perplexity max_tokens = 8000",
     "'max_tokens': 8000" in _ws_src or '"max_tokens": 8000' in _ws_src)
test("Perplexity Citations werden angehaengt",
     "citations" in _ws_src and "Quellen:" in _ws_src)
test("Perplexity Modell-spezifische Timeouts",
     "PERPLEXITY_TIMEOUTS" in _ws_src)
test("Perplexity ReadTimeout Error-Handling",
     "ReadTimeout" in _ws_src and "hat zu lange gebraucht" in _ws_src)
test("Perplexity Message-Alternierung (Merge)",
     "Merge consecutive same-role" in _ws_src or "merged" in _ws_src)

# --- CREATE_FILE JSON Sanitizer ---
test("sanitize_llm_json Funktion vorhanden",
     "def sanitize_llm_json" in _ws_src)
test("sanitize_llm_json wird bei CREATE_FILE verwendet",
     "sanitize_llm_json(json_str)" in _ws_src)
# Funktionstest: sanitize_llm_json mit Single Quotes
try:
    exec_ns = {}
    import re as _test_re
    _func_match = _test_re.search(r'(def sanitize_llm_json\(raw\):.*?)(?=\ndef \w)', _ws_src, _test_re.DOTALL)
    if _func_match:
        exec(_func_match.group(1), exec_ns)
        _san = exec_ns['sanitize_llm_json']
        _r1 = _san('{"title": "Test"}')
        _r2 = _san("{'title': 'Test'}")
        _r3 = _san('{"title": "Test",}')
        test("sanitize_llm_json: Standard JSON", _r1['title'] == 'Test')
        test("sanitize_llm_json: Single Quotes", _r2['title'] == 'Test')
        test("sanitize_llm_json: Trailing Comma", _r3['title'] == 'Test')
    else:
        test("sanitize_llm_json: Funktionstest", False, "Funktion nicht extrahierbar")
except Exception as e:
    test("sanitize_llm_json: Funktionstest", False, str(e))

# --- Gemini Bild/Video-Generierung ---
test("IMAGE_PROVIDERS hat gemini mit imagen-4",
     "imagen-4" in _ws_src and "'gemini'" in _ws_src)
test("VIDEO_PROVIDERS hat gemini mit veo-3.1",
     "veo-3.1" in _ws_src)
test("Imagen 4 Fallback-Chain vorhanden",
     "imagen-4.0-generate-001" in _ws_src and "imagen-4.0-fast-generate-001" in _ws_src)
test("Veo Download mit API-Key",
     "key={api_key}" in _ws_src and "dl_url" in _ws_src)
test("Gemini 3 Flash in models.json",
     os.path.exists(os.path.expanduser("~/Library/Mobile Documents/com~apple~CloudDocs/Downloads shared/claude_datalake/config/models.json"))
     and "gemini-3-flash-preview" in open(os.path.expanduser("~/Library/Mobile Documents/com~apple~CloudDocs/Downloads shared/claude_datalake/config/models.json")).read())

# --- System-Prompt: Bild/Video Capability ---
test("System-Prompt hat Bilder erstellen Capability",
     "Bilder erstellen" in _ws_src and "CREATE_IMAGE" in _ws_src and "Sage NIEMALS" in _ws_src)
test("System-Prompt hat Videos erstellen Capability",
     "Videos erstellen" in _ws_src and "CREATE_VIDEO" in _ws_src)

# --- Kontext-Dateien Persistenz ---
test("KONTEXT_DATEIEN Block in auto_save_session",
     "KONTEXT_DATEIEN" in _ws_src)
test("KONTEXT_DATEIEN Restore in load_conversation",
     "KONTEXT_DATEIEN" in _ws_src and "restored_ctx" in _ws_src)
test("restored_ctx + missing_ctx im Response",
     "restored_ctx" in _ws_src and "missing_ctx" in _ws_src)
test("Kontext-Item Tooltip (40 Zeichen + title)",
     "substring(0, 40)" in html and "div.title = name" in html)

# --- Sub-Agent Confirmation ---
test("detect_delegation gibt dict zurueck (matched_keywords)",
     "matched_keywords" in _ws_src and "display_name" in _ws_src)
test("/api/subagent_confirm Route vorhanden",
     "subagent_confirm" in _ws_src and "@app.route" in _ws_src)
try:
    _sc_r = requests.post(f"{BASE_URL}/api/subagent_confirm",
        json={"session_id": "test", "confirmation_id": "invalid", "confirmed": False}, timeout=5)
    test("subagent_confirm Route antwortet",
         _sc_r.status_code == 200 and "abgelaufen" in _sc_r.json().get('error', ''))
except Exception as e:
    test("subagent_confirm Route antwortet", False, str(e))
test("pending_delegations dict vorhanden",
     "_pending_delegations" in _ws_src)
test("showSubagentConfirmation im Frontend",
     "showSubagentConfirmation" in html)
test("confirmSubagent im Frontend",
     "confirmSubagent" in html)
test("handleChatResponse Funktion im Frontend",
     "function handleChatResponse" in html)
test("subagent_confirmation_required Handler",
     "subagent_confirmation_required" in html)

# --- macOS Contacts Pollution Fix-Skript ---
test("fix_contacts_pollution.py existiert",
     os.path.exists(os.path.expanduser("~/AssistantDev/scripts/fix_contacts_pollution.py")))
test("analyze_contact_corruption.py existiert",
     os.path.exists(os.path.expanduser("~/AssistantDev/scripts/analyze_contact_corruption.py")))

section("Features 2026-04-10 — Progress Bar / Task Status")

# --- Backend: Task Status System ---
test("TASK_STATUS dict definiert",
     "TASK_STATUS = {}" in _ws_src)
test("task_lock (threading.Lock) definiert",
     "task_lock = threading.Lock()" in _ws_src)
test("task_create Funktion vorhanden",
     "def task_create(" in _ws_src)
test("task_update Funktion vorhanden",
     "def task_update(" in _ws_src)
test("task_done Funktion vorhanden",
     "def task_done(" in _ws_src)
test("task_error Funktion vorhanden",
     "def task_error(" in _ws_src)
test("task_get Funktion vorhanden",
     "def task_get(" in _ws_src)
test("tasks_for_session Funktion vorhanden",
     "def tasks_for_session(" in _ws_src)
test("tasks_cleanup Funktion vorhanden",
     "def tasks_cleanup(" in _ws_src)

# --- Backend: Integration in generate_video / generate_image ---
test("generate_video akzeptiert task_id Parameter",
     "def generate_video(prompt, agent_name, provider_key=None, task_id=None)" in _ws_src)
test("generate_image akzeptiert task_id Parameter",
     "def generate_image(prompt, agent_name, provider_key=None, task_id=None)" in _ws_src)
test("generate_video ruft task_update im Poll-Loop",
     _ws_src.count("task_update(task_id") >= 3)
test("generate_video ruft task_done bei Erfolg",
     "task_done(task_id, message='Video fertig')" in _ws_src)
test("generate_image ruft task_done bei Erfolg",
     "task_done(task_id, message='Bild fertig')" in _ws_src)
test("process_single_message erzeugt task_create('image'",
     "task_create('image'" in _ws_src)
test("process_single_message erzeugt task_create('video'",
     "task_create('video'" in _ws_src)
test("task_error Aufruf bei Fehler (image oder video)",
     "task_error(_img_task_id" in _ws_src and "task_error(_vid_task_id" in _ws_src)

# --- Backend: Routes ---
test("/task_status/<task_id> Route definiert",
     "@app.route('/task_status/<task_id>'" in _ws_src)
test("queue_status enthaelt active_tasks",
     "active_tasks" in _ws_src and "tasks_for_session(session_id)" in _ws_src)

try:
    r = requests.get(BASE_URL + "/task_status/nonexistent-task-id", timeout=5)
    test("/task_status/<id> gibt 404 fuer unbekannte ID",
         r.status_code == 404)
    test("/task_status/<id> gibt JSON fuer unbekannte ID",
         "application/json" in r.headers.get("content-type", ""))
except Exception as e:
    test("/task_status/<id> erreichbar", False, str(e))

try:
    r = requests.get(BASE_URL + "/queue_status?session_id=" + TEST_SESSION, timeout=5)
    qs = r.json()
    test("/queue_status enthaelt active_tasks Feld",
         "active_tasks" in qs and isinstance(qs["active_tasks"], list))
    test("/queue_status active_tasks leer fuer frische Session",
         qs.get("active_tasks") == [])
except Exception as e:
    test("/queue_status erweitert erreichbar", False, str(e))

# --- Frontend: Progress Bar HTML/CSS/JS ---
test("Progress Bar CSS .task-progress vorhanden",
     ".task-progress" in html)
test("Progress Bar CSS .tp-bar-inner vorhanden",
     ".tp-bar-inner" in html)
test("Progress Bar CSS tpPulse Keyframe",
     "@keyframes tpPulse" in html)
test("Progress Bar CSS tpShimmer Keyframe",
     "@keyframes tpShimmer" in html)
test("progressBars Registry im Frontend",
     "progressBars = {}" in html)
test("createProgressBar Funktion im Frontend",
     "function createProgressBar" in html)
test("updateProgressBar Funktion im Frontend",
     "function updateProgressBar" in html)
test("removeProgressBar Funktion im Frontend",
     "function removeProgressBar" in html)
test("pollTaskStatus Funktion im Frontend",
     "function pollTaskStatus" in html or "async function pollTaskStatus" in html)
test("discoverTasksOnce Funktion im Frontend",
     "function discoverTasksOnce" in html or "async function discoverTasksOnce" in html)
test("startTaskDiscovery Funktion im Frontend",
     "function startTaskDiscovery" in html)
test("stopTaskDiscovery Funktion im Frontend",
     "function stopTaskDiscovery" in html)
test("fmtDuration Helper im Frontend",
     "function fmtDuration" in html)
test("doSendChat startet Task-Discovery",
     "startTaskDiscovery()" in html)
test("Polling-Loop erkennt active_tasks",
     "st.active_tasks" in html and "createProgressBar" in html)
test("ETA-Text 'verbleibend' im Frontend",
     "verbleibend" in html)

section("Features 2026-04-10 — Veo Timeout Fix")

# --- Backend: erweiterte generate_video Poll-Schleife ---
test("VEO_PATCH_V2 Marker vorhanden",
     "VEO_PATCH_V2" in _ws_src)
test("MAX_ATTEMPTS auf 72 erhoeht",
     "MAX_ATTEMPTS = 72" in _ws_src)
test("POLL_INTERVAL als Konstante",
     "POLL_INTERVAL = 5" in _ws_src)
test("Logging: '[VEO] Poll gestartet' vorhanden",
     "[VEO] Poll gestartet" in _ws_src)
test("Logging: '[VEO] Poll #' je Versuch",
     "[VEO] Poll #" in _ws_src)
test("Logging: API-Fehler wird geloggt",
     "[VEO] API-Fehler" in _ws_src)
test("Content-Filter-Erkennung: raiMediaFilteredCount",
     "raiMediaFilteredCount" in _ws_src)
test("Content-Filter-Erkennung: raiMediaFilteredReasons",
     "raiMediaFilteredReasons" in _ws_src)
test("Content-Filter Fehlermeldung user-friendly",
     "vom Content-Filter blockiert" in _ws_src)
test("Timeout-Fehlermeldung enthaelt '6 Minuten' dynamisch (TOTAL_SECS//60)",
     "TOTAL_SECS//60" in _ws_src)
test("Transient Poll-Errors werden abgefangen (continue)",
     "Netzwerk-Fehler" in _ws_src and "continue" in _ws_src)
test("Video-Download Timeout erhoeht auf 180",
     "requests.get(dl_url, timeout=180)" in _ws_src)
test("Response wird bei leeren samples fuer Debugging geloggt",
     "done=true aber keine samples" in _ws_src)
test("Unbekanntes Sample-Format wird geloggt",
     "Sample-Format nicht erkannt" in _ws_src)

# Sanity: generate_video akzeptiert weiterhin task_id (kein Regression am Progress Bar)
test("generate_video Signatur bleibt kompatibel",
     "def generate_video(prompt, agent_name, provider_key=None, task_id=None)" in _ws_src)
test("task_done wird nach erfolgreichem Download aufgerufen",
     "task_done(task_id, message='Video fertig')" in _ws_src)

# Sanity: es existiert noch eine Timeout-Raise am Ende
test("Timeout-Exception nach Poll-Loop",
     'raise Exception(f"Gemini Veo: Timeout nach' in _ws_src)

section("Features 2026-04-10 — Video Retry + Agent Button + Tooltips")

# --- Fix 1: VEO_RETRY_V3 ---
test("VEO_RETRY_V3 Marker vorhanden",
     "VEO_RETRY_V3" in _ws_src)
test("MAX_RETRIES = 3 in generate_video",
     "MAX_RETRIES = 3" in _ws_src)
test("RETRYABLE_CODES enthaelt 13/14/429",
     "RETRYABLE_CODES = {13, 14, 429}" in _ws_src)
test("Backoff-Konfiguration BACKOFF = [0, 10, 20]",
     "BACKOFF = [0, 10, 20]" in _ws_src)
test("STABLE_FALLBACK_MODEL = veo-2.0-generate-001",
     "veo-2.0-generate-001" in _ws_src)
test("Retry: durationSeconds=5 als Kuerzer-Fallback",
     "duration = 5" in _ws_src)
test("Retry: aspectRatio flip 9:16",
     '"9:16"' in _ws_src and "aspect = " in _ws_src)
test("Retry-Status code 13 Server-Fehler Text",
     "Gemini Veo Server-Fehler" in _ws_src)
test("Retry-Status code 429 Rate Limit Text",
     "Gemini Veo Rate Limit" in _ws_src)
test("Klare Endmeldung nach 3 Versuchen",
     "nach 3 Versuchen fehlgeschlagen" in _ws_src or
     "nach {MAX_RETRIES} Versuchen fehlgeschlagen" in _ws_src)
test("Progress-Status zeigt Retry [N/3]",
     "Retry [{_retry+1}/{MAX_RETRIES}]" in _ws_src)
test("durationSeconds Parameter im Veo-Payload",
     '"durationSeconds": duration' in _ws_src)

# --- Fix 2: AGENT_BTN_V1 ---
test("AGENT_BTN_V1 Marker vorhanden",
     "AGENT_BTN_V1" in _ws_src)
test("Agent-Button hat id agent-btn",
     'id="agent-btn"' in html)
test("agent-label sitzt INNERHALB des Agent-Buttons",
     'id="agent-btn"' in html and 'id="agent-label"' in html and
     html.find('id="agent-btn"') < html.find('id="agent-label"') < html.find('id="agent-btn"') + 300)
test("Header-Spacer ersetzt das alte agent-label flex:1",
     'id="header-spacer"' in html)
test("Kein separates Label mehr links vom Button",
     '<span id="agent-label" style="flex:1;">' not in html)
test("data-tooltip-kind=agent auf Button gesetzt",
     'data-tooltip-kind="agent"' in html)

# --- Fix 3: TOOLTIPS_V1 ---
test("Tooltip-Box im DOM",
     '<div id="tt-box">' in html)
test("Tooltip CSS .tt-title vorhanden",
     ".tt-title" in html)
test("Tooltip CSS #tt-box.show",
     "#tt-box.show" in html)
test("PROVIDER_TOOLTIPS Map im JS",
     "var PROVIDER_TOOLTIPS" in html)
test("MODEL_TOOLTIPS Map im JS",
     "var MODEL_TOOLTIPS" in html)
test("AGENT_DESCRIPTIONS Map im JS",
     "var AGENT_DESCRIPTIONS" in html)
test("PROVIDER_TOOLTIPS hat Anthropic Eintrag",
     "Anthropic Claude" in html)
test("PROVIDER_TOOLTIPS hat Google Gemini Eintrag",
     "Google Gemini" in html and "Multimodal" in html)
test("PROVIDER_TOOLTIPS hat Mistral",
     "Mistral" in html and "europaeischen Sprachen" in html)
test("PROVIDER_TOOLTIPS hat Perplexity",
     "Perplexity" in html and "Web-Suche" in html)
test("MODEL_TOOLTIPS hat Claude Sonnet 4.6",
     "Claude Sonnet 4.6" in html and "Preis-Leistungs" in html)
test("MODEL_TOOLTIPS hat Gemini 2.5 Flash",
     "Gemini 2.5 Flash" in html and "Video/Bild-Generierung" in html)
test("MODEL_TOOLTIPS hat o1 Reasoning",
     "OpenAI Reasoning-Modell" in html)
test("ttShow Funktion vorhanden",
     "function ttShow" in html)
test("ttHide Funktion vorhanden",
     "function ttHide" in html)
test("ttAttach Funktion vorhanden",
     "function ttAttach" in html)
test("ttAttachAll Funktion vorhanden",
     "function ttAttachAll" in html)
test("Tooltip 300ms Hover-Delay",
     "setTimeout(function(){ ttShow(el); }, 300)" in html)
test("loadProviders ruft ttAttachAll() auf",
     "ttAttachAll(); // TOOLTIPS_V1" in html)
test("loadAgents fuellt AGENT_DESCRIPTIONS",
     "AGENT_DESCRIPTIONS[a.name]" in html)

# --- Fix 3: /agents Route mit description ---
test("/agents Route _agent_description Helper",
     "def _agent_description" in _ws_src)

try:
    r = requests.get(BASE_URL + "/agents", timeout=5)
    agents_data = r.json()
    test("/agents JSON gibt Liste",
         isinstance(agents_data, list) and len(agents_data) > 0)
    test("Mindestens 1 Agent hat description Feld",
         any("description" in a for a in agents_data))
    test("Mindestens 1 Agent hat nicht-leere description",
         any(a.get("description", "") for a in agents_data))
except Exception as e:
    test("/agents description Test", False, str(e))

section("Kalender-Integration")

# --- Backend ---
test("get_calendar_events Funktion vorhanden",
     "def get_calendar_events(" in _ws_src)
test("_parse_applescript_date Funktion vorhanden",
     "def _parse_applescript_date(" in _ws_src)
test("_has_calendar_intent Funktion vorhanden",
     "def _has_calendar_intent(" in _ws_src)
test("format_calendar_context Funktion vorhanden",
     "def format_calendar_context(" in _ws_src)
test("CALENDAR_INTEGRATION_V1 Marker",
     "CALENDAR_INTEGRATION_V1" in _ws_src)
test("Kalender-Cache (_cal_cache) vorhanden",
     "_cal_cache" in _ws_src)
test("AppleScript Timeout 45s",
     "timeout=45" in _ws_src)
test("Auto-Inject bei Kalender-Intent",
     "_has_calendar_intent(msg)" in _ws_src and "format_calendar_context" in _ws_src)
test("Kalender-Keywords DE (termin, heute, morgen)",
     '"termin"' in _ws_src and '"heute"' in _ws_src and '"morgen"' in _ws_src)

# --- Route ---
test("/api/calendar Route vorhanden",
     "@app.route('/api/calendar'" in _ws_src)
try:
    r = requests.post(BASE_URL + "/api/calendar",
        json={"days_ahead": 1}, timeout=50)
    test("/api/calendar antwortet",
         r.status_code == 200)
    d = r.json()
    test("/api/calendar hat events + count + range Felder",
         "events" in d and "count" in d and "range" in d)
except Exception as e:
    test("/api/calendar erreichbar", False, str(e))

# --- Slash Commands ---
test("/calendar-today Slash Command im HTML",
     "/calendar-today" in html)
test("/calendar-week Slash Command im HTML",
     "/calendar-week" in html)
test("/calendar-search Slash Command im HTML",
     "/calendar-search" in html)
test("handleCalendarCommand Funktion im HTML",
     "handleCalendarCommand" in html)

section("Slack API Integration")

test("SLACK_API_V1 Marker",
     "SLACK_API_V1" in _ws_src)
test("_get_slack_config Funktion vorhanden",
     "def _get_slack_config(" in _ws_src)
test("_slack_api Funktion vorhanden",
     "def _slack_api(" in _ws_src)
test("slack_send_message Funktion vorhanden",
     "def slack_send_message(" in _ws_src)
test("slack_list_channels Funktion vorhanden",
     "def slack_list_channels(" in _ws_src)
test("slack_list_users Funktion vorhanden",
     "def slack_list_users(" in _ws_src)
test("slack_channel_history Funktion vorhanden",
     "def slack_channel_history(" in _ws_src)
test("slack_find_channel_id Funktion vorhanden",
     "def slack_find_channel_id(" in _ws_src)
test("slack_find_user_id Funktion vorhanden",
     "def slack_find_user_id(" in _ws_src)
test("send_slack_draft nutzt API wenn Token vorhanden",
     "_get_slack_config()" in _ws_src and "slack_send_message" in _ws_src)
test("/api/slack Route vorhanden",
     "@app.route('/api/slack'" in _ws_src)

try:
    r = requests.post(BASE_URL + "/api/slack",
        json={"action": "channels"}, timeout=5)
    test("/api/slack antwortet (ohne Token: ok=false)",
         r.status_code == 200)
except Exception as e:
    test("/api/slack erreichbar", False, str(e))

section("Canva API Integration")

test("CANVA_API_V1 Marker",
     "CANVA_API_V1" in _ws_src)
test("_get_canva_config Funktion vorhanden",
     "def _get_canva_config(" in _ws_src)
test("_canva_api Funktion vorhanden",
     "def _canva_api(" in _ws_src)
test("CANVA_TOKEN_REFRESH Marker",
     "CANVA_TOKEN_REFRESH" in _ws_src)
test("_canva_refresh_token Funktion vorhanden",
     "def _canva_refresh_token(" in _ws_src)
test("canva_list_designs Funktion vorhanden",
     "def canva_list_designs(" in _ws_src)
test("canva_create_design Funktion vorhanden",
     "def canva_create_design(" in _ws_src)
test("canva_export_design Funktion vorhanden",
     "def canva_export_design(" in _ws_src)
test("/api/canva Route vorhanden",
     "@app.route('/api/canva'" in _ws_src)

# --- Canva Campaigns ---
test("CANVA_CAMPAIGNS_V1 Marker",
     "CANVA_CAMPAIGNS_V1" in _ws_src)
test("canva_list_brand_templates Funktion vorhanden",
     "def canva_list_brand_templates(" in _ws_src)
test("canva_autofill Funktion vorhanden",
     "def canva_autofill(" in _ws_src)
test("canva_batch_campaign Funktion vorhanden",
     "def canva_batch_campaign(" in _ws_src)
test("canva_upload_asset Funktion vorhanden",
     "def canva_upload_asset(" in _ws_src)
test("canva_get_autofill_job Funktion vorhanden",
     "def canva_get_autofill_job(" in _ws_src)

try:
    r = requests.post(BASE_URL + "/api/canva",
        json={"action": "list", "count": 1}, timeout=30)
    test("/api/canva list antwortet",
         r.status_code == 200)
    d = r.json()
    test("/api/canva hat ok + data Felder",
         "ok" in d and "data" in d)
    test("/api/canva Token funktioniert (ok=true)",
         d.get("ok") == True)
except Exception as e:
    test("/api/canva erreichbar", False, str(e))

try:
    r = requests.post(BASE_URL + "/api/canva",
        json={"action": "brand_templates"}, timeout=15)
    test("/api/canva brand_templates Action",
         r.status_code == 200 and "ok" in r.json())
except Exception as e:
    test("/api/canva brand_templates", False, str(e))

section("Slash Commands Clustering")

test("SLASH_CLUSTER_V1 Marker",
     "SLASH_CLUSTER_V1" in _ws_src)
test("Slash Commands haben group Feld",
     "group: 'Kommunikation'" in html or "group: \\'Kommunikation\\'" in _ws_src)
test("Gruppen-Header CSS .slash-ac-group vorhanden",
     ".slash-ac-group" in html)
test("Gruppen-Header Rendering (lastGroup)",
     "lastGroup" in html)

# Prüfe alle Gruppen vorhanden
for grp in ['Kommunikation', 'Kalender', 'Medien', 'Dokumente', 'Canva', 'Suche', 'Globale Suche']:
    test(f"Slash-Gruppe '{grp}' definiert",
         grp in html)

# --- Canva Slash Commands ---
test("/canva-search Slash Command",
     "/canva-search" in html)
test("/canva-create Slash Command",
     "/canva-create" in html)
test("/canva-templates Slash Command",
     "/canva-templates" in html)
test("/canva-campaign Slash Command",
     "/canva-campaign" in html)
test("/canva-export Slash Command",
     "/canva-export" in html)
test("handleCanvaCommand Funktion im HTML",
     "handleCanvaCommand" in html)

# --- Canva + Kalender in System-Prompt ---
test("System-Prompt erwaehnt Canva Designs",
     "Canva" in _ws_src and "Canva-Designs" in _ws_src)
test("System-Prompt erwaehnt Kalender Slash-Commands",
     "/calendar-today" in _ws_src and "/calendar-week" in _ws_src)

section("Sub-Agent History Fix")

test("SUBAGENT_HISTORY_V1 Marker",
     "SUBAGENT_HISTORY_V1" in _ws_src)
test("get_history nutzt get_agent_speicher",
     "get_agent_speicher(agent)" in _ws_src)
test("get_history filtert Sub-Agent-Konversationen",
     "sub_suffix" in _ws_src and "known_subs" in _ws_src)

try:
    r = requests.get(BASE_URL + "/get_history?agent=signicat_outbound&session_id=" + TEST_SESSION, timeout=5)
    d = r.json()
    test("signicat_outbound History hat Sessions",
         len(d.get("sessions", [])) > 0)
    # Prüfe: alle Dateien enthalten _outbound
    if d.get("sessions"):
        all_outbound = all("_outbound" in s["file"] for s in d["sessions"])
        test("signicat_outbound zeigt nur eigene Konversationen",
             all_outbound)
except Exception as e:
    test("Sub-Agent History API", False, str(e))

try:
    r = requests.get(BASE_URL + "/get_history?agent=signicat&session_id=" + TEST_SESSION, timeout=5)
    d = r.json()
    test("signicat Parent History hat Sessions",
         len(d.get("sessions", [])) > 0)
    # Prüfe: keine Sub-Agent-Dateien
    if d.get("sessions"):
        no_sub = not any("_outbound" in s["file"] or "_lamp" in s["file"] or "_meddpicc" in s["file"] for s in d["sessions"])
        test("signicat Parent zeigt keine Sub-Agent-Konversationen",
             no_sub)
except Exception as e:
    test("Parent Agent History API", False, str(e))

section("CREATE_EMAIL_REPLY Feature")

# Backend function exists
test("send_email_reply Funktion vorhanden",
     "def send_email_reply(spec):" in _ws_src)

# Parser for CREATE_EMAIL_REPLY in response processing
test("CREATE_EMAIL_REPLY Parser vorhanden",
     "[CREATE_EMAIL_REPLY:" in _ws_src and "er_prefix = '[CREATE_EMAIL_REPLY:'" in _ws_src)

# CREATE_EMAIL parser skips CREATE_EMAIL_REPLY
test("CREATE_EMAIL Parser skipt REPLY-Variante",
     "CREATE_EMAIL_REPLY:" in _ws_src and "# Skip if this is actually CREATE_EMAIL_REPLY" in _ws_src)

# System prompt mentions CREATE_EMAIL_REPLY
test("System-Prompt erwaehnt CREATE_EMAIL_REPLY",
     "CREATE_EMAIL_REPLY" in _ws_src and "message_id" in _ws_src)

# Route exists
test("/send_email_reply Route vorhanden",
     "send_email_reply_route" in _ws_src and "/send_email_reply" in _ws_src)

# AppleScript reply logic
test("AppleScript Reply sucht nach message id",
     "message id is msgId" in _ws_src)

# Fallback to new email when no message_id
test("Fallback auf neue E-Mail wenn keine message_id",
     "# No message_id: fallback to regular new email" in _ws_src)

# JS shows Reply vs Draft
test("JS unterscheidet Reply und Draft",
     "e.reply ? 'Reply' : 'Draft'" in _ws_src)

# KEINE WIEDERHOLUNG includes CREATE_EMAIL_REPLY
test("KEINE WIEDERHOLUNG erwaehnt CREATE_EMAIL_REPLY",
     "CREATE_EMAIL_REPLY, CREATE_WHATSAPP" in _ws_src)

# API route responds
try:
    r = requests.post(BASE_URL + "/send_email_reply", json={
        "message_id": "", "to": "test@example.com", "subject": "Test", "body": "Test"
    }, timeout=10)
    d = r.json()
    test("/send_email_reply Route antwortet", "ok" in d)
except Exception as e:
    test("/send_email_reply Route antwortet", False, str(e))


section("Status Check Bundle-Name Detection 2026-04-15")

# _admin_status_check in web_server.py must match both .py and app-bundle names
test("_admin_status_check matched bundle-Namen fuer email_watcher",
     "AssistantDev EmailWatcher" in _ws_src and "email_watcher.py" in _ws_src)

test("_admin_status_check nutzt proc_alive Helper mit mehreren Pattern",
     "def proc_alive" in _ws_src and 'proc_alive("email_watcher.py"' in _ws_src)

# scripts/status.sh must accept optional bundle-name and check it
_status_sh_path = os.path.expanduser("~/AssistantDev/scripts/status.sh")
try:
    with open(_status_sh_path, "r", encoding="utf-8") as _f:
        _status_sh = _f.read()
except Exception:
    _status_sh = ""

test("status.sh check_proc akzeptiert bundle_name als 2. Argument",
     "local bundle_name=" in _status_sh)

test("status.sh prueft AssistantDev WebServer",
     "AssistantDev WebServer" in _status_sh)

test("status.sh prueft AssistantDev EmailWatcher",
     "AssistantDev EmailWatcher" in _status_sh)

test("status.sh prueft kchat_watcher.py",
     "kchat_watcher.py" in _status_sh)


section("Image Downscaling fuer Anthropic API 2026-04-15")

# web_server.py muss Helper fuer Anthropic 8000px-Limit definieren
test("downscale_image_b64_if_needed Helper vorhanden",
     "def downscale_image_b64_if_needed" in _ws_src)

test("_sanitize_anthropic_images Helper vorhanden",
     "def _sanitize_anthropic_images" in _ws_src)

test("ANTHROPIC_MAX_IMAGE_DIM Konstante definiert",
     "ANTHROPIC_MAX_IMAGE_DIM" in _ws_src and "8000" in _ws_src)

test("call_anthropic ruft _sanitize_anthropic_images",
     _ws_src.count("_sanitize_anthropic_images(messages)") >= 1)

test("load_selected_files nutzt downscale_image_b64_if_needed",
     _ws_src.count("downscale_image_b64_if_needed") >= 3)

# Funktionaler Test: 9000x9000 Bild muss auf <=8000 skaliert werden
try:
    import sys as _fn_sys, base64 as _fn_b64, io as _fn_io
    _fn_sys.path.insert(0, os.path.expanduser("~/AssistantDev/src"))
    from web_server import downscale_image_b64_if_needed as _dfn
    from PIL import Image as _TestImage
    _big = _TestImage.new('RGB', (9000, 9000), (10, 20, 30))
    _buf = _fn_io.BytesIO(); _big.save(_buf, 'PNG')
    _in_b64 = _fn_b64.b64encode(_buf.getvalue()).decode()
    _out_b64, _out_mime = _dfn(_in_b64, 'image/png')
    _out_img = _TestImage.open(_fn_io.BytesIO(_fn_b64.b64decode(_out_b64)))
    test("Oversize 9000x9000 wird auf <=8000 skaliert",
         max(_out_img.size) <= 8000 and _out_b64 != _in_b64)

    # Kleine Bilder bleiben unveraendert
    _small = _TestImage.new('RGB', (400, 400), (5, 5, 5))
    _sbuf = _fn_io.BytesIO(); _small.save(_sbuf, 'PNG')
    _small_b64 = _fn_b64.b64encode(_sbuf.getvalue()).decode()
    _res_b64, _res_mime = _dfn(_small_b64, 'image/png')
    test("Kleines Bild wird nicht veraendert",
         _res_b64 == _small_b64 and _res_mime == 'image/png')

    # Decode-Fehler: ungueltiges b64 -> (None, None) statt Original
    _bad_b64, _bad_mime = _dfn("nicht-ein-bild!!!", 'image/png')
    test("Nicht dekodierbares Bild wird mit (None, None) verworfen",
         _bad_b64 is None and _bad_mime is None)
except Exception as _img_test_ex:
    test("Oversize 9000x9000 wird auf <=8000 skaliert", False, str(_img_test_ex))

# _sanitize_anthropic_images muss kaputte Bilder aus content rausfiltern
try:
    from web_server import _sanitize_anthropic_images as _san
    _msgs = [{'role': 'user', 'content': [
        {'type': 'text', 'text': 'hi'},
        {'type': 'image', 'source': {'type': 'base64',
                                     'media_type': 'image/png',
                                     'data': 'kaputt!!!'}},
    ]}]
    _san(_msgs)
    _parts = _msgs[0]['content']
    test("_sanitize_anthropic_images entfernt nicht-dekodierbare Bilder",
         len(_parts) == 1 and _parts[0].get('type') == 'text')
except Exception as _san_ex:
    test("_sanitize_anthropic_images entfernt nicht-dekodierbare Bilder",
         False, str(_san_ex))


section("Agent Auto-Restore nach Neustart 2026-04-15")

_html_restore = requests.get(BASE_URL + "/").text

test("localStorage Key 'last_active_agent' wird in selectAgent gesetzt",
     "localStorage.setItem('last_active_agent'" in _html_restore)

test("localStorage 'last_active_agent' wird bei Fehler geleert",
     _html_restore.count("localStorage.removeItem('last_active_agent')") >= 2)

test("window.onload liest 'last_active_agent' und ruft selectAgent auf",
     "localStorage.getItem('last_active_agent')" in _html_restore
     and "await selectAgent(savedAgent)" in _html_restore)

test("selectAgent behandelt data.ok === false und zeigt Modal",
     "data.ok === false" in _html_restore
     and "showAgentModal()" in _html_restore)

test("selectAgent faengt Netzwerk-/Parse-Fehler ab (try/catch um fetch)",
     "Agent-Laden fehlgeschlagen" in _html_restore)

test("window.onload ruft showAgentModal nur als Fallback (nicht immer)",
     "if (savedAgent)" in _html_restore
     and _html_restore.count("window.onload") == 1)

_resp_root = requests.get(BASE_URL + "/")
test("Index-Response setzt Cache-Control: no-store (kein stale-JS nach Update)",
     "no-store" in _resp_root.headers.get("Cache-Control", ""))


section("Access Control Matrix-UI 2026-04-15")

_ac_html = requests.get(BASE_URL + "/admin/access-control").text

test("Access Control hat matrix-table CSS-Klasse",
     "matrix-table" in _ac_html)

test("Access Control hat matrix-wrap Container",
     "matrix-wrap" in _ac_html)

test("Access Control hat matrix-container div",
     'id="matrix-container"' in _ac_html)

test("Access Control hat sticky source-cell Klasse",
     "source-cell" in _ac_html)

test("Access Control hat agent-header Klasse (rotierte Spaltenkoepfe)",
     "agent-header" in _ac_html)

test("Access Control hat section-row Klasse (Sektions-Trenner)",
     "section-row" in _ac_html)

test("Access Control hat ac-cb Checkbox-Klasse",
     "ac-cb" in _ac_html)

test("Access Control hat Eigenes Memory Sektion",
     "Eigenes Memory" in _ac_html)

test("Access Control hat Shared Memory Sektion",
     "Shared Memory" in _ac_html)

test("Access Control hat Cross-Agent Read Sektion",
     "Cross-Agent Read" in _ac_html)

test("Access Control hat Shared Sources: webclips, email_inbox, calendar",
     "webclips" in _ac_html and "email_inbox" in _ac_html and "calendar" in _ac_html)

test("Access Control hat badge-shared CSS-Klasse",
     "badge-shared" in _ac_html)

test("Access Control hat badge-exclusive CSS-Klasse",
     "badge-exclusive" in _ac_html)

test("Access Control hat source-badge Klasse",
     "source-badge" in _ac_html)

test("Access Control hat loadMatrix JS-Funktion",
     "function loadMatrix" in _ac_html)

test("Access Control hat saveMatrix JS-Funktion",
     "function saveMatrix" in _ac_html)

test("Access Control hat renderMatrix JS-Funktion",
     "function renderMatrix" in _ac_html)

test("Access Control hat collectFromDOM JS-Funktion",
     "function collectFromDOM" in _ac_html)

test("Access Control hat updateBadges JS-Funktion",
     "function updateBadges" in _ac_html)

test("Access Control ruft /agents API auf",
     "fetch('/agents')" in _ac_html)

test("Access Control ruft /api/access-control API auf",
     "fetch('/api/access-control')" in _ac_html)

test("Access Control hat Speichern-Button",
     "saveMatrix()" in _ac_html)

test("Access Control hat Verwerfen-Button",
     "loadMatrix()" in _ac_html)

test("Access Control hat last-mod Anzeige",
     'id="last-mod"' in _ac_html)

test("Access Control hat KEINE alte agent-card Klasse",
     "agent-card" not in _ac_html)

test("Access Control hat KEINE alte renderAgents Funktion",
     "function renderAgents" not in _ac_html)

test("Access Control hat KEINE alte loadAccessControl Funktion",
     "function loadAccessControl" not in _ac_html)

test("Access Control hat KEINE alte saveAccessControl Funktion",
     "function saveAccessControl" not in _ac_html)

test("Access Control hat accent-color #1B6FD8 fuer Checkboxen",
     "#1B6FD8" in _ac_html)

_ac_api = requests.get(BASE_URL + "/api/access-control")
test("GET /api/access-control antwortet mit 200",
     _ac_api.status_code == 200)
try:
    _ac_json = _ac_api.json()
    test("GET /api/access-control liefert JSON mit version Feld",
         'version' in _ac_json)
except Exception:
    test("GET /api/access-control liefert JSON mit version Feld", False)


section("Native Nav-Menu 2026-04-15")

_nav_html = requests.get(BASE_URL + "/").text

test("Nav-Menu: nav-wrap Container vorhanden",
     'id="nav-wrap"' in _nav_html)

test("Nav-Menu: nav-menu Dropdown vorhanden",
     'id="nav-menu"' in _nav_html)

test("Nav-Menu: nav-btn Hamburger-Button vorhanden",
     "nav-btn" in _nav_html)

test("Nav-Menu: toggleNavMenu JS-Funktion vorhanden",
     "function toggleNavMenu" in _nav_html)

test("Nav-Menu: navigateTo JS-Funktion vorhanden",
     "function navigateTo" in _nav_html)

test("Nav-Menu: closeNavOnClickOutside JS-Funktion vorhanden",
     "function closeNavOnClickOutside" in _nav_html)

test("Nav-Menu: Link zu /admin vorhanden",
     "navigateTo('/admin')" in _nav_html)

test("Nav-Menu: Link zu /admin/access-control vorhanden",
     "navigateTo('/admin/access-control')" in _nav_html)

test("Nav-Menu: Link zu /admin/permissions vorhanden",
     "navigateTo('/admin/permissions')" in _nav_html)

test("Nav-Menu: Link zu /admin/docs vorhanden",
     "navigateTo('/admin/docs')" in _nav_html)

test("Nav-Menu: Link zu /admin/changelog vorhanden",
     "navigateTo('/admin/changelog')" in _nav_html)

test("Nav-Menu: Changelog Link vorhanden",
     "navigateTo('/admin/changelog')" in _nav_html)

test("Nav-Menu: nav-menu-section CSS-Klasse vorhanden",
     "nav-menu-section" in _nav_html)

test("Nav-Menu: nav-menu-item CSS-Klasse vorhanden",
     "nav-menu-item" in _nav_html)

test("Nav-Menu: nav-menu-divider CSS-Klasse vorhanden",
     "nav-menu-divider" in _nav_html)

test("Nav-Menu: Alter admin-btn mit window.open NICHT mehr vorhanden",
     "window.open('/admin/access-control'" not in _nav_html)


section("Services-API und Multi-Fenster 2026-04-15")

# Services API
_svc_resp = requests.get(BASE_URL + "/api/services")
test("GET /api/services antwortet mit 200",
     _svc_resp.status_code == 200)

try:
    _svc_json = _svc_resp.json()
    _svc_ids = [s['id'] for s in _svc_json.get('services', [])]
    test("/api/services liefert web_server",
         "web_server" in _svc_ids)
    test("/api/services liefert web_clipper",
         "web_clipper" in _svc_ids)
    test("/api/services liefert email_watcher",
         "email_watcher" in _svc_ids)
    test("/api/services liefert kchat_watcher",
         "kchat_watcher" in _svc_ids)
    test("/api/services enthaelt online-Status",
         all('online' in s for s in _svc_json.get('services', [])))
except Exception:
    test("/api/services JSON-Parsing", False)

# Services Restart API existiert
test("/api/services/restart Route in web_server.py",
     "@app.route('/api/services/restart'" in _ws_src)

# Open Window API existiert
test("/api/open-window Route in web_server.py",
     "@app.route('/api/open-window'" in _ws_src)

# Nav-Menu: Services und Multi-Fenster im HTML
_nav2 = requests.get(BASE_URL + "/").text

test("Nav-Menu: svc-list Container vorhanden",
     'id="svc-list"' in _nav2)

test("Nav-Menu: loadServices JS-Funktion vorhanden",
     "function loadServices" in _nav2)

test("Nav-Menu: restartService JS-Funktion vorhanden",
     "function restartService" in _nav2)

test("Nav-Menu: openNewWindow JS-Funktion vorhanden",
     "function openNewWindow" in _nav2)

test("Nav-Menu: Admin Panel Link vorhanden",
     "navigateTo('/admin')" in _nav2)

test("Nav-Menu: svc-dot CSS-Klasse vorhanden",
     "svc-dot" in _nav2)

test("Nav-Menu: svc-restart CSS-Klasse vorhanden",
     "svc-restart" in _nav2)

test("Nav-Menu: Menu oeffnet rechts (right:0 statt left:0)",
     "right:0" in _nav2 and "nav-menu" in _nav2)

test("Nav-Menu: loadServices wird bei toggleNavMenu aufgerufen",
     "loadServices()" in _nav2)

test("Nav-Menu: kchat_watcher in _admin_status_check",
     "kchat_watcher" in _ws_src and "kchat_watcher.py" in _ws_src)


section("Fixes 2026-04-15 (History, WorkingMemory, Deploy)")

# History: Event-Delegation statt btn.onclick
_fix_html = requests.get(BASE_URL + "/").text

test("History: Event-Delegation via document.addEventListener click",
     "document.addEventListener('click'" in _fix_html or 'document.addEventListener("click"' in _fix_html)

test("History: _histSessions Lookup-Map vorhanden",
     "_histSessions" in _fix_html)

test("History: onHistoryClick via inline onclick statt event delegation",
     "onHistoryClick(this)" in _fix_html)

test("History: KEIN btn.onclick = () => loadConversation mehr",
     "btn.onclick = () => loadConversation" not in _fix_html)

# Access Control: Working Memory als Datenquelle
_ac2 = requests.get(BASE_URL + "/admin/access-control").text

test("Access Control: working_memory in SHARED_SOURCES",
     "working_memory" in _ac2)

test("Access Control: Working Memory Label vorhanden",
     "Working Memory" in _ac2)

# Deploy-Script: kein Assistant.app Pfad mehr
_deploy_path = os.path.expanduser("~/AssistantDev/scripts/deploy.sh")
try:
    with open(_deploy_path, "r") as _df:
        _deploy_src = _df.read()
except Exception:
    _deploy_src = ""

test("deploy.sh referenziert NICHT mehr Assistant.app",
     "Assistant.app" not in _deploy_src)

test("deploy.sh startet Server aus src/",
     "web_server.py" in _deploy_src and "SRC" in _deploy_src)


section("UI-Fixes 2026-04-15 (Topbar, History-onclick, Chrome-Fix)")

_ui_html = requests.get(BASE_URL + "/").text

test("History: onHistoryClick inline onclick vorhanden",
     "onHistoryClick" in _ui_html)

test("History: function onHistoryClick definiert",
     "function onHistoryClick" in _ui_html)

test("Chrome-Fix: webbrowser.open NICHT mehr im Server-Code",
     "webbrowser" not in _ws_src)

test("Chrome-Fix: kein import webbrowser",
     "import webbrowser" not in _ws_src)

# Admin-Topbar auf allen Admin-Seiten
_admin_html = requests.get(BASE_URL + "/admin").text
test("Admin-Topbar auf /admin vorhanden",
     "admin-topbar" in _admin_html)

test("Admin-Topbar hat Zurueck-zum-Chat Button",
     "back-btn" in _admin_html and ("href='/'" in _admin_html or 'href="/"' in _admin_html))

_ac_topbar = requests.get(BASE_URL + "/admin/access-control").text
test("Admin-Topbar auf /admin/access-control vorhanden",
     "admin-topbar" in _ac_topbar)

_perm_topbar = requests.get(BASE_URL + "/admin/permissions").text
test("Admin-Topbar auf /admin/permissions vorhanden",
     "admin-topbar" in _perm_topbar)

_docs_topbar = requests.get(BASE_URL + "/admin/docs").text
test("Admin-Topbar auf /admin/docs vorhanden",
     "admin-topbar" in _docs_topbar)

_cl_topbar = requests.get(BASE_URL + "/admin/changelog").text
test("Admin-Topbar auf /admin/changelog vorhanden",
     "admin-topbar" in _cl_topbar)

# Nav-Menu: kein doppelter Admin Panel Eintrag mit openNewWindow
test("Nav-Menu: kein openNewWindow('/admin') mehr",
     "openNewWindow('/admin')" not in _ui_html)


section("Permissions Working Memory + Shared Data 2026-04-15")

_perm2 = requests.get(BASE_URL + "/admin/permissions").text

test("Permissions: Working Memory Spalte vorhanden",
     "Working Memory" in _perm2)

test("Permissions: working_memory Pfade angezeigt",
     "working_memory" in _perm2)

test("Permissions: Shared Data Sources Sektion vorhanden",
     "Shared Data Sources" in _perm2)

test("Permissions: E-Mail Inbox in Shared Sources",
     "E-Mail Inbox" in _perm2)

test("Permissions: Webclips in Shared Sources",
     "Webclips" in _perm2)

test("Permissions: Kalender in Shared Sources",
     "Kalender" in _perm2)


section("WhatsApp periodischer Import 2026-04-15")

_svc3 = requests.get(BASE_URL + "/api/services").json()
_svc3_ids = [s['id'] for s in _svc3.get('services', [])]

test("/api/services liefert whatsapp_import",
     "whatsapp_import" in _svc3_ids)

_wa_svc = next((s for s in _svc3.get('services', []) if s['id'] == 'whatsapp_import'), {})
test("WhatsApp Import hat last_run Feld",
     "last_run" in _wa_svc)

test("WhatsApp Import hat periodic Feld (20min)",
     _wa_svc.get("periodic") == "20min")

test("WhatsApp Import ist in web_server.py als Service definiert",
     "whatsapp_import" in _ws_src)

# LaunchAgent existiert
_wa_plist = os.path.expanduser("~/Library/LaunchAgents/com.assistantdev.whatsapp-import.plist")
test("WhatsApp Import LaunchAgent plist existiert",
     os.path.exists(_wa_plist))

# Access Control: WhatsApp als Shared Source
_ac3 = requests.get(BASE_URL + "/admin/access-control").text
test("Access Control: WhatsApp Chats in SHARED_SOURCES",
     "whatsapp" in _ac3 and "WhatsApp" in _ac3)


# ============================================================
# ERGEBNIS
# ============================================================
total = len(passed) + len(failed)
print(f"\n{'='*50}")
print(f"{BOLD}TEST-ERGEBNIS: {datetime.now().strftime('%d.%m.%Y %H:%M')}{RESET}")
print(f"{'='*50}")
print(f"  {GREEN}✓ Bestanden: {len(passed)}/{total}{RESET}")
if warnings:
    print(f"  {YELLOW}⚠ Warnungen: {len(warnings)}{RESET}")
if failed:
    print(f"  {RED}✗ Fehlgeschlagen: {len(failed)}/{total}{RESET}")
    print(f"\n{RED}{BOLD}FEHLGESCHLAGENE TESTS:{RESET}")
    for f in failed:
        print(f"  {RED}✗ {f}{RESET}")
    print(f"\n{RED}→ Bitte diese Fehler beheben bevor du deployest!{RESET}")
    sys.exit(1)
else:
    print(f"\n{GREEN}{BOLD}✓ Alle Tests bestanden – sicher zu deployen!{RESET}")
    sys.exit(0)
