#!/usr/bin/env python3
"""
Patch: Slack API Outbound + Canva REST API Integration

1. SLACK_API_V1  — Echter Slack-API-Client (chat.postMessage, conversations.list,
                   conversations.history, users.list) statt Clipboard-Hack
2. CANVA_API_V1  — Canva Connect API Client (designs suchen/erstellen/exportieren)
3. Neue Routen: /api/slack, /api/canva
4. Tool-Definitionen fuer Anthropic tool_use (Agenten koennen Slack/Canva aufrufen)

Alle Stellen NACH der duplizierten Zone (>1358). Idempotent.
"""
import os, sys

WS = os.path.expanduser("~/AssistantDev/src/web_server.py")

def apply(src, old, new, marker, desc):
    if marker in src:
        print(f"  [skip] {desc}")
        return src, False
    c = src.count(old)
    if c != 1:
        print(f"  [FAIL] {desc}: {c} Vorkommen (erwarte 1)")
        sys.exit(2)
    print(f"  [OK]   {desc}")
    return src.replace(old, new, 1), True


# ═══════════════════════════════════════════════════════════════════════════
# Patch 1: Slack + Canva API-Funktionen VOR dem Calendar-Block einfuegen
# ═══════════════════════════════════════════════════════════════════════════

ANCHOR_1 = '# ─── CALENDAR INTEGRATION (CALENDAR_INTEGRATION_V1)'

NEW_1 = '''# ─── SLACK API INTEGRATION (SLACK_API_V1) ──────────────────────────────────────
# Echter Slack-API-Client via Bot-Token. Ersetzt den Clipboard-Paste-Hack fuer
# Outbound und fuegt Lese-Faehigkeiten hinzu (Channels, History, Users).
# Docs: https://docs.slack.dev/reference/methods/chat.postMessage/

def _get_slack_config():
    """Laedt Slack-Config aus models.json. Gibt dict oder None zurueck."""
    config = load_models()
    sc = config.get('slack')
    if not sc or not sc.get('bot_token'):
        return None
    return sc

def _slack_api(method, params=None, json_body=None):
    """Generischer Slack Web API Aufruf. Returns (ok, data_dict)."""
    sc = _get_slack_config()
    if not sc:
        return False, {'error': 'Kein Slack bot_token in models.json konfiguriert'}
    token = sc['bot_token']
    url = f"https://slack.com/api/{method}"
    headers = {'Authorization': f'Bearer {token}'}
    try:
        if json_body is not None:
            headers['Content-Type'] = 'application/json'
            r = requests.post(url, headers=headers, json=json_body, timeout=15)
        elif params:
            r = requests.get(url, headers=headers, params=params, timeout=15)
        else:
            r = requests.get(url, headers=headers, timeout=15)
        data = r.json()
        return data.get('ok', False), data
    except Exception as e:
        return False, {'error': str(e)}

def slack_send_message(channel, text, thread_ts=None):
    """Sendet eine Nachricht an einen Slack-Channel oder User.
    channel: '#channel-name' oder Channel-ID oder User-ID
    Returns: (ok, response_dict)
    """
    body = {'channel': channel.lstrip('#'), 'text': text}
    if thread_ts:
        body['thread_ts'] = thread_ts
    return _slack_api('chat.postMessage', json_body=body)

def slack_list_channels(limit=100):
    """Listet alle Channels auf die der Bot Zugriff hat."""
    return _slack_api('conversations.list', params={
        'types': 'public_channel,private_channel',
        'limit': limit, 'exclude_archived': True,
    })

def slack_list_users(limit=200):
    """Listet alle User im Workspace."""
    return _slack_api('users.list', params={'limit': limit})

def slack_channel_history(channel_id, limit=20):
    """Liest die letzten N Nachrichten aus einem Channel."""
    return _slack_api('conversations.history', params={
        'channel': channel_id, 'limit': limit,
    })

def slack_find_channel_id(name):
    """Sucht Channel-ID anhand des Namens."""
    ok, data = slack_list_channels(limit=500)
    if not ok:
        return None
    for ch in data.get('channels', []):
        if ch.get('name') == name.lstrip('#') or ch.get('name_normalized') == name.lstrip('#'):
            return ch['id']
    return None

def slack_find_user_id(name):
    """Sucht User-ID anhand des Display-Namens oder Real-Namens."""
    ok, data = slack_list_users(limit=500)
    if not ok:
        return None
    name_low = name.lower()
    for u in data.get('members', []):
        rn = (u.get('real_name') or '').lower()
        dn = (u.get('profile', {}).get('display_name') or '').lower()
        un = (u.get('name') or '').lower()
        if name_low in (rn, dn, un) or name_low in rn:
            return u['id']
    return None


# ─── CANVA API INTEGRATION (CANVA_API_V1) ─────────────────────────────────────
# Canva Connect REST API fuer Design-Operationen.
# Docs: https://www.canva.dev/docs/connect/

def _get_canva_config():
    """Laedt Canva-Config aus models.json. Gibt dict oder None zurueck."""
    config = load_models()
    cc = config.get('canva')
    if not cc or not cc.get('access_token'):
        return None
    return cc

def _canva_api(method, path, json_body=None, params=None):
    """Generischer Canva Connect API Aufruf."""
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
        return False, {'error': str(e)}

def canva_list_designs(query=None, count=20):
    """Sucht Designs im Canva-Account."""
    params = {'count': count}
    if query:
        params['query'] = query
    return _canva_api('GET', '/designs', params=params)

def canva_get_design(design_id):
    """Gibt Details zu einem Design zurueck."""
    return _canva_api('GET', f'/designs/{design_id}')

def canva_create_design(title, design_type='doc', width=None, height=None):
    """Erstellt ein neues leeres Canva-Design."""
    body = {'title': title}
    if design_type:
        body['design_type'] = {'type': design_type}
    if width and height:
        body['design_type'] = {'type': 'custom', 'width': width, 'height': height}
    return _canva_api('POST', '/designs', json_body=body)

def canva_export_design(design_id, format_type='pdf'):
    """Exportiert ein Design als PDF/PNG/JPG."""
    body = {'design_id': design_id, 'format': {'type': format_type}}
    return _canva_api('POST', '/exports', json_body=body)

def canva_list_folders(count=50):
    """Listet Ordner im Canva-Account."""
    return _canva_api('GET', '/folders', params={'count': count})


''' + ANCHOR_1


