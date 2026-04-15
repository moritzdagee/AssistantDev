#!/usr/bin/env python3
"""
Kontakt-Analyse fuer Agent Memory
Liest alle E-Mail-Dateien ein und erstellt eine contacts.json + menschenlesbaren Report.

Usage: python3 ~/analyze_contacts.py [--months N] [--agent AGENT]
"""

import os
import re
import json
import argparse
import datetime
from collections import defaultdict

BASE = os.path.expanduser(
    "~/Library/Mobile Documents/com~apple~CloudDocs/Downloads shared/claude_datalake"
)
OUTPUT_DIR = os.path.expanduser(
    "~/Library/Mobile Documents/com~apple~CloudDocs/Downloads shared/claude_outputs"
)

OWN_EMAILS = {
    "moritz.cremer@me.com", "moritz.cremer@icloud.com",
    "moritz.cremer@signicat.com", "londoncityfox@gmail.com",
    "moritz@demoscapital.co", "moritz@vegatechnology.com.br",
    "moritz.cremer@trustedcarrier.net",
}

# Notification-Absender die NICHT als Kontakte gespeichert werden
NOTIFICATION_PATTERNS = [
    re.compile(r'no[-_.]?reply', re.I),
    re.compile(r'noreply', re.I),
    re.compile(r'^notifications?@', re.I),
    re.compile(r'@.*\.mail\.microsoft', re.I),         # Teams, Outlook
    re.compile(r'@slack\.com', re.I),
    re.compile(r'@.*atlassian\.net', re.I),             # Confluence, Jira
    re.compile(r'@sharepointonline\.com', re.I),
    re.compile(r'@.*hibob\.com', re.I),
    re.compile(r'@.*winningtemp\.com', re.I),
    re.compile(r'@.*teamtailor', re.I),
    re.compile(r'@.*dokobit\.com', re.I),
    re.compile(r'@docs\.google\.com', re.I),
    re.compile(r'@email\.apple\.com', re.I),
    re.compile(r'^support@', re.I),
    re.compile(r'^invoiceapproval@', re.I),
    re.compile(r'srm-info\.no-reply@', re.I),
    re.compile(r'@.*\.aiwork\.app', re.I),
    re.compile(r'^info@e\.atlassian\.com$', re.I),
]

# Name-Suffixe die entfernt werden (Notification-Formate)
NAME_CLEANUP_PATTERNS = [
    re.compile(r'\s*\((?:via\s+\w+|Confluence|Google\s+Slides?|Google\s+Docs?|Jira|Teams?)\)\s*$', re.I),
    re.compile(r'^Sie haben neue\s+.*$', re.I),  # Deutsche Teams-Notifications
]

# Regex fuer Email-Dateien: YYYY-MM-DD_HH-MM-SS_IN/OUT_KONTAKT_BETREFF.txt
EMAIL_PATTERN = re.compile(
    r'^(\d{4}-\d{2}-\d{2})_(\d{2}-\d{2}-\d{2})_(IN|OUT)_(.+)\.txt$'
)

# Signatur-Extraktion
PHONE_PATTERNS = [
    re.compile(r'(?:Tel|Phone|Mob|Mobile|Fon|Telefon|Direct|Cell)[.:)]*\s*([+\d][\d\s./-]{7,18}\d)', re.I),
    re.compile(r'(?:^|\n)\s*(\+\d{1,3}[\s.-]?\d[\d\s.-]{6,16}\d)\s*$', re.M),
]
TITLE_PATTERNS = [
    re.compile(r'(?:^|\n)\s*((?:Chief|Head|Director|VP|Vice President|Manager|Senior|Lead|Principal|Associate|Partner|CEO|CTO|CFO|COO|CSO|CMO|CIO|SVP|EVP)[^\n]{2,60})\s*(?:\n|$)', re.I),
    re.compile(r'(?:^|\n)\s*([\w\s]+(?:Officer|Manager|Director|Consultant|Analyst|Engineer|Architect|Specialist|Advisor|Strategist|Developer))\s*(?:\n|$)', re.I),
]


def is_notification_sender(email_addr):
    """Prueft ob eine E-Mail-Adresse ein automatischer Absender ist."""
    for pat in NOTIFICATION_PATTERNS:
        if pat.search(email_addr):
            return True
    return False


def clean_name(name):
    """Entfernt Notification-Suffixe und bereinigt den Namen."""
    if not name:
        return name
    for pat in NAME_CLEANUP_PATTERNS:
        if pat.match(name):
            return None  # Ganzer Name ist ein Notification-Artefakt
        name = pat.sub('', name)
    return name.strip() if name.strip() else None


