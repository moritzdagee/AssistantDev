"""Zentrales Zeitzonen-Management fuer AssistantDev.

Regel: Alle Timestamps innerhalb der App sind in der **lokalen Zeitzone des
Systems** (typischerweise die Zeitzone des Nutzer-Macs, bei Moritz Brasilien
BRT = UTC-3).

Rationale: Apps wie Apple Mail, WhatsApp, iMessage, Kalender zeigen dem
Nutzer die lokale Zeit. Wenn unser Dashboard UTC anzeigt oder mischt,
entstehen Verwirrungen — siehe den Naiara-Fall: Message "00:07 Bom dia"
wurde wegen `utcfromtimestamp()` als "03:07" gespeichert.

Oeffentliche Helpers:

  now()           — aware datetime in lokaler TZ
  now_iso()       — ISO-String mit lokalem TZ-Offset ("...+01:00" / "...-03:00")
  now_iso_naive() — ISO-String OHNE TZ-Suffix (fuer Legacy-Konsumenten)
  from_unix(ts)   — aware datetime in lokaler TZ aus Unix-Timestamp
  from_apple(ts)  — aware datetime aus Apple Core Data Timestamp
                    (Sekunden seit 2001-01-01 UTC)
  to_local(dt)    — (aware oder naive) datetime -> aware in lokaler TZ
  to_local_naive(dt) — datetime -> naive in lokaler TZ (fuer Vergleiche)

Verboten in der Codebase:
  datetime.utcfromtimestamp()  — liefert naive-UTC, leakt als "lokal"
  datetime.utcnow()            — gleiches Problem
  Der Regression-Test in tests/run_tests.py grept dagegen.
"""
from __future__ import annotations

import datetime as _dt
import time as _time


APPLE_CORE_DATA_EPOCH = 978307200  # 2001-01-01 00:00:00 UTC


def _local_tz() -> _dt.tzinfo:
    """Liefert die aktuelle lokale Zeitzone als tzinfo."""
    # astimezone() auf naive-local-datetime liefert die System-TZ.
    return _dt.datetime.now().astimezone().tzinfo


def now() -> _dt.datetime:
    """Aware datetime in der lokalen Zeitzone."""
    return _dt.datetime.now().astimezone()


def now_iso() -> str:
    """ISO-String mit lokalem TZ-Offset, z.B. '2026-04-20T00:07:00-03:00'."""
    return now().isoformat(timespec="seconds")


def now_iso_naive() -> str:
    """ISO-String ohne TZ-Suffix (naive, lokale Zeit). Fuer Legacy-
    Konsumenten, die keine TZ-Info erwarten."""
    return _dt.datetime.now().isoformat(timespec="seconds")


def from_unix(ts: float) -> _dt.datetime:
    """Aware datetime in lokaler TZ aus Unix-Timestamp (Sekunden)."""
    return _dt.datetime.fromtimestamp(ts).astimezone()


def from_apple(ts: float) -> _dt.datetime:
    """Aware datetime aus Apple Core Data Timestamp (Sekunden seit
    2001-01-01 UTC — Format der iMessage- und WhatsApp-SQLite-Stores)."""
    return from_unix(ts + APPLE_CORE_DATA_EPOCH)


def to_local(dt: _dt.datetime) -> _dt.datetime:
    """Konvertiert aware oder naive datetime in aware-lokal.
    Naive datetimes werden als lokale Zeit interpretiert (nicht UTC)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=_local_tz())
    return dt.astimezone()


def to_local_naive(dt: _dt.datetime) -> _dt.datetime:
    """Liefert naive datetime in lokaler Zeit — fuer Vergleiche mit
    anderen naive datetimes (z.B. aus `strptime`)."""
    if dt.tzinfo is None:
        return dt
    return dt.astimezone().replace(tzinfo=None)


def parse_rfc822(s: str) -> _dt.datetime | None:
    """Parst RFC822 Date-Header (E-Mail `Date:`) zu aware-lokal datetime."""
    if not s:
        return None
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(s)
        if dt is None:
            return None
        if dt.tzinfo is None:
            # Sicherstellen dass naive als lokal interpretiert wird
            dt = dt.replace(tzinfo=_local_tz())
        return dt.astimezone()
    except Exception:
        return None


__all__ = [
    "APPLE_CORE_DATA_EPOCH",
    "now", "now_iso", "now_iso_naive",
    "from_unix", "from_apple",
    "to_local", "to_local_naive",
    "parse_rfc822",
]
