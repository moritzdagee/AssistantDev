#!/usr/bin/env python3
"""
Patch web_server.py:
1. Feature: WhatsApp Draft Handler (CREATE_WHATSAPP)
2. Bug Fix: Model Dropdown CSS
3. Feature: Capability-Tags im Dropdown
4. Feature: Per-Agent Sticky Model Selection
"""

import re
import sys

FILEPATH = "/Users/moritzcremer/AssistantDev/src/web_server.py"

with open(FILEPATH, 'r') as f:
    content = f.read()

lines = content.split('\n')
original_len = len(lines)

# ─── HELPER: find line index containing exact text (from bottom for active defs) ───
def find_line(text, start=0, from_end=False):
    if from_end:
        for i in range(len(lines)-1, -1, -1):
            if text in lines[i]:
                return i
    for i in range(start, len(lines)):
        if text in lines[i]:
            return i
    return -1

# ─── HELPER: find last occurrence of text ───
def find_last_line(text):
    for i in range(len(lines)-1, -1, -1):
        if text in lines[i]:
            return i
    return -1

changes = []

# ═══════════════════════════════════════════════════════════════════════════════
# 1. Add MODEL_CAPABILITIES dict after IMAGE_PROVIDERS/VIDEO_PROVIDERS
# ═══════════════════════════════════════════════════════════════════════════════

# Find the VIDEO_PROVIDERS dict (should be around line 1155)
vp_line = find_line('VIDEO_PROVIDERS = {')
if vp_line == -1:
    print("ERROR: VIDEO_PROVIDERS not found")
    sys.exit(1)

# Find closing brace
vp_end = vp_line + 1
while vp_end < len(lines) and '}' not in lines[vp_end]:
    vp_end += 1

# Insert MODEL_CAPABILITIES after VIDEO_PROVIDERS
cap_block = '''
# Capability-Tags fuer Model-Dropdown
MODEL_CAPABILITIES = {
    "gemini-2.0-flash": ["video", "image"],
    "gemini-2.5-flash": ["image"],
    "gemini-2.5-flash-image": ["image"],
    "gemini-2.5-pro": ["reasoning"],
    "gpt-4o": ["image"],
    "gpt-image-1": ["image"],
    "o1": ["reasoning"],
    "sonar-deep-research": ["reasoning"],
    "sonar-reasoning-pro": ["reasoning"],
    "sonar-reasoning": ["reasoning"],
}
CAPABILITY_EMOJI = {"video": "\\U0001f3ac", "image": "\\U0001f5bc\\ufe0f", "reasoning": "\\U0001f9e0"}
'''

insert_pos = vp_end + 1
lines.insert(insert_pos, cap_block)
changes.append(f"Added MODEL_CAPABILITIES dict after line {vp_end}")

# Re-read since we inserted
content = '\n'.join(lines)
lines = content.split('\n')

# ═══════════════════════════════════════════════════════════════════════════════
# 2. Add send_whatsapp_draft function after the LAST send_email_draft
# ═══════════════════════════════════════════════════════════════════════════════

# Find the last send_email_draft function end (look for the return True line)
# The active send_email_draft is the second one (around line 833+)
se_line = find_last_line("def send_email_draft(spec):")
if se_line == -1:
    print("ERROR: send_email_draft not found")
    sys.exit(1)

# Find its end: look for next "def " or assignment at module level after the function
se_end = se_line + 1
while se_end < len(lines):
    stripped = lines[se_end].lstrip()
    indent = len(lines[se_end]) - len(stripped)
    if indent == 0 and stripped and not stripped.startswith('#') and not stripped.startswith('"""'):
        break
    se_end += 1

# Insert whatsapp function before the next module-level code
whatsapp_func = '''
def send_whatsapp_draft(spec, agent_name=None):
    """Opens WhatsApp with a pre-filled message. Looks up phone in contacts.json."""
    import subprocess
    import urllib.parse

    to_name = spec.get('to', '')
    message = spec.get('message', '')
    phone = spec.get('phone', '')  # Optional direct phone

    # If no direct phone, look up in contacts.json
    if not phone and to_name and agent_name:
        parent = agent_name.split('_')[0] if '_' in agent_name else agent_name
        contacts_path = os.path.join(BASE, parent, "memory", "contacts.json")
        if os.path.exists(contacts_path):
            try:
                with open(contacts_path) as f:
                    cdata = json.load(f)
                to_lower = to_name.lower()
                for c in cdata.get('contacts', []):
                    cname = (c.get('name') or '').lower()
                    if to_lower in cname or cname in to_lower:
                        if c.get('phone'):
                            phone = c['phone']
                            break
            except Exception:
                pass

    if not phone:
        raise Exception(f"Kein WhatsApp-Kontakt fuer '{to_name}' gefunden. Bitte Nummer in contacts.json ergaenzen.")

    # Normalize phone: remove spaces, dashes, dots, leading +
    phone_clean = re.sub(r'[\\s./-]', '', phone).lstrip('+')

    encoded_msg = urllib.parse.quote(message)
    whatsapp_url = f"whatsapp://send?phone={phone_clean}&text={encoded_msg}"

    result = subprocess.run(['open', whatsapp_url], capture_output=True, text=True, timeout=10)
    if result.returncode != 0:
        raise Exception(f"WhatsApp konnte nicht geoeffnet werden: {result.stderr.strip()}")
    return to_name, phone

'''

