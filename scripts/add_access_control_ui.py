#!/usr/bin/env python3
"""Patch: Access Control Web UI.
- 3 neue Routes: GET /admin/access-control (HTML), GET/POST /api/access-control (JSON)
- Admin-Button im Header
"""
import sys

path = '/Users/moritzcremer/AssistantDev/src/web_server.py'
with open(path, 'r') as f:
    content = f.read()

def must_replace(label, old, new):
    global content
    if old not in content:
        print(f"FEHLER bei {label}: Suchstring nicht gefunden!", file=sys.stderr)
        sys.exit(1)
    content = content.replace(old, new, 1)
    print(f"OK: {label}")

# ═══════════════════════════════════════════════════════════════
# 1. Admin-Button im Header neben agent-btn
# ═══════════════════════════════════════════════════════════════
must_replace("Admin Button im Header",
'  <button id="agent-btn" class="hdr-btn" data-tooltip-kind="agent" onclick="showAgentModal()"><span id="agent-label">Kein Agent</span> <span class="shortcut-label">[A]</span></button>',
'  <button id="agent-btn" class="hdr-btn" data-tooltip-kind="agent" onclick="showAgentModal()"><span id="agent-label">Kein Agent</span> <span class="shortcut-label">[A]</span></button>\n'
'  <button id="admin-btn" class="hdr-btn" onclick="window.open(\'/admin/access-control\', \'_blank\')" title="Access Control">\\u2699 Admin</button>')

