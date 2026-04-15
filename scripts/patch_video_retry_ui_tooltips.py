#!/usr/bin/env python3
"""
Konsolidiertes Patch-Skript fuer drei Fixes in web_server.py:

Fix 1  VEO_RETRY_V3  Video-Generierung: Retry-Logik fuer Code 13/14/429 mit
                     exponentiellem Backoff, Duration/Aspect-Fallback, bessere
                     Fehlermeldungen je Error-Code.

Fix 2  AGENT_BTN_V1  Agent-Name sitzt jetzt im Agent-Button selbst. Kein
                     separates Label links davon. agent-label bleibt als span
                     erhalten (fuer getAgentName()), wandert aber in den Button.

Fix 3  TOOLTIPS_V1   Tooltip-System (data-tooltip Attribut) mit dezentem Dark-
                     Theme, 300 ms Hover-Delay. Provider-, Modell- und Agent-
                     Tooltips mit beschreibenden Texten. /agents Route liefert
                     zusaetzlich ein description-Feld.

Alle drei Fixes sind idempotent (pro Fix ein Marker).
Alle betroffenen Code-Stellen liegen AUSSERHALB der duplizierten Bloecke 1-1358
(generate_video ist nur 1x definiert, das HTML ist nach Flask-Instanz 2). Exakt
1 Vorkommen pro Replacement ist erforderlich.
"""
import os
import sys

WS = os.path.expanduser("~/AssistantDev/src/web_server.py")


def apply_patch(src, old, new, marker, description):
    """Ersetzt genau 1 Vorkommen, mit Marker-basierter Idempotenz."""
    if marker in src:
        print(f"  [skip] {description}: marker '{marker}' schon vorhanden")
        return src, False
    count = src.count(old)
    if count != 1:
        print(f"  [FAIL] {description}: erwarte 1 Vorkommen, gefunden {count}")
        sys.exit(2)
    new_src = src.replace(old, new, 1)
    print(f"  [OK]   {description}")
    return new_src, True


# ══════════════════════════════════════════════════════════════════════════
# Fix 1: VEO_RETRY_V3 — generate_video Retry-Logik
# ══════════════════════════════════════════════════════════════════════════

OLD_VEO = '''    # Start long-running operation
    task_update(task_id, progress=2, message='Sende Anfrage an Gemini Veo...')
    video_model = VIDEO_PROVIDERS.get(provider_key, 'veo-3.1-generate-preview')
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{video_model}:predictLongRunning?key={api_key}"
    r = requests.post(url,
        headers={"Content-Type": "application/json"},
        json={"instances": [{"prompt": prompt}], "parameters": {"aspectRatio": "16:9"}},
        timeout=30)
    data = r.json()
    if r.status_code != 200:
        raise Exception(f"Gemini Veo API Fehler: {data.get('error', {}).get('message', str(data))}")

    op_name = data.get('name')
    if not op_name:
        raise Exception("Gemini Veo: Keine Operation gestartet")

    task_update(task_id, progress=5, message='Video wird generiert...')'''