lines.insert(se_end, whatsapp_func)
changes.append(f"Added send_whatsapp_draft function after line {se_end}")

# Re-read
content = '\n'.join(lines)
lines = content.split('\n')

# ═══════════════════════════════════════════════════════════════════════════════
# 3. Update /models route to include capabilities
# ═══════════════════════════════════════════════════════════════════════════════

# Find the models route
models_route = find_line("def get_models():")
if models_route == -1:
    print("ERROR: get_models not found")
    sys.exit(1)

# Find the line that builds the model list: 'models': pdata.get('models', [])
models_append = find_line("'models': pdata.get('models', [])", models_route)
if models_append != -1:
    old_line = lines[models_append]
    # Replace with capability-enriched version
    indent = len(old_line) - len(old_line.lstrip())
    new_line = ' ' * indent + "'models': [dict(m, capabilities=[CAPABILITY_EMOJI.get(c,'') for c in MODEL_CAPABILITIES.get(m['id'], [])]) for m in pdata.get('models', [])]"
    lines[models_append] = new_line
    changes.append(f"Updated /models route to include capabilities at line {models_append}")

# Re-read
content = '\n'.join(lines)
lines = content.split('\n')

# ═══════════════════════════════════════════════════════════════════════════════
# 4. Fix Model Dropdown CSS — add option styling for dark mode
# ═══════════════════════════════════════════════════════════════════════════════

css_target = "select.hdr-select:hover { border-color:#666; }"
css_line = find_line(css_target)
if css_line != -1:
    lines[css_line] = lines[css_line] + "\n  select.hdr-select option { background:#1a1a1a; color:#e0e0e0; padding:4px 8px; }"
    lines[css_line] += "\n  select.hdr-select { -webkit-appearance:menulist; appearance:menulist; min-width:120px; }"
    changes.append(f"Added dark-mode option styling at line {css_line}")

# Re-read
content = '\n'.join(lines)
lines = content.split('\n')

# ═══════════════════════════════════════════════════════════════════════════════
# 5. Update populateModels to show capability tags
# ═══════════════════════════════════════════════════════════════════════════════

# Find populateModels function
pm_line = find_line("function populateModels(providerData)")
if pm_line != -1:
    # Find the line: o.value = m.id; o.textContent = m.name;
    for i in range(pm_line, min(pm_line+15, len(lines))):
        if "o.value = m.id; o.textContent = m.name;" in lines[i]:
            indent = len(lines[i]) - len(lines[i].lstrip())
            lines[i] = ' ' * indent + "o.value = m.id; o.textContent = m.name + (m.capabilities && m.capabilities.length ? ' ' + m.capabilities.join('') : '');"
            changes.append(f"Updated populateModels capability tags at line {i}")
            break

# Re-read
content = '\n'.join(lines)
lines = content.split('\n')

# ═══════════════════════════════════════════════════════════════════════════════
# 6. Add Per-Agent Sticky Model Preferences
# ═══════════════════════════════════════════════════════════════════════════════

# 6a. Add backend routes: after select_model route
sm_line = find_line("def select_model():")
if sm_line == -1:
    print("ERROR: select_model not found")
    sys.exit(1)

# Find the end of select_model function
sm_end = sm_line + 1
while sm_end < len(lines):
    stripped = lines[sm_end].lstrip()
    indent = len(lines[sm_end]) - len(stripped)
    # Module-level code (not blank, not indented)
    if indent == 0 and stripped and not stripped.startswith('#'):
        break
    sm_end += 1

pref_routes = '''
AGENT_PREFS_FILE = os.path.join(BASE, "config", "agent_model_preferences.json")

def _load_agent_prefs():
    if os.path.exists(AGENT_PREFS_FILE):
        try:
            with open(AGENT_PREFS_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def _save_agent_prefs(prefs):
    os.makedirs(os.path.dirname(AGENT_PREFS_FILE), exist_ok=True)
    with open(AGENT_PREFS_FILE, 'w') as f:
        json.dump(prefs, f, indent=2)

@app.route('/api/agent-model-preference', methods=['GET', 'POST'])
def agent_model_preference():
    if request.method == 'POST':
        data = request.json
        agent = data.get('agent', '')
        if not agent:
            return jsonify({'ok': False, 'error': 'No agent specified'})
        prefs = _load_agent_prefs()
        prefs[agent] = {'provider': data.get('provider', ''), 'model': data.get('model', '')}
        _save_agent_prefs(prefs)
        return jsonify({'ok': True})
    else:
        agent = request.args.get('agent', '')
        prefs = _load_agent_prefs()
        pref = prefs.get(agent, {})
        return jsonify({'ok': True, 'provider': pref.get('provider', ''), 'model': pref.get('model', '')})

'''

