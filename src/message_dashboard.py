#!/usr/bin/env python3
"""
Message Dashboard - Native macOS App (PyQt6)

Globaler Posteingang fuer alle Nachrichten aus dem AssistantDev Datalake.
Aggregiert E-Mails, kChat- und WhatsApp-Nachrichten aus allen Agent-Memorys,
priorisiert sie nach Alter, Quelle, Schluesselwoertern und Gelesen-Status.

Start:  python3 ~/AssistantDev/src/message_dashboard.py
        oder: bash ~/AssistantDev/scripts/start_dashboard.sh

Liest ausschliesslich aus dem Datalake — keine eigenen Backend-Calls.
Status (gelesen/ungelesen) wird in ~/.message_dashboard_state.json persistiert.
"""

import sys
import os
import re
import json
import hashlib
import datetime
import subprocess
import traceback
from pathlib import Path

# ── Dependencies ─────────────────────────────────────────────────────────────

try:
    from PyQt6.QtCore import (
        Qt, QTimer, QSize, QPoint, pyqtSignal, QThread, QObject,
    )
    from PyQt6.QtGui import (
        QFont, QColor, QPalette, QAction, QIcon, QKeySequence, QShortcut,
    )
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QLabel, QPushButton, QVBoxLayout,
        QHBoxLayout, QListWidget, QListWidgetItem, QTextEdit, QFrame,
        QScrollArea, QSplitter, QMenu, QMessageBox, QSizePolicy, QStyle,
    )
except ImportError as e:
    sys.stderr.write(
        f"FEHLER: PyQt6 fehlt ({e}). Installation:\n"
        f"  pip3 install PyQt6\n"
    )
    sys.exit(1)


# ── Konfiguration ────────────────────────────────────────────────────────────

DATALAKE = os.path.expanduser(
    "~/Library/Mobile Documents/com~apple~CloudDocs/Downloads shared/claude_datalake"
)

# Welche Top-Level-Ordner als Agenten gescannt werden
AGENT_DIRS = [
    "signicat", "trustedcarrier", "privat", "standard", "system ward",
]

# Eigene E-Mail-Adressen (zum Filtern eigener Outbound-Nachrichten)
OWN_EMAILS = {
    "londoncityfox@gmail.com",
    "moritz.cremer@me.com",
    "moritz.cremer@icloud.com",
    "moritz@demoscapital.co",
    "moritz@vegatechnology.com.br",
    "moritz.cremer@signicat.com",
    "moritz.cremer@trustedcarrier.net",
    "moritz@casiopayaconsulting.io",
    "moritz@tangerina.com",
}

STATE_FILE = os.path.expanduser("~/.message_dashboard_state.json")
ASSISTANT_URL = "http://localhost:8080"
REFRESH_INTERVAL_MS = 5 * 60 * 1000  # 5 Minuten
PREVIEW_LEN = 150
SUBJECT_PREVIEW_LEN = 60
# Performance: nur die N neuesten Dateien pro Agent scannen (mtime descending).
# Bei 25K+ Dateien im Datalake auf iCloud waeren Volltext-Scans zu langsam
# (>10s). Aktuelle Nachrichten sind die wichtigsten — Cap haelt Startup unter 3s.
MAX_FILES_PER_AGENT = 800
LIST_VISIBLE_CAP = 500  # max sichtbare Items in der Liste

# Performance: nur Nachrichten der letzten N Tage anzeigen (Inbox-Dashboard
# soll keine 25k historischen Mails laden). Aelteres bleibt im Datalake fuer
# Suche/Memory verfuegbar, ist aber nicht relevant fuer den Inbox-Workflow.
INBOX_WINDOW_DAYS = 90
# Nur die ersten N Bytes pro Datei lesen — Header + Preview reichen
PARSE_READ_BYTES = 8192

# Priority-Scoring Keywords
URGENT_KEYWORDS = [
    "urgent", "dringend", "asap", "sofort", "kritisch", "critical",
]
INVOICE_KEYWORDS = [
    "invoice", "rechnung", "zahlung", "payment", "fällig", "faellig", "due",
    "boleto", "fatura",
]
CONTRACT_KEYWORDS = [
    "contract", "vertrag", "unterzeichnen", "sign",
]
MEETING_KEYWORDS = [
    "meeting", "call", "termin", "heute", "today", "morgen", "tomorrow",
]
OFFER_KEYWORDS = [
    "angebot", "offer", "proposal", "quote",
]
REMINDER_KEYWORDS = [
    "follow-up", "follow up", "reminder", "erinnerung",
]
COMPANY_KEYWORDS = [
    "signicat", "trustedcarrier", "trusted carrier", "elavon",
]


# ── Theme / Stylesheets ──────────────────────────────────────────────────────

