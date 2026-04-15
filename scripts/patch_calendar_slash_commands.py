#!/usr/bin/env python3
"""Patch: Calendar Slash Commands + Frontend Handler.
/calendar-today, /calendar-week, /calendar-tomorrow, /calendar-search
Marker: CALENDAR_SLASH_V1
"""
import os, sys
WS = os.path.expanduser("~/AssistantDev/src/web_server.py")
src = open(WS).read()
MARKER = 'CALENDAR_SLASH_V1'
if MARKER in src:
    print("Schon gepatcht.")
    sys.exit(0)

changed = False

# 1. Slash Commands einfuegen nach den Canva-Commands
OLD1 = """  {cmd: '/canva-export', label: '/canva-export [design-id] [format]', desc: 'Canva Design exportieren (pdf/png/jpg)', template: 'Exportiere Canva Design: '},"""

NEW1 = """  {cmd: '/canva-export', label: '/canva-export [design-id] [format]', desc: 'Canva Design exportieren (pdf/png/jpg)', template: 'Exportiere Canva Design: '},
  // CALENDAR_SLASH_V1: Kalender-Befehle
  {cmd: '/calendar-today', label: '/calendar-today', desc: 'Heutige Termine anzeigen', template: ''},
  {cmd: '/calendar-tomorrow', label: '/calendar-tomorrow', desc: 'Termine morgen', template: ''},
  {cmd: '/calendar-week', label: '/calendar-week', desc: 'Termine diese Woche (7 Tage)', template: ''},
  {cmd: '/calendar-search', label: '/calendar-search [query]', desc: 'Termine durchsuchen', template: 'Suche Termin: '},"""

if src.count(OLD1) == 1:
    src = src.replace(OLD1, NEW1, 1)
    print("  [OK] Slash Commands")
    changed = True
else:
    print(f"  [SKIP] Slash Commands: {src.count(OLD1)}")

# 2. Frontend Handler — vor dem Canva-Handler einfuegen
OLD2 = """  // CANVA_SLASH_V1: Canva-Befehle intercepten
  if (text.startsWith('/canva-')) {"""

NEW2 = """  // CALENDAR_SLASH_V1: Kalender-Befehle intercepten
  if (text.startsWith('/calendar-')) {
    addMessage('user', text);
    scrollDown();
    handleCalendarCommand(text);
    return;
  }

  // CANVA_SLASH_V1: Canva-Befehle intercepten
  if (text.startsWith('/canva-')) {"""

if src.count(OLD2) == 1:
    src = src.replace(OLD2, NEW2, 1)
    print("  [OK] Calendar intercept")
    changed = True
else:
    print(f"  [SKIP] Calendar intercept: {src.count(OLD2)}")

# 3. handleCalendarCommand Funktion — vor handleCanvaCommand einfuegen
OLD3 = """async function handleCanvaCommand(text) {"""

NEW3 = """async function handleCalendarCommand(text) {
  startTyping('Kalender...');
  try {
    const parts = text.split(/\\s+/);
    const cmd = parts[0];
    const arg = parts.slice(1).join(' ').trim();
    let daysBack = 0, daysAhead = 1, label = 'Heute';

    if (cmd === '/calendar-today') { daysBack = 0; daysAhead = 1; label = 'Heute'; }
    else if (cmd === '/calendar-tomorrow') { daysBack = 0; daysAhead = 2; label = 'Morgen'; }
    else if (cmd === '/calendar-week') { daysBack = 0; daysAhead = 7; label = 'Diese Woche'; }
    else if (cmd === '/calendar-search') {
      if (!arg) { stopTyping(); addStatusMsg('Bitte Suchbegriff angeben: /calendar-search Meeting'); return; }
      daysBack = 30; daysAhead = 30; label = 'Suche: ' + arg;
    }

    const payload = {days_back: daysBack, days_ahead: daysAhead};
    if (cmd === '/calendar-search' && arg) payload.search = arg;

    const r = await fetch('/api/calendar', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
    const d = await r.json();
    stopTyping();

    if (d.error) { addStatusMsg('Kalender-Fehler: ' + d.error); return; }

    let msg = '**\\U0001f4c5 Kalender — ' + label + '** (' + d.count + ' Termine)\\n';
    if (!d.events || !d.events.length) {
      msg += '\\nKeine Termine gefunden.';
    } else {
      let lastDate = '';
      d.events.forEach(function(e) {
        const startStr = e.start || '';
        const dateOnly = startStr.substring(0, 10);
        if (dateOnly !== lastDate) {
          msg += '\\n**' + dateOnly + '**';
          lastDate = dateOnly;
        }
        const time = e.all_day ? 'Ganztaegig' : startStr.substring(11, 16);
        msg += '\\n- ' + time + ' — **' + e.title + '**';
        if (e.calendar_name) msg += ' _(' + e.calendar_name + ')_';
        if (e.location) msg += ' \\U0001f4cd ' + e.location;
      });
    }
    addMessage('assistant', msg);
  } catch(e) {
    stopTyping();
    addStatusMsg('Kalender-Fehler: ' + e.message);
  }
}

async function handleCanvaCommand(text) {"""

if src.count(OLD3) == 1:
    src = src.replace(OLD3, NEW3, 1)
    print("  [OK] handleCalendarCommand")
    changed = True
else:
    print(f"  [SKIP] handleCalendarCommand: {src.count(OLD3)}")

# 4. System-Prompt: Kalender-Slash-Commands erwaehnen
OLD4 = """- Canva Designs: Du kannst Canva-Designs suchen, erstellen und exportieren. Verwende die /canva-Befehle oder sage einfach "erstelle ein Canva Design", "suche in Canva", "exportiere als PDF". Fuer Kampagnen mit Brand Templates: /canva-campaign."""

NEW4 = """- Kalender: Du hast Zugriff auf den Kalender (Fantastical/Apple Calendar). Befehle: /calendar-today, /calendar-tomorrow, /calendar-week, /calendar-search [query]. Termine werden auch automatisch eingeblendet wenn der Nutzer danach fragt.
- Canva Designs: Du kannst Canva-Designs suchen, erstellen und exportieren. Verwende die /canva-Befehle oder sage einfach "erstelle ein Canva Design", "suche in Canva", "exportiere als PDF". Fuer Kampagnen mit Brand Templates: /canva-campaign."""

if src.count(OLD4) == 1:
    src = src.replace(OLD4, NEW4, 1)
    print("  [OK] System-Prompt Kalender-Slash")
    changed = True
else:
    print(f"  [SKIP] System-Prompt: {src.count(OLD4)}")

if not changed:
    print("Keine Aenderungen.")
    sys.exit(0)

open(WS, 'w').write(src)
print(f"OK ({len(src)} bytes)")
