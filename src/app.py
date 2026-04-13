#!/usr/bin/env python3
"""
Assistant Menu Bar App
Manages all AssistantDev services from the macOS menu bar.

Services:
  - Web Server (port 8080)      — Flask UI + Chat API
  - Email Watcher               — Importiert E-Mails ins Agent-Memory
  - Web Clipper (port 8081)     — Chrome Extension Backend
  - kChat Watcher               — Importiert kChat-Nachrichten ins Agent-Memory
  - Message Dashboard           — Native macOS Inbox-App (PyQt6, GUI)
"""

import os
import sys
import signal
import subprocess
import threading
import time
import logging
from datetime import datetime

import rumps

# ── Pfade ────────────────────────────────────────────────────────────────────

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(sys.executable))),
        "Resources",
    )
    PYTHON = "/Applications/Xcode.app/Contents/Developer/usr/bin/python3"
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    PYTHON = sys.executable

LOG_DIR = os.path.expanduser("~/Library/Logs/Assistant")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    filename=os.path.join(LOG_DIR, "assistant.log"),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("Assistant")


# ── Service-Klasse ───────────────────────────────────────────────────────────

class Service:
    """Ein verwalteter Hintergrund-Dienst."""

    def __init__(self, name, script, port=None, is_gui=False, auto_restart=True):
        self.name = name
        self.script = os.path.join(BASE_DIR, script)
        self.port = port
        self.is_gui = is_gui            # GUI-Apps: kein Watchdog-Auto-Restart
        self.auto_restart = auto_restart
        self.process = None
        self.log_path = os.path.join(LOG_DIR, f"{name.lower().replace(' ', '_')}.log")
        self.paused = False              # Manuell gestoppt → kein Auto-Restart

    @property
    def running(self):
        return self.process is not None and self.process.poll() is None

    @property
    def status_emoji(self):
        if self.running:
            return "\U0001F7E2"  # 🟢
        if self.paused:
            return "\u23F8\uFE0F"  # ⏸️
        return "\U0001F534"  # 🔴

    @property
    def status_text(self):
        port_info = f" :{self.port}" if self.port else ""
        if self.running:
            return f"{self.status_emoji} {self.name}{port_info}"
        if self.paused:
            return f"{self.status_emoji} {self.name}{port_info} (pausiert)"
        return f"{self.status_emoji} {self.name}{port_info} (gestoppt)"

    def start(self):
        if self.running:
            return
        if not os.path.exists(self.script):
            log.error("Script nicht gefunden: %s", self.script)
            return
        log.info("Starting %s", self.name)
        log_file = open(self.log_path, "a")
        env = os.environ.copy()
        for key in ("PYTHONHOME", "PYTHONPATH", "PYOBJC_BUNDLE_ADDRESS",
                     "RESOURCEPATH", "__PYVENV_LAUNCHER__"):
            env.pop(key, None)
        self.process = subprocess.Popen(
            [PYTHON, self.script],
            stdout=log_file,
            stderr=subprocess.STDOUT,
            env=env,
            preexec_fn=os.setsid,
        )
        self.paused = False
        log.info("%s started (pid %d)", self.name, self.process.pid)

    def stop(self):
        if not self.running:
            self.process = None
            return
        log.info("Stopping %s (pid %d)", self.name, self.process.pid)
        try:
            os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
            self.process.wait(timeout=5)
        except Exception:
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
            except Exception:
                pass
        self.process = None
        log.info("%s stopped", self.name)

    def restart(self):
        self.stop()
        time.sleep(0.5)
        self.start()

    def pause(self):
        """Stoppt den Service und verhindert Auto-Restart bis resume()."""
        self.stop()
        self.paused = True
        log.info("%s paused (kein Auto-Restart)", self.name)

    def resume(self):
        """Startet den Service und erlaubt Auto-Restart wieder."""
        self.paused = False
        self.start()
        log.info("%s resumed", self.name)


# ── Haupt-App ────────────────────────────────────────────────────────────────