NEW_VEO = '''    # VEO_RETRY_V3: Retry-Schleife fuer transiente Fehler (code 13/14/429)
    # Retry 0: default (16:9, 8s)
    # Retry 1: durationSeconds=5 (kuerzer)
    # Retry 2: aspectRatio flip + stable fallback-model (veo-2.0-generate-001)
    default_model = VIDEO_PROVIDERS.get(provider_key, 'veo-3.1-generate-preview')
    STABLE_FALLBACK_MODEL = 'veo-2.0-generate-001'
    MAX_RETRIES = 3
    RETRYABLE_CODES = {13, 14, 429}
    BACKOFF = [0, 10, 20]  # seconds before retry 0/1/2
    import time as _vt

    op_name = None
    last_error_text = ''
    for _retry in range(MAX_RETRIES):
        # Retry-spezifische Parameter
        video_model = default_model
        aspect = "16:9"
        duration = 8
        retry_label = ''
        if _retry == 1:
            duration = 5
            retry_label = ' (kuerzere Dauer)'
        elif _retry == 2:
            aspect = "9:16"  # flipped
            video_model = STABLE_FALLBACK_MODEL
            retry_label = f' (Fallback {STABLE_FALLBACK_MODEL})'

        if _retry == 0:
            task_update(task_id, progress=2, message='Sende Anfrage an Gemini Veo...')
        else:
            wait_s = BACKOFF[_retry]
            task_update(
                task_id,
                progress=2,
                message=f'Retry [{_retry+1}/{MAX_RETRIES}]{retry_label}... warte {wait_s}s',
            )
            print(f"[VEO] Retry {_retry+1}/{MAX_RETRIES}{retry_label}: backoff {wait_s}s", flush=True)
            _vt.sleep(wait_s)

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{video_model}:predictLongRunning?key={api_key}"
        payload = {
            "instances": [{"prompt": prompt}],
            "parameters": {"aspectRatio": aspect, "durationSeconds": duration},
        }
        print(f"[VEO] POST model={video_model} aspect={aspect} dur={duration}s", flush=True)
        try:
            r = requests.post(url,
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=30)
        except Exception as post_ex:
            last_error_text = f"Netzwerk-Fehler: {post_ex}"
            print(f"[VEO] POST Exception: {post_ex}", flush=True)
            task_update(task_id, progress=3, message=f'Netzwerk-Fehler - wird erneut versucht ({_retry+1}/{MAX_RETRIES})...')
            continue

        try:
            data = r.json()
        except Exception:
            data = {}

        if r.status_code == 200 and data.get('name'):
            op_name = data['name']
            print(f"[VEO] Operation gestartet: {op_name}", flush=True)
            break

        # Fehler analysieren
        err_obj = data.get('error', {}) or {}
        err_code = err_obj.get('code', r.status_code)
        err_msg = err_obj.get('message', str(data) if data else f'HTTP {r.status_code}')
        last_error_text = f"code {err_code}: {err_msg}"
        print(f"[VEO] POST-Fehler code={err_code}: {err_msg}", flush=True)

        # User-facing Status je Error-Code
        try:
            err_code_int = int(err_code)
        except Exception:
            err_code_int = 0

        if err_code_int == 13:
            status_msg = f'Gemini Veo Server-Fehler - wird erneut versucht ({_retry+1}/{MAX_RETRIES})...'
        elif err_code_int == 429:
            status_msg = f'Gemini Veo Rate Limit - warte {BACKOFF[min(_retry+1, MAX_RETRIES-1)]}s und versuche erneut ({_retry+1}/{MAX_RETRIES})...'
        elif err_code_int == 14:
            status_msg = f'Gemini Veo kurz nicht verfuegbar - wird erneut versucht ({_retry+1}/{MAX_RETRIES})...'
        else:
            status_msg = f'Unbekannter Fehler [{err_code}] - wird erneut versucht ({_retry+1}/{MAX_RETRIES})...'
        task_update(task_id, progress=3, message=status_msg)

        # Nicht-retryable Fehler bubbeln sofort hoch
        if err_code_int not in RETRYABLE_CODES and r.status_code not in (500, 502, 503, 504):
            raise Exception(f"Gemini Veo API-Fehler (code {err_code}): {err_msg}")
        # Sonst weiter in die naechste Retry-Runde

    if not op_name:
        raise Exception(
            f"Video-Generierung nach {MAX_RETRIES} Versuchen fehlgeschlagen. "
            f"Bitte spaeter erneut versuchen. Letzter Fehler: {last_error_text}"
        )

    task_update(task_id, progress=5, message='Video wird generiert...')'''


# ══════════════════════════════════════════════════════════════════════════
# Fix 2: AGENT_BTN_V1 — Agent-Name im Button integriert
# ══════════════════════════════════════════════════════════════════════════

OLD_AGENT_BTN = '''  <button id="prompt-btn" onclick="toggleSidebar()">☰ Prompt <span class="shortcut-label">[P]</span></button>
  <span id="agent-label" style="flex:1;">Kein Agent</span>
  <button class="hdr-btn" onclick="newSession()" style="background:#2a3a2a;border-color:#4a6a4a;color:#a0d090;">+ Neu <span class="shortcut-label">[N]</span></button>
  <button class="hdr-btn" onclick="showAgentModal()">Agent <span class="shortcut-label">[A]</span></button>'''

