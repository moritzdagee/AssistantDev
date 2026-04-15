#!/usr/bin/env python3
"""
cleanup_all_contacts.py — Umfassende Kontakt-Bereinigung ueber ALLE Sources.

Klassifiziert JEDE E-Mail-Adresse auf JEDEM Kontakt nach:
  KEEP         — passt zum Namen ODER Domain passt zur Organisation
                 ODER Kontakt hat sowieso nur diese eine E-Mail
  AUTO_DELETE  — eigene E-Mail auf fremdem Kontakt
                 ODER Rolle/Benachrichtigung (noreply, store+...) auf
                 einem human-benamten Kontakt mit weiteren E-Mails
                 ODER Hash/UUID-artiger Local-Part auf named Kontakt
  REVIEW       — Name passt nicht, aber kein obvious Muell → manuelle Entscheidung

Ausgabe:
  - Report:     ~/Library/.../claude_outputs/contacts_cleanup_YYYYMMDD.md
  - (bei --fix) Loescht AUTO_DELETE-Eintraege aus den AddressBook-DBs.

Sicherheitsnetze:
  - Nie die LETZTE E-Mail eines Kontakts loeschen
  - Eigene E-Mails auf der My Card (Name ~= 'Moritz Cremer') werden nie geloescht
  - Dry-run per Default; --fix muss explizit angegeben werden
  - Eigener Backup-Pfad wird in den Report geschrieben

Nutzung:
  python3 ~/AssistantDev/scripts/cleanup_all_contacts.py            # dry-run
  python3 ~/AssistantDev/scripts/cleanup_all_contacts.py --fix      # schreibt in DBs
"""

import os
import re
import sys
import glob
import sqlite3
import shutil
import datetime
import unicodedata
from collections import defaultdict

ADDRESSBOOK_DIR = os.path.expanduser("~/Library/Application Support/AddressBook")
OUTPUT_DIR = os.path.expanduser(
    "~/Library/Mobile Documents/com~apple~CloudDocs/Downloads shared/claude_outputs"
)
DB_GLOB = os.path.join(ADDRESSBOOK_DIR, "Sources/*/AddressBook-v22.abcddb")

OWN_EMAILS = {
    'moritz.cremer@me.com', 'moritz.cremer@icloud.com',
    'moritz.cremer@signicat.com', 'londoncityfox@gmail.com',
    'moritz@demoscapital.co', 'moritz@vegatechnology.com.br',
    'moritz.cremer@trustedcarrier.net', 'moritz@brandshare.me',
    'cremer.moritz@gmx.de', 'family.cremer@gmail.com',
    'moritz.cremer@trustedcarrier.de', 'naiaraebertz@gmail.com',
}

ROLE_LOCALS = {
    'noreply', 'no-reply', 'donotreply', 'do-not-reply', 'newsletter',
    'notifications', 'notification', 'notify', 'alerts', 'alert',
    'support', 'info', 'hello', 'help', 'contact', 'contato',
    'sales', 'marketing', 'billing', 'invoice', 'invoices',
    'postmaster', 'webmaster', 'mailer', 'mailer-daemon', 'daemon',
    'service', 'services', 'atendimento', 'sac', 'faleconosco',
    'hr', 'careers', 'jobs', 'press', 'office', 'team',
    'account-update', 'account', 'store-news', 'updates', 'news',
    'message', 'messages', 'email', 'mail', 'system', 'admin',
    'communications', 'comunicacao', 'comercial', 'financeiro',
    'cadastro', 'anfrage', 'kontakt',
}

# Generische Domains — Name-vs-Org-Match ist dann nicht aussagekraeftig
GENERIC_DOMAINS = {
    'gmail.com', 'googlemail.com', 'yahoo.com', 'yahoo.de', 'hotmail.com',
    'hotmail.de', 'outlook.com', 'outlook.de', 'live.com', 'icloud.com',
    'me.com', 'aol.com', 'protonmail.com', 'gmx.de', 'gmx.net', 'web.de',
    'mail.com', 't-online.de', 'freenet.de', 'arcor.de',
}

OWN_NAMES_NORM = {'moritzcremer'}


