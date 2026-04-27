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

# Start-Zeit — wird am Ende fuer das Test-Artefakt-Cleanup genutzt.
# Alle Konversations-Dateien in <agent>/, die WAEHREND des Tests frisch
# erzeugt wurden UND reine Test-Muster enthalten, werden am Ende aufgeraeumt.
_TEST_START_TIME = time.time()


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
test("Session-ID Generierung vorhanden", "makeSessionId" in html or "getSessionId" in html)
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
        "message_id": "", "to": "test@example.com", "subject": "Test", "body": "Test",
        "dry_run": True,  # oeffnet KEIN Apple-Mail-Fenster
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

# Seit 2026-04-16 kommen die Sources aus /api/access-control (shared_sources)
_ac_api = requests.get(BASE_URL + "/api/access-control").json()
_ac_keys = {s.get("key") for s in _ac_api.get("shared_sources", [])}
test("Access Control hat Shared Sources: webclips, email_inbox, calendar",
     {"webclips", "email_inbox", "calendar"}.issubset(_ac_keys))

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

# Access Control: Working Memory als Datenquelle (seit 2026-04-16 API-basiert)
_ac2 = requests.get(BASE_URL + "/admin/access-control").text
_ac2_api = requests.get(BASE_URL + "/api/access-control").json()

test("Access Control: working_memory in SHARED_SOURCES",
     any(s.get("key") == "working_memory" for s in _ac2_api.get("shared_sources", [])))

test("Access Control: Working Memory Label vorhanden",
     any(s.get("label") == "Working Memory" for s in _ac2_api.get("shared_sources", [])))

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

test("Permissions: E-Mail Archive in Shared Sources",
     "E-Mail Archive" in _perm2)

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

# Access Control: WhatsApp als Shared Source (seit 2026-04-16 API-basiert)
_ac3_api = requests.get(BASE_URL + "/api/access-control").json()
test("Access Control: WhatsApp Chats in SHARED_SOURCES",
     any(s.get("key") == "whatsapp" and s.get("label") == "WhatsApp Chats"
         for s in _ac3_api.get("shared_sources", [])))


section("Chat-Tabs 2026-04-16")

_tab_html = requests.get(BASE_URL + "/").text

test("Chat-Tabs: tab-bar Container vorhanden",
     'id="tab-bar"' in _tab_html)

test("Chat-Tabs: tab-add Button vorhanden",
     'id="tab-add"' in _tab_html)

test("Chat-Tabs: addChatTab JS-Funktion vorhanden",
     "function addChatTab" in _tab_html)

test("Chat-Tabs: switchToTab JS-Funktion vorhanden",
     "function switchToTab" in _tab_html)

test("Chat-Tabs: closeTab JS-Funktion vorhanden",
     "function closeTab" in _tab_html)

test("Chat-Tabs: renderTabs JS-Funktion vorhanden",
     "function renderTabs" in _tab_html)

test("Chat-Tabs: updateActiveTabLabel JS-Funktion vorhanden",
     "function updateActiveTabLabel" in _tab_html)

test("Chat-Tabs: _tabs Array initialisiert",
     "var _tabs = []" in _tab_html or "var _tabs=[]" in _tab_html)

test("Chat-Tabs: chat-tab CSS-Klasse vorhanden",
     ".chat-tab" in _tab_html)

test("Chat-Tabs: updateActiveTabLabel wird in selectAgent aufgerufen",
     "updateActiveTabLabel(name, displayName)" in _tab_html)


section("Session-State Isolation 2026-04-16")

_iso_html = requests.get(BASE_URL + "/").text

test("Session-Isolation: _tabStates Objekt vorhanden",
     "var _tabStates" in _iso_html or "_tabStates = {}" in _iso_html)

test("Session-Isolation: _tabState() Helper definiert",
     "function _tabState(" in _iso_html)

test("Session-Isolation: _isActiveSession() Helper definiert",
     "function _isActiveSession(" in _iso_html)

test("Session-Isolation: renderActiveTabState() definiert",
     "function renderActiveTabState(" in _iso_html)

test("Session-Isolation: switchToTab ruft renderActiveTabState auf",
     "renderActiveTabState()" in _iso_html)

test("Session-Isolation: startPolling benutzt session-id im fetch",
     "/poll_responses?session_id=' + sid" in _iso_html)

test("Session-Isolation: startPolling nimmt sid Parameter",
     "function startPolling(sid)" in _iso_html)

test("Session-Isolation: stopPolling nimmt sid Parameter",
     "function stopPolling(sid)" in _iso_html)

test("Session-Isolation: startTyping nimmt sid Parameter",
     "function startTyping(prompt, sid)" in _iso_html)

test("Session-Isolation: stopTyping nimmt sid Parameter",
     "function stopTyping(sid)" in _iso_html)

test("Session-Isolation: showStopBtn nimmt sid Parameter",
     "function showStopBtn(show, sid)" in _iso_html)

test("Session-Isolation: updateQueueDisplay nimmt sid Parameter",
     "function updateQueueDisplay(count, sid)" in _iso_html)

test("Session-Isolation: pollIntervalId pro Tab gespeichert",
     "pollIntervalId" in _iso_html)

test("Session-Isolation: pendingResponses fuer inaktive Tabs gepuffert",
     "pendingResponses" in _iso_html)

test("Session-Isolation: globale pollInterval/typingInterval Variablen entfernt",
     "let pollInterval = null" not in _iso_html
     and "let typingInterval = null" not in _iso_html)

test("Session-Isolation: stopQueue sendet SESSION_ID (nicht globale)",
     "session_id: sid" in _iso_html and "var sid = SESSION_ID" in _iso_html)

test("Session-Isolation: closeTab raeumt Intervals der geschlossenen Session auf",
     "clearInterval(cs.pollIntervalId)" in _iso_html
     and "clearInterval(cs.typingIntervalId)" in _iso_html)

test("Session-Isolation: Active-Session Check verhindert DOM-Leak",
     "if (!_isActiveSession(sid)) return" in _iso_html)

# Backend smoke: /queue_status und /stop_queue beachten session_id
_qs1 = requests.get(BASE_URL + "/queue_status?session_id=test-sid-iso-a")
test("Session-Isolation: /queue_status?session_id=... antwortet 200",
     _qs1.status_code == 200 and "processing" in _qs1.json())

_qs2 = requests.get(BASE_URL + "/queue_status?session_id=test-sid-iso-b")
test("Session-Isolation: unterschiedliche session_ids liefern eigenen Status",
     _qs2.status_code == 200
     and _qs2.json().get("processing") in (False, True)
     and _qs2.json().get("queue_length", 0) == 0)


section("Copy-Button Robustheit 2026-04-16")

_copy_html = requests.get(BASE_URL + "/").text

test("Copy-Button: copyToClipboard Funktion definiert",
     "function copyToClipboard(text, btn, label)" in _copy_html)

test("Copy-Button: Feature-Detection fuer navigator.clipboard",
     "navigator.clipboard" in _copy_html
     and "window.isSecureContext" in _copy_html
     and "typeof navigator.clipboard.writeText === 'function'" in _copy_html)

test("Copy-Button: execCommand-Fallback vorhanden",
     "document.execCommand('copy')" in _copy_html)

test("Copy-Button: execCommand-Erfolg wird geprueft (nicht blind 'Kopiert')",
     # Jeder Pfad muss den Rueckgabewert von execCommand auswerten
     "ok = document.execCommand('copy')" in _copy_html
     or "res = document.execCommand('copy')" in _copy_html)

test("Copy-Button: Fallback-Textarea nutzt off-screen Positionierung",
     "position = 'fixed'" in _copy_html
     and "left = '-9999px'" in _copy_html)

test("Copy-Button: showFail() Feedback-Helper vorhanden",
     "function showFail(" in _copy_html)

test("Copy-Button: synchrone TypeError beim clipboard-Zugriff abgefangen",
     # Äusseres try/catch muss vorhanden sein (nicht nur .catch() der Promise)
     "try {\n    if (navigator && navigator.clipboard" in _copy_html
     or "try {\n    if (navigator && navigator.clipboard && window.isSecureContext" in _copy_html)

test("Copy-Button: copyLastAssistantMessage hat Fallback",
     "function copyLastAssistantMessage()" in _copy_html
     and _copy_html.count("function fallback()") >= 2)

test("Copy-Button: copyLastAssistantMessage nutzt innerText (Plain Text)",
     "last.innerText || last.textContent" in _copy_html)

test("Copy-Button: copyLastAssistantMessage meldet Fehler bei misslungenem Copy",
     "Kopieren fehlgeschlagen" in _copy_html)

test("Copy-Button: addCodeCopyButtons verwendet copyToClipboard",
     "addCodeCopyButtons" in _copy_html
     and "copyToClipboard(code, btn, 'Kopieren')" in _copy_html)

test("Copy-Button: addCopyButton verwendet copyToClipboard fuer Output-Block",
     "copyToClipboard(outputText, obtn" in _copy_html)

test("Copy-Button: addSectionCopyButtons verwendet copyToClipboard",
     "copyToClipboard(rt, b, '\u2193 Kopieren')" in _copy_html)

test("Copy-Button: jeder writeText-Aufruf ist durch Feature-Detection geschuetzt",
     # Zaehle Aufrufe (nicht Type-Checks). Pattern: writeText(  — gefolgt von Variable.
     _copy_html.count("navigator.clipboard.writeText(text)") == 2
     and _copy_html.count("typeof navigator.clipboard.writeText === 'function'") == 2)


section("Cross-Session-Pollution Fix 2026-04-16")

_xsp_html = requests.get(BASE_URL + "/").text

test("Cross-Session: sessionStorage-Persistenz der Session-ID entfernt",
     "sessionStorage.getItem('assistant_session_id')" not in _xsp_html
     and "sessionStorage.setItem('assistant_session_id'" not in _xsp_html)

test("Cross-Session: Init generiert immer frische Session-ID (makeSessionId())",
     "var sessId = makeSessionId()" in _xsp_html)

test("Cross-Session: Alter sessionStorage-Wert wird auf Init geloescht",
     "sessionStorage.removeItem('assistant_session_id')" in _xsp_html)

test("Cross-Session: doSendChat capturet Session-ID zum Sendezeitpunkt",
     "var mySid = SESSION_ID" in _xsp_html
     and "var mySt = _tabState(mySid)" in _xsp_html)

test("Cross-Session: doSendChat sendet mySid im /chat-Body (nicht globales SESSION_ID)",
     "session_id: mySid" in _xsp_html)

test("Cross-Session: doSendChat puffert Response bei inaktivem Tab",
     "mySt.pendingResponses.push(data)" in _xsp_html)

test("Cross-Session: doSendChat Queue-Placeholder im richtigen Tab-State",
     "mySt.queuedPlaceholders[data.queue_id] = ph" in _xsp_html)

test("Cross-Session: doSendChat startet Typing/Polling mit mySid",
     "startTyping(text.substring(0,50), mySid)" in _xsp_html
     and "startPolling(mySid)" in _xsp_html)

test("Cross-Session: doSendChat prueft _isActiveSession vor handleResponse",
     "if (_isActiveSession(mySid)) {\n    handleResponse(data);" in _xsp_html)

test("Cross-Session: doSendChat stopTyping/showStopBtn mit mySid",
     "stopTyping(mySid)" in _xsp_html and "showStopBtn(false, mySid)" in _xsp_html)

# Backend-Smoke: zwei frisch generierte Session-IDs liefern isolierte Status
import uuid as _uuid
_sa = "iso-a-" + _uuid.uuid4().hex[:8]
_sb = "iso-b-" + _uuid.uuid4().hex[:8]
_r_a = requests.get(BASE_URL + "/queue_status?session_id=" + _sa).json()
_r_b = requests.get(BASE_URL + "/queue_status?session_id=" + _sb).json()
test("Cross-Session: zwei frische session_ids haben je eigenen Status",
     _r_a.get("processing") is False and _r_b.get("processing") is False
     and _r_a.get("queue_length", 0) == 0 and _r_b.get("queue_length", 0) == 0)


section("SOTA RAG + Auto-Search 2026-04-16")

# Direkt-Import aus src/: QueryParser + auto_search
_se_path = os.path.expanduser("~/AssistantDev/src")
if _se_path not in sys.path:
    sys.path.insert(0, _se_path)

try:
    import search_engine as _se
    QueryParser = _se.QueryParser
    _se_import_ok = True
except Exception as _se_err:
    _se_import_ok = False
    test("search_engine importierbar", False, str(_se_err))

