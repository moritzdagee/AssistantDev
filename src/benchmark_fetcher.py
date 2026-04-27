"""
benchmark_fetcher.py — Woechentliche Aktualisierung der skill_database aus
externen Benchmark-Quellen.

Strategie:
- Pluggable Sources: jede Source liefert eine Liste von Update-Dicts der Form
    {"model_ref": "<provider>/<model_id>", "skill": "<skill>", "rating": 1-5}
- Aggregat wird durch skill_database.apply_updates() persistiert. Diff wird in
  config/skill_database_changes.jsonl geschrieben (das macht die Library).
- Scheduler-Thread prueft einmal pro Stunde, ob Wochen-Slot faellig ist
  (Montag, ab 06:00 Lokalzeit America/Sao_Paulo, mindestens 6 Tage seit
  letztem Lauf).
- Bei signifikanten Aenderungen (>=1 Punkt Differenz auf irgend einem Skill)
  wird eine "Heartbeat-Notification" geschrieben — Heartbeat-System existiert
  noch nicht (Feature 1+2 der Roadmap), Notifications landen aktuell in
  config/pending_notifications.jsonl und werden vom Heartbeat-Daemon konsumiert,
  sobald er online ist.

Public API:
    run_once(force=False)   -> dict   Komplett-Lauf, returns summary
    should_run_now()        -> bool
    start_scheduler()       -> Thread Daemon-Thread starten (idempotent)
    state_path()            -> str
"""
import os
import json
import time
import threading
import datetime
import re

try:
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo("America/Sao_Paulo")
except Exception:
    _TZ = None

try:
    import requests
except Exception:
    requests = None

try:
    import skill_database as _sd
except Exception:
    _sd = None

_BASE = os.path.expanduser(
    "~/Library/Mobile Documents/com~apple~CloudDocs/"
    "Downloads shared/claude_datalake"
)
STATE_PATH = os.path.join(_BASE, "config", "benchmark_fetcher_state.json")
NOTIFICATIONS_PATH = os.path.join(_BASE, "config", "pending_notifications.jsonl")

_scheduler_lock = threading.Lock()
_scheduler_started = False


def state_path():
    return STATE_PATH


def _now():
    if _TZ is not None:
        return datetime.datetime.now(_TZ)
    return datetime.datetime.now().astimezone()


def _now_iso():
    return _now().isoformat(timespec="seconds")


def _load_state():
    if not os.path.exists(STATE_PATH):
        return {"last_run": None, "last_status": None, "history": []}
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"last_run": None, "last_status": None, "history": []}


def _save_state(state):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, STATE_PATH)


def should_run_now():
    """True, wenn Wochen-Slot faellig ist."""
    now = _now()
    state = _load_state()
    last_run = state.get("last_run")
    # Bedingung 1: Montag 06:00 Lokalzeit oder spaeter
    if now.weekday() != 0:  # 0 = Monday
        return False
    if now.hour < 6:
        return False
    # Bedingung 2: Mindestens 6 Tage seit letztem Lauf
    if last_run:
        try:
            last_dt = datetime.datetime.fromisoformat(last_run)
            if last_dt.tzinfo is None and _TZ is not None:
                last_dt = last_dt.replace(tzinfo=_TZ)
            if (now - last_dt).total_seconds() < 6 * 86400:
                return False
        except Exception:
            pass
    return True


# ── Sources ──────────────────────────────────────────────────────────────────

# Mapping aus Benchmark-Kategorien zu unseren internen Skills.
# Wenn artificialanalysis.ai z.B. einen "coding" Score liefert, mappen wir das
# auf coding. Mehrere externe Spalten koennen denselben internen Skill
# beeinflussen (z.B. "math" + "reasoning" -> reasoning).
_SOURCE_MAP_AA = {
    "quality": "reasoning",
    "intelligence": "reasoning",
    "coding": "coding",
    "humaneval": "coding",
    "math": "reasoning",
    "long_context": "document_analysis",
    "speed": "speed",
    "tokens_per_second": "speed",
    "price": "cost_efficiency",
    "cost": "cost_efficiency",
}


def _aa_score_to_rating(value, kind):
    """Externer Score (kann float, int oder Prozent sein) -> 1-5."""
    try:
        v = float(value)
    except Exception:
        return None
    if v <= 0:
        return None
    if kind in ("speed", "tokens_per_second"):
        # tok/s grob: <30 schlecht, >150 sehr gut
        if v >= 150: return 5
        if v >= 100: return 4
        if v >= 60:  return 3
        if v >= 30:  return 2
        return 1
    if kind in ("price", "cost"):
        # niedriger = besser
        if v <= 0.5:  return 5
        if v <= 2:    return 4
        if v <= 10:   return 3
        if v <= 30:   return 2
        return 1
    # Default: Quality/Intelligence-Index (oft 0-100 oder 0-1)
    if v <= 1.0:
        v *= 100
    if v >= 80: return 5
    if v >= 65: return 4
    if v >= 50: return 3
    if v >= 35: return 2
    return 1