# ═══════════════════════════════════════════════════════════════════════════
# Patch 2: Neue Routen /api/slack und /api/canva
# ═══════════════════════════════════════════════════════════════════════════

ANCHOR_2 = "@app.route('/search_memory', methods=['POST'])"

NEW_2 = """# SLACK_API_V1: Slack-API Route
@app.route('/api/slack', methods=['POST'])
def api_slack():
    \"\"\"Slack-API Proxy: send, channels, history, users.\"\"\"
    data = request.json or {}
    action = data.get('action', 'send')

    if action == 'send':
        channel = data.get('channel', '')
        text = data.get('text', data.get('message', ''))
        if not channel or not text:
            return jsonify({'error': 'channel und text/message erforderlich'})
        # Channel-Name → ID aufloesen wenn noetig
        if channel.startswith('#'):
            ch_id = slack_find_channel_id(channel)
            if ch_id:
                channel = ch_id
        ok, resp = slack_send_message(channel, text, thread_ts=data.get('thread_ts'))
        return jsonify({'ok': ok, 'data': resp})

    elif action == 'channels':
        ok, resp = slack_list_channels(limit=data.get('limit', 100))
        channels = [{'id': c['id'], 'name': c['name'], 'topic': c.get('topic', {}).get('value', '')}
                    for c in resp.get('channels', [])] if ok else []
        return jsonify({'ok': ok, 'channels': channels})

    elif action == 'history':
        ch = data.get('channel_id', data.get('channel', ''))
        if not ch:
            return jsonify({'error': 'channel_id erforderlich'})
        ok, resp = slack_channel_history(ch, limit=data.get('limit', 20))
        return jsonify({'ok': ok, 'messages': resp.get('messages', []) if ok else [], 'error': resp.get('error')})

    elif action == 'users':
        ok, resp = slack_list_users(limit=data.get('limit', 200))
        users = [{'id': u['id'], 'name': u.get('real_name', u.get('name', '')),
                  'display': u.get('profile', {}).get('display_name', '')}
                 for u in resp.get('members', []) if not u.get('is_bot') and not u.get('deleted')] if ok else []
        return jsonify({'ok': ok, 'users': users})

    return jsonify({'error': f'Unbekannte action: {action}'})


# CANVA_API_V1: Canva-API Route
@app.route('/api/canva', methods=['POST'])
def api_canva():
    \"\"\"Canva Connect API Proxy: designs, create, export, folders.\"\"\"
    data = request.json or {}
    action = data.get('action', 'list')

    if action == 'list' or action == 'search':
        ok, resp = canva_list_designs(query=data.get('query'), count=data.get('count', 20))
        return jsonify({'ok': ok, 'data': resp})

    elif action == 'get':
        did = data.get('design_id', '')
        if not did:
            return jsonify({'error': 'design_id erforderlich'})
        ok, resp = canva_get_design(did)
        return jsonify({'ok': ok, 'data': resp})

    elif action == 'create':
        title = data.get('title', 'Neues Design')
        ok, resp = canva_create_design(
            title, design_type=data.get('design_type', 'doc'),
            width=data.get('width'), height=data.get('height'),
        )
        return jsonify({'ok': ok, 'data': resp})

    elif action == 'export':
        did = data.get('design_id', '')
        fmt = data.get('format', 'pdf')
        if not did:
            return jsonify({'error': 'design_id erforderlich'})
        ok, resp = canva_export_design(did, format_type=fmt)
        return jsonify({'ok': ok, 'data': resp})

    elif action == 'folders':
        ok, resp = canva_list_folders(count=data.get('count', 50))
        return jsonify({'ok': ok, 'data': resp})

    return jsonify({'error': f'Unbekannte action: {action}'})


@app.route('/search_memory', methods=['POST'])"""