NEW_AGENT_BTN = '''  <button id="prompt-btn" onclick="toggleSidebar()">☰ Prompt <span class="shortcut-label">[P]</span></button>
  <div id="header-spacer" style="flex:1;"></div><!-- AGENT_BTN_V1 -->
  <button class="hdr-btn" onclick="newSession()" style="background:#2a3a2a;border-color:#4a6a4a;color:#a0d090;">+ Neu <span class="shortcut-label">[N]</span></button>
  <button id="agent-btn" class="hdr-btn" data-tooltip-kind="agent" onclick="showAgentModal()"><span id="agent-label">Kein Agent</span> <span class="shortcut-label">[A]</span></button>'''


# ══════════════════════════════════════════════════════════════════════════
# Fix 3a: TOOLTIPS_V1_CSS — Tooltip-Styles
# ══════════════════════════════════════════════════════════════════════════

OLD_TOOLTIP_CSS_ANCHOR = '''  .section-copy-btn.copied { color:#4caf50; border-color:#4caf50; opacity:1; }
</style>'''

NEW_TOOLTIP_CSS_ANCHOR = '''  .section-copy-btn.copied { color:#4caf50; border-color:#4caf50; opacity:1; }
  /* TOOLTIPS_V1 — dezente Hover-Tooltips fuer Provider/Modell/Agent */
  #tt-box { position:fixed; z-index:9999; background:#1a1a1a; color:#eaeaea; border:1px solid #3a3a3a; border-radius:8px; padding:8px 12px; font-size:12px; font-family:Inter,sans-serif; max-width:320px; line-height:1.4; box-shadow:0 6px 18px rgba(0,0,0,0.6); pointer-events:none; opacity:0; transition:opacity 0.12s ease; white-space:normal; }
  #tt-box.show { opacity:1; }
  #tt-box .tt-title { color:#f0c060; font-weight:700; margin-bottom:3px; font-size:12px; }
  #tt-box .tt-body { color:#cfcfcf; font-size:11px; }
</style>'''


# ══════════════════════════════════════════════════════════════════════════
# Fix 3b: TOOLTIPS_V1_HTML — Tooltip-Box nach <body>
# ══════════════════════════════════════════════════════════════════════════

OLD_TOOLTIP_BODY = '''<body>
<div id="drop-overlay">
  <div style="font-size:48px;">📂</div>
  <div style="font-size:18px;font-weight:600;color:#f0c060;font-family:Inter,sans-serif;">Dateien hier ablegen</div>
</div>'''

NEW_TOOLTIP_BODY = '''<body>
<div id="tt-box"><div class="tt-title"></div><div class="tt-body"></div></div><!-- TOOLTIPS_V1 -->
<div id="drop-overlay">
  <div style="font-size:48px;">📂</div>
  <div style="font-size:18px;font-weight:600;color:#f0c060;font-family:Inter,sans-serif;">Dateien hier ablegen</div>
</div>'''


# ══════════════════════════════════════════════════════════════════════════
# Fix 3c: TOOLTIPS_V1_JS — Tooltip-System, Maps, Bindings
# ══════════════════════════════════════════════════════════════════════════

# Wir haengen das Tooltip-System direkt hinter die SESSION-ID Initialisierung an.
OLD_TT_JS_ANCHOR = '''function getAgentName() { return document.getElementById('agent-label').dataset.agentName || document.getElementById('agent-label').textContent; }'''

