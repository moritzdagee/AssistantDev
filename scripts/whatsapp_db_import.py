#!/usr/bin/env python3
"""
WhatsApp DB Import — Liest direkt aus der WhatsApp Mac App SQLite-Datenbank.
Importiert ALLE Chats automatisch – kein manueller Export noetig.

Nutzung:
  python3 whatsapp_db_import.py --agent privat
  python3 whatsapp_db_import.py --agent privat --min-messages 10
  python3 whatsapp_db_import.py --agent privat --contact "Marco"
  python3 whatsapp_db_import.py --agent privat --since 2026-01-01
  python3 whatsapp_db_import.py --agent privat --list  # Nur Chats auflisten

Wichtig: WhatsApp Mac App muss installiert sein. DB wird nur gelesen (read-only).
"""

import argparse
import datetime
import json
import os
import re
import shutil
import sqlite3
import sys

BASE = os.path.expanduser(
    "~/Library/Mobile Documents/com~apple~CloudDocs/Downloads shared/claude_datalake"
)

WA_DB = os.path.expanduser(
    "~/Library/Group Containers/group.net.whatsapp.WhatsApp.shared/ChatStorage.sqlite"
)

# Apple Core Data epoch offset (2001-01-01 00:00:00 UTC)
APPLE_EPOCH = 978307200

# Message types: 0=text, 1=image, 2=video, 3=voice, 5=location, 6=contact,
# 7=link/url, 8=doc/file, 10=deleted, 14=sticker, 15=gif, 59=reaction, 66=poll
MEDIA_TYPES = {1: 'Bild', 2: 'Video', 3: 'Sprachnachricht', 5: 'Standort',
               6: 'Kontakt', 8: 'Dokument', 14: 'Sticker', 15: 'GIF', 66: 'Umfrage'}
SKIP_TYPES = {10, 59}  # deleted, reactions — skip entirely

# Session types: 0=direct, 1=group, 2=community, 3=status/broadcast, 4=channel
VALID_SESSION_TYPES = {0, 1}  # Only direct + group chats


def apple_ts_to_iso(ts):
    """Convert Apple Core Data timestamp to ISO string."""
    if not ts:
        return None
    try:
        dt = datetime.datetime.utcfromtimestamp(ts + APPLE_EPOCH)
        return dt.strftime('%Y-%m-%d %H:%M')
    except (OSError, ValueError):
        return None


def apple_ts_to_date(ts):
    """Convert Apple Core Data timestamp to date string."""
    if not ts:
        return None
    try:
        dt = datetime.datetime.utcfromtimestamp(ts + APPLE_EPOCH)
        return dt.strftime('%Y-%m-%d')
    except (OSError, ValueError):
        return None


def sanitize_filename(name, max_len=50):
    """Make a string safe for filenames."""
    name = re.sub(r'[^\w\s-]', '', str(name), flags=re.UNICODE)
    name = re.sub(r'\s+', '_', name).strip('_')
    name = re.sub(r'_+', '_', name)
    return name[:max_len].strip('_') or 'Unbekannt'


