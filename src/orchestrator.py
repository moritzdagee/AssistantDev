"""
orchestrator.py — Roadmap-Feature 6 (April 2026).

Wenn eine User-Anfrage komplex genug ist, schlaegt der Orchestrator vor,
sie in Teilaufgaben zu zerlegen und jede Teilaufgabe an das jeweils beste
Modell aus der skill_database zu delegieren.

Drei Phasen:
1. should_orchestrate(msg)        — heuristische Pruefung
2. propose(msg)                   — Plan bauen + Notification
3. execute_step(proposal_id, idx) — einzelnen Schritt ausfuehren

Decomposition kann per LLM laufen (set_llm_invoker) oder rein heuristisch
(Bullet-Listen, Nummerierungen, Mehrkategorien-Erkennung). LLM-Pfad ist
empfohlen fuer Produktion, Heuristik ist Fallback fuer Tests + Offline.

Public API:
    should_orchestrate(msg, min_words=50)  -> dict   {orchestrate, reason, ...}
    propose(msg, session_id=None)          -> dict   proposal-Snapshot
    list_proposals()                        -> list
    get_proposal(proposal_id)              -> dict
    respond(proposal_id, response)         -> dict   yes / no / edit
    execute_step(proposal_id, step_index, prior_output=None) -> dict
    set_llm_invoker(fn)                    -> None
"""
import os
import json
import re
import datetime
import threading
import uuid

try:
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo("America/Sao_Paulo")
except Exception:
    _TZ = None

try:
    import skill_database as _sd
except Exception:
    _sd = None

try:
    import usage_logger as _ul
except Exception:
    _ul = None

try:
    import heartbeat as _hb
except Exception:
    _hb = None

try:
    import pattern_analyzer as _pa
except Exception:
    _pa = None

_BASE = os.path.expanduser(
    "~/Library/Mobile Documents/com~apple~CloudDocs/"
    "Downloads shared/claude_datalake"
)
PROPOSALS_PATH = os.path.join(_BASE, "patterns", "orchestrator_proposals.json")
_ORCHESTRATOR_CONFIG_PATH = os.path.join(_BASE, "config", "orchestrator.json")

# Fallback-Cascade: erstes Modell, das funktioniert, gewinnt. Lokal zuerst,
# damit der Orchestrator auch offline einsatzbereit ist (User-Wunsch
# 2026-04-28: "Sonst ist der ganze Agent komplett useless wenn ich keine
# Internetverbindung habe").
_DEFAULT_DECOMPOSER_CASCADE = [
    ("ollama", "deepseek-r1:14b"),
    ("ollama", "deepseek-r1:8b"),
    ("ollama", "qwen3:14b"),
    ("deepseek", "deepseek-v4-flash"),
    ("anthropic", "claude-haiku-4-5-20251001"),
]


def _load_orchestrator_config():
    try:
        with open(_ORCHESTRATOR_CONFIG_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def _decomposer_cascade():
    """Effektive Cascade aus config/orchestrator.json oder Default."""
    cfg = _load_orchestrator_config()
    raw = cfg.get("decomposer_cascade")
    if isinstance(raw, list) and raw:
        cascade = []
        for item in raw:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                cascade.append((str(item[0]), str(item[1])))
        if cascade:
            return cascade
    return list(_DEFAULT_DECOMPOSER_CASCADE)


# Backwards-Compat: Modul-Konstante zeigt auf das erste Modell der Cascade
# (alte Stellen die DECOMPOSITION_MODEL importieren bekommen das primary).
DECOMPOSITION_MODEL = _decomposer_cascade()[0]

MIN_WORDS_FOR_ORCHESTRATION = 50
MIN_DISTINCT_CATEGORIES = 2

# Wiederverwendet aus pattern_analyzer (gleiche Map). Lokale Kopie haelt
# die Module entkoppelt.
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
    "orchestrated": "reasoning",
}

_lock = threading.RLock()
_llm_invoker = None  # callable(provider, model_id, system_prompt, user_msg) -> str


# ── LLM-Invoker (wird von web_server beim Import gesetzt) ────────────────────

def set_llm_invoker(fn):
    """Erlaubt web_server.py, die ADAPTERS-basierte LLM-Funktion einzuhaengen.

    fn(provider, model_id, system_prompt, user_msg) -> str
    """
    global _llm_invoker
    _llm_invoker = fn


def _now():
    if _TZ is not None:
        return datetime.datetime.now(_TZ)
    return datetime.datetime.now().astimezone()


