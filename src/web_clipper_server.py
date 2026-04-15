from flask import Flask, request, jsonify
import os
import re
import json
import base64
import datetime
try:
    import setproctitle
    setproctitle.setproctitle("AssistantDev WebClipper")
except ImportError:
    pass

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB for screenshots

BASE = os.path.expanduser("~/Library/Mobile Documents/com~apple~CloudDocs/Downloads shared/claude_datalake")
AGENTS_DIR = os.path.join(BASE, "config/agents")
GLOBAL_WEBCLIPS = os.path.expanduser("~/Library/Mobile Documents/com~apple~CloudDocs/Downloads shared/webclips")


def get_parent_agents():
    """Return only parent agents (no sub-agents with _ in name)."""
    try:
        agents = []
        for f in sorted(os.listdir(AGENTS_DIR)):
            if f.endswith('.txt'):
                name = f.replace('.txt', '')
                if '_' not in name:
                    agents.append(name)
        return agents
    except Exception:
        return []


def sanitize_filename(name, max_len=60):
    """Sanitize a string for use as filename."""
    name = re.sub(r'[^a-zA-Z0-9 _-]', '', str(name))
    name = re.sub(r'\s+', '_', name).strip('_')
    name = re.sub(r'_+', '_', name)
    return name[:max_len].strip('_') or 'untitled'


