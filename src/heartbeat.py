"""
heartbeat.py — Heartbeat-Daemon (Roadmap-Feature 2, April 2026).

Zwei Aufgaben:

1. **Notification-Pump**: Liest periodisch die JSONL-Datei
   `<datalake>/config/pending_notifications.jsonl`, die andere Subsysteme
   befuellen (z.B. benchmark_fetcher bei DB-Aenderungen, spaeter
   pattern_analyzer bei Pattern-Vorschlaegen). Neue Eintraege werden in eine
   In-Memory-Queue gestellt und vom Browser via Polling abgeholt.
   Konsumierte Eintraege werden in eine archivierte Datei verschoben, damit
   die JSONL nicht ewig waechst.

2. **Cron-Registry**: Andere Subsysteme registrieren periodische Jobs
   (z.B. Pattern Analyzer "Sonntag 22:00", Skill-Refresh "Mo 06:00"). Der
   Daemon-Tick prueft im 60s-Takt, welche Jobs faellig sind, und ruft sie
   isoliert auf. Persistenz der last-run-Zeitpunkte in einer JSON-Datei,
   sodass Server-Restarts das Schedule nicht zuruecksetzen.

Beide Pfade sind als Daemon-Thread implementiert, blockieren nichts und
sind robust gegen Subsystem-Fehler (try/except + log).

Public API:
    enqueue_notification(payload)            -> bool   sofort einreihen
    fetch_pending(since_id=None, limit=50)   -> list   fuer Browser-Polling
    ack(notification_ids)                    -> int    als gesehen markieren
    schedule_cron(name, schedule_fn, job_fn) -> None   periodischer Job
    start_daemon()                           -> bool   Daemon starten (idempotent)
    stop_daemon()                            -> None   nur fuer Tests
    state_path(), notifications_path(), archive_path()
"""
import os
import json
import time
import threading
import datetime
import uuid

try:
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo("America/Sao_Paulo")
except Exception:
    _TZ = None

_BASE = os.path.expanduser(
    "~/Library/Mobile Documents/com~apple~CloudDocs/"
    "Downloads shared/claude_datalake"
)
NOTIFICATIONS_PATH = os.path.join(_BASE, "config", "pending_notifications.jsonl")
ARCHIVE_PATH = os.path.join(_BASE, "config", "pending_notifications.archive.jsonl")
CRON_STATE_PATH = os.path.join(_BASE, "config", "heartbeat_cron_state.json")

DAEMON_TICK_SECONDS = 60

_pump_lock = threading.Lock()
_cron_lock = threading.Lock()
_daemon_lock = threading.Lock()
_daemon_started = False
_daemon_stop = threading.Event()

# In-Memory Queue der pending Notifications. Jede Notification bekommt eine
# stabile id (entweder vom Producer oder hier generiert) und ein status.
# status: "pending" -> "delivered" -> "acked"
_pending_queue = []  # list of dicts
_seen_ids = set()    # damit Re-Reads nicht dupliziert einreihen

# Cron-Jobs: name -> {schedule_fn, job_fn, last_run_iso}
_cron_jobs = {}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _now():
    if _TZ is not None:
        return datetime.datetime.now(_TZ)
    return datetime.datetime.now().astimezone()


def _now_iso():
    return _now().isoformat(timespec="seconds")


def state_path():
    return CRON_STATE_PATH


def notifications_path():
    return NOTIFICATIONS_PATH


def archive_path():
    return ARCHIVE_PATH


def _load_cron_state():
    if not os.path.exists(CRON_STATE_PATH):
        return {}
    try:
        with open(CRON_STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_cron_state(state):
    os.makedirs(os.path.dirname(CRON_STATE_PATH), exist_ok=True)
    tmp = CRON_STATE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, CRON_STATE_PATH)


# ── Notifications: Producer-Side ─────────────────────────────────────────────

def enqueue_notification(payload):
    """Direkt-Enqueue (umgeht Datei-Pumping). Andere Subsysteme koennen
    entweder direkt hierhin schreiben oder weiter in pending_notifications.jsonl
    schreiben — die Datei-Variante ist crash-safer.
    """
    if not isinstance(payload, dict):
        return False
    note = dict(payload)
    if "id" not in note:
        note["id"] = str(uuid.uuid4())[:12]
    if "timestamp" not in note:
        note["timestamp"] = _now_iso()
    note.setdefault("status", "pending")
    with _pump_lock:
        if note["id"] in _seen_ids:
            return False
        _seen_ids.add(note["id"])
        _pending_queue.append(note)
    return True