def _now_iso():
    return _now().isoformat(timespec="seconds")


# ── Heuristik: should_orchestrate ────────────────────────────────────────────

_BULLET_RE = re.compile(r"^\s*(?:[-*•]|\d+[\.\)])\s+", re.MULTILINE)


def _count_words(s):
    if not isinstance(s, str):
        return 0
    return len(re.findall(r"\b[\w'\-äöüÄÖÜß]+\b", s))


def _detect_categories(msg):
    """Findet alle Kategorien, die irgendwo in der Message vorkommen.

    Anders als usage_logger.classify_task (das genau EINE liefert), gehen wir
    durch ALLE Keyword-Regeln und sammeln alle Treffer — sodass eine
    Kombination wie "Recherche + Bild generieren + Report schreiben" drei
    verschiedene Kategorien als orchestrierungsbeduerftig erkennt.
    """
    if not isinstance(msg, str) or not msg.strip():
        return []
    if _ul is None:
        return []
    m = msg.lower()
    found = []
    for category, keywords in getattr(_ul, "_KEYWORD_RULES", []):
        for kw in keywords:
            if kw in m:
                if category not in found:
                    found.append(category)
                break
    return found


def should_orchestrate(msg, min_words=MIN_WORDS_FOR_ORCHESTRATION,
                      min_categories=MIN_DISTINCT_CATEGORIES,
                      force=False):
    """Heuristische Pruefung. Liefert Diagnose-Dict.

    {orchestrate: bool, reason: str, words, categories, has_bullets}
    """
    out = {
        "orchestrate": False,
        "msg_excerpt": (msg or "")[:120],
        "words": _count_words(msg),
        "categories": _detect_categories(msg),
        "has_bullets": False,
        "reason": "",
    }
    if not isinstance(msg, str) or not msg.strip():
        out["reason"] = "leere Nachricht"
        return out

    out["has_bullets"] = bool(_BULLET_RE.search(msg))

    if force:
        out["orchestrate"] = True
        out["reason"] = "force=True"
        return out

    # Bullet-Listen >= 2 Bullets sind starker Hinweis auf Mehrschritt
    bullet_count = len(_BULLET_RE.findall(msg))
    if bullet_count >= 2:
        out["orchestrate"] = True
        out["reason"] = f"{bullet_count} Bullet-Punkte erkannt"
        return out

    # Mehrere Kategorien = unterschiedliche Modell-Faehigkeiten gefragt
    if len(out["categories"]) >= min_categories:
        out["orchestrate"] = True
        out["reason"] = (f"{len(out['categories'])} Kategorien "
                        f"({', '.join(out['categories'])})")
        return out

    # Lange Anfrage + nicht-trivial (>= 1 erkannte Kategorie != 'other')
    has_real_cat = any(c != "other" for c in out["categories"])
    if out["words"] >= min_words and has_real_cat:
        out["orchestrate"] = True
        out["reason"] = (f"{out['words']} Woerter, "
                        f"Kategorie '{out['categories'][0]}'")
        return out

    out["reason"] = "kurze/einfache Anfrage — keine Orchestrierung noetig"
    return out


# ── Decomposition ────────────────────────────────────────────────────────────

_DECOMP_SYSTEM_PROMPT = """Du bist ein Aufgaben-Zerleger.

Eingabe: eine User-Anfrage, die mehrere Teilaufgaben enthaelt.
Aufgabe: zerlege sie in 2 bis 6 sequentielle Teilaufgaben.

Antworte AUSSCHLIESSLICH mit gueltigem JSON in diesem Schema:

{
  "subtasks": [
    {"step": 1, "description": "...", "category": "<kategorie>"},
    {"step": 2, "description": "...", "category": "<kategorie>"}
  ]
}

Erlaubte Kategorien: research, coding, writing, email, document, calendar,
image, video, translation, analysis, search, other.

Wichtige Regeln:
- Sequentielle Reihenfolge — Schritt 2 darf das Ergebnis von Schritt 1 voraussetzen.
- Keine Anrede, keine Erklaerung, kein Markdown — nur JSON.
- Beschreibung pro Schritt 1-2 Saetze, klar handlungsleitend.
"""


