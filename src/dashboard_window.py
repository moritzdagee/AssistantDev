#!/usr/bin/env python3
"""
AssistantDev — Native Dashboard Window
Oeffnet das Web-Dashboard in einem eigenstaendigen macOS-Fenster (WebKit),
getrennt von Chrome und anderen Browsern.

Aufruf:
  python3 dashboard_window.py                    → localhost:8080
  python3 dashboard_window.py /admin             → localhost:8080/admin
  python3 dashboard_window.py /admin/docs        → localhost:8080/admin/docs
  python3 dashboard_window.py /admin/changelog   → localhost:8080/admin/changelog
  python3 dashboard_window.py /admin/permissions  → localhost:8080/admin/permissions
"""

import sys
import os

try:
    import setproctitle
    setproctitle.setproctitle("AssistantDev Dashboard")
except ImportError:
    pass

# ── URL bestimmen ────────────────────────────────────────────────────────────

BASE_URL = "http://localhost:8080"
path = sys.argv[1] if len(sys.argv) > 1 else ""
if path and not path.startswith("/"):
    path = "/" + path
url = BASE_URL + path

# ── Fenstertitel aus Pfad ableiten ───────────────────────────────────────────

TITLE_MAP = {
    "": "AssistantDev — Dashboard",
    "/": "AssistantDev — Dashboard",
    "/admin": "AssistantDev — Admin Panel",
    "/admin/docs": "AssistantDev — Technische Dokumentation",
    "/admin/changelog": "AssistantDev — Changelog",
    "/admin/permissions": "AssistantDev — Berechtigungen",
}
title = TITLE_MAP.get(path, f"AssistantDev — {path}")

# ── Natives Fenster oeffnen ──────────────────────────────────────────────────

import webview

window = webview.create_window(
    title=title,
    url=url,
    width=1280,
    height=900,
    min_size=(800, 600),
    text_select=True,
)

webview.start(
    debug=False,
    private_mode=False,
)
