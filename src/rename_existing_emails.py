#!/usr/bin/env python3
"""
Rename Existing Emails
Benennt alle bestehenden email_*.txt und *.eml Dateien in Agent-Memory-Ordnern
nach dem neuen Schema um: DATUM_UHRZEIT_IN/OUT_KONTAKT_BETREFF.txt

Lauf: python3 ~/AssistantDev/src/rename_existing_emails.py
Trockenlauf: python3 ~/AssistantDev/src/rename_existing_emails.py --dry-run
"""

import os
import re
import json
import datetime
import email
import sys
from email.header import decode_header

BASE = os.path.expanduser("~/Library/Mobile Documents/com~apple~CloudDocs/Downloads shared/claude_datalake")
OWN_ADDRS_CACHE = os.path.expanduser("~/.emailwatcher_own_addresses.json")

AGENTS = ["signicat", "trustedcarrier", "privat", "standard"]
DRY_RUN = "--dry-run" in sys.argv


def get_own_addresses():
    if os.path.exists(OWN_ADDRS_CACHE):
        try:
            with open(OWN_ADDRS_CACHE) as f:
                return [a.lower() for a in json.load(f)]
        except Exception:
            pass
    return ["moritz.cremer@me.com", "moritz.cremer@icloud.com",
            "moritz.cremer@signicat.com", "londoncityfox@gmail.com",
            "moritz@demoscapital.co", "moritz@vegatechnology.com.br",
            "moritz.cremer@trustedcarrier.net"]


def is_own(addr):
    return addr.lower().strip() in get_own_addresses()


def extract_email_addr(raw):
    m = re.search(r'[\w.+%-]+@[\w.-]+\.[a-zA-Z]{2,}', str(raw))
    return m.group(0).lower() if m else str(raw).lower().strip()


def clean_for_filename(s, maxlen=55):
    s = re.sub(r'[^\w\s@.-]', ' ', str(s))
    s = re.sub(r'\s+', '_', s.strip())
    s = s.replace('@', '_at_').replace('.', '_')
    s = re.sub(r'_+', '_', s)
    return s[:maxlen].strip('_')


def decode_str(s):
    if not s:
        return ''
    try:
        parts = decode_header(s)
        result = []
        for part, enc in parts:
            if isinstance(part, bytes):
                result.append(part.decode(enc or 'utf-8', errors='ignore'))
            else:
                result.append(str(part))
        return ' '.join(result).strip()
    except Exception:
        return str(s)


def parse_header_from_txt(filepath):
    """Parse Von/An/Betreff/Datum from processed email_*.txt files."""
    headers = {}
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('\u2500'):
                    break
                for key in ['Von', 'An', 'Betreff', 'Datum']:
                    if line.startswith(key + ': '):
                        headers[key] = line[len(key) + 2:]
                        break
    except Exception:
        pass
    return headers


def parse_eml_file(filepath):
    """Parse headers from raw .eml file."""
    try:
        with open(filepath, 'rb') as f:
            msg = email.message_from_bytes(f.read(20000))
        return {
            'Von': decode_str(msg.get('From', '')),
            'An': decode_str(msg.get('To', '')),
            'Betreff': decode_str(msg.get('Subject', '')),
            'Datum': str(msg.get('Date', '')),
        }
    except Exception:
        return {}


def determine_timestamp(headers, filepath):
    """Determine timestamp from Datum header or file mtime."""
    date_str = headers.get('Datum', '')
    if date_str:
        # Try common date formats
        for fmt in [
            "%a, %d %b %Y %H:%M:%S %z",
            "%a, %d %b %Y %H:%M:%S %Z",
            "%d %b %Y %H:%M:%S %z",
            "%Y-%m-%dT%H:%M:%S",
        ]:
            try:
                dt = datetime.datetime.strptime(date_str.strip(), fmt)
                return dt.strftime("%Y-%m-%d_%H-%M-%S")
            except ValueError:
                continue
        # Try with regex to extract date parts
        m = re.search(r'(\d{1,2})\s+(\w{3})\s+(\d{4})\s+(\d{2}):(\d{2}):(\d{2})', date_str)
        if m:
            months = {'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04', 'May': '05', 'Jun': '06',
                      'Jul': '07', 'Aug': '08', 'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'}
            month = months.get(m.group(2), '01')
            return f"{m.group(3)}-{month}-{int(m.group(1)):02d}_{m.group(4)}-{m.group(5)}-{m.group(6)}"
    # Fallback: file mtime
    try:
        mtime = os.path.getmtime(filepath)
        return datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d_%H-%M-%S")
    except Exception:
        return datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def rename_file(filepath, headers):
    """Generate new filename and rename."""
    sender_addr = extract_email_addr(headers.get('Von', ''))
    to_addr = extract_email_addr(headers.get('An', '').split(',')[0])
    subject = headers.get('Betreff', 'kein_betreff')

    if is_own(sender_addr):
        direction = "OUT"
        contact = to_addr
    else:
        direction = "IN"
        contact = sender_addr

    timestamp = determine_timestamp(headers, filepath)
    contact_clean = clean_for_filename(contact, 40)
    subject_clean = clean_for_filename(subject, 55)
    new_name = f"{timestamp}_{direction}_{contact_clean}_{subject_clean}.txt"

    dirpath = os.path.dirname(filepath)
    new_path = os.path.join(dirpath, new_name)

    # Avoid collision
    if os.path.exists(new_path) and new_path != filepath:
        base, ext = os.path.splitext(new_name)
        new_name = f"{base}_2{ext}"
        new_path = os.path.join(dirpath, new_name)

    return new_path, new_name


def main():
    own_addrs = get_own_addresses()
    print(f"Rename Existing Emails {'(DRY RUN)' if DRY_RUN else ''}")
    print(f"Eigene Adressen: {own_addrs}")
    print(f"{'=' * 50}")

    total = 0
    renamed = 0
    skipped = 0
    errors = 0

    for agent in AGENTS:
        memory_dir = os.path.join(BASE, agent, "memory")
        if not os.path.isdir(memory_dir):
            continue

        agent_renamed = 0
        files = os.listdir(memory_dir)

        for fname in files:
            # Skip already renamed files (have _IN_ or _OUT_ pattern)
            if re.search(r'_IN_|_OUT_', fname):
                continue

            filepath = os.path.join(memory_dir, fname)
            if not os.path.isfile(filepath):
                continue

            headers = None

            # Process email_*.txt files
            if fname.startswith('email_') and fname.endswith('.txt'):
                headers = parse_header_from_txt(filepath)
            # Process .eml files in memory (raw copies from distribution)
            elif fname.endswith('.eml'):
                headers = parse_eml_file(filepath)
            else:
                continue

            if not headers or not headers.get('Von'):
                skipped += 1
                continue

            total += 1
            try:
                new_path, new_name = rename_file(filepath, headers)
                if DRY_RUN:
                    if total <= 20:
                        print(f"  {agent}: {fname[:60]} -> {new_name[:60]}")
                else:
                    os.rename(filepath, new_path)
                renamed += 1
                agent_renamed += 1
            except Exception as e:
                errors += 1
                if errors <= 10:
                    print(f"  FEHLER: {fname}: {e}")

        if agent_renamed > 0 or DRY_RUN:
            print(f"  {agent}: {agent_renamed} umbenannt")

    print(f"\n{'=' * 50}")
    print(f"Ergebnis:")
    print(f"  Verarbeitet: {total}")
    print(f"  Umbenannt: {renamed}")
    print(f"  Uebersprungen: {skipped}")
    print(f"  Fehler: {errors}")


if __name__ == '__main__':
    main()
