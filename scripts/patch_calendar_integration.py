#!/usr/bin/env python3
"""
Patch: Kalender-Integration (Fantastical/Apple Calendar)

1. get_calendar_events() Hilfsfunktion (AppleScript-basiert)
2. /api/calendar Route
3. Auto-Inject Kalender-Daten bei Kalender-Intent im Chat

Alle betroffenen Stellen liegen NACH der duplizierten Zone (>Zeile 1358).
Idempotent via CALENDAR_INTEGRATION_V1 Marker.
"""
import os, sys

WS = os.path.expanduser("~/AssistantDev/src/web_server.py")

def apply(src, old, new, marker, desc):
    if marker in src:
        print(f"  [skip] {desc}: marker vorhanden")
        return src, False
    c = src.count(old)
    if c != 1:
        print(f"  [FAIL] {desc}: {c} Vorkommen (erwarte 1)")
        sys.exit(2)
    print(f"  [OK]   {desc}")
    return src.replace(old, new, 1), True


# ═══════════════════════════════════════════════════════════════════════════
# Patch 1: get_calendar_events() Funktion
# Einfuegen VOR "# ─── STATE (SESSION-BASED)" (nach generate_video)
# ═══════════════════════════════════════════════════════════════════════════

ANCHOR_FUNC = '# ─── STATE (SESSION-BASED) ─────────────────────────────────────────────────────'

