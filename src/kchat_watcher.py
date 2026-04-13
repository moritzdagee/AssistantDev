#!/usr/bin/env python3
"""
kChat Inbound Watcher
Hintergrunddienst der eingehende Nachrichten aus Infomaniak kChat
(Mattermost-basiert) ins AssistantDev Memory speichert — analog zum
bestehenden email_watcher.py.

kChat API: Mattermost v4 unter
    https://<team>.kchat.infomaniak.com/api/v4/
Auth:      Authorization: Bearer <token>

Start:     python3 ~/AssistantDev/src/kchat_watcher.py
Laeuft im Hintergrund. Control+C zum Beenden.
"""

import os
import sys
import json
import time
import datetime
import re
import traceback

try:
    import requests
except ImportError:
    print("FEHLER: Python-Modul 'requests' fehlt. Bitte installieren: pip3 install requests")
    sys.exit(1)

# ── Pfade ────────────────────────────────────────────────────────────────────

BASE = os.path.expanduser(
    "~/Library/Mobile Documents/com~apple~CloudDocs/Downloads shared/claude_datalake"
)
MODELS_FILE = os.path.join(BASE, "config/models.json")
AGENTS_DIR = os.path.join(BASE, "config/agents")

# State liegt im HOME (nicht iCloud) – LaunchAgent-freundlich
STATE_FILE = os.path.expanduser("~/.kchat_watcher_state.json")
# Credential-Cache im HOME, weil LaunchAgents keinen Zugriff auf
# iCloud-Pfade haben (macOS Privacy-Sandbox). Der Cache wird bei jedem
# erfolgreichen Lesen von models.json aktualisiert und dient sonst als
# Fallback.
CRED_CACHE_FILE = os.path.expanduser("~/.kchat_watcher_config.json")
LOG_FILE = "/tmp/kchat_watcher.log"

DEFAULT_AGENT = "privat"

# Hard-coded Routing analog email_watcher.py (keyword -> agent)
ROUTING = [
    ("signicat", "signicat"),
    ("elavon", "signicat"),
    ("trustedcarrier", "trustedcarrier"),
    ("trusted carrier", "trustedcarrier"),
    ("tangerina", "privat"),
    ("family", "privat"),
    ("familie", "privat"),
    ("privat", "privat"),
]

# Search-Index-Integration (optional)
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from search_engine import index_single_file  # type: ignore
except Exception:
    index_single_file = None


# ── Logging ──────────────────────────────────────────────────────────────────

def log(msg):
    ts = datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    line = f"{ts} {msg}"
    print(line, flush=True)


# ── Credentials laden ────────────────────────────────────────────────────────

def _parse_kchat_block(kc):
    api_base = kc.get("api_base") or (
        kc.get("server_url", "").rstrip("/") + "/api/v4"
    )
    token = kc.get("auth_token", "")
    if not token:
        raise ValueError("Kein auth_token in kchat-Config gesetzt.")
    return {
        "api_base": api_base.rstrip("/"),
        "team_name": kc.get("team_name", ""),
        "token": token,
        "user_id": kc.get("user_id", ""),
        "poll_interval_seconds": int(kc.get("poll_interval_seconds", 60)),
    }


