#!/usr/bin/env python3
"""
Transform web_server.py to support multi-session isolation.
Each browser tab gets its own session via sessionStorage.
"""
import re
import time

FPATH = "/Users/moritzcremer/AssistantDev/src/web_server.py"

with open(FPATH, "r") as f:
    content = f.read()

original_len = len(content)
print(f"Original file: {original_len} chars")

# ============================================================================
# STEP 1: Replace both global state dicts with sessions dict + get_session()
# ============================================================================

# First occurrence (around line 379-388) — no queue_lock before it
old_state_block_1 = """# ─── STATE ────────────────────────────────────────────────────────────────────

state = {
    "agent": None, "system_prompt": None, "speicher": None,
    "verlauf": [], "dateiname": None, "kontext_items": [],
    "provider": "anthropic", "model_id": "claude-sonnet-4-6",
    "session_files": [],
    "queue": [], "processing": False, "stop_requested": False,
    "completed_responses": [], "current_prompt": "",
}"""

# Second occurrence (around line 1147-1158) — has queue_lock
old_state_block_2 = """# ─── STATE ────────────────────────────────────────────────────────────────────

queue_lock = threading.Lock()

state = {
    "agent": None, "system_prompt": None, "speicher": None,
    "verlauf": [], "dateiname": None, "kontext_items": [],
    "provider": "anthropic", "model_id": "claude-sonnet-4-6",
    "session_files": [],
    "queue": [], "processing": False, "stop_requested": False,
    "completed_responses": [], "current_prompt": "",
}"""

new_state_block = """# ─── STATE (SESSION-BASED) ─────────────────────────────────────────────────────

import time as _time

queue_lock = threading.Lock()
sessions = {}  # session_id -> state dict

def _new_state():
    return {
        "agent": None, "system_prompt": None, "speicher": None,
        "verlauf": [], "dateiname": None, "kontext_items": [],
        "provider": "anthropic", "model_id": "claude-sonnet-4-6",
        "session_files": [],
        "queue": [], "processing": False, "stop_requested": False,
        "completed_responses": [], "current_prompt": "",
        "last_active": _time.time(),
    }

def get_session(session_id=None):
    if not session_id:
        session_id = 'default'
    if session_id not in sessions:
        sessions[session_id] = _new_state()
    sessions[session_id]['last_active'] = _time.time()
    return sessions[session_id]

def cleanup_old_sessions():
    cutoff = _time.time() - (24 * 60 * 60)
    to_delete = [sid for sid, s in sessions.items() if s.get('last_active', 0) < cutoff]
    for sid in to_delete:
        del sessions[sid]"""

# Replace block 2 first (has queue_lock), then block 1
count2 = content.count(old_state_block_2)
print(f"Found state block 2 (with queue_lock): {count2} times")
if count2 == 1:
    content = content.replace(old_state_block_2, new_state_block)
else:
    print("ERROR: Expected exactly 1 occurrence of state block 2")

count1 = content.count(old_state_block_1)
print(f"Found state block 1 (without queue_lock): {count1} times")
if count1 == 1:
    # Replace with minimal reference to avoid double definition
    content = content.replace(old_state_block_1,
        "# ─── STATE (see session-based state below) ────────────────────────────────────")
else:
    print("ERROR: Expected exactly 1 occurrence of state block 1")


# ============================================================================
# STEP 2: Fix close_current_session to accept state parameter
# ============================================================================

# Both occurrences
old_close = """def close_current_session():
    \"\"\"Summarize and index the current session before switching agents.\"\"\"
    if not state['agent'] or not state['verlauf']:"""

new_close = """def close_current_session(state=None):
    \"\"\"Summarize and index the current session before switching agents.\"\"\"
    if state is None:
        state = get_session()
    if not state['agent'] or not state['verlauf']:"""

c = content.count(old_close)
print(f"Found close_current_session: {c} times")
content = content.replace(old_close, new_close)


# ============================================================================
# STEP 3: Fix process_single_message to accept state parameter
# ============================================================================

old_psm = """def process_single_message(msg, kontext_override=None):
    \"\"\"Process a single chat message through the LLM. Returns result dict.
    Does not use Flask request/jsonify — can be called from queue worker thread.\"\"\"
    kontext_items = kontext_override if kontext_override is not None else state['kontext_items']"""

