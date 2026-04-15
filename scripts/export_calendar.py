#!/usr/bin/env python3
"""
Exportiert alle macOS Kalender (Apple Calendar + Fantastical-Accounts) in den
AssistantDev Data Lake.

Output:
  <output-dir>/calendar_events.json   — Maschinenlesbar
  <output-dir>/calendar_summary.txt   — Human-readable fuer Agent Memory

Methoden (in dieser Prioritaet):
  1. icalBuddy CLI (falls installiert)
  2. PyObjC EventKit Bridge
  3. AppleScript via osascript
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

DEFAULT_OUTPUT_DIR = Path(
    os.path.expanduser(
        "~/Library/Mobile Documents/com~apple~CloudDocs/"
        "Downloads shared/claude_datalake/calendar"
    )
)

WEEKDAYS_DE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


# ---------------------------------------------------------------------------
# Methode 1: icalBuddy
# ---------------------------------------------------------------------------
def fetch_via_icalbuddy(days_back: int, days_forward: int,
                        calendars: list[str] | None) -> list[dict] | None:
    icalbuddy = shutil.which("icalbuddy")
    if not icalbuddy:
        return None
    start = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    end_days = days_back + days_forward
    cmd = [
        icalbuddy,
        "-nc", "-npn",
        "-b", "|||",
        "-ab", "",
        "-po", "title,datetime,location,notes,url,attendees",
        "-tf", "%H:%M",
        "-df", "%Y-%m-%d",
        f"eventsFrom:{start}", f"to:+{end_days}days",
    ]
    if calendars:
        cmd.extend(["-ic", ",".join(calendars)])
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except Exception:
        return None
    if out.returncode != 0 or not out.stdout.strip():
        return None
    events: list[dict] = []
    for line in out.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("|||")]
        if len(parts) < 2:
            continue
        events.append({
            "title": parts[0],
            "start": parts[1],
            "end": parts[1],
            "all_day": False,
            "calendar": "",
            "location": parts[2] if len(parts) > 2 else "",
            "notes": parts[3] if len(parts) > 3 else "",
            "url": parts[4] if len(parts) > 4 else "",
        })
    return events


# ---------------------------------------------------------------------------
# Methode 2: EventKit via PyObjC
# ---------------------------------------------------------------------------
def fetch_via_eventkit(days_back: int, days_forward: int,
                       calendars: list[str] | None) -> list[dict] | None:
    try:
        import EventKit  # type: ignore
        from Foundation import NSDate  # type: ignore
    except Exception:
        return None

    store = EventKit.EKEventStore.alloc().init()

    # macOS 14+: requestFullAccessToEventsWithCompletion
    # altere: requestAccessToEntityType_completion
    granted = {"v": None, "done": False}

    def handler(ok, err):
        granted["v"] = bool(ok)
        granted["done"] = True

    if hasattr(store, "requestFullAccessToEventsWithCompletion_"):
        store.requestFullAccessToEventsWithCompletion_(handler)
    else:
        store.requestAccessToEntityType_completion_(
            EventKit.EKEntityTypeEvent, handler
        )

    # Kurzes Warten auf Completion Handler (non-blocking Runloop tick)
    from Foundation import NSRunLoop
    deadline = datetime.now() + timedelta(seconds=5)
    while not granted["done"] and datetime.now() < deadline:
        NSRunLoop.currentRunLoop().runUntilDate_(
            NSDate.dateWithTimeIntervalSinceNow_(0.1)
        )

    if granted["v"] is False:
        print("EventKit: Zugriff verweigert", file=sys.stderr)
        return None

    all_cals = store.calendarsForEntityType_(EventKit.EKEntityTypeEvent) or []
    if calendars:
        want = set(calendars)
        cal_objs = [c for c in all_cals if c.title() in want]
    else:
        cal_objs = list(all_cals)

    if not cal_objs:
        return None

    now = datetime.now()
    start_dt = now - timedelta(days=days_back)
    end_dt = now + timedelta(days=days_forward)
    start_ns = NSDate.dateWithTimeIntervalSince1970_(start_dt.timestamp())
    end_ns = NSDate.dateWithTimeIntervalSince1970_(end_dt.timestamp())

    # Predicate akzeptiert max. 4 Jahre auf einmal
    predicate = store.predicateForEventsWithStartDate_endDate_calendars_(
        start_ns, end_ns, cal_objs
    )
    raw = store.eventsMatchingPredicate_(predicate) or []

    events: list[dict] = []
    for ev in raw:
        s = ev.startDate()
        e = ev.endDate()
        if s is None:
            continue
        s_py = datetime.fromtimestamp(s.timeIntervalSince1970())
        e_py = datetime.fromtimestamp(e.timeIntervalSince1970()) if e else s_py
        all_day = bool(ev.isAllDay())
        cal_title = ev.calendar().title() if ev.calendar() else ""
        events.append({
            "title": str(ev.title() or ""),
            "start": s_py.strftime("%Y-%m-%dT%H:%M:%S"),
            "end": e_py.strftime("%Y-%m-%dT%H:%M:%S"),
            "all_day": all_day,
            "calendar": str(cal_title),
            "location": str(ev.location() or ""),
            "notes": str(ev.notes() or "")[:2000],
            "url": str(ev.URL().absoluteString()) if ev.URL() else "",
        })
    return events


# ---------------------------------------------------------------------------
# Methode 3: AppleScript
# ---------------------------------------------------------------------------
APPLESCRIPT_TEMPLATE = r'''
on run argv
    set startDaysBack to (item 1 of argv) as integer
    set endDaysForward to (item 2 of argv) as integer
    set startDate to (current date) - (startDaysBack * days)
    set endDate to (current date) + (endDaysForward * days)
    set output to ""
    set AppleScript's text item delimiters to ""
    tell application "Calendar"
        set calList to every calendar
        repeat with c in calList
            set calName to title of c
            try
                set evList to (every event of c whose start date is greater than or equal to startDate and start date is less than or equal to endDate)
                repeat with ev in evList
                    set evTitle to summary of ev
                    set evStart to start date of ev
                    set evEnd to end date of ev
                    set evLoc to ""
                    try
                        set evLoc to location of ev
                    end try
                    set evAllDay to allday event of ev
                    set output to output & calName & tab & evTitle & tab & (my fmt(evStart)) & tab & (my fmt(evEnd)) & tab & (evAllDay as text) & tab & evLoc & linefeed
                end repeat
            end try
        end repeat
    end tell
    return output
end run

on fmt(d)
    set y to year of d as integer
    set m to (month of d as integer)
    set dy to day of d as integer
    set hh to hours of d
    set mm to minutes of d
    return (y as text) & "-" & (my pad(m)) & "-" & (my pad(dy)) & "T" & (my pad(hh)) & ":" & (my pad(mm)) & ":00"
end fmt

on pad(n)
    if n < 10 then return "0" & (n as text)
    return (n as text)
end pad
'''


def fetch_via_applescript(days_back: int, days_forward: int,
                          calendars: list[str] | None) -> list[dict] | None:
    try:
        out = subprocess.run(
            ["osascript", "-e", APPLESCRIPT_TEMPLATE,
             str(days_back), str(days_forward)],
            capture_output=True, text=True, timeout=120,
        )
    except Exception:
        return None
    if out.returncode != 0:
        if out.stderr:
            print(f"AppleScript-Fehler: {out.stderr.strip()}", file=sys.stderr)
        return None
    events: list[dict] = []
    want = set(calendars) if calendars else None
    for line in out.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) < 6:
            continue
        cal_name, title, start, end, all_day, loc = parts[:6]
        if want and cal_name not in want:
            continue
        events.append({
            "title": title,
            "start": start,
            "end": end,
            "all_day": all_day.strip().lower() == "true",
            "calendar": cal_name,
            "location": loc,
            "notes": "",
            "url": "",
        })
    return events


# ---------------------------------------------------------------------------
# Summary Rendering
# ---------------------------------------------------------------------------
def render_summary(events: list[dict], calendars_found: list[str],
                   days_back: int, days_forward: int) -> str:
    now = datetime.now()
    header = [
        "KALENDER-UEBERSICHT",
        "=" * 60,
        f"Export: {now.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Zeitraum: {days_back} Tage rueckwaerts bis {days_forward} Tage voraus",
        f"Kalender: {', '.join(calendars_found) if calendars_found else '-'}",
        f"Events gesamt: {len(events)}",
        "=" * 60,
        "",
    ]

    # Sortiert nach start
    def _key(ev):
        try:
            return datetime.strptime(ev["start"], "%Y-%m-%dT%H:%M:%S")
        except Exception:
            return datetime.max
    events_sorted = sorted(events, key=_key)

    by_month: dict[str, list[dict]] = defaultdict(list)
    for ev in events_sorted:
        try:
            d = datetime.strptime(ev["start"], "%Y-%m-%dT%H:%M:%S")
            month_key = d.strftime("%Y-%m (%B)")
        except Exception:
            month_key = "Unbekannt"
        by_month[month_key].append(ev)

    body: list[str] = []
    for month, evs in by_month.items():
        body.append(f"## {month}")
        body.append("-" * 60)
        by_week: dict[int, list[dict]] = defaultdict(list)
        for ev in evs:
            try:
                d = datetime.strptime(ev["start"], "%Y-%m-%dT%H:%M:%S")
                by_week[d.isocalendar()[1]].append(ev)
            except Exception:
                by_week[0].append(ev)
        for week, wevs in sorted(by_week.items()):
            body.append(f"  KW {week}")
            for ev in wevs:
                try:
                    d = datetime.strptime(ev["start"], "%Y-%m-%dT%H:%M:%S")
                    wd = WEEKDAYS_DE[d.weekday()]
                    date_str = d.strftime("%Y-%m-%d")
                    time_str = "ganztaegig" if ev.get("all_day") else d.strftime("%H:%M")
                except Exception:
                    wd, date_str, time_str = "??", ev.get("start", ""), ""
                extras = []
                if ev.get("calendar"):
                    extras.append(f"Kalender: {ev['calendar']}")
                if ev.get("location"):
                    extras.append(f"Ort: {ev['location']}")
                extras_str = f" ({' | '.join(extras)})" if extras else ""
                title = ev.get("title", "").replace("\n", " ").strip() or "(ohne Titel)"
                body.append(f"    [{date_str} {wd}] {time_str} — {title}{extras_str}")
            body.append("")
        body.append("")
    return "\n".join(header + body)


# ---------------------------------------------------------------------------
# Memory-Symlinks
# ---------------------------------------------------------------------------
AGENTS = ["signicat", "privat", "trustedcarrier", "standard", "system ward"]


def install_memory_links(summary_path: Path) -> list[str]:
    """Legt pro Agent memory/calendar_events.txt als Symlink (oder Kopie) an."""
    base = summary_path.parent.parent  # …/claude_datalake/
    results = []
    for agent in AGENTS:
        mem_dir = base / agent / "memory"
        mem_dir.mkdir(parents=True, exist_ok=True)
        target = mem_dir / "calendar_events.txt"
        try:
            if target.is_symlink() or target.exists():
                target.unlink()
            os.symlink(summary_path, target)
            results.append(f"symlink: {agent}")
        except Exception as e:
            try:
                shutil.copy2(summary_path, target)
                results.append(f"copy:    {agent} ({e})")
            except Exception as e2:
                results.append(f"FAIL:    {agent} ({e2})")
    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Exportiert macOS Kalender in Data Lake")
    ap.add_argument("--days-back", type=int, default=30)
    ap.add_argument("--days-forward", type=int, default=180)
    ap.add_argument("--calendars", default="",
                    help="Kommagetrennte Liste, default: alle")
    ap.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    ap.add_argument("--skip-memory-links", action="store_true")
    args = ap.parse_args()

    calendars = [c.strip() for c in args.calendars.split(",") if c.strip()] or None
    out_dir = Path(os.path.expanduser(args.output_dir))
    out_dir.mkdir(parents=True, exist_ok=True)

    events = None
    method_used = None
    for name, fn in (
        ("icalbuddy", fetch_via_icalbuddy),
        ("eventkit",  fetch_via_eventkit),
        ("applescript", fetch_via_applescript),
    ):
        print(f"Versuche Methode: {name} …", file=sys.stderr)
        try:
            events = fn(args.days_back, args.days_forward, calendars)
        except Exception as e:
            print(f"  {name} fehlgeschlagen: {e}", file=sys.stderr)
            events = None
        if events is not None and len(events) >= 0:
            method_used = name
            if events:
                break
            # 0 Events => Methode lief, aber leer. Trotzdem weiterprobieren.
            print(f"  {name} lieferte 0 Events – probiere naechste Methode", file=sys.stderr)
            events = None

    if events is None:
        sys.stderr.write(
            "FEHLER: Keine Kalender-Methode war erfolgreich.\n"
            "Empfehlungen:\n"
            "  • icalBuddy installieren: brew install ical-buddy\n"
            "  • In Systemeinstellungen > Datenschutz > Kalender: Terminal/Python freigeben\n"
            "  • Calendar.app muss mindestens einmal gestartet werden\n"
        )
        sys.exit(2)

    calendars_found = sorted({ev["calendar"] for ev in events if ev["calendar"]})

    payload = {
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "method": method_used,
        "days_back": args.days_back,
        "days_forward": args.days_forward,
        "calendars": calendars_found,
        "event_count": len(events),
        "events": events,
    }

    json_path = out_dir / "calendar_events.json"
    summary_path = out_dir / "calendar_summary.txt"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    summary_path.write_text(
        render_summary(events, calendars_found, args.days_back, args.days_forward),
        encoding="utf-8",
    )

    print(f"Export fertig: {len(events)} Events via '{method_used}'")
    print(f"  JSON:    {json_path}")
    print(f"  Summary: {summary_path}")
    print(f"  Kalender: {', '.join(calendars_found) if calendars_found else '(keine Namen)'}")

    if not args.skip_memory_links:
        print("Memory-Links:")
        for line in install_memory_links(summary_path):
            print(f"  {line}")


if __name__ == "__main__":
    main()