DARK_STYLE = """
QMainWindow, QWidget { background-color: #1a1a1a; color: #e0e0e0; font-family: -apple-system, "Helvetica Neue", "SF Pro Text", sans-serif; }
QFrame#sidebar { background-color: #161616; border-right: 1px solid #2a2a2a; }
QFrame#stats-bar { background-color: #161616; border-bottom: 1px solid #2a2a2a; }
QFrame#detail-pane { background-color: #1a1a1a; border-left: 1px solid #2a2a2a; }
QListWidget { background-color: #1a1a1a; border: none; outline: none; }
QListWidget::item { padding: 0px; border-bottom: 1px solid #232323; }
QListWidget::item:selected { background-color: #2a2a2a; }
QListWidget::item:hover { background-color: #222222; }
QLabel#stats-label { color: #888; font-size: 12px; padding: 0 8px; }
QLabel#stats-label-strong { color: #f0c060; font-size: 12px; font-weight: 700; padding: 0 8px; }
QLabel#detail-subject { color: #ffffff; font-size: 18px; font-weight: 700; padding: 12px 14px 4px 14px; }
QLabel#detail-meta { color: #888; font-size: 11px; padding: 0 14px 8px 14px; }
QLabel#detail-meta a { color: #f0c060; }
QTextEdit#detail-body { background-color: #141414; color: #d0d0d0; border: 1px solid #2a2a2a; border-radius: 6px; padding: 12px; font-size: 12px; font-family: -apple-system, "Helvetica Neue", sans-serif; }
QPushButton { background-color: #2a2a2a; color: #e0e0e0; border: 1px solid #3a3a3a; border-radius: 6px; padding: 7px 14px; font-size: 12px; }
QPushButton:hover { background-color: #333333; border-color: #f0c060; }
QPushButton:pressed { background-color: #222222; }
QPushButton#primary-btn { background-color: #f0c060; color: #111; border: none; font-weight: 700; }
QPushButton#primary-btn:hover { background-color: #f5cc70; }
QPushButton#filter-btn { text-align: left; padding: 8px 12px; background-color: transparent; border: none; border-radius: 4px; color: #c0c0c0; }
QPushButton#filter-btn:hover { background-color: #222222; color: #ffffff; }
QPushButton#filter-btn:checked { background-color: #2a2a1a; color: #f0c060; font-weight: 700; }
QScrollBar:vertical { background: #1a1a1a; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: #333; border-radius: 5px; min-height: 20px; }
QScrollBar::handle:vertical:hover { background: #555; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { background: none; height: 0; }
"""


# ── Parser ───────────────────────────────────────────────────────────────────

EMAIL_FIELD_RE = re.compile(r'^(Von|An|From|To|Betreff|Subject|Datum|Date|Kontakt|Richtung|Agent|Importiert|Quelle|Kanal):\s*(.*)$', re.IGNORECASE)

EMAIL_RE = re.compile(r'[\w.+%-]+@[\w.-]+\.[a-zA-Z]{2,}')


def _file_hash(path):
    return hashlib.sha1(path.encode("utf-8")).hexdigest()[:16]


def _strip_separator(text):
    """Entfernt den Header/Body-Separator (─────) und alles davor."""
    sep = "\u2500" * 10  # 10 oder mehr U+2500 = Separator
    idx = text.find(sep)
    if idx != -1:
        # Finde das Ende der Separator-Zeile
        eol = text.find("\n", idx)
        if eol != -1:
            return text[eol+1:].lstrip()
    # Fallback: '---' Marker
    for marker in ["\n---\n", "\n----\n", "\n-----\n"]:
        idx = text.find(marker)
        if idx != -1:
            return text[idx+len(marker):].lstrip()
    return text


def _parse_email_date(date_str):
    """Versucht ein Datum aus diversen Formaten zu parsen.
    Faellt auf File-mtime zurueck wenn alles fehlschlaegt.
    Rueckgabe: datetime oder None.
    """
    if not date_str:
        return None
    s = date_str.strip()
    # Versuch 1: RFC 2822 (E-Mail-Standard)
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(s)
        if dt:
            # Auf naive datetime reduzieren (lokale Zeit)
            if dt.tzinfo:
                dt = dt.astimezone().replace(tzinfo=None)
            return dt
    except Exception:
        pass
    # Versuch 2: ISO-Format
    try:
        return datetime.datetime.fromisoformat(s.replace("Z", "+00:00").split("+")[0].split(".")[0])
    except Exception:
        pass
    # Versuch 3: 2026-04-10_09-30-00 (Importiert-Format)
    try:
        return datetime.datetime.strptime(s[:19], "%Y-%m-%d_%H-%M-%S")
    except Exception:
        pass
    return None