_AA_NAME_PATTERNS = [
    # (regex, provider, model_id) — Reihenfolge ist Prioritaet
    (re.compile(r"claude.*opus.*4[\.\-]?7", re.I), "anthropic", "claude-opus-4-7"),
    (re.compile(r"claude.*sonnet.*4[\.\-]?6", re.I), "anthropic", "claude-sonnet-4-6"),
    (re.compile(r"claude.*opus.*4[\.\-]?6", re.I), "anthropic", "claude-opus-4-6"),
    (re.compile(r"claude.*haiku.*4[\.\-]?5", re.I), "anthropic", "claude-haiku-4-5-20251001"),
    (re.compile(r"gpt[\-\s]?5\.5\s*pro", re.I), "openai", "gpt-5.5-pro"),
    (re.compile(r"gpt[\-\s]?5\.5", re.I), "openai", "gpt-5.5"),
    (re.compile(r"gpt[\-\s]?5\.4\s*pro", re.I), "openai", "gpt-5.4-pro"),
    (re.compile(r"gpt[\-\s]?5\.4\s*mini", re.I), "openai", "gpt-5.4-mini"),
    (re.compile(r"gpt[\-\s]?5\.4\s*nano", re.I), "openai", "gpt-5.4-nano"),
    (re.compile(r"gpt[\-\s]?5\.4", re.I), "openai", "gpt-5.4"),
    (re.compile(r"gpt[\-\s]?5\s*mini", re.I), "openai", "gpt-5-mini"),
    (re.compile(r"gpt[\-\s]?5\s*nano", re.I), "openai", "gpt-5-nano"),
    (re.compile(r"\bo3\s*pro\b", re.I), "openai", "o3-pro"),
    (re.compile(r"\bo3\b", re.I), "openai", "o3"),
    (re.compile(r"gemini.*3\.1.*pro", re.I), "gemini", "gemini-3.1-pro-preview"),
    (re.compile(r"gemini.*3\.1.*flash[\-\s]?lite", re.I), "gemini", "gemini-3.1-flash-lite-preview"),
    (re.compile(r"gemini.*3.*pro", re.I), "gemini", "gemini-3-pro-preview"),
    (re.compile(r"gemini.*3.*flash", re.I), "gemini", "gemini-3-flash-preview"),
    (re.compile(r"gemini.*2\.5.*pro", re.I), "gemini", "gemini-2.5-pro"),
    (re.compile(r"gemini.*2\.5.*flash", re.I), "gemini", "gemini-2.5-flash"),
    (re.compile(r"deepseek[\s\-]*v4[\s\-]*pro", re.I), "deepseek", "deepseek-v4-pro"),
    (re.compile(r"deepseek[\s\-]*v4[\s\-]*flash", re.I), "deepseek", "deepseek-v4-flash"),
    (re.compile(r"sonar.*deep.*research", re.I), "perplexity", "sonar-deep-research"),
    (re.compile(r"sonar.*reasoning.*pro", re.I), "perplexity", "sonar-reasoning-pro"),
    (re.compile(r"sonar.*pro", re.I), "perplexity", "sonar-pro"),
    (re.compile(r"\bsonar\b", re.I), "perplexity", "sonar"),
    (re.compile(r"magistral.*medium", re.I), "mistral", "magistral-medium-latest"),
    (re.compile(r"magistral.*small", re.I), "mistral", "magistral-small-latest"),
    (re.compile(r"mistral.*large", re.I), "mistral", "mistral-large-latest"),
    (re.compile(r"mistral.*medium", re.I), "mistral", "mistral-medium-latest"),
    (re.compile(r"mistral.*small", re.I), "mistral", "mistral-small-latest"),
    (re.compile(r"codestral", re.I), "mistral", "codestral-latest"),
]


def _resolve_model_ref(name):
    if not isinstance(name, str):
        return None
    for rx, prov, mid in _AA_NAME_PATTERNS:
        if rx.search(name):
            return f"{prov}/{mid}"
    return None


def fetch_from_artificialanalysis(timeout=15):
    """Best-effort: holt Quality/Speed/Price-Daten von artificialanalysis.ai.

    Die Site ist eine Next.js-App und embedded ein __NEXT_DATA__ JSON. Wir
    versuchen das zu lesen. Schlaegt der Abruf oder das Parsen fehl, wird eine
    leere Liste zurueckgegeben — kein Crash.
    """
    if requests is None:
        return {"updates": [], "source_ok": False, "reason": "requests fehlt"}
    try:
        r = requests.get(
            "https://artificialanalysis.ai/models",
            timeout=timeout,
            headers={"User-Agent": "Mozilla/5.0 AssistantDev/benchmark_fetcher"},
        )
        if r.status_code != 200:
            return {"updates": [], "source_ok": False,
                    "reason": f"http {r.status_code}"}
        html = r.text
    except Exception as e:
        return {"updates": [], "source_ok": False, "reason": str(e)}

    m = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        return {"updates": [], "source_ok": False, "reason": "no __NEXT_DATA__"}
    try:
        nd = json.loads(m.group(1))
    except Exception as e:
        return {"updates": [], "source_ok": False, "reason": f"json parse: {e}"}

    # Tiefe Suche nach Listen, deren Eintraege ein 'name' UND ein
    # quality/intelligence-Feld enthalten — robust gegen Schema-Aenderungen.
    found_models = []

    def _walk(node):
        if isinstance(node, list):
            for it in node:
                _walk(it)
        elif isinstance(node, dict):
            keys = set(node.keys())
            if "name" in keys and (keys & {
                "quality_index", "quality", "intelligence_index",
                "median_output_tokens_per_second",
                "tokens_per_second", "speed",
                "median_price_per_million", "price",
            }):
                found_models.append(node)
            for v in node.values():
                _walk(v)

    try:
        _walk(nd)
    except Exception:
        pass

    updates = []
    seen = set()
    for entry in found_models:
        ref = _resolve_model_ref(entry.get("name"))
        if not ref:
            continue
        for src_key, internal_skill in _SOURCE_MAP_AA.items():
            if src_key not in entry:
                continue
            rating = _aa_score_to_rating(entry.get(src_key), src_key)
            if rating is None:
                continue
            sig = (ref, internal_skill)
            if sig in seen:
                continue
            seen.add(sig)
            updates.append({
                "model_ref": ref,
                "skill": internal_skill,
                "rating": rating,
                "source": "artificialanalysis.ai",
            })

    return {"updates": updates, "source_ok": True,
            "models_seen": len(found_models)}


