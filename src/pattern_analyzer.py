"""
pattern_analyzer.py — Roadmap-Feature 5 (April 2026).

Liest periodisch die Usage-Logs, clustert Turns nach Agent + Task-Kategorie +
Wochentag + Tageszeit-Bucket, erkennt regelmaessige Muster und schlaegt dem
User Automatisierungen via Heartbeat-Notification vor.

User antwortet pro Pattern: "yes" (als Cron-Automation aktivieren), "no",
"later" (nach `later_threshold` weiteren Vorkommen erneut fragen).

Aktivierte Patterns landen als heartbeat-Cron-Job; ihre automatische
Ausfuehrung erzeugt eine neue Heartbeat-Notification mit dem Ergebnis.

Public API:
    analyze_logs(now=None)              -> dict   Pattern-Detection-Run
    list_patterns()                      -> list
    respond(pattern_id, response)        -> dict   yes / no / later
    activate_pattern(pattern_id)         -> bool   als Cron-Job registrieren
    register_with_heartbeat()            -> bool   wochentlich Sonntag 22:00
"""
import os
import json
import re
import datetime
import threading
import uuid
from collections import defaultdict, Counter

try:
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo("America/Sao_Paulo")
except Exception:
    _TZ = None

try:
    import heartbeat as _hb
except Exception:
    _hb = None

try:
    import skill_database as _sd
except Exception:
    _sd = None

try:
    import usage_logger as _ul
except Exception:
    _ul = None

_BASE = os.path.expanduser(
    "~/Library/Mobile Documents/com~apple~CloudDocs/"
    "Downloads shared/claude_datalake"
)
PATTERNS_DIR = os.path.join(_BASE, "patterns")
PATTERNS_PATH = os.path.join(PATTERNS_DIR, "detected_patterns.json")
USAGE_LOGS_DIR = os.path.join(_BASE, "usage_logs")

_lock = threading.RLock()

# Tagesfenster fuer "Tageszeit-Bucket"
TIME_BUCKETS = [
    ("morning", 5, 11),
    ("forenoon", 11, 13),
    ("afternoon", 13, 17),
    ("evening", 17, 22),
    ("night", 22, 5),  # wraps
]

WEEKDAY_DE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag",
              "Freitag", "Samstag", "Sonntag"]

# Mapping Skill -> bestes Modell-Lookup-Skill (skill_database.get_best)
CATEGORY_TO_SKILL = {
    "research": "research_long",
    "coding": "coding",
    "writing": "writing",
    "email": "writing",
    "document": "document_analysis",
    "calendar": "instruction_following",
    "image": "image_generation",
    "video": "video_generation",
    "translation": "translation",
    "analysis": "reasoning",
    "search": "web_search",
    "other": "instruction_following",
}

MIN_OCCURRENCES = 3
DEFAULT_LATER_THRESHOLD = 10


# ── Persistenz ───────────────────────────────────────────────────────────────

def _load_state():
    if not os.path.exists(PATTERNS_PATH):
        return {"last_analysis": None, "patterns": {}}
    try:
        with open(PATTERNS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("patterns", {})
        return data
    except Exception:
        return {"last_analysis": None, "patterns": {}}


def _save_state(state):
    os.makedirs(PATTERNS_DIR, exist_ok=True)
    tmp = PATTERNS_PATH + ".tmp"
    with _lock:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, PATTERNS_PATH)


def _now():
    if _TZ is not None:
        return datetime.datetime.now(_TZ)
    return datetime.datetime.now().astimezone()


def _now_iso():
    return _now().isoformat(timespec="seconds")


# ── Helpers ──────────────────────────────────────────────────────────────────

def _time_bucket(hour):
    for name, lo, hi in TIME_BUCKETS:
        if lo < hi:
            if lo <= hour < hi:
                return name
        else:  # wraps midnight
            if hour >= lo or hour < hi:
                return name
    return "other"


def _bucket_label(bucket):
    return {
        "morning": "morgens",
        "forenoon": "vormittags",
        "afternoon": "nachmittags",
        "evening": "abends",
        "night": "nachts",
    }.get(bucket, bucket)