def _decompose_via_llm(msg):
    """Probiert die Decomposer-Cascade durch (offline-first).

    User-Wunsch 2026-04-28: 'Lieber DeepSeek-Local als Haiku — funktioniert
    auch ohne Internetverbindung.' Daher: lokal (Ollama) zuerst, Cloud nur
    als Fallback.
    """
    if _llm_invoker is None:
        return None
    cascade = _decomposer_cascade()
    last_error = None
    for provider, model_id in cascade:
        try:
            raw = _llm_invoker(provider, model_id, _DECOMP_SYSTEM_PROMPT,
                               [{"role": "user", "content": msg}])
        except Exception as e:
            last_error = e
            print(f"[orchestrator] {provider}/{model_id} fehlgeschlagen: {e} "
                  f"— probiere naechstes Modell der Cascade", flush=True)
            continue
        if not isinstance(raw, str):
            continue
        # JSON aus der Antwort extrahieren — manchmal kommt LLM mit Code-Fence
        # oder DeepSeek-R1 mit <think>...</think>-Block davor.
        m = re.search(r"\{[\s\S]*\}", raw)
        if not m:
            print(f"[orchestrator] {provider}/{model_id} lieferte kein JSON, "
                  f"probiere naechstes Modell", flush=True)
            continue
        try:
            data = json.loads(m.group(0))
        except Exception:
            print(f"[orchestrator] {provider}/{model_id}: JSON-parse-fail",
                  flush=True)
            continue
        subs = data.get("subtasks") if isinstance(data, dict) else None
        if not isinstance(subs, list) or not subs:
            continue
        # Ergebnis brauchbar — markiere welches Modell gewonnen hat
        print(f"[orchestrator] decomposer-cascade: {provider}/{model_id} "
              f"gewonnen ({len(subs)} subtasks)", flush=True)
        # Cleanup-Schleife unten (gemeinsam fuer alle Pfade)
        break
    else:
        if last_error:
            print(f"[orchestrator] gesamte Cascade fehlgeschlagen "
                  f"(letzter Fehler: {last_error})", flush=True)
        return None
    cleaned = []
    for i, s in enumerate(subs[:6]):
        if not isinstance(s, dict):
            continue
        desc = (s.get("description") or "").strip()
        if not desc:
            continue
        cat = (s.get("category") or "other").strip().lower()
        if cat not in CATEGORY_TO_SKILL:
            cat = "other"
        cleaned.append({"step": i + 1, "description": desc, "category": cat})
    return cleaned or None


def _decompose_heuristic(msg):
    """Fallback: zerlegt in Bullet-Listen oder Saetze.

    1. Bullet-Punkte (>= 2) -> jeder Bullet = Subtask
    2. Saetze (>= 2) mit unterschiedlichen Kategorien -> je Kategorie
    3. Sonst: ein einziger Subtask
    """
    if not isinstance(msg, str) or not msg.strip():
        return None

    # Bullet-Liste
    bullets = []
    last_end = 0
    for m in _BULLET_RE.finditer(msg):
        if last_end > 0:
            bullets.append(msg[last_end:m.start()].strip())
        last_end = m.end()
    if last_end > 0:
        bullets.append(msg[last_end:].strip())
    bullets = [b for b in bullets if b]
    if len(bullets) >= 2:
        return [
            {"step": i + 1,
             "description": b[:200],
             "category": (_ul.classify_task(b) if _ul else "other")}
            for i, b in enumerate(bullets[:6])
        ]

    # Saetze nach Kategorie clustern
    sentences = re.split(r"(?<=[.!?])\s+", msg.strip())
    sentences = [s for s in sentences if len(s.strip()) > 5]
    if _ul is not None and len(sentences) >= 2:
        seen_cats = []
        result = []
        for s in sentences:
            cat = _ul.classify_task(s)
            if cat in seen_cats:
                continue
            seen_cats.append(cat)
            result.append({
                "step": len(result) + 1,
                "description": s.strip()[:200],
                "category": cat,
            })
            if len(result) >= 6:
                break
        if len(result) >= 2:
            return result

    return None


def decompose(msg):
    """Hauptfunktion: zerlegt eine Anfrage in Subtasks.

    Versucht zuerst LLM (wenn invoker gesetzt), dann Heuristik. Liefert
    None wenn keine sinnvolle Zerlegung moeglich.
    """
    subs = _decompose_via_llm(msg)
    if subs:
        return {"method": "llm", "subtasks": subs}
    subs = _decompose_heuristic(msg)
    if subs:
        return {"method": "heuristic", "subtasks": subs}
    return None


# ── Model Selection ──────────────────────────────────────────────────────────