# ═══════════════════════════════════════════════════════════════════════════
# Patch 3: send_slack_draft upgraden — nutze API wenn Token vorhanden,
# sonst Fallback auf alten Clipboard-Hack
# ═══════════════════════════════════════════════════════════════════════════

OLD_SLACK = '''def send_slack_draft(spec):
    """Opens Slack Desktop and pastes message text via clipboard. Never auto-sends."""
    import subprocess

    channel = spec.get('channel', '')
    to = spec.get('to', '')
    message = spec.get('message', '')
    if not message:
        raise Exception("Slack: Kein Nachrichtentext angegeben")
    if not channel and not to:
        raise Exception("Slack: Weder 'channel' noch 'to' angegeben")

    target = channel or to

    # Copy message to clipboard
    subprocess.run(['pbcopy'], input=message.encode('utf-8'), timeout=5)

    # Open Slack Desktop
    subprocess.run(['open', '-a', 'Slack'], capture_output=True, text=True, timeout=10)

    # Wait for Slack to activate, then paste via Cmd+V
    script = \'\'\'
delay 1.5
tell application "System Events"
    tell process "Slack"
        set frontmost to true
        delay 0.3
        keystroke "v" using command down
    end tell
end tell\'\'\'
    result = subprocess.run(['osascript', '-e', script],
                          capture_output=True, text=True, timeout=10)
    if result.returncode != 0:
        # Paste failed but Slack is open with text in clipboard
        return target, True  # clipboard_only=True
    return target, False  # clipboard_only=False'''

NEW_SLACK = '''def send_slack_draft(spec):
    """SLACK_API_V1: Sendet Slack-Nachricht via API wenn Bot-Token vorhanden,
    sonst Fallback auf Desktop-App + Clipboard.
    """
    import subprocess

    channel = spec.get('channel', '')
    to = spec.get('to', '')
    message = spec.get('message', '')
    if not message:
        raise Exception("Slack: Kein Nachrichtentext angegeben")
    if not channel and not to:
        raise Exception("Slack: Weder 'channel' noch 'to' angegeben")

    target = channel or to

    # Versuch 1: Slack API (wenn Bot-Token konfiguriert)
    sc = _get_slack_config() if '_get_slack_config' in dir() or True else None
    try:
        sc = _get_slack_config()
    except Exception:
        sc = None
    if sc:
        # Channel/User-ID aufloesen
        resolved = target
        if target.startswith('#'):
            ch_id = slack_find_channel_id(target)
            if ch_id:
                resolved = ch_id
        elif not target.startswith(('C', 'U', 'D', 'G')):
            # Kein Channel-Prefix → vermutlich Personenname
            uid = slack_find_user_id(target)
            if uid:
                # DM Channel oeffnen
                ok, dm_data = _slack_api('conversations.open', json_body={'users': uid})
                if ok and dm_data.get('channel', {}).get('id'):
                    resolved = dm_data['channel']['id']
        ok, resp = slack_send_message(resolved, message)
        if ok:
            print(f"[SLACK API] Nachricht gesendet an {target}", flush=True)
            return target, False  # clipboard_only=False, erfolgreich via API
        else:
            print(f"[SLACK API] Fehler: {resp.get('error', '?')} — Fallback auf Desktop", flush=True)

    # Fallback: Desktop-App + Clipboard (alter Mechanismus)
    subprocess.run(['pbcopy'], input=message.encode('utf-8'), timeout=5)
    subprocess.run(['open', '-a', 'Slack'], capture_output=True, text=True, timeout=10)
    script = \'\'\'
delay 1.5
tell application "System Events"
    tell process "Slack"
        set frontmost to true
        delay 0.3
        keystroke "v" using command down
    end tell
end tell\'\'\'
    result = subprocess.run(['osascript', '-e', script],
                          capture_output=True, text=True, timeout=10)
    if result.returncode != 0:
        return target, True
    return target, False'''


def main():
    if not os.path.exists(WS):
        print(f"FEHLER: {WS} nicht gefunden")
        sys.exit(1)
    src = open(WS).read()
    orig = len(src)
    changed = False

    print("Slack + Canva Integration Patches:")
    src, a = apply(src, ANCHOR_1, NEW_1, 'SLACK_API_V1', 'Patch 1 — Slack+Canva API-Funktionen')
    changed = changed or a
    src, a = apply(src, ANCHOR_2, NEW_2, '/api/slack', 'Patch 2 — /api/slack + /api/canva Routen')
    changed = changed or a
    src, a = apply(src, OLD_SLACK, NEW_SLACK, 'SLACK_API_V1: Sendet', 'Patch 3 — send_slack_draft Upgrade')
    changed = changed or a

    if not changed:
        print("Alle Patches schon angewendet.")
        return
    open(WS, 'w').write(src)
    print(f"OK: {orig} -> {len(src)} bytes")


if __name__ == '__main__':
    main()
