#!/usr/bin/env python3
"""
Incremental Indexing: Nachhaltige Lösung für automatische Index-Updates.

1. web_server.py: Periodischer Background-Thread (alle 5 Min) fuer alle Agenten
2. search_engine.py: Neue Funktion update_all_indexes()
3. email_watcher.py: Index-Update nach jedem verarbeiteten File
"""

import os

# ============================================================================
# 1. search_engine.py: Neue Funktion update_all_indexes()
# ============================================================================
se_path = os.path.expanduser("~/AssistantDev/src/search_engine.py")
with open(se_path, 'r') as f:
    se = f.read()

# Add update_all_indexes() after build_global_index_async()
old_se = """def build_global_index_async():
    \"\"\"Build/update global index in a background thread.\"\"\"
    def _build():
        get_global_index()
    t = threading.Thread(target=_build, daemon=True)
    t.start()"""

new_se = """def build_global_index_async():
    \"\"\"Build/update global index in a background thread.\"\"\"
    def _build():
        get_global_index()
    t = threading.Thread(target=_build, daemon=True)
    t.start()


def update_all_indexes():
    \"\"\"Incremental update of all agent indexes + global index.
    Called periodically by the web server background thread.\"\"\"
    datalake = os.path.expanduser("~/Library/Mobile Documents/com~apple~CloudDocs/Downloads shared/claude_datalake")
    if not os.path.exists(datalake):
        return
    total_updated = 0
    for item in os.listdir(datalake):
        agent_path = os.path.join(datalake, item)
        if not os.path.isdir(agent_path):
            continue
        memory_dir = os.path.join(agent_path, 'memory')
        if not os.path.exists(memory_dir):
            continue
        # Skip config, email_inbox etc.
        if item.startswith('.') or item in ('config', 'email_inbox', 'claude_outputs'):
            continue
        try:
            idx = get_or_build_index(agent_path)
            updated = idx.update_index()
            total_updated += updated
        except Exception as e:
            print(f"Index update error for {item}: {e}")
    # Also update global index
    try:
        gi = get_global_index()
        gi.update_index()
    except Exception as e:
        print(f"Global index update error: {e}")
    if total_updated > 0:
        print(f"[INDEX] Periodischer Update: {total_updated} neue/geaenderte Dateien indexiert")
    return total_updated


def index_single_file(speicher_path, filename):
    \"\"\"Index a single file immediately. Used by email_watcher after saving.\"\"\"
    try:
        idx = get_or_build_index(speicher_path)
        idx.add_file(filename)
    except Exception as e:
        print(f"Single file index error ({filename}): {e}")"""

assert old_se in se, "Could not find build_global_index_async in search_engine.py"
se = se.replace(old_se, new_se)

with open(se_path, 'w') as f:
    f.write(se)
print("✅ search_engine.py: update_all_indexes() + index_single_file() hinzugefuegt")

# ============================================================================
# 2. web_server.py: Import + Background-Thread
# ============================================================================
ws_path = os.path.expanduser("~/AssistantDev/src/web_server.py")
with open(ws_path, 'r') as f:
    ws = f.read()

# 2a. Update import to include new functions
old_import = "from search_engine import auto_search, format_search_feedback, build_index_async, build_global_index_async, detect_global_trigger"
new_import = "from search_engine import auto_search, format_search_feedback, build_index_async, build_global_index_async, detect_global_trigger, update_all_indexes"
assert old_import in ws, "Could not find search_engine import in web_server.py"
ws = ws.replace(old_import, new_import)

# 2b. Update fallback None assignments
old_fallback = """    build_index_async = None
    build_global_index_async = None
    detect_global_trigger = None"""
new_fallback = """    build_index_async = None
    build_global_index_async = None
    detect_global_trigger = None
    update_all_indexes = None"""
assert old_fallback in ws, "Could not find fallback None assignments"
ws = ws.replace(old_fallback, new_fallback)

# 2c. Add periodic index update thread in __main__ block
old_main = """    # Build global search index in background at startup
    if build_global_index_async:
        build_global_index_async()"""

new_main = """    # Build global search index in background at startup
    if build_global_index_async:
        build_global_index_async()
    # Periodic incremental index update (every 5 minutes)
    def index_update_loop():
        import time
        time.sleep(60)  # Wait 1 min after startup before first run
        while True:
            try:
                if update_all_indexes:
                    update_all_indexes()
            except Exception as e:
                print(f'[INDEX] Periodischer Update Fehler: {e}')
            time.sleep(300)  # Every 5 minutes
    threading.Thread(target=index_update_loop, daemon=True).start()"""

assert old_main in ws, "Could not find global index startup block"
ws = ws.replace(old_main, new_main)

with open(ws_path, 'w') as f:
    f.write(ws)
print("✅ web_server.py: Import + 5-Minuten Background-Thread hinzugefuegt")

# ============================================================================
# 3. email_watcher.py: Index-Update nach jedem verarbeiteten File
# ============================================================================
ew_path = os.path.expanduser("~/AssistantDev/src/email_watcher.py")
with open(ew_path, 'r') as f:
    ew = f.read()

# 3a. Add import at top
old_ew_import = """from email.header import decode_header"""
new_ew_import = """from email.header import decode_header

# Search index integration
try:
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from search_engine import index_single_file
except ImportError:
    index_single_file = None"""
assert old_ew_import in ew, "Could not find email.header import in email_watcher.py"
ew = ew.replace(old_ew_import, new_ew_import, 1)  # Only first occurrence

# 3b. Add index call after writing the email file
old_ew_write = """        with open(os.path.join(memory_dir, email_filename), 'w') as f:
            f.write(content)

        # Anhaenge speichern"""
new_ew_write = """        with open(os.path.join(memory_dir, email_filename), 'w') as f:
            f.write(content)

        # Index aktualisieren
        if index_single_file:
            try:
                index_single_file(os.path.dirname(memory_dir), email_filename)
            except Exception:
                pass

        # Anhaenge speichern"""
assert old_ew_write in ew, "Could not find email file write block in email_watcher.py"
ew = ew.replace(old_ew_write, new_ew_write)

with open(ew_path, 'w') as f:
    f.write(ew)
print("✅ email_watcher.py: Index-Update nach jedem File hinzugefuegt")

print("\n✅ Alle Aenderungen angewendet")