NEW_FUNC = '''# ─── CALENDAR INTEGRATION (CALENDAR_INTEGRATION_V1) ────────────────────────────
# AppleScript-basiertes Auslesen von Fantastical/Apple Calendar Events.
# Fantastical teilt den macOS CalendarStore, deshalb funktioniert Apple Calendar
# AppleScript direkt mit Fantastical-Daten.

_CALENDAR_TARGETS = ["Arbeit", "Privat", "Familie", "Calendar", "Moritz Cremer",
                     "londoncityfox@gmail.com", "moritz@demoscapital.co"]

_CALENDAR_INTENT_DE = [
    "kalender", "termin", "termine", "meeting", "meetings", "heute", "morgen",
    "diese woche", "naechste woche", "wann", "agenda", "tagesplan", "zeitplan",
    "verfuegbar", "verfügbar", "frei", "besetzt", "schedule",
]
_CALENDAR_INTENT_EN = [
    "calendar", "schedule", "today", "tomorrow", "appointment", "appointments",
    "meeting", "meetings", "when", "agenda", "free", "busy", "available",
    "this week", "next week",
]
_CALENDAR_KEYWORDS = set(_CALENDAR_INTENT_DE + _CALENDAR_INTENT_EN)


def _has_calendar_intent(msg):
    """Prueft ob eine User-Nachricht nach Kalender-Daten fragt."""
    low = msg.lower()
    return any(kw in low for kw in _CALENDAR_KEYWORDS)


def get_calendar_events(days_back=0, days_ahead=7, calendars=None, search=None):
    """Liest Events aus Apple Calendar via AppleScript.
    Returns: (events_list, calendars_found_set, error_str_or_None)

    Jedes Event: {title, start, end, location, calendar_name, notes, all_day}
    Events sind chronologisch nach start sortiert.
    """
    target_cals = calendars if calendars else _CALENDAR_TARGETS

    # AppleScript bauen: pro Kalender einen try-Block
    cal_blocks = []
    for cname in target_cals:
        safe = cname.replace('"', '\\\\"')
        cal_blocks.append(f"""
        try
            set c to calendar "{safe}"
            set es to (every event of c whose start date >= startD and start date <= endD)
            repeat with e in es
                set t to summary of e
                set s to start date of e
                set eEnd to end date of e
                set loc to ""
                try
                    set loc to location of e
                end try
                set nt to ""
                try
                    set nt to description of e
                end try
                set ad to allday event of e
                set out to out & t & "|||" & (s as string) & "|||" & (eEnd as string) & "|||" & loc & "|||" & "{safe}" & "|||" & (ad as string) & "|||" & nt & "\\n"
            end repeat
        end try""")

    script = f"""
set today to current date
set startD to today - ({days_back} * days)
set endD to today + ({days_ahead} * days)
tell application "Calendar"
    set out to ""
    {"".join(cal_blocks)}
    return out
end tell
"""

    try:
        import subprocess as _cal_sp
        r = _cal_sp.run(
            ['osascript', '-e', script],
            capture_output=True, text=True, timeout=20,
        )
        if r.returncode != 0:
            err = (r.stderr or '').strip()
            if 'not allowed' in err.lower() or 'permission' in err.lower():
                return [], set(), "Keine Kalender-Berechtigung. Bitte in Systemeinstellungen > Datenschutz > Kalender erlauben."
            return [], set(), f"AppleScript-Fehler: {err[:200]}"
        raw = r.stdout.strip()
    except Exception as e:
        return [], set(), f"Kalender-Zugriff fehlgeschlagen: {e}"

    if not raw:
        return [], set(), None  # keine Events, kein Fehler

    events = []
    cals_found = set()
    for line in raw.split("\\n"):
        line = line.strip()
        if not line or '|||' not in line:
            continue
        parts = line.split('|||')
        if len(parts) < 6:
            continue
        title = parts[0].strip()
        start_str = parts[1].strip()
        end_str = parts[2].strip()
        location = parts[3].strip()
        cal_name = parts[4].strip()
        all_day = parts[5].strip().lower() == 'true'
        notes = parts[6].strip() if len(parts) > 6 else ''

        # Freitext-Suche
        if search:
            s = search.lower()
            if s not in title.lower() and s not in notes.lower() and s not in location.lower():
                continue

        # Datum parsen (macOS AppleScript Format: "Monday, 14 April 2026 at 07:30:00")
        dt_start = _parse_applescript_date(start_str)
        dt_end = _parse_applescript_date(end_str)

        events.append({
            'title': title,
            'start': dt_start.isoformat() if dt_start else start_str,
            'end': dt_end.isoformat() if dt_end else end_str,
            'location': location,
            'calendar_name': cal_name,
            'notes': notes[:500],
            'all_day': all_day,
            '_sort_key': dt_start.timestamp() if dt_start else 0,
        })
        cals_found.add(cal_name)

    events.sort(key=lambda e: e['_sort_key'])
    for e in events:
        e.pop('_sort_key', None)
    return events, cals_found, None


def _parse_applescript_date(s):
    """Parst ein macOS AppleScript Datum wie 'Monday, 14 April 2026 at 07:30:00'."""
    if not s:
        return None
    import re as _cal_re
    # Format: "Weekday, DD Month YYYY at HH:MM:SS"
    m = _cal_re.search(r'(\\d{1,2})\\s+(\\w+)\\s+(\\d{4})\\s+(?:at|um)?\\s*(\\d{1,2}):(\\d{2}):(\\d{2})', s)
    if m:
        day, month_str, year, h, mi, sec = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5), m.group(6)
        months = {
            'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
            'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12,
            'januar': 1, 'februar': 2, 'maerz': 3, 'märz': 3, 'mai': 5, 'juni': 6,
            'juli': 7, 'oktober': 10, 'dezember': 12,
        }
        month = months.get(month_str.lower())
        if month:
            try:
                return datetime.datetime(int(year), month, int(day), int(h), int(mi), int(sec))
            except Exception:
                pass
    return None


def format_calendar_context(events, max_items=15):
    """Formatiert Events als Kontext-Block fuer den System-Prompt."""
    if not events:
        return ""
    lines = ["--- KALENDER (kommende Termine) ---"]
    for e in events[:max_items]:
        start = e.get('start', '')
        title = e.get('title', '')
        cal = e.get('calendar_name', '')
        loc = e.get('location', '')
        ad = ' (ganztaegig)' if e.get('all_day') else ''
        line = f"[{start}] {title}{ad}"
        if cal:
            line += f" | Kalender: {cal}"
        if loc:
            line += f" | Ort: {loc}"
        lines.append(line)
    lines.append("--- ENDE KALENDER ---")
    return "\\n".join(lines)


''' + ANCHOR_FUNC