def extract_email_from_header(content, direction):
    """Extrahiert die Kontakt-E-Mail aus den Von/An Headern."""
    for line in content.split('\n')[:8]:
        if direction == 'IN' and line.startswith('Von:'):
            m = re.search(r'[\w.+%-]+@[\w.-]+\.[a-zA-Z]{2,}', line)
            if m:
                return m.group(0).lower()
        elif direction == 'OUT' and line.startswith('An:'):
            # Alle E-Mail-Adressen im An-Feld pruefen, erste nicht-eigene zurueck
            for m in re.finditer(r'[\w.+%-]+@[\w.-]+\.[a-zA-Z]{2,}', line):
                addr = m.group(0).lower()
                if addr not in OWN_EMAILS:
                    return addr
    return None


def company_from_domain(email_addr):
    """Extrahiert Firmenname aus E-Mail-Domain."""
    m = re.search(r'@([\w.-]+)', email_addr)
    if not m:
        return "Unknown"
    domain = m.group(1).lower()
    # Generische Domains ignorieren
    generic = {'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com',
               'icloud.com', 'me.com', 'live.com', 'aol.com', 'protonmail.com',
               'gmx.de', 'gmx.net', 'web.de', 'mail.com', 'googlemail.com'}
    if domain in generic:
        return "(Persoenlich)"
    # Domain ohne TLD als Firmenname
    parts = domain.split('.')
    if len(parts) >= 2:
        return parts[-2].capitalize()
    return domain.capitalize()


def extract_name_from_header_name(content, direction):
    """Extrahiert den Namen aus dem Von/An Header basierend auf Richtung."""
    target = 'Von:' if direction == 'IN' else 'An:'
    for line in content.split('\n')[:8]:
        if line.startswith(target):
            m = re.search(r'(.+?)\s*<[\w.+%-]+@', line[len(target):])
            if m:
                name = m.group(1).strip().strip('"\'').strip(',')
                if name and '@' not in name and len(name) > 1:
                    return name
    return None


def extract_sender_section(content):
    """Extrahiert nur den Teil der E-Mail, der vom Absender stammt.

    Schneidet weitergeleitete/zitierte Inhalte ab, indem nach
    Forwarding-Markern und eingebetteten 'From:'-Headern gesucht wird.
    """
    # Suche nach Forward/Quote-Markern die fremde Inhalte einleiten
    forward_markers = [
        re.compile(r'^-{4,}\s*(?:Forwarded|Original|Weitergeleitete)', re.M | re.I),
        re.compile(r'^_{4,}\s*$', re.M),  # Outlook-Trennlinie (______)
        re.compile(r'^\s*From:\s+.+@.+\..+\s*$', re.M),  # Eingebetteter From-Header
        re.compile(r'^\s*Von:\s+.+@.+\..+\s*$', re.M),   # Deutsch
        re.compile(r'^>\s*From:', re.M),
    ]

    # Ueberspringe die ersten 10 Zeilen (Original-Header des Absenders)
    lines = content.split('\n')
    body_start = min(10, len(lines))
    body = '\n'.join(lines[body_start:])

    earliest_cut = len(body)
    for marker in forward_markers:
        m = marker.search(body)
        if m and m.start() < earliest_cut:
            earliest_cut = m.start()

    sender_text = '\n'.join(lines[:body_start]) + '\n' + body[:earliest_cut]
    return sender_text


