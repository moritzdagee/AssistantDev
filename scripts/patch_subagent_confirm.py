#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Patch web_server.py:
Sub-agent delegation now requires user confirmation before executing.
"""

filepath = '/Users/moritzcremer/AssistantDev/src/web_server.py'

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

changes = 0

# =============================================================
# 1. Modify detect_delegation to return score + keywords
# =============================================================

old_detect = """def detect_delegation(msg, current_agent):
    \"\"\"Detect if user wants to delegate to a sub-agent. Returns matched full_name or None.\"\"\"
    msg_lower = msg.lower()
    parent = get_parent_agent(current_agent) or current_agent

    words = msg_lower.split()
    has_action = any(w.rstrip('.,;:!?') in _DELEGATION_ACTIONS for w in words)
    if not has_action:
        has_action = any(phrase in msg_lower for phrase in _DELEGATION_PHRASES)
    if not has_action:
        return None

    subs = _get_available_subagents(parent)
    if not subs:
        return None

    kw_map = _load_subagent_keywords()
    best_match = None
    best_score = 0

    for sub in subs:
        sub_label = sub['sub_label']
        score = 0

        # 1. Exact match
        if sub_label in msg_lower:
            score = 100

        # 2. Keyword match from config
        if score == 0 and sub_label in kw_map:
            for kw in kw_map[sub_label]:
                if kw.lower() in msg_lower:
                    score = max(score, 50)

        # 3. Partial / fuzzy match
        if score == 0:
            for w in words:
                w_clean = w.rstrip('.,;:!?')
                if len(w_clean) < 3:
                    continue
                if w_clean in sub_label or sub_label in w_clean:
                    score = max(score, 30)
                dist = _levenshtein(w_clean, sub_label)
                if dist <= 2 and len(sub_label) > 3:
                    score = max(score, 40 - dist * 10)

        if score > best_score:
            best_score = score
            best_match = sub['full_name']

    return best_match if best_score > 0 else None"""

new_detect = """def detect_delegation(msg, current_agent):
    \"\"\"Detect if user wants to delegate to a sub-agent.
    Returns dict with full_name, score, matched_keywords — or None.\"\"\"
    msg_lower = msg.lower()
    parent = get_parent_agent(current_agent) or current_agent

    words = msg_lower.split()
    has_action = any(w.rstrip('.,;:!?') in _DELEGATION_ACTIONS for w in words)
    if not has_action:
        has_action = any(phrase in msg_lower for phrase in _DELEGATION_PHRASES)
    if not has_action:
        return None

    subs = _get_available_subagents(parent)
    if not subs:
        return None

    kw_map = _load_subagent_keywords()
    best_match = None
    best_score = 0
    best_keywords = []

    for sub in subs:
        sub_label = sub['sub_label']
        score = 0
        matched_kws = []

        # 1. Exact match
        if sub_label in msg_lower:
            score = 100
            matched_kws.append(sub_label)

        # 2. Keyword match from config
        if score == 0 and sub_label in kw_map:
            for kw in kw_map[sub_label]:
                if kw.lower() in msg_lower:
                    score = max(score, 50)
                    matched_kws.append(kw)

        # 3. Partial / fuzzy match
        if score == 0:
            for w in words:
                w_clean = w.rstrip('.,;:!?')
                if len(w_clean) < 3:
                    continue
                if w_clean in sub_label or sub_label in w_clean:
                    score = max(score, 30)
                    matched_kws.append(w_clean)
                dist = _levenshtein(w_clean, sub_label)
                if dist <= 2 and len(sub_label) > 3:
                    score = max(score, 40 - dist * 10)
                    matched_kws.append(w_clean)

        if score > best_score:
            best_score = score
            best_match = sub['full_name']
            best_keywords = matched_kws[:]

    if best_score > 0:
        return {
            'full_name': best_match,
            'score': best_score,
            'matched_keywords': list(set(best_keywords)),
            'display_name': get_agent_display_name(best_match),
        }
    return None"""

count = content.count(old_detect)
if count > 0:
    content = content.replace(old_detect, new_detect)
    print(f"1. detect_delegation now returns dict with score+keywords ({count})")
    changes += count
else:
    print("ERROR: detect_delegation not found!")
    exit(1)

# =============================================================
# 2. Add pending_delegations dict + confirmation route
#    Insert right before the /chat route
# =============================================================

old_chat_route = """@app.route('/chat', methods=['POST'])
def chat():"""

new_chat_route = """# Pending sub-agent delegations awaiting user confirmation
_pending_delegations = {}  # confirmation_id -> {session_id, sub_agent, msg, kontext, timestamp, auto_loaded, auto_search_info}

