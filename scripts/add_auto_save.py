#!/usr/bin/env python3
"""
Add auto_save_session + atexit/SIGTERM handlers to web_server.py.
"""

FPATH = "/Users/moritzcremer/AssistantDev/src/web_server.py"

with open(FPATH, "r") as f:
    content = f.read()

original_len = len(content)
print(f"Original: {original_len} chars")

# ============================================================================
# STEP 1: Add auto_save_session function after cleanup_old_sessions
# ============================================================================

old_cleanup = """def cleanup_old_sessions():
    cutoff = _time.time() - (24 * 60 * 60)
    to_delete = [sid for sid, s in sessions.items() if s.get('last_active', 0) < cutoff]
    for sid in to_delete:
        del sessions[sid]"""

new_cleanup = """def cleanup_old_sessions():
    cutoff = _time.time() - (24 * 60 * 60)
    to_delete = [sid for sid, s in sessions.items() if s.get('last_active', 0) < cutoff]
    for sid in to_delete:
        try:
            auto_save_session(sid)
        except Exception:
            pass
        del sessions[sid]


def auto_save_session(session_id):
    \"\"\"Auto-save the full conversation of a session to its konversation file.
    Overwrites the file with the complete conversation (header + all messages).
    Silent fail — logs errors but never raises.\"\"\"
    try:
        if session_id not in sessions:
            return
        st = sessions[session_id]
        if not st.get('agent') or not st.get('verlauf') or not st.get('dateiname'):
            return
        dateiname = st['dateiname']
        agent = st['agent']
        provider_key = st.get('provider', 'anthropic')
        model_id = st.get('model_id', 'claude-sonnet-4-6')

        # Build full file content: header + all messages
        # Extract date from dateiname (konversation_2026-04-06_08-45.txt)
        import re
        basename = os.path.basename(dateiname).replace('.txt', '').replace('konversation_', '')
        lines = ['Agent: ' + agent, 'Datum: ' + basename, '']

        for i, m in enumerate(st['verlauf']):
            role = m.get('role', '')
            text = m.get('content', '')
            if isinstance(text, list):
                # Vision content — extract text parts
                text = ' '.join(p.get('text', '') for p in text if isinstance(p, dict) and p.get('type') == 'text')
            if role == 'user':
                lines.append('[' + provider_key + '/' + model_id + ']')
                lines.append('Du: ' + text)
            elif role == 'assistant':
                lines.append('Assistant: ' + text)
                lines.append('')  # blank line after each exchange

        with open(dateiname, 'w', encoding='utf-8') as f:
            f.write('\\n'.join(lines))
        print(f'[AUTO-SAVE] Session {session_id[:12]} gesichert -> {os.path.basename(dateiname)}')
    except Exception as e:
        print(f'[AUTO-SAVE] Fehler bei {session_id[:12]}: {e}')"""

c = content.count(old_cleanup)
print(f"cleanup_old_sessions: {c}")
content = content.replace(old_cleanup, new_cleanup)


# ============================================================================
# STEP 2: Add auto_save_session call at end of process_single_message
# (after the return dict is built, just before the return)
# ============================================================================

# The return block at end of process_single_message (successful path)
old_return = """        state['verlauf'].append({'role': 'assistant', 'content': text})
        with open(state['dateiname'], 'a') as f:
            f.write('[' + provider_key + '/' + model_id + ']\\nDu: ' + msg + '\\nAssistant: ' + text + '\\n\\n')
        return {
            'response': text,
            'model_name': model_name,
            'auto_loaded': auto_loaded_names,
            'auto_search_info': auto_search_info,
            'agent': state['agent'],
            'created_files': created_files,
            'created_emails': created_emails,
        }
    except Exception as e:
        state['verlauf'].pop()
        raise"""

