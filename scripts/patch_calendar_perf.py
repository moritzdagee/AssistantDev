#!/usr/bin/env python3
"""Patch: Kalender-Performance — weniger Kalender, laengerer Timeout, Caching."""
import os, sys
WS = os.path.expanduser("~/AssistantDev/src/web_server.py")
src = open(WS).read()

# 1. Weniger Kalender + Cache-Variable
OLD1 = '''_CALENDAR_TARGETS = ["Arbeit", "Privat", "Familie", "Calendar", "Moritz Cremer",
                     "londoncityfox@gmail.com", "moritz@demoscapital.co"]'''
NEW1 = '''_CALENDAR_TARGETS = ["Arbeit", "Privat", "Familie"]
_cal_cache = {'events': [], 'cals': set(), 'ts': 0, 'key': ''}'''
if NEW1 not in src:
    if src.count(OLD1) == 1:
        src = src.replace(OLD1, NEW1)
        print("  [OK] Weniger Kalender + Cache-Variable")
    else:
        print(f"  [SKIP] OLD1 nicht gefunden ({src.count(OLD1)})")

# 2. Timeout 20 -> 45
OLD2 = "capture_output=True, text=True, timeout=20,"
NEW2 = "capture_output=True, text=True, timeout=45,"
if OLD2 in src:
    src = src.replace(OLD2, NEW2)
    print("  [OK] Timeout 20 -> 45")
else:
    print("  [SKIP] Timeout schon geaendert")

# 3. Caching in get_calendar_events — VOR dem AppleScript-Aufruf
OLD3 = '''    target_cals = calendars if calendars else _CALENDAR_TARGETS

    # AppleScript bauen: pro Kalender einen try-Block'''
NEW3 = '''    target_cals = calendars if calendars else _CALENDAR_TARGETS

    # Cache pruefen (120s Gueltigkeitsdauer)
    import time as _cal_time
    cache_key = f"{days_back}:{days_ahead}:{','.join(target_cals)}:{search or ''}"
    if _cal_cache['key'] == cache_key and (_cal_time.time() - _cal_cache['ts']) < 120:
        return list(_cal_cache['events']), set(_cal_cache['cals']), None

    # AppleScript bauen: pro Kalender einen try-Block'''
if OLD3 in src:
    src = src.replace(OLD3, NEW3)
    print("  [OK] Cache-Check eingefuegt")
else:
    print("  [SKIP] Cache-Check schon da")

# 4. Cache-Update nach erfolgreichem Parse (vor dem return)
OLD4 = '''    events.sort(key=lambda e: e['_sort_key'])
    for e in events:
        e.pop('_sort_key', None)
    return events, cals_found, None'''
NEW4 = '''    events.sort(key=lambda e: e['_sort_key'])
    for e in events:
        e.pop('_sort_key', None)
    # Cache aktualisieren
    _cal_cache['events'] = list(events)
    _cal_cache['cals'] = set(cals_found)
    _cal_cache['ts'] = _cal_time.time()
    _cal_cache['key'] = cache_key
    return events, cals_found, None'''
if OLD4 in src:
    src = src.replace(OLD4, NEW4)
    print("  [OK] Cache-Update eingefuegt")
else:
    print("  [SKIP] Cache-Update schon da")

open(WS, 'w').write(src)
print("Done")