new_psm = """def process_single_message(msg, kontext_override=None, state=None):
    \"\"\"Process a single chat message through the LLM. Returns result dict.
    Does not use Flask request/jsonify — can be called from queue worker thread.\"\"\"
    if state is None:
        state = get_session()
    kontext_items = kontext_override if kontext_override is not None else state['kontext_items']"""

c = content.count(old_psm)
print(f"Found process_single_message: {c} times")
content = content.replace(old_psm, new_psm)


# ============================================================================
# STEP 4: Fix process_queue_worker to accept state parameter
# ============================================================================

old_pqw = """def process_queue_worker():
    \"\"\"Background thread: processes queued messages one by one.\"\"\"
    while True:
        with queue_lock:
            if state['stop_requested']:"""

new_pqw = """def process_queue_worker(state):
    \"\"\"Background thread: processes queued messages one by one.\"\"\"
    while True:
        with queue_lock:
            if state['stop_requested']:"""

c = content.count(old_pqw)
print(f"Found process_queue_worker: {c} times")
content = content.replace(old_pqw, new_pqw)

# Fix the call to process_single_message inside process_queue_worker
old_psm_call_in_worker = "result = process_single_message(item['message'], kontext_override=item.get('kontext_snapshot'))"
new_psm_call_in_worker = "result = process_single_message(item['message'], kontext_override=item.get('kontext_snapshot'), state=state)"
c = content.count(old_psm_call_in_worker)
print(f"Found process_single_message call in worker: {c} times")
content = content.replace(old_psm_call_in_worker, new_psm_call_in_worker)

# Fix the thread start for process_queue_worker (pass state)
old_thread_start = "threading.Thread(target=process_queue_worker, daemon=True).start()"
new_thread_start = "threading.Thread(target=process_queue_worker, args=(state,), daemon=True).start()"
c = content.count(old_thread_start)
print(f"Found thread start: {c} times")
content = content.replace(old_thread_start, new_thread_start)


# ============================================================================
# STEP 5: Add session_id extraction to all routes
# ============================================================================

# --- POST routes that use request.json ---
post_json_routes = {
    "def close_session():\n    close_current_session()":
        "def close_session():\n    session_id = request.json.get('session_id', 'default') if request.is_json else 'default'\n    state = get_session(session_id)\n    close_current_session(state)",

    "def select_agent():\n    name = request.json['agent']":
        "def select_agent():\n    session_id = request.json.get('session_id', 'default')\n    state = get_session(session_id)\n    name = request.json['agent']",

    "def new_conversation():\n    name = request.json['agent']\n    if not state['agent']:":
        "def new_conversation():\n    session_id = request.json.get('session_id', 'default')\n    state = get_session(session_id)\n    name = request.json['agent']\n    if not state['agent']:",

    "def save_prompt():\n    agent = request.json['agent']":
        "def save_prompt():\n    session_id = request.json.get('session_id', 'default')\n    state = get_session(session_id)\n    agent = request.json['agent']",

    "def create_agent():\n    name = request.json.get('name', '').strip()":
        "def create_agent():\n    session_id = request.json.get('session_id', 'default')\n    state = get_session(session_id)\n    name = request.json.get('name', '').strip()",

    "def select_model():\n    state['provider']":
        "def select_model():\n    session_id = request.json.get('session_id', 'default')\n    state = get_session(session_id)\n    state['provider']",

    "def chat():\n    if not state['agent']:":
        "def chat():\n    session_id = request.json.get('session_id', 'default')\n    state = get_session(session_id)\n    if not state['agent']:",

    "def stop_queue():\n    with queue_lock:":
        "def stop_queue():\n    session_id = request.json.get('session_id', 'default') if request.is_json else 'default'\n    state = get_session(session_id)\n    with queue_lock:",

    "def add_url():\n    url = request.json['url'].strip()":
        "def add_url():\n    session_id = request.json.get('session_id', 'default')\n    state = get_session(session_id)\n    url = request.json['url'].strip()",

    "def search_memory():\n    query = request.json.get('query', '')\n    if not state.get('speicher')":
        "def search_memory():\n    session_id = request.json.get('session_id', 'default')\n    state = get_session(session_id)\n    query = request.json.get('query', '')\n    if not state.get('speicher')",

    "def search_preview():\n    \"\"\"Search memory and return rich preview results for interactive selection.\"\"\"\n    query = request.json.get('query', '')\n    if not state.get('speicher')":
        "def search_preview():\n    \"\"\"Search memory and return rich preview results for interactive selection.\"\"\"\n    session_id = request.json.get('session_id', 'default')\n    state = get_session(session_id)\n    query = request.json.get('query', '')\n    if not state.get('speicher')",

    "def load_selected_files():\n    \"\"\"Load selected files into kontext_items.\"\"\"\n    paths = request.json.get('paths', [])[:5]":
        "def load_selected_files():\n    \"\"\"Load selected files into kontext_items.\"\"\"\n    session_id = request.json.get('session_id', 'default')\n    state = get_session(session_id)\n    paths = request.json.get('paths', [])[:5]",

    "def remove_ctx():\n    name = request.json['name']":
        "def remove_ctx():\n    session_id = request.json.get('session_id', 'default')\n    state = get_session(session_id)\n    name = request.json['name']",

    "def send_email_draft_route():\n    try:\n        spec = request.json":
        "def send_email_draft_route():\n    session_id = request.json.get('session_id', 'default') if request.is_json else 'default'\n    state = get_session(session_id)\n    try:\n        spec = request.json",

    "def create_file():\n    try:":
        "def create_file():\n    session_id = request.json.get('session_id', 'default') if request.is_json else 'default'\n    state = get_session(session_id)\n    try:",
}