def parse_message_file(filepath):
    """Liest eine .txt Datei und gibt ein normalisiertes Message-Dict zurueck.
    Erkennt sowohl Email-Format (Von/An/Betreff/Datum) als auch kChat-Format
    (Quelle: kChat, Kanal, Von, Datum). Gibt None bei kaputten Dateien zurueck.
    """
    # Performance: nur die ersten 8 KB lesen — Header + Preview reichen.
    # Volltext wird on-demand beim Detail-Klick nachgeladen.
    try:
        with open(filepath, "rb") as f:
            raw_bytes = f.read(8192)
        if not raw_bytes.strip():
            return None
        raw = raw_bytes.decode("utf-8", errors="replace")
    except Exception:
        return None

    fname = os.path.basename(filepath)
    fields = {}
    lines = raw.splitlines()
    header_end_idx = 0
    for i, line in enumerate(lines):
        # Header-Ende: Separator-Zeile oder leere Zeile nach Headern
        if "\u2500\u2500\u2500" in line:
            header_end_idx = i + 1
            break
        if line.strip() == "" and fields:
            header_end_idx = i + 1
            break
        m = EMAIL_FIELD_RE.match(line)
        if m:
            key = m.group(1).lower()
            value = m.group(2).strip()
            # Ersten Wert pro Feld behalten (mehrzeilige Header ignorieren)
            if key not in fields:
                fields[key] = value
        elif i > 30 and not fields:
            # Keine Header gefunden, nach 30 Zeilen abbrechen
            break

    body = "\n".join(lines[header_end_idx:]).strip() if header_end_idx else _strip_separator(raw)

    # Source erkennen
    source = "email"
    if fields.get("quelle", "").lower() == "kchat":
        source = "kchat"
    elif fname.lower().startswith("kchat_"):
        source = "kchat"
    elif fname.lower().startswith("whatsapp_"):
        source = "whatsapp"

    # Channel = Agent-Ordner
    parent_dir = os.path.basename(os.path.dirname(os.path.dirname(filepath)))
    channel = parent_dir if parent_dir in AGENT_DIRS else "standard"

    # Absender / Empfaenger
    from_raw = fields.get("von", fields.get("from", ""))
    to_raw = fields.get("an", fields.get("to", fields.get("kanal", "")))
    subject = fields.get("betreff", fields.get("subject", "")).strip()
    if not subject:
        # Fallback aus Dateinamen extrahieren oder erste Body-Zeile
        first_body_line = next((l for l in body.splitlines() if l.strip()), "").strip()
        subject = first_body_line[:100] if first_body_line else fname

    # E-Mail-Adresse aus from extrahieren
    sender_email = ""
    m = EMAIL_RE.search(from_raw)
    if m:
        sender_email = m.group(0).lower()

    # Datum
    date_str = fields.get("datum", fields.get("date", ""))
    dt = _parse_email_date(date_str)
    if not dt:
        # Aus Dateinamen extrahieren (YYYY-MM-DD_HH-MM-SS_)
        m2 = re.match(r"(\d{4}-\d{2}-\d{2})_(\d{2})-(\d{2})-(\d{2})_", fname)
        if m2:
            try:
                dt = datetime.datetime.strptime(
                    f"{m2.group(1)}_{m2.group(2)}-{m2.group(3)}-{m2.group(4)}",
                    "%Y-%m-%d_%H-%M-%S",
                )
            except Exception:
                pass
    if not dt:
        # Letzter Fallback: File-mtime
        try:
            dt = datetime.datetime.fromtimestamp(os.path.getmtime(filepath))
        except Exception:
            dt = datetime.datetime.now()

    age_days = (datetime.datetime.now() - dt).total_seconds() / 86400.0

    # Eigene Outbound-Nachrichten ueberspringen
    direction = fields.get("richtung", "").upper()
    if direction == "OUT":
        return None
    if sender_email and sender_email in OWN_EMAILS:
        return None

    body_clean = body.strip()
    preview = (body_clean[:PREVIEW_LEN] + "...") if len(body_clean) > PREVIEW_LEN else body_clean
    preview = " ".join(preview.split())  # Whitespace normalisieren

    return {
        "id": _file_hash(filepath),
        "source": source,
        "channel": channel,
        "from": from_raw or sender_email or "(unbekannt)",
        "from_email": sender_email,
        "to": to_raw,
        "subject": subject[:200],
        "body": body_clean,
        "body_preview": preview,
        "date": dt,
        "filepath": filepath,
        "is_read": False,  # wird nach State-Load gesetzt
        "age_days": age_days,
        "priority_score": 0,  # wird gleich berechnet
    }


def calculate_priority(msg):
    """Berechnet einen Score 0-100 fuer eine Nachricht."""
    score = 0
    age = msg["age_days"]

    # Basis-Score nach Alter
    if age < 1:
        score += 20
    elif age < 2:
        score += 10
    elif age < 3:
        score += 5

    # Source-Score
    source_score = {"email": 15, "kchat": 10, "whatsapp": 12}
    score += source_score.get(msg["source"], 5)

    # Keyword-Scoring (Subject + Body-Preview)
    haystack = (msg["subject"] + " " + msg["body_preview"]).lower()

    if any(k in haystack for k in URGENT_KEYWORDS):
        score += 30
    if any(k in haystack for k in INVOICE_KEYWORDS):
        score += 25
    if any(k in haystack for k in CONTRACT_KEYWORDS):
        score += 20
    if any(k in haystack for k in MEETING_KEYWORDS):
        score += 15
    if any(k in haystack for k in OFFER_KEYWORDS):
        score += 10
    if any(k in haystack for k in REMINDER_KEYWORDS):
        score += 10

    # Firmennamen im Absender
    sender_low = (msg["from"] + " " + msg["from_email"]).lower()
    if any(c in sender_low for c in COMPANY_KEYWORDS):
        score += 10

    # Ungelesen-Boost
    if not msg["is_read"]:
        score += 15

    return min(100, max(0, score))


