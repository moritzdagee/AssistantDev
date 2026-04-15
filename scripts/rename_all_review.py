#!/usr/bin/env python3
"""
rename_all_review.py — Benennt ALLE verbleibenden REVIEW-Kontakte um, indem
der Anzeigename durch die erste E-Mail-Adresse des Kontakts (sortiert nach Z_PK)
ersetzt wird. Greift auch bei Kontakten mit mehreren E-Mails.

Ausnahmen (werden NIE umbenannt):
  - My Card (Name ~= 'Moritz Cremer')
  - Moritz Wilhelm @ Qonto (Z_PK=49665 in der iCloud-Source A42FFC88)
    — vom User explizit ausgenommen.

Nutzt classify() aus cleanup_all_contacts.py, um REVIEW-Kandidaten zu finden.

Nutzung:
  python3 ~/AssistantDev/scripts/rename_all_review.py           # dry-run
  python3 ~/AssistantDev/scripts/rename_all_review.py --fix     # anwenden
"""

import os
import sys
import glob
import shutil
import sqlite3
import datetime
import importlib.util

ADDRESSBOOK_DIR = os.path.expanduser("~/Library/Application Support/AddressBook")
DB_GLOB = os.path.join(ADDRESSBOOK_DIR, "Sources/*/AddressBook-v22.abcddb")

_cleanup_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cleanup_all_contacts.py")
_spec = importlib.util.spec_from_file_location("cleanup_all_contacts", _cleanup_path)
_cleanup = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_cleanup)
classify = _cleanup.classify
is_my_card = _cleanup.is_my_card

# Explizit ausgenommene (source_id_prefix, Z_PK)
EXCLUDE = {
    ('A42FFC88', 49665),   # Moritz Wilhelm / Qonto
}


def find_review_contacts(db_path):
    """Gibt [(z_pk, name, first_email), ...] fuer Kontakte mit >=1 REVIEW-Email."""
    src_prefix = os.path.basename(os.path.dirname(db_path))[:8]
    conn = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
    cur = conn.cursor()
    cur.execute("""
        SELECT r.Z_PK,
               TRIM(COALESCE(r.ZFIRSTNAME,'') || ' ' || COALESCE(r.ZLASTNAME,'')),
               r.ZORGANIZATION
        FROM ZABCDRECORD r
    """)
    rows = cur.fetchall()
    out = []
    for z_pk, name, org in rows:
        if (src_prefix, z_pk) in EXCLUDE:
            continue
        name = (name or '').strip()
        org = org or ''
        if is_my_card(name):
            continue
        cur2 = conn.cursor()
        cur2.execute(
            "SELECT ZADDRESS FROM ZABCDEMAILADDRESS WHERE ZOWNER=? AND ZADDRESS IS NOT NULL "
            "ORDER BY Z_PK",
            (z_pk,),
        )
        emails = [a.strip() for (a,) in cur2.fetchall() if a and a.strip()]
        if not emails:
            continue
        has_review = False
        for e in emails:
            v, _ = classify(e, name, org)
            if v == 'REVIEW':
                has_review = True
                break
        if not has_review:
            continue
        out.append((z_pk, name, emails[0]))
    conn.close()
    return out


def apply_renames(db_path, triples):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    n = 0
    for z_pk, _name, email in triples:
        cur.execute(
            "UPDATE ZABCDRECORD SET ZFIRSTNAME = '', ZLASTNAME = ? WHERE Z_PK = ?",
            (email, z_pk),
        )
        n += 1
    conn.commit()
    conn.close()
    return n


def main():
    dry_run = '--fix' not in sys.argv
    dbs = sorted(glob.glob(DB_GLOB))
    if not dbs:
        print('Keine AddressBook-DBs gefunden.')
        sys.exit(1)

    backup_dir = None
    if not dry_run:
        ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_dir = os.path.expanduser(f'~/AssistantDev/backups/addressbook_renameall_{ts}')
        os.makedirs(backup_dir, exist_ok=True)
        for db in dbs:
            src_id = os.path.basename(os.path.dirname(db))
            shutil.copy2(db, os.path.join(backup_dir, f'{src_id}_AddressBook-v22.abcddb'))
        print(f'Backup: {backup_dir}')

    total = 0
    for db in dbs:
        src_id = os.path.basename(os.path.dirname(db))[:8]
        triples = find_review_contacts(db)
        print(f'[{src_id}] review-contacts: {len(triples)}')
        if triples and not dry_run:
            n = apply_renames(db, triples)
            print(f'[{src_id}]   → {n} Kontakte umbenannt')
        total += len(triples)

    print(f'\nTotal: {total}')
    if dry_run:
        print('*** DRY-RUN *** — nochmal mit --fix ausfuehren um zu benennen.')
    else:
        print('Fertig. Bitte Contacts.app und Mail.app beenden + neu starten.')


if __name__ == '__main__':
    main()
