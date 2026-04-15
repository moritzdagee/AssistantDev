#!/usr/bin/env python3
"""
Canva OAuth2 Setup — Einmaliges Token-Abruf-Skript.

Oeffnet den Browser fuer Canva-Autorisierung, faengt den Callback lokal ab
und tauscht den Auth-Code gegen Access+Refresh Token ein.
Speichert die Tokens direkt in models.json.

Aufruf: python3 ~/AssistantDev/scripts/canva_oauth_setup.py
"""

import os
import sys
import json
import hashlib
import secrets
import base64
import webbrowser
import urllib.parse
import http.server
import threading

try:
    import requests
except ImportError:
    print("pip3 install requests")
    sys.exit(1)

# ── Konfiguration ────────────────────────────────────────────────────────────

CLIENT_ID = "OC-AZ2G7Oc4afr0"
CLIENT_SECRET = "cnvca7tL0kCuC13dmUA3eqcOgnptcJTvXlO63EDplV9T5b8E8ea2a719"

REDIRECT_PORT = 8765
REDIRECT_URI = f"http://127.0.0.1:{REDIRECT_PORT}/callback"

# Alle relevanten Scopes anfordern
SCOPES = " ".join([
    "design:content:read",
    "design:content:write",
    "design:meta:read",
    "design:permission:read",
    "asset:read",
    "asset:write",
    "folder:read",
    "folder:write",
    "brandtemplate:meta:read",
    "brandtemplate:content:read",
    "profile:read",
    "comment:read",
    "comment:write",
])

MODELS_FILE = os.path.expanduser(
    "~/Library/Mobile Documents/com~apple~CloudDocs/Downloads shared/"
    "claude_datalake/config/models.json"
)

# ── PKCE ─────────────────────────────────────────────────────────────────────

def generate_pkce():
    code_verifier = secrets.token_urlsafe(64)[:128]
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return code_verifier, code_challenge


# ── Lokaler Callback-Server ──────────────────────────────────────────────────

auth_code = None
auth_state = None
server_done = threading.Event()


class CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code, auth_state
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if parsed.path == "/callback" and "code" in params:
            auth_code = params["code"][0]
            auth_state = params.get("state", [""])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"""
            <html><body style="font-family:sans-serif;text-align:center;padding:60px;background:#1a1a1a;color:#e0e0e0;">
            <h1 style="color:#4caf50;">&#10004; Canva Autorisierung erfolgreich!</h1>
            <p>Du kannst dieses Fenster schliessen. Token wird gespeichert...</p>
            </body></html>
            """)
            server_done.set()
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Fehler: Kein Auth-Code erhalten.")
            if "error" in params:
                print(f"  OAuth-Fehler: {params.get('error_description', params['error'])}")
            server_done.set()

    def log_message(self, format, *args):
        pass  # Kein Log-Spam


# ── Token-Exchange ───────────────────────────────────────────────────────────

def exchange_code(code, code_verifier):
    """Tauscht Auth-Code gegen Access+Refresh Token."""
    creds = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    r = requests.post(
        "https://api.canva.com/rest/v1/oauth/token",
        headers={
            "Authorization": f"Basic {creds}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "authorization_code",
            "code": code,
            "code_verifier": code_verifier,
            "redirect_uri": REDIRECT_URI,
        },
        timeout=30,
    )
    if r.status_code != 200:
        print(f"FEHLER: Token-Exchange HTTP {r.status_code}")
        print(r.text[:500])
        return None
    return r.json()


def save_tokens(token_data):
    """Speichert Tokens in models.json."""
    with open(MODELS_FILE) as f:
        config = json.load(f)

    config["canva"] = {
        "access_token": token_data["access_token"],
        "refresh_token": token_data.get("refresh_token", ""),
        "token_type": token_data.get("token_type", "Bearer"),
        "expires_in": token_data.get("expires_in", 0),
        "scope": token_data.get("scope", ""),
        "api_base": "https://api.canva.com/rest/v1",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }

    with open(MODELS_FILE, "w") as f:
        json.dump(config, f, indent=4)
    print(f"  Tokens gespeichert in models.json")


# ── Haupt-Flow ───────────────────────────────────────────────────────────────

def main():
    print()
    print("  CANVA OAUTH2 SETUP")
    print("  " + "─" * 40)
    print()

    # 1. PKCE generieren
    code_verifier, code_challenge = generate_pkce()
    state = secrets.token_urlsafe(32)

    # 2. Auth-URL bauen
    auth_url = (
        "https://www.canva.com/api/oauth/authorize?"
        + urllib.parse.urlencode({
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "scope": SCOPES,
            "response_type": "code",
            "client_id": CLIENT_ID,
            "state": state,
            "redirect_uri": REDIRECT_URI,
        })
    )

    # 3. Lokalen Callback-Server starten
    server = http.server.HTTPServer(("localhost", REDIRECT_PORT), CallbackHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    print(f"  Callback-Server laeuft auf localhost:{REDIRECT_PORT}")

    # 4. Browser oeffnen
    print(f"  Oeffne Browser fuer Canva-Login...")
    print()
    webbrowser.open(auth_url)
    print(f"  Warte auf Autorisierung...")
    print(f"  (Falls der Browser sich nicht oeffnet, kopiere diese URL:)")
    print(f"  {auth_url[:120]}...")
    print()

    # 5. Auf Callback warten (max 5 Minuten)
    if not server_done.wait(timeout=300):
        print("FEHLER: Timeout — keine Antwort innerhalb von 5 Minuten")
        server.shutdown()
        sys.exit(1)

    server.shutdown()

    if not auth_code:
        print("FEHLER: Kein Auth-Code erhalten.")
        sys.exit(1)

    print(f"  Auth-Code erhalten! Tausche gegen Token...")

    # 6. Token Exchange
    token_data = exchange_code(auth_code, code_verifier)
    if not token_data:
        sys.exit(1)

    print(f"  Access Token: {token_data['access_token'][:20]}...")
    print(f"  Refresh Token: {token_data.get('refresh_token', 'N/A')[:20]}...")
    print(f"  Scopes: {token_data.get('scope', '?')}")
    print(f"  Expires in: {token_data.get('expires_in', '?')} Sekunden")

    # 7. In models.json speichern
    save_tokens(token_data)

    print()
    print("  ✅ Canva-Integration ist jetzt aktiv!")
    print("  Teste mit: curl -s -X POST http://localhost:8080/api/canva \\")
    print("    -H 'Content-Type: application/json' -d '{\"action\":\"list\"}'")
    print()


if __name__ == "__main__":
    main()