def extract_signature_info(content, sender_name=None, sender_email=None):
    """Extrahiert Titel und Telefon aus der E-Mail-Signatur des ABSENDERS.

    Nur die Signatur des Absenders wird beruecksichtigt, nicht Signaturen
    aus weitergeleiteten oder zitierten E-Mails.
    """
    title = None
    phone = None

    # Nur den Absender-Abschnitt verwenden (vor Forwards/Quotes)
    sender_section = extract_sender_section(content)

    # Signatur ist typischerweise nach den letzten "Best regards" o.ae.
    sig_start = None
    for marker in ['Best regards', 'Best Regards', 'Kind regards', 'Regards',
                    'Mit freundlichen', 'Viele Gruesse', 'Greetings', 'Cheers',
                    'Thanks', 'Thank you', 'BR,', 'VG,', 'LG,', 'MfG']:
        idx = sender_section.rfind(marker)
        if idx != -1:
            sig_start = idx
            break

    if sig_start is None:
        # Keine Gruessformel gefunden → letzte 800 Zeichen des Absender-Abschnitts
        sig_text = sender_section[-800:]
    else:
        sig_text = sender_section[sig_start:]

    # Validierung: Signatur muss zum Absender passen
    # Wenn der Absender-Name bekannt ist, pruefen ob er in der Signatur vorkommt
    if sender_name and sig_text:
        name_parts = sender_name.lower().split()
        # Mindestens Nachname muss in der Signatur vorkommen
        sig_lower = sig_text.lower()
        name_match = any(part in sig_lower for part in name_parts if len(part) > 2)
        email_match = sender_email and sender_email.split('@')[0].replace('.', ' ').lower() in sig_lower
        if not name_match and not email_match:
            # Signatur gehoert wahrscheinlich nicht zum Absender
            return None, None

    for pat in PHONE_PATTERNS:
        m = pat.search(sig_text)
        if m:
            phone = re.sub(r'\s+', ' ', m.group(1).strip())
            break

    for pat in TITLE_PATTERNS:
        m = pat.search(sig_text)
        if m:
            candidate = m.group(1).strip()
            # Filter: zu kurz oder zu lang -> skip
            if 5 < len(candidate) < 80:
                # Titel darf nicht den Namen einer anderen Person enthalten
                if sender_name:
                    # Pruefe ob der Titel mit einem fremden Namen beginnt
                    first_word = candidate.split()[0] if candidate.split() else ''
                    sender_parts = [p.lower() for p in sender_name.split() if len(p) > 2]
                    # Wenn das erste Wort ein Name ist der NICHT zum Absender gehoert → skip
                    if first_word[0].isupper() and first_word.lower() not in sender_parts:
                        # Koennte ein Titel-Keyword sein (Chief, Director etc.)
                        title_keywords = {'chief', 'head', 'director', 'vp', 'vice', 'manager',
                                          'senior', 'lead', 'principal', 'associate', 'partner',
                                          'ceo', 'cto', 'cfo', 'coo', 'officer', 'consultant'}
                        if first_word.lower() not in title_keywords:
                            continue  # Fremder Name im Titel → skip
                # Wenn der Titel den Absender-Namen enthaelt, Namen entfernen
                if sender_name:
                    # Versuche den vollstaendigen Namen zu entfernen
                    name_parts = sender_name.split()
                    # Suche nach zusammenhaengenden Namensteilen am Anfang
                    cleaned = candidate
                    for part in name_parts:
                        if len(part) > 2:
                            # Entferne Namensteil am Anfang (case-insensitive)
                            if cleaned.lower().startswith(part.lower()):
                                cleaned = cleaned[len(part):].strip().lstrip('\n').strip()
                    if cleaned and cleaned != candidate:
                        candidate = cleaned
                title = candidate
                break

    return title, phone


def parse_email_file(filepath, filename):
    """Parst eine E-Mail-Datei und gibt Metadaten zurueck."""
    m = EMAIL_PATTERN.match(filename)
    if not m:
        return None

    date_str, time_str, direction, _rest = m.groups()

    try:
        dt = datetime.datetime.strptime(f"{date_str}_{time_str}", "%Y-%m-%d_%H-%M-%S")
    except ValueError:
        return None

    # Dateiinhalt fuer E-Mail-Adresse, Name, Titel, Telefon lesen
    try:
        with open(filepath, 'r', errors='ignore') as f:
            content = f.read(5000)
    except Exception:
        return None

    email_addr = extract_email_from_header(content, direction)
    if not email_addr:
        return None

    # Eigene Adressen ignorieren
    if email_addr.lower() in OWN_EMAILS:
        return None

    # Notification-Absender rausfiltern
    if is_notification_sender(email_addr):
        return None

    name = extract_name_from_header_name(content, direction)
    name = clean_name(name)

    # Signatur nur fuer eingehende E-Mails extrahieren (Absender-Signatur)
    title, phone = None, None
    if direction == 'IN':
        title, phone = extract_signature_info(content, sender_name=name, sender_email=email_addr)

    return {
        'email': email_addr,
        'name': name,
        'direction': direction,
        'date': dt,
        'title': title,
        'phone': phone,
    }


