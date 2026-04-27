"""
skill_database.py — Zentrale Faehigkeits-Datenbank fuer alle aktiven LLM-Modelle.

Rating 1-5 pro (Modell, Skill). 0 = nicht unterstuetzt.

Storage: <datalake>/config/skill_database.json
Initial-Befuellung aus models.json via bootstrap_from_models() — pro Modell
wird ein Tier (flagship_reasoning, flagship, mid, small_fast,
research_specialist, code_specialist, local, image_gen, video_gen)
abgeleitet, der ein Default-Skill-Profil liefert. Spaetere Updates kommen
vom benchmark_fetcher.

Public API:
    bootstrap_from_models()     -> dict   Initial-Build aus models.json
    load()                       -> dict   Aktuelle DB lesen
    save(db)                     -> None
    get_best(task, n=3)          -> list   Top-N Modelle fuer Skill
    get_model(model_ref)         -> dict
    apply_updates(updates, src)  -> dict   diff + write + change log
    classify_tier(model_id, name) -> str
"""
import os
import json
import datetime
import threading

_BASE = os.path.expanduser(
    "~/Library/Mobile Documents/com~apple~CloudDocs/"
    "Downloads shared/claude_datalake"
)
DB_PATH = os.path.join(_BASE, "config", "skill_database.json")
MODELS_PATH = os.path.join(_BASE, "config", "models.json")
CHANGELOG_PATH = os.path.join(_BASE, "config", "skill_database_changes.jsonl")

_lock = threading.Lock()

SKILLS = [
    "research_long", "writing", "coding", "reasoning",
    "instruction_following", "image_understanding",
    "image_generation", "video_generation",
    "translation", "document_analysis", "web_search",
    "speed", "cost_efficiency",
]

SKILL_DEFINITIONS = {
    "research_long": "Lange strukturierte Recherchen mit Quellenangaben",
    "writing": "Professionelle Texterstellung in DE/EN/PT",
    "coding": "Code schreiben, debuggen, architekturieren",
    "reasoning": "Mehrstufige logische Schluesse, Mathematik, Planung",
    "instruction_following": "Praezise Befolgen komplexer System-Prompts",
    "image_understanding": "Bilder als Input verstehen (Vision)",
    "image_generation": "Bilder generieren — 0 wenn nicht unterstuetzt",
    "video_generation": "Videos generieren — 0 wenn nicht unterstuetzt",
    "translation": "Uebersetzung zwischen Sprachen",
    "document_analysis": "PDFs, lange Dokumente analysieren und extrahieren",
    "web_search": "Live-Suche im Web mit Quellen — 0 wenn nicht integriert",
    "speed": "Antwort-Latenz (5 = sehr schnell, 1 = sehr langsam)",
    "cost_efficiency": "Preis/Leistung (5 = guenstig, 1 = teuer)",
}

