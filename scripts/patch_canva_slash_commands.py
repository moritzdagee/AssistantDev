#!/usr/bin/env python3
"""
Patch: Canva Slash Commands + System-Prompt-Faehigkeiten + Frontend-Handler.

1. Slash Commands im Frontend: /canva-search, /canva-create, /canva-campaign, /canva-export
2. System-Prompt-Erweiterung: Canva-Faehigkeiten fuer alle Agenten
3. Frontend-Handler: Canva-Slash-Commands intercepten und an /api/canva routen

Marker: CANVA_SLASH_V1
"""
import os, sys
WS = os.path.expanduser("~/AssistantDev/src/web_server.py")
src = open(WS).read()
MARKER = 'CANVA_SLASH_V1'
if MARKER in src:
    print("Schon gepatcht.")
    sys.exit(0)

changed = False

# ═══════════════════════════════════════════════════════════════════════════
# 1. Slash Commands in _SLASH_COMMANDS Array einfuegen
# ═══════════════════════════════════════════════════════════════════════════

OLD_SLASH = """  {cmd: '/create-file-pptx', label: '/create-file-pptx', desc: 'PowerPoint-Praesentation erstellen', template: 'Erstelle eine PowerPoint-Praesentation: '},"""

NEW_SLASH = """  {cmd: '/create-file-pptx', label: '/create-file-pptx', desc: 'PowerPoint-Praesentation erstellen', template: 'Erstelle eine PowerPoint-Praesentation: '},
  // CANVA_SLASH_V1: Canva-Befehle
  {cmd: '/canva-search', label: '/canva-search [query]', desc: 'Canva Designs durchsuchen', template: 'Suche in Canva nach: '},
  {cmd: '/canva-create', label: '/canva-create [titel]', desc: 'Neues Canva Design erstellen', template: 'Erstelle ein Canva Design: '},
  {cmd: '/canva-templates', label: '/canva-templates', desc: 'Canva Brand Templates auflisten', template: ''},
  {cmd: '/canva-campaign', label: '/canva-campaign', desc: 'Canva Ad-Kampagne aus Template generieren', template: 'Erstelle eine Canva Kampagne mit Template: '},
  {cmd: '/canva-export', label: '/canva-export [design-id] [format]', desc: 'Canva Design exportieren (pdf/png/jpg)', template: 'Exportiere Canva Design: '},"""

if src.count(OLD_SLASH) == 1:
    src = src.replace(OLD_SLASH, NEW_SLASH, 1)
    print("  [OK] Slash Commands eingefuegt")
    changed = True
else:
    print(f"  [SKIP] Slash Commands: {src.count(OLD_SLASH)} Vorkommen")


# ═══════════════════════════════════════════════════════════════════════════
# 2. System-Prompt: Canva-Faehigkeiten nach "Videos erstellen" einfuegen
# ═══════════════════════════════════════════════════════════════════════════

OLD_PROMPT = """- Videos erstellen: Wenn der Nutzer ein Video moechte, verwende CREATE_VIDEO. Das System nutzt automatisch Google Veo. Sage NIEMALS dass du keine Videos erstellen kannst.
--- ENDE DATEI-ERSTELLUNG ---\""""

NEW_PROMPT = """- Videos erstellen: Wenn der Nutzer ein Video moechte, verwende CREATE_VIDEO. Das System nutzt automatisch Google Veo. Sage NIEMALS dass du keine Videos erstellen kannst.
- Canva Designs: Du kannst Canva-Designs suchen, erstellen und exportieren. Verwende die /canva-Befehle oder sage einfach "erstelle ein Canva Design", "suche in Canva", "exportiere als PDF". Fuer Kampagnen mit Brand Templates: /canva-campaign.
--- ENDE DATEI-ERSTELLUNG ---\""""

if src.count(OLD_PROMPT) == 1:
    src = src.replace(OLD_PROMPT, NEW_PROMPT, 1)
    print("  [OK] System-Prompt Canva-Faehigkeit")
    changed = True
else:
    print(f"  [SKIP] System-Prompt: {src.count(OLD_PROMPT)} Vorkommen")


# ═══════════════════════════════════════════════════════════════════════════
# 3. Frontend: Canva Slash Commands intercepten (wie /find)
#    Einfuegen in sendMessage() vor dem normalen doSendChat
# ═══════════════════════════════════════════════════════════════════════════

OLD_SEND = """  addMessage('user', text);
  scrollDown();
  doSendChat(text);
}

async function doSendChat(text) {"""