lines.insert(sm_end, pref_routes)
changes.append(f"Added agent-model-preference routes after line {sm_end}")

# Re-read
content = '\n'.join(lines)
lines = content.split('\n')

# 6b. Update frontend: onModelChange to save preference
omc_line = find_line("async function onModelChange()")
if omc_line != -1:
    # Find the closing brace of onModelChange
    for i in range(omc_line, min(omc_line+20, len(lines))):
        if "localStorage.setItem('claude_model'" in lines[i]:
            # Add preference save after localStorage save
            indent = len(lines[i]) - len(lines[i].lstrip())
            save_pref = ' ' * indent + "var agName = document.getElementById('agent-label').dataset.agentName; if (agName) fetch('/api/agent-model-preference', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({agent:agName, provider:pv, model:mv})});"
            lines.insert(i+1, save_pref)
            changes.append(f"Added preference save in onModelChange at line {i+1}")
            break

# Re-read
content = '\n'.join(lines)
lines = content.split('\n')

# 6c. Update selectAgent to load preference
sa_line = find_line("async function selectAgent(name)")
if sa_line != -1:
    # Find "addStatusMsg('Agent" line — add preference loading after it
    for i in range(sa_line, min(sa_line+30, len(lines))):
        if "addStatusMsg('Agent" in lines[i]:
            indent = len(lines[i]) - len(lines[i].lstrip())
            load_pref = ' ' * indent + """// Load sticky model preference for this agent
""" + ' ' * indent + """fetch('/api/agent-model-preference?agent='+encodeURIComponent(name)).then(r=>r.json()).then(pref => {
""" + ' ' * indent + """  if (pref.provider && pref.model) {
""" + ' ' * indent + """    var ps = document.getElementById('provider-select');
""" + ' ' * indent + """    ps.value = pref.provider;
""" + ' ' * indent + """    fetch('/models').then(r=>r.json()).then(mdata => {
""" + ' ' * indent + """      var pd = mdata.find(p => p.provider === pref.provider);
""" + ' ' * indent + """      if (pd) { populateModels(pd); var ms = document.getElementById('model-select'); ms.value = pref.model; onModelChange(); }
""" + ' ' * indent + """    });
""" + ' ' * indent + """  }
""" + ' ' * indent + """}).catch(()=>{});"""
            lines.insert(i+1, load_pref)
            changes.append(f"Added preference loading in selectAgent at line {i+1}")
            break

# Re-read
content = '\n'.join(lines)
lines = content.split('\n')

# ═══════════════════════════════════════════════════════════════════════════════
# 7. Add CREATE_WHATSAPP to system prompt (file_capability string)
# ═══════════════════════════════════════════════════════════════════════════════

# Find the CREATE_EMAIL instruction in file_capability
ce_wichtig = find_line("WICHTIG: Du schickst NIEMALS eine E-Mail direkt ab")
if ce_wichtig != -1:
    # Find good insertion point — after the email reply instructions, before WEITERE FAEHIGKEITEN
    wf_line = find_line("--- WEITERE FAEHIGKEITEN ---", ce_wichtig)
    if wf_line != -1:
        wa_instruction = """
Fuer WhatsApp-Nachricht (oeffnet WhatsApp mit vorausgefuellter Nachricht):
[CREATE_WHATSAPP:{"to":"Vorname oder Name","message":"Nachrichtentext hier"}]

WICHTIG: WhatsApp-Nachrichten werden NIEMALS automatisch gesendet. Die App wird nur geoeffnet mit vorausgefuelltem Text. Der Nutzer muss manuell auf Senden klicken. Verwende dies wenn der Nutzer sagt: 'schreib auf WhatsApp', 'WhatsApp an', 'schick per WhatsApp'."""
        lines.insert(wf_line, wa_instruction)
        changes.append(f"Added CREATE_WHATSAPP instruction to system prompt at line {wf_line}")

# Re-read
content = '\n'.join(lines)
lines = content.split('\n')

# ═══════════════════════════════════════════════════════════════════════════════
# 8. Add CREATE_WHATSAPP parsing in chat() response handler
# ═══════════════════════════════════════════════════════════════════════════════

