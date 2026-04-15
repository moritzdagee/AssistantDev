#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Patch web_server.py for:
1. LLM Provider + Model display in every assistant response signature
2. Atomic save with immediate user-message save
"""

filepath = '/Users/moritzcremer/AssistantDev/src/web_server.py'

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

changes = 0

# =============================================================
# 1a: Add PROVIDER_DISPLAY and MODEL_DISPLAY mappings
# =============================================================

adapters_marker = "\nADAPTERS = {"
if adapters_marker not in content:
    print("ERROR: ADAPTERS marker not found!")
    exit(1)

mapping_block = """
# Human-readable provider names
PROVIDER_DISPLAY = {
    'anthropic': 'Anthropic',
    'openai': 'OpenAI',
    'mistral': 'Mistral',
    'gemini': 'Google',
    'perplexity': 'Perplexity',
}

# Human-readable model names
MODEL_DISPLAY = {
    'claude-sonnet-4-6': 'Claude Sonnet 4.6',
    'claude-opus-4-6': 'Claude Opus 4.6',
    'claude-haiku-4-5': 'Claude Haiku 4.5',
    'claude-sonnet-4-20250514': 'Claude Sonnet 4',
    'claude-3-5-sonnet-20241022': 'Claude 3.5 Sonnet',
    'gpt-4o': 'GPT-4o',
    'gpt-4o-mini': 'GPT-4o Mini',
    'o1': 'o1',
    'o1-mini': 'o1 Mini',
    'mistral-large-latest': 'Mistral Large',
    'mistral-small-latest': 'Mistral Small',
    'open-mistral-nemo': 'Mistral Nemo',
    'gemini-2.0-flash': 'Gemini 2.0 Flash',
    'gemini-2.5-pro': 'Gemini 2.5 Pro',
    'gemini-2.5-flash': 'Gemini 2.5 Flash',
    'gemini-1.5-pro': 'Gemini 1.5 Pro',
    'sonar': 'Sonar',
    'sonar-pro': 'Sonar Pro',
    'sonar-reasoning': 'Sonar Reasoning',
    'sonar-reasoning-pro': 'Sonar Reasoning Pro',
    'sonar-deep-research': 'Sonar Deep Research',
}
"""

# Only insert once before the FIRST ADAPTERS
content = content.replace(adapters_marker, mapping_block + adapters_marker, 1)
print("1a: Inserted PROVIDER_DISPLAY + MODEL_DISPLAY mappings")
changes += 1

# =============================================================
# 1b: Add provider_display + model_display to main chat response
# =============================================================

old_main_response = """        return {
            'response': text,
            'model_name': model_name,
            'auto_loaded': auto_loaded_names,
            'auto_search_info': auto_search_info,
            'agent': state['agent'],"""

new_main_response = """        return {
            'response': text,
            'model_name': model_name,
            'provider_display': PROVIDER_DISPLAY.get(provider_key, provider_key),
            'model_display': MODEL_DISPLAY.get(model_id, model_name),
            'auto_loaded': auto_loaded_names,
            'auto_search_info': auto_search_info,
            'agent': state['agent'],"""

count = content.count(old_main_response)
if count == 0:
    print("ERROR: Main response block not found!")
    exit(1)
content = content.replace(old_main_response, new_main_response)
print(f"1b: Added provider_display + model_display to main chat response ({count})")
changes += count

# =============================================================
# 1c: Add to sub-agent (execute_delegation) response
# =============================================================

old_sub_response = """    return {
        'response': response_text,
        'model_name': model_name,
        'delegated_to': sub_agent_name,
        'delegated_display': display_name,
    }"""

new_sub_response = """    return {
        'response': response_text,
        'model_name': model_name,
        'provider_display': PROVIDER_DISPLAY.get(provider_key, provider_key),
        'model_display': MODEL_DISPLAY.get(model_id, model_name),
        'delegated_to': sub_agent_name,
        'delegated_display': display_name,
    }"""

count = content.count(old_sub_response)
if count > 0:
    content = content.replace(old_sub_response, new_sub_response)
    print(f"1c: Added to sub-agent response ({count})")
    changes += count

# Also handle the delegation return in main chat route
old_deleg_return = """                return {
                    'response': deleg_result['response'],
                    'model_name': model_name,"""

new_deleg_return = """                return {
                    'response': deleg_result['response'],
                    'model_name': model_name,
                    'provider_display': PROVIDER_DISPLAY.get(state.get('provider', 'anthropic'), state.get('provider', '')),
                    'model_display': MODEL_DISPLAY.get(state.get('model_id', ''), model_name),"""

count = content.count(old_deleg_return)
if count > 0:
    content = content.replace(old_deleg_return, new_deleg_return)
    print(f"1c2: Added to delegation return ({count})")
    changes += count

# =============================================================
# 1d: Update Frontend — addMessage call
# =============================================================

old_call = "  addMessage('assistant', data.response, data.model_name);"
new_call = "  addMessage('assistant', data.response, data.model_name, data.provider_display, data.model_display);"

count = content.count(old_call)
if count > 0:
    content = content.replace(old_call, new_call)
    print(f"1d: Updated addMessage call ({count})")
    changes += count

# =============================================================
# 1e: Update addMessage function — use literal middle dot
# =============================================================

# The middle dot is a literal · (U+00B7) in the source
middot = '\u00b7'

old_fn = f"function addMessage(role, text, modelName) {{\n  var msgs = document.getElementById('messages');\n  var div = document.createElement('div');\n  div.className = 'msg ' + role;\n  var time = new Date().toLocaleTimeString('de-DE', {{hour:'2-digit', minute:'2-digit'}});\n  var meta = time + (modelName ? ' {middot} ' + modelName : '');\n  if (role === 'assistant') {{\n    div.innerHTML = '<div class=\"bubble markdown-rendered\">' + renderMessageContent(text) + '</div><div class=\"meta\">' + meta + '</div>';"

new_fn = f"function addMessage(role, text, modelName, providerDisplay, modelDisplay) {{\n  var msgs = document.getElementById('messages');\n  var div = document.createElement('div');\n  div.className = 'msg ' + role;\n  var time = new Date().toLocaleTimeString('de-DE', {{hour:'2-digit', minute:'2-digit'}});\n  var meta = time;\n  if (providerDisplay && modelDisplay) {{\n    meta += ' {middot} <span style=\"color:#888;font-style:italic\">' + escHtml(providerDisplay) + ' / ' + escHtml(modelDisplay) + '</span>';\n  }} else if (modelName) {{\n    meta += ' {middot} ' + escHtml(modelName);\n  }}\n  if (role === 'assistant') {{\n    div.innerHTML = '<div class=\"bubble markdown-rendered\">' + renderMessageContent(text) + '</div><div class=\"meta\">' + meta + '</div>';"

count = content.count(old_fn)
if count == 0:
    print("ERROR: addMessage function not found! Trying alternate match...")
    # Debug: print what we're looking for
    import re
    m = re.search(r'function addMessage\(role, text, modelName\)', content)
    if m:
        print(f"  Found at pos {m.start()}, context: {repr(content[m.start():m.start()+200])}")
    exit(1)
content = content.replace(old_fn, new_fn)
print(f"1e: Updated addMessage function ({count})")
changes += count

# =============================================================
# 2a: Atomic writes in auto_save_session
# =============================================================

old_save = """        with open(dateiname, 'w', encoding='utf-8') as f:
            f.write('\\n'.join(lines))
        print(f'[AUTO-SAVE] Session {session_id[:12]} gesichert -> {os.path.basename(dateiname)}')"""

new_save = """        # Atomic write: write to .tmp then rename
        tmp_path = dateiname + '.tmp'
        with open(tmp_path, 'w', encoding='utf-8') as f:
            f.write('\\n'.join(lines))
        os.replace(tmp_path, dateiname)
        print(f'[AUTO-SAVE] Session {session_id[:12]} gesichert -> {os.path.basename(dateiname)}')"""

count = content.count(old_save)
if count > 0:
    content = content.replace(old_save, new_save)
    print(f"2a: Atomic writes in auto_save_session ({count})")
    changes += count

# =============================================================
# 2b: Immediate save when user message is received
# =============================================================

old_user_append = """    state['verlauf'].append({'role': 'user', 'content': user_content})
    try:
        config = load_models()
        provider_key = state.get('provider', 'anthropic')
        model_id = state.get('model_id', 'claude-sonnet-4-6')"""

new_user_append = """    state['verlauf'].append({'role': 'user', 'content': user_content})
    # Sofort-Save: User-Nachricht sofort sichern (auch wenn Antwort noch aussteht)
    for _sid_imm, _st_imm in sessions.items():
        if _st_imm is state:
            auto_save_session(_sid_imm)
            break
    try:
        config = load_models()
        provider_key = state.get('provider', 'anthropic')
        model_id = state.get('model_id', 'claude-sonnet-4-6')"""

count = content.count(old_user_append)
if count > 0:
    content = content.replace(old_user_append, new_user_append)
    print(f"2b: Immediate save on user message ({count})")
    changes += count

# =============================================================
# 2c: Atomic write for new_conversation
# =============================================================

old_new_conv = """    dateiname = os.path.join(state['speicher'], 'konversation_' + datum + '.txt')
    with open(dateiname, 'w') as f:
        f.write('Agent: ' + name + '\\nDatum: ' + datum + '\\n\\n')
    state['verlauf'] = []
    state['dateiname'] = dateiname"""

new_new_conv = """    dateiname = os.path.join(state['speicher'], 'konversation_' + datum + '.txt')
    tmp_path = dateiname + '.tmp'
    with open(tmp_path, 'w') as f:
        f.write('Agent: ' + name + '\\nDatum: ' + datum + '\\n\\n')
    os.replace(tmp_path, dateiname)
    state['verlauf'] = []
    state['dateiname'] = dateiname"""

count = content.count(old_new_conv)
if count > 0:
    content = content.replace(old_new_conv, new_new_conv)
    print(f"2c: Atomic write for new_conversation ({count})")
    changes += count

# =============================================================
# 2d: Atomic write for agent init
# =============================================================

old_agent_init = """    else:
        dateiname = os.path.join(speicher, 'konversation_' + datum + '.txt')
    with open(dateiname, 'w') as f:
        f.write('Agent: ' + name + '\\nDatum: ' + datum + '\\n\\n')

    # Add file creation capability to system prompt"""

new_agent_init = """    else:
        dateiname = os.path.join(speicher, 'konversation_' + datum + '.txt')
    tmp_path = dateiname + '.tmp'
    with open(tmp_path, 'w') as f:
        f.write('Agent: ' + name + '\\nDatum: ' + datum + '\\n\\n')
    os.replace(tmp_path, dateiname)

    # Add file creation capability to system prompt"""

count = content.count(old_agent_init)
if count > 0:
    content = content.replace(old_agent_init, new_agent_init)
    print(f"2d: Atomic write for agent init ({count})")
    changes += count

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"\nTotal changes: {changes}")
print("DONE")