@app.route('/api/subagent_confirm', methods=['POST'])
def subagent_confirm():
    session_id = request.json.get('session_id', 'default')
    state = get_session(session_id)
    confirmation_id = request.json.get('confirmation_id', '')
    confirmed = request.json.get('confirmed', False)

    pending = _pending_delegations.pop(confirmation_id, None)
    if not pending:
        return jsonify({'error': 'Confirmation abgelaufen oder nicht gefunden'})

    if not confirmed:
        # User declined — process with current agent (no delegation)
        try:
            # Re-process the original message without delegation
            result = process_single_message(
                pending['msg'], state=state, skip_delegation=True,
                kontext_override=pending.get('kontext'),
                auto_loaded_override=pending.get('auto_loaded', []),
                auto_search_info_override=pending.get('auto_search_info', ''),
            )
            return jsonify(result)
        except Exception as e:
            return jsonify({'error': str(e)})

    # User confirmed — execute delegation
    try:
        deleg_result = execute_delegation(
            pending['sub_agent'], pending['msg'],
            pending.get('kontext', []), state=state
        )
        if 'error' in deleg_result:
            return jsonify({'error': deleg_result['error']})
        state['verlauf'].append({'role': 'user', 'content': pending['msg']})
        state['verlauf'].append({'role': 'assistant', 'content': deleg_result['response']})
        for _sid, _st in sessions.items():
            if _st is state:
                auto_save_session(_sid)
                break
        model_name = deleg_result.get('model_name', '')
        return jsonify({
            'response': deleg_result['response'],
            'model_name': model_name,
            'provider_display': deleg_result.get('provider_display', ''),
            'model_display': deleg_result.get('model_display', ''),
            'auto_loaded': pending.get('auto_loaded', []),
            'auto_search_info': pending.get('auto_search_info', ''),
            'agent': state['agent'],
            'created_files': [], 'created_emails': [], 'created_whatsapps': [],
            'created_images': [], 'created_videos': [], 'created_slacks': [],
            'delegated_to': deleg_result.get('delegated_to', ''),
            'delegated_display': deleg_result.get('delegated_display', ''),
        })
    except Exception as e:
        return jsonify({'error': str(e)})


