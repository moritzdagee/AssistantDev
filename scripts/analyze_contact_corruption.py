#!/usr/bin/env python3
"""
Analyse-Skript fuer Kontakt-Korruption in contacts.json.
Prueft auf Anomalien, Eigen-E-Mail-Kontamination, Domain-Chaos und Duplikate.
"""

import json
import os
import sys
from collections import Counter, defaultdict

OWN_EMAILS = {
    'moritz.cremer@me.com', 'londoncityfox@gmail.com',
    'moritz.cremer@signicat.com', 'moritz@demoscapital.co',
    'moritz@brandshare.me', 'cremer.moritz@gmx.de',
    'family.cremer@gmail.com', 'moritz.cremer@icloud.com',
    'moritz@vegatechnology.com.br', 'moritz.cremer@trustedcarrier.net',
}

BASE = os.path.expanduser(
    "~/Library/Mobile Documents/com~apple~CloudDocs/Downloads shared/claude_datalake"
)


def analyze_contacts(filepath):
    with open(filepath) as f:
        data = json.load(f)

    contacts = data.get('contacts', [])
    print(f"=== Kontakt-Korruptions-Analyse: {os.path.basename(os.path.dirname(os.path.dirname(filepath)))} ===")
    print(f"Datei: {filepath}")
    print(f"Generiert: {data.get('generated')}")
    print(f"Kontakte gesamt: {len(contacts)}")
    print()

    # 1. Anomalie-Score: Kontakte mit ungewoehnlich vielen E-Mails oder Domains
    # Da jeder Kontakt nur 1 E-Mail-Feld hat (String, keine Liste),
    # pruefen wir ob email ein String oder eine Liste ist
    print("=== 1. ANOMALIE-SCORE ===")
    anomalies = []
    for c in contacts:
        email = c.get('email', '')
        emails_field = c.get('emails', [])
        if isinstance(email, list):
            emails = email
        elif isinstance(emails_field, list) and emails_field:
            emails = emails_field
        elif email:
            emails = [email]
        else:
            emails = []

        domains = set()
        for e in emails:
            if '@' in str(e):
                domains.add(str(e).split('@')[1].lower())

        if len(emails) > 10 or len(domains) > 5:
            anomalies.append({
                'name': c.get('name', 'UNKNOWN'),
                'email_count': len(emails),
                'domain_count': len(domains),
                'emails': emails[:20],
            })

    if anomalies:
        for a in anomalies:
            print(f"  ANOMALIE: {a['name']} — {a['email_count']} E-Mails, {a['domain_count']} Domains")
            for e in a['emails'][:10]:
                print(f"    - {e}")
    else:
        print("  Keine Anomalien gefunden (alle Kontakte haben <=10 E-Mails und <=5 Domains)")

    # 2. Eigen-E-Mail-Kontamination
    print()
    print("=== 2. EIGEN-E-MAIL-KONTAMINATION ===")
    contaminated = []
    for c in contacts:
        email = (c.get('email') or '').lower()
        name = (c.get('name') or '').lower()
        if email in OWN_EMAILS and 'moritz' not in name and 'cremer' not in name:
            contaminated.append({'name': c.get('name'), 'email': email})

    if contaminated:
        for cc in contaminated:
            print(f"  WARNUNG: '{cc['name']}' hat eigene E-Mail: {cc['email']}")
    else:
        print("  Keine Kontamination gefunden — eigene E-Mails sind nicht bei fremden Kontakten")

    # 3. Domain-Chaos-Score
    print()
    print("=== 3. DOMAIN-CHAOS-SCORE ===")
    chaos = []
    for c in contacts:
        email = c.get('email', '')
        if isinstance(email, list):
            domains = set(e.split('@')[1].lower() for e in email if '@' in e)
            if len(domains) > 5:
                chaos.append({'name': c.get('name'), 'domains': domains})

    if chaos:
        for ch in chaos:
            print(f"  CHAOS: {ch['name']} — {len(ch['domains'])} Domains: {ch['domains']}")
    else:
        print("  Kein Domain-Chaos — jeder Kontakt hat maximal 1 Domain (single email field)")

    # 4. Duplikat-E-Mails
    print()
    print("=== 4. DUPLIKAT-E-MAILS ===")
    email_map = defaultdict(list)
    for c in contacts:
        email = (c.get('email') or '').lower()
        if email:
            email_map[email].append(c.get('name', 'UNKNOWN'))

    dupes = {e: names for e, names in email_map.items() if len(names) > 1}
    if dupes:
        for email, names in dupes.items():
            print(f"  DUPLIKAT: {email} -> {names}")
    else:
        print("  Keine Duplikate gefunden")

    # 5. Gesamtbewertung
    print()
    print("=== 5. GESAMTBEWERTUNG ===")
    score = 0
    if anomalies:
        score += len(anomalies) * 10
    if contaminated:
        score += len(contaminated) * 5
    if chaos:
        score += len(chaos) * 8
    if dupes:
        score += len(dupes) * 3

    if score >= 20:
        rating = "KRITISCH"
    elif score >= 10:
        rating = "STARK BESCHAEDIGT"
    elif score >= 3:
        rating = "LEICHT BESCHAEDIGT"
    else:
        rating = "OK"

    print(f"  Score: {score}")
    print(f"  Bewertung: {rating}")
    print()

    # Top 20 Kontakte nach Kontaktanzahl
    print("=== TOP 20 KONTAKTE ===")
    sorted_contacts = sorted(contacts, key=lambda x: x.get('total_contacts', 0), reverse=True)
    for c in sorted_contacts[:20]:
        print(f"  {c.get('name', 'UNKNOWN'):40s} | {c.get('email', ''):40s} | {c.get('total_contacts', 0)} Kontakte | {c.get('company', '')}")

    return rating


if __name__ == '__main__':
    # Alle contacts.json im Datalake finden
    import glob
    files = glob.glob(os.path.join(BASE, '*/memory/contacts.json'))
    if not files:
        print("Keine contacts.json Dateien gefunden!")
        sys.exit(1)

    for filepath in files:
        analyze_contacts(filepath)
        print("\n" + "=" * 80 + "\n")