# ── Datalake-Scanner ─────────────────────────────────────────────────────────

# Pattern fuer Email-Watcher Dateien: YYYY-MM-DD_HH-MM-SS_DIR_...
EMAIL_FILE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}_(IN|OUT)_.*\.txt$")
KCHAT_FILE_RE = re.compile(r"^kchat_.*\.txt$", re.IGNORECASE)
WHATSAPP_FILE_RE = re.compile(r"^whatsapp_.*\.txt$", re.IGNORECASE)
LEGACY_EMAIL_RE = re.compile(r"^email_.*\.txt$", re.IGNORECASE)


def scan_datalake():
    """Scant alle Agent-Memorys nach Nachrichten-Dateien.
    Gibt Liste von Message-Dicts zurueck (gefiltert: keine eigenen Outbounds).
    """
    messages = []
    if not os.path.isdir(DATALAKE):
        return messages

    for agent in AGENT_DIRS:
        memdir = os.path.join(DATALAKE, agent, "memory")
        if not os.path.isdir(memdir):
            continue
        # Schritt 1: Nur passende Dateinamen sammeln (super schnell)
        candidates = []
        try:
            with os.scandir(memdir) as it:
                for entry in it:
                    if not entry.is_file(follow_symlinks=False):
                        continue
                    fname = entry.name
                    if not fname.endswith(".txt"):
                        continue
                    if fname.startswith("konversation_"):
                        continue
                    if not (
                        EMAIL_FILE_RE.match(fname)
                        or KCHAT_FILE_RE.match(fname)
                        or WHATSAPP_FILE_RE.match(fname)
                        or LEGACY_EMAIL_RE.match(fname)
                    ):
                        continue
                    # mtime fuer Sortierung — entry.stat() ist gecached
                    try:
                        mtime = entry.stat(follow_symlinks=False).st_mtime
                    except Exception:
                        mtime = 0
                    candidates.append((mtime, entry.path))
        except Exception:
            continue
        # Schritt 2: Top-N nach mtime descending → nur die neuesten parsen
        candidates.sort(key=lambda x: x[0], reverse=True)
        candidates = candidates[:MAX_FILES_PER_AGENT]
        # Schritt 3: Parsen
        for _, fpath in candidates:
            try:
                msg = parse_message_file(fpath)
            except Exception:
                continue
            if msg:
                messages.append(msg)
    return messages


# ── State Management ────────────────────────────────────────────────────────

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {"read_messages": [], "last_refresh": ""}


def save_state(state):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"State save error: {e}", file=sys.stderr)


# ── Helpers ──────────────────────────────────────────────────────────────────

def fmt_age(age_days):
    if age_days < 1/24:  # < 1 Stunde
        mins = max(1, int(age_days * 24 * 60))
        return f"{mins}min"
    if age_days < 1:
        hours = int(age_days * 24)
        return f"{hours}h"
    if age_days < 2:
        return "gestern"
    if age_days < 7:
        return f"{int(age_days)}d"
    if age_days < 30:
        return f"{int(age_days/7)}w"
    return f"{int(age_days/30)}mo"


def channel_icon(source):
    return {"email": "\U0001F4E7", "kchat": "\U0001F4AC", "whatsapp": "\U0001F4F1"}.get(source, "\U0001F4E8")


# ── Worker Thread fuer Datalake-Scan ────────────────────────────────────────

class ScanWorker(QObject):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def run(self):
        try:
            msgs = scan_datalake()
            self.finished.emit(msgs)
        except Exception as e:
            self.error.emit(f"{e}\n{traceback.format_exc()}")


# ── Custom List Item Widget ─────────────────────────────────────────────────

