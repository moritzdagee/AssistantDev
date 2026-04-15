#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Patch web_server.py: Fix Perplexity message alternation error.
Adds a normalization step that merges consecutive same-role messages
before sending to Perplexity API.
"""

filepath = '/Users/moritzcremer/AssistantDev/src/web_server.py'

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

changes = 0

# The old line that builds pplx_messages (exists in both copies)
old_line = '    pplx_messages = [{"role": "system", "content": system_prompt}] + messages'

new_block = '''    # Perplexity requires strictly alternating user/assistant messages after system.
    # Merge consecutive same-role messages to enforce this.
    raw_msgs = list(messages)
    # Remove empty messages
    raw_msgs = [m for m in raw_msgs if m.get('content')]
    # Flatten list-type content (vision messages) to text
    for m in raw_msgs:
        if isinstance(m.get('content'), list):
            m = dict(m)
            m['content'] = ' '.join(
                p.get('text', '') for p in m['content']
                if isinstance(p, dict) and p.get('type') == 'text'
            )
    # Merge consecutive same-role messages
    merged = []
    for m in raw_msgs:
        content_text = m.get('content', '')
        if isinstance(content_text, list):
            content_text = ' '.join(
                p.get('text', '') for p in content_text
                if isinstance(p, dict) and p.get('type') == 'text'
            )
        if not content_text or not content_text.strip():
            continue
        if merged and merged[-1]['role'] == m['role']:
            merged[-1]['content'] += '\\n\\n' + content_text
        else:
            merged.append({'role': m['role'], 'content': content_text})
    # Ensure first non-system message is 'user' (Perplexity requirement)
    if merged and merged[0]['role'] != 'user':
        merged.insert(0, {'role': 'user', 'content': '.'})
    # Ensure last message is 'user' (Perplexity sends to model for completion)
    if merged and merged[-1]['role'] != 'user':
        merged.append({'role': 'user', 'content': '.'})
    pplx_messages = [{"role": "system", "content": system_prompt}] + merged'''

count = content.count(old_line)
if count == 0:
    print("ERROR: pplx_messages line not found!")
    exit(1)

content = content.replace(old_line, new_block)
print(f"Replaced pplx_messages builder: {count} occurrence(s)")
changes += count

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"Total: {changes} changes")
print("DONE")