def _select_model_for(category):
    """Liefert das beste verfuegbare Modell fuer eine Kategorie."""
    skill = CATEGORY_TO_SKILL.get(category, "instruction_following")
    if _sd is None:
        return None
    try:
        best = _sd.get_best(skill, n=1)
    except Exception:
        return None
    if not best:
        return None
    top = best[0]
    return {
        "model_ref": top.get("model_ref"),
        "provider": top.get("provider"),
        "model_id": top.get("model_id"),
        "display_name": top.get("display_name"),
        "rating": top.get("rating"),
        "rationale": top.get("rationale"),
        "skill_used": skill,
    }


def select_models(subtasks):
    """Augmentiert jeden Subtask mit dem ausgewaehlten Modell."""
    out = []
    for st in subtasks:
        model = _select_model_for(st.get("category", "other"))
        out.append({**st, "model": model})
    return out


# ── Persistenz ───────────────────────────────────────────────────────────────

def _load_proposals():
    if not os.path.exists(PROPOSALS_PATH):
        return {"proposals": {}}
    try:
        with open(PROPOSALS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("proposals", {})
        return data
    except Exception:
        return {"proposals": {}}


def _save_proposals(data):
    os.makedirs(os.path.dirname(PROPOSALS_PATH), exist_ok=True)
    tmp = PROPOSALS_PATH + ".tmp"
    with _lock:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, PROPOSALS_PATH)


# ── Proposal-Lifecycle ───────────────────────────────────────────────────────

def propose(msg, session_id=None, force=False):
    """Komplett-Pipeline: Pruefung -> Decomposition -> Model-Selection -> Push."""
    decision = should_orchestrate(msg, force=force)
    out = {
        "ok": True,
        "orchestrate": decision["orchestrate"],
        "reason": decision["reason"],
        "msg_excerpt": decision["msg_excerpt"],
        "words": decision["words"],
        "categories": decision["categories"],
    }
    if not decision["orchestrate"]:
        out["proposal_id"] = None
        out["plan"] = None
        return out

    decomp = decompose(msg)
    if not decomp:
        out["orchestrate"] = False
        out["reason"] = "Decomposition lieferte keine Subtasks"
        out["proposal_id"] = None
        out["plan"] = None
        return out

    subs_with_models = select_models(decomp["subtasks"])
    proposal_id = f"orch_{uuid.uuid4().hex[:10]}"
    proposal = {
        "id": proposal_id,
        "created_at": _now_iso(),
        "session_id": session_id,
        "original_message": msg,
        "decomposition_method": decomp["method"],
        "categories": decision["categories"],
        "subtasks": subs_with_models,
        "user_response": None,  # null | yes | no | edit
        "status": "proposed",   # proposed | accepted | declined | edited | running | completed | error
        "step_results": [],     # list of {step, description, model, output, duration_seconds, error?}
    }

    with _lock:
        data = _load_proposals()
        data["proposals"][proposal_id] = proposal
        _save_proposals(data)

    # Heartbeat-Push fuer Browser-Confirmation
    if _hb is not None:
        try:
            _hb.enqueue_notification({
                "type": "orchestration_proposal",
                "proposal_id": proposal_id,
                "title": "Aufgabe in Teilaufgaben zerlegen?",
                "message": (
                    f"{len(subs_with_models)} Teilaufgaben erkannt — "
                    "soll ich sie sequentiell mit jeweils dem besten "
                    "Modell ausfuehren?"),
                "actions": [
                    {"id": "yes", "label": "Ja, ausfuehren"},
                    {"id": "no", "label": "Nein, klassisch"},
                    {"id": "edit", "label": "Plan bearbeiten"},
                ],
                "proposal": proposal,
            })
        except Exception as e:
            print(f"[orchestrator] push failed: {e}", flush=True)

    out["proposal_id"] = proposal_id
    out["plan"] = proposal
    return out


def list_proposals():
    return list(_load_proposals().get("proposals", {}).values())


def get_proposal(proposal_id):
    return _load_proposals().get("proposals", {}).get(proposal_id)