NEW_SEND = """  // CANVA_SLASH_V1: Canva-Befehle intercepten
  if (text.startsWith('/canva-')) {
    addMessage('user', text);
    scrollDown();
    handleCanvaCommand(text);
    return;
  }

  addMessage('user', text);
  scrollDown();
  doSendChat(text);
}

async function handleCanvaCommand(text) {
  startTyping('Canva...');
  try {
    const parts = text.split(/\\s+/);
    const cmd = parts[0];
    const arg = parts.slice(1).join(' ').trim();

    if (cmd === '/canva-search') {
      const r = await fetch('/api/canva', {method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({action:'search', query: arg || '', count: 10})});
      const d = await r.json();
      stopTyping();
      if (d.ok && d.data && d.data.items) {
        let msg = '**Canva Designs' + (arg ? ' fuer "'+arg+'"' : '') + ':**\\n';
        d.data.items.forEach(function(it) {
          msg += '\\n- **' + (it.title || '(Ohne Titel)') + '** (ID: `' + it.id + '`)';
          if (it.urls && it.urls.edit_url) msg += ' — [Bearbeiten](' + it.urls.edit_url + ')';
        });
        if (!d.data.items.length) msg += '\\nKeine Designs gefunden.';
        addMessage('assistant', msg);
      } else { addStatusMsg('Canva-Fehler: ' + (d.error || d.data?.error || 'Unbekannt')); }

    } else if (cmd === '/canva-create') {
      if (!arg) { stopTyping(); addStatusMsg('Bitte Titel angeben: /canva-create Mein Design'); return; }
      const r = await fetch('/api/canva', {method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({action:'create', title: arg, design_type: 'doc'})});
      const d = await r.json();
      stopTyping();
      if (d.ok && d.data) {
        let msg = '**Canva Design erstellt:** ' + arg;
        if (d.data.design && d.data.design.urls) msg += '\\n[Design oeffnen](' + d.data.design.urls.edit_url + ')';
        addMessage('assistant', msg);
      } else { addStatusMsg('Canva-Fehler: ' + (d.error || d.data?.error || 'Unbekannt')); }

    } else if (cmd === '/canva-templates') {
      const r = await fetch('/api/canva', {method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({action:'brand_templates', query: arg || '', count: 20})});
      const d = await r.json();
      stopTyping();
      if (d.ok && d.data && d.data.items) {
        let msg = '**Canva Brand Templates:**\\n';
        d.data.items.forEach(function(it) {
          msg += '\\n- **' + (it.title || it.id) + '** (ID: `' + it.id + '`)';
        });
        if (!d.data.items.length) msg += '\\nKeine Brand Templates gefunden. Erstelle Templates in Canva und markiere sie als Brand Template.';
        addMessage('assistant', msg);
      } else { addStatusMsg('Canva-Fehler: ' + (d.error || d.data?.error || 'Unbekannt')); }

    } else if (cmd === '/canva-export') {
      const exportParts = arg.split(/\\s+/);
      const designId = exportParts[0] || '';
      const fmt = exportParts[1] || 'pdf';
      if (!designId) { stopTyping(); addStatusMsg('Bitte Design-ID angeben: /canva-export DAGxxxx pdf'); return; }
      const r = await fetch('/api/canva', {method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({action:'export', design_id: designId, format: fmt})});
      const d = await r.json();
      stopTyping();
      if (d.ok && d.data) {
        addMessage('assistant', '**Export gestartet** (Design: `' + designId + '`, Format: ' + fmt + ')\\nStatus: ' + JSON.stringify(d.data).substring(0, 200));
      } else { addStatusMsg('Export-Fehler: ' + (d.error || d.data?.error || 'Unbekannt')); }

    } else if (cmd === '/canva-campaign') {
      // Kampagne wird ans LLM delegiert — der Agent erstellt die Varianten
      stopTyping();
      doSendChat('Erstelle eine Canva-Kampagne mit mehreren Varianten. ' + (arg || 'Ich moechte verschiedene Ad-Varianten aus einem Brand Template generieren. Zeige mir erst die verfuegbaren Templates.'));

    } else {
      stopTyping();
      addStatusMsg('Unbekannter Canva-Befehl: ' + cmd);
    }
  } catch(e) {
    stopTyping();
    addStatusMsg('Canva-Fehler: ' + e.message);
  }
}

async function doSendChat(text) {"""

if src.count(OLD_SEND) == 1:
    src = src.replace(OLD_SEND, NEW_SEND, 1)
    print("  [OK] Frontend Canva Command Handler")
    changed = True
else:
    print(f"  [SKIP] Frontend Handler: {src.count(OLD_SEND)} Vorkommen")

if not changed:
    print("Keine Aenderungen.")
    sys.exit(0)

open(WS, 'w').write(src)
print(f"OK ({len(src)} bytes)")