@app.route('/agents', methods=['GET'])
def list_agents():
    try:
        agents = get_parent_agents()
        print(f"[Clipper] /agents -> {agents}")
        return jsonify({'agents': agents})
    except Exception as e:
        print(f"[Clipper] /agents ERROR: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/save', methods=['POST'])
def save():
    try:
        data = request.json
        agent = data.get('agent', 'signicat')

        print(f"[Clipper] /save request: agent={agent}")

        memory_dir = os.path.join(BASE, agent, 'memory')
        os.makedirs(memory_dir, exist_ok=True)
        os.makedirs(GLOBAL_WEBCLIPS, exist_ok=True)

        # ── Detect format: new (extracted_data) vs old (content string) ──
        if 'extracted_data' in data or 'full_text' in data:
            return _save_new_format(data, agent, memory_dir)
        else:
            return _save_legacy_format(data, agent, memory_dir)

    except Exception as e:
        print(f"[Clipper] /save ERROR: {e}")
        import traceback; traceback.print_exc()
        return jsonify({'error': str(e)}), 500


def _save_legacy_format(data, agent, memory_dir):
    """Save old-style text clips (backward compat)."""
    content = data.get('content', '')
    filename = data.get('filename', '')
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    if not content:
        return jsonify({'error': 'Kein Inhalt'}), 400
    if not filename:
        filename = f"web_{timestamp}.txt"

    # Save to agent memory
    agent_path = os.path.join(memory_dir, filename)
    with open(agent_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"[Clipper] Legacy save: {agent_path}")

    # Save to global webclips
    global_path = os.path.join(GLOBAL_WEBCLIPS, f"{agent}_{filename}")
    with open(global_path, 'w', encoding='utf-8') as f:
        f.write(content)

    return jsonify({
        'success': True,
        'saved_to': agent_path,
        'saved_to_agent': f"{agent}/memory/{filename}",
        'saved_to_global': f"webclips/{agent}_{filename}",
    })


def _save_new_format(data, agent, memory_dir):
    """Save new structured JSON clips with optional PNG screenshot."""
    filename = data.get('filename', '')
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    if not filename:
        title_safe = sanitize_filename(data.get('title', 'page'))
        filename = f"web_{title_safe}_{datetime.date.today().isoformat()}.json"
    if not filename.endswith('.json'):
        filename = os.path.splitext(filename)[0] + '.json'

    # Build JSON clip data (without screenshot — too large for search)
    clip_data = {
        'url': data.get('url', ''),
        'title': data.get('title', ''),
        'timestamp': data.get('timestamp', timestamp),
        'extracted_data': data.get('extracted_data', {}),
        'full_text': data.get('full_text', ''),
    }

    # ── SAVE JSON to agent memory ──
    json_path = os.path.join(memory_dir, filename)
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(clip_data, f, ensure_ascii=False, indent=2)
    print(f"[Clipper] JSON saved: {json_path}")

    # ── SAVE PNG to agent memory (if screenshot provided) ──
    png_filename = os.path.splitext(filename)[0] + '.png'
    screenshot_b64 = data.get('screenshot_png_base64')
    png_saved = False
    if screenshot_b64:
        png_path = os.path.join(memory_dir, png_filename)
        with open(png_path, 'wb') as f:
            f.write(base64.b64decode(screenshot_b64))
        print(f"[Clipper] PNG saved: {png_path} ({os.path.getsize(png_path)} bytes)")
        png_saved = True

    # ── DUAL SAVE to global webclips ──
    global_json = os.path.join(GLOBAL_WEBCLIPS, f"{agent}_{filename}")
    with open(global_json, 'w', encoding='utf-8') as f:
        json.dump(clip_data, f, ensure_ascii=False, indent=2)

    if screenshot_b64:
        global_png = os.path.join(GLOBAL_WEBCLIPS, f"{agent}_{png_filename}")
        with open(global_png, 'wb') as f:
            f.write(base64.b64decode(screenshot_b64))

    return jsonify({
        'success': True,
        'saved_to': json_path,
        'saved_to_agent': f"{agent}/memory/{filename}",
        'saved_to_global': f"webclips/{agent}_{filename}",
        'screenshot_saved': png_saved,
    })


# ─── WHATSAPP SYNC ───────────────────────────────────────────────────────────

@app.route('/whatsapp/sync', methods=['POST', 'OPTIONS'])
def whatsapp_sync():
    if request.method == 'OPTIONS':
        return '', 204

    try:
        data = request.json
        agent = data.get('agent', 'privat')
        contact = data.get('contact', 'Unbekannt')
        messages = data.get('messages', [])
        last_known = data.get('last_known_timestamp', '')

        # Validate agent
        valid_agents = get_parent_agents()
        if agent not in valid_agents:
            return jsonify({'status': 'error', 'message': f'Unbekannter Agent: {agent}'}), 400

        whatsapp_dir = os.path.join(BASE, agent, 'memory', 'whatsapp')
        os.makedirs(whatsapp_dir, exist_ok=True)

        if not messages:
            return jsonify({'status': 'success', 'appended': 0, 'file': None})

        # Filter only new messages (after last_known_timestamp)
        new_msgs = []
        for m in messages:
            if last_known and m.get('timestamp', '') <= last_known:
                continue
            new_msgs.append(m)

        if not new_msgs:
            return jsonify({'status': 'success', 'appended': 0, 'file': None})

        # Build filename from today's date
        today = datetime.date.today().isoformat()
        safe_contact = sanitize_filename(contact)
        fname = f'whatsapp_chat_{safe_contact}_{today}.txt'
        fpath = os.path.join(whatsapp_dir, fname)

        # Append to existing file or create new
        if os.path.exists(fpath):
            with open(fpath, 'a', encoding='utf-8') as f:
                for m in new_msgs:
                    ts = m.get('timestamp', '')[:16].replace('T', ' ')
                    sender = 'Ich' if m.get('sender') in ('Me', 'me', 'Ich') else m.get('sender', '?')
                    text = '[Medien]' if m.get('is_media') else m.get('text', '')
                    f.write(f'[{ts}] {sender}: {text}\n')
        else:
            with open(fpath, 'w', encoding='utf-8') as f:
                f.write(f'=== WhatsApp Chat: {contact} ===\n')
                f.write(f'Kontakt: {contact}\n')
                f.write(f'Datum: {today}\n')
                f.write(f'(Live-Sync via Chrome Extension)\n\n')
                for m in new_msgs:
                    ts = m.get('timestamp', '')[:16].replace('T', ' ')
                    sender = 'Ich' if m.get('sender') in ('Me', 'me', 'Ich') else m.get('sender', '?')
                    text = '[Medien]' if m.get('is_media') else m.get('text', '')
                    f.write(f'[{ts}] {sender}: {text}\n')

        # Update metadata
        meta_path = os.path.join(whatsapp_dir, 'whatsapp_metadata.json')
        meta = {'imported_chats': [], 'last_sync': None}
        if os.path.exists(meta_path):
            try:
                with open(meta_path, 'r') as f:
                    meta = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

        meta['last_sync'] = datetime.datetime.now().isoformat()
        # Update or add contact entry
        existing = {c['contact']: c for c in meta.get('imported_chats', [])}
        entry = existing.get(contact, {'contact': contact, 'message_count': 0})
        entry['message_count'] = entry.get('message_count', 0) + len(new_msgs)
        entry['last_sync'] = meta['last_sync']
        existing[contact] = entry
        meta['imported_chats'] = list(existing.values())

        with open(meta_path, 'w') as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        # Mirror to Downloads shared/whatsapp/ for global access
        shared_wa_dir = os.path.join(os.path.dirname(BASE), 'whatsapp')
        os.makedirs(shared_wa_dir, exist_ok=True)
        shared_path = os.path.join(shared_wa_dir, f'{agent}_{fname}')
        try:
            import shutil
            shutil.copy2(fpath, shared_path)
        except Exception as me:
            print(f"[WA-Sync] Mirror error: {me}")

        print(f"[WA-Sync] {len(new_msgs)} Nachrichten von {contact} -> {fname}")

        return jsonify({
            'status': 'success',
            'appended': len(new_msgs),
            'file': fpath,
        })

    except Exception as e:
        print(f"[WA-Sync] ERROR: {e}")
        import traceback; traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.after_request
def add_cors(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'POST, GET, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response


@app.route('/save', methods=['OPTIONS'])
def save_options():
    return '', 204


@app.route('/agents', methods=['OPTIONS'])
def agents_options():
    return '', 204


if __name__ == '__main__':
    print("[Clipper] Memory Save Server laeuft auf http://localhost:8081")
    print(f"[Clipper] BASE: {BASE}")
    print(f"[Clipper] GLOBAL_WEBCLIPS: {GLOBAL_WEBCLIPS}")
    app.run(port=8081, debug=False)