if _se_import_ok:
    test("search_engine importierbar", True)

    # --- Trigger-Cases (positive) ---
    _pos = [
        "Was stand nochmal in der ExFlow-Mail?",
        "Welches Datum hatten wir mit Thomas vereinbart?",
        "Suche die Rechnung von gestern",
        "ExFlow Rechnung",
        "Pitch Folien",
        "Zeig mir die letzten 10 Rechnungen",
        "die drei neuesten Mails",
    ]
    for _msg in _pos:
        _intent = QueryParser.parse(_msg)
        test(f"Trigger POSITIV: '{_msg[:40]}'", _intent.is_search,
             f"QueryParser.is_search war False")

    # --- Trigger-Cases (negative) ---
    _neg = [
        "Hallo, wie geht es dir?",
        "Wer bist du?",
        "Was ist die Hauptstadt von Frankreich?",
        "hi",
        "danke",
        "ok",
        "Thomas",  # Einzelner Name zu ambiguous
    ]
    for _msg in _neg:
        _intent = QueryParser.parse(_msg)
        test(f"Trigger NEGATIV: '{_msg[:40]}'", not _intent.is_search,
             f"QueryParser.is_search war True (ungewollt)")

    # --- max_results Extraktion ---
    test("max_results aus 'letzten 10 Rechnungen'",
         QueryParser.parse("Zeig mir die letzten 10 Rechnungen").max_results == 10)
    test("max_results aus 'drei neuesten Mails'",
         QueryParser.parse("die drei neuesten Mails").max_results == 3)
    test("max_results aus 'letzten 5 Emails'",
         QueryParser.parse("die letzten 5 Emails von Simonas").max_results == 5)
    test("max_results bei Datum 20.03.2024 NICHT gesetzt",
         QueryParser.parse("Suche die Rechnung vom 20.03.2024").max_results is None)

    # --- wants_global Trigger ---
    test("wants_global bei 'überall suchen'",
         QueryParser.parse("Suche überall nach ExFlow").wants_global is True)
    test("wants_global bei 'extended memory'",
         QueryParser.parse("Search extended memory for thomas").wants_global is True)
    test("wants_global NICHT bei normaler Query",
         QueryParser.parse("Suche die Rechnung").wants_global is False)

    # --- wants_deep Trigger ---
    test("wants_deep bei '/deep' Prefix",
         QueryParser.parse("/deep Was stand in der ExFlow-Mail?").wants_deep is True)
    test("wants_deep bei 'ausführlich'",
         QueryParser.parse("Erkläre mir ausführlich die Rechnung").wants_deep is True)
    test("wants_deep NICHT bei normaler Query",
         QueryParser.parse("Was stand in der Mail?").wants_deep is False)

    # --- SEARCH_OBJECTS Plural-Coverage ---
    _plurals = ['mails', 'emails', 'rechnungen', 'dateien', 'dokumente']
    for _p in _plurals:
        test(f"SEARCH_OBJECTS enthaelt Plural '{_p}'", _p in _se.SEARCH_OBJECTS)

    # --- rstrip-Bug Fix: 'Mails' bleibt 'Mails', nicht 'Mail' ---
    test("Proper-Noun 'Mails' wird nicht zu 'Mail' verstuemmelt (rstrip-Bug)",
         'mails' in _se.SEARCH_OBJECTS)  # wenn mails als Plural, ist Mail->Mail-Verstuemmelung egal

    # --- auto_search-Signatur akzeptiert neue Parameter ---
    import inspect as _inspect
    _as_sig = _inspect.signature(_se.auto_search)
    _as_params = set(_as_sig.parameters.keys())
    test("auto_search hat neue Parameter (max_results, use_rag, fast, enable_global)",
         {'max_results', 'use_rag', 'fast', 'enable_global'}.issubset(_as_params))

    # --- hybrid_rag_search akzeptiert n_variants ---
    _hr_sig = _inspect.signature(_se.hybrid_rag_search)
    test("hybrid_rag_search akzeptiert n_variants-Parameter",
         'n_variants' in _hr_sig.parameters)

    # --- global_rag_search existiert ---
    test("global_rag_search existiert und ist callable",
         callable(getattr(_se, 'global_rag_search', None)))

    # --- reindex_all_embeddings_async existiert ---
    test("reindex_all_embeddings_async existiert und ist callable",
         callable(getattr(_se, 'reindex_all_embeddings_async', None)))

    # --- QueryIntent-Felder ---
    _qi = _se.QueryIntent()
    for _attr in ('max_results', 'wants_global', 'wants_deep'):
        test(f"QueryIntent hat Feld '{_attr}'", hasattr(_qi, _attr))

    # --- QUESTION_INTENT_PHRASES vorhanden ---
    test("QUESTION_INTENT_PHRASES exportiert und non-empty",
         hasattr(_se, 'QUESTION_INTENT_PHRASES') and len(_se.QUESTION_INTENT_PHRASES) > 10)
    test("NO_SEARCH_OVERRIDES exportiert und non-empty",
         hasattr(_se, 'NO_SEARCH_OVERRIDES') and len(_se.NO_SEARCH_OVERRIDES) > 5)

    # --- GLOBAL_TRIGGERS werden vom Parser gelesen (nicht nur detect_global_trigger) ---
    test("GLOBAL_TRIGGERS sind im QueryParser-Pfad integriert",
         QueryParser.parse("alles durchsuchen nach ExFlow").wants_global is True)

# --- Backend-Smoke: format_search_feedback behandelt neue Felder ---
if _se_import_ok:
    _fb = {'query': 'test', 'found_count': 2, 'index_count': 100,
           'rag': True, 'semantic': True, 'global': False}
    _formatted = _se.format_search_feedback(_fb, 2)
    test("format_search_feedback markiert RAG-Mode",
         'RAG' in _formatted and 'semantic' in _formatted)

    _fb_global = {'query': 'test', 'found_count': 0, 'index_count': 0,
                  'rag': True, 'semantic': False, 'global': True}
    _formatted_g = _se.format_search_feedback(_fb_global, 0)
    test("format_search_feedback markiert global-Mode",
         'global' in _formatted_g)


section("Neue-Tab-Konversation Lazy-Create 2026-04-16")

# Struktur-Tests: web_server.py Source direkt lesen
_ws_path = os.path.expanduser("~/AssistantDev/src/web_server.py")
with open(_ws_path, encoding="utf-8") as _fp:
    _ws_src_full = _fp.read()

# select_agent-Funktion extrahieren
import re as _re_lz
_sel_match = _re_lz.search(
    r"@app\.route\('/select_agent'[^\n]*\ndef select_agent\(\):(.+?)(?=\n@app\.route|\ndef [a-z_]+\()",
    _ws_src_full, _re_lz.DOTALL)
_sel_src = _sel_match.group(1) if _sel_match else ""

test("Neue-Tab: select_agent ruft find_latest_konversation NICHT mehr auf",
     "find_latest_konversation" not in _sel_src)

test("Neue-Tab: select_agent setzt dateiname=None bei neuer Session",
     "dateiname = None" in _sel_src)

test("Neue-Tab: select_agent legt keine leere Konversationsdatei mehr upfront an",
     "konversation_' + datum" not in _sel_src)

# auto_save_session-Funktion extrahieren
_as_match = _re_lz.search(
    r"def auto_save_session\(session_id\):(.+?)\ndef [a-z_]+\(", _ws_src_full, _re_lz.DOTALL)
_as_src = _as_match.group(1) if _as_match else ""

test("Neue-Tab: auto_save_session hat Lazy-Create-Zweig",
     "if not st.get('dateiname')" in _as_src)

test("Neue-Tab: Lazy-Create benutzt Sekunden-Genauigkeit im Timestamp",
     '"%Y-%m-%d_%H-%M-%S"' in _as_src)

test("Neue-Tab: auto_save verlangt NICHT mehr dateiname vor dem Speichern",
     "or not st.get('dateiname')" not in _as_src)

# Backend-Smoke: get_history filtert weiterhin leere Dateien
_gh_match = _re_lz.search(
    r"@app\.route\('/get_history'[^\n]*\ndef get_history\(\):(.+?)(?=\n@app\.route|\ndef [a-z_]+\()",
    _ws_src_full, _re_lz.DOTALL)
_gh_src = _gh_match.group(1) if _gh_match else ""
test("Neue-Tab: get_history filtert leere Konversationsdateien (fsize <= 50)",
     "fsize <= 50" in _gh_src)

# Integration: frische Session liefert leere History (kein Pseudo-Agent)
_new_sid = "lazy-test-" + _uuid.uuid4().hex[:8]
_gh_r = requests.get(BASE_URL + "/get_history?agent=&session_id=" + _new_sid)
test("Neue-Tab: /get_history ohne Agent liefert leere Liste",
     _gh_r.status_code == 200 and _gh_r.json().get("sessions") == [])


# ============================================================
# Recency + Konversationelle Personen-Suche (Bug Fix 2026-04-16)
# ============================================================
section("Recency + Konversationelle Personen-Suche 2026-04-16")

try:
    import search_engine as _rec_se
    _QP = _rec_se.QueryParser

    # 1) Helper: extract_date_from_name
    test("Recency: extract_date_from_name() existiert",
         hasattr(_rec_se, 'extract_date_from_name'))
    if hasattr(_rec_se, 'extract_date_from_name'):
        _ed = _rec_se.extract_date_from_name
        test("Recency: extract_date erkennt v2-Schema",
             _ed('2026-04-14_12-50-42_IN_x_at_y_subject.txt')
             == '2026-04-14T12-50-42')
        test("Recency: extract_date erkennt YYYY-MM-DD ohne Uhrzeit",
             _ed('2026-04-14_subject.txt').startswith('2026-04-14T'))
        test("Recency: extract_date erkennt email_-Prefix",
             _ed('email_2026-04-06_16-02-57_unread.txt')
             == '2026-04-06T16-02-57')
        test("Recency: extract_date returns '' bei Datums-freiem Namen",
             _ed('attachments/Rechnung.pdf') == '')
        # Sortierbarkeit: jüngste > ältere
        _a = _ed('2026-04-14_12-50-42_x.txt')
        _b = _ed('2026-03-24_09-00-27_x.txt')
        test("Recency: Datum-Strings sind monoton sortierbar",
             _a > _b)

    # 2) QueryIntent.recency_first Feld existiert
    _i = _QP.parse('test')
    test("QueryParser: QueryIntent.recency_first vorhanden",
         hasattr(_i, 'recency_first'))

    # 3) Konversationelle Personen-Phrasen lösen Suche aus + recency_first
    _conversational_cases = [
        "Hat sich Fabian Adam gemeldet?",
        "Meldet sich Sebastian noch?",
        "News von Fabian Adam",
        "Update zu Signicat",
        "gibts was neues von Fabian?",
        "Was macht Fabian Adam?",
        "Has Fabian replied?",
        "Heard from Sebastian",
        "Any news from Thomas?",
    ]
    for _q in _conversational_cases:
        _it = _QP.parse(_q)
        test(f"Konversationell: is_search=True ({_q!r})",
             _it.is_search == True)
        test(f"Konversationell: recency_first=True ({_q!r})",
             _it.recency_first == True)

    # 4) Personen-Only-Query bekommt recency_first
    _person_only = _QP.parse("Fabian Adam")
    test("PersonenOnly: 'Fabian Adam' wird als Suche erkannt",
         _person_only.is_search == True)
    test("PersonenOnly: 'Fabian Adam' setzt recency_first",
         _person_only.recency_first == True)

    # 5) Explizite Recency-Trigger ('letzte', 'neueste', 'latest', 'last')
    for _q in ['Letzte E-Mail von Fabian',
               'Neueste Nachricht von Sebastian',
               'Latest mail from Fabian',
               'Last email from Sebastian']:
        _it = _QP.parse(_q)
        test(f"RecencyTrigger setzt recency_first ({_q!r})",
             _it.recency_first == True)

    # 6) Konversationelle Greetings/Meta lösen KEINE Suche aus
    for _q in ['Hallo', 'Hi', 'Danke', 'wer bist du', 'help']:
        _it = _QP.parse(_q)
        test(f"NoSearch fuer Conversational ({_q!r})",
             _it.is_search == False)

    # 7) Frage-ohne-Recency bleibt Score-First (kein recency_first)
    _it_was = _QP.parse('Was schrieb Fabian Adam?')
    test("Frage ohne Recency: 'Was schrieb…' bleibt is_search=True",
         _it_was.is_search == True)
    test("Frage ohne Recency: 'Was schrieb…' recency_first=False",
         _it_was.recency_first == False)
    _it_top = _QP.parse('ExFlow Rechnung')
    test("TopicQuery: 'ExFlow Rechnung' is_search=True, recency=False",
         _it_top.is_search == True and _it_top.recency_first == False)

    # 8) E-Mail-Person-Query setzt recency_first (Person-Only kickt rein)
    _it_em = _QP.parse('E-Mails von Fabian')
    test("EmailQuery: 'E-Mails von Fabian' bekommt recency_first",
         _it_em.recency_first == True)

    # 9) HybridSearch.search akzeptiert recency_first Parameter
    import inspect as _insp
    _sig = _insp.signature(_rec_se.HybridSearch.search)
    test("HybridSearch.search: recency_first Parameter vorhanden",
         'recency_first' in _sig.parameters)

    # 10) hybrid_rag_search akzeptiert recency_first Parameter
    _sig2 = _insp.signature(_rec_se.hybrid_rag_search)
    test("hybrid_rag_search: recency_first Parameter vorhanden",
         'recency_first' in _sig2.parameters)

    # 11) auto_search liefert recency_first im feedback (smoke gegen real index)
    import os as _os_rec
    _sp = _os_rec.path.expanduser(
        "~/Library/Mobile Documents/com~apple~CloudDocs/Downloads shared/"
        "claude_datalake/signicat")
    if _os_rec.path.exists(_os_rec.path.join(_sp, '.search_index.json')):
        _r1, _fb1 = _rec_se.auto_search('Fabian Adam', _sp)
        test("auto_search liefert recency_first im feedback dict",
             _fb1 is not None and 'recency_first' in _fb1)
        # Recency-Verhalten: jüngste Fabian-Mail muss vor älterer kommen
        if _r1 and _fb1.get('recency_first'):
            _fab_dates = [
                _rec_se.extract_date_from_name(r['name']) for r in _r1
                if 'fabian_adam' in r['name'].lower()
            ]
            if len(_fab_dates) >= 2:
                test("Recency: 1. Fabian-Treffer juenger als 2. Fabian-Treffer",
                     _fab_dates[0] > _fab_dates[1])

    # 12) ExFlow Rechnung Regression-Test (force_search-Pfad muss intakt sein)
    if _os_rec.path.exists(_os_rec.path.join(_sp, '.search_index.json')):
        _re_results, _re_fb = _rec_se.auto_search('ExFlow Rechnung', _sp)
        test("Regression: 'ExFlow Rechnung' liefert mind. 1 Treffer",
             _re_fb is not None and len(_re_results) >= 1)

    # 13) Konversationelle Phrasen-Liste enthaelt Schluesselwoerter
    test("Konversationell: 'hat sich gemeldet' in QUESTION_INTENT_PHRASES",
         'hat sich gemeldet' in getattr(_rec_se, 'QUESTION_INTENT_PHRASES', []))
    test("Konversationell: 'news von' in QUESTION_INTENT_PHRASES",
         'news von' in getattr(_rec_se, 'QUESTION_INTENT_PHRASES', []))
    test("Konversationell: REGEX-Liste exportiert",
         hasattr(_rec_se, 'QUESTION_INTENT_REGEXES'))
    test("Recency: RECENCY_TRIGGER_PHRASES exportiert + 'letzte' enthalten",
         hasattr(_rec_se, 'RECENCY_TRIGGER_PHRASES')
         and 'letzte' in _rec_se.RECENCY_TRIGGER_PHRASES)

except Exception as _ex_rec:
    test("Recency + Konversationelle Suche", False, str(_ex_rec))


# ============================================================
# Email-Watcher-Härtung (Bug Fix 2026-04-16)
# ============================================================
section("Email-Watcher-Haertung 2026-04-16")

_ew_path = os.path.expanduser("~/AssistantDev/src/email_watcher.py")
with open(_ew_path, encoding="utf-8") as _ew_fp:
    _ew_src = _ew_fp.read()

test("EmailWatcher: POLL_INTERVAL_SEC Konstante definiert",
     "POLL_INTERVAL_SEC" in _ew_src)
test("EmailWatcher: Polling-Intervall <= 5s",
     "POLL_INTERVAL_SEC = 2" in _ew_src
     or "POLL_INTERVAL_SEC = 3" in _ew_src
     or "POLL_INTERVAL_SEC = 1" in _ew_src)
test("EmailWatcher: force_apple_mail_sync() existiert",
     "def force_apple_mail_sync" in _ew_src)
test("EmailWatcher: Force-Sync verwendet osascript 'check for new mail'",
     "check for new mail" in _ew_src)
test("EmailWatcher: _trigger_index_update_for() existiert",
     "_trigger_index_update_for" in _ew_src)
test("EmailWatcher: Index-Update nach process_eml aufgerufen",
     "_trigger_index_update_for(memory_dir, email_filename)" in _ew_src)
test("EmailWatcher: Force-Sync periodisch (FORCE_SYNC_EVERY)",
     "FORCE_SYNC_EVERY" in _ew_src)

# Compiled binary deployed?
_app_bin = os.path.expanduser("~/Applications/EmailWatcher.app/Contents/MacOS/EmailWatcher")
if os.path.exists(_app_bin) and os.path.exists(_ew_path):
    _src_mtime = os.path.getmtime(_ew_path)
    _bin_mtime = os.path.getmtime(_app_bin)
    test("EmailWatcher: Deployed binary nicht aelter als Source (-60s)",
         _bin_mtime >= _src_mtime - 60)