def analyze(agent='signicat', months=3):
    """Hauptanalyse: liest alle E-Mails und baut Kontaktdatenbank."""
    memory_dir = os.path.join(BASE, agent, "memory")
    if not os.path.isdir(memory_dir):
        print(f"Fehler: {memory_dir} existiert nicht")
        return

    cutoff = datetime.datetime.now() - datetime.timedelta(days=months * 30)
    contacts = defaultdict(lambda: {
        'name': None, 'email': None, 'company': None,
        'title': None, 'phone': None,
        'total_contacts': 0, 'sent': 0, 'received': 0,
        'first_contact': None, 'last_contact': None,
    })

    total_files = 0
    matched_files = 0
    filtered_files = 0

    for fname in os.listdir(memory_dir):
        if not fname.endswith('.txt'):
            continue
        if not EMAIL_PATTERN.match(fname):
            continue
        total_files += 1

        result = parse_email_file(os.path.join(memory_dir, fname), fname)
        if not result:
            continue
        matched_files += 1

        if result['date'] < cutoff:
            continue
        filtered_files += 1

        addr = result['email']
        c = contacts[addr]

        c['email'] = addr
        c['company'] = company_from_domain(addr)

        # Name: den laengsten/besten behalten
        if result['name'] and (not c['name'] or len(result['name']) > len(c['name'])):
            c['name'] = result['name']

        # Titel/Telefon: nur setzen wenn noch leer
        if result['title'] and not c['title']:
            c['title'] = result['title']
        if result['phone'] and not c['phone']:
            c['phone'] = result['phone']

        c['total_contacts'] += 1
        if result['direction'] == 'OUT':
            c['sent'] += 1
        else:
            c['received'] += 1

        dt_str = result['date'].strftime('%Y-%m-%d')
        if not c['first_contact'] or dt_str < c['first_contact']:
            c['first_contact'] = dt_str
        if not c['last_contact'] or dt_str > c['last_contact']:
            c['last_contact'] = dt_str

    # Telefonnummern-Deduplizierung: gleiche Nummer bei mehreren Kontakten
    # → nur beim Kontakt mit den meisten E-Mails behalten
    phone_counts = defaultdict(list)
    for addr, c in contacts.items():
        if c['phone']:
            normalized = re.sub(r'[\s./-]', '', c['phone'])
            phone_counts[normalized].append((addr, c['total_contacts']))

    for normalized, holders in phone_counts.items():
        if len(holders) > 1:
            # Nur der haeufigste Kontakt behaelt die Nummer
            holders.sort(key=lambda x: x[1], reverse=True)
            for addr, _ in holders[1:]:
                contacts[addr]['phone'] = None

    # Sortieren nach Kontakthaeufigkeit
    contacts_list = sorted(contacts.values(), key=lambda x: x['total_contacts'], reverse=True)

    # ── contacts.json schreiben ──
    contacts_json_path = os.path.join(memory_dir, "contacts.json")
    with open(contacts_json_path, 'w') as f:
        json.dump({
            'generated': datetime.datetime.now().isoformat(),
            'period_months': months,
            'agent': agent,
            'total_contacts': len(contacts_list),
            'contacts': contacts_list,
        }, f, indent=2, ensure_ascii=False)

    print(f"contacts.json geschrieben: {contacts_json_path}")

    # ── Menschenlesbarer Report ──
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    report_name = f"contact_report_{datetime.date.today().isoformat()}.md"
    report_path = os.path.join(OUTPUT_DIR, report_name)

    # Nach Firma gruppieren
    by_company = defaultdict(list)
    for c in contacts_list:
        by_company[c['company'] or 'Unknown'].append(c)

    # Firmen nach Gesamtkontakten sortieren
    sorted_companies = sorted(
        by_company.items(),
        key=lambda x: sum(c['total_contacts'] for c in x[1]),
        reverse=True
    )

    with open(report_path, 'w') as f:
        f.write(f"# Kontakt-Report: {agent}\n")
        f.write(f"Zeitraum: letzte {months} Monate (ab {cutoff.strftime('%Y-%m-%d')})\n")
        f.write(f"Erstellt: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"Kontakte gesamt: {len(contacts_list)}\n")
        f.write(f"E-Mails im Zeitraum: {filtered_files}\n\n")
        f.write("---\n\n")

        for company, members in sorted_companies:
            total = sum(c['total_contacts'] for c in members)
            f.write(f"## {company} ({total} Kontakte)\n\n")
            for c in sorted(members, key=lambda x: x['total_contacts'], reverse=True):
                name = c['name'] or c['email']
                f.write(f"**{name}** ({c['email']})\n")
                if c['title']:
                    f.write(f"  Titel: {c['title']}\n")
                if c['phone']:
                    f.write(f"  Tel: {c['phone']}\n")
                f.write(f"  Kontakte: {c['total_contacts']} (gesendet: {c['sent']}, empfangen: {c['received']})\n")
                f.write(f"  Zeitraum: {c['first_contact']} bis {c['last_contact']}\n\n")

    print(f"Report geschrieben: {report_path}")
    print(f"\nStatistik:")
    print(f"  E-Mail-Dateien gesamt: {total_files}")
    print(f"  Davon gematcht: {matched_files}")
    print(f"  Im Zeitraum ({months} Monate): {filtered_files}")
    print(f"  Unique Kontakte: {len(contacts_list)}")

    return contacts_list


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Kontakt-Analyse fuer Agent Memory')
    parser.add_argument('--months', type=int, default=3, help='Zeitraum in Monaten (Default: 3)')
    parser.add_argument('--agent', type=str, default='signicat', help='Agent (Default: signicat)')
    args = parser.parse_args()
    analyze(agent=args.agent, months=args.months)