# ═══════════════════════════════════════════════════════════════════════════
# Patch 2: /api/calendar Route
# Einfuegen nach /api/context-info
# ═══════════════════════════════════════════════════════════════════════════

ANCHOR_ROUTE = """        return jsonify({
            'system_prompt_tokens': sp_tokens,
            'conversation_tokens': conv_tokens,
            'memory_files_loaded': memory_files,
            'total_tokens': total,"""

# Finde das Ende von api_context_info — suche nach der naechsten Route
# Ich verankere am Ende des api_context_info return-Blocks

# Einfacher: Suche nach einem eindeutigen String in der Naehe
ANCHOR_ROUTE2_OLD = """@app.route('/search_memory', methods=['POST'])"""

ANCHOR_ROUTE2_NEW = """# CALENDAR_INTEGRATION_V1: Kalender-API Route
@app.route('/api/calendar', methods=['GET', 'POST'])
def api_calendar():
    \"\"\"Gibt Kalender-Events im angegebenen Zeitraum zurueck.\"\"\"
    if request.method == 'POST' and request.is_json:
        data = request.json or {}
    else:
        data = dict(request.args)
    days_back = int(data.get('days_back', 0))
    days_ahead = int(data.get('days_ahead', 7))
    cal_filter = data.get('calendar_filter', None)
    search = data.get('search', None)
    calendars = [cal_filter] if cal_filter else None

    events, cals_found, error = get_calendar_events(
        days_back=days_back, days_ahead=days_ahead,
        calendars=calendars, search=search,
    )
    if error:
        return jsonify({'error': error, 'events': [], 'count': 0})

    now = datetime.datetime.now()
    return jsonify({
        'events': events,
        'count': len(events),
        'range': {
            'from': (now - datetime.timedelta(days=days_back)).strftime('%Y-%m-%d'),
            'to': (now + datetime.timedelta(days=days_ahead)).strftime('%Y-%m-%d'),
        },
        'calendars_found': sorted(cals_found),
    })


@app.route('/search_memory', methods=['POST'])"""


# ═══════════════════════════════════════════════════════════════════════════
# Patch 3: Auto-Inject Kalender-Kontext vor LLM-Call
# Einfuegen nach "# Build context string" Block, vor dem LLM-Call
# ═══════════════════════════════════════════════════════════════════════════

ANCHOR_INJECT_OLD = """    full_text = msg + text_ctx if text_ctx else msg

    provider_key = state.get('provider', 'anthropic')"""

ANCHOR_INJECT_NEW = """    full_text = msg + text_ctx if text_ctx else msg

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


def main():
    if not os.path.exists(WS):
        print(f"FEHLER: {WS} nicht gefunden")
        sys.exit(1)
    src = open(WS).read()
    orig = len(src)
    changed = False

    print("Kalender-Integration Patches:")
    src, a = apply(src, ANCHOR_FUNC, NEW_FUNC, 'CALENDAR_INTEGRATION_V1', 'Patch 1 — get_calendar_events()')
    changed = changed or a
    src, a = apply(src, ANCHOR_ROUTE2_OLD, ANCHOR_ROUTE2_NEW, '/api/calendar', 'Patch 2 — /api/calendar Route')
    changed = changed or a
    src, a = apply(src, ANCHOR_INJECT_OLD, ANCHOR_INJECT_NEW, '_has_calendar_intent(msg)', 'Patch 3 — Auto-Inject')
    changed = changed or a

    if not changed:
        print("Alle Patches schon angewendet.")
        return
    open(WS, 'w').write(src)
    print(f"OK: {orig} -> {len(src)} bytes")


if __name__ == '__main__':
    main()