# ═══════════════════════════════════════════════════════════════
# 2. Backend-Routes nach /get_prompt route einfuegen
# ═══════════════════════════════════════════════════════════════
access_control_routes = '''

# ─── ACCESS CONTROL ───────────────────────────────────────────────────────
ACCESS_CONTROL_FILE = os.path.join(BASE, "config", "access_control.json")

def _load_access_control():
    try:
        with open(ACCESS_CONTROL_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {"agents": {}, "last_modified": "", "version": "1.0"}


@app.route('/api/access-control', methods=['GET'])
def api_access_control_get():
    return jsonify(_load_access_control())


@app.route('/api/access-control', methods=['POST'])
def api_access_control_post():
    import datetime as _dt
    data = request.get_json(silent=True)
    if not data or 'agents' not in data:
        return jsonify({'success': False, 'error': 'Ungueltige Eingabe: agents fehlt'}), 400
    # Validate: each agent must exist as .txt in AGENTS_DIR
    valid_agents = set()
    if os.path.exists(AGENTS_DIR):
        for fname in os.listdir(AGENTS_DIR):
            if fname.endswith('.txt') and '.backup_' not in fname:
                valid_agents.add(fname[:-4])
    for agent in data['agents'].keys():
        if agent not in valid_agents:
            return jsonify({'success': False, 'error': f'Unbekannter Agent: {agent}'}), 400
    # Write
    data['last_modified'] = _dt.datetime.now().isoformat()
    data.setdefault('version', '1.0')
    try:
        os.makedirs(os.path.dirname(ACCESS_CONTROL_FILE), exist_ok=True)
        with open(ACCESS_CONTROL_FILE, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return jsonify({'success': True, 'saved_at': data['last_modified']})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/admin/access-control', methods=['GET'])
def admin_access_control_page():
    html = """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Access Control — AssistantDev</title>
<style>
* { box-sizing:border-box; }
body { background:#1a1a2e; color:#e0e0e0; font-family:-apple-system,Inter,sans-serif; margin:0; padding:30px; }
h1 { color:#f0c060; font-size:24px; margin:0 0 8px; }
.subtitle { color:#888; font-size:13px; margin-bottom:24px; }
.container { max-width:900px; margin:0 auto; }
.agent-card { background:#22224a; border:1px solid #334; border-radius:10px; padding:18px; margin:12px 0; }
.agent-name { font-size:16px; font-weight:600; color:#e0e0e0; margin-bottom:4px; }
.agent-desc { font-size:12px; color:#888; margin-bottom:14px; line-height:1.5; }
.field-row { margin:10px 0; }
.field-row label { display:inline-flex; align-items:center; color:#ccc; font-size:13px; cursor:pointer; }
.field-row input[type=checkbox] { margin-right:8px; accent-color:#4a8aca; }
.field-row span.hint { color:#666; font-size:11px; margin-left:6px; }
.shared-options { display:flex; gap:12px; margin-top:6px; padding-left:22px; }
.cross-input { background:#111; border:1px solid #334; color:#e0e0e0; padding:6px 10px; border-radius:5px; font-size:12px; width:100%; font-family:Inter,sans-serif; margin-top:4px; }
.btn-row { margin-top:24px; padding-top:16px; border-top:1px solid #334; }
.btn { padding:10px 24px; border:none; border-radius:6px; cursor:pointer; font-size:14px; font-family:Inter,sans-serif; font-weight:600; }
.btn-primary { background:#4a8aca; color:#fff; }
.btn-primary:hover { background:#5a9ada; }
.btn-secondary { background:#333; color:#aaa; margin-left:8px; }
.msg { padding:10px 14px; border-radius:6px; margin:10px 0; font-size:13px; display:none; }
.msg.success { background:#1f4a1f; border:1px solid #4a8a4a; color:#a0d090; display:block; }
.msg.error { background:#4a1f1f; border:1px solid #8a4a4a; color:#d09090; display:block; }
.last-mod { color:#666; font-size:11px; margin-top:6px; }
.back-link { color:#4a8aca; text-decoration:none; font-size:13px; }
.back-link:hover { text-decoration:underline; }
</style></head><body>
<div class="container">
<a href="/" class="back-link">\\u2190 Zurueck zum Chat</a>
<h1>\\u2699 Access Control</h1>
<div class="subtitle">Zugriffsrechte pro Agent — Memory, Shared Memory und Cross-Agent-Reads</div>
<div id="msg" class="msg"></div>
<div id="agents-container">Lade...</div>
<div class="btn-row">
  <button class="btn btn-primary" onclick="saveAccessControl()">Speichern</button>
  <button class="btn btn-secondary" onclick="loadAccessControl()">Verwerfen</button>
  <span class="last-mod" id="last-mod"></span>
</div>
</div>
<script>
let _acData = null;
const SHARED_OPTIONS = ['webclips', 'email_inbox', 'calendar'];

async function loadAccessControl() {
  const r = await fetch('/api/access-control');
  _acData = await r.json();
  renderAgents();
  document.getElementById('last-mod').textContent = _acData.last_modified ? 'Zuletzt geaendert: ' + _acData.last_modified : '';
}

function renderAgents() {
  const container = document.getElementById('agents-container');
  container.innerHTML = '';
  const agents = _acData.agents || {};
  Object.keys(agents).sort().forEach(name => {
    const a = agents[name];
    const shared = a.shared_memory || [];
    const cross = (a.cross_agent_read || []).join(', ');
    const sharedHtml = SHARED_OPTIONS.map(opt => {
      const checked = shared.includes(opt) ? 'checked' : '';
      return `<label><input type="checkbox" data-agent="${name}" data-shared="${opt}" ${checked}> ${opt}</label>`;
    }).join(' ');
    container.innerHTML += `
      <div class="agent-card">
        <div class="agent-name">${escHtml(name)}</div>
        <div class="agent-desc">${escHtml(a.description || '')}</div>
        <div class="field-row">
          <label>
            <input type="checkbox" data-agent="${name}" data-field="own_memory" ${a.own_memory ? 'checked' : ''}>
            Eigenes Memory aktiv
          </label>
        </div>
        <div class="field-row">
          <label>Shared Memory Zugriff:</label>
          <div class="shared-options">${sharedHtml}</div>
        </div>
        <div class="field-row">
          <label>Cross-Agent Read Access (komma-separiert):</label>
          <input type="text" class="cross-input" data-agent="${name}" data-field="cross_agent_read" value="${escHtml(cross)}" placeholder="z.B. standard, privat">
        </div>
      </div>
    `;
  });
}

function escHtml(s) {
  return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

async function saveAccessControl() {
  if (!_acData) return;
  // Collect from DOM
  const agents = _acData.agents || {};
  Object.keys(agents).forEach(name => {
    // own_memory
    const ownBox = document.querySelector(`input[data-agent="${name}"][data-field="own_memory"]`);
    if (ownBox) agents[name].own_memory = ownBox.checked;
    // shared_memory
    const sharedBoxes = document.querySelectorAll(`input[data-agent="${name}"][data-shared]`);
    agents[name].shared_memory = Array.from(sharedBoxes).filter(b => b.checked).map(b => b.dataset.shared);
    // cross_agent_read
    const crossInput = document.querySelector(`input[data-agent="${name}"][data-field="cross_agent_read"]`);
    if (crossInput) agents[name].cross_agent_read = crossInput.value.split(',').map(s => s.trim()).filter(Boolean);
  });
  const msg = document.getElementById('msg');
  try {
    const r = await fetch('/api/access-control', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(_acData)
    });
    const d = await r.json();
    if (d.success) {
      msg.className = 'msg success';
      msg.textContent = 'Gespeichert um ' + d.saved_at;
      document.getElementById('last-mod').textContent = 'Zuletzt geaendert: ' + d.saved_at;
    } else {
      msg.className = 'msg error';
      msg.textContent = 'Fehler: ' + (d.error || 'unbekannt');
    }
  } catch(e) {
    msg.className = 'msg error';
    msg.textContent = 'Netzwerk-Fehler: ' + e.message;
  }
  setTimeout(() => { msg.style.display = 'none'; }, 5000);
}

loadAccessControl();
</script>
</body></html>"""
    return html

'''

# Insert before @app.route('/get_prompt')
anchor = "@app.route('/get_prompt', methods=['GET'])"
content = content.replace(anchor, access_control_routes.strip() + "\n\n" + anchor, 1)
print("OK: Access Control Routes eingefuegt")

with open(path, 'w') as f:
    f.write(content)

print("\nAlle Patches angewendet!")