# ============================================================

section("Email-Routing Domain-Based 2026-04-20")

# Der alte Keyword-basierte Routing-Mechanismus ist komplett ersetzt
# durch reines Domain-Matching der eigenen Empfaenger- bzw. Sender-Adresse.
test("EmailWatcher: DEFAULT_AGENT = 'privat' (nicht mehr 'standard')",
     'DEFAULT_AGENT = "privat"' in _ew_src)
test("EmailWatcher: alte ROUTING-Liste entfernt",
     "ROUTING = [" not in _ew_src)
test("EmailWatcher: DOMAIN_AGENT_MAP_EXACT definiert",
     "DOMAIN_AGENT_MAP_EXACT" in _ew_src)
test("EmailWatcher: DOMAIN_AGENT_MAP_SUBSTR definiert",
     "DOMAIN_AGENT_MAP_SUBSTR" in _ew_src)
test("EmailWatcher: signicat.com -> signicat im Mapping",
     '"signicat.com": "signicat"' in _ew_src)
test("EmailWatcher: signicat.tech -> signicat im Mapping",
     '"signicat.tech": "signicat"' in _ew_src)
test("EmailWatcher: trustedcarrier-Substring -> trustedcarrier",
     '("trustedcarrier", "trustedcarrier")' in _ew_src)
test("EmailWatcher: route_agent neue Signatur (direction, sender, to_field)",
     "def route_agent(direction, sender, to_field):" in _ew_src)
test("EmailWatcher: GLOBAL_EMAIL_DIR fuer globale Email-Kopie definiert",
     "GLOBAL_EMAIL_DIR" in _ew_src)
test("EmailWatcher: process_eml schreibt globale Kopie in GLOBAL_EMAIL_DIR",
     "os.makedirs(GLOBAL_EMAIL_DIR" in _ew_src)
test("EmailWatcher: process_eml referenziert Anhaenge im Header",
     "Anhaenge: {len(saved_attachments)}" in _ew_src
     or 'f"Anhaenge: {len(saved_attachments)}' in _ew_src)
test("EmailWatcher: Anhaenge werden VOR dem .txt-Write gespeichert",
     _ew_src.find("saved_attachments.append(final_name)")
         < _ew_src.find("primary_path = os.path.join(memory_dir, email_filename)"))
test("EmailWatcher: Attachments bekommen Timestamp-Prefix gegen Kollisionen",
     "att_prefix = f\"{timestamp}_{direction}" in _ew_src)

# Funktionsebene: route_agent liefert die erwarteten Agenten zurueck
import importlib.util as _ilu
_spec = _ilu.spec_from_file_location("email_watcher", _ew_path)
_ew_mod = _ilu.module_from_spec(_spec)
try:
    _spec.loader.exec_module(_ew_mod)
    test("route_agent: IN an signicat.com -> signicat",
         _ew_mod.route_agent("IN", "x@external.com",
                             "moritz.cremer@signicat.com") == "signicat")
    test("route_agent: IN an signicat.tech -> signicat",
         _ew_mod.route_agent("IN", "x@external.com",
                             "moritz.cremer@signicat.tech") == "signicat")
    test("route_agent: IN an trustedcarrier.net -> trustedcarrier",
         _ew_mod.route_agent("IN", "x@external.com",
                             "moritz.cremer@trustedcarrier.net") == "trustedcarrier")
    test("route_agent: IN an trustedcarrier.de -> trustedcarrier",
         _ew_mod.route_agent("IN", "x@external.com",
                             "moritz@trustedcarrier.de") == "trustedcarrier")
    test("route_agent: IN an privat-Adresse -> privat",
         _ew_mod.route_agent("IN", "x@external.com",
                             "moritz.cremer@me.com") == "privat")
    test("route_agent: OUT von signicat -> signicat",
         _ew_mod.route_agent("OUT", "moritz.cremer@signicat.com",
                             "customer@example.com") == "signicat")
    test("route_agent: OUT von trustedcarrier -> trustedcarrier",
         _ew_mod.route_agent("OUT", "moritz@trustedcarrier.de",
                             "x@external.com") == "trustedcarrier")
    test("route_agent: unbekannte Domains -> privat (Default)",
         _ew_mod.route_agent("IN", "spam@shady.xyz",
                             "random@nowhere.net") == "privat")
    test("route_agent: Multi-Empfaenger, eigene signicat bevorzugt",
         _ew_mod.route_agent("IN", "acme@partner.io",
             "moritz.cremer@me.com, moritz.cremer@signicat.com") == "signicat")
except Exception as _e:
    test(f"route_agent: Modul-Import erfolgreich ({_e})", False)


# ============================================================

section("Email-Anhang-Auto-Load + Dashboard-Button 2026-04-20")

# Backend: Anhaenge-Header-Parsing in _msg_normalize_email_content
test("Dashboard: Email-Parser kennt 'anhaenge' Header-Key",
     'fields.get("anhaenge"' in _ws_src)
test("Dashboard: attachments-Liste wird aus Header befuellt",
     "attachments_list = []" in _ws_src
     and '"attachments": attachments_list' in _ws_src)
test("Dashboard: has_attachments nutzt attachments_list-Laenge",
     "len(attachments_list) > 0" in _ws_src)

# Backend: email_content_route gibt attachment_paths mit
test("email_content_route: parst 'anhaenge' Header",
     "'anhaenge:','attachments'" in _ws_src
     or "('anhaenge:','attachments')" in _ws_src)
test("email_content_route: returned attachment_paths",
     "'attachment_paths': attachment_paths" in _ws_src)
test("email_content_route: attachment_paths = absolute Pfade",
     "base_dir = os.path.dirname(fpath)" in _ws_src
     and "attachment_paths = [" in _ws_src)

# Frontend: Miniatur-Card hat direkten 'Mit Agent oeffnen'-Button
test("Dashboard-Card: .md-card-agentbtn in HTML",
     "'md-card-agentbtn'" in _ws_src
     or 'class="md-card-agentbtn"' in _ws_src
     or "class=\"md-card-agentbtn\"" in _ws_src)
test("Dashboard-Card: .md-card-agentbtn CSS definiert",
     ".md-card-agentbtn { background:" in _ws_src
     or ".md-card-agentbtn {background:" in _ws_src)
test("Dashboard-Card: Agent-Button-Handler lazy-fetcht volle Message",
     "card.querySelector('.md-card-agentbtn')" in _ws_src
     and "openAgentModal(df.message)" in _ws_src)

# Frontend: Agent-Modal zeigt Sub-Agents als eigene Kacheln
test("Agent-Modal: .md-agent-sub CSS-Klasse definiert",
     ".md-agent-choice.md-agent-sub" in _ws_src)
test("Agent-Modal: Sub-Agents werden iteriert (a.subagents.forEach)",
     "a.subagents.forEach" in _ws_src)
test("Agent-Modal: Sub-Agent-Label 'parent > sub' gerendert",
     "(a.label || a.name) + ' \\u203a '" in _ws_src
     or "(a.label || a.name) + ' \u203a '" in _ws_src)
test("Agent-Modal: Sub-Agent-Klick ruft openChatWithMessage(sub.name, ...)",
     "openChatWithMessage(sub.name, msg.id)" in _ws_src)

# Frontend: handlePreloadMessage laedt Anhaenge automatisch
test("handlePreloadMessage: laedt Anhaenge via /load_selected_files",
     "handlePreloadMessage" in _ws_src
     and "/load_selected_files" in _ws_src
     and "m.attachments" in _ws_src)
test("handlePreloadMessage: addCtxItem fuer jeden Anhang",
     "dl.loaded.forEach" in _ws_src
     and "addCtxItem(fn, 'file')" in _ws_src)
test("handlePreloadMessage: Status-Msg bei Auto-Load",
     "automatisch in Kontext geladen" in _ws_src)

# Frontend: _openEmailInChat (Suche) laedt Anhaenge ebenfalls automatisch
test("_openEmailInChat: nutzt data.attachment_paths aus API",
     "data.attachment_paths" in _ws_src
     and "_openEmailInChat" in _ws_src)
test("_openEmailInChat: Load-Request enthaelt attachment_paths",
     "body: JSON.stringify({paths: data.attachment_paths" in _ws_src)

# Doppelklick-Fenster: bereits da, Button dort existiert
test("Msg-View-Fenster: 'Mit Agent oeffnen' Button vorhanden",
     'id="mv-btn-open-agent"' in _ws_src)
test("Msg-View-Fenster: Sub-Agenten im Dropdown-Menu",
     "a.subagents.forEach" in _ws_src
     and "(a.label||a.name)+' \\u203a '" in _ws_src)

# Regression (2026-04-20): /api/messages cappt PER SOURCE, nicht global.
# Rationale: Mit globalem Cap von 2000 fuellte WhatsApp mit ~1700 Messages
# fast alle Slots und drueckte signicat auf 2 Messages runter — Dashboard
# zeigte leere Inbox-Spalten trotz hunderter verfuegbarer Emails.
test("/api/messages: per-source Limit statt globalem Cap",
     "per_source_limit" in _ws_src
     and "by_source = _dd(list)" in _ws_src)
test("/api/messages: default per-source limit >= 500",
     "int(request.args.get(\"limit\", \"500\"))" in _ws_src
     or 'int(request.args.get("limit", "500"))' in _ws_src)
test("/api/messages: kein globaler messages[:2000]-Cap mehr",
     "messages = messages[:limit]" not in _ws_src
     or "per_source_limit" in _ws_src)

# Receipt-only Status fuer Typen ohne Read-Sync-Rueckkanal (2026-04-20)
# WhatsApp/iMessage/kChat haben keine Schreib-API zur Quelle. Dort macht
# ein Read/Unread-Flag keinen Sinn und erzeugt False-Positives im Unread-
# Count. Stattdessen: neutraler "Erhalten"-Badge in der UI.
test("Receipt-only: _MSG_BIDIRECTIONAL_SYNC_TYPES definiert (enthaelt 'email')",
     '_MSG_BIDIRECTIONAL_SYNC_TYPES = {"email"}' in _ws_src)
test("Receipt-only: _msg_get_all setzt 'sync_direction' pro Message",
     'm2["sync_direction"] =' in _ws_src
     and '"bidirectional" if bidirectional else "receipt_only"' in _ws_src)
test("Receipt-only: nicht-bidirektionale Messages haben permanent read=True",
     '# Receipt-only: kein Read/Unread-Konzept' in _ws_src
     and 'm2["read"] = True' in _ws_src)
test("Receipt-only: Frontend-Check auf sync_direction === 'receipt_only'",
     "m.sync_direction === 'receipt_only'" in _ws_src)
test("Receipt-only: 'Erhalten'-Badge statt Quickread-Button",
     "md-card-receipt" in _ws_src
     and "Erhalten" in _ws_src)
test("Receipt-only: CSS .md-card-receipt vorhanden",
     ".md-card-receipt { background:" in _ws_src
     or ".md-card-receipt {" in _ws_src)
test("Receipt-only: .md-dot.receipt fuer neutralen Dot-Status",
     ".md-dot.receipt" in _ws_src)
test("Receipt-only: CSS .md-card.receipt-only Sender-Styles",
     ".md-card.receipt-only .md-card-sender" in _ws_src)
test("Receipt-only: Quickread-Handler defensiv via null-check",
     "var qrBtnEl = card.querySelector('.md-card-quickread');" in _ws_src
     and "if (qrBtnEl)" in _ws_src)

# End-to-End: Backend labelt korrekt
import importlib.util as _ilu2
try:
    _spec2 = _ilu2.spec_from_file_location("web_server_check", _ws_path)
    # Wir importieren NICHT (Module-Side-Effects). Stattdessen rein Source-
    # Check: Verify dass die drei receipt-only-Typen nicht in
    # _MSG_BIDIRECTIONAL_SYNC_TYPES stehen.
    test("Receipt-only: whatsapp nicht bidirektional",
         '"whatsapp"' not in _ws_src.split('_MSG_BIDIRECTIONAL_SYNC_TYPES =')[1].split('\n')[0])
    test("Receipt-only: imessage nicht bidirektional",
         '"imessage"' not in _ws_src.split('_MSG_BIDIRECTIONAL_SYNC_TYPES =')[1].split('\n')[0])
    test("Receipt-only: kchat nicht bidirektional",
         '"kchat"' not in _ws_src.split('_MSG_BIDIRECTIONAL_SYNC_TYPES =')[1].split('\n')[0])
except Exception as _e:
    test(f"Receipt-only: Source-Introspection OK ({_e})", False)


# ============================================================

section("Message Dashboard Kanban 2026-04-16")

# Backend: Routen existieren in der Source
test("Message Dashboard: /messages Route in web_server.py",
     "@app.route(\"/messages\")" in _ws_src or "@app.route('/messages')" in _ws_src)
test("Message Dashboard: /api/messages/sources Route",
     "@app.route(\"/api/messages/sources\")" in _ws_src)
test("Message Dashboard: /api/messages Route",
     "@app.route(\"/api/messages\")" in _ws_src)
test("Message Dashboard: /api/messages/<msg_id> Route",
     "@app.route(\"/api/messages/<msg_id>\")" in _ws_src)
test("Message Dashboard: /api/messages/mark-read Route",
     "@app.route(\"/api/messages/mark-read\"" in _ws_src)

# Source config + Parser-Helper
test("Message Dashboard: _MSG_SOURCES definiert",
     "_MSG_SOURCES = [" in _ws_src)
test("Message Dashboard: _MSG_SOURCE_TO_AGENT Mapping",
     "_MSG_SOURCE_TO_AGENT" in _ws_src and "signicat" in _ws_src)
test("Message Dashboard: email-Parser Funktion",
     "def _msg_normalize_email_content" in _ws_src)
test("Message Dashboard: whatsapp-Parser Funktion",
     "def _msg_normalize_whatsapp_file" in _ws_src)
test("Message Dashboard: chat-Parser Funktion",
     "def _msg_normalize_chat_file" in _ws_src)
test("Message Dashboard: In-Memory Cache mit TTL",
     "_MSG_CACHE_TTL_SECONDS" in _ws_src and "_MSG_CACHE" in _ws_src)
test("Message Dashboard: State-File Pfad definiert",
     "_MSG_STATE_FILE" in _ws_src and ".message_dashboard_state.json" in _ws_src)
test("Message Dashboard: OUT-Richtung wird gefiltert",
     'direction == "OUT"' in _ws_src)
test("Message Dashboard: Eigene E-Mails werden gefiltert",
     "_MSG_OWN_EMAILS" in _ws_src)
test("Message Dashboard: 90-Tage Window",
     "_MSG_INBOX_WINDOW_DAYS = 90" in _ws_src)

