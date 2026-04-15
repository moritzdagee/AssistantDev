#!/usr/bin/env python3
"""AssistantDev System Tray App — unified status dashboard and service manager."""

import os
import sys
import time
import socket
import signal
import subprocess
import threading
import webbrowser

import pystray
from PIL import Image, ImageDraw, ImageFont


HOME = os.path.expanduser("~")
SRC_DIR = os.path.join(HOME, "AssistantDev", "src")
DATALAKE = os.path.join(HOME, "Library", "Mobile Documents",
                        "com~apple~CloudDocs", "Downloads shared", "claude_datalake")
ICON_PATH = os.path.join(HOME, "AssistantDev", "assets", "tray_icon.png")

STATUS = {"web": False, "clipper": False, "watcher": False}
_tray = None
_icons = {}


def _make_icon(bg_color, char, fg_color):
    img = Image.new("RGBA", (22, 22), bg_color)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 15)
    except Exception:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), char, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (22 - tw) // 2
    y = (22 - th) // 2 - bbox[1]
    draw.text((x, y), char, fill=fg_color, font=font)
    return img


def _build_icons():
    if os.path.isfile(ICON_PATH):
        try:
            _icons["normal"] = Image.open(ICON_PATH).resize((22, 22))
        except Exception:
            _icons["normal"] = _make_icon("#1a1a2e", "A", "white")
    else:
        _icons["normal"] = _make_icon("#1a1a2e", "A", "white")
    _icons["warn"] = _make_icon("#f0a500", "!", "black")
    _icons["error"] = _make_icon("#c0392b", "!", "white")


def _port_alive(port, timeout=5):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout):
            return True
    except Exception:
        return False


def _process_alive(name):
    try:
        r = subprocess.run(["pgrep", "-f", name], capture_output=True, text=True, timeout=5)
        return bool(r.stdout.strip())
    except Exception:
        return False


def _check_status():
    STATUS["web"] = _port_alive(8080)
    STATUS["clipper"] = _port_alive(8081)
    STATUS["watcher"] = _process_alive("email_watcher.py")


def _current_icon():
    if all(STATUS.values()):
        return _icons["normal"]
    if not STATUS["web"]:
        return _icons["error"]
    return _icons["warn"]


def _status_dot(key):
    return "\u2705" if STATUS[key] else "\u274c"


def _status_loop():
    while True:
        try:
            _check_status()
            if _tray:
                _tray.icon = _current_icon()
                _tray.update_menu()
        except Exception:
            pass
        time.sleep(30)


# ── Service actions ──────────────────────────────────────────────────────────