for old, new in post_json_routes.items():
    c = content.count(old)
    fname = old.split('(')[0].replace('def ', '')
    if c == 0:
        print(f"  WARNING: {fname} not found!")
    else:
        print(f"  Route {fname}: {c} match(es)")
        content = content.replace(old, new)

# --- GET routes that use request.args ---
get_routes = {
    "def get_prompt():\n    agent = request.args.get('agent', '')":
        "def get_prompt():\n    session_id = request.args.get('session_id', 'default')\n    state = get_session(session_id)\n    agent = request.args.get('agent', '')",

    "def get_history():\n    agent":
        "def get_history():\n    session_id = request.args.get('session_id', 'default')\n    state = get_session(session_id)\n    agent",

    "def queue_status():\n    with queue_lock:":
        "def queue_status():\n    session_id = request.args.get('session_id', 'default')\n    state = get_session(session_id)\n    with queue_lock:",

    "def poll_responses():\n    with queue_lock:":
        "def poll_responses():\n    session_id = request.args.get('session_id', 'default')\n    state = get_session(session_id)\n    with queue_lock:",

    "def available_subagents():\n    agent = request.args.get('agent', state.get('agent', ''))":
        "def available_subagents():\n    session_id = request.args.get('session_id', 'default')\n    state = get_session(session_id)\n    agent = request.args.get('agent', state.get('agent', ''))",

    "def download_file():\n    from flask import send_file":
        "def download_file():\n    session_id = request.args.get('session_id', 'default')\n    state = get_session(session_id)\n    from flask import send_file",
}

for old, new in get_routes.items():
    c = content.count(old)
    fname = old.split('(')[0].replace('def ', '')
    if c == 0:
        print(f"  WARNING: GET {fname} not found!")
    else:
        print(f"  GET Route {fname}: {c} match(es)")
        content = content.replace(old, new)


# --- /add_file uses request.files (multipart), session_id from form data ---
old_add_file = """def add_file():
    file = request.files.get('file')
    if not file:
        return jsonify({'ok': False, 'error': 'Keine Datei erhalten'})
    if not state['agent'] or not state['speicher']:"""

new_add_file = """def add_file():
    session_id = request.form.get('session_id', 'default')
    state = get_session(session_id)
    file = request.files.get('file')
    if not file:
        return jsonify({'ok': False, 'error': 'Keine Datei erhalten'})
    if not state['agent'] or not state['speicher']:"""

c = content.count(old_add_file)
print(f"  Route add_file (multipart): {c} match(es)")
content = content.replace(old_add_file, new_add_file)


# --- Fix process_single_message call in chat() route ---
old_chat_psm = "result = process_single_message(msg)\n    except Exception as e:\n        with queue_lock:"
new_chat_psm = "result = process_single_message(msg, state=state)\n    except Exception as e:\n        with queue_lock:"
c = content.count(old_chat_psm)
print(f"  chat() process_single_message call: {c} match(es)")
content = content.replace(old_chat_psm, new_chat_psm)


