#!/usr/bin/env python3
"""
contact_watchdog.py — taegliche Praeventivpruefung fuer Kontaktdatenbestaende.

Prueft zwei Quellen:
1. macOS AddressBook (sqlite)  — Pollution: viele E-Mails aus vielen Domains
   auf einem Kontakt (hist. Problem: Sebastian Schroeder mit 64 Adressen).
2. Agent-Memory contacts.json  — Sanity: Name passt nicht zum E-Mail-Local-Part,
   eigene E-Mails bei fremden Kontakten.

Schreibt NUR bei Fund eine Warnung nach
  ~/Library/Mobile Documents/.../claude_outputs/contact_watchdog_warning_YYYYMMDD.txt
Modifiziert KEINE Daten (Apple DB waere live-risky).
"""

import os, sys, json, glob, sqlite3, re, datetime

HOME = os.path.expanduser('~')
DATALAKE = os.path.join(HOME, 'Library/Mobile Documents/com~apple~CloudDocs/Downloads shared/claude_datalake')
OUTPUTS = os.path.join(HOME, 'Library/Mobile Documents/com~apple~CloudDocs/Downloads shared/claude_outputs')
OWN_ADDRS_CACHE = os.path.join(HOME, '.emailwatcher_own_addresses.json')
ADDRESSBOOK_GLOB = os.path.join(HOME, 'Library/Application Support/AddressBook/Sources/*/AddressBook-v22.abcddb')

POLLUTION_EMAIL_THRESHOLD = 5
POLLUTION_DOMAIN_THRESHOLD = 3


def load_own_addrs():
    try:
        return {a.lower() for a in json.load(open(OWN_ADDRS_CACHE))}
    except Exception:
        return set()


def check_addressbook(warnings):
    dbs = glob.glob(ADDRESSBOOK_GLOB)
    for db in dbs:
        try:
            conn = sqlite3.connect(f'file:{db}?mode=ro', uri=True)
        except sqlite3.OperationalError as e:
            warnings.append(f'[AddressBook] konnte {db} nicht oeffnen: {e}')
            continue
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT r.Z_PK,
                       TRIM(COALESCE(r.ZFIRSTNAME,'')||' '||COALESCE(r.ZLASTNAME,'')) AS nm,
                       r.ZORGANIZATION
                FROM ZABCDRECORD r
                WHERE (SELECT COUNT(*) FROM ZABCDEMAILADDRESS e WHERE e.ZOWNER=r.Z_PK) >= ?
            """, (POLLUTION_EMAIL_THRESHOLD,))
            for z_pk, nm, org in cur.fetchall():
                cur2 = conn.cursor()
                cur2.execute('SELECT ZADDRESS FROM ZABCDEMAILADDRESS WHERE ZOWNER=?', (z_pk,))
                addrs = [a for (a,) in cur2.fetchall() if a]
                domains = {a.split('@')[-1].lower() for a in addrs if '@' in a}
                if len(domains) >= POLLUTION_DOMAIN_THRESHOLD:
                    warnings.append(
                        f'[AddressBook] Z_PK={z_pk} {nm!r} (org={org!r}): '
                        f'{len(addrs)} E-Mails aus {len(domains)} Domains'
                    )
        finally:
            conn.close()


def norm(s):
    s = (s or '').lower()
    for a, b in [('ä','ae'),('ö','oe'),('ü','ue'),('ß','ss'),('é','e'),('è','e'),('ė','e'),('ū','u')]:
        s = s.replace(a, b)
    return s


ROLE_LOCALS = {'info','hello','mail','kontakt','noreply','no-reply','notifications',
               'notification','support','admin','service','office','contact','events',
               'marketing','newsletter','billing','invoice','team','hi','press'}


def name_tokens_from_email(email):
    if '@' not in email:
        return None
    local = email.split('@')[0].lower()
    if local in ROLE_LOCALS or any(r in local for r in ('noreply','no-reply','notifications','do-not-reply')):
        return None
    local = re.sub(r'[+_\-]', ' ', local).replace('.', ' ')
    local = re.sub(r'\d+', '', local)
    toks = [t for t in local.split() if len(t) >= 3]
    return toks or None


def check_agent_contacts(warnings, own_addrs):
    for f in sorted(glob.glob(os.path.join(DATALAKE, '*', 'memory', 'contacts.json'))):
        agent = os.path.relpath(f, DATALAKE).split(os.sep)[0]
        try:
            d = json.load(open(f))
        except Exception as e:
            warnings.append(f'[{agent}] contacts.json nicht lesbar: {e}')
            continue
        for c in d.get('contacts', []):
            email = (c.get('email') or '').lower().strip()
            name = c.get('name') or ''
            if not email:
                continue
            # ROT_EIGEN: eigene E-Mail bei fremdem Namen
            if email in own_addrs and norm(name) not in (norm('Moritz Cremer'), norm('Moritz')):
                warnings.append(f'[{agent}] eigene E-Mail bei fremdem Kontakt: {name!r} <{email}>')
                continue
            # Name vs local-part sanity (nur hart warnen, wenn Tokens aus lokalem Teil gar nicht matchen
            # UND es kein Role/Notification-Account ist)
            toks = name_tokens_from_email(email)
            if not toks or not name:
                continue
            cn = norm(name)
            if not any(norm(t) in cn for t in toks):
                # leiser Hinweis, da viele legitime Faelle (Initialen, Firmenname als Display)
                pass  # bewusst nicht als Warnung — zu viele false positives


def main():
    os.makedirs(OUTPUTS, exist_ok=True)
    warnings = []
    own = load_own_addrs()
    check_addressbook(warnings)
    check_agent_contacts(warnings, own)

    ts = datetime.datetime.now().strftime('%Y%m%d')
    out = os.path.join(OUTPUTS, f'contact_watchdog_warning_{ts}.txt')
    if warnings:
        with open(out, 'w') as f:
            f.write(f'contact_watchdog {datetime.datetime.now().isoformat()}\n')
            f.write(f'{len(warnings)} Warnung(en):\n\n')
            for w in warnings:
                f.write(f'- {w}\n')
        print(f'{len(warnings)} Warnung(en) nach {out}')
        sys.exit(1)
    print('OK — keine Auffaelligkeiten')


if __name__ == '__main__':
    main()