def load_credentials():
    """Versuche zuerst models.json aus iCloud, falle auf HOME-Cache zurueck.
    LaunchAgents haben unter macOS keinen Zugriff auf iCloud-Pfade, deshalb
    wird beim erfolgreichen Lesen aus iCloud automatisch ein Cache im HOME
    angelegt (~/.kchat_watcher_config.json).
    """
    icloud_err = None
    if os.path.exists(MODELS_FILE):
        try:
            with open(MODELS_FILE) as f:
                data = json.load(f)
            kc = data.get("kchat")
            if not kc:
                raise ValueError("Kein 'kchat' Block in models.json.")
            creds = _parse_kchat_block(kc)
            # Cache aktualisieren fuer LaunchAgent-Zugriff
            try:
                with open(CRED_CACHE_FILE, "w") as f:
                    json.dump(kc, f, indent=2)
                try:
                    os.chmod(CRED_CACHE_FILE, 0o600)
                except Exception:
                    pass
                log(f"Credentials aus models.json geladen und nach {CRED_CACHE_FILE} gespiegelt")
            except Exception as ce:
                log(f"WARN: Cache-Write fehlgeschlagen: {ce}")
            return creds
        except PermissionError as pe:
            icloud_err = pe
            log(f"WARN: Kein Zugriff auf iCloud models.json ({pe}) — verwende HOME-Cache")
        except Exception as e:
            icloud_err = e
            log(f"WARN: models.json konnte nicht gelesen werden ({e}) — verwende HOME-Cache")
    else:
        log(f"INFO: models.json nicht gefunden ({MODELS_FILE}) — verwende HOME-Cache")

    # Fallback: HOME-Cache
    if os.path.exists(CRED_CACHE_FILE):
        with open(CRED_CACHE_FILE) as f:
            kc = json.load(f)
        log(f"Credentials aus HOME-Cache geladen: {CRED_CACHE_FILE}")
        return _parse_kchat_block(kc)

    # Nichts funktioniert
    raise FileNotFoundError(
        f"Weder iCloud models.json ({icloud_err}) noch HOME-Cache verfuegbar. "
        f"Bitte Watcher einmal manuell starten um Cache anzulegen: "
        f"python3 ~/AssistantDev/src/kchat_watcher.py"
    )


# ── State ────────────────────────────────────────────────────────────────────

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except Exception as e:
            log(f"WARN: State-Datei nicht lesbar ({e}) – erzeuge neuen State")
    # Default: letzte 24h importieren
    cutoff = datetime.datetime.now() - datetime.timedelta(hours=24)
    return {
        "last_check_ms": int(cutoff.timestamp() * 1000),
        "last_check_iso": cutoff.isoformat(),
        "known_channel_ids": [],
        "processed_post_ids": [],
    }


def save_state(state):
    # processed_post_ids auf sinnvolle Groesse begrenzen (letzte 5000)
    if len(state.get("processed_post_ids", [])) > 5000:
        state["processed_post_ids"] = state["processed_post_ids"][-5000:]
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        log(f"FEHLER beim Schreiben von State: {e}")


# ── HTTP-Client ──────────────────────────────────────────────────────────────

class KChatClient:
    def __init__(self, api_base, token):
        self.api_base = api_base
        self.token = token
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "AssistantDev kChat Watcher",
        })

    def _req(self, method, path, **kwargs):
        url = f"{self.api_base}{path}"
        kwargs.setdefault("timeout", 30)
        resp = self.session.request(method, url, **kwargs)
        return resp

    def get_me(self):
        r = self._req("GET", "/users/me")
        r.raise_for_status()
        return r.json()

    def get_team_by_name(self, team_name):
        r = self._req("GET", f"/teams/name/{team_name}")
        r.raise_for_status()
        return r.json()

    def get_my_channels(self, team_id, user_id):
        """Liste aller Kanaele inkl. DMs / Private Groups fuer Team + User."""
        r = self._req(
            "GET",
            f"/users/{user_id}/teams/{team_id}/channels",
        )
        r.raise_for_status()
        return r.json()

    def get_direct_channels(self, user_id):
        """Alle Channels (inkl. DMs/Gruppen) des Users teamuebergreifend."""
        r = self._req("GET", f"/users/{user_id}/channels")
        try:
            r.raise_for_status()
            return r.json()
        except Exception:
            return []

    def get_channel(self, channel_id):
        r = self._req("GET", f"/channels/{channel_id}")
        r.raise_for_status()
        return r.json()

    def get_posts_since(self, channel_id, since_ms):
        r = self._req(
            "GET",
            f"/channels/{channel_id}/posts",
            params={"since": since_ms},
        )
        r.raise_for_status()
        return r.json()

    def get_user(self, user_id):
        r = self._req("GET", f"/users/{user_id}")
        r.raise_for_status()
        return r.json()


