#!/usr/bin/env python3
"""
WhatsApp Chat Import — Liest native WhatsApp-Export ZIPs und speichert sie
als durchsuchbare Textdateien im AssistantDev Memory.

Nutzung:
  python3 whatsapp_import.py --zip ~/Downloads/WhatsApp-Chat-Marco.zip --agent privat
  python3 whatsapp_import.py --folder ~/Downloads/WhatsApp-Exports/ --agent privat
"""

import argparse
import datetime
import json
import os
import re
import sys
import tempfile
import zipfile

BASE = os.path.expanduser(
    "~/Library/Mobile Documents/com~apple~CloudDocs/Downloads shared/claude_datalake"
)

# Regex for WhatsApp message lines — supports both DE and EN date formats
# DE: [02.04.26, 14:30:15]  or  [02.04.2026, 14:30:15]
# EN: [4/2/26, 2:30:15 PM]  or  [2026-04-02, 14:30:15]
RE_MSG_DE = re.compile(
    r'\[(\d{2})\.(\d{2})\.(\d{2,4}),\s*(\d{2}:\d{2}:\d{2})\]\s+(.+?):\s+(.*)'
)
RE_MSG_EN = re.compile(
    r'\[(\d{1,2})/(\d{1,2})/(\d{2,4}),\s*(\d{1,2}:\d{2}:\d{2}(?:\s*[AP]M)?)\]\s+(.+?):\s+(.*)'
)
# System messages (no sender)
RE_SYSTEM = re.compile(
    r'\[(\d{2})\.(\d{2})\.(\d{2,4}),\s*(\d{2}:\d{2}:\d{2})\]\s+(.*)'
)

# Own name patterns (configurable)
OWN_NAMES = {'moritz cremer', 'moritz', 'ich', 'me', 'you'}

MEDIA_PLACEHOLDER = {'<medien weggelassen>', '<media omitted>', '<mídia omitida>'}


class WhatsAppParser:
    """Parse WhatsApp _chat.txt export format."""

    @staticmethod
    def parse_line(line):
        """Parse a single WhatsApp message line. Returns dict or None."""
        line = line.strip()
        if not line:
            return None

        # Try DE format first
        m = RE_MSG_DE.match(line)
        if m:
            day, month, year, time_str, sender, text = m.groups()
            year = WhatsAppParser._normalize_year(year)
            timestamp = f"{year}-{month}-{day}T{time_str}"
            is_media = text.strip().lower() in MEDIA_PLACEHOLDER
            return {
                'timestamp': timestamp,
                'sender': sender.strip(),
                'text': '[Medien]' if is_media else text,
                'is_media': is_media,
                'is_own': sender.strip().lower() in OWN_NAMES,
            }

        # Try EN format
        m = RE_MSG_EN.match(line)
        if m:
            month, day, year, time_str, sender, text = m.groups()
            year = WhatsAppParser._normalize_year(year)
            day = day.zfill(2)
            month = month.zfill(2)
            # Convert 12h to 24h if needed
            time_24 = WhatsAppParser._to_24h(time_str)
            timestamp = f"{year}-{month}-{day}T{time_24}"
            is_media = text.strip().lower() in MEDIA_PLACEHOLDER
            return {
                'timestamp': timestamp,
                'sender': sender.strip(),
                'text': '[Medien]' if is_media else text,
                'is_media': is_media,
                'is_own': sender.strip().lower() in OWN_NAMES,
            }

        return None

    @staticmethod
    def _normalize_year(y):
        if len(y) == 2:
            return '20' + y
        return y

    @staticmethod
    def _to_24h(time_str):
        time_str = time_str.strip()
        if 'AM' in time_str.upper() or 'PM' in time_str.upper():
            try:
                dt = datetime.datetime.strptime(time_str, '%I:%M:%S %p')
                return dt.strftime('%H:%M:%S')
            except ValueError:
                pass
        return time_str

    @staticmethod
    def parse_chat(text):
        """Parse full chat text into list of messages."""
        messages = []
        current = None

        for line in text.split('\n'):
            parsed = WhatsAppParser.parse_line(line)
            if parsed:
                if current:
                    messages.append(current)
                current = parsed
            elif current and line.strip():
                # Continuation of previous message
                current['text'] += '\n' + line.strip()

        if current:
            messages.append(current)
        return messages

    @staticmethod
    def detect_contact(messages):
        """Detect the main contact name (not own messages)."""
        senders = {}
        for msg in messages:
            if not msg['is_own']:
                name = msg['sender']
                senders[name] = senders.get(name, 0) + 1
        if not senders:
            return 'Unbekannt'
        return max(senders, key=senders.get)

    @staticmethod
    def detect_group(messages):
        """Detect if this is a group chat (3+ unique senders)."""
        senders = set()
        for msg in messages:
            senders.add(msg['sender'].lower())
        return len(senders) >= 3


def format_output(contact, messages, is_group=False):
    """Format parsed messages into the output text format."""
    if not messages:
        return ''

    dates = [m['timestamp'][:10] for m in messages]
    first_date = min(dates)
    last_date = max(dates)

    chat_type = 'Gruppenchat' if is_group else 'Chat'
    lines = [
        f'=== WhatsApp {chat_type}: {contact} ===',
        f'Kontakt: {contact}',
        f'Zeitraum: {first_date} bis {last_date}',
        f'Nachrichten: {len(messages)}',
        '',
    ]

    for msg in messages:
        ts = msg['timestamp'][:16].replace('T', ' ')
        sender = 'Ich' if msg['is_own'] else msg['sender']
        lines.append(f'[{ts}] {sender}: {msg["text"]}')

    return '\n'.join(lines)