# ── Tier → Default-Skill-Profil ──────────────────────────────────────────────
# Pro Tier ein vollstaendiges Profil. Werte sind Default-Schaetzungen, die der
# Benchmark-Fetcher spaeter anhand realer Daten ueberschreibt.
_TIER_PROFILES = {
    "flagship_reasoning": {
        "research_long": 5, "writing": 5, "coding": 5, "reasoning": 5,
        "instruction_following": 5, "image_understanding": 5,
        "image_generation": 0, "video_generation": 0,
        "translation": 5, "document_analysis": 5, "web_search": 0,
        "speed": 2, "cost_efficiency": 1,
    },
    "flagship": {
        "research_long": 5, "writing": 5, "coding": 5, "reasoning": 5,
        "instruction_following": 5, "image_understanding": 4,
        "image_generation": 0, "video_generation": 0,
        "translation": 5, "document_analysis": 5, "web_search": 0,
        "speed": 3, "cost_efficiency": 2,
    },
    "mid": {
        "research_long": 4, "writing": 4, "coding": 4, "reasoning": 4,
        "instruction_following": 4, "image_understanding": 3,
        "image_generation": 0, "video_generation": 0,
        "translation": 4, "document_analysis": 4, "web_search": 0,
        "speed": 4, "cost_efficiency": 3,
    },
    "small_fast": {
        "research_long": 3, "writing": 3, "coding": 3, "reasoning": 3,
        "instruction_following": 4, "image_understanding": 3,
        "image_generation": 0, "video_generation": 0,
        "translation": 4, "document_analysis": 3, "web_search": 0,
        "speed": 5, "cost_efficiency": 5,
    },
    "research_specialist": {
        # Perplexity Sonar Deep Research, Sonar Reasoning Pro
        "research_long": 5, "writing": 4, "coding": 2, "reasoning": 4,
        "instruction_following": 4, "image_understanding": 0,
        "image_generation": 0, "video_generation": 0,
        "translation": 4, "document_analysis": 4, "web_search": 5,
        "speed": 2, "cost_efficiency": 3,
    },
    "code_specialist": {
        # Codestral, GPT-5.3 Codex
        "research_long": 2, "writing": 3, "coding": 5, "reasoning": 4,
        "instruction_following": 4, "image_understanding": 0,
        "image_generation": 0, "video_generation": 0,
        "translation": 3, "document_analysis": 3, "web_search": 0,
        "speed": 4, "cost_efficiency": 4,
    },
    "local": {
        # Lokal via Ollama — kein API-Cost, aber schwaechere Qualitaet.
        "research_long": 2, "writing": 3, "coding": 3, "reasoning": 3,
        "instruction_following": 3, "image_understanding": 0,
        "image_generation": 0, "video_generation": 0,
        "translation": 3, "document_analysis": 3, "web_search": 0,
        "speed": 4, "cost_efficiency": 5,
    },
    "image_gen": {
        # Imagen 4, gpt-image-1 — reine Bild-Modelle
        "research_long": 0, "writing": 0, "coding": 0, "reasoning": 0,
        "instruction_following": 4, "image_understanding": 0,
        "image_generation": 5, "video_generation": 0,
        "translation": 0, "document_analysis": 0, "web_search": 0,
        "speed": 3, "cost_efficiency": 3,
    },
    "video_gen": {
        # Veo 3.1
        "research_long": 0, "writing": 0, "coding": 0, "reasoning": 0,
        "instruction_following": 4, "image_understanding": 0,
        "image_generation": 0, "video_generation": 5,
        "translation": 0, "document_analysis": 0, "web_search": 0,
        "speed": 1, "cost_efficiency": 1,
    },
}


def classify_tier(provider, model_id, model_name=""):
    """Heuristische Tier-Klassifikation anhand Provider/ID/Name."""
    mid = (model_id or "").lower()
    name = (model_name or "").lower()
    p = (provider or "").lower()

    # Lokale Modelle
    if p == "ollama" or ":" in mid:
        return "local"

    # Perplexity Sonar — Research-Spezialisten
    if p == "perplexity" or "sonar" in mid:
        if "deep-research" in mid or "reasoning" in mid:
            return "research_specialist"
        # Normales Sonar kann immer noch suchen, aber weniger Tiefe
        return "research_specialist"

    # Code-Spezialisten
    if "codex" in mid or "codestral" in mid:
        return "code_specialist"

    # Anthropic
    if p == "anthropic":
        if "opus-4-7" in mid:
            return "flagship_reasoning"
        if "opus" in mid:
            return "flagship"
        if "sonnet" in mid:
            return "flagship"
        if "haiku" in mid:
            return "small_fast"

    # OpenAI
    if p == "openai":
        if mid in ("o3-pro", "gpt-5.5-pro"):
            return "flagship_reasoning"
        if mid in ("o3", "gpt-5.5", "gpt-5.4-pro"):
            return "flagship"
        if mid in ("gpt-5.4", "gpt-5"):
            return "mid"
        if "mini" in mid or "nano" in mid:
            return "small_fast"
        if mid.startswith("gpt-4o"):
            return "mid"

    # Gemini
    if p == "gemini":
        if "3.1-pro" in mid:
            return "flagship_reasoning"
        if "3-pro" in mid or "2.5-pro" in mid:
            return "flagship"
        if "flash-lite" in mid:
            return "small_fast"
        if "flash" in mid:
            return "small_fast"

    # Mistral
    if p == "mistral":
        if "magistral-medium" in mid:
            return "flagship_reasoning"
        if "magistral-small" in mid:
            return "mid"
        if "large" in mid:
            return "flagship"
        if "medium" in mid:
            return "mid"
        if "small" in mid or "nemo" in mid:
            return "small_fast"

    # DeepSeek
    if p == "deepseek":
        if "pro" in mid:
            return "flagship"
        if "flash" in mid:
            return "small_fast"

    # Default-Bucket
    return "mid"