# ── Routing ──────────────────────────────────────────────────────────────────

def route_agent(channel_name, message_text):
    text = (str(channel_name or "") + " " + str(message_text or ""))[:1000].lower()
    for keyword, agent in ROUTING:
        if keyword in text:
            agent_file = os.path.join(AGENTS_DIR, agent + ".txt")
            if os.path.exists(agent_file):
                return agent
    return DEFAULT_AGENT


# ── Dateinamen-Bereinigung ───────────────────────────────────────────────────

def clean_for_filename(s, maxlen=55):
    s = re.sub(r"[^\w\s@.-]", " ", str(s or ""))
    s = re.sub(r"\s+", "_", s.strip())
    s = s.replace("@", "_at_").replace(".", "_")
    s = re.sub(r"_+", "_", s)
    return s[:maxlen].strip("_") or "unknown"


# ── Benutzer-Cache ───────────────────────────────────────────────────────────

_user_cache = {}


def resolve_username(client, user_id):
    if not user_id:
        return "unknown", ""
    if user_id in _user_cache:
        return _user_cache[user_id]
    try:
        u = client.get_user(user_id)
        username = u.get("username") or u.get("email") or user_id
        display = (
            (u.get("first_name", "") + " " + u.get("last_name", "")).strip()
            or u.get("nickname", "")
        )
        _user_cache[user_id] = (username, display)
        return username, display
    except Exception as e:
        log(f"  WARN: Konnte User {user_id} nicht aufloesen: {e}")
        _user_cache[user_id] = (user_id, "")
        return user_id, ""


# ── Kanal-Cache ──────────────────────────────────────────────────────────────

_channel_cache = {}


def resolve_channel_name(client, channel_id, channel_obj=None):
    if channel_id in _channel_cache:
        return _channel_cache[channel_id]
    try:
        ch = channel_obj or client.get_channel(channel_id)
        # Mattermost types: O=Open, P=Private, D=DM, G=GroupMsg
        ctype = ch.get("type", "")
        if ctype == "D":
            # DM: display_name enthaelt gegenueber als "id1__id2"
            name = "dm_" + (ch.get("display_name") or ch.get("name") or channel_id)[:40]
        elif ctype == "G":
            name = "gm_" + (ch.get("display_name") or ch.get("name") or channel_id)[:40]
        else:
            name = ch.get("display_name") or ch.get("name") or channel_id
        _channel_cache[channel_id] = (name, ctype)
        return name, ctype
    except Exception as e:
        log(f"  WARN: Konnte Channel {channel_id} nicht aufloesen: {e}")
        _channel_cache[channel_id] = (channel_id, "")
        return channel_id, ""


# ── Nachricht speichern ──────────────────────────────────────────────────────

