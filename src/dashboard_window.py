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
    setproctitle.setproctitle("AssistantDev")
except ImportError:
    pass

# ── macOS App-Name korrekt setzen ────────────────────────────────────────────
try:
    from Foundation import NSBundle
    bundle = NSBundle.mainBundle()
    info = bundle.localizedInfoDictionary() or bundle.infoDictionary()
    if info is not None:
        info["CFBundleName"] = "AssistantDev"
except Exception:
    pass

# ── URL bestimmen ────────────────────────────────────────────────────────────

BASE_URL = "http://localhost:8080"

# Default-Route:
# • Wenn frontend/dist/index.html existiert → /app  (neue React-SPA)
# • sonst                                    → /    (Legacy-HTML aus web_server.py)
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_FRONTEND_INDEX = os.path.join(_REPO_ROOT, "frontend", "dist", "index.html")
DEFAULT_PATH = "/app" if os.path.isfile(_FRONTEND_INDEX) else ""

path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PATH
if path and not path.startswith("/"):
    path = "/" + path
url = BASE_URL + path

# ── Fenstertitel aus Pfad ableiten ───────────────────────────────────────────

TITLE_MAP = {
    "": "AssistantDev",
    "/": "AssistantDev",
    "/messages": "AssistantDev — Posteingang",
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

# DevTools im nativen Fenster: per ENV an/aus. Default: AUS — der User
# soll eine saubere App ohne automatisch geoeffnete Konsole sehen.
# Zum Aktivieren: ASSISTANTDEV_WEBVIEW_DEBUG=1 setzen, oder im Fenster
# Rechtsklick -> "Element untersuchen" (Inspector kommt auch ohne Debug-Mode).
_DEBUG = os.environ.get("ASSISTANTDEV_WEBVIEW_DEBUG", "0") != "0"

webview.start(
    debug=_DEBUG,
    private_mode=False,
)