NEW_TT_JS_ANCHOR = '''function getAgentName() { return document.getElementById('agent-label').dataset.agentName || document.getElementById('agent-label').textContent; }

// ─── TOOLTIPS_V1 ─────────────────────────────────────────────────────────────
var PROVIDER_TOOLTIPS = {
  'Anthropic': 'Anthropic Claude \u2014 Stark in Analyse, Schreiben, Coding und komplexem Reasoning',
  'OpenAI': 'OpenAI GPT \u2014 Vielseitig, stark in Coding, Bildgenerierung (gpt-image-1) und strukturierten Outputs',
  'Google Gemini': 'Google Gemini \u2014 Stark in Multimodal, langer Kontext, Video- & Bildgenerierung (Veo, Imagen)',
  'Gemini': 'Google Gemini \u2014 Stark in Multimodal, langer Kontext, Video- & Bildgenerierung (Veo, Imagen)',
  'Mistral': 'Mistral \u2014 Schnell und effizient, stark in europaeischen Sprachen und Code',
  'Perplexity': 'Perplexity \u2014 Spezialisiert auf Web-Suche und aktuelle Informationen'
};
var MODEL_TOOLTIPS = {
  'Claude Sonnet 4.6': 'Bestes Preis-Leistungs-Verhaeltnis \u2014 schnell, intelligent, fuer taegliche Aufgaben',
  'Claude Opus 4.6': 'Staerkstes Claude-Modell \u2014 fuer komplexe, anspruchsvolle Aufgaben',
  'Claude Haiku 4.5': 'Schnellstes Claude-Modell \u2014 fuer einfache, schnelle Antworten',
  'GPT-4o': 'OpenAIs Flagship \u2014 stark in Multimodal, Coding, strukturierten Outputs',
  'GPT-4o Mini': 'Schnell und guenstig \u2014 fuer einfache Aufgaben und hohe Volumen',
  'o1': 'OpenAI Reasoning-Modell \u2014 fuer komplexe logische und mathematische Probleme',
  'Mistral Large': 'Mistral Flagship \u2014 stark in Mehrsprachigkeit und komplexen Aufgaben',
  'Mistral Small': 'Mistral kompakt \u2014 effizient fuer einfachere Aufgaben',
  'Mistral Nemo': 'Mistral Nemo \u2014 leichtgewichtig, sehr schnell',
  'Gemini 2.0 Flash': 'Schnell und guenstig \u2014 fuer alltaegliche Aufgaben mit Multimodal-Unterstuetzung',
  'Gemini 2.5 Pro': 'Googles staerkstes Modell \u2014 langer Kontext (1M tokens), komplexes Reasoning',
  'Gemini 2.5 Flash': 'Googles schnellstes Flagship \u2014 ideal fuer Video/Bild-Generierung und schnelle Antworten',
  'Gemini 3 Flash (Preview)': 'Gemini 3 Flash Preview \u2014 neue Generation, sehr schnell',
  'Gemini 3 Pro (Preview)': 'Gemini 3 Pro Preview \u2014 neue Generation, fuer anspruchsvolle Aufgaben',
  'Gemini 3.1 Pro (Preview)': 'Gemini 3.1 Pro Preview \u2014 neueste Generation mit Reasoning',
  'Sonar': 'Perplexity Web-Suche \u2014 schnell, aktuelle Informationen',
  'Sonar Pro': 'Perplexity Pro-Suche \u2014 tiefere Recherche, mehr Quellen',
  'Sonar Reasoning': 'Perplexity mit Reasoning \u2014 Suche + logische Schlussfolgerung',
  'Sonar Reasoning Pro': 'Perplexity Pro Reasoning \u2014 tiefste Analyse mit aktuellen Daten',
  'Sonar Deep Research': 'Perplexity Deep Research \u2014 ausfuehrliche Recherche fuer komplexe Themen'
};
var AGENT_DESCRIPTIONS = {};  // befuellt durch loadAgents()
var _ttTimer = null;

function ttGetContent(el) {
  var kind = el.getAttribute('data-tooltip-kind') || '';
  if (kind === 'provider') {
    var ps = document.getElementById('provider-select');
    var name = ps ? (ps.selectedOptions[0] ? ps.selectedOptions[0].textContent : ps.value) : '';
    var body = PROVIDER_TOOLTIPS[name] || ('KI-Provider: ' + name);
    return {title: name, body: body};
  }
  if (kind === 'model') {
    var ms = document.getElementById('model-select');
    if (!ms || !ms.selectedOptions[0]) return {title: 'Modell', body: ''};
    var txt = ms.selectedOptions[0].textContent;
    // Capabilities-Emojis am Ende abtrennen
    var name = txt.replace(/[\\s\\u{1f3ac}\\u{1f5bc}\\ufe0f\\u{1f9e0}]+$/u, '').trim();
    var body = MODEL_TOOLTIPS[name];
    if (!body) {
      var pv = document.getElementById('provider-select');
      var pname = pv && pv.selectedOptions[0] ? pv.selectedOptions[0].textContent : '';
      body = 'KI-Modell von ' + (pname || 'unbekannt');
    }
    return {title: name, body: body};
  }
  if (kind === 'agent') {
    var lbl = document.getElementById('agent-label');
    var name = lbl ? (lbl.dataset.agentName || lbl.textContent) : '';
    if (!name || name === 'Kein Agent') {
      return {title: 'Kein Agent aktiv', body: 'Waehle oben rechts einen Agenten aus.'};
    }
    var desc = AGENT_DESCRIPTIONS[name] || '';
    return {title: 'Agent: ' + name, body: desc || 'Aktiver Agent - klicken zum Wechseln.'};
  }
  // Generic fallback
  var t = el.getAttribute('data-tooltip') || '';
  return {title: '', body: t};
}

function ttShow(el) {
  var box = document.getElementById('tt-box');
  if (!box) return;
  var c = ttGetContent(el);
  if (!c.body && !c.title) return;
  box.querySelector('.tt-title').textContent = c.title || '';
  box.querySelector('.tt-title').style.display = c.title ? 'block' : 'none';
  box.querySelector('.tt-body').textContent = c.body || '';
  var r = el.getBoundingClientRect();
  // Zuerst sichtbar machen um Groesse zu messen
  box.style.left = '-9999px'; box.style.top = '-9999px';
  box.classList.add('show');
  var bw = box.offsetWidth;
  var bh = box.offsetHeight;
  var left = r.left + r.width/2 - bw/2;
  if (left < 8) left = 8;
  if (left + bw > window.innerWidth - 8) left = window.innerWidth - bw - 8;
  var top = r.bottom + 8;
  if (top + bh > window.innerHeight - 8) top = r.top - bh - 8; // ueber dem Element
  box.style.left = left + 'px';
  box.style.top = top + 'px';
}

function ttHide() {
  if (_ttTimer) { clearTimeout(_ttTimer); _ttTimer = null; }
  var box = document.getElementById('tt-box');
  if (box) box.classList.remove('show');
}

function ttAttach(el) {
  if (!el || el.dataset.ttBound === '1') return;
  el.dataset.ttBound = '1';
  el.addEventListener('mouseenter', function(){
    if (_ttTimer) clearTimeout(_ttTimer);
    _ttTimer = setTimeout(function(){ ttShow(el); }, 300);
  });
  el.addEventListener('mouseleave', ttHide);
  el.addEventListener('mousedown', ttHide);
}

function ttAttachAll() {
  var ps = document.getElementById('provider-select');
  if (ps) { ps.setAttribute('data-tooltip-kind','provider'); ttAttach(ps); }
  var ms = document.getElementById('model-select');
  if (ms) { ms.setAttribute('data-tooltip-kind','model'); ttAttach(ms); }
  var ab = document.getElementById('agent-btn');
  if (ab) ttAttach(ab);
}'''


