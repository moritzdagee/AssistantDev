#!/usr/bin/env python3
"""Patch email_watcher.py: dual-write processed log to iCloud mirror.
- After local write (~/.emailwatcher_processed.json), also write to BASE/config/email_processed_log.json
- On load: if local is empty/missing, try iCloud mirror
"""
import sys

path = '/Users/moritzcremer/AssistantDev/src/email_watcher.py'
with open(path, 'r') as f:
    content = f.read()

def must_replace(label, old, new):
    global content
    if old not in content:
        print(f"FEHLER bei {label}: Suchstring nicht gefunden!", file=sys.stderr)
        sys.exit(1)
    content = content.replace(old, new, 1)
    print(f"OK: {label}")

# Add mirror path constant after PROCESSED_LOG
must_replace("Add mirror path constant",
'PROCESSED_LOG = os.path.expanduser("~/.emailwatcher_processed.json")\n'
'OWN_ADDRS_CACHE = os.path.expanduser("~/.emailwatcher_own_addresses.json")',
'PROCESSED_LOG = os.path.expanduser("~/.emailwatcher_processed.json")\n'
'# Dual-write mirror in iCloud datalake (for recovery if local is lost)\n'
'PROCESSED_LOG_MIRROR = os.path.join(BASE, "config", "email_processed_log.json")\n'
'OWN_ADDRS_CACHE = os.path.expanduser("~/.emailwatcher_own_addresses.json")')

# Update load_processed with iCloud fallback
must_replace("load_processed: iCloud Fallback",
"def load_processed():\n"
"    if os.path.exists(PROCESSED_LOG):\n"
"        try:\n"
"            with open(PROCESSED_LOG) as f:\n"
"                return set(json.load(f))\n"
"        except Exception:\n"
"            return set()\n"
"    return set()",
"def load_processed():\n"
"    # Primary: local log\n"
"    if os.path.exists(PROCESSED_LOG):\n"
"        try:\n"
"            with open(PROCESSED_LOG) as f:\n"
"                data = json.load(f)\n"
"                if data:\n"
"                    return set(data)\n"
"        except Exception:\n"
"            pass\n"
"    # Fallback: iCloud mirror\n"
"    if os.path.exists(PROCESSED_LOG_MIRROR):\n"
"        try:\n"
"            with open(PROCESSED_LOG_MIRROR) as f:\n"
"                data = json.load(f)\n"
"                if data:\n"
"                    print(f'[WATCHER] Recovered processed log from iCloud mirror ({len(data)} entries)', flush=True)\n"
"                    return set(data)\n"
"        except Exception:\n"
"            pass\n"
"    return set()")

# Update save_processed to dual-write
must_replace("save_processed: dual-write",
"def save_processed(processed):\n"
"    with open(PROCESSED_LOG, 'w') as f:\n"
"        json.dump(list(processed), f)",
"def save_processed(processed):\n"
"    data = list(processed)\n"
"    # Primary: local\n"
"    with open(PROCESSED_LOG, 'w') as f:\n"
"        json.dump(data, f)\n"
"    # Mirror: iCloud (best-effort, don't fail on error)\n"
"    try:\n"
"        os.makedirs(os.path.dirname(PROCESSED_LOG_MIRROR), exist_ok=True)\n"
"        with open(PROCESSED_LOG_MIRROR, 'w') as f:\n"
"            json.dump(data, f)\n"
"    except Exception as e:\n"
"        print(f'[WATCHER] Warning: mirror write failed: {e}', flush=True)")

with open(path, 'w') as f:
    f.write(content)

print("\nAlle Patches erfolgreich angewendet!")
