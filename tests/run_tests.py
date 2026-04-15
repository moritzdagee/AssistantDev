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
test("Slash-Command /find im HTML vorhanden", "/find" in html and "Agent-Memory" in html)
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
