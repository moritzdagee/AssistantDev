#!/usr/bin/env python3
"""Patch: Slash Commands clustern mit Gruppen-Headern.
Ersetzt das gesamte _SLASH_COMMANDS Array + showSlashAutocomplete Renderer.
Marker: SLASH_CLUSTER_V1
"""
import os, sys
WS = os.path.expanduser("~/AssistantDev/src/web_server.py")
src = open(WS).read()
MARKER = 'SLASH_CLUSTER_V1'
if MARKER in src:
    print("Schon gepatcht.")
    sys.exit(0)

# 1. _SLASH_COMMANDS Array komplett ersetzen (von "const _SLASH_COMMANDS" bis "];")
import re
m = re.search(r'(const _SLASH_COMMANDS = \[.*?\];)', src, re.DOTALL)
if not m:
    print("FEHLER: _SLASH_COMMANDS Array nicht gefunden")
    sys.exit(2)
old_array = m.group(1)

new_array = """const _SLASH_COMMANDS = [
  // SLASH_CLUSTER_V1: Gruppierte Slash Commands
  // ─── Kommunikation ───
  {cmd: '/create-email', label: '/create-email', desc: 'E-Mail Draft erstellen', template: 'Erstelle eine E-Mail an [Empfaenger] zum Thema: ', group: 'Kommunikation'},
  {cmd: '/create-whatsapp', label: '/create-whatsapp', desc: 'WhatsApp-Nachricht', template: 'Schreibe eine WhatsApp-Nachricht an [Name]: ', group: 'Kommunikation'},
  {cmd: '/create-slack', label: '/create-slack', desc: 'Slack-Nachricht', template: 'Schreibe eine Slack-Nachricht an [#channel oder Name]: ', group: 'Kommunikation'},
  // ─── Kalender ───
  {cmd: '/calendar-today', label: '/calendar-today', desc: 'Heutige Termine', template: '', group: 'Kalender'},
  {cmd: '/calendar-tomorrow', label: '/calendar-tomorrow', desc: 'Termine morgen', template: '', group: 'Kalender'},
  {cmd: '/calendar-week', label: '/calendar-week', desc: 'Naechste 7 Tage', template: '', group: 'Kalender'},
  {cmd: '/calendar-search', label: '/calendar-search [query]', desc: 'Termine durchsuchen', template: 'Suche Termin: ', group: 'Kalender'},
  // ─── Medien ───
  {cmd: '/create-image', label: '/create-image', desc: 'Bild generieren (Gemini/OpenAI)', template: 'Erstelle ein Bild: ', group: 'Medien'},
  {cmd: '/create-video', label: '/create-video', desc: 'Video generieren (Gemini Veo)', template: 'Erstelle ein Video: ', group: 'Medien'},
  // ─── Dokumente ───
  {cmd: '/create-file-docx', label: '/create-file-docx', desc: 'Word-Dokument', template: 'Erstelle ein Word-Dokument: ', group: 'Dokumente'},
  {cmd: '/create-file-xlsx', label: '/create-file-xlsx', desc: 'Excel-Tabelle', template: 'Erstelle eine Excel-Tabelle: ', group: 'Dokumente'},
  {cmd: '/create-file-pdf', label: '/create-file-pdf', desc: 'PDF erstellen', template: 'Erstelle ein PDF: ', group: 'Dokumente'},
  {cmd: '/create-file-pptx', label: '/create-file-pptx', desc: 'PowerPoint', template: 'Erstelle eine PowerPoint-Praesentation: ', group: 'Dokumente'},
  // ─── Canva ───
  {cmd: '/canva-search', label: '/canva-search [query]', desc: 'Designs durchsuchen', template: 'Suche in Canva nach: ', group: 'Canva'},
  {cmd: '/canva-create', label: '/canva-create [titel]', desc: 'Neues Design', template: 'Erstelle ein Canva Design: ', group: 'Canva'},
  {cmd: '/canva-templates', label: '/canva-templates', desc: 'Brand Templates', template: '', group: 'Canva'},
  {cmd: '/canva-campaign', label: '/canva-campaign', desc: 'Ad-Kampagne generieren', template: 'Erstelle eine Canva Kampagne mit Template: ', group: 'Canva'},
  {cmd: '/canva-export', label: '/canva-export [id] [format]', desc: 'Design exportieren', template: 'Exportiere Canva Design: ', group: 'Canva'},
  // ─── Suche (Agent) ───
  {cmd: '/find', label: '/find [query]', desc: 'Alle Dateien durchsuchen', group: 'Suche'},
  {cmd: '/find-email', label: '/find-email [query]', desc: 'Nur E-Mails', group: 'Suche'},
  {cmd: '/find-whatsapp', label: '/find-whatsapp [query]', desc: 'Nur WhatsApp', group: 'Suche'},
  {cmd: '/find-webclip', label: '/find-webclip [query]', desc: 'Web Clips', group: 'Suche'},
  {cmd: '/find-slack', label: '/find-slack [query]', desc: 'Slack Nachrichten', group: 'Suche'},
  {cmd: '/find-salesforce', label: '/find-salesforce [query]', desc: 'Salesforce Records', group: 'Suche'},
  {cmd: '/find-document', label: '/find-document [query]', desc: 'Dokumente', group: 'Suche'},
  {cmd: '/find-conversation', label: '/find-conversation [query]', desc: 'Konversationen', group: 'Suche'},
  {cmd: '/find-screenshot', label: '/find-screenshot [query]', desc: 'Screenshots', group: 'Suche'},
  // ─── Suche (Global) ───
  {cmd: '/find_global', label: '/find_global [query]', desc: 'Alle Agenten', group: 'Globale Suche'},
  {cmd: '/find_global-email', label: '/find_global-email [query]', desc: 'E-Mails global', group: 'Globale Suche'},
  {cmd: '/find_global-webclip', label: '/find_global-webclip [query]', desc: 'Web Clips global', group: 'Globale Suche'},
  {cmd: '/find_global-document', label: '/find_global-document [query]', desc: 'Dokumente global', group: 'Globale Suche'},
  {cmd: '/find_global-conversation', label: '/find_global-conversation [query]', desc: 'Konversationen global', group: 'Globale Suche'},
  {cmd: '/find_global-screenshot', label: '/find_global-screenshot [query]', desc: 'Screenshots global', group: 'Globale Suche'},
];"""

