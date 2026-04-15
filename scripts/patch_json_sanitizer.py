#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Patch web_server.py:
Add JSON sanitizer for CREATE_FILE blocks to handle malformed JSON from LLMs.
Common issues: single quotes, trailing commas, unquoted keys, markdown fences.
"""

filepath = '/Users/moritzcremer/AssistantDev/src/web_server.py'

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

changes = 0

# =============================================================
# 1. Add sanitize_json helper function
#    Insert right before the first create_docx_from_spec
# =============================================================

old_docx_start = "def create_docx_from_spec(spec):"
# Only insert before the FIRST occurrence
first_idx = content.find(old_docx_start)
if first_idx == -1:
    print("ERROR: create_docx_from_spec not found!")
    exit(1)

sanitizer_func = '''def sanitize_llm_json(raw):
    """Sanitize JSON from LLM output that may have single quotes, trailing commas, etc."""
    import re as _sre
    s = raw.strip()
    # Remove markdown code fences
    if s.startswith('```'):
        s = _sre.sub(r'^```\\w*\\n?', '', s)
        s = _sre.sub(r'\\n?```$', '', s)
        s = s.strip()
    # Try standard JSON first
    try:
        import json as _sjson
        return _sjson.loads(s)
    except Exception:
        pass
    # Fix single quotes → double quotes (careful with apostrophes in text)
    # Strategy: replace single-quoted keys and values
    try:
        import ast
        parsed = ast.literal_eval(s)
        return parsed
    except Exception:
        pass
    # Manual fixes: trailing commas before } or ]
    s2 = _sre.sub(r',\\s*([}\\]])', r'\\1', s)
    # Replace single quotes with double quotes (simple approach)
    s2 = s2.replace("'", '"')
    try:
        import json as _sjson
        return _sjson.loads(s2)
    except Exception:
        pass
    # Last resort: raise the original error
    import json as _sjson
    return _sjson.loads(raw)


'''

# Insert before the first create_docx_from_spec
content = content[:first_idx] + sanitizer_func + content[first_idx:]
print("1. Inserted sanitize_llm_json helper function")
changes += 1

# =============================================================
# 2. Replace json.loads(json_str) with sanitize_llm_json(json_str)
#    in the CREATE_FILE parsing block
# =============================================================

# The CREATE_FILE parsing block uses json.loads(json_str) — but we need to be
# specific because json.loads is used in many places
old_parse = """        # Parse CREATE_FILE
        for full_block, ftype, json_str in extract_blocks(text, 'CREATE_FILE'):
            try:
                spec = json.loads(json_str)"""

new_parse = """        # Parse CREATE_FILE
        for full_block, ftype, json_str in extract_blocks(text, 'CREATE_FILE'):
            try:
                spec = sanitize_llm_json(json_str)"""

count = content.count(old_parse)
if count > 0:
    content = content.replace(old_parse, new_parse)
    print(f"2. Replaced json.loads with sanitize_llm_json in CREATE_FILE parsing ({count})")
    changes += count
else:
    print("WARNING: CREATE_FILE parsing block not found")

# =============================================================
# 3. Also fix the error message to be more helpful
# =============================================================

old_error = """            except Exception as fe:
                text = text.replace(full_block, '[Datei-Erstellung fehlgeschlagen: ' + str(fe) + ']')"""

new_error = """            except Exception as fe:
                err_msg = str(fe)
                if 'double quotes' in err_msg or 'Expecting' in err_msg:
                    err_msg = 'JSON-Format ungueltig. Bitte versuche es erneut.'
                text = text.replace(full_block, f'\\n*Datei-Erstellung fehlgeschlagen: {err_msg}*\\n')"""

count = content.count(old_error)
if count > 0:
    content = content.replace(old_error, new_error)
    print(f"3. Improved error message for CREATE_FILE ({count})")
    changes += count

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"\nTotal changes: {changes}")
print("DONE")