# Liste registrierter Sources. Spaeter koennen weitere via register_source
# eingehaengt werden (z.B. lmarena, evalplus).
_SOURCES = [
    ("artificialanalysis", fetch_from_artificialanalysis),
]


def register_source(name, fn):
    _SOURCES.append((name, fn))


# ── Notification ─────────────────────────────────────────────────────────────

def _emit_notification(payload):
    """Schreibt Push-Kandidat in pending_notifications.jsonl. Heartbeat-Daemon
    (Feature 1+2) wird das spaeter konsumieren."""
    try:
        os.makedirs(os.path.dirname(NOTIFICATIONS_PATH), exist_ok=True)
        with open(NOTIFICATIONS_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[benchmark_fetcher] notification write failed: {e}", flush=True)


# ── Run-Once ─────────────────────────────────────────────────────────────────

def run_once(force=False):
    """Fuehrt alle Sources aus und applied Updates. Liefert Summary-Dict."""
    if _sd is None:
        return {"ok": False, "error": "skill_database nicht geladen",
                "started_at": _now_iso(), "changes": []}

    started = _now_iso()
    if not force and not should_run_now():
        return {"ok": False, "skipped": True,
                "reason": "not due (Mo>=06:00 + 6d seit letztem Lauf)",
                "started_at": started, "changes": []}

    summary = {
        "ok": True, "started_at": started, "finished_at": None,
        "sources": [], "all_updates": 0, "applied_changes": [],
    }

    aggregated = []
    for name, fn in _SOURCES:
        try:
            res = fn()
            updates = res.get("updates", []) if isinstance(res, dict) else []
            summary["sources"].append({
                "name": name,
                "ok": bool(res.get("source_ok")) if isinstance(res, dict) else False,
                "updates": len(updates),
                "reason": (res or {}).get("reason"),
            })
            for u in updates:
                u["source"] = u.get("source") or name
            aggregated.extend(updates)
        except Exception as e:
            summary["sources"].append({"name": name, "ok": False, "error": str(e)})

    summary["all_updates"] = len(aggregated)

    if aggregated:
        try:
            changes = _sd.apply_updates(aggregated, source="benchmark_fetcher")
            summary["applied_changes"] = changes
            # Bei signifikanten Aenderungen Heartbeat-Notification kandidieren.
            big = [c for c in changes if abs(int(c["new"]) - int(c["old"])) >= 1]
            if big:
                _emit_notification({
                    "type": "skill_database_update",
                    "timestamp": _now_iso(),
                    "changes_total": len(changes),
                    "changes_significant": len(big),
                    "samples": big[:10],
                })
        except Exception as e:
            summary["ok"] = False
            summary["error"] = f"apply_updates failed: {e}"

    summary["finished_at"] = _now_iso()
    state = _load_state()
    state["last_run"] = summary["finished_at"]
    state["last_status"] = "ok" if summary.get("ok") else "error"
    history = state.setdefault("history", [])
    history.append({
        "ts": summary["finished_at"],
        "applied": len(summary["applied_changes"]),
        "sources": [s["name"] for s in summary["sources"]],
    })
    # Halte History kompakt
    state["history"] = history[-20:]
    _save_state(state)
    return summary


# ── Scheduler ────────────────────────────────────────────────────────────────

def _scheduler_loop():
    while True:
        try:
            if should_run_now():
                run_once()
        except Exception as e:
            print(f"[benchmark_fetcher] scheduler tick failed: {e}", flush=True)
        # Stuendlicher Tick
        time.sleep(3600)


def start_scheduler():
    """Daemon-Thread starten, idempotent."""
    global _scheduler_started
    with _scheduler_lock:
        if _scheduler_started:
            return False
        t = threading.Thread(target=_scheduler_loop,
                             name="benchmark-fetcher-scheduler",
                             daemon=True)
        t.start()
        _scheduler_started = True
        return True