@app.route('/chat', methods=['POST'])
def chat():"""

count = content.count(old_chat_route)
if count > 0:
    content = content.replace(old_chat_route, new_chat_route)
    print(f"2. Added pending_delegations + /api/subagent_confirm route ({count})")
    changes += count

# =============================================================
# 3. Modify process_single_message to return confirmation instead of executing
# =============================================================

old_delegation_block = """    # Check for sub-agent delegation
    if state['agent']:
        delegated_sub = detect_delegation(msg, state['agent'])
        if delegated_sub:
            try:
                deleg_result = execute_delegation(delegated_sub, msg, kontext_items, state=state)
                if 'error' in deleg_result:
                    raise ValueError(deleg_result['error'])
                # Add delegation to conversation history and log
                state['verlauf'].append({'role': 'user', 'content': msg})
                state['verlauf'].append({'role': 'assistant', 'content': deleg_result['response']})
                with open(state['dateiname'], 'a') as f:
                    provider_key = state.get('provider', 'anthropic')
                    model_id = state.get('model_id', 'claude-sonnet-4-6')
                    f.write('[' + provider_key + '/' + model_id + ' -> ' + delegated_sub + ']\\nDu: ' + msg + '\\nAssistant: ' + deleg_result['response'] + '\\n\\n')
                # Auto-save after delegation
                for _sid, _st in sessions.items():
                    if _st is state:
                        auto_save_session(_sid)
                        break
                return {
                    'response': deleg_result['response'],
                    'model_name': deleg_result.get('model_name', ''),
                    'auto_loaded': auto_loaded_names,
                    'auto_search_info': auto_search_info,
                    'agent': state['agent'],
                    'created_files': [],
                    'created_emails': [],
                    'created_whatsapps': [],
                    'created_images': [],
                    'created_videos': [],
                    'created_slacks': [],
                    'delegated_to': deleg_result.get('delegated_to', ''),
                    'delegated_display': deleg_result.get('delegated_display', ''),
                }
            except Exception as e:
                # Delegation failed — fall through to normal processing
                print(f"Delegation error: {e}")"""

new_delegation_block = """    # Check for sub-agent delegation (requires user confirmation)
    if state['agent'] and not kwargs.get('skip_delegation'):
        deleg_info = detect_delegation(msg, state['agent'])
        if deleg_info:
            import uuid as _deleg_uuid
            import time as _deleg_time
            # Clean expired pending delegations (>5 min)
            expired = [k for k, v in _pending_delegations.items()
                       if _deleg_time.time() - v.get('timestamp', 0) > 300]
            for k in expired:
                _pending_delegations.pop(k, None)
            # Also expire any previous pending for this session
            old_pending = [k for k, v in _pending_delegations.items()
                          if v.get('session_id') == kwargs.get('_session_id', '')]
            for k in old_pending:
                _pending_delegations.pop(k, None)
            conf_id = str(_deleg_uuid.uuid4())[:12]
            _pending_delegations[conf_id] = {
                'session_id': kwargs.get('_session_id', ''),
                'sub_agent': deleg_info['full_name'],
                'msg': msg,
                'kontext': kontext_items[:],
                'auto_loaded': auto_loaded_names,
                'auto_search_info': auto_search_info,
                'timestamp': _deleg_time.time(),
            }
            return {
                'type': 'subagent_confirmation_required',
                'suggested_subagent': deleg_info['full_name'],
                'subagent_display': deleg_info['display_name'],
                'matched_keywords': deleg_info['matched_keywords'],
                'score': deleg_info['score'],
                'confirmation_id': conf_id,
                'original_message': msg[:100],
            }"""

count = content.count(old_delegation_block)
if count > 0:
    content = content.replace(old_delegation_block, new_delegation_block)
    print(f"3. process_single_message now returns confirmation instead of executing ({count})")
    changes += count
else:
    print("ERROR: delegation block not found!")
    exit(1)

# =============================================================
# 4. Add skip_delegation and override params to process_single_message signature
# =============================================================

old_sig = """def process_single_message(msg, state=None, kontext_override=None):"""
new_sig = """def process_single_message(msg, state=None, kontext_override=None, **kwargs):"""

count = content.count(old_sig)
if count > 0:
    content = content.replace(old_sig, new_sig)
    print(f"4. Added **kwargs to process_single_message ({count})")
    changes += count

# Also handle auto_loaded/auto_search_info overrides at the top of the function
old_auto_init = """    auto_loaded_names = []
    auto_search_info = ''
    if auto_search and state.get('speicher'):"""

new_auto_init = """    auto_loaded_names = kwargs.get('auto_loaded_override', [])
    auto_search_info = kwargs.get('auto_search_info_override', '')
    if auto_loaded_names or auto_search_info:
        pass  # Overrides provided — skip auto-search
    elif auto_search and state.get('speicher'):"""

count = content.count(old_auto_init)
if count > 0:
    content = content.replace(old_auto_init, new_auto_init)
    print(f"4b. Added auto_loaded override support ({count})")
    changes += count

# =============================================================
# 5. Pass session_id to process_single_message from chat route
# =============================================================

old_process_call = "        result = process_single_message(msg, state=state)"
new_process_call = "        result = process_single_message(msg, state=state, _session_id=session_id)"

count = content.count(old_process_call)
if count > 0:
    content = content.replace(old_process_call, new_process_call)
    print(f"5. Pass session_id to process_single_message ({count})")
    changes += count

# =============================================================
# 6. Frontend: Handle subagent_confirmation_required response
# =============================================================

old_frontend_handler = """  if (data.delegated_to) {
    addStatusMsg('\\u2192 Delegiert an ' + (data.delegated_display || data.delegated_to));
  }
  addMessage('assistant', data.response, data.model_name, data.provider_display, data.model_display);"""

new_frontend_handler = """  if (data.type === 'subagent_confirmation_required') {
    showSubagentConfirmation(data);
    return;
  }
  if (data.delegated_to) {
    addStatusMsg('\\u2192 Delegiert an ' + (data.delegated_display || data.delegated_to));
  }
  addMessage('assistant', data.response, data.model_name, data.provider_display, data.model_display);"""

count = content.count(old_frontend_handler)
if count > 0:
    content = content.replace(old_frontend_handler, new_frontend_handler)
    print(f"6. Frontend: Added subagent_confirmation_required handler ({count})")
    changes += count

# =============================================================
# 7. Frontend: Add showSubagentConfirmation function
#    Insert right before function addCtxItem
# =============================================================

old_addctx = "function addCtxItem(name, type, autoLoaded) {"

confirmation_fn = """function showSubagentConfirmation(data) {
  var msgs = document.getElementById('messages');
  var div = document.createElement('div');
  div.className = 'msg assistant';
  var kws = data.matched_keywords ? data.matched_keywords.join(', ') : '';
  var inner = '<div class="bubble" style="background:#1a2a1a;border:1px solid #4a8a4a;padding:12px;">';
  inner += '<div style="margin-bottom:8px;">\\ud83d\\udd00 <b>Sub-Agent erkannt:</b> ' + escHtml(data.subagent_display || data.suggested_subagent) + '</div>';
  if (kws) inner += '<div style="margin-bottom:8px;color:#888;">Keywords: ' + escHtml(kws) + '</div>';
  inner += '<div style="margin-bottom:8px;color:#888;font-size:12px;">Nachricht: \\u201c' + escHtml(data.original_message || '') + '\\u201d</div>';
  inner += '<div id="subagent-btns-' + data.confirmation_id + '">';
  inner += '<button onclick="confirmSubagent(\\'' + data.confirmation_id + '\\',true)" style="background:#4a8a4a;color:#fff;border:none;padding:6px 16px;border-radius:4px;cursor:pointer;margin-right:8px;">\\u2713 Ja, weiterleiten</button>';
  inner += '<button onclick="confirmSubagent(\\'' + data.confirmation_id + '\\',false)" style="background:#555;color:#fff;border:none;padding:6px 16px;border-radius:4px;cursor:pointer;">\\u2717 Nein, selbst antworten</button>';
  inner += '</div></div>';
  var time = new Date().toLocaleTimeString('de-DE', {hour:'2-digit', minute:'2-digit'});
  div.innerHTML = inner + '<div class="meta">' + time + '</div>';
  msgs.appendChild(div);
  scrollDown();
  // Auto-decline after 5 minutes
  setTimeout(function() {
    var btns = document.getElementById('subagent-btns-' + data.confirmation_id);
    if (btns && btns.querySelector('button')) {
      confirmSubagent(data.confirmation_id, false);
    }
  }, 300000);
}