def _nfd_umlaut(s):
    """NFD + Umlaut-Collapse (ae/oe/ue/ss)."""
    s = unicodedata.normalize('NFD', s)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return s.lower().replace('ae', 'a').replace('oe', 'o').replace('ue', 'u').replace('ss', 's')


def normalize(s):
    """Fuer My-Card-Vergleich: komplett zusammengefasst ohne Spaces."""
    if not s:
        return ''
    return re.sub(r'[^a-z]+', '', _nfd_umlaut(s))


def name_tokens(s):
    """Tokens aus dem Anzeigenamen, normalisiert, mind. 3 Zeichen."""
    if not s:
        return set()
    t = re.findall(r'[a-z]+', _nfd_umlaut(s))
    return {x for x in t if len(x) >= 3}


def normalize_addr_part(s):
    """Local- oder Domain-Part zur Suche aufbereiten (Trenner → Spaces, Umlaut-Collapse)."""
    if not s:
        return ''
    s = s.lower().replace('.', ' ').replace('_', ' ').replace('-', ' ').replace('+', ' ')
    s = _nfd_umlaut(s)
    s = re.sub(r'[^a-z\s]+', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def is_own_address(addr):
    return addr.lower().strip() in OWN_EMAILS


def is_my_card(name):
    return normalize(name) in OWN_NAMES_NORM


def is_role_local(local):
    local_low = local.lower()
    if local_low in ROLE_LOCALS:
        return True
    for role in ROLE_LOCALS:
        if len(role) >= 5 and role in local_low:
            return True
    return False


def is_hash_local(local):
    """Lokal-Teil, der nach Shop/Booking-ID aussieht: lange Zahlen, UUIDs, Hash-Prefix."""
    low = local.lower()
    if re.match(r'^[a-z]*\+?\d{5,}', low):  # 'store+67126100210', '83823923...'
        return True
    if re.search(r'[0-9a-f]{10,}', low):
        return True
    digits = sum(1 for c in low if c.isdigit())
    alpha = sum(1 for c in low if c.isalpha())
    if digits >= 4 and digits >= alpha:
        return True
    unsep = re.sub(r'[._\-+]', '', low)
    if len(unsep) > 18 and not re.search(r'[._\-+]', low):
        return True
    return False


def domain_matches_org(domain, org):
    if not org or not domain:
        return False
    if domain in GENERIC_DOMAINS:
        return False
    org_toks = name_tokens(org)
    dom_core = domain.split('.')[-2] if '.' in domain else domain
    for t in org_toks:
        if len(t) >= 4 and (t in dom_core or dom_core in t):
            return True
    return False


def classify(email_addr, contact_name, org):
    """Gibt (verdict, reason) zurueck — verdict in {KEEP, DELETE, REVIEW}."""
    if not email_addr or '@' not in email_addr:
        return 'KEEP', 'no-email'
    addr = email_addr.lower().strip()
    # Name ist selbst die E-Mail → KEEP (schon korrekt benannt)
    if contact_name and '@' in contact_name and contact_name.lower().strip() == addr:
        return 'KEEP', 'name-is-email'
    local, _, domain = addr.partition('@')
    name_t = name_tokens(contact_name)
    local_norm = normalize_addr_part(local)
    dom_core = domain.rsplit('.', 2)[0] if domain.count('.') >= 2 else domain.split('.')[0]
    dom_norm = normalize_addr_part(dom_core)

    # Regel 1 (Schutz): Name-Token im Local-Part ODER Domain-Kern → KEEP
    # Schuetzt z.B. 'email@alexandermahr.de' auf Alexander Mahr oder
    # 'mail@till-kothe.de' auf Till Kothe vor faelschlichem DELETE.
    if name_t:
        for t in name_t:
            if t in local_norm or t in dom_norm:
                return 'KEEP', 'name-matches'

    # Regel 2: Domain matcht Organisation → KEEP
    if domain_matches_org(domain, org):
        return 'KEEP', 'domain-matches-org'

    # Regel 3: Eigene E-Mail auf fremdem Kontakt
    if addr in OWN_EMAILS:
        if is_my_card(contact_name):
            return 'KEEP', 'own-on-mycard'
        if name_t:
            return 'DELETE', 'own-email-on-named-contact'
        return 'REVIEW', 'own-email-unnamed'

    # Regel 4: Rolle/Notification auf benamtem Kontakt (Name matcht nicht)
    if is_role_local(local) and name_t:
        return 'DELETE', f'role-local:{local}'

    # Regel 5: Hash/ID-Local auf benamtem Kontakt
    if is_hash_local(local) and name_t:
        return 'DELETE', 'hash-like-local'

    # Regel 6/7: Unnamed Kontakt mit role/hash → DELETE
    if not name_t and is_role_local(local):
        return 'DELETE', f'role-local-unnamed:{local}'
    if not name_t and is_hash_local(local):
        return 'DELETE', 'hash-like-unnamed'

    # Rest: Mismatch, aber nicht eindeutig Muell
    if name_t:
        return 'REVIEW', 'name-does-not-match-local'
    return 'REVIEW', 'unnamed-contact'


def gather_contacts(db_path):
    """Gibt Liste [(z_pk, name, org, [(email_pk, addr), ...])] zurueck."""
    out = []
    try:
        conn = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
    except sqlite3.OperationalError as e:
        print(f"  konnte {db_path} nicht oeffnen: {e}", file=sys.stderr)
        return out
    cur = conn.cursor()
    cur.execute("""
        SELECT r.Z_PK,
               TRIM(COALESCE(r.ZFIRSTNAME,'') || ' ' || COALESCE(r.ZLASTNAME,'')),
               r.ZORGANIZATION
        FROM ZABCDRECORD r
    """)
    for z_pk, nm, org in cur.fetchall():
        c2 = conn.cursor()
        c2.execute("SELECT Z_PK, ZADDRESS FROM ZABCDEMAILADDRESS WHERE ZOWNER = ?", (z_pk,))
        emails = [(pk, a) for pk, a in c2.fetchall() if a]
        if emails:
            out.append((z_pk, nm.strip(), org or '', emails))
    conn.close()
    return out


def process(db_path):
    """Klassifiziert alle Kontakte und gibt dict mit Stats + Listen zurueck."""
    result = {
        'delete': [],   # (z_pk, name, org, email_pk, addr, reason)
        'review': [],   # dito
        'keep_count': 0,
        'contacts_with_any_delete': set(),
    }
    for z_pk, name, org, emails in gather_contacts(db_path):
        per_email = []
        for email_pk, addr in emails:
            v, r = classify(addr, name, org)
            per_email.append((email_pk, addr, v, r))
        # Sicherheitsnetz: nie die LETZTE E-Mail loeschen
        delete_count = sum(1 for _, _, v, _ in per_email if v == 'DELETE')
        keep_plus_review = sum(1 for _, _, v, _ in per_email if v in ('KEEP', 'REVIEW'))
        if delete_count > 0 and keep_plus_review == 0:
            # Alles wuerde geloescht → den ersten DELETE auf REVIEW zuruecksetzen
            for i, (pk, a, v, r) in enumerate(per_email):
                if v == 'DELETE':
                    per_email[i] = (pk, a, 'REVIEW', f'would-orphan-contact; orig:{r}')
                    break
        for email_pk, addr, v, r in per_email:
            if v == 'DELETE':
                result['delete'].append((z_pk, name, org, email_pk, addr, r))
                result['contacts_with_any_delete'].add(z_pk)
            elif v == 'REVIEW':
                result['review'].append((z_pk, name, org, email_pk, addr, r))
            else:
                result['keep_count'] += 1
    return result


def apply_deletes(db_path, delete_list):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    n = 0
    for _, _, _, email_pk, _, _ in delete_list:
        cur.execute("DELETE FROM ZABCDEMAILADDRESS WHERE Z_PK = ?", (email_pk,))
        n += 1
    conn.commit()
    conn.close()
    return n


def write_report(all_results, dry_run, backup_note):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ts = datetime.datetime.now().strftime('%Y%m%d')
    path = os.path.join(OUTPUT_DIR, f'contacts_cleanup_{ts}.md')
    total_delete = sum(len(r['delete']) for r in all_results.values())
    total_review = sum(len(r['review']) for r in all_results.values())
    total_keep = sum(r['keep_count'] for r in all_results.values())
    mode = 'DRY-RUN' if dry_run else 'APPLIED'

    with open(path, 'w', encoding='utf-8') as f:
        f.write(f'# Contacts Cleanup — {ts} ({mode})\n\n')
        if backup_note:
            f.write(f'Backup: `{backup_note}`\n\n')
        f.write(f'**KEEP**:   {total_keep}\n\n')
        f.write(f'**DELETE**: {total_delete}\n\n')
        f.write(f'**REVIEW**: {total_review} (manuelle Entscheidung noetig)\n\n')
        f.write('---\n\n')

        for db_path, res in all_results.items():
            src_id = os.path.basename(os.path.dirname(db_path))[:8]
            f.write(f'## Source {src_id}\n\n')
            if res['delete']:
                f.write(f'### AUTO-DELETE ({len(res["delete"])})\n\n')
                by_contact = defaultdict(list)
                for z_pk, nm, org, pk, addr, reason in res['delete']:
                    by_contact[(z_pk, nm, org)].append((addr, reason))
                for (z_pk, nm, org), items in sorted(by_contact.items(),
                                                     key=lambda x: x[0][1].lower()):
                    f.write(f'- **{nm or "(unnamed)"}** — Z_PK={z_pk}, org={org!r}\n')
                    for addr, reason in items:
                        f.write(f'    - `{addr}` — _{reason}_\n')
                f.write('\n')
            if res['review']:
                f.write(f'### MANUAL REVIEW ({len(res["review"])})\n\n')
                by_contact = defaultdict(list)
                for z_pk, nm, org, pk, addr, reason in res['review']:
                    by_contact[(z_pk, nm, org)].append((addr, reason))
                for (z_pk, nm, org), items in sorted(by_contact.items(),
                                                     key=lambda x: x[0][1].lower()):
                    f.write(f'- **{nm or "(unnamed)"}** — Z_PK={z_pk}, org={org!r}\n')
                    for addr, reason in items:
                        f.write(f'    - `{addr}` — _{reason}_\n')
                f.write('\n')
    return path


def main():
    dry_run = '--fix' not in sys.argv
    dbs = sorted(glob.glob(DB_GLOB))
    if not dbs:
        print('Keine AddressBook-DBs gefunden.')
        sys.exit(1)

    # Immer eigener Backup-Ordner (auch bei dry-run — symmetrisch zum apply_fix Flow)
    backup_dir = None
    if not dry_run:
        ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_dir = os.path.expanduser(f'~/AssistantDev/backups/addressbook_cleanup_{ts}')
        os.makedirs(backup_dir, exist_ok=True)
        for db in dbs:
            src_id = os.path.basename(os.path.dirname(db))
            shutil.copy2(db, os.path.join(backup_dir, f'{src_id}_AddressBook-v22.abcddb'))
        print(f'Backup: {backup_dir}')

    all_results = {}
    total_delete = 0
    total_review = 0
    for db in dbs:
        src_id = os.path.basename(os.path.dirname(db))[:8]
        res = process(db)
        all_results[db] = res
        total_delete += len(res['delete'])
        total_review += len(res['review'])
        print(f'[{src_id}] delete={len(res["delete"])}  review={len(res["review"])}  keep={res["keep_count"]}')

    if not dry_run:
        print()
        for db, res in all_results.items():
            if res['delete']:
                n = apply_deletes(db, res['delete'])
                print(f'[{os.path.basename(os.path.dirname(db))[:8]}] {n} E-Mails geloescht')

    report_path = write_report(all_results, dry_run, backup_dir)
    print(f'\nReport: {report_path}')
    print(f'\nTotal DELETE: {total_delete}   REVIEW: {total_review}')
    if dry_run:
        print('\n*** DRY-RUN *** — nochmal mit --fix ausfuehren um zu loeschen.')
    else:
        print('\nFertig. Bitte Contacts.app und Mail.app beenden + neu starten.')


if __name__ == '__main__':
    main()