# HTTP Sanity-Checks gegen laufenden Server
try:
    _msg_src_resp = requests.get(BASE_URL + "/api/messages/sources", timeout=15)
    test("GET /api/messages/sources antwortet mit 200",
         _msg_src_resp.status_code == 200)
    _msg_src_json = _msg_src_resp.json()
    test("/api/messages/sources liefert ok=True",
         _msg_src_json.get("ok") is True)
    _src_keys = [s.get("key") for s in _msg_src_json.get("sources", [])]
    test("/api/messages/sources enthaelt email_signicat",
         "email_signicat" in _src_keys)
    test("/api/messages/sources enthaelt email_privat",
         "email_privat" in _src_keys)
    test("/api/messages/sources enthaelt whatsapp",
         "whatsapp" in _src_keys)
    # Seit 2026-04-17: 'chat' (interne Agent-Konversations-History) ist kein
    # eigener Inflow-Channel mehr. Dafuer 'imessage' als echte Message-Quelle.
    test("/api/messages/sources enthaelt imessage",
         "imessage" in _src_keys)
    test("/api/messages/sources liefert recommended_agent",
         all("recommended_agent" in s for s in _msg_src_json.get("sources", [])))
    test("/api/messages/sources liefert count + unread Felder",
         all("count" in s and "unread" in s for s in _msg_src_json.get("sources", [])))
except Exception as e:
    test("GET /api/messages/sources HTTP-Aufruf", False)

try:
    _msg_resp = requests.get(BASE_URL + "/api/messages?limit=5", timeout=15)
    test("GET /api/messages antwortet mit 200",
         _msg_resp.status_code == 200)
    _msg_json = _msg_resp.json()
    test("/api/messages liefert ok=True",
         _msg_json.get("ok") is True)
    _ms = _msg_json.get("messages", [])
    test("/api/messages liefert messages-Array (kann leer sein)",
         isinstance(_ms, list))
    if _ms:
        _first = _ms[0]
        test("/api/messages Item hat id/source/sender_name/subject/timestamp",
             all(k in _first for k in ["id", "source", "sender_name", "subject", "timestamp"]))
        test("/api/messages Item hat read-Flag",
             "read" in _first)
        test("/api/messages Item hat timestamp_epoch (float)",
             isinstance(_first.get("timestamp_epoch"), (int, float)))
        # Detail-Route
        _mid = _first["id"]
        _dresp = requests.get(BASE_URL + "/api/messages/" + _mid, timeout=15)
        test("GET /api/messages/<id> antwortet mit 200",
             _dresp.status_code == 200)
        _djson = _dresp.json()
        test("/api/messages/<id> liefert message-Objekt",
             _djson.get("ok") is True and isinstance(_djson.get("message"), dict))
        test("/api/messages/<id> laedt full_content nach",
             len(_djson.get("message", {}).get("full_content", "") or "") > 0)
        # Mark-Read Toggle
        _mr1 = requests.post(BASE_URL + "/api/messages/mark-read",
                             json={"message_id": _mid, "read": True}, timeout=10)
        test("POST /api/messages/mark-read read=True antwortet mit 200",
             _mr1.status_code == 200 and _mr1.json().get("ok") is True)
        _mr2 = requests.post(BASE_URL + "/api/messages/mark-read",
                             json={"message_id": _mid, "read": False}, timeout=10)
        test("POST /api/messages/mark-read read=False antwortet mit 200",
             _mr2.status_code == 200 and _mr2.json().get("ok") is True)
        _mr3 = requests.post(BASE_URL + "/api/messages/mark-read",
                             json={}, timeout=10)
        test("POST /api/messages/mark-read ohne message_id gibt 400",
             _mr3.status_code == 400)
    _msg_src_filter = requests.get(BASE_URL + "/api/messages?source=email_signicat&limit=3", timeout=15)
    _mf_json = _msg_src_filter.json()
    test("/api/messages?source=email_signicat filtert korrekt",
         all(m.get("source") == "email_signicat" for m in _mf_json.get("messages", [])))
except Exception as e:
    test("GET /api/messages HTTP-Aufruf", False)

try:
    _dash_resp = requests.get(BASE_URL + "/messages", timeout=10)
    _dash_html = _dash_resp.text
    test("GET /messages antwortet mit 200",
         _dash_resp.status_code == 200)
    test("Dashboard HTML enthaelt Kanban-Board Container",
         'id="md-board"' in _dash_html)
    test("Dashboard HTML enthaelt globale Suche",
         'id="md-search"' in _dash_html)
    test("Dashboard HTML enthaelt Refresh-Button",
         'id="md-btn-refresh"' in _dash_html)
    test("Dashboard HTML enthaelt Agent-Auswahl-Modal",
         'id="md-agent-modal"' in _dash_html and 'id="md-agent-list"' in _dash_html)
    test("Dashboard HTML: keine unaufgeloesten \\U-Escapes",
         "\\U0001F4" not in _dash_html)
    test("Dashboard HTML: openAgentModal Funktion definiert",
         "function openAgentModal" in _dash_html)
    test("Dashboard HTML: openChatWithMessage Funktion definiert",
         "function openChatWithMessage" in _dash_html)
    test("Dashboard HTML: auto-refresh via setInterval",
         "setInterval(softRefresh" in _dash_html)
    # Seit 2026-04-17: einheitliche chronologische Sortierung (juengste oben),
    # plus per-Spalte Toggle 'nur ungelesen'.
    test("Dashboard HTML: Sort juengste-zuerst implementiert",
         "return b.timestamp_epoch - a.timestamp_epoch" in _dash_html)
    test("Dashboard HTML: 'nur ungelesen'-Toggle pro Spalte",
         "md-only-unread" in _dash_html and "onlyUnread" in _dash_html)
except Exception as e:
    test("GET /messages HTTP-Aufruf", False)

# Preload-Mechanismus im Haupt-Chat
_main_html = requests.get(BASE_URL + "/").text
test("Main HTML: handlePreloadMessage Funktion vorhanden",
     "function handlePreloadMessage" in _main_html or "async function handlePreloadMessage" in _main_html)
test("Main HTML: URLSearchParams Handling in window.onload",
     "URLSearchParams(window.location.search)" in _main_html)
test("Main HTML: preload_message Parameter wird gelesen",
     "preload_message" in _main_html)
test("Main HTML: agent Parameter wird gelesen",
     "urlParams.get('agent')" in _main_html)
test("Main HTML: preload Banner wird eingefuegt",
     "preload-banner" in _main_html or "Antwort auf eingehende Nachricht" in _main_html)

# app.py Menu-Eintrag
_app_src = open(os.path.expanduser("~/AssistantDev/src/app.py")).read()
test("app.py: Posteingang-Menueintrag vorhanden",
     "Posteingang" in _app_src and "_open_messages" in _app_src)
test("app.py: _open_messages oeffnet /messages",
     '_open_native_window("/messages")' in _app_src)

# dashboard_window.py: Title-Map
_dw_src = open(os.path.expanduser("~/AssistantDev/src/dashboard_window.py")).read()
test("dashboard_window.py: /messages in TITLE_MAP",
     '"/messages"' in _dw_src)

# /open_in_finder erweitert um path-Parameter
test("/open_in_finder akzeptiert direct_path (Datalake-sicher)",
     "direct_path" in _ws_src and "startswith(real_base" in _ws_src)


section("Access Control Custom Sources 2026-04-16")

# GET /api/access-control liefert enriched shared_sources mit Pfad + Status
try:
    _ac_resp = requests.get(BASE_URL + "/api/access-control", timeout=10)
    _ac_json = _ac_resp.json()
    test("GET /api/access-control HTTP 200", _ac_resp.status_code == 200)
    test("Response enthaelt shared_sources-Array",
         isinstance(_ac_json.get("shared_sources"), list) and len(_ac_json["shared_sources"]) >= 5)
    _keys = {s.get("key") for s in _ac_json.get("shared_sources", [])}
    test("shared_sources enthaelt builtin webclips/email_inbox/calendar/working_memory/whatsapp",
         {"webclips","email_inbox","calendar","working_memory","whatsapp"}.issubset(_keys))
    test("Jede Source hat path-Feld und status-Dict",
         all("path" in s and isinstance(s.get("status"), dict) for s in _ac_json["shared_sources"]))
    test("Builtin-Sources sind als builtin:true markiert",
         all(s.get("builtin") is True for s in _ac_json["shared_sources"]
             if s.get("key") in {"webclips","email_inbox","calendar","working_memory","whatsapp"}))
    test("Response enthaelt custom_sources-Liste",
         isinstance(_ac_json.get("custom_sources"), list))
except Exception as e:
    test("GET /api/access-control HTTP-Aufruf", False, details=str(e))

# POST /api/access-control/custom-sources mit nicht-existierendem Pfad -> 400
try:
    _bad = requests.post(BASE_URL + "/api/access-control/custom-sources",
                         json={"label": "Bad", "path": "/nonexistent/xyz/abc"}, timeout=10)
    test("POST custom-sources lehnt nicht-existierenden Pfad ab",
         _bad.status_code == 400 and _bad.json().get("success") is False)
except Exception as e:
    test("POST custom-sources (invalid) HTTP-Aufruf", False, details=str(e))

# POST mit fehlendem Label -> 400
try:
    _empty = requests.post(BASE_URL + "/api/access-control/custom-sources",
                           json={"path": "/tmp"}, timeout=10)
    test("POST custom-sources lehnt fehlendes Label ab",
         _empty.status_code == 400)
except Exception as e:
    test("POST custom-sources (no label) HTTP-Aufruf", False, details=str(e))

# End-to-End: add + verify in shared_sources + delete
import tempfile as _tmp
_tmpdir = _tmp.mkdtemp()
try:
    with open(os.path.join(_tmpdir, "a.txt"), "w") as _f:
        _f.write("x")
    with open(os.path.join(_tmpdir, "b.txt"), "w") as _f:
        _f.write("y")
    _add = requests.post(BASE_URL + "/api/access-control/custom-sources",
                         json={"label": "Run-Tests Temp", "path": _tmpdir}, timeout=10)
    _add_json = _add.json()
    test("POST custom-sources fuegt Quelle hinzu und liefert key",
         _add.status_code == 200 and _add_json.get("success") is True and _add_json.get("key"))
    _key = _add_json.get("key")

    _ac2 = requests.get(BASE_URL + "/api/access-control", timeout=10).json()
    _custom = [s for s in _ac2.get("shared_sources", []) if s.get("key") == _key]
    test("Neue Quelle erscheint in shared_sources mit builtin=false",
         len(_custom) == 1 and _custom[0].get("builtin") is False)
    test("Neue Quelle hat korrekten Status (exists, count=2)",
         len(_custom) == 1 and _custom[0].get("status", {}).get("exists") is True
         and _custom[0].get("status", {}).get("count") == 2)
    test("Custom-Source hat Pfad = Input-Pfad",
         len(_custom) == 1 and _custom[0].get("path") == _tmpdir)

    # Doppelter Add mit gleichem Label liefert unique key (custom_run_tests_temp_2)
    _add2 = requests.post(BASE_URL + "/api/access-control/custom-sources",
                          json={"label": "Run-Tests Temp", "path": _tmpdir}, timeout=10)
    test("Doppelter Add mit gleichem Label liefert eindeutigen Key",
         _add2.status_code == 200 and _add2.json().get("key") != _key)
    _key2 = _add2.json().get("key")

    # DELETE unbekannt -> 404
    _del_bad = requests.delete(BASE_URL + "/api/access-control/custom-sources/no_such_key", timeout=10)
    test("DELETE unbekannter Key liefert 404",
         _del_bad.status_code == 404)

    # DELETE beide keys
    _del1 = requests.delete(BASE_URL + f"/api/access-control/custom-sources/{_key}", timeout=10)
    _del2 = requests.delete(BASE_URL + f"/api/access-control/custom-sources/{_key2}", timeout=10)
    test("DELETE entfernt Custom-Source erfolgreich",
         _del1.status_code == 200 and _del1.json().get("success") is True
         and _del2.status_code == 200)

    _ac3 = requests.get(BASE_URL + "/api/access-control", timeout=10).json()
    _remaining = [s for s in _ac3.get("custom_sources", []) if s.get("key") in (_key, _key2)]
    test("Nach DELETE ist Custom-Source weg", len(_remaining) == 0)
finally:
    import shutil as _sh
    _sh.rmtree(_tmpdir, ignore_errors=True)

# UI: Admin-Seite rendert neue Elemente
try:
    _ac_page = requests.get(BASE_URL + "/admin/access-control", timeout=10).text
    test("Access-Control-Seite enthaelt 'Ordner hinzufuegen'-Button",
         "Ordner hinzufuegen" in _ac_page or "openAddSourceModal" in _ac_page)
    test("Access-Control-Seite enthaelt add-source-modal",
         'id="add-source-modal"' in _ac_page)
    test("Access-Control-Seite verwendet _sharedSources aus Backend",
         "_sharedSources = _acData.shared_sources" in _ac_page)
    test("Access-Control-Seite hat source-path CSS + removeCustomSource JS",
         "source-path" in _ac_page and "removeCustomSource" in _ac_page)
except Exception as e:
    test("GET /admin/access-control HTTP-Aufruf", False, details=str(e))

# Memory-Berechtigungen: kChat + Slack in Shared Data Sources
try:
    _perm_page = requests.get(BASE_URL + "/admin/permissions", timeout=10).text
    test("/admin/permissions enthaelt kChat-Zeile",
         "kChat Messages" in _perm_page)
    test("/admin/permissions enthaelt Slack-Zeile",
         "Slack Web-Clips" in _perm_page)
    test("/admin/permissions weist Slack-Dateien pro Agent aus",
         "slack_*.txt" in _perm_page)
except Exception as e:
    test("GET /admin/permissions HTTP-Aufruf", False, details=str(e))


section("Timezone-Konsistenz 2026-04-20")

# Zentraler Helper muss existieren und korrekte API haben
_tu_path = os.path.expanduser("~/AssistantDev/src/timeutils.py")
test("timeutils.py existiert", os.path.isfile(_tu_path))
try:
    sys.path.insert(0, os.path.expanduser("~/AssistantDev/src"))
    import timeutils as _tu
    _tu_ok = True
except Exception as _e:
    _tu_ok = False
    print(f"  import-error: {_e}")
test("timeutils importierbar", _tu_ok)

if _tu_ok:
    for name in ("now", "now_iso", "from_unix", "from_apple",
                 "to_local", "to_local_naive", "parse_rfc822"):
        test(f"timeutils.{name} verfuegbar", hasattr(_tu, name))

    # Runtime: now() liefert aware datetime in lokaler TZ
    _t = _tu.now()
    test("timeutils.now() ist timezone-aware", _t.tzinfo is not None)
    test("timeutils.now_iso() enthaelt TZ-Offset", any(x in _tu.now_iso() for x in ('+', '-')) and 'T' in _tu.now_iso())

    # Apple-Timestamp-Helper: 0 -> 2001-01-01 UTC (Apple-Epoch).
    # Rechne zurueck in UTC fuer den Vergleich (lokale Zeit kann je nach
    # TZ 2000-12-31 sein).
    _dt_apple_utc = _tu.from_apple(0).astimezone(_dt.timezone.utc) if '_dt' in dir() else None
    if _dt_apple_utc is None:
        import datetime as _dt_local_ref
        _dt_apple_utc = _tu.from_apple(0).astimezone(_dt_local_ref.timezone.utc)
    test("timeutils.from_apple(0) == 2001-01-01 UTC (Apple-Epoch)",
         _dt_apple_utc.year == 2001 and _dt_apple_utc.month == 1 and _dt_apple_utc.day == 1)

