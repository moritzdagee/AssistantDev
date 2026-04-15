#!/usr/bin/env python3
"""
split_multiemail_renamed.py — Splittet die zuvor umbenannten Multi-E-Mail-Kontakte:
Fuer jeden Kontakt, dessen aktueller Anzeigename eine E-Mail-Adresse ist
(Ergebnis von rename_all_review.py), und der >=2 E-Mails hat, wird pro
zusaetzlicher E-Mail ein neuer ZABCDRECORD angelegt. Die E-Mail wird vom
Original-Kontakt auf den neuen Record umgehaengt (UPDATE ZOWNER).

Ergebnis: jeder E-Mail-Eintrag hat am Ende seinen eigenen Kontakt, Name=email.

Ausnahmen (werden NIE angefasst):
  - My Card (Name ~= 'Moritz Cremer')
  - Moritz Wilhelm @ Qonto (Z_PK=49665 in A42FFC88)

Schema-Quelle fuer den INSERT: apply_contact_fixes.py merge_datalake_contacts().
CoreData-Epoch: Unix timestamp - 978307200.

Nutzung:
  python3 ~/AssistantDev/scripts/split_multiemail_renamed.py           # dry-run
  python3 ~/AssistantDev/scripts/split_multiemail_renamed.py --fix     # anwenden
"""

import os
import re
import sys
import glob
import uuid
import shutil
import sqlite3
import datetime
import importlib.util

ADDRESSBOOK_DIR = os.path.expanduser("~/Library/Application Support/AddressBook")
DB_GLOB = os.path.join(ADDRESSBOOK_DIR, "Sources/*/AddressBook-v22.abcddb")

Z_ENT_RECORD = 22
Z_ENT_EMAIL = 11

_cleanup_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cleanup_all_contacts.py")
_spec = importlib.util.spec_from_file_location("cleanup_all_contacts", _cleanup_path)
_cleanup = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_cleanup)
is_my_card = _cleanup.is_my_card

EXCLUDE = {
    ('A42FFC88', 49665),   # Moritz Wilhelm / Qonto
}

EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def find_candidates(db_path):
    """Gibt [(z_pk, name, org, [(email_pk, addr), ...])] fuer Multi-Mail-Kontakte
    zurueck, deren aktueller ZLASTNAME eine E-Mail ist."""
    src_prefix = os.path.basename(os.path.dirname(db_path))[:8]
    conn = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
    cur = conn.cursor()
    cur.execute("""
        SELECT r.Z_PK,
               COALESCE(r.ZFIRSTNAME,''),
               COALESCE(r.ZLASTNAME,''),
               COALESCE(r.ZORGANIZATION,'')
        FROM ZABCDRECORD r
    """)
    rows = cur.fetchall()
    out = []
    for z_pk, fn, ln, org in rows:
        if (src_prefix, z_pk) in EXCLUDE:
            continue
        fullname = (fn + ' ' + ln).strip()
        if is_my_card(fullname):
            continue
        # Der Kontakt muss per rename_all_review.py umbenannt worden sein:
        # leerer Vorname + Nachname = E-Mail-Adresse.
        if fn or not EMAIL_RE.match(ln):
            continue
        cur2 = conn.cursor()
        cur2.execute(
            "SELECT Z_PK, ZADDRESS FROM ZABCDEMAILADDRESS "
            "WHERE ZOWNER=? AND ZADDRESS IS NOT NULL ORDER BY Z_PK",
            (z_pk,),
        )
        emails = [(pk, a.strip()) for pk, a in cur2.fetchall() if a and a.strip()]
        if len(emails) < 2:
            continue
        out.append((z_pk, ln, org, emails))
    conn.close()
    return out


