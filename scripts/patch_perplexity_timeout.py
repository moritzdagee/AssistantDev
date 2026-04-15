#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Patch web_server.py:
1. Modell-spezifische Timeouts fuer Perplexity (300s Deep Research, 180s Reasoning, 120s Standard)
2. Benutzerfreundliche Timeout-Fehlermeldungen
"""

filepath = '/Users/moritzcremer/AssistantDev/src/web_server.py'

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

changes = 0

# =============================================================
# Replace both call_perplexity functions with timeout + error handling
# =============================================================

old_func = """def call_perplexity(api_key, model_id, system_prompt, messages):
    import openai
    import requests as _pplx_req
    client = openai.OpenAI(api_key=api_key, base_url="https://api.perplexity.ai")
    pplx_messages = [{"role": "system", "content": system_prompt}] + messages
    # Use raw requests to access citations field (not exposed by openai SDK)
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": model_id, "messages": pplx_messages, "max_tokens": 8000}
    resp = _pplx_req.post("https://api.perplexity.ai/chat/completions", headers=headers, json=payload, timeout=120)
    data = resp.json()
    if resp.status_code != 200:
        raise Exception(f"Perplexity API Fehler: {data.get('error', {}).get('message', str(data))}")
    text = data["choices"][0]["message"]["content"]
    # Append citations as clickable Markdown links if present
    citations = data.get("citations")
    if citations and isinstance(citations, list) and len(citations) > 0:
        text += "\\n\\n**Quellen:**\\n"
        for i, url in enumerate(citations, 1):
            # Clean display: show domain for readability
            try:
                from urllib.parse import urlparse
                domain = urlparse(url).netloc.replace("www.", "")
            except Exception:
                domain = url[:60]
            text += f"[{i}] [{domain}]({url})\\n"
    return text"""

new_func = """def call_perplexity(api_key, model_id, system_prompt, messages):
    import requests as _pplx_req
    from requests.exceptions import ReadTimeout, ConnectionError as ReqConnectionError

    pplx_messages = [{"role": "system", "content": system_prompt}] + messages
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": model_id, "messages": pplx_messages, "max_tokens": 8000}

    # Model-specific timeouts (connect_timeout, read_timeout)
    PERPLEXITY_TIMEOUTS = {
        'sonar-deep-research': (10, 300),   # Deep Research: bis zu 5 Min
        'sonar-reasoning-pro': (10, 180),   # Reasoning Pro: bis zu 3 Min
        'sonar-reasoning': (10, 180),       # Reasoning: bis zu 3 Min
        'sonar-pro': (10, 120),             # Sonar Pro: 2 Min
        'sonar': (10, 120),                 # Sonar: 2 Min
    }
    timeout = PERPLEXITY_TIMEOUTS.get(model_id, (10, 120))

    MODEL_LABELS = {
        'sonar-deep-research': 'Sonar Deep Research',
        'sonar-reasoning-pro': 'Sonar Reasoning Pro',
        'sonar-reasoning': 'Sonar Reasoning',
        'sonar-pro': 'Sonar Pro',
        'sonar': 'Sonar',
    }
    model_label = MODEL_LABELS.get(model_id, model_id)

    try:
        resp = _pplx_req.post(
            "https://api.perplexity.ai/chat/completions",
            headers=headers, json=payload, timeout=timeout
        )
    except ReadTimeout:
        raise Exception(
            f"Perplexity {model_label} hat zu lange gebraucht (Timeout nach {timeout[1]}s). "
            f"Versuche es erneut oder waehle ein schnelleres Modell."
        )
    except ReqConnectionError:
        raise Exception(
            f"Verbindung zu Perplexity fehlgeschlagen. Pruefe deine Internetverbindung."
        )

    data = resp.json()
    if resp.status_code != 200:
        raise Exception(f"Perplexity API Fehler: {data.get('error', {}).get('message', str(data))}")
    text = data["choices"][0]["message"]["content"]
    # Append citations as clickable Markdown links if present
    citations = data.get("citations")
    if citations and isinstance(citations, list) and len(citations) > 0:
        text += "\\n\\n**Quellen:**\\n"
        for i, url in enumerate(citations, 1):
            try:
                from urllib.parse import urlparse
                domain = urlparse(url).netloc.replace("www.", "")
            except Exception:
                domain = url[:60]
            text += f"[{i}] [{domain}]({url})\\n"
    return text"""

count = content.count(old_func)
if count == 0:
    print("ERROR: call_perplexity function not found!")
    exit(1)
content = content.replace(old_func, new_func)
print(f"Replaced call_perplexity: {count} occurrence(s)")
print(f"  - Timeouts: Deep Research 300s, Reasoning 180s, Standard 120s")
print(f"  - Error handling: user-friendly timeout messages")
changes += count

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"\nTotal: {changes} function(s) replaced")
print("DONE")