class MessageItemWidget(QWidget):
    def __init__(self, msg, parent=None):
        super().__init__(parent)
        self.msg = msg
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        # Status-Punkt
        dot = QLabel("\u25CF" if not self.msg["is_read"] else "\u25CB")
        dot.setStyleSheet(
            f"color: {'#f0c060' if not self.msg['is_read'] else '#444'}; font-size: 12px;"
        )
        dot.setFixedWidth(14)
        layout.addWidget(dot)

        # Inhalt (vertical)
        content = QVBoxLayout()
        content.setSpacing(2)
        content.setContentsMargins(0, 0, 0, 0)

        # Top-Zeile: Icon + Sender + Age
        top = QHBoxLayout()
        top.setSpacing(6)
        top.setContentsMargins(0, 0, 0, 0)

        icon = QLabel(channel_icon(self.msg["source"]))
        icon.setStyleSheet("font-size: 11px;")
        top.addWidget(icon)

        sender_text = self._sender_short()
        sender = QLabel(sender_text)
        sender.setStyleSheet(
            "color: #ffffff; font-size: 12px;"
            + (" font-weight: 700;" if not self.msg["is_read"] else "")
        )
        sender.setMinimumWidth(0)
        sender.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        sender.setText(sender_text)
        top.addWidget(sender, 1)

        # Score-Badge
        if self.msg["priority_score"] >= 70:
            badge = QLabel(str(self.msg["priority_score"]))
            badge.setStyleSheet(
                "background-color: #f0c060; color: #111; border-radius: 8px; "
                "padding: 1px 6px; font-size: 10px; font-weight: 700;"
            )
            top.addWidget(badge)

        # Ueberfaellig-Badge
        if self.msg["age_days"] > 3 and not self.msg["is_read"]:
            ov = QLabel("\u00DCBERF\u00C4LLIG")
            ov.setStyleSheet(
                "background-color: #a04040; color: #fff; border-radius: 4px; "
                "padding: 1px 5px; font-size: 9px; font-weight: 700;"
            )
            top.addWidget(ov)

        age = QLabel(fmt_age(self.msg["age_days"]))
        age.setStyleSheet("color: #777; font-size: 10px;")
        top.addWidget(age)

        content.addLayout(top)

        # Subject + Preview
        subj_text = self.msg["subject"][:SUBJECT_PREVIEW_LEN]
        if len(self.msg["subject"]) > SUBJECT_PREVIEW_LEN:
            subj_text += "\u2026"
        subj = QLabel(subj_text)
        subj.setStyleSheet(
            "color: #c8c8c8; font-size: 11px;"
            + (" font-weight: 600;" if not self.msg["is_read"] else "")
        )
        content.addWidget(subj)

        if self.msg["body_preview"]:
            prev = QLabel(self.msg["body_preview"][:90] + ("\u2026" if len(self.msg["body_preview"]) > 90 else ""))
            prev.setStyleSheet("color: #6a6a6a; font-size: 10px;")
            content.addWidget(prev)

        layout.addLayout(content, 1)
        self.setLayout(layout)

    def _sender_short(self):
        s = self.msg["from"]
        # Wenn "Name <email>" → nur Name
        m = re.match(r"\s*(.+?)\s*<", s)
        if m:
            return m.group(1).strip().strip('"')[:35]
        return s[:35]


# ── Main Window ──────────────────────────────────────────────────────────────

class MessageDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.messages = []
        self.filtered = []
        self.state = load_state()
        self.read_set = set(self.state.get("read_messages", []))
        self.current_filter = "all"
        self.last_count_seen = 0
        self.refresh_in_progress = False
        self._build_ui()
        self._setup_shortcuts()
        # Erstes Laden direkt
        QTimer.singleShot(50, self.refresh)
        # Auto-refresh
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(REFRESH_INTERVAL_MS)
        self.refresh_timer.timeout.connect(self.refresh)
        self.refresh_timer.start()
        # Live-Uhr
        self.clock_timer = QTimer(self)
        self.clock_timer.setInterval(30 * 1000)
        self.clock_timer.timeout.connect(self._update_clock)
        self.clock_timer.start()

    # ── UI Setup ─────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.setWindowTitle("\U0001F4EC Message Dashboard")
        self.resize(1200, 800)
        self.setStyleSheet(DARK_STYLE)

        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Stats Bar
        stats = QFrame()
        stats.setObjectName("stats-bar")
        stats.setFixedHeight(40)
        stats_layout = QHBoxLayout(stats)
        stats_layout.setContentsMargins(16, 0, 16, 0)
        stats_layout.setSpacing(0)
        self.stat_total = QLabel("Gesamt: 0")
        self.stat_total.setObjectName("stats-label")
        self.stat_unread = QLabel("Ungelesen: 0")
        self.stat_unread.setObjectName("stats-label-strong")
        self.stat_overdue = QLabel("\u00DCberf\u00E4llig: 0")
        self.stat_overdue.setObjectName("stats-label")
        self.stat_top = QLabel("Top Priority: 0")
        self.stat_top.setObjectName("stats-label")
        for w in (self.stat_total, self.stat_unread, self.stat_overdue, self.stat_top):
            stats_layout.addWidget(w)
        stats_layout.addStretch()
        self.clock_label = QLabel("")
        self.clock_label.setObjectName("stats-label")
        stats_layout.addWidget(self.clock_label)
        self._update_clock()
        outer.addWidget(stats)

        # Hauptbereich: Splitter mit 3 Panels
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)

        # Sidebar
        self.sidebar = self._build_sidebar()
        splitter.addWidget(self.sidebar)

        # Mittlere Spalte: Liste
        self.list_widget = QListWidget()
        self.list_widget.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._on_context_menu)
        splitter.addWidget(self.list_widget)

        # Rechte Spalte: Detail
        self.detail_pane = self._build_detail_pane()
        splitter.addWidget(self.detail_pane)

        splitter.setSizes([250, 400, 550])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 1)
        outer.addWidget(splitter, 1)

    def _build_sidebar(self):
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(250)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(8, 12, 8, 12)
        layout.setSpacing(2)

        title = QLabel("FILTER")
        title.setStyleSheet("color: #555; font-size: 10px; font-weight: 700; padding: 6px 12px; letter-spacing: 1px;")
        layout.addWidget(title)

        self.filter_buttons = {}
        filters = [
            ("all", "\U0001F4E5 Alle Nachrichten", None),
            ("unread", "\U0001F534 Ungelesen", None),
            ("overdue", "\u26A0\uFE0F \u00DCberf\u00E4llig (>3 Tage)", None),
            ("top", "\u2B50 Top Priority", None),
        ]
        for fid, label, _ in filters:
            btn = QPushButton(label)
            btn.setObjectName("filter-btn")
            btn.setCheckable(True)
            btn.clicked.connect(lambda _checked, f=fid: self.set_filter(f))
            self.filter_buttons[fid] = btn
            layout.addWidget(btn)
        self.filter_buttons["all"].setChecked(True)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background-color: #2a2a2a; max-height: 1px;")
        layout.addWidget(sep)

        title2 = QLabel("KAN\u00C4LE")
        title2.setStyleSheet("color: #555; font-size: 10px; font-weight: 700; padding: 8px 12px 4px 12px; letter-spacing: 1px;")
        layout.addWidget(title2)

        for ch in AGENT_DIRS:
            btn = QPushButton(f"\U0001F4E7 {ch}")
            btn.setObjectName("filter-btn")
            btn.setCheckable(True)
            btn.clicked.connect(lambda _checked, c=ch: self.set_filter(f"channel:{c}"))
            self.filter_buttons[f"channel:{ch}"] = btn
            layout.addWidget(btn)

        for src_label, src in [("\U0001F4AC kChat", "source:kchat"), ("\U0001F4F1 WhatsApp", "source:whatsapp")]:
            btn = QPushButton(src_label)
            btn.setObjectName("filter-btn")
            btn.setCheckable(True)
            btn.clicked.connect(lambda _checked, f=src: self.set_filter(f))
            self.filter_buttons[src] = btn
            layout.addWidget(btn)

        layout.addStretch()

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("background-color: #2a2a2a; max-height: 1px;")
        layout.addWidget(sep2)

        self.refresh_btn = QPushButton("\U0001F504 Aktualisieren")
        self.refresh_btn.setObjectName("primary-btn")
        self.refresh_btn.clicked.connect(self.refresh)
        layout.addWidget(self.refresh_btn)

        self.last_refresh_label = QLabel("Noch nicht aktualisiert")
        self.last_refresh_label.setStyleSheet("color: #555; font-size: 10px; padding: 4px 12px;")
        layout.addWidget(self.last_refresh_label)

        return sidebar

    def _build_detail_pane(self):
        pane = QFrame()
        pane.setObjectName("detail-pane")
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.detail_subject = QLabel("Keine Nachricht ausgew\u00E4hlt")
        self.detail_subject.setObjectName("detail-subject")
        self.detail_subject.setWordWrap(True)
        layout.addWidget(self.detail_subject)

        self.detail_meta = QLabel("")
        self.detail_meta.setObjectName("detail-meta")
        self.detail_meta.setWordWrap(True)
        self.detail_meta.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.detail_meta)

        self.detail_body = QTextEdit()
        self.detail_body.setObjectName("detail-body")
        self.detail_body.setReadOnly(True)
        layout.addWidget(self.detail_body, 1)

        # Action Buttons
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(14, 10, 14, 14)
        btn_row.setSpacing(8)
        self.btn_mark_read = QPushButton("\u2713 Als gelesen markieren")
        self.btn_mark_read.setObjectName("primary-btn")
        self.btn_mark_read.clicked.connect(self._mark_current_read)
        self.btn_mark_read.setEnabled(False)
        btn_row.addWidget(self.btn_mark_read)

        self.btn_finder = QPushButton("\U0001F4C2 In Finder")
        self.btn_finder.clicked.connect(self._open_in_finder)
        self.btn_finder.setEnabled(False)
        btn_row.addWidget(self.btn_finder)

        self.btn_assistant = QPushButton("\U0001F4AC AssistantDev")
        self.btn_assistant.clicked.connect(self._open_in_assistant)
        self.btn_assistant.setEnabled(False)
        btn_row.addWidget(self.btn_assistant)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.current_msg = None
        return pane

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Cmd+R"), self, activated=self.refresh)
        QShortcut(QKeySequence("Ctrl+R"), self, activated=self.refresh)

    # ── Daten-Refresh ────────────────────────────────────────────────────────

    def refresh(self):
        if self.refresh_in_progress:
            return
        self.refresh_in_progress = True
        self.refresh_btn.setText("\u23F3 L\u00E4dt...")
        self.refresh_btn.setEnabled(False)

        self._thread = QThread(self)
        self._worker = ScanWorker()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_scan_finished)
        self._worker.error.connect(self._on_scan_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _on_scan_finished(self, msgs):
        # is_read aus State setzen
        for m in msgs:
            m["is_read"] = m["id"] in self.read_set
            m["priority_score"] = calculate_priority(m)
        # Sortierung: Score absteigend, dann Datum absteigend
        msgs.sort(key=lambda m: (-m["priority_score"], -m["date"].timestamp()))
        prev_unread_count = sum(1 for m in self.messages if not m["is_read"])
        self.messages = msgs
        new_unread_count = sum(1 for m in msgs if not m["is_read"])

        # macOS-Notification wenn neue Nachrichten
        if self.last_count_seen > 0 and len(msgs) > self.last_count_seen:
            delta = len(msgs) - self.last_count_seen
            self._notify(f"{delta} neue Nachricht(en) im Posteingang")
        self.last_count_seen = len(msgs)

        self._apply_filter()
        self._update_stats()
        self.refresh_btn.setText("\U0001F504 Aktualisieren")
        self.refresh_btn.setEnabled(True)
        self.last_refresh_label.setText(
            f"Zuletzt: {datetime.datetime.now().strftime('%H:%M:%S')}"
        )
        self.refresh_in_progress = False
        self.state["last_refresh"] = datetime.datetime.now().isoformat()
        save_state(self.state)

    def _on_scan_error(self, err):
        self.refresh_btn.setText("\U0001F504 Aktualisieren")
        self.refresh_btn.setEnabled(True)
        self.refresh_in_progress = False
        QMessageBox.warning(self, "Scan-Fehler", f"Datalake-Scan fehlgeschlagen:\n{err}")

    def _notify(self, text):
        try:
            subprocess.Popen(
                ["osascript", "-e",
                 f'display notification "{text}" with title "Message Dashboard"'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass

    # ── Filtern & Anzeigen ───────────────────────────────────────────────────

    def set_filter(self, fid):
        self.current_filter = fid
        for b_id, btn in self.filter_buttons.items():
            btn.setChecked(b_id == fid)
        self._apply_filter()

    def _apply_filter(self):
        f = self.current_filter
        if f == "all":
            self.filtered = list(self.messages)
        elif f == "unread":
            self.filtered = [m for m in self.messages if not m["is_read"]]
        elif f == "overdue":
            self.filtered = [m for m in self.messages if m["age_days"] > 3 and not m["is_read"]]
        elif f == "top":
            self.filtered = [m for m in self.messages if m["priority_score"] >= 70]
        elif f.startswith("channel:"):
            ch = f.split(":", 1)[1]
            self.filtered = [m for m in self.messages if m["channel"] == ch]
        elif f.startswith("source:"):
            src = f.split(":", 1)[1]
            self.filtered = [m for m in self.messages if m["source"] == src]
        else:
            self.filtered = list(self.messages)

        self._populate_list()

    def _populate_list(self):
        self.list_widget.clear()
        for m in self.filtered[:500]:  # Cap auf 500 fuer Performance
            item = QListWidgetItem()
            widget = MessageItemWidget(m)
            item.setSizeHint(widget.sizeHint())
            item.setData(Qt.ItemDataRole.UserRole, m["id"])
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, widget)

    def _update_stats(self):
        total = len(self.messages)
        unread = sum(1 for m in self.messages if not m["is_read"])
        overdue = sum(1 for m in self.messages if m["age_days"] > 3 and not m["is_read"])
        top = sum(1 for m in self.messages if m["priority_score"] >= 70)
        self.stat_total.setText(f"Gesamt: {total}")
        self.stat_unread.setText(f"Ungelesen: {unread}")
        self.stat_overdue.setText(f"\u00DCberf\u00E4llig: {overdue}")
        self.stat_top.setText(f"Top Priority: {top}")
        # Filter-Button-Labels mit Counts ergaenzen
        self.filter_buttons["all"].setText(f"\U0001F4E5 Alle Nachrichten ({total})")
        self.filter_buttons["unread"].setText(f"\U0001F534 Ungelesen ({unread})")
        self.filter_buttons["overdue"].setText(f"\u26A0\uFE0F \u00DCberf\u00E4llig ({overdue})")
        self.filter_buttons["top"].setText(f"\u2B50 Top Priority ({top})")
        # Channel-Counts
        for ch in AGENT_DIRS:
            c = sum(1 for m in self.messages if m["channel"] == ch)
            self.filter_buttons[f"channel:{ch}"].setText(f"\U0001F4E7 {ch} ({c})")
        kc = sum(1 for m in self.messages if m["source"] == "kchat")
        wa = sum(1 for m in self.messages if m["source"] == "whatsapp")
        self.filter_buttons["source:kchat"].setText(f"\U0001F4AC kChat ({kc})")
        self.filter_buttons["source:whatsapp"].setText(f"\U0001F4F1 WhatsApp ({wa})")

    def _update_clock(self):
        now = datetime.datetime.now()
        self.clock_label.setText(now.strftime("%a %d.%m.%Y \u00B7 %H:%M"))

    # ── Detail-Ansicht ───────────────────────────────────────────────────────

    def _on_item_clicked(self, item):
        mid = item.data(Qt.ItemDataRole.UserRole)
        msg = next((m for m in self.messages if m["id"] == mid), None)
        if not msg:
            return
        self._show_detail(msg)

    def _load_full_body(self, msg):
        """Bei initialem Scan haben wir nur 8 KB gelesen. Beim Detail-Klick
        laden wir ggf. den Volltext nach (max 1 MB)."""
        if msg.get("_body_full_loaded"):
            return msg["body"]
        try:
            with open(msg["filepath"], "r", encoding="utf-8", errors="replace") as f:
                raw = f.read(1024 * 1024)
            full = _strip_separator(raw).strip()
            # Headers vom Anfang abschneiden falls _strip_separator nichts gefunden hat
            if EMAIL_FIELD_RE.match(full.splitlines()[0] if full else ""):
                lines = full.splitlines()
                hidx = 0
                for i, ln in enumerate(lines[:30]):
                    if "\u2500\u2500\u2500" in ln or (ln.strip() == "" and hidx > 0):
                        hidx = i + 1
                        break
                    if EMAIL_FIELD_RE.match(ln):
                        hidx = i + 1
                full = "\n".join(lines[hidx:]).strip()
            msg["body"] = full or msg.get("body", "")
            msg["_body_full_loaded"] = True
        except Exception as e:
            print(f"Volltext-Load Fehler: {e}", file=sys.stderr)
        return msg["body"]

    def _show_detail(self, msg):
        self.current_msg = msg
        self._load_full_body(msg)
        self.detail_subject.setText(msg["subject"])
        meta_lines = [
            f"<b>Von:</b> {self._html_escape(msg['from'])}",
        ]
        if msg.get("to"):
            meta_lines.append(f"<b>An:</b> {self._html_escape(msg['to'])}")
        meta_lines.append(
            f"<b>Datum:</b> {msg['date'].strftime('%a, %d.%m.%Y %H:%M')} \u00B7 "
            f"<b>Quelle:</b> {msg['source']} \u00B7 "
            f"<b>Kanal:</b> {msg['channel']} \u00B7 "
            f"<b>Score:</b> {msg['priority_score']}"
        )
        self.detail_meta.setText("<br>".join(meta_lines))
        self.detail_meta.setTextFormat(Qt.TextFormat.RichText)
        self.detail_body.setPlainText(msg["body"] or "(leer)")
        self.btn_mark_read.setEnabled(True)
        self.btn_finder.setEnabled(True)
        self.btn_assistant.setEnabled(True)
        if msg["is_read"]:
            self.btn_mark_read.setText("\u2713 Als ungelesen markieren")
        else:
            self.btn_mark_read.setText("\u2713 Als gelesen markieren")

    def _html_escape(self, s):
        return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

    def _mark_current_read(self):
        if not self.current_msg:
            return
        mid = self.current_msg["id"]
        if self.current_msg["is_read"]:
            self.read_set.discard(mid)
            self.current_msg["is_read"] = False
        else:
            self.read_set.add(mid)
            self.current_msg["is_read"] = True
        self.state["read_messages"] = sorted(self.read_set)
        save_state(self.state)
        # Score neu berechnen + neu sortieren
        for m in self.messages:
            if m["id"] == mid:
                m["is_read"] = self.current_msg["is_read"]
                m["priority_score"] = calculate_priority(m)
        self.messages.sort(key=lambda m: (-m["priority_score"], -m["date"].timestamp()))
        self._apply_filter()
        self._update_stats()
        self._show_detail(self.current_msg)

    def _open_in_finder(self):
        if not self.current_msg:
            return
        try:
            subprocess.Popen(["open", "-R", self.current_msg["filepath"]])
        except Exception as e:
            QMessageBox.warning(self, "Fehler", f"Konnte Finder nicht oeffnen: {e}")

    def _open_in_assistant(self):
        if not self.current_msg:
            return
        try:
            subprocess.Popen(["open", ASSISTANT_URL])
        except Exception:
            pass

    # ── Kontextmenue ─────────────────────────────────────────────────────────

    def _on_context_menu(self, pos: QPoint):
        item = self.list_widget.itemAt(pos)
        if not item:
            return
        mid = item.data(Qt.ItemDataRole.UserRole)
        msg = next((m for m in self.messages if m["id"] == mid), None)
        if not msg:
            return
        menu = QMenu(self)
        a_read = menu.addAction(
            "Als ungelesen markieren" if msg["is_read"] else "Als gelesen markieren"
        )
        a_finder = menu.addAction("In Finder zeigen")
        action = menu.exec(self.list_widget.mapToGlobal(pos))
        if action == a_read:
            self.current_msg = msg
            self._mark_current_read()
        elif action == a_finder:
            try:
                subprocess.Popen(["open", "-R", msg["filepath"]])
            except Exception:
                pass


# ── Entry Point ──────────────────────────────────────────────────────────────

def main():
    # macOS Dock-Name
    try:
        from PyQt6.QtCore import QCoreApplication
        QCoreApplication.setApplicationName("Message Dashboard")
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setApplicationName("Message Dashboard")
    app.setStyle("Fusion")

    win = MessageDashboard()
    win.show()
    win.raise_()
    win.activateWindow()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
