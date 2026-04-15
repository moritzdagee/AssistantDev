#!/usr/bin/env python3
"""Patch: Automatischer Canva Token-Refresh wenn Access Token abgelaufen (HTTP 401)."""
import os, sys
WS = os.path.expanduser("~/AssistantDev/src/web_server.py")
src = open(WS).read()
MARKER = 'CANVA_TOKEN_REFRESH'
if MARKER in src:
    print("Schon gepatcht.")
    sys.exit(0)

OLD = """def _canva_api(method, path, json_body=None, params=None):
    \"\"\"Generischer Canva Connect API Aufruf.\"\"\"
    cc = _get_canva_config()
    if not cc:
        return False, {'error': 'Kein Canva access_token in models.json konfiguriert'}
    token = cc['access_token']
    base = cc.get('api_base', 'https://api.canva.com/rest/v1')
    url = f"{base}{path}"
    headers = {'Authorization': f'Bearer {token}'}
    try:
        if method == 'GET':
            r = requests.get(url, headers=headers, params=params or {}, timeout=30)
        elif method == 'POST':
            headers['Content-Type'] = 'application/json'
            r = requests.post(url, headers=headers, json=json_body or {}, timeout=30)
        else:
            return False, {'error': f'Unbekannte Methode: {method}'}
        data = r.json() if r.content else {}
        if r.status_code >= 400:
            return False, {'error': data.get('message', f'HTTP {r.status_code}'), 'status': r.status_code}
        return True, data
    except Exception as e:
        return False, {'error': str(e)}"""

NEW = """def _canva_refresh_token():
    \"\"\"CANVA_TOKEN_REFRESH: Erneuert den Access Token via Refresh Token.\"\"\"
    import base64 as _cb64
    config = load_models()
    cc = config.get('canva', {})
    rt = cc.get('refresh_token', '')
    cid = cc.get('client_id', '')
    csec = cc.get('client_secret', '')
    if not rt or not cid or not csec:
        return False
    creds = _cb64.b64encode(f"{cid}:{csec}".encode()).decode()
    try:
        r = requests.post(
            'https://api.canva.com/rest/v1/oauth/token',
            headers={'Authorization': f'Basic {creds}', 'Content-Type': 'application/x-www-form-urlencoded'},
            data={'grant_type': 'refresh_token', 'refresh_token': rt},
            timeout=15,
        )
        if r.status_code != 200:
            print(f"[CANVA] Token-Refresh fehlgeschlagen: HTTP {r.status_code}", flush=True)
            return False
        td = r.json()
        # In models.json speichern
        config['canva']['access_token'] = td['access_token']
        if td.get('refresh_token'):
            config['canva']['refresh_token'] = td['refresh_token']
        config['canva']['expires_in'] = td.get('expires_in', 0)
        config['canva']['scope'] = td.get('scope', cc.get('scope', ''))
        with open(MODELS_FILE, 'w') as f:
            json.dump(config, f, indent=4)
        print(f"[CANVA] Token erfolgreich erneuert (expires_in={td.get('expires_in')}s)", flush=True)
        return True
    except Exception as e:
        print(f"[CANVA] Token-Refresh Exception: {e}", flush=True)
        return False


def _canva_api(method, path, json_body=None, params=None):
    \"\"\"Generischer Canva Connect API Aufruf mit automatischem Token-Refresh.\"\"\"
    cc = _get_canva_config()
    if not cc:
        return False, {'error': 'Kein Canva access_token in models.json konfiguriert'}
    token = cc['access_token']
    base = cc.get('api_base', 'https://api.canva.com/rest/v1')
    url = f"{base}{path}"
    headers = {'Authorization': f'Bearer {token}'}
    try:
        if method == 'GET':
            r = requests.get(url, headers=headers, params=params or {}, timeout=30)
        elif method == 'POST':
            headers['Content-Type'] = 'application/json'
            r = requests.post(url, headers=headers, json=json_body or {}, timeout=30)
        else:
            return False, {'error': f'Unbekannte Methode: {method}'}
        # CANVA_TOKEN_REFRESH: Bei 401 automatisch Token erneuern und Retry
        if r.status_code == 401:
            print("[CANVA] 401 — versuche Token-Refresh...", flush=True)
            if _canva_refresh_token():
                cc2 = _get_canva_config()
                headers['Authorization'] = f'Bearer {cc2["access_token"]}'
                if method == 'GET':
                    r = requests.get(url, headers=headers, params=params or {}, timeout=30)
                else:
                    r = requests.post(url, headers=headers, json=json_body or {}, timeout=30)
        data = r.json() if r.content else {}
        if r.status_code >= 400:
            return False, {'error': data.get('message', f'HTTP {r.status_code}'), 'status': r.status_code}
        return True, data
    except Exception as e:
        return False, {'error': str(e)}"""

if src.count(OLD) != 1:
    print(f"FEHLER: {src.count(OLD)} Vorkommen")
    sys.exit(2)
src = src.replace(OLD, NEW, 1)
open(WS, 'w').write(src)
print("OK: Token-Refresh eingefuegt")