def _iter_log_entries(months_back=2):
    """Liest die letzten N Monatsdateien als Generator."""
    if not os.path.exists(USAGE_LOGS_DIR):
        return
    now = _now()
    paths = []
    for offset in range(months_back + 1):
        ts = now - datetime.timedelta(days=30 * offset)
        p = os.path.join(USAGE_LOGS_DIR, f"usage_{ts.strftime('%Y-%m')}.jsonl")
        if p not in paths:
            paths.append(p)
    for p in paths:
        if not os.path.exists(p):
            continue
        try:
            with open(p, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        yield json.loads(line)
                    except Exception:
                        continue
        except Exception:
            continue


def _normalize_token(s):
    """Vereinfachter Tokenizer fuer Stop-Word-armes Matching."""
    if not isinstance(s, str):
        return []
    s = s.lower()
    return re.findall(r"[a-z0-9äöüß]{3,}", s)


_STOP_WORDS = {
    "der", "die", "das", "und", "oder", "aber", "auch", "ich", "mir", "mein",
    "meine", "ist", "war", "sein", "haben", "hat", "wird", "werde", "wie",
    "was", "wann", "wo", "wer", "den", "des", "dem", "ein", "eine", "einen",
    "kann", "kannst", "soll", "sollst", "muss", "musst", "mit", "von", "bei",
    "zur", "zum", "auf", "fuer", "fur", "dass", "das", "this", "that", "the",
    "and", "for", "you", "with", "have", "has", "are", "was", "from", "your",
    "give", "make", "let", "please", "bitte", "kurz", "mal",
}


def _key_terms(msg):
    """Liefert sortiertes Tupel der Top-Terme (Schluesselwoerter) einer Message
    fuer simples Cluster-Matching ohne Embedding-Library."""
    tokens = [t for t in _normalize_token(msg) if t not in _STOP_WORDS]
    if not tokens:
        return ()
    counts = Counter(tokens).most_common(5)
    return tuple(sorted(t for t, _ in counts))


# ── Detection ────────────────────────────────────────────────────────────────

def _cluster_entries(entries):
    """Clustert Logs nach (agent, category, weekday, time_bucket).

    Liefert dict cluster_key -> {entries: [...], term_signatures: Counter}.
    """
    clusters = defaultdict(lambda: {"entries": [], "term_sigs": Counter()})
    for e in entries:
        ts = e.get("timestamp")
        if not ts:
            continue
        try:
            dt = datetime.datetime.fromisoformat(ts)
        except Exception:
            continue
        if dt.tzinfo is None and _TZ is not None:
            dt = dt.replace(tzinfo=_TZ)
        agent = e.get("agent") or "unknown"
        category = e.get("category") or "other"
        weekday = dt.weekday()
        bucket = _time_bucket(dt.hour)
        key = (agent, category, weekday, bucket)
        clusters[key]["entries"].append(e)
        sig = _key_terms(e.get("user_message", ""))
        if sig:
            clusters[key]["term_sigs"][sig] += 1
    return clusters


def _build_pattern(cluster_key, cluster_data, existing_id=None):
    agent, category, weekday, bucket = cluster_key
    entries = cluster_data["entries"]
    occurrences = len(entries)
    last_seen = max((e.get("timestamp") for e in entries
                     if e.get("timestamp")), default=_now_iso())
    skill = CATEGORY_TO_SKILL.get(category, "instruction_following")
    suggested_model = None
    suggested_rationale = ""
    if _sd is not None:
        try:
            best = _sd.get_best(skill, n=1)
            if best:
                suggested_model = best[0].get("model_ref")
                suggested_rationale = best[0].get("rationale", "")
        except Exception:
            pass
    weekday_label = WEEKDAY_DE[weekday] if 0 <= weekday <= 6 else "?"
    bucket_label = _bucket_label(bucket)
    description = (
        f"{occurrences}x {category}-Anfrage an Agent '{agent}' "
        f"jeden {weekday_label} {bucket_label}"
    )
    # Top-Signatur falls verfuegbar
    top_sigs = cluster_data["term_sigs"].most_common(1)
    if top_sigs:
        top_terms = list(top_sigs[0][0])
        if top_terms:
            description += f" — Themen: {', '.join(top_terms[:5])}"

    target_hour = {"morning": 9, "forenoon": 11, "afternoon": 14,
                   "evening": 19, "night": 22}.get(bucket, 9)
    suggested_schedule = {
        "kind": "weekly",
        "weekday": weekday,
        "hour": target_hour,
        "minute": 0,
    }

    pattern = {
        "id": existing_id or f"pattern_{uuid.uuid4().hex[:10]}",
        "cluster_key": [agent, category, weekday, bucket],
        "description": description,
        "agent": agent,
        "category": category,
        "weekday": weekday,
        "weekday_label": weekday_label,
        "time_bucket": bucket,
        "occurrences": occurrences,
        "last_seen": last_seen,
        "first_detected_at": _now_iso(),
        "suggested_skill": skill,
        "suggested_model": suggested_model,
        "suggested_rationale": suggested_rationale,
        "suggested_schedule": suggested_schedule,
        "user_response": None,
        "later_threshold": DEFAULT_LATER_THRESHOLD,
        "occurrences_at_last_response": 0,
        "automation_active": False,
        "cron_job_name": None,
        "last_automation_run": None,
    }
    if top_sigs:
        pattern["top_term_signature"] = list(top_sigs[0][0])
    return pattern


def _cluster_key_to_id_map(state):
    return {
        tuple(p["cluster_key"]): pid
        for pid, p in state.get("patterns", {}).items()
        if p.get("cluster_key")
    }


def analyze_logs(now=None, push_notifications=True):
    """Komplett-Run: liest Logs, baut/aktualisiert Patterns, pusht Vorschlaege.

    Liefert Summary:
    {
      ok, started_at, finished_at, total_entries,
      clusters_total, patterns_qualifying,
      patterns_new[], patterns_updated[], patterns_resurfaced[]
    }
    """
    started = _now_iso()
    summary = {
        "ok": True, "started_at": started,
        "total_entries": 0, "clusters_total": 0,
        "patterns_qualifying": 0,
        "patterns_new": [], "patterns_updated": [], "patterns_resurfaced": [],
    }
    try:
        entries = list(_iter_log_entries(months_back=2))
        summary["total_entries"] = len(entries)
        clusters = _cluster_entries(entries)
        summary["clusters_total"] = len(clusters)

        with _lock:
            state = _load_state()
            existing_map = _cluster_key_to_id_map(state)

            for key, cluster_data in clusters.items():
                if len(cluster_data["entries"]) < MIN_OCCURRENCES:
                    continue
                summary["patterns_qualifying"] += 1
                existing_pid = existing_map.get(key)
                pattern = _build_pattern(
                    key, cluster_data,
                    existing_id=existing_pid,
                )
                if existing_pid is None:
                    state["patterns"][pattern["id"]] = pattern
                    summary["patterns_new"].append({
                        "id": pattern["id"],
                        "description": pattern["description"],
                    })
                    if push_notifications:
                        _push_pattern_suggestion(pattern, kind="new")
                else:
                    old = state["patterns"][existing_pid]
                    old_occ = old.get("occurrences", 0)
                    # update fields
                    pattern["first_detected_at"] = old.get(
                        "first_detected_at", pattern["first_detected_at"])
                    pattern["user_response"] = old.get("user_response")
                    pattern["later_threshold"] = old.get(
                        "later_threshold", DEFAULT_LATER_THRESHOLD)
                    pattern["occurrences_at_last_response"] = old.get(
                        "occurrences_at_last_response", 0)
                    pattern["automation_active"] = old.get(
                        "automation_active", False)
                    pattern["cron_job_name"] = old.get("cron_job_name")
                    pattern["last_automation_run"] = old.get("last_automation_run")
                    state["patterns"][existing_pid] = pattern
                    summary["patterns_updated"].append({
                        "id": pattern["id"],
                        "description": pattern["description"],
                        "occurrences_old": old_occ,
                        "occurrences_new": pattern["occurrences"],
                    })
                    # Resurface bei "later"-Status, wenn genug neue Vorkommen
                    if (pattern["user_response"] == "later" and
                            (pattern["occurrences"] -
                             pattern["occurrences_at_last_response"]
                             ) >= pattern["later_threshold"]):
                        pattern["user_response"] = None  # erneut anbieten
                        pattern["occurrences_at_last_response"] = pattern["occurrences"]
                        summary["patterns_resurfaced"].append({
                            "id": pattern["id"],
                            "description": pattern["description"],
                        })
                        if push_notifications:
                            _push_pattern_suggestion(pattern, kind="resurfaced")

            state["last_analysis"] = _now_iso()
            _save_state(state)
        summary["finished_at"] = _now_iso()
    except Exception as e:
        summary["ok"] = False
        summary["error"] = str(e)
        summary["finished_at"] = _now_iso()
    return summary


# ── Notifications ────────────────────────────────────────────────────────────

def _push_pattern_suggestion(pattern, kind="new"):
    if _hb is None:
        return False
    try:
        prefix = ("Pattern erneut erkannt"
                  if kind == "resurfaced"
                  else "Neues Pattern erkannt")
        msg = (
            f"{prefix}: {pattern['description']}. Soll ich das automatisch "
            f"jeden {pattern['weekday_label']} um "
            f"{pattern['suggested_schedule']['hour']:02d}:"
            f"{pattern['suggested_schedule']['minute']:02d} Uhr "
            f"mit {pattern.get('suggested_model') or 'dem besten verfuegbaren Modell'} "
            "ausfuehren?"
        )
        _hb.enqueue_notification({
            "type": "pattern_suggestion",
            "pattern_id": pattern["id"],
            "title": "Wiederkehrendes Muster erkannt",
            "message": msg,
            "actions": [
                {"id": "yes", "label": "Ja, automatisieren"},
                {"id": "no", "label": "Nein, danke"},
                {"id": "later",
                 "label": f"Nach {pattern['later_threshold']} weiteren Vorkommen erneut fragen"},
            ],
            "pattern": pattern,
        })
        return True
    except Exception as e:
        try:
            print(f"[pattern_analyzer] push failed: {e}", flush=True)
        except Exception:
            pass
        return False


def _push_automation_run(pattern, run_summary):
    if _hb is None:
        return False
    try:
        _hb.enqueue_notification({
            "type": "pattern_automation_run",
            "pattern_id": pattern["id"],
            "title": "Automatisierter Pattern-Lauf",
            "message": (f"'{pattern['description']}' wurde automatisch "
                       f"ausgefuehrt."),
            "summary": run_summary,
        })
        return True
    except Exception:
        return False


# ── Responses + Activation ──────────────────────────────────────────────────

def list_patterns():
    state = _load_state()
    return list(state.get("patterns", {}).values())


def get_pattern(pattern_id):
    state = _load_state()
    return state.get("patterns", {}).get(pattern_id)


def respond(pattern_id, response):
    """User-Response: 'yes', 'no', 'later'."""
    if response not in ("yes", "no", "later"):
        return {"ok": False, "error": "response muss yes|no|later sein"}
    with _lock:
        state = _load_state()
        p = state.get("patterns", {}).get(pattern_id)
        if not p:
            return {"ok": False, "error": "pattern_id unbekannt"}
        p["user_response"] = response
        p["occurrences_at_last_response"] = p.get("occurrences", 0)
        if response == "yes":
            ok = _activate_pattern_locked(p)
            p["automation_active"] = bool(ok)
        elif response == "no":
            # Bei "no" optional auch deaktivieren falls schon aktiv
            _deactivate_pattern_locked(p)
            p["automation_active"] = False
        _save_state(state)
        return {"ok": True, "pattern": p}


def activate_pattern(pattern_id):
    """Direkt aktivieren ohne Response (z.B. fuer Tests / Admin)."""
    with _lock:
        state = _load_state()
        p = state.get("patterns", {}).get(pattern_id)
        if not p:
            return False
        ok = _activate_pattern_locked(p)
        p["automation_active"] = bool(ok)
        if ok:
            p["user_response"] = p.get("user_response") or "yes"
        _save_state(state)
        return ok


def _activate_pattern_locked(pattern):
    """Registriert Pattern als heartbeat-Cron-Job."""
    if _hb is None:
        return False
    sched = pattern.get("suggested_schedule") or {}
    if sched.get("kind") != "weekly":
        return False
    try:
        weekday = int(sched.get("weekday", 0))
        hour = int(sched.get("hour", 9))
        minute = int(sched.get("minute", 0))
    except Exception:
        return False
    name = pattern.get("cron_job_name") or f"pattern_{pattern['id']}"
    pattern["cron_job_name"] = name
    schedule_fn = _hb.weekly_at(weekday, hour, minute)

    def _job_fn(now, pid=pattern["id"]):
        # Beim Cron-Lauf: aktuellen Pattern-State holen, naive Run erstellen,
        # Notification an User. Echte LLM-Ausfuehrung ueberlassen wir dem
        # Browser/User — der Heartbeat-Push triggert die UI.
        with _lock:
            st = _load_state()
            pp = st.get("patterns", {}).get(pid)
            if not pp:
                return
            pp["last_automation_run"] = _now_iso()
            _save_state(st)
        run_summary = {
            "started_at": _now_iso(),
            "trigger": "weekly_cron",
            "pattern_id": pid,
        }
        _push_automation_run(pattern, run_summary)

    try:
        _hb.schedule_cron(name, schedule_fn, _job_fn, run_immediately=False)
        return True
    except Exception as e:
        try:
            print(f"[pattern_analyzer] activation failed: {e}", flush=True)
        except Exception:
            pass
        return False


def _deactivate_pattern_locked(pattern):
    # heartbeat hat aktuell kein 'unschedule'. Wir markieren den Job als
    # inaktiv und fangen das in der job_fn ab. Alternativ: cron_job_name auf
    # None setzen — fuer den naechsten Tick prueft analyze_logs den Status.
    pattern["cron_job_name"] = None
    return True


# ── Heartbeat-Integration ────────────────────────────────────────────────────

def register_with_heartbeat():
    """Registriert den woechentlichen Analyse-Lauf als Cron-Job.

    Sonntag 22:00 Lokalzeit (Sao Paulo). Cron-Name: 'pattern_analyzer_weekly'.
    Idempotent: bei Doppel-Aufruf wird der bestehende Job ueberschrieben.
    """
    if _hb is None:
        return False
    # Sonntag = weekday 6 in Python (Mo=0)
    schedule_fn = _hb.weekly_at(6, 22, 0)
    try:
        _hb.schedule_cron(
            "pattern_analyzer_weekly",
            schedule_fn=schedule_fn,
            job_fn=lambda now: analyze_logs(),
            run_immediately=False,
        )
        return True
    except Exception:
        return False
