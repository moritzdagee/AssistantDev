#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Patch web_server.py:
1. auto_save_session: Save kontext_items as [KONTEXT_DATEIEN] block
2. load_conversation: Parse and restore kontext_items
3. Frontend: Extend addCtxItem display to 40 chars + tooltip
"""

filepath = '/Users/moritzcremer/AssistantDev/src/web_server.py'

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

changes = 0

# =============================================================
# 1. auto_save_session: Append context files block
# =============================================================

old_save_build = """        # Atomic write: write to .tmp then rename
        tmp_path = dateiname + '.tmp'
        with open(tmp_path, 'w', encoding='utf-8') as f:
            f.write('\\n'.join(lines))
        os.replace(tmp_path, dateiname)
        print(f'[AUTO-SAVE] Session {session_id[:12]} gesichert -> {os.path.basename(dateiname)}')"""

new_save_build = """        # Append context files block if any are loaded
        ctx_items = st.get('kontext_items', [])
        if ctx_items:
            ctx_entries = []
            for ci in ctx_items:
                entry = {'name': ci.get('name', ''), 'type': 'file'}
                if ci.get('image_b64'):
                    entry['type'] = 'image'
                ctx_entries.append(entry)
            lines.append('')
            lines.append('[KONTEXT_DATEIEN:' + json.dumps(ctx_entries, ensure_ascii=False) + ']')

        # Atomic write: write to .tmp then rename
        tmp_path = dateiname + '.tmp'
        with open(tmp_path, 'w', encoding='utf-8') as f:
            f.write('\\n'.join(lines))
        os.replace(tmp_path, dateiname)
        print(f'[AUTO-SAVE] Session {session_id[:12]} gesichert -> {os.path.basename(dateiname)}')"""

count = content.count(old_save_build)
if count > 0:
    content = content.replace(old_save_build, new_save_build)
    print(f"1. auto_save: Added KONTEXT_DATEIEN block ({count})")
    changes += count
else:
    print("ERROR: auto_save atomic write block not found")

# =============================================================
# 2. load_conversation: Parse KONTEXT_DATEIEN and restore
# =============================================================

old_load_resume = """        # Resume mode: set session state so new messages continue in this file
        if resume and state.get('agent'):
            state['dateiname'] = fpath
            state['verlauf'] = messages[:]
            state['kontext_items'] = []
            state['session_files'] = []"""

new_load_resume = """        # Parse KONTEXT_DATEIEN block if present
        restored_ctx = []
        missing_ctx = []
        import re as _ctx_re
        ctx_match = _ctx_re.search(r'\\[KONTEXT_DATEIEN:(\\[.*?\\])\\]', raw)
        if ctx_match:
            try:
                ctx_entries = json.loads(ctx_match.group(1))
                for entry in ctx_entries:
                    fname = entry.get('name', '')
                    if not fname:
                        continue
                    # Try to find the file in agent memory
                    ctx_fpath = os.path.join(speicher, 'memory', fname)
                    if os.path.exists(ctx_fpath):
                        try:
                            with open(ctx_fpath, 'r', encoding='utf-8', errors='replace') as cf:
                                ctx_content = cf.read(50000)
                            restored_ctx.append({'name': fname, 'content': ctx_content})
                        except Exception:
                            missing_ctx.append(fname)
                    else:
                        missing_ctx.append(fname)
            except Exception as ctx_err:
                print(f'[LOAD] KONTEXT_DATEIEN parse error: {ctx_err}')

        # Resume mode: set session state so new messages continue in this file
        if resume and state.get('agent'):
            state['dateiname'] = fpath
            state['verlauf'] = messages[:]
            state['kontext_items'] = restored_ctx[:]
            state['session_files'] = [c['name'] for c in restored_ctx]"""

count = content.count(old_load_resume)
if count > 0:
    content = content.replace(old_load_resume, new_load_resume)
    print(f"2. load_conversation: Added KONTEXT_DATEIEN restore ({count})")
    changes += count
else:
    print("ERROR: load_conversation resume block not found")

# =============================================================
# 3. load_conversation: Add restored/missing context to response
# =============================================================

old_load_return = """        return jsonify({'ok': True, 'messages': messages, 'resumed': bool(resume),
                        'provider': conv_provider, 'model_id': conv_model_id})"""

new_load_return = """        return jsonify({'ok': True, 'messages': messages, 'resumed': bool(resume),
                        'provider': conv_provider, 'model_id': conv_model_id,
                        'restored_ctx': [c['name'] for c in restored_ctx],
                        'missing_ctx': missing_ctx})"""

count = content.count(old_load_return)
if count > 0:
    content = content.replace(old_load_return, new_load_return)
    print(f"3. load_conversation: Added restored/missing ctx to response ({count})")
    changes += count

# =============================================================
# 4. Frontend addCtxItem: Extend to 40 chars + tooltip
# =============================================================

old_addctx = """  const span = document.createElement('span');
  span.textContent = icon + ' ' + name.substring(0, 30) + (name.length > 30 ? '...' : '');"""

new_addctx = """  const span = document.createElement('span');
  span.textContent = icon + ' ' + name.substring(0, 40) + (name.length > 40 ? '...' : '');
  div.title = name;"""

count = content.count(old_addctx)
if count > 0:
    content = content.replace(old_addctx, new_addctx)
    print(f"4. Frontend addCtxItem: Extended to 40 chars + tooltip ({count})")
    changes += count

# =============================================================
# 5. Frontend loadConversation: Restore context items from response
# =============================================================

old_load_status = """    addStatusMsg('Konversation geladen — deine naechste Nachricht wird hier fortgesetzt.');
  }
}"""

new_load_status = """    // Restore context files from saved conversation
    document.getElementById('ctx-items').innerHTML = '';
    if (data.restored_ctx && data.restored_ctx.length) {
      data.restored_ctx.forEach(n => addCtxItem(n, 'file', true));
      addStatusMsg('Konversation geladen — ' + data.restored_ctx.length + ' Kontext-Datei(en) wiederhergestellt.');
    } else {
      addStatusMsg('Konversation geladen — deine naechste Nachricht wird hier fortgesetzt.');
    }
    if (data.missing_ctx && data.missing_ctx.length) {
      addStatusMsg('\\u26A0 ' + data.missing_ctx.length + ' Kontext-Datei(en) nicht mehr verfuegbar: ' + data.missing_ctx.join(', '));
    }
  }
}"""

count = content.count(old_load_status)
if count > 0:
    content = content.replace(old_load_status, new_load_status)
    print(f"5. Frontend loadConversation: Added context restore ({count})")
    changes += count

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"\nTotal changes: {changes}")
print("DONE")