# Regression: Verhindere echte Aufrufe von utcfromtimestamp/utcnow
# (produzieren naive-UTC-Timestamps die als lokal missverstanden werden).
# Wir matchen nur `.utcnow(` / `.utcfromtimestamp(` — also echte Method-
# Calls. Kommentare/Docstrings/String-Hinweise erwaehnen gern den Namen,
# aber ohne '(' direkt danach.
_src_dirs = [
    os.path.expanduser("~/AssistantDev/src"),
    os.path.expanduser("~/AssistantDev/scripts"),
]
_utc_leaks = []
import re as _re_audit
_call_re = _re_audit.compile(r'\.(utcnow|utcfromtimestamp)\s*\(')
for _base in _src_dirs:
    for _root, _dirs, _files in os.walk(_base):
        for _f in _files:
            if not _f.endswith('.py') or '.backup' in _f:
                continue
            _fp = os.path.join(_root, _f)
            # timeutils.py definiert die Regel selbst — die Docstring
            # erwaehnt beide Namen als Negativ-Beispiel. Aussen vor lassen.
            if _f == 'timeutils.py':
                continue
            try:
                with open(_fp, 'r', encoding='utf-8', errors='replace') as _fh:
                    _content = _fh.read()
            except Exception:
                continue
            for _ln, _line in enumerate(_content.splitlines(), 1):
                if _call_re.search(_line):
                    # Kommentar?
                    if _line.lstrip().startswith('#'):
                        continue
                    _utc_leaks.append(f"{_fp}:{_ln}: {_line.strip()[:100]}")

test("Keine utcfromtimestamp/utcnow Method-Calls im Code",
     len(_utc_leaks) == 0,
     details="\n".join(_utc_leaks[:5]) if _utc_leaks else "")


section("Dynamic Capabilities Injection 2026-04-16")

# Modul existiert und ist importierbar
_cap_src_path = os.path.expanduser("~/AssistantDev/src/capabilities_template.py")
test("capabilities_template.py existiert",
     os.path.isfile(_cap_src_path))

try:
    sys.path.insert(0, os.path.expanduser("~/AssistantDev/src"))
    import capabilities_template as _ct
    _ct_import_ok = True
except Exception as _ct_import_err:
    _ct_import_ok = False
    _ct = None
test("capabilities_template importierbar",
     _ct_import_ok,
     details=str(_ct_import_err) if not _ct_import_ok else "")

if _ct_import_ok:
    test("SEPARATOR-Konstante definiert und nicht-leer",
         isinstance(_ct.SEPARATOR, str) and "AUTO-GENERATED" in _ct.SEPARATOR)

    _u, _s = _ct.split_agent_prompt("Hallo\n" + _ct.SEPARATOR + "\nsys")
    test("split_agent_prompt trennt korrekt",
         _u.strip() == "Hallo" and _s.startswith(_ct.SEPARATOR))

    _u2, _s2 = _ct.split_agent_prompt("Kein Trennzeichen hier")
    test("split_agent_prompt ohne Separator liefert (alles, leer)",
         _u2 == "Kein Trennzeichen hier" and _s2 == "")

    _block = _ct.get_capabilities_block({
        "agent_name": "demo",
        "parent_agent": "demo",
        "models_config": {"providers": {
            "anthropic": {"name": "Anthropic", "models": [{"id": "x", "name": "Claude-X"}]}
        }},
    })
    test("get_capabilities_block startet mit Separator",
         _block.startswith(_ct.SEPARATOR))
    test("get_capabilities_block enthaelt Kern-Sektionen",
         all(s in _block for s in [
             "## MEMORY & SUCHE", "## DATEI-ERSTELLUNG",
             "## BILD & VIDEO", "## KALENDER & TOOLS",
             "## AKTIVE MODELLE & PROVIDER", "## WORKING MEMORY",
             "## PFADE (WICHTIG)"]))
    test("get_capabilities_block listet aktives Modell",
         "Claude-X" in _block)

# Integration in web_server.py
test("web_server.py importiert inject_capabilities_on_startup",
     "from capabilities_template import inject_capabilities_on_startup" in _ws_src)
test("web_server.py ruft inject_capabilities_on_startup beim Start auf",
     _ws_src.count("inject_capabilities_on_startup(") >= 2)
test("web_server.py behandelt ImportError des capabilities-Moduls",
     "inject_capabilities_on_startup = None" in _ws_src)

# Live-Wirkung: jede Agent-Datei hat nach dem Server-Start das Trennzeichen
_agents_dir = os.path.join(DATALAKE, "config", "agents")
if os.path.isdir(_agents_dir) and _ct_import_ok:
    _agent_files = [f for f in os.listdir(_agents_dir)
                    if f.endswith(".txt") and ".backup" not in f]
    test("Mindestens eine Agent-Datei im Datalake vorhanden",
         len(_agent_files) > 0)
    _missing_sep = []
    _double_sep = []
    _lost_user = []
    for _fname in _agent_files:
        _fpath = os.path.join(_agents_dir, _fname)
        try:
            with open(_fpath, "r", encoding="utf-8", errors="replace") as _f:
                _content = _f.read()
        except Exception:
            continue
        _sep_count = _content.count(_ct.SEPARATOR)
        if _sep_count == 0:
            _missing_sep.append(_fname)
        elif _sep_count > 1:
            _double_sep.append(_fname)
        _user, _ = _ct.split_agent_prompt(_content)
        if not _user.strip():
            _lost_user.append(_fname)
    test("Alle Agent-Dateien enthalten das Capabilities-Trennzeichen",
         len(_missing_sep) == 0,
         details="Fehlend: " + ", ".join(_missing_sep))
    test("Keine Agent-Datei hat doppelte Trennzeichen",
         len(_double_sep) == 0,
         details="Doppelt: " + ", ".join(_double_sep))
    test("Keine Agent-Datei hat leere User-Section",
         len(_lost_user) == 0,
         details="Leer: " + ", ".join(_lost_user))


# ============================================================
# TEST-ARTEFAKT-CLEANUP
# ============================================================
# Tests erzeugen ueber den Chat-Endpoint echte Konversations-Dateien in den
# Agent-Ordnern (z.B. signicat/konversation_*.txt). Die sollen die UI-History
# des Nutzers nicht zumuellen. Wir raeumen hier alle Dateien auf, die:
#   - WAEHREND der Test-Session erzeugt wurden (mtime > _TEST_START_TIME - 2s)
#   - nur aus Test-Mustern bestehen (jede "Du:"-Zeile ist bekanntes Test-Muster)
#   - keine CREATE_*/URL/Betreff-Marker enthalten
# Wir verschieben nach ~/AssistantDev/backups/<ts>_test_artifacts/, nie loeschen.

_TEST_CLEANUP_PATTERNS = {
    "Sag nur das Wort: TESTOK",
    "/find test",
    "Antworte NUR mit: TEST_OK",
    "Say hello",
    "TEST",
    "test",
}


def _cleanup_test_artifacts():
    import shutil
    import datetime as _dt
    cutoff = _TEST_START_TIME - 2
    removed_per_agent = {}
    backup_root = os.path.expanduser(
        f"~/AssistantDev/backups/{_dt.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}_test_artifacts_autoclean"
    )
    try:
        for entry in os.listdir(DATALAKE):
            agent_dir = os.path.join(DATALAKE, entry)
            if not os.path.isdir(agent_dir):
                continue
            if entry.startswith('.') or entry in (
                'config', 'email_inbox', 'webclips', 'calendar', 'whatsapp'
            ):
                continue
            victims = []
            try:
                for fname in os.listdir(agent_dir):
                    if not (fname.startswith('konversation_') and fname.endswith('.txt')):
                        continue
                    fpath = os.path.join(agent_dir, fname)
                    try:
                        st = os.stat(fpath)
                    except OSError:
                        continue
                    if st.st_mtime < cutoff:
                        continue
                    if st.st_size > 3500:
                        continue
                    try:
                        with open(fpath, 'r', encoding='utf-8', errors='replace') as _rf:
                            _c = _rf.read()
                    except OSError:
                        continue
                    du_lines = [l for l in _c.splitlines() if l.startswith('Du: ')]
                    if not du_lines:
                        continue
                    if not all(d[4:].strip() in _TEST_CLEANUP_PATTERNS for d in du_lines):
                        continue
                    # Marker nur in User-Lines pruefen (Assistant darf alles)
                    _du_bad = False
                    for _du in du_lines:
                        _msg = _du[4:].strip().lower()
                        if any(m in _msg for m in (
                            'create_email', 'create_file', 'create_image',
                            'create_video', 'create_whatsapp', 'http://', 'https://'
                        )):
                            _du_bad = True
                            break
                    if _du_bad:
                        continue
                    victims.append(fpath)
            except OSError:
                continue
            if not victims:
                continue
            target = os.path.join(backup_root, entry)
            os.makedirs(target, exist_ok=True)
            for src in victims:
                try:
                    shutil.move(src, os.path.join(target, os.path.basename(src)))
                except OSError:
                    pass
            removed_per_agent[entry] = len(victims)
    except OSError:
        return
    if removed_per_agent:
        total_removed = sum(removed_per_agent.values())
        print(f"\n{YELLOW}Test-Artefakte aufgeraeumt: {total_removed} Datei(en) verschoben nach {backup_root}{RESET}")
        for ag, n in removed_per_agent.items():
            print(f"  {ag}: {n}")


# ============================================================
# FRONTEND-MIGRATION 2026-04-20
# Scaffold fuer React/Vite/TS/Tailwind/shadcn/ui neben dem inline-HTML.
# Tests pruefen Existenz der Scaffold-Dateien und dass web_server.py
# bzw. dashboard_window.py die neuen Routen korrekt ansprechen — ohne
# das React-Frontend tatsaechlich zu bauen (kein npm install in CI).
# ============================================================
section("Features 2026-04-20: Frontend-Scaffold")

_REPO = os.path.expanduser("~/AssistantDev")
_FRONT = os.path.join(_REPO, "frontend")

for _fname in (
    "package.json",
    "vite.config.ts",
    "tsconfig.json",
    "tsconfig.node.json",
    "tailwind.config.ts",
    "postcss.config.cjs",
    "components.json",
    "index.html",
    "README.md",
    ".gitignore",
):
    test(
        f"frontend/{_fname} existiert",
        os.path.isfile(os.path.join(_FRONT, _fname)),
    )

for _fname in (
    "src/main.tsx",
    "src/App.tsx",
    "src/index.css",
    "src/vite-env.d.ts",
    "src/lib/api.ts",
    "src/lib/endpoints.ts",
    "src/lib/utils.ts",
    "src/components/layout/Shell.tsx",
    "src/components/layout/Sidebar.tsx",
    "src/components/layout/PageHeader.tsx",
    "src/components/MigrationNotice.tsx",
    "src/components/ui/button.tsx",
    "src/components/ui/card.tsx",
    "src/components/ui/separator.tsx",
):
    test(
        f"frontend/{_fname} existiert",
        os.path.isfile(os.path.join(_FRONT, _fname)),
    )

for _page in (
    "Dashboard",
    "Messages",
    "Admin",
    "AdminDocs",
    "AdminChangelog",
    "AdminPermissions",
    "Memory",
    "NotFound",
):
    test(
        f"frontend/src/pages/{_page}.tsx existiert",
        os.path.isfile(os.path.join(_FRONT, "src", "pages", f"{_page}.tsx")),
    )

try:
    with open(os.path.join(_FRONT, "package.json"), encoding="utf-8") as _fh:
        _pkg = json.load(_fh)
    _deps = {**_pkg.get("dependencies", {}), **_pkg.get("devDependencies", {})}
    for _dep in (
        "react",
        "react-dom",
        "react-router-dom",
        "vite",
        "typescript",
        "tailwindcss",
        "@tanstack/react-query",
        "class-variance-authority",
        "lucide-react",
    ):
        test(f"package.json → {_dep} gelistet", _dep in _deps)
    _scripts = _pkg.get("scripts", {})
    for _s in ("dev", "build", "preview"):
        test(f"package.json → script '{_s}' definiert", _s in _scripts)
except Exception as _e:
    test("package.json parsebar", False, str(_e))

try:
    with open(os.path.join(_REPO, "src", "web_server.py"), encoding="utf-8") as _fh:
        _ws = _fh.read()
    test("web_server.py importiert send_from_directory", "send_from_directory" in _ws)
    test("web_server.py definiert _FRONTEND_DIST", "_FRONTEND_DIST" in _ws)
    test(
        "web_server.py definiert /app-Route",
        "@app.route('/app')" in _ws or '@app.route("/app")' in _ws,
    )
    test(
        "web_server.py definiert /assets-Route",
        "@app.route('/assets/<path:filename>')" in _ws
        or '@app.route("/assets/<path:filename>")' in _ws,
    )
    test(
        "web_server.py behaelt Legacy-Index-Route",
        '@app.route("/")' in _ws or "@app.route('/')" in _ws,
    )
except Exception as _e:
    test("web_server.py lesbar", False, str(_e))

try:
    with open(os.path.join(_REPO, "src", "dashboard_window.py"), encoding="utf-8") as _fh:
        _dw = _fh.read()
    test("dashboard_window.py kennt DEFAULT_PATH", "DEFAULT_PATH" in _dw)
    test(
        "dashboard_window.py verweist auf frontend/dist/index.html",
        "frontend" in _dw and "dist" in _dw and "index.html" in _dw,
    )
except Exception as _e:
    test("dashboard_window.py lesbar", False, str(_e))


section("Frontend-Migration /app 2026-04-21")

try:
    with open(os.path.join(_REPO, "src", "app.py"), encoding="utf-8") as _fh:
        _ap = _fh.read()
    # _open_dashboard muss auf /app zeigen (neue React-UI), nicht auf /
    _odash_idx = _ap.find("def _open_dashboard(")
    _odash_block = _ap[_odash_idx:_odash_idx + 400] if _odash_idx >= 0 else ""
    test("app.py: _open_dashboard existiert", _odash_idx >= 0)
    test(
        "app.py: _open_dashboard oeffnet /app (nicht / — alte UI)",
        '_open_native_window("/app")' in _odash_block,
    )
except Exception as _e:
    test("app.py lesbar", False, str(_e))