def _restart_web(_=None):
    subprocess.run(["pkill", "-f", "web_server.py"], capture_output=True)
    time.sleep(2)
    subprocess.Popen(
        [sys.executable, os.path.join(SRC_DIR, "web_server.py")],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(3)
    _check_status()
    if _tray:
        _tray.icon = _current_icon()
        _tray.update_menu()


def _restart_clipper(_=None):
    subprocess.run(["pkill", "-f", "web_clipper_server.py"], capture_output=True)
    time.sleep(2)
    subprocess.Popen(
        [sys.executable, os.path.join(SRC_DIR, "web_clipper_server.py")],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(3)
    _check_status()
    if _tray:
        _tray.icon = _current_icon()
        _tray.update_menu()


def _toggle_watcher(_=None):
    if STATUS["watcher"]:
        subprocess.run(["pkill", "-f", "email_watcher.py"], capture_output=True)
    else:
        subprocess.Popen(
            [sys.executable, os.path.join(SRC_DIR, "email_watcher.py")],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    time.sleep(2)
    _check_status()
    if _tray:
        _tray.icon = _current_icon()
        _tray.update_menu()


# ── Open actions ─────────────────────────────────────────────────────────────

def _open_dashboard(_=None):
    webbrowser.open("http://localhost:8080")

def _open_agents(_=None):
    webbrowser.open("http://localhost:8080")

def _open_memory(_=None):
    webbrowser.open("http://localhost:8080/memory")

def _open_search(_=None):
    webbrowser.open("http://localhost:8080")

def _open_clipper_status(_=None):
    webbrowser.open("http://localhost:8081")

def _open_emails(_=None):
    webbrowser.open("http://localhost:8080")

def _open_changelog(_=None):
    subprocess.run(["open", os.path.join(HOME, "AssistantDev", "changelog.md")])

def _open_techdocs(_=None):
    subprocess.run(["open", os.path.join(HOME, "AssistantDev", "docs", "TECHNICAL_DOCUMENTATION.md")])

def _open_api_docs(_=None):
    webbrowser.open("http://localhost:8080/api/docs")

def _open_source(_=None):
    subprocess.run(["open", os.path.join(HOME, "AssistantDev")])

def _open_datalake(_=None):
    subprocess.run(["open", DATALAKE])

def _quit(_=None):
    if _tray:
        _tray.stop()


# ── Menu builder ─────────────────────────────────────────────────────────────

def _build_menu():
    return pystray.Menu(
        pystray.MenuItem("AssistantDev", None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(f"{_status_dot('web')} Web Server (Port 8080)", None, enabled=False),
        pystray.MenuItem(f"{_status_dot('clipper')} Web Clipper (Port 8081)", None, enabled=False),
        pystray.MenuItem(f"{_status_dot('watcher')} Email Watcher", None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("\U0001f310  Dashboard oeffnen", _open_dashboard),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("\U0001f4f1  Services", pystray.Menu(
            pystray.MenuItem("\U0001f916  Agenten-Uebersicht", _open_agents),
            pystray.MenuItem("\U0001f9e0  Memory Management", _open_memory),
            pystray.MenuItem("\U0001f50d  Suche", _open_search),
            pystray.MenuItem("\U0001f4ce  Web Clipper Status", _open_clipper_status),
            pystray.MenuItem("\U0001f4e7  Email Inbox", _open_emails),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("\U0001f504  Web Server neu starten", _restart_web),
            pystray.MenuItem("\U0001f504  Web Clipper neu starten", _restart_clipper),
            pystray.MenuItem(
                f"\U0001f504  Email Watcher {'stoppen' if STATUS['watcher'] else 'starten'}",
                _toggle_watcher,
            ),
        )),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("\U0001f4da  Dokumentation", pystray.Menu(
            pystray.MenuItem("\U0001f4cb  Changelog", _open_changelog),
            pystray.MenuItem("\U0001f527  Technische Dokumentation", _open_techdocs),
            pystray.MenuItem("\U0001f50c  API Dokumentation", _open_api_docs),
            pystray.MenuItem("\U0001f4c1  Source Code", _open_source),
            pystray.MenuItem("\U0001f4c1  Datalake", _open_datalake),
        )),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("\u2139\ufe0f   Komponenten & Pfade", pystray.Menu(
            pystray.MenuItem("web_server.py - Haupt-App (Port 8080)", None, enabled=False),
            pystray.MenuItem("search_engine.py - Such-System", None, enabled=False),
            pystray.MenuItem("web_clipper_server.py - Chrome Extension (Port 8081)", None, enabled=False),
            pystray.MenuItem("email_watcher.py - Email Daemon", None, enabled=False),
            pystray.MenuItem("tray_app.py - System Tray", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(f"Source: {HOME}/AssistantDev/src/", None, enabled=False),
            pystray.MenuItem("Deployed: /Applications/Assistant.app/", None, enabled=False),
            pystray.MenuItem("Data: claude_datalake/", None, enabled=False),
        )),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("\u274c  Beenden", _quit),
    )


# ── LaunchAgent setup ────────────────────────────────────────────────────────

def _install_launch_agent():
    la_dir = os.path.join(HOME, "Library", "LaunchAgents")
    plist_path = os.path.join(la_dir, "com.assistantdev.tray.plist")
    tray_script = os.path.join(HOME, "AssistantDev", "src", "tray_app.py")

    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.assistantdev.tray</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>{tray_script}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardErrorPath</key>
    <string>/tmp/assistantdev_tray.log</string>
    <key>StandardOutPath</key>
    <string>/tmp/assistantdev_tray.log</string>
</dict>
</plist>
"""

    os.makedirs(la_dir, exist_ok=True)

    # Unload old menubar agent if present
    old_plist = os.path.join(la_dir, "com.assistantdev.menubar.plist")
    if os.path.isfile(old_plist):
        subprocess.run(["launchctl", "unload", old_plist],
                       capture_output=True, timeout=5)

    # Unload existing tray agent before rewriting
    if os.path.isfile(plist_path):
        subprocess.run(["launchctl", "unload", plist_path],
                       capture_output=True, timeout=5)

    with open(plist_path, "w") as f:
        f.write(plist_content)

    subprocess.run(["launchctl", "load", plist_path],
                   capture_output=True, timeout=5)
    print(f"[TRAY] LaunchAgent installed: {plist_path}")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    global _tray

    _build_icons()
    _check_status()

    # Don't install LaunchAgent when already running from it (avoid reload loop)
    if not os.environ.get("__ASSISTANTDEV_TRAY_SKIP_LA"):
        os.environ["__ASSISTANTDEV_TRAY_SKIP_LA"] = "1"
        _install_launch_agent()

    _tray = pystray.Icon(
        "AssistantDev",
        icon=_current_icon(),
        title="AssistantDev",
        menu=_build_menu(),
    )

    t = threading.Thread(target=_status_loop, daemon=True)
    t.start()

    print("[TRAY] AssistantDev System Tray started")
    _tray.run()


if __name__ == "__main__":
    main()