def apply_split(db_path, candidates):
    """Legt pro zusaetzlicher E-Mail einen neuen Kontakt an und haengt die
    E-Mail dorthin um. Gibt (n_new_contacts, n_moved_emails) zurueck."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("SELECT MAX(Z_PK) FROM ZABCDRECORD")
    max_record_pk = cur.fetchone()[0] or 0

    n_new = 0
    n_moved = 0

    for z_pk, name, org, emails in candidates:
        # E-Mails: [e0=first_kept, e1, e2, ...] — e0 bleibt am Original
        # Den Owner-Typ (Z22_OWNER) der E-Mail vom Original uebernehmen.
        cur.execute(
            "SELECT Z22_OWNER FROM ZABCDEMAILADDRESS WHERE Z_PK = ? LIMIT 1",
            (emails[0][0],),
        )
        row = cur.fetchone()
        z22_owner = row[0] if row and row[0] is not None else Z_ENT_RECORD

        for email_pk, addr in emails[1:]:
            # Neuen Record anlegen: ZLASTNAME = addr, Org uebernehmen
            max_record_pk += 1
            new_pk = max_record_pk
            now = datetime.datetime.now().timestamp() - 978307200
            year = datetime.datetime.now().year
            uid = str(uuid.uuid4()).upper()
            cur.execute("""
                INSERT INTO ZABCDRECORD (
                    Z_PK, Z_ENT, Z_OPT, ZFIRSTNAME, ZLASTNAME,
                    ZORGANIZATION, ZJOBTITLE,
                    ZCREATIONDATE, ZMODIFICATIONDATE,
                    ZCREATIONDATEYEAR, ZMODIFICATIONDATEYEAR,
                    ZCREATIONDATEYEARLESS, ZMODIFICATIONDATEYEARLESS,
                    ZUNIQUEID
                ) VALUES (?, ?, 1, NULL, ?, ?, NULL, ?, ?, ?, ?, 0.0, 0.0, ?)
            """, (
                new_pk, Z_ENT_RECORD, addr,
                (org or None),
                now, now, year, year, uid,
            ))
            # E-Mail umhaengen
            cur.execute("""
                UPDATE ZABCDEMAILADDRESS
                SET ZOWNER = ?, Z22_OWNER = ?
                WHERE Z_PK = ?
            """, (new_pk, z22_owner, email_pk))
            n_new += 1
            n_moved += 1

    conn.commit()
    conn.close()
    return n_new, n_moved


def main():
    dry_run = '--fix' not in sys.argv
    dbs = sorted(glob.glob(DB_GLOB))
    if not dbs:
        print('Keine AddressBook-DBs gefunden.')
        sys.exit(1)

    backup_dir = None
    if not dry_run:
        ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_dir = os.path.expanduser(f'~/AssistantDev/backups/addressbook_split_{ts}')
        os.makedirs(backup_dir, exist_ok=True)
        for db in dbs:
            src_id = os.path.basename(os.path.dirname(db))
            shutil.copy2(db, os.path.join(backup_dir, f'{src_id}_AddressBook-v22.abcddb'))
        print(f'Backup: {backup_dir}')

    total_contacts = 0
    total_new_records = 0
    for db in dbs:
        src_id = os.path.basename(os.path.dirname(db))[:8]
        cands = find_candidates(db)
        extra = sum(len(c[3]) - 1 for c in cands)
        print(f'[{src_id}] candidates: {len(cands)} contacts, {extra} new records needed')
        if cands and not dry_run:
            n_new, n_moved = apply_split(db, cands)
            print(f'[{src_id}]   → {n_new} neue Kontakte, {n_moved} E-Mails umgehaengt')
            total_new_records += n_new
        total_contacts += len(cands)

    print(f'\nTotal: {total_contacts} Kontakte aufgesplittet, {total_new_records} neue Records erstellt')
    if dry_run:
        print('*** DRY-RUN *** — nochmal mit --fix ausfuehren um zu splitten.')
    else:
        print('Fertig. Bitte Contacts.app und Mail.app beenden + neu starten.')


if __name__ == '__main__':
    main()