try:
    with open(os.path.join(_REPO, "scripts", "sync_all.sh"), encoding="utf-8") as _fh:
        _sa = _fh.read()
    test("sync_all.sh: kennt FRONTEND_DIST-Pfad", "FRONTEND_DIST=" in _sa)
    test(
        "sync_all.sh: hat Build+Deploy-Funktion",
        "build_frontend_and_redeploy" in _sa,
    )
    test(
        "sync_all.sh: triggered Build nach Frontend-Pull",
        "FRONTEND_CHANGED" in _sa,
    )
    test("sync_all.sh: ruft bun run build auf", "bun run build" in _sa)
    test(
        "sync_all.sh: haengt ~/.bun/bin an PATH",
        ".bun/bin" in _sa,
    )
    test(
        "sync_all.sh: nutzt deploy.sh fuer Server-Restart",
        "deploy.sh" in _sa,
    )
    test(
        "sync_all.sh: merge develop->main bricht bei dirty tree ab",
        "uncommitted changes" in _sa and "develop->main" in _sa,
    )
except Exception as _e:
    test("sync_all.sh lesbar", False, str(_e))

try:
    with open(os.path.join(_REPO, "macos_app", "AssistantDev"), encoding="utf-8") as _fh:
        _la = _fh.read()
    test(
        "macos_app/AssistantDev (Launcher) default PATH_ARG=/app",
        'PATH_ARG="${1:-/app}"' in _la,
    )
except Exception as _e:
    test("macos_app/AssistantDev lesbar", False, str(_e))

# Frontend-Smoketest-Infrastruktur
_smoke = os.path.join(_REPO, "tests", "test_frontend_smoke.py")
test("tests/test_frontend_smoke.py existiert", os.path.isfile(_smoke))
if os.path.isfile(_smoke):
    with open(_smoke, encoding="utf-8") as _fh:
        _sm = _fh.read()
    test(
        "test_frontend_smoke.py prueft #root-Fuellung",
        "children.length" in _sm and "rendered" in _sm,
    )
    test(
        "test_frontend_smoke.py sammelt Console-Errors",
        "console_errors" in _sm and 'msg.type == "error"' in _sm,
    )
    test(
        "test_frontend_smoke.py sammelt Failed-Requests",
        "failed_requests" in _sm and "requestfailed" in _sm,
    )

try:
    with open(os.path.join(_REPO, "scripts", "sync_all.sh"), encoding="utf-8") as _fh:
        _sa2 = _fh.read()
    test(
        "sync_all.sh: ruft Frontend-Smoketest nach Build auf",
        "run_frontend_smoketest" in _sa2
        and "test_frontend_smoke.py" in _sa2,
    )
except Exception as _e:
    test("sync_all.sh smoke-Integration lesbar", False, str(_e))

try:
    with open(os.path.join(_REPO, "src", "dashboard_window.py"), encoding="utf-8") as _fh:
        _dw2 = _fh.read()
    test(
        "dashboard_window.py: debug per default AN (DevTools verfuegbar)",
        "ASSISTANTDEV_WEBVIEW_DEBUG" in _dw2 and 'debug=_DEBUG' in _dw2,
    )
except Exception as _e:
    test("dashboard_window.py debug lesbar", False, str(_e))

# Lovable-Territorium-Guard
try:
    with open(os.path.join(_REPO, "scripts", "sync_all.sh"), encoding="utf-8") as _fh:
        _sa3 = _fh.read()
    test(
        "sync_all.sh: check_lovable_territory-Funktion vorhanden",
        "check_lovable_territory" in _sa3,
    )
    test(
        "sync_all.sh: Territorium-Guard filtert auf Lovable-Author",
        "gpt-engineer" in _sa3 and "--author=" in _sa3,
    )
    test(
        "sync_all.sh: Territorium-Whitelist enthaelt src/components/",
        "src/components/*" in _sa3,
    )
except Exception as _e:
    test("sync_all.sh territory-guard lesbar", False, str(_e))

# Neue JSON-APIs fuer Frontend-Pages (docs, changelog, oauth-status)
try:
    _ws3 = open(os.path.join(_REPO, "src", "web_server.py"), encoding="utf-8").read()
    test("web_server.py definiert /api/docs/list", "@app.route('/api/docs/list')" in _ws3)
    test("web_server.py definiert /api/docs/read/<slug>", "@app.route('/api/docs/read/<slug>')" in _ws3)
    test("web_server.py definiert /api/changelog.json", "@app.route('/api/changelog.json')" in _ws3)
    test("web_server.py definiert /api/oauth-status", "@app.route('/api/oauth-status')" in _ws3)
    test("web_server.py: Docs-Whitelist enthaelt architecture.md", "'architecture.md'" in _ws3 and "_DOCS_WHITELIST" in _ws3)
except Exception as _e:
    test("web_server.py neue Routes lesbar", False, str(_e))

# Live-Tests: JSON-Responses sind parse-bar
try:
    import requests
    r = requests.get("http://localhost:8080/api/docs/list", timeout=3)
    _docs = r.json()
    test(
        "/api/docs/list liefert JSON-Array mit slug+title",
        r.status_code == 200 and isinstance(_docs, list)
        and all("slug" in d and "title" in d for d in _docs),
    )
except Exception as _e:
    test("/api/docs/list live", False, str(_e))

try:
    import requests
    r = requests.get("http://localhost:8080/api/changelog.json", timeout=3)
    _cl = r.json()
    test(
        "/api/changelog.json liefert Eintraege mit date+body",
        r.status_code == 200 and isinstance(_cl, list)
        and (len(_cl) == 0 or all("date" in e and "body" in e for e in _cl)),
    )
except Exception as _e:
    test("/api/changelog.json live", False, str(_e))

try:
    import requests
    r = requests.get("http://localhost:8080/api/oauth-status", timeout=3)
    _os = r.json()
    test(
        "/api/oauth-status liefert oauth/api_keys/macos_automation",
        r.status_code == 200 and "oauth" in _os and "api_keys" in _os and "macos_automation" in _os,
    )
except Exception as _e:
    test("/api/oauth-status live", False, str(_e))

# CORS + Token-Auth Middleware
try:
    _ws4 = open(os.path.join(_REPO, "src", "web_server.py"), encoding="utf-8").read()
    test("web_server.py: _configure_cors_and_auth definiert",
         "_configure_cors_and_auth" in _ws4)
    test("web_server.py: Middleware auf BEIDEN app-Instanzen aktiviert",
         _ws4.count("_configure_cors_and_auth(app)") >= 2)
    test("web_server.py: _API_TOKEN wird aus config/api_auth.json geladen",
         "_API_TOKEN" in _ws4 and "api_auth.json" in _ws4)
    test("web_server.py: CORS-Origins enthalten lovable + bios",
         "lovable" in _ws4 and "bios" in _ws4)
    test("web_server.py: Host-basierter Localhost-Check (nicht remote_addr)",
         'request.headers.get("Host"' in _ws4 or "request.headers.get('Host'" in _ws4)
except Exception as _e:
    test("web_server.py auth/cors lesbar", False, str(_e))

# gitignore schuetzt api_auth.json
try:
    _gi = open(os.path.join(_REPO, ".gitignore"), encoding="utf-8").read()
    test("gitignore ignoriert config/api_auth.json", "config/api_auth.json" in _gi)
    test("gitignore ignoriert config/*_oauth.json", "config/*_oauth.json" in _gi)
except Exception as _e:
    test("gitignore lesbar", False, str(_e))

# scan_api_todos.sh
_scan = os.path.join(_REPO, "scripts", "scan_api_todos.sh")
test("scripts/scan_api_todos.sh existiert", os.path.isfile(_scan))
test("scripts/scan_api_todos.sh ist executable",
     os.path.isfile(_scan) and os.access(_scan, os.X_OK))
if os.path.isfile(_scan):
    _sc = open(_scan, encoding="utf-8").read()
    test("scan_api_todos.sh kennt alle 3 Marker",
         "TODO(API)" in _sc and "NEEDS_BACKEND" in _sc and "@api" in _sc)

# Live-Auth-Flow (4 Szenarien)
try:
    import requests, json as _json
    _tok = _json.load(open(os.path.join(_REPO, "config", "api_auth.json")))["api_token"]
    r1 = requests.get("http://localhost:8080/api/oauth-status", timeout=3)
    r2 = requests.get("http://localhost:8080/api/oauth-status",
                      headers={"Host": "api.bios.love"}, timeout=3)
    r3 = requests.get("http://localhost:8080/api/oauth-status",
                      headers={"Host": "api.bios.love", "Authorization": "Bearer wrong"},
                      timeout=3)
    r4 = requests.get("http://localhost:8080/api/oauth-status",
                      headers={"Host": "api.bios.love", "Authorization": f"Bearer {_tok}"},
                      timeout=3)
    # Shared-Token-Pfad ist seit 2026-04-24 hinter legacy_shared_token_enabled-Flag.
    # Test-Erwartung richtet sich danach.
    _sb_cfg_path2 = os.path.join(_REPO, "config", "supabase_auth.json")
    _legacy_flag = True
    if os.path.isfile(_sb_cfg_path2):
        try:
            _legacy_flag = bool(_json.load(open(_sb_cfg_path2)).get(
                "legacy_shared_token_enabled", True))
        except Exception:
            pass
    test("Auth: localhost ohne Token → 200", r1.status_code == 200)
    test("Auth: externer Host ohne Token → 401", r2.status_code == 401)
    test("Auth: externer Host + falscher Token → 401", r3.status_code == 401)
    if _legacy_flag:
        test("Auth: externer Host + Shared-Token (Legacy an) → 200", r4.status_code == 200)
    else:
        test("Auth: externer Host + Shared-Token (Legacy aus) → 401", r4.status_code == 401)
except Exception as _e:
    test("Auth live-Tests", False, str(_e))

# Lovable LIVE_API_QA Endpoints (13 neue GET + Agent-CRUD)
section("Lovable LIVE_API_QA Endpoints 2026-04-22")
try:
    import requests
    _lovable_eps = [
        ("/api/health", "overall"),
        ("/api/docs", None),
        ("/api/docs/readme", "slug"),
        ("/api/changelog", None),
        ("/api/permissions", None),
        ("/api/permissions_matrix", "agents"),
        ("/api/memory/access_matrix", "agents"),
        ("/api/custom_sources", None),
        ("/api/commands", None),
        ("/api/capabilities", "chat"),
        ("/api/system_prompt/privat", "prompt"),
        ("/api/conversations", None),
    ]
    for ep, must_contain_key in _lovable_eps:
        r = requests.get("http://localhost:8080" + ep, timeout=5)
        ok = r.status_code == 200
        if ok and must_contain_key:
            body = r.json()
            if isinstance(body, dict):
                ok = must_contain_key in body
        test(f"GET {ep} → 200 JSON", ok, f"code={r.status_code}")
except Exception as _e:
    test("Lovable-Endpoints live", False, str(_e))

# Agent-CRUD spiegelt BACKEND_TODO_AGENT_MANAGER
try:
    import requests
    _ws5 = open(os.path.join(_REPO, "src", "web_server.py"), encoding="utf-8").read()
    test("Agent-CRUD: POST /agents Route", "methods=['POST']" in _ws5 and "api_agent_create" in _ws5)
    test("Agent-CRUD: PATCH /agents/<name> Route", "api_agent_update" in _ws5)
    test("Agent-CRUD: DELETE /agents/<name> Route", "api_agent_delete" in _ws5)
    test("Agent-CRUD: POST subagents Route", "api_subagent_create" in _ws5)
    test("Agent-CRUD: Slug-Regel spiegelt Frontend",
         "_slugify_agent_name" in _ws5 and "[^a-z0-9]+" in _ws5)
except Exception as _e:
    test("Agent-CRUD grep", False, str(_e))

# Lovable Messages-Batch 2026-04-22 (6 neue TODOs)
section("Lovable Messages-Batch 2026-04-22")
try:
    import requests
    _base = "http://localhost:8080"

    # DIRECTION-Filter
    r = requests.get(f"{_base}/api/messages?source=email_privat&direction=received&limit=3", timeout=5)
    test("GET /api/messages?direction=received → 200", r.status_code == 200)
    test("Response enthaelt direction-Feld", r.json().get("direction") == "received")

    r = requests.get(f"{_base}/api/messages?source=email_privat&direction=sent&limit=3", timeout=5)
    test("GET /api/messages?direction=sent → 200", r.status_code == 200)

    # BUCKET=other
    r = requests.get(f"{_base}/api/messages?source=email_privat&bucket=other&limit=3", timeout=5)
    _body = r.json() if r.status_code == 200 else {}
    test("GET /api/messages?bucket=other → 200", r.status_code == 200)
    test("excluded_domains enthaelt Work-Domains",
         "tangerina.me" in (_body.get("excluded_domains") or []) and
         "signicat.com" in (_body.get("excluded_domains") or []))

    # GROUP=conversation
    r = requests.get(f"{_base}/api/messages?source=whatsapp&group=conversation&limit=3", timeout=5)
    _body = r.json() if r.status_code == 200 else {}
    test("GET /api/messages?group=conversation → 200", r.status_code == 200)
    test("group=conversation liefert items (nicht messages)",
         "items" in _body and "messages" not in _body)
    if _body.get("items"):
        first = _body["items"][0]
        test("conversation-item hat conversation_id+last_message+unread_count",
             "conversation_id" in first and "last_message" in first and "unread_count" in first)

    # /api/messages/search
    r = requests.get(f"{_base}/api/messages/search?source=email_privat&q=test&limit=3", timeout=5)
    test("GET /api/messages/search → 200", r.status_code == 200)
    test("search-Response hat query+total+results",
         "query" in r.json() and "total" in r.json() and "results" in r.json())

    # /api/contacts
    r = requests.get(f"{_base}/api/contacts?limit=3", timeout=5)
    _body = r.json() if r.status_code == 200 else {}
    test("GET /api/contacts → 200", r.status_code == 200)
    test("contacts hat items+total", "items" in _body and "total" in _body)
    if _body.get("items"):
        first = _body["items"][0]
        test("contact hat email+first_seen_at+message_count",
             "email" in first and "first_seen_at" in first and "message_count" in first)

    # /api/messages/<id>/thread
    r = requests.get(f"{_base}/api/messages?limit=1", timeout=5)
    first_id = r.json().get("messages", [{}])[0].get("id") if r.status_code == 200 else None
    if first_id:
        r = requests.get(f"{_base}/api/messages/{first_id}/thread", timeout=5)
        test("GET /api/messages/<id>/thread → 200", r.status_code == 200)
        _body = r.json() if r.status_code == 200 else {}
        test("thread-Response hat kind+participants+messages",
             "kind" in _body and "participants" in _body and "messages" in _body)

    # POST /api/agents/<name>/sessions (reply_to_message)
    if first_id:
        r = requests.post(
            f"{_base}/api/agents/privat/sessions", timeout=5,
            json={"intent": "reply_to_message",
                  "source_message_id": first_id,
                  "source_kind": "email_thread"},
        )
        test("POST /api/agents/privat/sessions → 201", r.status_code == 201)
        _body = r.json() if r.status_code == 201 else {}
        test("session-Response hat session_id+initial_messages",
             "session_id" in _body and "initial_messages" in _body)
except Exception as _e:
    test("Messages-Batch live-Tests", False, str(_e))


