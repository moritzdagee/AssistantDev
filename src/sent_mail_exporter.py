#!/usr/bin/env python3
"""
Sent Mail Exporter
Exportiert gesendete E-Mails aus Apple Mail ins Agent-Memory.
Gleicher Dateinamen-Standard wie email_watcher v2.

Lauf: python3 ~/AssistantDev/src/sent_mail_exporter.py
Optionaler Parameter: max Anzahl Mails (Default: 500)
"""

import os
import json
import re
import datetime
import subprocess
import sys

BASE = os.path.expanduser("~/Library/Mobile Documents/com~apple~CloudDocs/Downloads shared/claude_datalake")
STATE_FILE = os.path.expanduser("~/.sent_mail_exporter_state.json")
OWN_ADDRS_CACHE = os.path.expanduser("~/.emailwatcher_own_addresses.json")
DEFAULT_AGENT = "standard"

ROUTING = [
    ("signicat", "signicat"),
    ("elavon", "signicat"),
    ("trustedcarrier", "trustedcarrier"),
    ("trusted carrier", "trustedcarrier"),
    ("tangerina", "privat"),
    ("privat", "privat"),
    ("family", "privat"),
    ("familie", "privat"),
]

# ── Hilfsfunktionen ──────────────────────────────────────────────────────────

def clean_for_filename(s, maxlen=55):
    s = re.sub(r'[^\w\s@.-]', ' ', str(s))
    s = re.sub(r'\s+', '_', s.strip())
    s = s.replace('@', '_at_').replace('.', '_')
    s = re.sub(r'_+', '_', s)
    return s[:maxlen].strip('_')


def route_agent(text):
    text = text.lower()
    for keyword, agent in ROUTING:
        if keyword in text:
            if os.path.exists(os.path.join(BASE, "config/agents", agent + ".txt")):
                return agent
    return DEFAULT_AGENT


def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {"exported_ids": []}


def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


def extract_email_addr(raw):
    m = re.search(r'[\w.+%-]+@[\w.-]+\.[a-zA-Z]{2,}', str(raw))
    return m.group(0).lower() if m else str(raw).lower().strip()


def parse_date(date_str):
    """Parse AppleScript date string to datetime."""
    # Format: "Monday, 6 April 2026 at 10:40:01"
    for fmt in [
        "%A, %d %B %Y at %H:%M:%S",
        "%A, %d %B %Y at %I:%M:%S %p",
        "%d/%m/%Y %H:%M:%S",
    ]:
        try:
            return datetime.datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return None

# ── AppleScript: Sent Mails lesen ────────────────────────────────────────────

def read_sent_mails_applescript(max_mails):
    """Liest Sent-Mails via AppleScript. Gibt Liste von Dicts zurueck."""
    script = f'''
tell application "Mail"
    set sentBox to sent mailbox
    set output to ""
    set maxCount to {max_mails}
    set msgCount to count of messages of sentBox
    if msgCount < maxCount then set maxCount to msgCount
    repeat with i from 1 to maxCount
        set msg to message i of sentBox
        set msgId to message id of msg
        set msgSubj to subject of msg
        set msgFrom to sender of msg
        set msgDate to date sent of msg
        set recipAddr to ""
        try
            set recipAddr to address of to recipient 1 of msg
        end try
        set msgBody to ""
        try
            set msgBody to content of msg
            if length of msgBody > 2000 then
                set msgBody to text 1 thru 2000 of msgBody
            end if
        end try
        -- Replace ||| in content to avoid delimiter collision
        set tid to AppleScript's text item delimiters
        set AppleScript's text item delimiters to "|||"
        set msgBody to text items of msgBody
        set AppleScript's text item delimiters to "---"
        set msgBody to msgBody as string
        set AppleScript's text item delimiters to tid
        set output to output & msgId & "|||" & msgSubj & "|||" & msgFrom & "|||" & recipAddr & "|||" & (msgDate as string) & "|||" & msgBody & "|||END" & linefeed
    end repeat
    return output
end tell
'''
    print(f"Lese {max_mails} Sent-Mails aus Apple Mail...")
    r = subprocess.run(['osascript', '-e', script], capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        print(f"AppleScript Fehler: {r.stderr}")
        return []

    mails = []
    for line in r.stdout.strip().split('\n'):
        line = line.strip()
        if not line or '|||' not in line:
            continue
        if line.endswith('|||END'):
            line = line[:-6]
        parts = line.split('|||')
        if len(parts) < 5:
            continue
        mails.append({
            'id': parts[0].strip(),
            'subject': parts[1].strip(),
            'from': parts[2].strip(),
            'to': parts[3].strip(),
            'date': parts[4].strip(),
            'body': parts[5].strip() if len(parts) > 5 else '',
        })
    print(f"  {len(mails)} Mails gelesen.")
    return mails

# ── Export ────────────────────────────────────────────────────────────────────

def export_sent_mails(max_mails=500):
    state = load_state()
    already_exported = set(state.get("exported_ids", []))

    mails = read_sent_mails_applescript(max_mails)
    if not mails:
        print("Keine Mails zum Exportieren.")
        return

    exported = 0
    skipped = 0
    agents_count = {}

    for m in mails:
        if m['id'] in already_exported:
            skipped += 1
            continue

        # Datum parsen
        dt = parse_date(m['date'])
        if dt:
            timestamp = dt.strftime("%Y-%m-%d_%H-%M-%S")
        else:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        # Immer OUT (sent folder)
        direction = "OUT"
        contact = extract_email_addr(m['to']) if m['to'] else "unknown"

        # Routing
        text = m['subject'] + " " + m['to'] + " " + m['body'][:500]
        agent = route_agent(text)

        memory_dir = os.path.join(BASE, agent, "memory")
        os.makedirs(memory_dir, exist_ok=True)

        # Dateiname
        contact_clean = clean_for_filename(contact, 40)
        subject_clean = clean_for_filename(m['subject'], 55)
        email_filename = f"{timestamp}_{direction}_{contact_clean}_{subject_clean}.txt"

        # Inhalt
        separator = '\u2500' * 60
        content = (f"Von: {m['from']}\n"
                   f"An: {m['to']}\n"
                   f"Betreff: {m['subject']}\n"
                   f"Datum: {m['date']}\n"
                   f"Richtung: {direction}\n"
                   f"Kontakt: {contact}\n"
                   f"Agent: {agent}\n"
                   f"Importiert: {datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}\n"
                   f"{separator}\n\n{m['body']}")

        filepath = os.path.join(memory_dir, email_filename)
        with open(filepath, 'w') as f:
            f.write(content)

        already_exported.add(m['id'])
        exported += 1
        agents_count[agent] = agents_count.get(agent, 0) + 1

        if exported % 50 == 0:
            print(f"  {exported} exportiert...")

    # State speichern
    state['exported_ids'] = list(already_exported)
    state['last_export'] = datetime.datetime.now().isoformat()
    save_state(state)

    print(f"\n{'=' * 45}")
    print(f"Sent-Mail Export abgeschlossen")
    print(f"  Exportiert: {exported}")
    print(f"  Uebersprungen (bereits exportiert): {skipped}")
    for agent, count in sorted(agents_count.items()):
        print(f"  -> {agent}: {count}")
    print(f"{'=' * 45}")


if __name__ == '__main__':
    max_mails = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    export_sent_mails(max_mails)