class AssistantApp(rumps.App):
    def __init__(self):
        super().__init__("Assistant", icon=None, title="\U0001F916", quit_button=None)

        self.services = [
            Service("Web Server", "web_server.py", port=8080),
            Service("Email Watcher", "email_watcher.py"),
            Service("Web Clipper", "web_clipper_server.py", port=8081),
            Service("kChat Watcher", "kchat_watcher.py"),
            Service("Message Dashboard", "message_dashboard.py", is_gui=True, auto_restart=False),
        ]

        self._build_menu()
        self._start_background_services()
        self._start_watchdog()

    # ── Menu aufbauen ────────────────────────────────────────────────────────

    def _build_menu(self):
        self.menu.clear()

        # --- Status-Header ---
        header = rumps.MenuItem("SERVICES")
        header.set_callback(None)
        self.menu.add(header)

        # --- Pro Service: Status + Toggle-Button ---
        self.status_items = {}
        self.toggle_items = {}

        for svc in self.services:
            # Status-Zeile (nicht klickbar)
            status = rumps.MenuItem(svc.status_text)
            status.set_callback(None)
            self.status_items[svc.name] = status
            self.menu.add(status)

            # Toggle-Button: Start/Stopp
            toggle_label = self._toggle_label(svc)
            toggle = rumps.MenuItem(
                toggle_label,
                callback=self._make_toggle_callback(svc),
            )
            self.toggle_items[svc.name] = toggle
            self.menu.add(toggle)

            # Restart-Button (nur fuer laufende Services sinnvoll)
            restart = rumps.MenuItem(
                f"    \u21BB Restart {svc.name}",
                callback=self._make_restart_callback(svc),
            )
            self.menu.add(restart)

        self.menu.add(rumps.separator)

        # --- Globale Aktionen ---
        self.menu.add(rumps.MenuItem(
            "\U0001F4EC Open Dashboard",
            callback=self._open_dashboard,
        ))
        self.menu.add(rumps.MenuItem(
            "\U0001F4C2 Open Logs",
            callback=self._open_logs,
        ))
        self.menu.add(rumps.MenuItem(
            "\U0001F310 Open Web Interface",
            callback=self._open_web,
        ))
        self.menu.add(rumps.separator)
        self.menu.add(rumps.MenuItem(
            "\u21BB Restart All Services",
            callback=self._restart_all,
        ))
        self.menu.add(rumps.separator)
        self.menu.add(rumps.MenuItem("Quit", callback=self._quit))

    def _toggle_label(self, svc):
        if svc.running:
            return f"    \u23F8 Pause {svc.name}"
        else:
            return f"    \u25B6 Start {svc.name}"

    def _make_toggle_callback(self, svc):
        def callback(_):
            if svc.running:
                threading.Thread(target=svc.pause, daemon=True).start()
            else:
                threading.Thread(target=svc.resume, daemon=True).start()
            # Status nach kurzer Verzoegerung aktualisieren
            time.sleep(1)
            self._update_status()
        return callback

    def _make_restart_callback(self, svc):
        def callback(_):
            threading.Thread(target=svc.restart, daemon=True).start()
            time.sleep(1.5)
            self._update_status()
        return callback

    # ── Services starten ─────────────────────────────────────────────────────

    def _start_background_services(self):
        """Startet alle Services ausser GUI-Apps (die startet der User manuell)."""
        for svc in self.services:
            if svc.is_gui:
                continue  # Dashboard wird nicht automatisch gestartet
            try:
                svc.start()
            except Exception as e:
                log.error("Failed to start %s: %s", svc.name, e)

    # ── Watchdog ─────────────────────────────────────────────────────────────

    def _start_watchdog(self):
        self._watchdog_timer = rumps.Timer(self._watchdog_tick, 15)
        self._watchdog_timer.start()

    def _watchdog_tick(self, _):
        for svc in self.services:
            # Auto-Restart: nur fuer nicht-pausierte Background-Services
            if not svc.running and svc.auto_restart and not svc.paused:
                log.warning("%s is down, restarting...", svc.name)
                try:
                    svc.start()
                except Exception as e:
                    log.error("Auto-restart failed for %s: %s", svc.name, e)
        self._update_status()

    def _update_status(self):
        """Aktualisiert alle Status-Zeilen und Toggle-Labels im Menu."""
        for svc in self.services:
            if svc.name in self.status_items:
                self.status_items[svc.name].title = svc.status_text
            if svc.name in self.toggle_items:
                self.toggle_items[svc.name].title = self._toggle_label(svc)

    # ── Globale Aktionen ─────────────────────────────────────────────────────

    def _open_dashboard(self, _):
        """Startet das Message Dashboard falls es nicht laeuft."""
        dash = next((s for s in self.services if s.name == "Message Dashboard"), None)
        if dash and not dash.running:
            threading.Thread(target=dash.start, daemon=True).start()
        else:
            # Falls es schon laeuft: Fenster nach vorne bringen
            subprocess.Popen([
                "osascript", "-e",
                'tell application "System Events" to set frontmost of '
                'every process whose name contains "Python" to true',
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _open_logs(self, _):
        subprocess.Popen(["open", LOG_DIR])

    def _open_web(self, _):
        subprocess.Popen(["open", "http://localhost:8080"])

    def _restart_all(self, _):
        def do_restart():
            for svc in self.services:
                if svc.is_gui:
                    continue  # GUI-Apps nicht automatisch restarten
                svc.restart()
        threading.Thread(target=do_restart, daemon=True).start()

    def _quit(self, _):
        log.info("Quitting Assistant app")
        for svc in self.services:
            svc.stop()
        rumps.quit_application()


if __name__ == "__main__":
    AssistantApp().run()