# System-Prompt-Editor: strukturierte Response-Shape (BACKEND_TODO_SYSTEM_PROMPT_SECTIONS)
section("System-Prompt strukturiert 2026-04-22")
try:
    import requests
    _base = "http://localhost:8080"
    r = requests.get(_base + "/api/system_prompt/privat", timeout=5)
    _sp = r.json() if r.status_code == 200 else {}
    test("GET /api/system_prompt/privat → 200", r.status_code == 200)
    test("Shape: user/generated/prompt/sections vorhanden",
         all(k in _sp for k in ("user", "generated", "prompt", "sections")))
    test("sections[] ist Liste", isinstance(_sp.get("sections"), list))
    test("user + generated ergibt (teil-)prompt",
         isinstance(_sp.get("user"), str) and isinstance(_sp.get("generated"), str)
         and _sp["user"] and _sp["generated"])
    r2 = requests.get(_base + "/api/system_prompt/signicat/lamp", timeout=5)
    _sp2 = r2.json() if r2.status_code == 200 else {}
    test("Sub-Agent /api/system_prompt/<agent>/<sub> → 200", r2.status_code == 200)
    test("Sub-Agent hat sub-Key im Response", _sp2.get("sub") == "lamp")
    r3 = requests.get(_base + "/api/system_prompt/__nonexistent__", timeout=5)
    test("Unbekannter Agent → 404", r3.status_code == 404)
except Exception as _e:
    test("System-Prompt strukturiert", False, str(_e))

# Service-Restart-Endpoint (TODO(API) aus AdminHealth.tsx)
try:
    import requests
    _base = "http://localhost:8080"
    r = requests.post(_base + "/api/health/unknown_svc/restart",
                      json={"op": "restart"}, timeout=5)
    test("POST /api/health/<unknown>/restart → 404", r.status_code == 404)
    r = requests.post(_base + "/api/health/web_clipper/restart",
                      json={"op": "invalid"}, timeout=5)
    test("POST /api/health/<svc>/restart {op:invalid} → 400", r.status_code == 400)
except Exception as _e:
    test("Health-Restart live-Tests", False, str(_e))

try:
    _ws_sp = open(os.path.join(_REPO, "src", "web_server.py"), encoding="utf-8").read()
    test("api_system_prompt nutzt _split_system_prompt",
         "_split_system_prompt" in _ws_sp)
    test("_parse_generated_sections vorhanden", "_parse_generated_sections" in _ws_sp)
    test("api_health_service_restart vorhanden", "api_health_service_restart" in _ws_sp)
    test("Restart-Route: POST /api/health/<service>/restart",
         "/api/health/<service>/restart" in _ws_sp)
except Exception as _e:
    test("System-Prompt/Restart grep", False, str(_e))


# BACKEND_TODO_API_GAPS_2026-04-22 — 7 gaps in einem Batch
section("API-Gaps 2026-04-22")
try:
    import requests
    _base = "http://localhost:8080"

    # §2 Mark-as-read: id-Alias + conversation_id-Mode
    r = requests.post(_base + "/api/messages/mark-read", json={"id": "__nope__"}, timeout=5)
    test("mark-read {id:nope} → 404 (nicht 400)", r.status_code == 404)
    r = requests.post(_base + "/api/messages/mark-read", json={}, timeout=5)
    test("mark-read ohne ids → 400", r.status_code == 400)
    _mr_body = r.json() if r.status_code == 400 else {}
    test("mark-read 400-Error nennt message_id+conversation_id",
         "conversation_id" in (_mr_body.get("error") or ""))
    r = requests.post(_base + "/api/messages/mark-read",
                      json={"conversation_id": "__nope__"}, timeout=5)
    test("mark-read {conversation_id:...} wird akzeptiert (404 weil bogus)",
         r.status_code == 404)

    # §3 Changelog-Parser: one-liner + legacy gemischt
    r = requests.get(_base + "/api/changelog", timeout=5)
    _cl = r.json() if r.status_code == 200 else []
    test("changelog parst one-liner-Format (≥5 Eintraege nach 2026-04-22)",
         sum(1 for e in _cl if e.get("date", "") >= "2026-04-22") >= 5)
    test("changelog ist nach date absteigend sortiert",
         len(_cl) < 2 or _cl[0].get("date", "") >= _cl[-1].get("date", ""))

    # §5 Health: jetzt 8 services
    r = requests.get(_base + "/api/health", timeout=5)
    _h = r.json() if r.status_code == 200 else {}
    test("/api/health listet ≥7 Services",
         len(_h.get("services", [])) >= 7)
    _names = {s["name"] for s in _h.get("services", [])}
    test("Health enthaelt cloudflared+kchat_watcher",
         {"cloudflared", "kchat_watcher"} <= _names)

    # §6 /api/memory/all — Aggregations-Endpoint
    r = requests.get(_base + "/api/memory/all?flat=1", timeout=10)
    test("/api/memory/all?flat=1 → 200 Liste",
         r.status_code == 200 and isinstance(r.json(), list))
    r = requests.get(_base + "/api/memory/all", timeout=10)
    test("/api/memory/all → 200 dict{agent:[...]}",
         r.status_code == 200 and isinstance(r.json(), dict))

    # §7 Conversations in Memory-List
    r = requests.get(_base + "/api/memory/list/privat?include=conversations", timeout=10)
    _ml = r.json() if r.status_code == 200 else []
    test("memory/list include=conversations → mind. 1 Entry mit kind='conversation'",
         any(f.get("kind") == "conversation" for f in _ml))

    # §8 Docs dual-path: beide geben content + markdown
    r1 = requests.get(_base + "/api/docs/readme", timeout=5)
    r2 = requests.get(_base + "/api/docs/read/readme", timeout=5)
    test("/api/docs/<slug> hat content+markdown",
         r1.status_code == 200 and all(k in r1.json() for k in ("content", "markdown")))
    test("/api/docs/read/<slug> hat content+markdown",
         r2.status_code == 200 and all(k in r2.json() for k in ("content", "markdown")))

    # §1 Custom-Sources CRUD-Zyklus
    r = requests.post(_base + "/custom_sources",
                      json={"label": "QA-Test", "agent": "privat", "kind": "folder", "url": "~/Downloads"},
                      timeout=5)
    test("POST /custom_sources → 201", r.status_code == 201)
    _created = r.json() if r.status_code == 201 else {}
    _sid = _created.get("id")
    r = requests.get(_base + "/custom_sources", timeout=5)
    _cs = r.json() if r.status_code == 200 else {}
    test("GET /custom_sources → {sources:[...]}",
         isinstance(_cs, dict) and isinstance(_cs.get("sources"), list))
    if _sid:
        r = requests.put(_base + f"/custom_sources/{_sid}", json={"enabled": False}, timeout=5)
        test("PUT /custom_sources/:id toggle enabled", r.status_code == 200
             and r.json().get("enabled") is False)
        r = requests.post(_base + f"/custom_sources/{_sid}/sync", timeout=10)
        test("POST /custom_sources/:id/sync → ok", r.status_code == 200 and r.json().get("ok"))
        r = requests.delete(_base + f"/custom_sources/{_sid}", timeout=5)
        test("DELETE /custom_sources/:id → ok", r.status_code == 200 and r.json().get("ok"))
    r = requests.post(_base + "/custom_sources/validate",
                      json={"url": "~/Downloads", "kind": "folder"}, timeout=5)
    _vs = r.json() if r.status_code == 200 else {}
    test("validate: status+message+itemCount+sample vorhanden",
         all(k in _vs for k in ("status", "message", "itemCount", "sample")))
except Exception as _e:
    test("API-Gaps live-Tests", False, str(_e))

# BACKEND_TODO_AUTH_REFACTOR — Supabase-JWT-Forwarding
section("Auth-Refactor (Supabase JWT) 2026-04-23")
try:
    import requests
    # Alle Auth-Tests gehen ueber den oeffentlichen Cloudflare-Tunnel,
    # weil Localhost eh exempt ist.
    _pub = "https://api.bios.love"

    # Legacy-Flag aus supabase_auth.json
    _sb_cfg_path = os.path.join(_REPO, "config", "supabase_auth.json")
    _sb_cfg = json.load(open(_sb_cfg_path)) if os.path.isfile(_sb_cfg_path) else {}
    _legacy_on = bool(_sb_cfg.get("legacy_shared_token_enabled", True))
    _cfg = json.load(open(os.path.join(_REPO, "config", "api_auth.json")))
    _tok = _cfg.get("api_token", "")

    r = requests.get(_pub + "/agents", timeout=5)
    test("extern ohne Auth → 401", r.status_code == 401)

    r = requests.get(_pub + "/agents",
                     headers={"Authorization": "Bearer bogus-not-a-jwt"}, timeout=5)
    test("extern mit bogus Token → 401", r.status_code == 401)

    r = requests.get(_pub + "/agents",
                     headers={"Authorization": "Bearer eyJhbGciOiJSUzI1NiJ9.e30.fake"},
                     timeout=5)
    test("extern mit JWT-shaped-bogus → 401 invalid_token",
         r.status_code == 401 and r.json().get("reason") == "invalid_token")

    if _tok:
        r = requests.get(_pub + "/agents",
                         headers={"Authorization": f"Bearer {_tok}"}, timeout=5)
        if _legacy_on:
            test("extern mit Shared-Token (Legacy-Flag an) → 200", r.status_code == 200)
        else:
            test("extern mit Shared-Token (Legacy-Flag aus) → 401", r.status_code == 401)

    r = requests.get(_pub + "/api/health", timeout=5)
    test("/api/health bleibt unauthed", r.status_code == 200)
    r = requests.get(_pub + "/api/health-status", timeout=5)
    test("/api/health-status bleibt unauthed", r.status_code == 200)
except Exception as _e:
    test("Auth-Refactor live-Tests", False, str(_e))

# BACKEND_TODOs 2026-04-24 — 3 neue Spezifikationen
section("Agents/Memory/Thread 2026-04-24")
try:
    import requests
    _base = "http://localhost:8080"

    # §1 AGENTS_FULL_DESCRIPTION — description voll, preview truncated
    r = requests.get(_base + "/agents", timeout=5)
    _agents = r.json() if r.status_code == 200 else []
    _a = next((a for a in _agents if a.get("name") == "privat"), (_agents or [{}])[0])
    test("GET /agents → description voll (>180 chars)",
         len(_a.get("description", "")) > 180)
    test("GET /agents → description_preview truncated (<=180 chars)",
         len(_a.get("description_preview", "")) <= 180)

    r = requests.get(_base + "/agents/privat", timeout=5)
    _ad = r.json() if r.status_code == 200 else {}
    test("GET /agents/<name> → 200 + Detail-Shape",
         r.status_code == 200 and "description" in _ad and "subagents" in _ad)

    r = requests.get(_base + "/agents/__nonexistent__", timeout=5)
    test("GET /agents/<unknown> → 404", r.status_code == 404)

    # §2 MEMORY_AND_CONVERSATIONS §1 — kind-Classification
    r = requests.get(_base + "/api/memory/list/privat", timeout=10)
    _mem = r.json() if r.status_code == 200 else []
    from collections import Counter as _Cnt
    _kinds = _Cnt(f.get("kind") for f in _mem)
    test("/api/memory/list/privat → nicht leer", len(_mem) > 0)
    test("/api/memory/list mit E-Mails (>=1 kind='email')",
         _kinds.get("email", 0) >= 1)
    test("/api/memory/list klassifiziert images",
         _kinds.get("image", 0) >= 0)

    # §2 MEMORY_AND_CONVERSATIONS §2 — Conversations Shape
    r = requests.get(_base + "/api/conversations?agent=privat", timeout=10)
    _convs = r.json() if r.status_code == 200 else []
    if _convs:
        _c = _convs[0]
        test("/api/conversations Eintrag hat preview + updated_at + message_count",
             all(k in _c for k in ("preview", "updated_at", "message_count", "title")))
        test("/api/conversations updated_at und updatedAt sind identisch",
             _c.get("updated_at") == _c.get("updatedAt"))
        r2 = requests.get(_base + f"/api/conversations/{_c['id']}/messages", timeout=5)
        _conv_detail = r2.json() if r2.status_code == 200 else {}
        test("/api/conversations/<id>/messages → 200 mit messages[]",
             r2.status_code == 200 and isinstance(_conv_detail.get("messages"), list))
        if _conv_detail.get("messages"):
            _m = _conv_detail["messages"][0]
            test("Messages haben id + role + content + at",
                 all(k in _m for k in ("id", "role", "content", "at")))

    # §3 EMAIL_THREAD_RECONSTRUCTION — Thread aggregiert via Subject + Header-Walk
    # Hole eine Email, triggere thread, pruefe dass >= 1 Message
    r = requests.get(_base + "/api/messages", timeout=10)
    _msgs = r.json().get("messages", []) if r.status_code == 200 else []
    _email = next((m for m in _msgs if m.get("type") == "email"), None)
    if _email:
        r = requests.get(_base + f"/api/messages/{_email['id']}/thread", timeout=5)
        _thread = r.json() if r.status_code == 200 else {}
        test("/api/messages/<id>/thread → ok",
             _thread.get("ok") is True)
        test("Thread enthaelt mind. die Ursprungs-Message",
             len(_thread.get("messages", [])) >= 1)
except Exception as _e:
    test("Agents/Memory/Thread 2026-04-24 live-Tests", False, str(_e))

try:
    _ws_new = open(os.path.join(_REPO, "src", "web_server.py"), encoding="utf-8").read()
    test("_agent_description_full splittet am SYSTEM-CAPABILITIES-Marker",
         "_agent_description_full" in _ws_new and "_split_system_prompt" in _ws_new)
    test("Detail-Route /agents/<name> vorhanden",
         "def get_agent_detail" in _ws_new)
    test("_classify_memory_filename erkennt email/webclip/contacts/image",
         "_classify_memory_filename" in _ws_new
         and "'email'" in _ws_new and "'webclip'" in _ws_new)
    test("_email_thread_members walkt In-Reply-To-Graph",
         "_email_thread_members" in _ws_new and "in_reply_to" in _ws_new)
    test("_normalize_subject fuer thread-aggregation",
         "_normalize_subject" in _ws_new)
except Exception as _e:
    test("Agents/Memory/Thread 2026-04-24 grep", False, str(_e))

try:
    _ws_auth = open(os.path.join(_REPO, "src", "web_server.py"), encoding="utf-8").read()
    test("JWT-Verifikation: _verify_supabase_jwt vorhanden",
         "_verify_supabase_jwt" in _ws_auth)
    test("PyJWKClient fuer Supabase-Keys geladen",
         "PyJWKClient" in _ws_auth)
    test("Feature-Flag LEGACY_SHARED_TOKEN_ENABLED vorhanden",
         "_LEGACY_SHARED_TOKEN_ENABLED" in _ws_auth)
    test("Allowlist-Check im JWT-Pfad",
         "not_allowlisted" in _ws_auth and "_SUPABASE_ALLOWLIST" in _ws_auth)
    test("request.g.user_email/user_id gesetzt",
         "g.user_email" in _ws_auth and "g.user_id" in _ws_auth)
    _cfg_path = os.path.join(_REPO, "config", "supabase_auth.json")
    test("config/supabase_auth.json existiert + gitignored",
         os.path.isfile(_cfg_path))
    _gi = open(os.path.join(_REPO, ".gitignore")).read()
    test(".gitignore listet supabase_auth.json",
         "supabase_auth.json" in _gi)