def save_messages(agent, channel_name, messages):
    """Speichert eine Liste von Nachrichten aus einem Kanal in einer Datei.
    messages = list of dicts: {timestamp, username, display_name, text}
    """
    if not messages:
        return None
    memory_dir = os.path.join(BASE, agent, "memory")
    os.makedirs(memory_dir, exist_ok=True)

    ts = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    ch_clean = clean_for_filename(channel_name, 40)
    fname = f"kchat_{ts}_{ch_clean}.txt"
    fpath = os.path.join(memory_dir, fname)

    sep_msg = "\u2500" * 40
    lines = [
        "Quelle: kChat",
        f"Kanal: {channel_name}",
        f"Agent: {agent}",
        f"Importiert: {ts}",
        f"Nachrichten: {len(messages)}",
        "\u2500" * 60,
        "",
    ]
    for m in messages:
        display = m.get("display_name") or ""
        from_str = m["username"] + (f" ({display})" if display else "")
        lines.append(f"Von: {from_str}")
        lines.append(f"Datum: {m['timestamp']}")
        lines.append("")
        lines.append(m.get("text", "").strip())
        lines.append("")
        lines.append(sep_msg)
        lines.append("")

    with open(fpath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    # Optional: Suchindex aktualisieren
    if index_single_file:
        try:
            index_single_file(os.path.dirname(memory_dir), fname)
        except Exception:
            pass

    return fpath


# ── Haupt-Verarbeitung ───────────────────────────────────────────────────────

def process_once(client, state, own_user_id):
    """Einmaliger Poll-Durchlauf. Liest alle erreichbaren Channels, filtert neue
    fremde Nachrichten seit last_check_ms und speichert sie ins Memory.
    Aktualisiert state in-place. Gibt (n_imported, channels_seen) zurueck.
    """
    since_ms = int(state.get("last_check_ms", 0))
    if since_ms <= 0:
        cutoff = datetime.datetime.now() - datetime.timedelta(hours=24)
        since_ms = int(cutoff.timestamp() * 1000)

    try:
        channels = client.get_direct_channels(own_user_id)
    except requests.HTTPError as e:
        status = e.response.status_code if e.response is not None else 0
        if status == 401:
            raise  # Bubble up fuer Pause-Logik
        log(f"  WARN: channels-list Fehler {status}: {e}")
        return 0, 0

    if not isinstance(channels, list):
        log(f"  WARN: Unerwartete Channel-Response: {str(channels)[:200]}")
        return 0, 0

    # Neue Kanaele erkennen
    known = set(state.get("known_channel_ids", []))
    current = {c.get("id") for c in channels if c.get("id")}
    new_channels = current - known
    if new_channels:
        log(f"  {len(new_channels)} neue Kanaele entdeckt")
    state["known_channel_ids"] = sorted(current)

    n_imported = 0
    processed_set = set(state.get("processed_post_ids", []))
    per_agent_count = {}

    for ch in channels:
        ch_id = ch.get("id")
        if not ch_id:
            continue
        ch_name, ch_type = resolve_channel_name(client, ch_id, channel_obj=ch)

        try:
            posts_resp = client.get_posts_since(ch_id, since_ms)
        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else 0
            if status == 401:
                raise
            log(f"  WARN: Posts-Fetch {ch_name} fehlgeschlagen ({status})")
            continue
        except Exception as e:
            log(f"  WARN: Posts-Fetch {ch_name} Exception: {e}")
            continue

        posts = posts_resp.get("posts", {}) if isinstance(posts_resp, dict) else {}
        order = posts_resp.get("order", []) if isinstance(posts_resp, dict) else []

        # Chronologisch sortieren (order ist bereits nach Mattermost-API in der
        # Reihenfolge neueste-zuerst — wir drehen um)
        ordered_ids = list(reversed(order)) if order else sorted(
            posts.keys(),
            key=lambda pid: posts[pid].get("create_at", 0),
        )

        new_msgs_per_agent = {}  # agent -> list[msg_dict]

        for pid in ordered_ids:
            if pid in processed_set:
                continue
            p = posts.get(pid)
            if not isinstance(p, dict):
                continue
            # System-Nachrichten haben 't'-Feld gesetzt
            if p.get("type"):  # "" = user message, sonst system
                processed_set.add(pid)
                continue
            sender_id = p.get("user_id")
            if sender_id and sender_id == own_user_id:
                # Eigene Nachrichten ueberspringen
                processed_set.add(pid)
                continue
            text = p.get("message", "") or ""
            if not text.strip():
                processed_set.add(pid)
                continue

            username, display = resolve_username(client, sender_id)
            create_at = p.get("create_at", 0)
            ts_iso = datetime.datetime.fromtimestamp(create_at / 1000).isoformat() \
                if create_at else datetime.datetime.now().isoformat()

            agent = route_agent(ch_name, text)
            new_msgs_per_agent.setdefault(agent, []).append({
                "timestamp": ts_iso,
                "username": username,
                "display_name": display,
                "text": text,
            })
            processed_set.add(pid)

        # Pro Agent alle neuen Nachrichten dieses Kanals in eine Datei
        for agent, msgs in new_msgs_per_agent.items():
            try:
                fpath = save_messages(agent, ch_name, msgs)
                if fpath:
                    n_imported += len(msgs)
                    per_agent_count[agent] = per_agent_count.get(agent, 0) + len(msgs)
                    log(f"  [{ch_name}] {len(msgs)} Nachricht(en) -> {agent}")
            except Exception as e:
                log(f"  FEHLER beim Speichern {ch_name}->{agent}: {e}")

    # State aktualisieren
    now = datetime.datetime.now()
    state["last_check_ms"] = int(now.timestamp() * 1000)
    state["last_check_iso"] = now.isoformat()
    state["processed_post_ids"] = sorted(processed_set)
    save_state(state)

    if n_imported:
        summary = ", ".join(f"{a}={c}" for a, c in per_agent_count.items())
        log(f"  {n_imported} neue Nachrichten importiert ({summary})")
    return n_imported, len(channels)


# ── Main Loop ────────────────────────────────────────────────────────────────

def main():
    log("kChat Watcher gestartet")

    try:
        creds = load_credentials()
    except Exception as e:
        log(f"FATAL: {e}")
        sys.exit(1)

    log(f"API: {creds['api_base']}")
    client = KChatClient(creds["api_base"], creds["token"])
    state = load_state()
    log(f"State: last_check={state.get('last_check_iso','?')} "
        f"known_channels={len(state.get('known_channel_ids', []))}")

    # Eigene User ID ermitteln — wenn nicht in config, dann ueber /users/me holen
    own_user_id = creds.get("user_id") or ""
    if not own_user_id:
        try:
            me = client.get_me()
            own_user_id = me.get("id", "")
            log(f"Eigene User ID: {own_user_id} ({me.get('username','?')})")
        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else 0
            log(f"WARN: /users/me HTTP {status} — Token moeglicherweise ungueltig")
            if status == 401:
                log("  Token ist abgelaufen oder ungueltig. Watcher pausiert 5 Minuten und versucht erneut.")
                log("  Bitte einen frischen Bot-Token in models.json['kchat']['auth_token'] eintragen.")
        except Exception as e:
            log(f"WARN: /users/me Fehler: {e}")

    interval = creds["poll_interval_seconds"]
    while True:
        try:
            if not own_user_id:
                # Nochmal versuchen
                try:
                    me = client.get_me()
                    own_user_id = me.get("id", "")
                    if own_user_id:
                        log(f"Eigene User ID jetzt verfuegbar: {own_user_id}")
                except requests.HTTPError as e:
                    status = e.response.status_code if e.response is not None else 0
                    if status == 401:
                        log("Token weiterhin ungueltig (401). Warte 5 Minuten.")
                        time.sleep(300)
                        continue
                    log(f"WARN: /users/me {status}: {e}")
                    time.sleep(interval)
                    continue

            n_imp, n_ch = process_once(client, state, own_user_id)
            if n_imp == 0:
                log(f"Kein Update ({n_ch} Kanaele gescannt)")

        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else 0
            if status == 401:
                log("Token abgelaufen oder ungueltig (401). Pausiere 5 Minuten.")
                time.sleep(300)
                continue
            log(f"HTTP-Fehler {status}: {e}")
            time.sleep(interval)
            continue
        except KeyboardInterrupt:
            log("kChat Watcher beendet (Ctrl+C).")
            return
        except Exception as e:
            log(f"Fehler im Poll-Loop: {e}")
            log(traceback.format_exc())
            time.sleep(interval)
            continue

        time.sleep(interval)


if __name__ == "__main__":
    main()