def get_chats(db_path, min_messages=1, contact_filter=None, since_date=None):
    """Get all chat sessions from the WhatsApp DB."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    query = """
        SELECT Z_PK, ZPARTNERNAME, ZCONTACTJID, ZMESSAGECOUNTER,
               ZSESSIONTYPE, ZLASTMESSAGEDATE, ZLASTMESSAGETEXT
        FROM ZWACHATSESSION
        WHERE ZREMOVED = 0
          AND ZMESSAGECOUNTER >= ?
          AND ZSESSIONTYPE IN (0, 1)
    """
    params = [min_messages]

    if since_date:
        # Convert date to Apple timestamp
        dt = datetime.datetime.strptime(since_date, '%Y-%m-%d')
        apple_ts = dt.timestamp() - APPLE_EPOCH
        query += " AND ZLASTMESSAGEDATE >= ?"
        params.append(apple_ts)

    query += " ORDER BY ZLASTMESSAGEDATE DESC"
    cursor = conn.execute(query, params)
    chats = []

    # Pre-fetch actual message counts to skip archived/dead groups
    actual_counts = {}
    for row2 in conn.execute("SELECT ZCHATSESSION, COUNT(*) as cnt FROM ZWAMESSAGE GROUP BY ZCHATSESSION"):
        actual_counts[row2[0]] = row2[1]

    for row in cursor:
        name = row['ZPARTNERNAME'] or ''
        # Filter invisible unicode chars from name
        name = ''.join(c for c in name if c.isprintable()).strip()
        if not name:
            name = row['ZCONTACTJID'] or 'Unbekannt'

        if contact_filter and contact_filter.lower() not in name.lower():
            continue

        # Skip archived groups with no real messages in DB
        actual = actual_counts.get(row['Z_PK'], 0)
        if actual < min_messages:
            continue

        chats.append({
            'pk': row['Z_PK'],
            'name': name,
            'jid': row['ZCONTACTJID'] or '',
            'message_count': row['ZMESSAGECOUNTER'] or 0,
            'session_type': row['ZSESSIONTYPE'],
            'is_group': row['ZSESSIONTYPE'] == 1,
            'last_message_date': apple_ts_to_iso(row['ZLASTMESSAGEDATE']),
            'last_message_text': (row['ZLASTMESSAGETEXT'] or '')[:80],
        })

    conn.close()
    return chats


def get_messages(db_path, chat_pk, since_date=None, chat_name='', is_group=False):
    """Get all messages for a chat session."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    query = """
        SELECT ZISFROMME, ZPUSHNAME, ZTEXT, ZMESSAGETYPE, ZMESSAGEDATE, ZFROMJID
        FROM ZWAMESSAGE
        WHERE ZCHATSESSION = ?
    """
    params = [chat_pk]

    if since_date:
        dt = datetime.datetime.strptime(since_date, '%Y-%m-%d')
        apple_ts = dt.timestamp() - APPLE_EPOCH
        query += " AND ZMESSAGEDATE >= ?"
        params.append(apple_ts)

    query += " ORDER BY ZMESSAGEDATE ASC"
    cursor = conn.execute(query, params)
    messages = []

    for row in cursor:
        msg_type = row['ZMESSAGETYPE']
        if msg_type in SKIP_TYPES:
            continue

        ts = apple_ts_to_iso(row['ZMESSAGEDATE'])
        if not ts:
            continue

        is_from_me = row['ZISFROMME'] == 1
        text = row['ZTEXT'] or ''

        # Media messages
        if msg_type in MEDIA_TYPES:
            media_label = MEDIA_TYPES[msg_type]
            if text:
                text = f'[{media_label}] {text}'
            else:
                text = f'[{media_label}]'
        elif msg_type == 7 and text:
            # URL preview — keep text as-is
            pass
        elif not text:
            continue  # Skip empty non-media messages

        # Sender for group chats
        sender = 'Ich' if is_from_me else ''
        if not is_from_me:
            push = row['ZPUSHNAME']
            if push:
                # ZPUSHNAME contains binary data sometimes, extract readable part
                push = ''.join(c for c in push if c.isprintable()).strip()
                # Check if it's a readable name (not just base64/encoded junk)
                if push and not re.match(r'^[A-Za-z0-9+/=]{2,10}$', push):
                    sender = push
            if not sender:
                if not is_group and chat_name:
                    # Direct chat: other person is always the chat partner
                    sender = chat_name
                else:
                    # Group chat fallback: use JID phone number
                    jid = (row['ZFROMJID'] or '').split('@')[0]
                    if jid and len(jid) > 4:
                        sender = jid
                    else:
                        sender = '?'

        messages.append({
            'timestamp': ts,
            'sender': sender,
            'text': text,
            'is_from_me': is_from_me,
        })

    conn.close()
    return messages


def format_chat(contact, messages, is_group=False):
    """Format messages into the standard output text."""
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
        lines.append(f'[{msg["timestamp"]}] {msg["sender"]}: {msg["text"]}')

    return '\n'.join(lines)


def import_chat(chat, db_path, agent, since_date=None):
    """Import a single chat into AssistantDev memory."""
    messages = get_messages(db_path, chat['pk'], since_date, chat['name'], chat['is_group'])
    if not messages:
        return None

    output = format_chat(chat['name'], messages, chat['is_group'])

    whatsapp_dir = os.path.join(BASE, agent, 'memory', 'whatsapp')
    os.makedirs(whatsapp_dir, exist_ok=True)

    safe_name = sanitize_filename(chat['name'])
    group_tag = '_group' if chat['is_group'] else ''
    first_date = min(m['timestamp'][:10] for m in messages)
    fname = f'whatsapp_chat{group_tag}_{safe_name}_{first_date}.txt'
    fpath = os.path.join(whatsapp_dir, fname)

    with open(fpath, 'w', encoding='utf-8') as f:
        f.write(output)

    # Mirror to Downloads shared/whatsapp/ for global access
    shared_wa_dir = os.path.join(os.path.dirname(BASE), 'whatsapp')
    os.makedirs(shared_wa_dir, exist_ok=True)
    shared_path = os.path.join(shared_wa_dir, f'{agent}_{fname}')
    with open(shared_path, 'w', encoding='utf-8') as f:
        f.write(output)

    return {
        'contact': chat['name'],
        'filename': fname,
        'path': fpath,
        'message_count': len(messages),
        'first_date': first_date,
        'last_date': max(m['timestamp'][:10] for m in messages),
        'is_group': chat['is_group'],
    }


def update_metadata(agent, imports):
    """Update whatsapp_metadata.json."""
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
    meta['source'] = 'sqlite_direct'

    with open(meta_path, 'w') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def trigger_index_rebuild(agent):
    """Trigger search index rebuild."""
    try:
        sys.path.insert(0, os.path.expanduser('~/AssistantDev/src'))
        from search_engine import SearchIndex
        speicher = os.path.join(BASE, agent)
        idx = SearchIndex(speicher)
        idx.build_or_update()
        print(f"\n  \u2713 Such-Index aktualisiert fuer Agent '{agent}'")
    except Exception as e:
        print(f"\n  \u26a0 Index-Update fehlgeschlagen: {e}")


def main():
    parser = argparse.ArgumentParser(
        description='WhatsApp DB Import — Liest direkt aus der WhatsApp SQLite-Datenbank'
    )
    parser.add_argument('--agent', required=True, help='Ziel-Agent (z.B. privat)')
    parser.add_argument('--min-messages', type=int, default=5,
                        help='Minimum Nachrichten pro Chat (Default: 5)')
    parser.add_argument('--contact', help='Nur Chats mit diesem Kontaktnamen importieren')
    parser.add_argument('--since', help='Nur Nachrichten ab Datum (YYYY-MM-DD)')
    parser.add_argument('--list', action='store_true',
                        help='Nur Chats auflisten, nicht importieren')
    parser.add_argument('--db', default=WA_DB, help='Pfad zur ChatStorage.sqlite')
    args = parser.parse_args()

    # Validate
    if not os.path.exists(args.db):
        print(f"\u2717 WhatsApp DB nicht gefunden: {args.db}")
        print("  Ist WhatsApp Mac App installiert?")
        sys.exit(1)

    agent_dir = os.path.join(BASE, args.agent)
    if not os.path.exists(agent_dir):
        print(f"\u2717 Agent-Ordner nicht gefunden: {agent_dir}")
        sys.exit(1)

    # Copy DB to temp location (avoid locking issues if WhatsApp is open)
    import tempfile
    tmp_db = os.path.join(tempfile.gettempdir(), 'wa_chatstorage_copy.sqlite')
    shutil.copy2(args.db, tmp_db)

    print(f"WhatsApp DB Import \u2192 Agent: {args.agent}")
    print(f"{'='*60}")

    chats = get_chats(tmp_db, args.min_messages, args.contact, args.since)
    print(f"Gefunden: {len(chats)} Chats (min. {args.min_messages} Nachrichten)\n")

    if args.list:
        print(f"{'Name':<35} {'Typ':<8} {'Msgs':>6} {'Letzte Nachricht':<20}")
        print('-' * 75)
        for c in chats:
            ctype = 'Gruppe' if c['is_group'] else 'Direkt'
            print(f"{c['name'][:34]:<35} {ctype:<8} {c['message_count']:>6} {c['last_message_date'] or '?':<20}")
        print(f"\nGesamt: {sum(c['message_count'] for c in chats)} Nachrichten in {len(chats)} Chats")
        os.unlink(tmp_db)
        return

    imports = []
    for i, chat in enumerate(chats, 1):
        ctype = 'Gruppe' if chat['is_group'] else 'Direkt'
        print(f"  [{i}/{len(chats)}] {chat['name']} ({ctype}, {chat['message_count']} msgs)...", end=' ')
        result = import_chat(chat, tmp_db, args.agent, args.since)
        if result:
            imports.append(result)
            print(f"\u2713 {result['message_count']} Nachrichten")
        else:
            print("- keine Nachrichten")

    os.unlink(tmp_db)

    print(f"\n{'='*60}")
    if imports:
        update_metadata(args.agent, imports)
        trigger_index_rebuild(args.agent)
        total_msgs = sum(i['message_count'] for i in imports)
        print(f"\n\u2713 {len(imports)} Chats importiert ({total_msgs} Nachrichten total)")
    else:
        print("\u26a0 Keine Chats importiert.")


if __name__ == '__main__':
    main()