def _drain_notifications_file():
    """Liest neue Eintraege aus pending_notifications.jsonl und schiebt sie
    in die In-Memory-Queue. Datei wird danach getruncated und die geleseen
    Eintraege ans Archive angehaengt — damit es keine Duplikate beim
    naechsten Tick gibt.
    """
    if not os.path.exists(NOTIFICATIONS_PATH):
        return 0
    try:
        # Atomarer "Drain": neue Datei einlesen, alte umbenennen.
        # Falls ein Producer parallel schreibt: dessen Eintrag landet im
        # naechsten Tick — kein Datenverlust, da die Datei append-only ist.
        os.makedirs(os.path.dirname(NOTIFICATIONS_PATH), exist_ok=True)
        new_entries = []
        with open(NOTIFICATIONS_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    new_entries.append(json.loads(line))
                except Exception:
                    continue

        if not new_entries:
            return 0

        # Eintraege in In-Memory-Queue spielen
        added = 0
        with _pump_lock:
            for entry in new_entries:
                if not isinstance(entry, dict):
                    continue
                if "id" not in entry:
                    entry["id"] = str(uuid.uuid4())[:12]
                if entry["id"] in _seen_ids:
                    continue
                entry.setdefault("timestamp", _now_iso())
                entry.setdefault("status", "pending")
                _seen_ids.add(entry["id"])
                _pending_queue.append(entry)
                added += 1

        # Archivieren + truncate
        with open(ARCHIVE_PATH, "a", encoding="utf-8") as af:
            for entry in new_entries:
                af.write(json.dumps(entry, ensure_ascii=False) + "\n")
        # Truncate via mode='w' nachdem wir alles gelesen + archiviert haben
        open(NOTIFICATIONS_PATH, "w", encoding="utf-8").close()
        return added
    except Exception as e:
        try:
            print(f"[heartbeat] drain failed: {e}", flush=True)
        except Exception:
            pass
        return 0


# ── Notifications: Consumer-Side (Browser-Polling) ───────────────────────────

def fetch_pending(since_id=None, limit=50):
    """Liefert pending Notifications fuer den Browser.

    since_id: optional, "alles seit dieser ID" (exklusiv). Wenn None ->
              alle pending Notes.
    limit:    max. zurueckgegebene Notes (default 50, max 200).
    Markiert geliefert als 'delivered'. Erst nach ack() werden sie aus dem
    Pending-Queue entfernt.
    """
    limit = max(1, min(int(limit or 50), 200))
    with _pump_lock:
        items = []
        skip = since_id is not None
        for note in _pending_queue:
            if skip:
                if note.get("id") == since_id:
                    skip = False
                continue
            if note.get("status") in ("acked",):
                continue
            items.append(dict(note))
            if note.get("status") == "pending":
                note["status"] = "delivered"
            if len(items) >= limit:
                break
        return items


def ack(notification_ids):
    """Notifications als gesehen markieren — werden aus Pending entfernt."""
    if not notification_ids:
        return 0
    ids = set(notification_ids)
    removed = 0
    with _pump_lock:
        new_queue = []
        for note in _pending_queue:
            if note.get("id") in ids:
                removed += 1
                continue
            new_queue.append(note)
        _pending_queue.clear()
        _pending_queue.extend(new_queue)
    return removed


def queue_size():
    with _pump_lock:
        return len(_pending_queue)


# ── Cron-Registry ────────────────────────────────────────────────────────────

def schedule_cron(name, schedule_fn, job_fn, run_immediately=False):
    """Registriert einen wiederkehrenden Job.

    name:         eindeutiger Name fuer Logging und Persistenz
    schedule_fn:  callable(last_run_dt_or_None, now_dt) -> bool
                  liefert True, wenn der Job jetzt laufen soll
    job_fn:       callable(now_dt) -> any. Wird vom Daemon ausgefuehrt.
    run_immediately: True -> bei Registrierung sofort einmal laufen lassen
    """
    if not callable(schedule_fn) or not callable(job_fn):
        raise TypeError("schedule_fn und job_fn muessen callable sein")
    with _cron_lock:
        state = _load_cron_state()
        last_run = state.get(name, {}).get("last_run_iso")
        _cron_jobs[name] = {
            "schedule_fn": schedule_fn,
            "job_fn": job_fn,
            "last_run_iso": last_run,
        }
    if run_immediately:
        _run_cron(name)


def list_cron():
    with _cron_lock:
        return [{"name": n,
                 "last_run_iso": j.get("last_run_iso")}
                for n, j in _cron_jobs.items()]


def _run_cron(name):
    with _cron_lock:
        job = _cron_jobs.get(name)
        if not job:
            return False
    try:
        job["job_fn"](_now())
    except Exception as e:
        try:
            print(f"[heartbeat] cron job '{name}' failed: {e}", flush=True)
        except Exception:
            pass
    finally:
        with _cron_lock:
            j = _cron_jobs.get(name)
            if j is not None:
                j["last_run_iso"] = _now_iso()
                state = _load_cron_state()
                state[name] = {"last_run_iso": j["last_run_iso"]}
                try:
                    _save_cron_state(state)
                except Exception:
                    pass
    return True


def _tick_cron():
    """Wird vom Daemon einmal pro Tick aufgerufen. Iteriert ueber alle
    registrierten Jobs und ruft die schedule_fn — bei True: job_fn."""
    now = _now()
    with _cron_lock:
        names = list(_cron_jobs.keys())
    for name in names:
        with _cron_lock:
            job = _cron_jobs.get(name)
            if not job:
                continue
            schedule_fn = job["schedule_fn"]
            last_run_iso = job.get("last_run_iso")
        last_run_dt = None
        if last_run_iso:
            try:
                last_run_dt = datetime.datetime.fromisoformat(last_run_iso)
                if last_run_dt.tzinfo is None and _TZ is not None:
                    last_run_dt = last_run_dt.replace(tzinfo=_TZ)
            except Exception:
                last_run_dt = None
        try:
            due = bool(schedule_fn(last_run_dt, now))
        except Exception as e:
            try:
                print(f"[heartbeat] schedule_fn for '{name}' failed: {e}",
                      flush=True)
            except Exception:
                pass
            continue
        if due:
            _run_cron(name)


# ── Common Schedule-Predicates ───────────────────────────────────────────────

def every_n_seconds(n):
    """Predicate: laeuft alle N Sekunden."""
    def _fn(last, now):
        if last is None:
            return True
        return (now - last).total_seconds() >= n
    return _fn


def daily_at(hour, minute=0):
    """Predicate: laeuft einmal pro Tag, ab gegebener Uhrzeit (Lokalzeit)."""
    def _fn(last, now):
        if now.hour < hour or (now.hour == hour and now.minute < minute):
            return False
        if last is None:
            return True
        # Schon gleicher Tag gelaufen?
        return last.date() != now.date()
    return _fn


def weekly_at(weekday, hour, minute=0):
    """Predicate: einmal pro Woche, ab Wochentag+Uhrzeit. weekday: 0=Mo."""
    def _fn(last, now):
        if now.weekday() != weekday:
            return False
        if now.hour < hour or (now.hour == hour and now.minute < minute):
            return False
        if last is None:
            return True
        return (now - last).total_seconds() >= 6 * 86400
    return _fn


# ── Daemon-Loop ──────────────────────────────────────────────────────────────

def _daemon_loop():
    while not _daemon_stop.is_set():
        try:
            _drain_notifications_file()
        except Exception as e:
            try:
                print(f"[heartbeat] drain tick failed: {e}", flush=True)
            except Exception:
                pass
        try:
            _tick_cron()
        except Exception as e:
            try:
                print(f"[heartbeat] cron tick failed: {e}", flush=True)
            except Exception:
                pass
        # Schlafen, aber bei stop_daemon() sofort raus
        _daemon_stop.wait(timeout=DAEMON_TICK_SECONDS)


def start_daemon():
    """Daemon-Thread starten, idempotent."""
    global _daemon_started
    with _daemon_lock:
        if _daemon_started:
            return False
        _daemon_stop.clear()
        t = threading.Thread(target=_daemon_loop, name="heartbeat-daemon",
                             daemon=True)
        t.start()
        _daemon_started = True
        return True


def stop_daemon():
    """Nur fuer Tests: stoppt den Daemon."""
    global _daemon_started
    _daemon_stop.set()
    _daemon_started = False