# ══════════════════════════════════════════════════════════════════════════
# Fix 3d: loadAgents laed description-Feld in AGENT_DESCRIPTIONS
# ══════════════════════════════════════════════════════════════════════════

OLD_LOADAGENTS_START = '''async function loadAgents() {
  const r = await fetch('/agents');
  const agents = await r.json();
  const list = document.getElementById('agent-list');
  list.innerHTML = '';
  const expandedAgent = localStorage.getItem('agent_expanded') || '';'''

NEW_LOADAGENTS_START = '''async function loadAgents() {
  const r = await fetch('/agents');
  const agents = await r.json();
  // TOOLTIPS_V1: Agent-Beschreibungen in globaler Map cachen
  try {
    agents.forEach(function(a){
      if (a.description) AGENT_DESCRIPTIONS[a.name] = a.description;
      if (a.subagents) a.subagents.forEach(function(s){ if (s.description) AGENT_DESCRIPTIONS[s.name] = s.description; });
    });
  } catch(e) {}
  const list = document.getElementById('agent-list');
  list.innerHTML = '';
  const expandedAgent = localStorage.getItem('agent_expanded') || '';'''


# ══════════════════════════════════════════════════════════════════════════
# Fix 3e: loadProviders ruft ttAttachAll() auf
# ══════════════════════════════════════════════════════════════════════════

