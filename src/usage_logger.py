"""
usage_logger.py — Passive Turn-Logger fuer AssistantDev.

Schreibt jeden /chat-Turn als JSON-Zeile nach
  <datalake>/usage_logs/usage_YYYY-MM.jsonl

Async via Hintergrund-Daemon-Thread und queue.Queue: log_turn() blockiert nie
einen Request — schlimmstenfalls geht ein Eintrag bei Crash verloren, was
fuer Datenanalyse hinnehmbar ist.

Exposed API:
    log_turn(...)                     fire-and-forget Eintrag in JSONL
    classify_task(msg)                Keyword-Klassifikator -> Kategorie
    estimate_tokens(text)             Heuristik (len // 4)
    get_summary()                     Aggregat fuer /api/usage/summary
"""
import os
import re
import json
import queue
import threading
import datetime
from collections import Counter, defaultdict

try:
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo("America/Sao_Paulo")
except Exception:
    _TZ = None  # Fallback: lokale Systemzeit

_BASE = os.path.expanduser(
    "~/Library/Mobile Documents/com~apple~CloudDocs/"
    "Downloads shared/claude_datalake"
)
USAGE_LOGS_DIR = os.path.join(_BASE, "usage_logs")

CATEGORIES = [
    "research", "coding", "writing", "email", "document",
    "calendar", "image", "video", "translation", "analysis",
    "search", "other",
]

# Reihenfolge ist Prioritaet: erste passende Kategorie gewinnt bei Mehrfach-Treffern.
_KEYWORD_RULES = [
    ("video", [
        "video", "clip generier", "film generier", "animation",
        "generier ein video", "create video", "veo", "reels", "tiktok video",
    ]),
    ("image", [
        "bild generier", "generiere ein bild", "image generation",
        "create image", "illustrat", "grafik erstell", "infografik",
        "create_image", "imagen ", "midjourney", "dall-e",
    ]),
    ("translation", [
        "uebersetz", "übersetz", "translate", "translation",
        "ins englische", "ins deutsche", "auf portugiesisch",
        "in english", "in german", "in portuguese",
    ]),
    ("email", [
        "e-mail", "email", "mail an", "betreff", "antwort an",
        "reply", "inbox", "schreib eine mail", "write an email",
    ]),
    ("calendar", [
        "kalender", "calendar", "termin", "meeting", "event",
        "vereinbar", "schedule", "appointment",
    ]),
    ("coding", [
        "code", "python", "javascript", "typescript", "funktion",
        "function", "bug", "fix", "debug", "refactor", "repository",
        "git ", "deploy", "server", "endpoint", "stack trace",
        "syntax error", "compile",
    ]),
    ("document", [
        "dokument", "document", ".pdf", ".docx", "report",
        "praesentation", "präsentation", "slides", "powerpoint",
    ]),
    ("research", [
        "recherche", "research", "suche heraus", "find out",
        "wer ist", "was ist", "quelle", "quellen", "wikipedia",
        "studie", "studies", "marktanalyse", "market analysis",
        "deep research", "tiefgehende",
    ]),
    ("writing", [
        "schreib", "geschrieb", "draft", "entwurf", "formulier", "blog",
        "newsletter", "artikel", "post für", "post fuer", "social",
        "linkedin post", "twitter post", "redigier",
    ]),
    ("analysis", [
        "analysier", "analyze", "analysis", "vergleich", "compare",
        "evaluate", "bewerte", "metric", "kennzahl", "auswert",
        "interpretier",
    ]),
    ("search", [
        "/find ", "such ", "search ", "find ", "wo ist", "where is",
        "look for", "finde ",
    ]),
]


# ── Stemming ─────────────────────────────────────────────────────────────────
# Custom Suffix-Stripper fuer deutsches Token-Matching. Loest das Problem,
# dass z.B. "recherchiere" nicht Substring "recherche" enthaelt.
# Suffix-Liste: laengste zuerst (Greedy-Match). Min-Stem-Laenge 4.
# Lehnwoerter (email, meeting, ...) werden NICHT gestemmt (siehe _LOANWORDS).

_SUFFIXES = [
    "iertest", "iertet", "ierten", "ierte",
    "ieren", "iert", "ierst", "iere", "ier",
    "endes", "enden", "endem", "ender", "ende",
    "ungen", "ungs", "ung",
    "isch", "ische", "ischen",
    "lich", "liche", "lichen",
    "est", "en", "er", "es", "em",
    "st", "te",
    "e", "t", "s", "n",
]
_SUFFIXES.sort(key=len, reverse=True)

