"""
lifecycle.py — Context Lifecycle Engine (Roadmap-Feature 1, April 2026).

Schlanker In-Process-Event-Bus mit benannten Lifecycle-Punkten. Andere
Subsysteme (usage_logger, pattern_analyzer, orchestrator, ...) registrieren
sich als Subscriber und werden bei `emit()` synchron, aber isoliert
aufgerufen — eine fehlerhafte Subscriber-Funktion bringt weder andere
Subscriber noch den /chat-Request zum Stuerzen.

Bewusst nicht-async: jeder Handler MUSS schnell sein oder selbst einen
Hintergrund-Thread aufmachen (so wie usage_logger.log_turn). Das haelt das
Modul testbar (kein Event-Loop, keine asyncio-Annahmen) und passt zu Flask's
Thread-pro-Request-Modell.

Public API:
    on(event, handler)              -> id    Subscriber registrieren
    off(event, sub_id)              -> bool  abbestellen
    emit(event, ctx_dict)           -> dict  alle Handler ausfuehren, Stats
    list_subscribers(event=None)    -> dict  Diagnose
    EVENTS                          -> tuple aller bekannter Lifecycle-Punkte
"""
import threading
import traceback


# Bekannte Lifecycle-Punkte. Neue duerfen frei hinzukommen — die Engine
# selbst kennt keine Whitelist (Subscriber registrieren auf String-Names).
# Diese Konstanten sind die "offiziellen" Punkte fuer Code-Konsistenz.
EVENT_BEFORE_TURN = "BEFORE_TURN"
EVENT_AFTER_TURN = "AFTER_TURN"
EVENT_ON_AGENT_SWITCH = "ON_AGENT_SWITCH"
EVENT_ON_SESSION_START = "ON_SESSION_START"
EVENT_ON_SESSION_END = "ON_SESSION_END"
EVENT_ON_SUBAGENT_DELEGATION = "ON_SUBAGENT_DELEGATION"
EVENT_ON_TURN_ERROR = "ON_TURN_ERROR"

EVENTS = (
    EVENT_BEFORE_TURN,
    EVENT_AFTER_TURN,
    EVENT_ON_AGENT_SWITCH,
    EVENT_ON_SESSION_START,
    EVENT_ON_SESSION_END,
    EVENT_ON_SUBAGENT_DELEGATION,
    EVENT_ON_TURN_ERROR,
)


# event-name -> list of (sub_id, handler, label)
_subscribers = {}
_lock = threading.RLock()
_next_id = 1


def on(event, handler, label=None):
    """Registriert einen Handler fuer ein Event. Liefert Subscriber-ID."""
    global _next_id
    if not callable(handler):
        raise TypeError("handler muss callable sein")
    with _lock:
        sub_id = _next_id
        _next_id += 1
        _subscribers.setdefault(event, []).append((sub_id, handler, label or handler.__name__))
        return sub_id


def off(event, sub_id):
    """Entfernt einen Subscriber. True wenn gefunden + entfernt."""
    with _lock:
        subs = _subscribers.get(event)
        if not subs:
            return False
        for i, (sid, _, _) in enumerate(subs):
            if sid == sub_id:
                subs.pop(i)
                return True
        return False


def emit(event, ctx=None):
    """Ruft alle Handler fuer das Event auf, jeder isoliert in try/except.

    Liefert Dict mit Stats:
        {event, handlers_total, handlers_ok, handlers_errored, errors[]}
    Niemals exception-propagating.
    """
    if ctx is None:
        ctx = {}
    elif not isinstance(ctx, dict):
        ctx = {"value": ctx}

    with _lock:
        # Snapshot kopieren, damit on/off waehrend emit nicht stoeren
        snapshot = list(_subscribers.get(event, []))

    ok = 0
    errored = 0
    errors = []
    for sub_id, handler, label in snapshot:
        try:
            handler(ctx)
            ok += 1
        except Exception as e:
            errored += 1
            errors.append({
                "subscriber_id": sub_id,
                "label": label,
                "error": str(e),
                "traceback": traceback.format_exc(limit=3),
            })
            try:
                print(f"[lifecycle] handler '{label}' for event '{event}' "
                      f"failed: {e}", flush=True)
            except Exception:
                pass

    return {
        "event": event,
        "handlers_total": len(snapshot),
        "handlers_ok": ok,
        "handlers_errored": errored,
        "errors": errors,
    }


def list_subscribers(event=None):
    """Diagnose: Liste aller Subscriber, optional nach Event gefiltert."""
    with _lock:
        if event is not None:
            subs = _subscribers.get(event, [])
            return {event: [{"id": sid, "label": label}
                            for sid, _, label in subs]}
        return {
            ev: [{"id": sid, "label": label} for sid, _, label in subs]
            for ev, subs in _subscribers.items()
        }


def reset():
    """Komplett-Reset (Tests). Loescht alle Subscriber."""
    with _lock:
        _subscribers.clear()