# --- Fix close_current_session calls in select_agent (pass state) ---
# In select_agent, close_current_session is called before the agent switch
# The existing call is: close_current_session()
# We need it to pass the current state
# But the route already defines state via get_session now, so we just need:
old_close_call = "    close_current_session()\n    return jsonify({'ok': True})"
new_close_call = "    close_current_session(state)\n    return jsonify({'ok': True})"
c = content.count(old_close_call)
print(f"  close_session route close_current_session call: {c} match(es)")
content = content.replace(old_close_call, new_close_call)

# In select_agent, there's close_current_session() call before state.update
# Find it
old_close_in_select = "    close_current_session()\n    # Read agent"
if content.count(old_close_in_select) > 0:
    new_close_in_select = "    close_current_session(state)\n    # Read agent"
    content = content.replace(old_close_in_select, new_close_in_select)
    print("  Fixed close_current_session in select_agent")
else:
    # Try alternative pattern
    print("  Looking for close_current_session in select_agent...")
    # Let's find any remaining bare close_current_session() calls
    remaining = content.count("close_current_session()")
    print(f"  Remaining bare close_current_session() calls: {remaining}")


# ============================================================================
# STEP 6: Add session cleanup to startup
# ============================================================================

old_startup = """    # Build global search index in background at startup
    if build_global_index_async:
        build_global_index_async()"""

new_startup = """    # Cleanup old sessions every hour
    def session_cleanup_loop():
        import time
        while True:
            time.sleep(3600)
            cleanup_old_sessions()
    threading.Thread(target=session_cleanup_loop, daemon=True).start()
    # Build global search index in background at startup
    if build_global_index_async:
        build_global_index_async()"""

c = content.count(old_startup)
print(f"Found startup block: {c} times")
content = content.replace(old_startup, new_startup)


# ============================================================================
# STEP 7: Frontend - Add SESSION_ID and update all fetch() calls
# ============================================================================

# Add SESSION_ID generation at the start of the <script> block
old_script_start = "<script>\n"
# Find the first occurrence that's part of the main app script (after HTML)
# We need to add it right after <script>
new_script_start = """<script>
// ─── SESSION ID ──────────────────────────────────────────────────────────────
function getSessionId() {
  let sid = sessionStorage.getItem('assistant_session_id');
  if (!sid) {
    sid = 'sess_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    sessionStorage.setItem('assistant_session_id', sid);
  }
  return sid;
}
const SESSION_ID = getSessionId();
"""

# There should be only one <script> tag in the file
c = content.count(old_script_start)
print(f"Found <script> tags: {c}")
# Replace only the first occurrence
content = content.replace(old_script_start, new_script_start, 1)


# Now update all fetch() calls to include session_id
# POST requests with JSON body: add session_id to the JSON
fetch_post_replacements = [
    # select_agent
    ("body:JSON.stringify({agent:name})})",
     "body:JSON.stringify({agent:name, session_id:SESSION_ID})})"),
    # create_agent
    ("body:JSON.stringify({name})})",
     "body:JSON.stringify({name, session_id:SESSION_ID})})"),
    # close_session
    ("fetch('/close_session', {method:'POST'})",
     "fetch('/close_session', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({session_id:SESSION_ID})})"),
    # select_model
    ("body:JSON.stringify({provider:p,model_id:m})})",
     "body:JSON.stringify({provider:p,model_id:m, session_id:SESSION_ID})})"),
    # chat
    ("body:JSON.stringify({message:text})})",
     "body:JSON.stringify({message:text, session_id:SESSION_ID})})"),
    # add_url
    ("body:JSON.stringify({url})})",
     "body:JSON.stringify({url, session_id:SESSION_ID})})"),
    # remove_ctx
    ("body:JSON.stringify({name})})\n",
     "body:JSON.stringify({name, session_id:SESSION_ID})})\n"),
    # search_memory
    ("body:JSON.stringify({query:q})})",
     "body:JSON.stringify({query:q, session_id:SESSION_ID})})"),
    # load_selected_files
    ("body:JSON.stringify({paths})})",
     "body:JSON.stringify({paths, session_id:SESSION_ID})})"),
    # search_preview
    ("body:JSON.stringify({query:text, agent:getAgentName()})})",
     "body:JSON.stringify({query:text, agent:getAgentName(), session_id:SESSION_ID})})"),
    # global_search_preview
    ("body:JSON.stringify({query:text, requesting_agent:getAgentName()})})",
     "body:JSON.stringify({query:text, requesting_agent:getAgentName(), session_id:SESSION_ID})})"),
    # stop_queue
    ("fetch('/stop_queue', {method:'POST'})",
     "fetch('/stop_queue', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({session_id:SESSION_ID})})"),
    # open_in_finder
    ("body:JSON.stringify({agent, filename})})",
     "body:JSON.stringify({agent, filename, session_id:SESSION_ID})})"),
    # open_in_finder (memory folder - filename:'')
    ("body:JSON.stringify({agent, filename:''})})",
     "body:JSON.stringify({agent, filename:'', session_id:SESSION_ID})})"),
]