src = src.replace(old_array, new_array, 1)
print("  [OK] _SLASH_COMMANDS Array ersetzt (clustered)")


# 2. showSlashAutocomplete Renderer: Gruppen-Header anzeigen
OLD_RENDER = """  filtered.forEach((c, i) => {
    const item = document.createElement('div');
    item.className = 'slash-ac-item';
    item.dataset.cmd = c.cmd;
    item.innerHTML = '<strong>' + c.label + '</strong><span style="margin-left:8px;color:#888;font-size:12px">' + c.desc + '</span>';
    item.onmousedown = (e) => { e.preventDefault(); selectSlashCmd(inputEl, c.cmd); };
    dd.appendChild(item);
  });"""

NEW_RENDER = """  var lastGroup = '';
  filtered.forEach((c, i) => {
    // Gruppen-Header anzeigen wenn neue Gruppe beginnt
    if (c.group && c.group !== lastGroup) {
      lastGroup = c.group;
      var hdr = document.createElement('div');
      hdr.className = 'slash-ac-group';
      hdr.textContent = c.group;
      dd.appendChild(hdr);
    }
    const item = document.createElement('div');
    item.className = 'slash-ac-item';
    item.dataset.cmd = c.cmd;
    item.innerHTML = '<strong>' + c.label + '</strong><span style="margin-left:8px;color:#888;font-size:12px">' + c.desc + '</span>';
    item.onmousedown = (e) => { e.preventDefault(); selectSlashCmd(inputEl, c.cmd); };
    dd.appendChild(item);
  });"""

if src.count(OLD_RENDER) == 1:
    src = src.replace(OLD_RENDER, NEW_RENDER, 1)
    print("  [OK] Renderer mit Gruppen-Headern")
else:
    print(f"  [SKIP] Renderer: {src.count(OLD_RENDER)}")


# 3. CSS fuer Gruppen-Header
OLD_CSS = """  #slash-ac-dropdown"""
# Suche den bestehenden CSS-Block oder fuege neuen ein
# Erstmal pruefen ob slash-ac-dropdown CSS existiert
idx = src.find('#slash-ac-dropdown')
if idx == -1:
    # Kein bestehender CSS-Block — fuege vor </style> ein
    OLD_STYLE = "  .section-copy-btn.copied { color:#4caf50; border-color:#4caf50; opacity:1; }"
    NEW_STYLE = """  .section-copy-btn.copied { color:#4caf50; border-color:#4caf50; opacity:1; }
  /* SLASH_CLUSTER_V1: Gruppen-Header im Slash-Dropdown */
  .slash-ac-group { padding:6px 12px 3px; font-size:10px; color:#f0c060; font-weight:700; letter-spacing:1px; text-transform:uppercase; border-top:1px solid #2a2a2a; margin-top:2px; }
  .slash-ac-group:first-child { border-top:none; margin-top:0; }"""
    if src.count(OLD_STYLE) == 1:
        src = src.replace(OLD_STYLE, NEW_STYLE, 1)
        print("  [OK] CSS Gruppen-Header (via section-copy anchor)")
    else:
        print(f"  [SKIP] CSS: anchor nicht gefunden")
else:
    # Pruefe ob .slash-ac-group schon existiert
    if '.slash-ac-group' not in src:
        # Fuege nach dem vorhandenen #slash-ac-dropdown CSS-Block ein
        # Finde die Zeile und fuege danach ein
        line_end = src.find('\n', idx)
        # Suche nach dem Ende des CSS-Blocks (naechste Leerzeile oder naechster Selektor)
        insert_point = src.find('\n', line_end + 1)
        css_addition = "\n  .slash-ac-group { padding:6px 12px 3px; font-size:10px; color:#f0c060; font-weight:700; letter-spacing:1px; text-transform:uppercase; border-top:1px solid #2a2a2a; margin-top:2px; }\n  .slash-ac-group:first-child { border-top:none; margin-top:0; }"
        src = src[:insert_point] + css_addition + src[insert_point:]
        print("  [OK] CSS Gruppen-Header (nach slash-ac-dropdown)")
    else:
        print("  [SKIP] CSS schon vorhanden")


open(WS, 'w').write(src)
print(f"OK ({len(src)} bytes)")
