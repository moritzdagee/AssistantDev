#!/usr/bin/env python3
"""
AssistantDev — System Tray App
Verwaltet alle AssistantDev-Services aus der macOS Menu Bar.

Services:
  - Web Server (Port 8080)
  - Web Clipper (Port 8081)
  - Email Watcher
"""

import os
import sys
import signal
import subprocess
import threading
import time
import socket
import logging
from datetime import datetime

import rumps

try:
    import setproctitle
    setproctitle.setproctitle("AssistantDev")
except ImportError:
    pass

# ── macOS App-Name auf "AssistantDev" setzen (statt "Python") ────────────────
try:
    from Foundation import NSBundle
    bundle = NSBundle.mainBundle()
    info = bundle.localizedInfoDictionary() or bundle.infoDictionary()
    if info is not None:
        info["CFBundleName"] = "AssistantDev"
except Exception:
    pass

# ── Pfade ────────────────────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.expanduser("~")
ASSISTANT_DIR = os.path.join(HOME, "AssistantDev")
LOG_DIR = os.path.join(ASSISTANT_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    filename=os.path.join(LOG_DIR, "tray.log"),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("AssistantDev")


# ── Status-Checks ────────────────────────────────────────────────────────────

def _port_open(port, timeout=2):
    """Prueft ob ein Port erreichbar ist."""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout):
            return True
    except Exception:
        return False


def _process_running(*patterns):
    """Prueft ob mindestens einer der Patterns als laufender Prozess gefunden wird."""
    for pat in patterns:
        try:
            result = subprocess.run(
                ["pgrep", "-f", pat],
                capture_output=True, text=True, timeout=3,
            )
            if result.returncode == 0 and result.stdout.strip():
                return True
        except Exception:
            pass
    return False


# ── Haupt-App ────────────────────────────────────────────────────────────────