def _profile_for(provider, model_id, model_name=""):
    tier = classify_tier(provider, model_id, model_name)
    return tier, dict(_TIER_PROFILES[tier])


def _now_iso():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


# ── Persistenz ───────────────────────────────────────────────────────────────

def load():
    """Liefert aktuelle DB als dict. Wenn nicht vorhanden -> leere Skelett."""
    if not os.path.exists(DB_PATH):
        return {
            "last_updated": None,
            "update_source": None,
            "skill_definitions": dict(SKILL_DEFINITIONS),
            "models": {},
        }
    try:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            db = json.load(f)
        # Schema-Selbstheilung: Definitions immer aktuell halten
        db.setdefault("skill_definitions", dict(SKILL_DEFINITIONS))
        db.setdefault("models", {})
        return db
    except Exception as e:
        print(f"[skill_database] load failed: {e}", flush=True)
        return {"models": {}, "skill_definitions": dict(SKILL_DEFINITIONS)}


def save(db):
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    tmp = DB_PATH + ".tmp"
    with _lock:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2, sort_keys=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, DB_PATH)


def _model_ref(provider, model_id):
    return f"{provider}/{model_id}"


# ── Bootstrap ────────────────────────────────────────────────────────────────

def bootstrap_from_models(force=False):
    """Initial-Build der DB aus models.json.

    Erhaelt vorhandene Ratings und Notes, ergaenzt nur fehlende Modelle und
    fuegt fehlende Skill-Felder mit dem Tier-Default hinzu. Bei force=True
    werden alle Tier-Defaults neu gezogen (Notes/explizit gesetzte Ratings
    bleiben aber erhalten — ueberschrieben werden nur Skills die noch auf
    dem alten Tier-Default standen).
    """
    if not os.path.exists(MODELS_PATH):
        return load()

    with open(MODELS_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    db = load()
    db.setdefault("models", {})
    db["skill_definitions"] = dict(SKILL_DEFINITIONS)
    added = 0

    for provider, pcfg in (cfg.get("providers") or {}).items():
        if not isinstance(pcfg, dict):
            continue
        # Chat-Modelle
        for m in pcfg.get("models", []) or []:
            mid = m.get("id")
            if not mid:
                continue
            ref = _model_ref(provider, mid)
            tier, profile = _profile_for(provider, mid, m.get("name", ""))
            existing = db["models"].get(ref)
            if existing is None:
                db["models"][ref] = {
                    "display_name": m.get("name", mid),
                    "provider": provider,
                    "model_id": mid,
                    "available": True,
                    "tier": tier,
                    "skills": profile,
                    "notes": "",
                    "last_skill_update": _now_iso(),
                    "skill_sources": {},
                }
                added += 1
            else:
                existing.setdefault("display_name", m.get("name", mid))
                existing.setdefault("provider", provider)
                existing.setdefault("model_id", mid)
                existing.setdefault("available", True)
                existing.setdefault("tier", tier)
                existing.setdefault("notes", "")
                existing.setdefault("skill_sources", {})
                skills = existing.setdefault("skills", {})
                for sk, val in profile.items():
                    if sk not in skills:
                        skills[sk] = val
                if force:
                    # Skills die noch auf altem Tier-Default standen -> neu
                    pass  # keine Auto-Override-Heuristik im Bootstrap

        # Image / Video Sub-Modelle
        for kind, key in (("image_gen", "image_model"), ("video_gen", "video_model")):
            sub_id = pcfg.get(key)
            if not sub_id:
                continue
            ref = _model_ref(provider, sub_id)
            if ref in db["models"]:
                continue
            profile = dict(_TIER_PROFILES[kind])
            db["models"][ref] = {
                "display_name": sub_id,
                "provider": provider,
                "model_id": sub_id,
                "available": True,
                "tier": kind,
                "skills": profile,
                "notes": ("Reines Bild-Modell" if kind == "image_gen"
                         else "Reines Video-Modell"),
                "last_skill_update": _now_iso(),
                "skill_sources": {},
            }
            added += 1

    db["last_updated"] = _now_iso()
    if added > 0:
        db["update_source"] = (db.get("update_source") or "")
        if "bootstrap" not in (db.get("update_source") or ""):
            db["update_source"] = "bootstrap_from_models"
    save(db)
    return db


# ── Queries ──────────────────────────────────────────────────────────────────

def get_model(model_ref):
    """Liefert Eintrag fuer 'provider/model_id' oder None."""
    db = load()
    return db.get("models", {}).get(model_ref)


def get_best(task, n=3, only_available=True):
    """Top-N Modelle fuer einen Skill (Task), sortiert nach Rating dann tier-Speed.

    task = einer der Skills aus SKILLS. Wenn unbekannt -> []."""
    if task not in SKILLS:
        return []
    db = load()
    candidates = []
    for ref, m in (db.get("models") or {}).items():
        if only_available and not m.get("available", True):
            continue
        rating = (m.get("skills") or {}).get(task, 0)
        if rating <= 0:
            continue
        # Tie-Breaker: speed dann cost_efficiency
        skills = m.get("skills") or {}
        candidates.append((
            rating,
            skills.get("speed", 0),
            skills.get("cost_efficiency", 0),
            ref, m,
        ))
    candidates.sort(key=lambda t: (-t[0], -t[1], -t[2], t[3]))
    out = []
    for rating, speed, cost, ref, m in candidates[:n]:
        out.append({
            "model_ref": ref,
            "display_name": m.get("display_name", ref),
            "provider": m.get("provider"),
            "model_id": m.get("model_id"),
            "rating": rating,
            "tier": m.get("tier"),
            "rationale": _rationale(task, rating, m),
            "skills": m.get("skills", {}),
        })
    return out


def _rationale(task, rating, m):
    tier = m.get("tier") or "?"
    speed = (m.get("skills") or {}).get("speed", 0)
    cost = (m.get("skills") or {}).get("cost_efficiency", 0)
    parts = [f"Rating {rating}/5 fuer {task}", f"Tier {tier}"]
    if speed >= 4:
        parts.append("schnell")
    elif speed <= 2:
        parts.append("langsam")
    if cost >= 4:
        parts.append("kostenguenstig")
    elif cost <= 2:
        parts.append("teuer")
    return ", ".join(parts)


# ── Updates (vom Benchmark-Fetcher) ───────────────────────────────────────────

def apply_updates(updates, source="manual"):
    """Wendet Skill-Updates an, schreibt Diffs in JSONL-Changelog.

    updates = list of {model_ref, skill, rating, source?}.
    Liefert Liste der tatsaechlich geaenderten Eintraege (rating != alt).
    """
    if not updates:
        return []

    db = load()
    now = _now_iso()
    changes = []

    for u in updates:
        ref = u.get("model_ref")
        skill = u.get("skill")
        new_rating = u.get("rating")
        u_source = u.get("source") or source
        if ref is None or skill is None or new_rating is None:
            continue
        if skill not in SKILLS:
            continue
        m = db.get("models", {}).get(ref)
        if not m:
            continue
        old = (m.get("skills") or {}).get(skill, 0)
        try:
            new_int = int(new_rating)
        except Exception:
            continue
        if new_int < 0 or new_int > 5:
            continue
        if new_int == old:
            continue
        m.setdefault("skills", {})[skill] = new_int
        m.setdefault("skill_sources", {})[skill] = {
            "source": u_source,
            "updated_at": now,
            "previous": old,
        }
        m["last_skill_update"] = now
        changes.append({
            "timestamp": now,
            "model_ref": ref,
            "skill": skill,
            "old": old,
            "new": new_int,
            "source": u_source,
        })

    if changes:
        db["last_updated"] = now
        db["update_source"] = source
        save(db)
        os.makedirs(os.path.dirname(CHANGELOG_PATH), exist_ok=True)
        with open(CHANGELOG_PATH, "a", encoding="utf-8") as f:
            for c in changes:
                f.write(json.dumps(c, ensure_ascii=False) + "\n")

    return changes


def set_available(model_ref, available, source="manual"):
    """Markiert ein Modell als verfuegbar/nicht verfuegbar."""
    db = load()
    m = db.get("models", {}).get(model_ref)
    if not m:
        return False
    if bool(m.get("available", True)) == bool(available):
        return False
    m["available"] = bool(available)
    m["last_skill_update"] = _now_iso()
    db["last_updated"] = m["last_skill_update"]
    db["update_source"] = source
    save(db)
    return True