for old, new in fetch_post_replacements:
    c = content.count(old)
    short = old[:60].replace('\n', '\\n')
    if c == 0:
        print(f"  WARNING: fetch POST not found: {short}")
    else:
        print(f"  fetch POST ({c}x): {short}")
        content = content.replace(old, new)

# GET requests: add session_id as query parameter
fetch_get_replacements = [
    # models (no session needed, but keeping consistent)
    # agents (no session needed)
    # get_prompt
    ("fetch('/get_prompt?agent=' + encodeURIComponent(name))",
     "fetch('/get_prompt?agent=' + encodeURIComponent(name) + '&session_id=' + SESSION_ID)"),
    # get_history
    ("fetch('/get_history?agent=' + encodeURIComponent(agentName))",
     "fetch('/get_history?agent=' + encodeURIComponent(agentName) + '&session_id=' + SESSION_ID)"),
    # poll_responses
    ("fetch('/poll_responses')",
     "fetch('/poll_responses?session_id=' + SESSION_ID)"),
    # queue_status
    ("fetch('/queue_status')",
     "fetch('/queue_status?session_id=' + SESSION_ID)"),
]

for old, new in fetch_get_replacements:
    c = content.count(old)
    short = old[:60]
    if c == 0:
        print(f"  WARNING: fetch GET not found: {short}")
    else:
        print(f"  fetch GET ({c}x): {short}")
        content = content.replace(old, new)


# load_conversation POST
old_load_conv = "body:JSON.stringify({session, agent})})"
new_load_conv = "body:JSON.stringify({session, agent, session_id:SESSION_ID})})"
c = content.count(old_load_conv)
print(f"  load_conversation: {c} match(es)")
if c > 0:
    content = content.replace(old_load_conv, new_load_conv)

# save_prompt POST
old_save_prompt_js = "body:JSON.stringify({agent:name, prompt:p})})"
new_save_prompt_js = "body:JSON.stringify({agent:name, prompt:p, session_id:SESSION_ID})})"
c = content.count(old_save_prompt_js)
print(f"  save_prompt JS: {c} match(es)")
if c > 0:
    content = content.replace(old_save_prompt_js, new_save_prompt_js)

# select_model — need to find the actual pattern
old_select_model_js = "body:JSON.stringify({provider"
# Already handled above

# add_file (multipart form data) — need to add session_id to FormData
old_add_file_fd = "const r = await fetch('/add_file', {method:'POST', body:fd})"
new_add_file_fd = "fd.append('session_id', SESSION_ID);\n    const r = await fetch('/add_file', {method:'POST', body:fd})"
c = content.count(old_add_file_fd)
print(f"  add_file FormData: {c} match(es)")
content = content.replace(old_add_file_fd, new_add_file_fd)

# Check for select_model pattern
old_sm = "const r = await fetch('/select_model', {method:'POST', headers:{'Content-Type':'application/json'},"
c = content.count(old_sm)
print(f"  select_model fetch: {c} match(es)")
# Read the actual line to find what JSON body is sent
idx = content.find(old_sm)
if idx >= 0:
    line_end = content.find('\n', idx)
    line = content[idx:line_end]
    print(f"  Full line: {line[:120]}")

# Handle load_conversation route on backend
old_load_conv_route = "def load_conversation():"
c = content.count(old_load_conv_route)
print(f"  load_conversation route: {c} match(es)")

# Need to read the actual load_conversation function
idx = content.find("def load_conversation():")
if idx >= 0:
    snippet = content[idx:idx+300]
    print(f"  Snippet: {snippet[:200]}")


# ============================================================================
# FINAL: Write the file
# ============================================================================

print(f"\nNew file: {len(content)} chars (delta: {len(content) - original_len})")

with open(FPATH, "w") as f:
    f.write(content)

print("DONE - web_server.py updated with session support")