new_return = """        state['verlauf'].append({'role': 'assistant', 'content': text})
        with open(state['dateiname'], 'a') as f:
            f.write('[' + provider_key + '/' + model_id + ']\\nDu: ' + msg + '\\nAssistant: ' + text + '\\n\\n')
        # Auto-save full session after each message
        for _sid, _st in sessions.items():
            if _st is state:
                auto_save_session(_sid)
                break
        return {
            'response': text,
            'model_name': model_name,
            'auto_loaded': auto_loaded_names,
            'auto_search_info': auto_search_info,
            'agent': state['agent'],
            'created_files': created_files,
            'created_emails': created_emails,
        }
    except Exception as e:
        state['verlauf'].pop()
        raise"""

c = content.count(old_return)
print(f"process_single_message return block: {c}")
content = content.replace(old_return, new_return)


# Also add auto_save after delegation return in process_single_message
old_deleg_return = """                return {
                    'response': deleg_result['response'],
                    'model_name': deleg_result.get('model_name', ''),
                    'auto_loaded': auto_loaded_names,
                    'auto_search_info': auto_search_info,
                    'agent': state['agent'],
                    'created_files': [],
                    'created_emails': [],
                    'delegated_to': deleg_result.get('delegated_to', ''),
                    'delegated_display': deleg_result.get('delegated_display', ''),
                }"""

new_deleg_return = """                # Auto-save after delegation
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
                    'delegated_to': deleg_result.get('delegated_to', ''),
                    'delegated_display': deleg_result.get('delegated_display', ''),
                }"""

c = content.count(old_deleg_return)
print(f"delegation return block: {c}")
content = content.replace(old_deleg_return, new_deleg_return)


# ============================================================================
# STEP 3: Add auto_save in process_queue_worker after each completed message
# ============================================================================

old_queue_append = """            result['queue_id'] = item['id']
            result['original_message'] = item['message'][:50]
            with queue_lock:
                state['completed_responses'].append(result)"""

new_queue_append = """            result['queue_id'] = item['id']
            result['original_message'] = item['message'][:50]
            with queue_lock:
                state['completed_responses'].append(result)
            # Auto-save after queue item processed
            for _sid, _st in sessions.items():
                if _st is state:
                    auto_save_session(_sid)
                    break"""

c = content.count(old_queue_append)
print(f"queue worker append: {c}")
content = content.replace(old_queue_append, new_queue_append)


# ============================================================================
# STEP 4: Add atexit + SIGTERM handler
# ============================================================================

old_startup_block = """    # Cleanup old sessions every hour
    def session_cleanup_loop():
        import time
        while True:
            time.sleep(3600)
            cleanup_old_sessions()
    threading.Thread(target=session_cleanup_loop, daemon=True).start()"""

new_startup_block = """    # Cleanup old sessions every hour
    def session_cleanup_loop():
        import time
        while True:
            time.sleep(3600)
            cleanup_old_sessions()
    threading.Thread(target=session_cleanup_loop, daemon=True).start()

    # Save all sessions on shutdown (pkill, Ctrl+C, restart)
    import atexit, signal
    def _save_all_sessions_on_exit():
        print('[AUTO-SAVE] Shutdown erkannt — sichere alle Sessions...')
        for sid in list(sessions.keys()):
            try:
                auto_save_session(sid)
                print(f'[AUTO-SAVE] Session {sid[:12]} gesichert')
            except Exception as e:
                print(f'[AUTO-SAVE] Fehler bei {sid[:12]}: {e}')
    atexit.register(_save_all_sessions_on_exit)
    signal.signal(signal.SIGTERM, lambda sig, frame: (_save_all_sessions_on_exit(), exit(0)))"""

c = content.count(old_startup_block)
print(f"startup block: {c}")
content = content.replace(old_startup_block, new_startup_block)


# ============================================================================
# WRITE
# ============================================================================

print(f"\nNew: {len(content)} chars (delta: +{len(content) - original_len})")
with open(FPATH, "w") as f:
    f.write(content)
print("DONE")