async function confirmSubagent(confirmationId, confirmed) {
  var btnsDiv = document.getElementById('subagent-btns-' + confirmationId);
  if (btnsDiv) {
    btnsDiv.innerHTML = confirmed
      ? '<span style="color:#8aba8a;">\\u2713 Weiterleitung bestaetigt</span>'
      : '<span style="color:#888;">\\u2717 Aktueller Agent antwortet</span>';
  }
  addStatusMsg(confirmed ? 'Wird an Sub-Agent weitergeleitet...' : 'Aktueller Agent verarbeitet die Anfrage...');
  try {
    var r = await fetch('/api/subagent_confirm', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({session_id: SESSION_ID, confirmation_id: confirmationId, confirmed: confirmed})
    });
    var data = await r.json();
    if (data.error) {
      addStatusMsg('Fehler: ' + data.error);
      return;
    }
    handleChatResponse(data);
  } catch(e) {
    addStatusMsg('Fehler bei Sub-Agent Verarbeitung: ' + e.message);
  }
}

function addCtxItem(name, type, autoLoaded) {"""

count = content.count(old_addctx)
if count > 0:
    content = content.replace(old_addctx, confirmation_fn)
    print(f"7. Frontend: Added showSubagentConfirmation + confirmSubagent ({count})")
    changes += count

# =============================================================
# 8. Extract response handling into reusable handleChatResponse function
#    The existing response handling code needs to be callable from confirmSubagent too
# =============================================================

# Find the existing response handler and wrap it
old_response_start = """  if (data.type === 'subagent_confirmation_required') {
    showSubagentConfirmation(data);
    return;
  }
  if (data.delegated_to) {"""

# We need to wrap the response handling in a function — find its boundaries
# Let's check what comes before this block to identify the function it's in
# The handler is inside the fetch().then() for /chat
# We need a handleChatResponse(data) function

# Instead of complex extraction, add a simple handleChatResponse that re-dispatches
old_handle_check = """  if (data.type === 'subagent_confirmation_required') {
    showSubagentConfirmation(data);
    return;
  }
  if (data.delegated_to) {
    addStatusMsg('\\u2192 Delegiert an ' + (data.delegated_display || data.delegated_to));
  }
  addMessage('assistant', data.response, data.model_name, data.provider_display, data.model_display);
  if (data.created_files && data.created_files.length) data.created_files.forEach(f => addDownloadButton(f));"""

# We don't need to wrap — confirmSubagent already calls handleChatResponse
# and the existing code in the fetch handler IS handleChatResponse
# Let's add handleChatResponse as an alias

# Find where the response handling function starts — it's after the fetch response processing
# Let's add handleChatResponse right before showSubagentConfirmation

old_show_fn = "function showSubagentConfirmation(data) {"
new_show_fn = """function handleChatResponse(data) {
  if (data.error) { addStatusMsg('Fehler: '+data.error); return; }
  if (data.type === 'subagent_confirmation_required') {
    showSubagentConfirmation(data);
    return;
  }
  if (data.delegated_to) {
    addStatusMsg('\\u2192 Delegiert an ' + (data.delegated_display || data.delegated_to));
  }
  if (data.auto_search_info) addStatusMsg(data.auto_search_info);
  if (data.auto_loaded && data.auto_loaded.length) {
    const agent = data.agent || getAgentName();
    data.auto_loaded.forEach(n => { addCtxItem(n,'file',true); addFinderLink(agent,n); });
  }
  addMessage('assistant', data.response, data.model_name, data.provider_display, data.model_display);
  if (data.created_files && data.created_files.length) data.created_files.forEach(f => addDownloadButton(f));
  if (data.created_images && data.created_images.length) data.created_images.forEach(img => addImagePreview(img));
  if (data.created_videos && data.created_videos.length) data.created_videos.forEach(vid => addVideoPreview(vid));
  if (data.created_emails && data.created_emails.length) {
    data.created_emails.forEach(e => {
      if (e && e.ok) addStatusMsg('\\u2709 Apple Mail geoeffnet: '+e.subject);
      else addMailtoFallback(e||{});
    });
  }
  if (data.created_whatsapps && data.created_whatsapps.length) {
    data.created_whatsapps.forEach(wa => {
      if (wa && wa.ok && wa.clipboard_fallback) addStatusMsg('\\u260E WhatsApp geoeffnet \\u2014 Keine Nummer fuer \\u201c'+wa.to+'\\u201d gefunden. Nachricht in Zwischenablage \\u2014 bitte manuell einfuegen.');
      else if (wa && wa.ok) addStatusMsg('\\u260E WhatsApp geoeffnet \\u2014 Chat mit '+wa.to+' wird geoeffnet. Bitte auf Senden klicken.');
      else addStatusMsg('\\u26A0 WhatsApp-Fehler: '+(wa.error||'Unbekannt'));
    });
  }
  if (data.created_slacks && data.created_slacks.length) {
    data.created_slacks.forEach(sl => {
      if (sl && sl.ok) addStatusMsg('\\U0001f4ac Slack geoeffnet: ' + (sl.target || ''));
      else addStatusMsg('\\u26A0 Slack-Fehler: '+(sl.error||'Unbekannt'));
    });
  }
}

function showSubagentConfirmation(data) {"""

content = content.replace(old_show_fn, new_show_fn, 1)
print("8. Added handleChatResponse function")
changes += 1

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"\nTotal changes: {changes}")
print("DONE")