def respond(proposal_id, response, edited_plan=None):
    """User-Response auf einen Proposal: 'yes', 'no', 'edit'.

    Bei 'edit' kann edited_plan eine Liste {step, description, category}
    sein — die Modell-Selektion wird neu durchgefuehrt.
    """
    if response not in ("yes", "no", "edit"):
        return {"ok": False, "error": "response muss yes|no|edit sein"}
    with _lock:
        data = _load_proposals()
        p = data.get("proposals", {}).get(proposal_id)
        if not p:
            return {"ok": False, "error": "proposal_id unbekannt"}
        p["user_response"] = response
        if response == "yes":
            p["status"] = "accepted"
        elif response == "no":
            p["status"] = "declined"
        elif response == "edit":
            if isinstance(edited_plan, list) and edited_plan:
                cleaned = []
                for i, s in enumerate(edited_plan[:6]):
                    if not isinstance(s, dict):
                        continue
                    desc = (s.get("description") or "").strip()
                    if not desc:
                        continue
                    cat = (s.get("category") or "other").lower()
                    if cat not in CATEGORY_TO_SKILL:
                        cat = "other"
                    cleaned.append({"step": i + 1,
                                   "description": desc,
                                   "category": cat})
                if cleaned:
                    p["subtasks"] = select_models(cleaned)
            p["status"] = "edited"
        p["responded_at"] = _now_iso()
        _save_proposals(data)
        return {"ok": True, "proposal": p}


# ── Sequential Execution ────────────────────────────────────────────────────

def execute_step(proposal_id, step_index, prior_output=None):
    """Fuehrt einen einzelnen Schritt aus.

    step_index ist 0-basiert.
    prior_output (optional) wird als Vorgaenger-Kontext im Prompt eingebaut.
    Liefert {ok, step, output, duration_seconds, model, error?}.
    """
    with _lock:
        data = _load_proposals()
        p = data.get("proposals", {}).get(proposal_id)
        if not p:
            return {"ok": False, "error": "proposal_id unbekannt"}
        subs = p.get("subtasks") or []
        if step_index < 0 or step_index >= len(subs):
            return {"ok": False, "error": "step_index ausserhalb"}
        st = subs[step_index]

    started = _now()
    if _llm_invoker is None:
        # Kein LLM-Invoker -> wir koennen nur den Plan zeigen, nicht ausfuehren.
        return {"ok": False, "error": "kein LLM-Invoker registriert",
                "step": st}

    model = st.get("model") or {}
    provider = model.get("provider")
    model_id = model.get("model_id")
    if not provider or not model_id:
        return {"ok": False, "error": "Schritt hat kein Modell zugewiesen",
                "step": st}

    user_message = st.get("description", "")
    if prior_output:
        user_message = (
            "Kontext aus dem vorigen Schritt:\n"
            f"{prior_output}\n\n"
            "Aktueller Schritt:\n"
            f"{user_message}"
        )

    system_prompt = (
        "Du bist ein Spezialist fuer eine Teilaufgabe in einem orchestrierten "
        "Workflow. Beantworte die aktuelle Teilaufgabe direkt und praezise. "
        "Wenn ein Vorgaengerschritt-Output gegeben ist, baue darauf auf, "
        "ohne ihn zu wiederholen."
    )

    output = ""
    error = None
    try:
        output = _llm_invoker(provider, model_id, system_prompt,
                              [{"role": "user", "content": user_message}])
        if not isinstance(output, str):
            output = str(output)
    except Exception as e:
        error = str(e)

    duration = (_now() - started).total_seconds()

    result = {
        "ok": error is None,
        "step": st,
        "step_index": step_index,
        "output": output if error is None else "",
        "error": error,
        "duration_seconds": round(duration, 3),
        "model": model,
        "started_at": started.isoformat(timespec="seconds"),
        "finished_at": _now_iso(),
    }

    # Logging als category="orchestrated" (Pattern Analyzer kann lernen)
    if _ul is not None and error is None:
        try:
            _ul.log_turn(
                agent="orchestrator",
                provider=provider,
                model=model.get("display_name") or model_id,
                user_message=user_message,
                assistant_response=output,
                duration_seconds=duration,
                sub_agent=None,
                session_id=p.get("session_id"),
                extra={"orchestration_proposal_id": proposal_id,
                       "step_index": step_index,
                       "category": "orchestrated"},
            )
        except Exception:
            pass

    with _lock:
        data = _load_proposals()
        p = data.get("proposals", {}).get(proposal_id)
        if p is not None:
            results = p.setdefault("step_results", [])
            results.append({k: v for k, v in result.items() if k != "step"})
            p["status"] = "running"
            if step_index + 1 >= len(p.get("subtasks") or []):
                p["status"] = "completed" if error is None else "error"
                p["finished_at"] = _now_iso()
            _save_proposals(data)

    return result
