#!/usr/bin/env python3
"""Fix: Patch 3 der Kalender-Integration (Auto-Inject) separat anwenden."""
import os, sys
WS = os.path.expanduser("~/AssistantDev/src/web_server.py")
MARKER = "CALENDAR_INTEGRATION_V1: Automatisch Kalender-Daten injizieren"

OLD = """    full_text = msg + text_ctx if text_ctx else msg

    provider_key = state.get('provider', 'anthropic')"""

NEW = """    full_text = msg + text_ctx if text_ctx else msg

    # CALENDAR_INTEGRATION_V1: Automatisch Kalender-Daten injizieren wenn Intent erkannt
    if _has_calendar_intent(msg):
        try:
            _cal_events, _cal_cals, _cal_err = get_calendar_events(days_back=1, days_ahead=7)
            if _cal_events:
                _cal_ctx = format_calendar_context(_cal_events)
                full_text = full_text + '\\n\\n' + _cal_ctx
                print(f"[CALENDAR] {len(_cal_events)} Events injiziert fuer Intent in: {msg[:50]}", flush=True)
            elif _cal_err:
                print(f"[CALENDAR] Fehler: {_cal_err}", flush=True)
        except Exception as _cal_ex:
            print(f"[CALENDAR] Exception: {_cal_ex}", flush=True)

    provider_key = state.get('provider', 'anthropic')"""

src = open(WS).read()
if MARKER in src:
    print("Schon angewendet.")
    sys.exit(0)
c = src.count(OLD)
if c != 1:
    print(f"FEHLER: {c} Vorkommen (erwarte 1)")
    sys.exit(2)
open(WS, 'w').write(src.replace(OLD, NEW, 1))
print("OK: Kalender Auto-Inject eingefuegt")