# Find the CREATE_EMAIL parsing block end — look for "# Parse CREATE_FILE"
cf_line = find_line("# Parse CREATE_FILE")
if cf_line != -1:
    wa_parse = '''
        # Parse CREATE_WHATSAPP
        created_whatsapps = []
        wa_prefix = '[CREATE_WHATSAPP:'
        wi = 0
        while wi < len(text):
            widx = text.find(wa_prefix, wi)
            if widx == -1:
                break
            wjstart = widx + len(wa_prefix)
            depth = 0
            wj = wjstart
            wjend = -1
            win_str = False
            wesc = False
            while wj < len(text):
                wc = text[wj]
                if wesc:
                    wesc = False
                elif wc == '\\\\':
                    wesc = True
                elif wc == '"' and not wesc:
                    win_str = not win_str
                elif not win_str:
                    if wc == '{':
                        depth += 1
                    elif wc == '}':
                        depth -= 1
                        if depth == 0:
                            wjend = wj + 1
                            break
                wj += 1
            if wjend != -1 and wjend < len(text) and text[wjend] == ']':
                full_block = text[widx:wjend+1]
                json_str = text[wjstart:wjend]
                wspec = {}
                try:
                    wspec = json.loads(json_str)
                    agent_name = state.get('agent', 'standard')
                    wa_to, wa_phone = send_whatsapp_draft(wspec, agent_name)
                    created_whatsapps.append({'ok': True, 'to': wa_to, 'phone': wa_phone})
                    text = text[:widx] + text[wjend+1:]
                    wi = widx
                except Exception as we:
                    created_whatsapps.append({'ok': False, 'to': wspec.get('to',''), 'error': str(we)})
                    text = text[:widx] + text[wjend+1:]
                    wi = widx
            else:
                wi = widx + 1

'''
    lines.insert(cf_line, wa_parse)
    changes.append(f"Added CREATE_WHATSAPP parsing before line {cf_line}")

# Re-read
content = '\n'.join(lines)
lines = content.split('\n')

# ═══════════════════════════════════════════════════════════════════════════════
# 9. Add WhatsApp confirmation messages to response (after email confirmations)
# ═══════════════════════════════════════════════════════════════════════════════

# Find where created_emails are appended to response
email_confirm = find_line("for em in created_emails:")
if email_confirm != -1:
    # Find the end of the email confirmation block
    ec_end = email_confirm + 1
    while ec_end < len(lines) and (lines[ec_end].strip().startswith("text +=") or lines[ec_end].strip().startswith("if ") or lines[ec_end].strip().startswith("else") or not lines[ec_end].strip()):
        ec_end += 1

    wa_confirm = '''
        for wa in created_whatsapps:
            if wa['ok']:
                text += '\\n\\n*WhatsApp geoeffnet — Nachricht an ' + wa['to'] + ' ist vorausgefuellt. Bitte manuell absenden.*'
            else:
                text += '\\n\\n*WhatsApp-Fehler: ' + wa.get('error', 'Unbekannt') + '*'
'''
    lines.insert(ec_end, wa_confirm)
    changes.append(f"Added WhatsApp confirmation messages at line {ec_end}")

# Re-read
content = '\n'.join(lines)
lines = content.split('\n')

# ═══════════════════════════════════════════════════════════════════════════════
# 10. Add /send_whatsapp_draft API route (after /send_email_draft route)
# ═══════════════════════════════════════════════════════════════════════════════

sed_route = find_line("def send_email_draft_route():")
if sed_route != -1:
    # Find end of send_email_draft_route
    sed_end = sed_route + 1
    while sed_end < len(lines):
        stripped = lines[sed_end].lstrip()
        indent = len(lines[sed_end]) - len(stripped)
        if indent == 0 and stripped and not stripped.startswith('#'):
            break
        sed_end += 1

    wa_route = '''
@app.route('/send_whatsapp_draft', methods=['POST'])
def send_whatsapp_draft_route():
    session_id = request.json.get('session_id', 'default') if request.is_json else 'default'
    state = get_session(session_id)
    try:
        spec = request.json
        agent_name = state.get('agent', 'standard')
        to_name, phone = send_whatsapp_draft(spec, agent_name)
        return jsonify({'ok': True, 'to': to_name, 'phone': phone})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})

'''
    lines.insert(sed_end, wa_route)
    changes.append(f"Added /send_whatsapp_draft route at line {sed_end}")

# ═══════════════════════════════════════════════════════════════════════════════
# WRITE BACK
# ═══════════════════════════════════════════════════════════════════════════════

content = '\n'.join(lines)

with open(FILEPATH, 'w') as f:
    f.write(content)

print(f"Patched {FILEPATH}")
print(f"Lines: {original_len} -> {len(lines)}")
print(f"Changes ({len(changes)}):")
for c in changes:
    print(f"  - {c}")