class AssistantDevApp(rumps.App):
    def __init__(self):
        super().__init__("AssistantDev", icon=None, title="\U0001F916", quit_button=None)

        # Status-Tracking
        self._web_server_ok = False
        self._web_clipper_ok = False
        self._email_watcher_ok = False

        self._build_menu()
        self._start_status_timer()

    # ── Menu aufbauen ────────────────────────────────────────────────────────

    def _build_menu(self):
        self.menu.clear()

        # --- Titel ---
        title = rumps.MenuItem("AssistantDev")
        title.set_callback(None)
        self.menu.add(title)
        self.menu.add(rumps.separator)

        # --- Status ---
        status_header = rumps.MenuItem("Status:")
        status_header.set_callback(None)
        self.menu.add(status_header)

        self._status_web = rumps.MenuItem("\U0001F534 Web Server (Port 8080)")
        self._status_web.set_callback(None)
        self.menu.add(self._status_web)

        self._status_clipper = rumps.MenuItem("\U0001F534 Web Clipper (Port 8081)")
        self._status_clipper.set_callback(None)
        self.menu.add(self._status_clipper)

        self._status_email = rumps.MenuItem("\U0001F534 Email Watcher")
        self._status_email.set_callback(None)
        self.menu.add(self._status_email)

        self.menu.add(rumps.separator)

        # --- Services neu starten ---
        restart_menu = rumps.MenuItem("Services neu starten")
        restart_menu.add(rumps.MenuItem(
            "Web Server neu starten",
            callback=self._restart_web_server,
        ))
        restart_menu.add(rumps.MenuItem(
            "Web Clipper neu starten",
            callback=self._restart_web_clipper,
        ))
        restart_menu.add(rumps.MenuItem(
            "Email Watcher neu starten",
            callback=self._restart_email_watcher,
        ))
        restart_menu.add(rumps.separator)
        restart_menu.add(rumps.MenuItem(
            "Alle neu starten",
            callback=self._restart_all,
        ))
        self.menu.add(restart_menu)

        self.menu.add(rumps.separator)

        # --- Oeffnen ---
        open_menu = rumps.MenuItem("Oeffnen")
        open_menu.add(rumps.MenuItem(
            "Dashboard",
            callback=self._open_dashboard,
        ))
        open_menu.add(rumps.MenuItem(
            "Admin Panel",
            callback=self._open_admin,
        ))
        open_menu.add(rumps.MenuItem(
            "Technische Dokumentation",
            callback=self._open_docs,
        ))
        open_menu.add(rumps.MenuItem(
            "Changelog",
            callback=self._open_changelog,
        ))
        self.menu.add(open_menu)

        self.menu.add(rumps.separator)

        # --- Logs ---
        logs_menu = rumps.MenuItem("Logs")
        logs_menu.add(rumps.MenuItem(
            "Web Server Log anzeigen",
            callback=self._open_web_log,
        ))
        logs_menu.add(rumps.MenuItem(
            "Watchdog Log anzeigen",
            callback=self._open_watchdog_log,
        ))
        self.menu.add(logs_menu)

        self.menu.add(rumps.separator)

        # --- Beenden ---
        self.menu.add(rumps.MenuItem("Beenden", callback=self._quit))

    # ── Status-Timer (alle 30 Sekunden) ──────────────────────────────────────

    def _start_status_timer(self):
        self._timer = rumps.Timer(self._update_status, 30)
        self._timer.start()
        # Sofort einmal ausfuehren
        threading.Thread(target=self._do_status_check, daemon=True).start()

    def _update_status(self, _):
        threading.Thread(target=self._do_status_check, daemon=True).start()

    def _do_status_check(self):
        """Prueft alle Services und aktualisiert die Menu-Eintraege."""
        self._web_server_ok = _port_open(8080)
        self._web_clipper_ok = _port_open(8081)
        self._email_watcher_ok = _process_running(
            "email_watcher.py", "AssistantDev EmailWatcher"
        )

        green = "\U0001F7E2"  # 🟢
        red = "\U0001F534"    # 🔴

        self._status_web.title = (
            f"{green if self._web_server_ok else red} Web Server (Port 8080)"
        )
        self._status_clipper.title = (
            f"{green if self._web_clipper_ok else red} Web Clipper (Port 8081)"
        )
        self._status_email.title = (
            f"{green if self._email_watcher_ok else red} Email Watcher"
        )

    # ── Neustart-Aktionen ────────────────────────────────────────────────────

    def _restart_web_server(self, _):
        def do():
            log.info("Restarting Web Server...")
            # App Bundle aktualisieren
            src = os.path.join(ASSISTANT_DIR, "src", "web_server.py")
            dst = "/Applications/Assistant.app/Contents/Resources/web_server.py"
            if os.path.exists(src):
                try:
                    subprocess.run(["cp", src, dst], timeout=5)
                except Exception:
                    pass
            # Stoppen
            subprocess.run(["pkill", "-f", "web_server.py"], timeout=5,
                           capture_output=True)
            time.sleep(2)
            # Starten
            log_file = open(os.path.join(LOG_DIR, "web_server.log"), "a")
            subprocess.Popen(
                [sys.executable, os.path.join(ASSISTANT_DIR, "src", "web_server.py")],
                stdout=log_file, stderr=subprocess.STDOUT,
                cwd=os.path.join(ASSISTANT_DIR, "src"),
            )
            log.info("Web Server restarted")
            time.sleep(3)
            self._do_status_check()
        threading.Thread(target=do, daemon=True).start()

    def _restart_web_clipper(self, _):
        def do():
            log.info("Restarting Web Clipper...")
            subprocess.run(["pkill", "-f", "web_clipper_server.py"], timeout=5,
                           capture_output=True)
            time.sleep(1)
            log_file = open(os.path.join(LOG_DIR, "web_clipper.log"), "a")
            subprocess.Popen(
                [sys.executable, os.path.join(ASSISTANT_DIR, "src", "web_clipper_server.py")],
                stdout=log_file, stderr=subprocess.STDOUT,
                cwd=os.path.join(ASSISTANT_DIR, "src"),
            )
            log.info("Web Clipper restarted")
            time.sleep(2)
            self._do_status_check()
        threading.Thread(target=do, daemon=True).start()

    def _restart_email_watcher(self, _):
        def do():
            log.info("Restarting Email Watcher...")
            subprocess.run(["pkill", "-f", "email_watcher.py"], timeout=5,
                           capture_output=True)
            time.sleep(1)
            log_file = open(os.path.join(LOG_DIR, "email_watcher.log"), "a")
            subprocess.Popen(
                [sys.executable, os.path.join(ASSISTANT_DIR, "src", "email_watcher.py")],
                stdout=log_file, stderr=subprocess.STDOUT,
                cwd=os.path.join(ASSISTANT_DIR, "src"),
            )
            log.info("Email Watcher restarted")
            time.sleep(2)
            self._do_status_check()
        threading.Thread(target=do, daemon=True).start()

    def _restart_all(self, _):
        def do():
            log.info("Restarting ALL services...")
            # Web Server
            src = os.path.join(ASSISTANT_DIR, "src", "web_server.py")
            dst = "/Applications/Assistant.app/Contents/Resources/web_server.py"
            if os.path.exists(src):
                try:
                    subprocess.run(["cp", src, dst], timeout=5)
                except Exception:
                    pass
            subprocess.run(["pkill", "-f", "web_server.py"], timeout=5,
                           capture_output=True)
            subprocess.run(["pkill", "-f", "web_clipper_server.py"], timeout=5,
                           capture_output=True)
            subprocess.run(["pkill", "-f", "email_watcher.py"], timeout=5,
                           capture_output=True)
            time.sleep(2)

            for script, logname in [
                ("web_server.py", "web_server.log"),
                ("web_clipper_server.py", "web_clipper.log"),
                ("email_watcher.py", "email_watcher.log"),
            ]:
                lf = open(os.path.join(LOG_DIR, logname), "a")
                subprocess.Popen(
                    [sys.executable, os.path.join(ASSISTANT_DIR, "src", script)],
                    stdout=lf, stderr=subprocess.STDOUT,
                    cwd=os.path.join(ASSISTANT_DIR, "src"),
                )
                time.sleep(1)

            log.info("All services restarted")
            time.sleep(3)
            self._do_status_check()
        threading.Thread(target=do, daemon=True).start()

    # ── Natives Fenster oeffnen (pywebview statt Chrome) ───────────────────────

    def _open_native_window(self, path=""):
        """Oeffnet ein natives macOS-Fenster via dashboard_window.py."""
        script = os.path.join(ASSISTANT_DIR, "src", "dashboard_window.py")
        subprocess.Popen(
            [sys.executable, script, path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def _open_dashboard(self, _):
        self._open_native_window("/")

    def _open_admin(self, _):
        self._open_native_window("/admin")

    def _open_docs(self, _):
        self._open_native_window("/admin/docs")

    def _open_changelog(self, _):
        self._open_native_window("/admin/changelog")

    # ── Log-Aktionen ─────────────────────────────────────────────────────────

    def _open_web_log(self, _):
        log_path = os.path.join(LOG_DIR, "web_server.log")
        if os.path.exists(log_path):
            subprocess.Popen(["open", "-a", "Console", log_path])
        else:
            rumps.notification("AssistantDev", "", "Web Server Log nicht gefunden")

    def _open_watchdog_log(self, _):
        log_path = os.path.join(ASSISTANT_DIR, "logs", "watchdog.log")
        if os.path.exists(log_path):
            subprocess.Popen(["open", "-a", "Console", log_path])
        else:
            rumps.notification("AssistantDev", "", "Watchdog Log nicht gefunden")

    # ── Beenden ──────────────────────────────────────────────────────────────

    def _quit(self, _):
        log.info("AssistantDev Tray App beendet (Services laufen weiter)")
        rumps.quit_application()


if __name__ == "__main__":
    AssistantDevApp().run()
