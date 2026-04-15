#!/usr/bin/env python3
"""
name_unnamed_contacts.py — Setzt bei komplett unbenannten Kontakten
(ohne Vorname, Nachname, Organisation) die erste E-Mail-Adresse als ZLASTNAME,
damit sie in Apple Contacts nicht mehr leer angezeigt werden.

Regel streng:
  - ZFIRSTNAME leer/NULL UND ZLASTNAME leer/NULL UND ZORGANIZATION leer/NULL
  - Kontakt hat mind. 1 E-Mail
  → ZLASTNAME = erste E-Mail (sortiert nach Z_PK des Email-Records)

Dry-run per Default. --fix schreibt in die DBs und legt davor einen Backup-Ordner an.

Nutzung:
  python3 ~/AssistantDev/scripts/name_unnamed_contacts.py           # dry-run
  python3 ~/AssistantDev/scripts/name_unnamed_contacts.py --fix     # anwenden
"""

import os
import sys
import glob
import shutil
import sqlite3
import datetime

ADDRESSBOOK_DIR = os.path.expanduser("~/Library/Application Support/AddressBook")
DB_GLOB = os.path.join(ADDRESSBOOK_DIR, "Sources/*/AddressBook-v22.abcddb")


def find_unnamed(db_path):
    """Gibt [(z_pk, first_email), ...] fuer Kontakte ohne Namen+Org zurueck."""
    conn = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
    cur = conn.cursor()
    cur.execute("""
        SELECT r.Z_PK
        FROM ZABCDRECORD r
        WHERE (COALESCE(TRIM(r.ZFIRSTNAME),'') = '')
          AND (COALESCE(TRIM(r.ZLASTNAME),'') = '')
          AND (COALESCE(TRIM(r.ZORGANIZATION),'') = '')
    """)
    candidates = [r[0] for r in cur.fetchall()]
    out = []
    for z_pk in candidates:
        cur.execute(
            "SELECT ZADDRESS FROM ZABCDEMAILADDRESS WHERE ZOWNER=? AND ZADDRESS IS NOT NULL "
            "ORDER BY Z_PK LIMIT 1",
            (z_pk,),
        )
        row = cur.fetchone()
        if row and row[0]:
            out.append((z_pk, row[0].strip()))
    conn.close()
    return out


def apply_names(db_path, pairs):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    n = 0
    for z_pk, email in pairs:
        cur.execute("UPDATE ZABCDRECORD SET ZLASTNAME = ? WHERE Z_PK = ?", (email, z_pk))
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
        backup_dir = os.path.expanduser(f'~/AssistantDev/backups/addressbook_name_{ts}')
        os.makedirs(backup_dir, exist_ok=True)
        for db in dbs:
            src_id = os.path.basename(os.path.dirname(db))
            shutil.copy2(db, os.path.join(backup_dir, f'{src_id}_AddressBook-v22.abcddb'))
        print(f'Backup: {backup_dir}')

    total = 0
    for db in dbs:
        src_id = os.path.basename(os.path.dirname(db))[:8]
        pairs = find_unnamed(db)
        print(f'[{src_id}] unnamed-to-name: {len(pairs)}')
        if pairs and not dry_run:
            n = apply_names(db, pairs)
            print(f'[{src_id}]   → {n} Kontakte umbenannt')
        total += len(pairs)

    print(f'\nTotal: {total}')
    if dry_run:
        print('*** DRY-RUN *** — nochmal mit --fix ausfuehren um zu benennen.')
    else:
        print('Fertig. Bitte Contacts.app und Mail.app beenden + neu starten.')


if __name__ == '__main__':
    main()