OLD_LOADPROV_END = '''  if (data.length) populateModels(data[0]);
  const saved = localStorage.getItem('claude_model');
  if (saved) {
    try {
      const m = JSON.parse(saved);
      currentModel = m;
      for (let o of ps.options) { if (o.value === m.provider) { ps.value = m.provider; break; } }
      const pd = data.find(p => p.provider === m.provider);
      if (pd) { populateModels(pd); ms.value = m.model_id; }
    } catch(e) {}
  }
}'''

NEW_LOADPROV_END = '''  if (data.length) populateModels(data[0]);
  const saved = localStorage.getItem('claude_model');
  if (saved) {
    try {
      const m = JSON.parse(saved);
      currentModel = m;
      for (let o of ps.options) { if (o.value === m.provider) { ps.value = m.provider; break; } }
      const pd = data.find(p => p.provider === m.provider);
      if (pd) { populateModels(pd); ms.value = m.model_id; }
    } catch(e) {}
  }
  ttAttachAll(); // TOOLTIPS_V1
  // Initiales Laden der Agent-Descriptions fuer Tooltip auf Agent-Button
  try { fetch('/agents').then(function(r){return r.json();}).then(function(ags){
    ags.forEach(function(a){
      if (a.description) AGENT_DESCRIPTIONS[a.name] = a.description;
      if (a.subagents) a.subagents.forEach(function(s){ if (s.description) AGENT_DESCRIPTIONS[s.name] = s.description; });
    });
  }); } catch(e) {}
}'''


# ══════════════════════════════════════════════════════════════════════════
# Fix 3f: /agents Route mit description
# ══════════════════════════════════════════════════════════════════════════

OLD_AGENTS_ROUTE = '''@app.route('/agents')
def get_agents():
    files = sorted([f.replace('.txt','') for f in os.listdir(AGENTS_DIR) if f.endswith('.txt')])
    # Group: parents first, then sub-agents nested
    parents = []
    children = {}  # parent_name -> [sub_agent_names]
    for name in files:
        parent = get_parent_agent(name)
        if parent:
            children.setdefault(parent, []).append(name)
        else:
            parents.append(name)
    # Build hierarchical structure
    result = []
    for p in parents:
        subs = []
        for c in children.get(p, []):
            sub_label = c.split('_', 1)[1] if '_' in c else c
            subs.append({'name': c, 'label': sub_label})
        result.append({
            'name': p,
            'label': p,
            'has_subagents': len(subs) > 0,
            'subagents': subs
        })
    # Orphan sub-agents (parent has no .txt)
    orphan_parents = set(children.keys()) - set(parents)
    for op in sorted(orphan_parents):
        subs = []
        for c in children[op]:
            sub_label = c.split('_', 1)[1] if '_' in c else c
            subs.append({'name': c, 'label': sub_label})
        result.append({
            'name': op,
            'label': op,
            'has_subagents': True,
            'subagents': subs
        })
    return jsonify(result)'''

