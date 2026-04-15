#!/usr/bin/env python3
"""
Fix polluted macOS Contacts entries.
Removes incorrectly associated email addresses from contacts that have
too many unrelated emails (domain chaos).

The main offender: Sebastian Schroeder (Z_PK=238) with 64 emails from 42 domains.

This script:
1. Backs up the database
2. For contacts with >5 emails from >5 domains:
   - Identifies the "correct" email(s) by matching domain to the contact's organization
   - Removes all other emails
3. Reports what was changed

Usage: python3 fix_contacts_pollution.py [--dry-run]
"""

import sqlite3
import os
import shutil
import sys
import datetime
import re

DB_PATH = os.path.expanduser(
    "~/Library/Application Support/AddressBook/Sources/"
    "A42FFC88-6123-452D-8D58-9CFE3B556EF6/AddressBook-v22.abcddb"
)

# User's own emails — should never be associated with another person
OWN_EMAILS = {
    'moritz.cremer@me.com', 'moritz.cremer@icloud.com',
    'moritz.cremer@signicat.com', 'londoncityfox@gmail.com',
    'moritz@demoscapital.co', 'moritz@vegatechnology.com.br',
    'moritz.cremer@trustedcarrier.net', 'moritz@brandshare.me',
    'cremer.moritz@gmx.de', 'family.cremer@gmail.com',
    'moritz.cremer@trustedcarrier.de', 'naiaraebertz@gmail.com',
}


def get_domain(email):
    if '@' in email:
        return email.split('@')[1].lower()
    return ''


def analyze_and_fix(dry_run=True):
    if not os.path.exists(DB_PATH):
        print(f"ERROR: Database not found: {DB_PATH}")
        sys.exit(1)

    # Backup
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = DB_PATH + f'.backup_{timestamp}'
    if not dry_run:
        shutil.copy2(DB_PATH, backup_path)
        print(f"Backup: {backup_path}")
    else:
        print("=== DRY RUN — keine Aenderungen ===")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Find all contacts with their email counts
    cursor.execute("""
        SELECT r.Z_PK,
               COALESCE(r.ZFIRSTNAME,'') || ' ' || COALESCE(r.ZLASTNAME,'') as fullname,
               r.ZORGANIZATION,
               r.ZFIRSTNAME,
               r.ZLASTNAME
        FROM ZABCDRECORD r
        WHERE (SELECT COUNT(*) FROM ZABCDEMAILADDRESS e WHERE e.ZOWNER = r.Z_PK) > 0
    """)
    contacts = cursor.fetchall()

    total_removed = 0
    total_contacts_fixed = 0

    for z_pk, fullname, org, firstname, lastname in contacts:
        # Get all emails for this contact
        cursor.execute("""
            SELECT Z_PK, ZADDRESS FROM ZABCDEMAILADDRESS WHERE ZOWNER = ?
        """, (z_pk,))
        emails = cursor.fetchall()

        if len(emails) <= 3:
            continue  # Not polluted

        # Analyze domains
        domains = set()
        for _, addr in emails:
            if addr and '@' in addr:
                domains.add(get_domain(addr))

        if len(domains) <= 3:
            continue  # Few domains, probably legitimate

        # This contact is polluted — determine which emails are correct
        name_lower = fullname.strip().lower()
        name_parts = [p.lower() for p in fullname.strip().split() if len(p) > 2]
        org_lower = (org or '').lower()

        correct_emails = []
        wrong_emails = []

        for email_pk, addr in emails:
            if not addr:
                wrong_emails.append((email_pk, addr))
                continue

            addr_lower = addr.lower()
            domain = get_domain(addr_lower)
            local = addr_lower.split('@')[0]

            # Rule 1: User's own emails are ALWAYS wrong on someone else's contact
            if addr_lower in OWN_EMAILS:
                wrong_emails.append((email_pk, addr))
                continue

            # Rule 2: Email local part contains the contact's name parts
            name_match = False
            for part in name_parts:
                if part in local.replace('.', ' ').replace('-', ' '):
                    name_match = True
                    break

            # Rule 3: Domain matches the organization name
            org_match = False
            if org_lower and len(org_lower) > 2:
                org_parts = re.split(r'[\s-]+', org_lower)
                for op in org_parts:
                    if len(op) > 2 and op in domain:
                        org_match = True
                        break

            # Rule 4: Obvious spam/notification senders
            is_notification = any(x in addr_lower for x in [
                'noreply', 'no-reply', 'notification', 'mailer@',
                'account-update@', 'store-news@', 'service@',
                'paypal@', 'amazon.', 'shopify', 'easyjet',
                'smartfit', 'appmax', 'smiles@', 'medallia',
                'docusign', 'gothaer', 'nuernberger', 'prime@',
            ])

            if name_match or org_match:
                correct_emails.append((email_pk, addr))
            elif is_notification:
                wrong_emails.append((email_pk, addr))
            else:
                # Unknown — default to removing if contact has many domains
                if len(domains) > 5:
                    wrong_emails.append((email_pk, addr))
                else:
                    correct_emails.append((email_pk, addr))

        # Safety: never remove ALL emails — keep at least one
        if not correct_emails and wrong_emails:
            # Keep the one that best matches the name
            best = None
            for email_pk, addr in wrong_emails:
                local = addr.split('@')[0].lower() if '@' in addr else ''
                for part in name_parts:
                    if part in local:
                        best = (email_pk, addr)
                        break
                if best:
                    break
            if not best:
                best = wrong_emails[0]  # Keep the first one
            correct_emails.append(best)
            wrong_emails.remove(best)

        if wrong_emails:
            print(f"\n{'='*60}")
            print(f"CONTACT: {fullname} (Org: {org}, Z_PK: {z_pk})")
            print(f"  Total emails: {len(emails)}, Domains: {len(domains)}")
            print(f"  KEEPING ({len(correct_emails)}):")
            for _, addr in correct_emails:
                print(f"    ✓ {addr}")
            print(f"  REMOVING ({len(wrong_emails)}):")
            for _, addr in wrong_emails:
                print(f"    ✗ {addr}")

            if not dry_run:
                for email_pk, addr in wrong_emails:
                    cursor.execute("DELETE FROM ZABCDEMAILADDRESS WHERE Z_PK = ?", (email_pk,))
                    total_removed += 1
                total_contacts_fixed += 1

    if not dry_run and total_removed > 0:
        conn.commit()
        print(f"\n{'='*60}")
        print(f"DONE: {total_removed} falsche E-Mails von {total_contacts_fixed} Kontakt(en) entfernt")
        print(f"Backup: {backup_path}")
        print(f"\nWICHTIG: Apple Mail / Contacts App neu starten damit die Aenderungen wirksam werden!")
    elif dry_run:
        print(f"\n{'='*60}")
        print(f"DRY RUN: {len([e for c in contacts for e in [] ])} — wuerde {total_removed} E-Mails entfernen")
        print(f"Fuehre mit --fix aus um die Aenderungen anzuwenden")
    else:
        print("\nKeine Aenderungen noetig — alle Kontakte sind sauber")

    conn.close()


if __name__ == '__main__':
    dry_run = '--fix' not in sys.argv
    analyze_and_fix(dry_run=dry_run)