def sanitize_contact_name(name):
    """Make contact name safe for filenames."""
    name = re.sub(r'[^a-zA-Z0-9äöüÄÖÜß _-]', '', name)
    name = re.sub(r'\s+', '_', name).strip('_')
    return name[:50] or 'Unbekannt'


def process_zip(zip_path, agent):
    """Process a single WhatsApp export ZIP."""
    print(f"  Verarbeite: {os.path.basename(zip_path)}")

    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(tmpdir)

        # Find _chat.txt
        chat_file = None
        for root, dirs, files in os.walk(tmpdir):
            for f in files:
                if f == '_chat.txt' or f.endswith('_chat.txt'):
                    chat_file = os.path.join(root, f)
                    break
            if chat_file:
                break

        if not chat_file:
            print(f"    ✗ Keine _chat.txt gefunden in {zip_path}")
            return None

        # Read with UTF-8 fallback to Latin-1
        try:
            with open(chat_file, 'r', encoding='utf-8') as f:
                text = f.read()
        except UnicodeDecodeError:
            with open(chat_file, 'r', encoding='latin-1') as f:
                text = f.read()

    # Parse
    messages = WhatsAppParser.parse_chat(text)
    if not messages:
        print(f"    ✗ Keine Nachrichten erkannt in {zip_path}")
        return None

    contact = WhatsAppParser.detect_contact(messages)
    is_group = WhatsAppParser.detect_group(messages)
    print(f"    Kontakt: {contact} | Nachrichten: {len(messages)} | Gruppe: {is_group}")

    # Build output
    output_text = format_output(contact, messages, is_group)

    # Save
    whatsapp_dir = os.path.join(BASE, agent, 'memory', 'whatsapp')
    os.makedirs(whatsapp_dir, exist_ok=True)

    first_date = min(m['timestamp'][:10] for m in messages)
    safe_contact = sanitize_contact_name(contact)
    group_tag = '_group' if is_group else ''
    fname = f'whatsapp_chat{group_tag}_{safe_contact}_{first_date}.txt'
    fpath = os.path.join(whatsapp_dir, fname)

    with open(fpath, 'w', encoding='utf-8') as f:
        f.write(output_text)
    print(f"    ✓ Gespeichert: {fname}")

    return {
        'contact': contact,
        'filename': fname,
        'path': fpath,
        'message_count': len(messages),
        'first_date': first_date,
        'last_date': max(m['timestamp'][:10] for m in messages),
        'is_group': is_group,
    }


def update_metadata(agent, imports):
    """Update whatsapp_metadata.json with import info."""
    meta_path = os.path.join(BASE, agent, 'memory', 'whatsapp', 'whatsapp_metadata.json')
    meta = {'imported_chats': [], 'last_sync': None}

    if os.path.exists(meta_path):
        try:
            with open(meta_path, 'r') as f:
                meta = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass

    existing = {c['contact']: c for c in meta.get('imported_chats', [])}
    for imp in imports:
        existing[imp['contact']] = {
            'contact': imp['contact'],
            'last_imported': datetime.date.today().isoformat(),
            'message_count': imp['message_count'],
            'first_date': imp['first_date'],
            'last_date': imp['last_date'],
            'is_group': imp.get('is_group', False),
        }

    meta['imported_chats'] = list(existing.values())
    meta['last_import'] = datetime.datetime.now().isoformat()

    with open(meta_path, 'w') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"  ✓ Metadata aktualisiert: {meta_path}")


def trigger_index_rebuild(agent):
    """Trigger search index rebuild for the agent."""
    try:
        sys.path.insert(0, os.path.expanduser('~/AssistantDev/src'))
        from search_engine import SearchIndex
        speicher = os.path.join(BASE, agent)
        idx = SearchIndex(speicher)
        idx.build_or_update()
        print(f"  ✓ Such-Index aktualisiert fuer Agent '{agent}'")
    except Exception as e:
        print(f"  ⚠ Index-Update fehlgeschlagen: {e}")


def main():
    parser = argparse.ArgumentParser(description='WhatsApp Chat Import fuer AssistantDev')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--zip', help='Pfad zu einer WhatsApp-Export ZIP-Datei')
    group.add_argument('--folder', help='Ordner mit mehreren WhatsApp-Export ZIPs')
    parser.add_argument('--agent', required=True, help='Ziel-Agent (z.B. privat, signicat)')
    args = parser.parse_args()

    # Validate agent
    agent_dir = os.path.join(BASE, args.agent)
    if not os.path.exists(agent_dir):
        print(f"✗ Agent-Ordner nicht gefunden: {agent_dir}")
        sys.exit(1)

    print(f"WhatsApp Import → Agent: {args.agent}")
    print(f"{'='*50}")

    imports = []

    if args.zip:
        if not os.path.exists(args.zip):
            print(f"✗ Datei nicht gefunden: {args.zip}")
            sys.exit(1)
        result = process_zip(args.zip, args.agent)
        if result:
            imports.append(result)

    elif args.folder:
        if not os.path.isdir(args.folder):
            print(f"✗ Ordner nicht gefunden: {args.folder}")
            sys.exit(1)
        zips = sorted(f for f in os.listdir(args.folder) if f.lower().endswith('.zip'))
        print(f"Gefunden: {len(zips)} ZIP-Dateien")
        for zf in zips:
            result = process_zip(os.path.join(args.folder, zf), args.agent)
            if result:
                imports.append(result)

    print(f"\n{'='*50}")
    if imports:
        update_metadata(args.agent, imports)
        trigger_index_rebuild(args.agent)
        print(f"\n✓ {len(imports)} Chat(s) importiert:")
        for imp in imports:
            print(f"  - {imp['contact']}: {imp['message_count']} Nachrichten ({imp['first_date']} bis {imp['last_date']})")
    else:
        print("⚠ Keine Chats importiert.")


if __name__ == '__main__':
    main()