NEW_AGENTS_ROUTE = '''def _agent_description(name):
    """TOOLTIPS_V1: Liest die ersten zwei Saetze aus dem Agent-System-Prompt
    als knappe Beschreibung fuer Frontend-Tooltips. Max 180 Zeichen."""
    try:
        fpath = os.path.join(AGENTS_DIR, name + '.txt')
        if not os.path.exists(fpath):
            return ''
        with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
            raw = f.read(800)
        # Memory-/System-Marker entfernen
        for marker in ['--- GEDAECHTNIS:', '--- DATEI-ERSTELLUNG ---', '--- WEITERE FAEHIGKEITEN ---', 'VERGANGENE KONVERSATIONEN:']:
            idx = raw.find(marker)
            if idx != -1:
                raw = raw[:idx]
        raw = raw.strip()
        # Erste ~2 Saetze / 180 Zeichen
        snippet = raw.split('\\n\\n')[0] if '\\n\\n' in raw else raw
        snippet = ' '.join(snippet.split())
        if len(snippet) > 180:
            snippet = snippet[:177].rstrip() + '...'
        return snippet
    except Exception:
        return ''


@app.route('/agents')
def get_agents():
    files = sorted([f.replace('.txt','') for f in os.listdir(AGENTS_DIR) if f.endswith('.txt')])
    # Group: parents first, then sub-agents nested
    parents = []
    children = {}  # parent_name -> [sub_agent_names]
    for name in files:
        parent = get_parent_agent(name)
        if parent:
            children.setdefault(parent, []).append(name)
        else:
            parents.append(name)
    # Build hierarchical structure
    result = []
    for p in parents:
        subs = []
        for c in children.get(p, []):
            sub_label = c.split('_', 1)[1] if '_' in c else c
            subs.append({'name': c, 'label': sub_label, 'description': _agent_description(c)})
        result.append({
            'name': p,
            'label': p,
            'description': _agent_description(p),
            'has_subagents': len(subs) > 0,
            'subagents': subs
        })
    # Orphan sub-agents (parent has no .txt)
    orphan_parents = set(children.keys()) - set(parents)
    for op in sorted(orphan_parents):
        subs = []
        for c in children[op]:
            sub_label = c.split('_', 1)[1] if '_' in c else c
            subs.append({'name': c, 'label': sub_label, 'description': _agent_description(c)})
        result.append({
            'name': op,
            'label': op,
            'description': '',
            'has_subagents': True,
            'subagents': subs
        })
    return jsonify(result)'''


def main():
    if not os.path.exists(WS):
        print(f"FEHLER: {WS} existiert nicht", file=sys.stderr)
        sys.exit(1)
    src = open(WS).read()
    orig_len = len(src)
    any_applied = False

    print("Wende Patches an...")
    src, a = apply_patch(src, OLD_VEO, NEW_VEO, 'VEO_RETRY_V3', 'Fix 1 — Video Retry')
    any_applied = any_applied or a
    src, a = apply_patch(src, OLD_AGENT_BTN, NEW_AGENT_BTN, 'AGENT_BTN_V1', 'Fix 2 — Agent Button')
    any_applied = any_applied or a
    src, a = apply_patch(src, OLD_TOOLTIP_CSS_ANCHOR, NEW_TOOLTIP_CSS_ANCHOR, 'TOOLTIPS_V1', 'Fix 3a — Tooltip CSS')
    any_applied = any_applied or a
    src, a = apply_patch(src, OLD_TOOLTIP_BODY, NEW_TOOLTIP_BODY, '<div id="tt-box">', 'Fix 3b — Tooltip HTML')
    any_applied = any_applied or a
    src, a = apply_patch(src, OLD_TT_JS_ANCHOR, NEW_TT_JS_ANCHOR, 'PROVIDER_TOOLTIPS', 'Fix 3c — Tooltip JS')
    any_applied = any_applied or a
    src, a = apply_patch(src, OLD_LOADAGENTS_START, NEW_LOADAGENTS_START, 'AGENT_DESCRIPTIONS[a.name]', 'Fix 3d — loadAgents descr')
    any_applied = any_applied or a
    src, a = apply_patch(src, OLD_LOADPROV_END, NEW_LOADPROV_END, 'ttAttachAll(); // TOOLTIPS_V1', 'Fix 3e — loadProviders')
    any_applied = any_applied or a
    src, a = apply_patch(src, OLD_AGENTS_ROUTE, NEW_AGENTS_ROUTE, '_agent_description', 'Fix 3f — /agents route')
    any_applied = any_applied or a

    if not any_applied:
        print("Alle Patches waren bereits angewendet, keine Aenderung.")
        return

    with open(WS, 'w') as f:
        f.write(src)
    print(f"OK: web_server.py gepatcht ({orig_len} -> {len(src)} bytes)")


if __name__ == '__main__':
    main()
