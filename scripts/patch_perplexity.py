#!/usr/bin/env python3
"""
Patch web_server.py for two Perplexity bugs:
1. max_tokens: increase from 4096 to 8000 for Perplexity models
2. Citations: extract and append as clickable Markdown links
"""

filepath = '/Users/moritzcremer/AssistantDev/src/web_server.py'

with open(filepath, 'r') as f:
    content = f.read()

changes = 0

# =============================================================
# Both bugs: Replace the entire call_perplexity function
# It exists twice (duplicated block), so replace_all
# =============================================================

old_func = """def call_perplexity(api_key, model_id, system_prompt, messages):
    import openai
    client = openai.OpenAI(api_key=api_key, base_url="https://api.perplexity.ai")
    pplx_messages = [{"role": "system", "content": system_prompt}] + messages
    r = client.chat.completions.create(model=model_id, messages=pplx_messages, max_tokens=4096)
    return r.choices[0].message.content"""

new_func = """def call_perplexity(api_key, model_id, system_prompt, messages):
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

count = content.count(old_func)
if count == 0:
    print("ERROR: call_perplexity function not found!")
    exit(1)

content = content.replace(old_func, new_func)
print(f"Patched call_perplexity: {count} occurrence(s)")
print(f"  - max_tokens: 4096 -> 8000")
print(f"  - Citations: now extracted and appended as Markdown links")
changes += count

with open(filepath, 'w') as f:
    f.write(content)

print(f"\nTotal: {changes} function(s) replaced")
print("DONE")
