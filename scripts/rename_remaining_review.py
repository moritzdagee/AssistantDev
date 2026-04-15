#!/usr/bin/env python3
"""
rename_remaining_review.py — Benennt ALLE Kontakte um, die im aktuellen Report
noch als REVIEW auftauchen. Nutzt process() aus cleanup_all_contacts.py
(inklusive der would-orphan-contact Sicherheitsregel), damit auch Kontakte
erfasst werden, deren einzige E-Mail eigentlich DELETE waere aber durch das
Sicherheitsnetz zu REVIEW wird.

Regel: ZLASTNAME = erste E-Mail (sortiert nach Z_PK), ZFIRSTNAME = ''.

Ausnahmen:
  - My Card
  - Moritz Wilhelm @ Qonto (Z_PK=49665 in A42FFC88)

Nutzung:
  python3 ~/AssistantDev/scripts/rename_remaining_review.py           # dry-run
  python3 ~/AssistantDev/scripts/rename_remaining_review.py --fix     # anwenden
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
process = _cleanup.process
is_my_card = _cleanup.is_my_card

EXCLUDE = {
    ('A42FFC88', 49665),
}


def find_review_owners(db_path):
    """Gibt {z_pk: name} aller Kontakte zurueck, die >=1 E-Mail mit Verdict REVIEW haben."""
    src_prefix = os.path.basename(os.path.dirname(db_path))[:8]
    res = process(db_path)
    owners = {}
    for z_pk, name, org, email_pk, addr, reason in res['review']:
        if (src_prefix, z_pk) in EXCLUDE:
            continue
        if is_my_card(name or ''):
            continue
        owners[z_pk] = name or ''
    return owners


def first_email_of(db_path, z_pk):
    conn = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
    cur = conn.cursor()
    cur.execute(
        "SELECT ZADDRESS FROM ZABCDEMAILADDRESS WHERE ZOWNER=? AND ZADDRESS IS NOT NULL "
        "ORDER BY Z_PK LIMIT 1",
        (z_pk,),
    )
    row = cur.fetchone()
    conn.close()
    return (row[0].strip() if row and row[0] else None)


def apply_renames(db_path, mapping):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    n = 0
    for z_pk, email in mapping.items():
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
        backup_dir = os.path.expanduser(f'~/AssistantDev/backups/addressbook_renamerest_{ts}')
        os.makedirs(backup_dir, exist_ok=True)
        for db in dbs:
            src_id = os.path.basename(os.path.dirname(db))
            shutil.copy2(db, os.path.join(backup_dir, f'{src_id}_AddressBook-v22.abcddb'))
        print(f'Backup: {backup_dir}')

    total = 0
    for db in dbs:
        src_id = os.path.basename(os.path.dirname(db))[:8]
        owners = find_review_owners(db)
        mapping = {}
        for z_pk in owners:
            email = first_email_of(db, z_pk)
            if email:
                mapping[z_pk] = email
        print(f'[{src_id}] review-owners: {len(mapping)}')
        if mapping and not dry_run:
            n = apply_renames(db, mapping)
            print(f'[{src_id}]   → {n} umbenannt')
        total += len(mapping)

    print(f'\nTotal: {total}')
    if dry_run:
        print('*** DRY-RUN *** — nochmal mit --fix ausfuehren.')
    else:
        print('Fertig. Contacts.app + Mail.app beenden und neu starten.')


if __name__ == '__main__':
    main()