# Lehnwoerter / Anglizismen: nicht stemmen (sonst wird "email" zu "emai")
_LOANWORDS = {
    "email", "mail", "meeting", "report", "post", "social", "linkedin",
    "twitter", "blog", "newsletter", "code", "python", "javascript",
    "typescript", "function", "bug", "fix", "debug", "deploy", "server",
    "api", "endpoint", "compile", "git", "research", "find", "search",
    "analyze", "analysis", "calendar", "translate", "translation",
    "image", "video", "document", "test", "ok", "wikipedia",
}


def _stem(word):
    """Greedy Suffix-Stripping mit Min-Laenge 4. Lehnwoerter unveraendert."""
    if not isinstance(word, str):
        return ""
    w = word.lower().strip()
    if not w:
        return ""
    # Umlaut-Normalisierung
    w = (w.replace("ä", "a").replace("ö", "o").replace("ü", "u")
          .replace("ß", "ss"))
    if w in _LOANWORDS:
        return w
    if len(w) <= 4:
        return w
    for suf in _SUFFIXES:
        if len(suf) >= len(w):
            continue
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            return w[:-len(suf)]
    return w


def _is_single_word_keyword(kw):
    return isinstance(kw, str) and " " not in kw and "/" not in kw


# Pre-Compiled Stem-Index. Single-Word-Keywords werden gestemmt + im Dict
# abgelegt. Multi-Word-Keywords (z.B. "suche heraus", "wer ist") laufen
# weiter ueber substring-Match.
_STEM_INDEX = {}    # stem -> first matching category
_MULTI_WORD = []    # list of (category, keyword)
_TOKEN_RE = re.compile(r"[a-z0-9äöüß]{2,}", re.UNICODE)


def _build_keyword_index():
    _STEM_INDEX.clear()
    _MULTI_WORD.clear()
    for category, keywords in _KEYWORD_RULES:
        for kw in keywords:
            if _is_single_word_keyword(kw):
                stem = _stem(kw)
                if not stem:
                    continue
                _STEM_INDEX.setdefault(stem, category)
            else:
                _MULTI_WORD.append((category, kw.lower()))


_build_keyword_index()


def classify_task(msg):
    """Best-effort Kategorisierung anhand von Keywords + Stems. Default 'other'.

    Strategie:
    1. Multi-Word-Keywords: substring-Match (aelter Pfad, robust fuer
       Phrasen wie "suche heraus", "wer ist", "find out").
    2. Single-Word-Keywords: Token-basiertes Stem-Matching. Tokens werden
       gestemmt, im Pre-Compiled Index nachgeschlagen. Liefert die Kategorie
       des ERSTEN Keywords aus _KEYWORD_RULES (Reihenfolge = Prioritaet).
    """
    if not isinstance(msg, str) or not msg.strip():
        return "other"
    m = msg.lower()

    # Stage 1: Multi-Word substring-Match in Original-Reihenfolge
    for category, kw in _MULTI_WORD:
        if kw in m:
            return category

    # Stage 2: Token-Match per Stem-Lookup. Aber Reihenfolge in
    # _KEYWORD_RULES ist Prioritaet — wir muessen pro Kategorie pruefen,
    # ob irgendein Token-Stem in _STEM_INDEX dieser Kategorie matcht.
    tokens = _TOKEN_RE.findall(m)
    if not tokens:
        return "other"
    token_stems = {_stem(t) for t in tokens if t}

    for category, keywords in _KEYWORD_RULES:
        for kw in keywords:
            if not _is_single_word_keyword(kw):
                continue
            kw_stem = _stem(kw)
            if not kw_stem:
                continue
            if kw_stem in token_stems:
                return category

    return "other"