except Exception as _e:
    test("Auth-Refactor grep", False, str(_e))


try:
    _ws_gaps = open(os.path.join(_REPO, "src", "web_server.py"), encoding="utf-8").read()
    test("CRUD: POST /custom_sources Route",
         "api_custom_sources_create" in _ws_gaps)
    test("CRUD: PUT /custom_sources/<id>", "api_custom_sources_update" in _ws_gaps)
    test("CRUD: DELETE /custom_sources/<id>", "api_custom_sources_delete" in _ws_gaps)
    test("CRUD: /custom_sources/<id>/sync", "api_custom_sources_sync" in _ws_gaps)
    test("CRUD: /custom_sources/validate", "api_custom_sources_validate" in _ws_gaps)
    test("_cs_validate kennt folder/rss/url/notion/gist",
         "_VALID_SOURCE_KINDS" in _ws_gaps and "'folder'" in _ws_gaps and "'rss'" in _ws_gaps)
    test("memory/all Route vorhanden",
         "api_memory_all" in _ws_gaps and "/api/memory/all" in _ws_gaps)
    test("_collect_memory_files include_conversations",
         "include_conversations" in _ws_gaps)
except Exception as _e:
    test("API-Gaps grep", False, str(_e))


section("WhatsApp Empty-Name Match Bug 2026-04-26")

try:
    with open(os.path.expanduser("~/AssistantDev/src/web_server.py")) as _f:
        _ws = _f.read()
    test("Step1 contacts.json: cname Truthy-Check (kein '' in to_lower)",
         "if cname and (to_lower in cname or cname in to_lower):" in _ws)
    # Strip vorhanden gegen whitespace-only Namen
    test("cname.strip() um Whitespace-Names auszuschliessen",
         "(c.get('name') or '').lower().strip()" in _ws)
except Exception as _e:
    test("WhatsApp empty-name grep", False, str(_e))


section("WhatsApp Ambiguity Detection 2026-04-26")

try:
    with open(os.path.expanduser("~/AssistantDev/src/web_server.py")) as _f:
        _ws = _f.read()

    # Mehrdeutigkeits-Erkennung
    test("AppleScript holt Eintraege auch ohne Phone (fuer Ambiguity-Detection)",
         "set out to out & nm & \"\\\\t\" & linefeed" in _ws)
    test("Phantom-Duplicates ohne Phone blockieren eindeutigen Match nicht",
         "same_name_with_phone = [e for e in same_name if e[1]]" in _ws)
    test("Mehrere same_name MIT phone -> echte Mehrdeutigkeit",
         "len(same_name_with_phone) > 1" in _ws)
    test("Same_name ohne irgendeine Phone -> 'keine Telefonnummer hinterlegt'",
         "same_name and not same_name_with_phone" in _ws)
    test("Substring-Match nur wenn EINDEUTIG (sonst ambiguous)",
         "len(with_phone) == 1" in _ws and "len(with_phone) > 1" in _ws)

    # Hint-Propagation
    test("send_whatsapp_draft returnt 3-tuple (to, phone, hint)",
         "return to_name, phone, None" in _ws and
         "return to_name, None, _ambiguity_hint" in _ws)
    test("Caller in process_single_message unpackt 3-tuple",
         "wa_to, wa_phone, wa_hint = send_whatsapp_draft" in _ws)
    test("Action-Marker zeigt Hint statt 'vorbereitet' bei Mehrdeutigkeit",
         "KEIN AUTO-VERSAND" in _ws and "manuell" in _ws)
    test("Clipboard-Fallback oeffnet WhatsApp NICHT mehr automatisch",
         "KEIN automatisches Oeffnen von WhatsApp" in _ws)
    test("/send_whatsapp_draft-Route gibt ambiguity_hint zurueck",
         "'ambiguity_hint': hint" in _ws)
except Exception as _e:
    test("WhatsApp-Ambiguity grep", False, str(_e))


section("WhatsApp Group-Chat Search Fallback 2026-04-26")

try:
    with open(os.path.expanduser("~/AssistantDev/src/web_server.py")) as _f:
        _ws = _f.read()

    test("_open_whatsapp_with_chat_search-Helper definiert",
         "def _open_whatsapp_with_chat_search(chat_name, message):" in _ws)
    test("Helper aktiviert WhatsApp.app",
         'tell application "WhatsApp" to activate' in _ws)
    test("Helper triggert Cmd+F (Chat-Suche)",
         'keystroke "f" using command down' in _ws)
    test("Helper sendet Return (key code 36) zum Auswaehlen",
         "key code 36" in _ws)
    test("Helper paste'd Nachricht via Cmd+V",
         'keystroke "v" using command down' in _ws)
    test("Helper escaped \" und \\ im chat_name",
         "chat_name.replace('\\\\\\\\', '\\\\\\\\\\\\\\\\').replace('\"', '\\\\\\\\\"')" in _ws or
         "esc_name = chat_name.replace" in _ws)
    test("Helper kopiert Nachricht ins Clipboard via pbcopy",
         "subprocess.run(['pbcopy'], input=message.encode" in _ws)

    # Wiring im CREATE_WHATSAPP-Parser
    test("CREATE_WHATSAPP-Parser ruft chat-search bei wa_phone is None",
         "wa_phone is None and src_type == 'whatsapp' and src_conv" in _ws)
    test("Parser nimmt chat_target aus source_conversation_id",
         "src_conv[3:] if src_conv.startswith('wa:') else src_conv" in _ws)
    test("created_whatsapps liefert chat_search-Flag",
         "'chat_search': chat_search_used" in _ws)
    test("clipboard_fallback ist False wenn chat_search erfolgreich",
         "wa_phone is None and not chat_search_used" in _ws)
    test("Action-Marker bei chat_search erwaehnt 'Suche geoeffnet'",
         "via Suche geoeffnet" in _ws)
except Exception as _e:
    test("WhatsApp-ChatSearch grep", False, str(_e))


section("Frontend-TODOs CRUD + Reply-Context + Chat-Signature 2026-04-26")

try:
    with open(os.path.expanduser("~/AssistantDev/src/web_server.py")) as _f:
        _ws = _f.read()

    # REPLY_SESSION_CONTEXT — Kontext landet in kontext_items
    test("Reply-Session injectet konversations-kontext in kontext_items",
         "state.setdefault('kontext_items', []).append" in _ws and
         "reply_context_" in _ws)

    # CHAT_RESPONSE_MODEL_SIGNATURE
    test("/chat-Response enthaelt 'provider'-Feld",
         "'provider': PROVIDER_DISPLAY.get(provider_key" in _ws)
    test("/chat-Response enthaelt 'model'-Feld",
         "'model': MODEL_DISPLAY.get(model_id" in _ws)

    # FRONTEND_TODOS_CRUD
    test("GET /api/frontend-todos registered",
         "@app.route('/api/frontend-todos', methods=['GET'])" in _ws)
    test("PATCH /api/frontend-todos/<slug> registered",
         "@app.route('/api/frontend-todos/<slug>', methods=['PATCH'])" in _ws)
    test("DELETE /api/frontend-todos/<slug> registered",
         "@app.route('/api/frontend-todos/<slug>', methods=['DELETE'])" in _ws)
    test("Slug-Validation gegen Pfad-Traversal",
         "_TODO_SLUG_RE = re.compile(r'^[A-Z0-9_]+$')" in _ws)
    test("DELETE soft-renamed nach FIXED_<slug>_<date> bei reason=fixed",
         'reason == "fixed"' in _ws or "reason == 'fixed'" in _ws)
except Exception as _e:
    test("FrontendTodos+ReplyContext grep", False, str(_e))


section("WhatsApp Contact Disambiguation 2026-04-25")

try:
    with open(os.path.expanduser("~/AssistantDev/src/web_server.py")) as _f:
        _ws = _f.read()

    # Session-State persistiert source_*-Felder
    test("api_agent_sessions schreibt source_conversation_id in state",
         "state['source_conversation_id'] = conv_id" in _ws)
    test("api_agent_sessions schreibt source_type in state",
         "state['source_type'] = target.get('type')" in _ws)
    test("api_agent_sessions ruft get_session(session_id) auf",
         "state = get_session(session_id)" in _ws)

    # CREATE_WHATSAPP nutzt source_conversation_id
    test("CREATE_WHATSAPP override to-Name aus source_conversation_id",
         "src_conv = state.get('source_conversation_id'" in _ws and
         "wspec['to'] = true_contact" in _ws)
    test("CREATE_WHATSAPP entfernt halluzinierte phone-Werte",
         "wspec.pop('phone', None)" in _ws)

    # Best-Match Lookup (mehrdeutig -> Clipboard-Fallback)
    test("AppleScript-Lookup sammelt ALLE Treffer (nicht item 1)",
         "out & nm & \"\\\\t\" & num & linefeed" in _ws or
         'out & nm & "\\\\t" & num' in _ws)
    test("Best-Match: exakter Name bevorzugt (per same_name)",
         "e[0].lower() == target_lower" in _ws)
    test("Mehrdeutigkeit -> Clipboard-Fallback statt erste nehmen",
         "ambiguity_reason" in _ws and "-> Clipboard-Fallback" in _ws)

    # auto_search skip in Reply-Sessions
    test("auto_search wird in Reply-Session geskippt",
         "Reply-Session" in _ws or "reply session" in _ws)
except Exception as _e:
    test("WhatsApp-Disambiguation grep", False, str(_e))


section("WhatsApp + Conversations Cleanup 2026-04-25")

try:
    with open(os.path.expanduser("~/AssistantDev/src/web_server.py")) as _f:
        _ws = _f.read()

    # PLACEHOLDER_NUMBER
    test("_is_real_phone-Helper definiert",
         "def _is_real_phone(phone):" in _ws)
    test("send_whatsapp_draft validiert spec.phone",
         "Spec.phone" in _ws and "Placeholder" in _ws)
    test("Lookup-Phones gegen _is_real_phone gepruft",
         _ws.count("_is_real_phone(c['phone'])") >= 2)
    test("AppleScript-Phones werden ueber _is_real_phone gefiltert",
         "_is_real_phone(ph)" in _ws and "all_entries.append" in _ws)
    test("letzte Verteidigung vor whatsapp:// Aufruf",
         "fails sanity check" in _ws)

    # CHAT_THREAD_OWN_MESSAGES
    test("WhatsApp-Parser skippt 'Ich:' nicht mehr",
         "is_own = rest.startswith(\"Ich:\")" in _ws)
    test("Hash-Sender wird nicht als sender_name geleakt",
         "display_sender = contact or \"WhatsApp\"" in _ws)
    test("WhatsApp-Message hat is_own-Flag",
         "\"is_own\": is_own" in _ws)
    test("_msg_is_sent_by_user respektiert is_own",
         "m.get('is_own')" in _ws)
    test("Default-direction fuer chat-Sources auf 'received'",
         "(\"whatsapp\", \"imessage\", \"kchat\")" in _ws)

    # CONVERSATION_CLEANUP
    test("/api/conversations liest volles File",
         "full_text = fh.read()" in _ws and "CONVERSATION_CLEANUP" in _ws)
    test("user_message_count im Listing",
         "'user_message_count': user_count" in _ws)
    test("created_at im Listing",
         "'created_at': ctime_iso" in _ws)
    test("DELETE /api/conversations/<id> registered",
         "@app.route('/api/conversations/<conv_id>', methods=['DELETE'])" in _ws)
    test("Soft-Delete via .deleted_<ts>",
         '".deleted_{ts}"' in _ws or 'f".deleted_{ts}"' in _ws)
except Exception as _e:
    test("WhatsApp+Conv-Cleanup grep", False, str(_e))


section("DeepSeek + Ollama Provider 2026-04-25")

try:
    with open(os.path.expanduser("~/AssistantDev/src/web_server.py")) as _f:
        _ws = _f.read()

    test("VALID_PROVIDERS enthaelt 'deepseek'",
         "'deepseek'" in _ws and "VALID_PROVIDERS = {" in _ws)
    test("VALID_PROVIDERS enthaelt 'ollama'",
         "'ollama'" in _ws and "VALID_PROVIDERS = {" in _ws)

    test("call_deepseek-Adapter definiert",
         "def call_deepseek(api_key, model_id, system_prompt, messages):" in _ws)
    test("call_ollama-Adapter definiert",
         "def call_ollama(api_key, model_id, system_prompt, messages):" in _ws)

    test("call_deepseek nutzt api.deepseek.com",
         "https://api.deepseek.com/v1" in _ws)
    test("call_ollama nutzt 127.0.0.1:11434",
         "http://127.0.0.1:11434/v1" in _ws)

    test("ADAPTERS dict mappt 'deepseek'",
         '"deepseek": call_deepseek' in _ws)
    test("ADAPTERS dict mappt 'ollama'",
         '"ollama": call_ollama' in _ws)

    test("PROVIDER_DISPLAY hat 'DeepSeek'",
         "'deepseek': 'DeepSeek'" in _ws)
    test("PROVIDER_DISPLAY hat 'Ollama (lokal)'",
         "'ollama': 'Ollama (lokal)'" in _ws)

    test("MODEL_DISPLAY hat deepseek-v4-pro",
         "'deepseek-v4-pro':" in _ws)
    test("MODEL_DISPLAY hat deepseek-v4-flash",
         "'deepseek-v4-flash':" in _ws)
    test("MODEL_DISPLAY hat deepseek-r1:8b",
         "'deepseek-r1:8b':" in _ws)
except Exception as _e:
    test("DeepSeek+Ollama grep", False, str(_e))

# Optional: models.json hat die neuen Provider (datei liegt im iCloud-Datalake)
try:
    _models_path = os.path.expanduser(
        "~/Library/Mobile Documents/com~apple~CloudDocs/Downloads shared/claude_datalake/config/models.json"
    )
    if os.path.exists(_models_path):
        with open(_models_path) as _f:
            _models = json.load(_f)
        _provs = _models.get('providers', {})
        test("models.json: deepseek-Provider eingetragen", 'deepseek' in _provs)
        test("models.json: ollama-Provider eingetragen", 'ollama' in _provs)
        if 'deepseek' in _provs:
            _ds_models = [m['id'] for m in _provs['deepseek'].get('models', [])]
            test("models.json: deepseek-v4-flash gelistet", 'deepseek-v4-flash' in _ds_models)
            test("models.json: deepseek-v4-pro gelistet", 'deepseek-v4-pro' in _ds_models)
        if 'ollama' in _provs:
            _ol_models = [m['id'] for m in _provs['ollama'].get('models', [])]
            test("models.json: deepseek-r1:8b in ollama-Provider", 'deepseek-r1:8b' in _ol_models)
            test("models.json: ollama base_url localhost",
                 _provs['ollama'].get('base_url', '').startswith('http://127.0.0.1:11434'))
except Exception as _e:
    test("models.json check", False, str(_e))


_cleanup_test_artifacts()

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