def estimate_tokens(text):
    """Grobe Schaetzung: ~4 Zeichen pro Token (englisch/deutsch durchschnitt)."""
    if not text:
        return 0
    if not isinstance(text, str):
        text = str(text)
    return max(1, len(text) // 4)


def _now_iso():
    if _TZ is not None:
        return datetime.datetime.now(_TZ).isoformat(timespec="seconds")
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def _current_logfile():
    if _TZ is not None:
        ym = datetime.datetime.now(_TZ).strftime("%Y-%m")
    else:
        ym = datetime.datetime.now().strftime("%Y-%m")
    return os.path.join(USAGE_LOGS_DIR, f"usage_{ym}.jsonl")


# ── Background writer ────────────────────────────────────────────────────────

_write_queue = queue.Queue(maxsize=10000)
_writer_started = False
_writer_lock = threading.Lock()


def _writer_loop():
    while True:
        try:
            entry = _write_queue.get()
        except Exception:
            continue
        if entry is None:
            return  # Sentinel — used by tests
        try:
            os.makedirs(USAGE_LOGS_DIR, exist_ok=True)
            path = _current_logfile()
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            # Loggen aber nicht crashen — der Logger darf den Server nie stoeren.
            try:
                print(f"[usage_logger] write failed: {e}", flush=True)
            except Exception:
                pass


def _ensure_writer():
    global _writer_started
    if _writer_started:
        return
    with _writer_lock:
        if _writer_started:
            return
        t = threading.Thread(target=_writer_loop, name="usage-logger-writer", daemon=True)
        t.start()
        _writer_started = True


def log_turn(*, agent, provider, model, user_message, assistant_response,
             duration_seconds, sub_agent=None, session_id=None,
             extra=None):
    """Fire-and-forget: legt einen Turn in die Schreibqueue.

    Niemals blockierend: bei voller Queue wird verworfen statt zu warten.
    """
    try:
        _ensure_writer()
        entry = {
            "timestamp": _now_iso(),
            "session_id": session_id,
            "agent": agent,
            "sub_agent": sub_agent,
            "provider": provider,
            "model": model,
            "user_message": user_message or "",
            "assistant_response": assistant_response or "",
            "duration_seconds": round(float(duration_seconds), 3) if duration_seconds is not None else None,
            "tokens_estimated": {
                "input": estimate_tokens(user_message),
                "output": estimate_tokens(assistant_response),
            },
            "category": classify_task(user_message),
        }
        if extra and isinstance(extra, dict):
            entry["extra"] = extra
        try:
            _write_queue.put_nowait(entry)
        except queue.Full:
            print("[usage_logger] write queue full — entry dropped", flush=True)
    except Exception as e:
        try:
            print(f"[usage_logger] log_turn failed: {e}", flush=True)
        except Exception:
            pass


# ── Reader / Summary ─────────────────────────────────────────────────────────

def _iter_entries(months_back=2):
    """Liest die letzten N Monatsdateien als generator von dicts."""
    if _TZ is not None:
        now = datetime.datetime.now(_TZ)
    else:
        now = datetime.datetime.now()
    paths = []
    for offset in range(months_back + 1):
        # naive month rollback: subtract 30 days * offset
        ts = now - datetime.timedelta(days=30 * offset)
        path = os.path.join(USAGE_LOGS_DIR, f"usage_{ts.strftime('%Y-%m')}.jsonl")
        if path not in paths:
            paths.append(path)
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


def _parse_ts(entry):
    ts = entry.get("timestamp")
    if not ts:
        return None
    try:
        return datetime.datetime.fromisoformat(ts)
    except Exception:
        return None


def get_summary():
    """Aggregat-Statistiken fuer GET /api/usage/summary."""
    if _TZ is not None:
        now = datetime.datetime.now(_TZ)
    else:
        now = datetime.datetime.now().astimezone()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - datetime.timedelta(days=now.weekday())  # Montag
    month_start = today_start.replace(day=1)

    today = 0
    week = 0
    month = 0
    cat_counter = Counter()
    model_per_agent = defaultdict(Counter)
    durations = []
    total = 0

    for e in _iter_entries(months_back=1):
        ts = _parse_ts(e)
        if ts is None:
            continue
        # Wenn naive: lokal interpretieren
        if ts.tzinfo is None and _TZ is not None:
            ts = ts.replace(tzinfo=_TZ)
        total += 1
        if ts >= month_start:
            month += 1
            cat = e.get("category") or "other"
            cat_counter[cat] += 1
            agent = e.get("agent") or "unknown"
            model = e.get("model") or "unknown"
            model_per_agent[agent][model] += 1
            d = e.get("duration_seconds")
            if isinstance(d, (int, float)):
                durations.append(float(d))
        if ts >= week_start:
            week += 1
        if ts >= today_start:
            today += 1

    top_categories = [
        {"category": c, "count": n}
        for c, n in cat_counter.most_common(5)
    ]
    top_model = {}
    for agent, c in model_per_agent.items():
        if not c:
            continue
        model, cnt = c.most_common(1)[0]
        top_model[agent] = {"model": model, "count": cnt}

    avg = round(sum(durations) / len(durations), 2) if durations else 0.0

    return {
        "turns_today": today,
        "turns_this_week": week,
        "turns_this_month": month,
        "turns_total_scanned": total,
        "top_categories": top_categories,
        "top_model_per_agent": top_model,
        "avg_turn_duration_seconds": avg,
        "logfile": _current_logfile(),
    }
