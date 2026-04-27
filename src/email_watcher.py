#!/usr/bin/env python3
"""
Email Watcher v2
Neues Dateinamen-Schema: DATUM_UHRZEIT_IN/OUT_KONTAKT_BETREFF.txt
Speichert ins Agent-Memory mit vollstaendigen Metadaten im Dateinamen.

Start: python3 ~/AssistantDev/src/email_watcher.py
Laeuft im Hintergrund. Control+C zum Beenden.
"""

import os
import time
import email
import json
import datetime
import re
import subprocess
from email.header import decode_header
try:
    import setproctitle
    setproctitle.setproctitle("AssistantDev EmailWatcher")
except ImportError:
    pass

# Search index integration
try:
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from search_engine import index_single_file
except ImportError:
    index_single_file = None

BASE = os.path.expanduser("~/Library/Mobile Documents/com~apple~CloudDocs/Downloads shared/claude_datalake")
WATCH_DIR = os.path.join(BASE, "email_inbox")
PROCESSED_SUBDIR = os.path.join(WATCH_DIR, "processed")
# Globaler Email-Pool: Kopie jeder importierten Email als .txt, unabhaengig
# vom primaeren Agent-Routing. Andere Agenten koennen darauf optional Zugriff
# bekommen (nicht Default-Modus).
GLOBAL_EMAIL_DIR = os.path.join(WATCH_DIR, "all_emails")
# Fallback-Agent: Alles was nicht an eine bekannte Business-Domain ging.
DEFAULT_AGENT = "privat"

# Processed log lives in HOME folder - avoids iCloud permission issues with LaunchAgent
PROCESSED_LOG = os.path.expanduser("~/.emailwatcher_processed.json")
# Dual-write mirror in iCloud datalake (for recovery if local is lost)
PROCESSED_LOG_MIRROR = os.path.join(BASE, "config", "email_processed_log.json")
OWN_ADDRS_CACHE = os.path.expanduser("~/.emailwatcher_own_addresses.json")

# Agent-Routing nach Empfaenger- bzw. (bei OUT) Sender-Domain.
# Mapping: Domain-Muster -> Agent-Name.
# - exact-match: ganze Domain gleich (z.B. "signicat.com")
# - substring-match: Token taucht irgendwo in der Domain auf (z.B. "trustedcarrier"
#   matcht trustedcarrier.net, trustedcarrier.de, trustedcarrier.com, ...).
DOMAIN_AGENT_MAP_EXACT = {
    "signicat.com": "signicat",
    "signicat.tech": "signicat",
}
DOMAIN_AGENT_MAP_SUBSTR = [
    ("trustedcarrier", "trustedcarrier"),
]

# ── Signatur-Extraktion Patterns ────────────────────────────────────────────

_PHONE_PATTERNS = [
    re.compile(r'(?:Tel|Phone|Mob|Mobile|Fon|Telefon|Direct|Cell)[.:)]*\s*([+\d][\d\s./-]{7,18}\d)', re.I),
    re.compile(r'(?:^|\n)\s*(\+\d{1,3}[\s.-]?\d[\d\s.-]{6,16}\d)\s*$', re.M),
]
_TITLE_PATTERNS = [
    re.compile(r'(?:^|\n)\s*((?:Chief|Head|Director|VP|Vice President|Manager|Senior|Lead|Principal|Associate|Partner|CEO|CTO|CFO|COO|CSO|CMO|CIO|SVP|EVP)[^\n]{2,60})\s*(?:\n|$)', re.I),
    re.compile(r'(?:^|\n)\s*([\w\s]+(?:Officer|Manager|Director|Consultant|Analyst|Engineer|Architect|Specialist|Advisor|Strategist|Developer))\s*(?:\n|$)', re.I),
]

# ── Eigene Adressen ──────────────────────────────────────────────────────────

def get_own_addresses():
    """Eigene E-Mail-Adressen aus Apple Mail oder Cache laden."""
    if os.path.exists(OWN_ADDRS_CACHE):
        try:
            with open(OWN_ADDRS_CACHE) as f:
                addrs = json.load(f)
            if addrs:
                return addrs
        except Exception:
            pass
    try:
        script = ('tell application "Mail"\n'
                  '    set addrList to ""\n'
                  '    repeat with acct in every account\n'
                  '        set eAddrs to email addresses of acct\n'
                  '        repeat with addr in eAddrs\n'
                  '            set addrList to addrList & (addr as string) & ","\n'
                  '        end repeat\n'
                  '    end repeat\n'
                  '    return addrList\n'
                  'end tell')
        r = subprocess.run(['osascript', '-e', script], capture_output=True, text=True, timeout=15)
        if r.returncode == 0 and '@' in r.stdout:
            addrs = [a.strip() for a in r.stdout.strip().rstrip(',').split(',') if '@' in a]
            if addrs:
                with open(OWN_ADDRS_CACHE, 'w') as f:
                    json.dump(addrs, f)
                print(f"  Eigene Adressen: {addrs}")
                return addrs
    except Exception as e:
        print(f"  AppleScript Fehler: {e}")
    # Fallback
    fallback = ["moritz.cremer@me.com", "moritz.cremer@icloud.com",
                "moritz.cremer@signicat.com", "londoncityfox@gmail.com",
                "moritz@demoscapital.co", "moritz@vegatechnology.com.br",
                "moritz.cremer@trustedcarrier.net", "moritz@brandshare.me",
                "cremer.moritz@gmx.de", "family.cremer@gmail.com",
                "moritz.cremer@trustedcarrier.de", "naiaraebertz@gmail.com"]
    with open(OWN_ADDRS_CACHE, 'w') as f:
        json.dump(fallback, f)
    return fallback


def is_own(addr):
    """Prueft ob eine E-Mail-Adresse eine eigene ist."""
    addr_lower = addr.lower().strip()
    return any(own.lower() == addr_lower for own in get_own_addresses())


def extract_email_addr(raw):
    """Extrahiert reine E-Mail-Adresse aus 'Name <addr>' Format."""
    m = re.search(r'[\w.+%-]+@[\w.-]+\.[a-zA-Z]{2,}', str(raw))
    return m.group(0).lower() if m else str(raw).lower().strip()

# ── Dateinamen-Bereinigung ───────────────────────────────────────────────────

def clean_for_filename(s, maxlen=55):
    """Bereinigt String fuer Dateinamen."""
    s = re.sub(r'[^\w\s@.-]', ' ', str(s))
    s = re.sub(r'\s+', '_', s.strip())
    s = s.replace('@', '_at_').replace('.', '_')
    s = re.sub(r'_+', '_', s)
    return s[:maxlen].strip('_')

# ── Header-Dekodierung ───────────────────────────────────────────────────────

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

# ── Processed-Log ────────────────────────────────────────────────────────────

def load_processed():
    # Primary: local log
    if os.path.exists(PROCESSED_LOG):
        try:
            with open(PROCESSED_LOG) as f:
                data = json.load(f)
                if data:
                    return set(data)
        except Exception:
            pass
    # Fallback: iCloud mirror
    if os.path.exists(PROCESSED_LOG_MIRROR):
        try:
            with open(PROCESSED_LOG_MIRROR) as f:
                data = json.load(f)
                if data:
                    print(f'[WATCHER] Recovered processed log from iCloud mirror ({len(data)} entries)', flush=True)
                    return set(data)
        except Exception:
            pass
    return set()


def save_processed(processed):
    data = list(processed)
    # Primary: local
    with open(PROCESSED_LOG, 'w') as f:
        json.dump(data, f)
    # Mirror: iCloud (best-effort, don't fail on error)
    try:
        os.makedirs(os.path.dirname(PROCESSED_LOG_MIRROR), exist_ok=True)
        with open(PROCESSED_LOG_MIRROR, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        print(f'[WATCHER] Warning: mirror write failed: {e}', flush=True)

# ── Routing ──────────────────────────────────────────────────────────────────

def _domain_of(addr):
    """Extrahiert Domain aus 'Name <local@domain.tld>' oder 'local@domain.tld'.
    Gibt '' zurueck wenn keine Adresse gefunden."""
    if not addr:
        return ""
    m = re.search(r'@([\w.-]+)', str(addr))
    return m.group(1).lower() if m else ""


def route_agent(direction, sender, to_field):
    """Agent-Routing rein nach Domain der IN-VOLVIERTEN eigenen Adresse.

    - Bei IN: welcher Empfaenger in To/Cc ist "mein" Account?
    - Bei OUT: welche "meine" Absender-Adresse steht im From?

    Mapping:
        signicat.com, signicat.tech -> signicat
        *trustedcarrier*           -> trustedcarrier
        alles andere               -> privat (Default)

    Die Funktion fuellt nie den alten "standard"-Agent — der existiert
    nicht mehr.
    """
    if direction == "OUT":
        candidates = [extract_email_addr(sender)]
    else:
        # alle To/Cc-Adressen durchgehen, "meine" bevorzugen
        candidates = re.findall(r'[\w.+%-]+@[\w.-]+\.[a-zA-Z]{2,}', str(to_field or ""))
        mine = [c for c in candidates if is_own(c)]
        if mine:
            candidates = mine

    for addr in candidates:
        domain = _domain_of(addr)
        if not domain:
            continue
        if domain in DOMAIN_AGENT_MAP_EXACT:
            return DOMAIN_AGENT_MAP_EXACT[domain]
        for marker, agent in DOMAIN_AGENT_MAP_SUBSTR:
            if marker in domain:
                return agent
    return DEFAULT_AGENT

# ── Datei-Extraktion (PDF, DOCX) ────────────────────────────────────────────

def extract_file_content(raw, filename):
    fname = filename.lower()
    if fname.endswith('.pdf'):
        try:
            import PyPDF2
            import io
            reader = PyPDF2.PdfReader(io.BytesIO(raw))
            return "\n".join(p.extract_text() or "" for p in reader.pages)
        except Exception as e:
            return "[PDF: " + str(e) + "]"
    if fname.endswith('.docx'):
        try:
            import zipfile
            import io
            from xml.etree import ElementTree as ET
            z = zipfile.ZipFile(io.BytesIO(raw))
            xml = z.read('word/document.xml')
            tree = ET.fromstring(xml)
            ns = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
            return ' '.join(node.text for node in tree.iter(ns + 't') if node.text)
        except Exception as e:
            return "[DOCX: " + str(e) + "]"
    if any(fname.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.mp4', '.mov']):
        return "[Mediendatei: " + filename + "]"
    try:
        return raw.decode('utf-8', errors='ignore')
    except Exception:
        return "[Nicht lesbar]"

# ── Body + Attachments extrahieren ───────────────────────────────────────────

def extract_body_and_attachments(msg):
    """Extrahiert Body (Plaintext + HTML separat) und Anhaenge.

    Returns: (plaintext_body, html_body_or_None, attachments_list)

    HTML wird ZUSAETZLICH zum Plaintext-Body zurueckgegeben (statt zu
    text-strippen) — Frontend kann damit die Mail formatiert rendern,
    Plaintext bleibt fuer Volltext-Suche/Agent-Kontext sauber.
    """
    body_parts = []
    html_body = None
    attachments = []
    for part in msg.walk():
        ct = part.get_content_type()
        disp = str(part.get('Content-Disposition', ''))
        fname = part.get_filename()
        if fname:
            data = part.get_payload(decode=True)
            if data:
                attachments.append((decode_str(fname), data))
        elif ct == 'text/plain' and 'attachment' not in disp:
            payload = part.get_payload(decode=True)
            if payload:
                body_parts.append(payload.decode('utf-8', errors='ignore'))
        elif ct == 'text/html' and 'attachment' not in disp:
            payload = part.get_payload(decode=True)
            if payload:
                raw_html = payload.decode('utf-8', errors='ignore')
                # HTML separat speichern fuer Frontend-Rendering
                if html_body is None:
                    html_body = raw_html
                # Plaintext-Body nur fallback bauen, wenn keine text/plain-Part
                # da war — sonst landet HTML-stripped Text doppelt im Body.
                if not body_parts:
                    try:
                        from bs4 import BeautifulSoup
                        body_parts.append(BeautifulSoup(raw_html, 'html.parser').get_text(separator='\n', strip=True))
                    except Exception:
                        body_parts.append(raw_html)
    return '\n'.join(body_parts), html_body, attachments

# ── Kontakt-Tracking ────────────────────────────────────────────────────────

def _extract_signature_info(body):
    """Extrahiert Titel und Telefon aus der E-Mail-Signatur."""
    title = None
    phone = None
    sig_text = body
    for marker in ['Best regards', 'Best Regards', 'Kind regards', 'Regards',
                    'Mit freundlichen', 'Viele Gruesse', 'Greetings', 'Cheers',
                    'Thanks', 'Thank you', 'BR,', 'VG,', 'LG,', 'MfG']:
        idx = body.rfind(marker)
        if idx != -1:
            sig_text = body[idx:]
            break
    else:
        sig_text = body[-1500:]
    for pat in _PHONE_PATTERNS:
        m = pat.search(sig_text)
        if m:
            phone = re.sub(r'\s+', ' ', m.group(1).strip())
            break
    for pat in _TITLE_PATTERNS:
        m = pat.search(sig_text)
        if m:
            candidate = m.group(1).strip()
            if 5 < len(candidate) < 80:
                title = candidate
                break
    return title, phone


def _company_from_domain(email_addr):
    """Extrahiert Firmenname aus E-Mail-Domain."""
    m = re.search(r'@([\w.-]+)', email_addr)
    if not m:
        return "Unknown"
    domain = m.group(1).lower()
    generic = {'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com',
               'icloud.com', 'me.com', 'live.com', 'aol.com', 'protonmail.com',
               'gmx.de', 'gmx.net', 'web.de', 'mail.com', 'googlemail.com'}
    if domain in generic:
        return "(Persoenlich)"
    parts = domain.split('.')
    return parts[-2].capitalize() if len(parts) >= 2 else domain.capitalize()


def _extract_name_from_raw(raw_header):
    """Extrahiert den Namen aus 'Name <email>' Format."""
    m = re.match(r'\s*(.+?)\s*<', str(raw_header))
    if m:
        name = m.group(1).strip().strip('"\'')
        if name and '@' not in name:
            return name
    return None


# ── Name-vs-Email Sanity (gegen Contacts-Pollution) ──────────────────────────

def _name_tokens(name):
    """Lowercase, umlaut-normalisierte Alpha-Tokens (>=2 Zeichen) eines Namens."""
    if not name:
        return set()
    s = name.lower()
    for a, b in [('ä', 'ae'), ('ö', 'oe'), ('ü', 'ue'), ('ß', 'ss')]:
        s = s.replace(a, b)
    return {t for t in re.findall(r'[a-z]+', s) if len(t) >= 2}


def _name_matches_email(name, email_addr):
    """True wenn mind. ein >=3 Zeichen Token aus dem Namen im Local-Part vorkommt.
    Wenn der Name keine qualifizierten Tokens enthaelt, akzeptieren (Initialen, kurze Tags).
    """
    if not name or not email_addr or '@' not in email_addr:
        return True
    local = email_addr.split('@')[0].lower()
    local_clean = re.sub(r'[._\-+]', ' ', local)
    qual = [t for t in _name_tokens(name) if len(t) >= 3]
    if not qual:
        return True
    return any(t in local_clean for t in qual)


def _is_strict_name_extension(old_name, new_name):
    """True wenn new_name den old_name strikt erweitert (alle alten Tokens enthalten)."""
    if not old_name:
        return True
    old_t = _name_tokens(old_name)
    new_t = _name_tokens(new_name)
    return bool(old_t) and old_t.issubset(new_t)


def update_contacts_json(memory_dir, contact_addr, contact_name, direction, body):
    """Aktualisiert contacts.json im Agent-Memory mit neuen Kontaktdaten.

    Schutz vor Contacts-Pollution: ein Name aus dem From:-Header wird nur akzeptiert,
    wenn er entweder zur E-Mail-Adresse passt (Token im Local-Part) ODER der Name
    keine qualifizierten Tokens hat. Vorhandene Namen werden NUR ueberschrieben,
    wenn der neue Name eine echte Erweiterung des alten ist.
    """
    contacts_path = os.path.join(memory_dir, "contacts.json")

    # Sanity: mismatched From-Names komplett verwerfen
    if contact_name and not _name_matches_email(contact_name, contact_addr):
        contact_name = None

    # Bestehende Datei laden oder neu erstellen
    data = {'generated': '', 'period_months': 0, 'agent': '', 'total_contacts': 0, 'contacts': []}
    if os.path.exists(contacts_path):
        try:
            with open(contacts_path, 'r') as f:
                data = json.load(f)
        except Exception:
            pass

    contacts = data.get('contacts', [])
    # Kontakt suchen oder neu anlegen
    existing = None
    for c in contacts:
        if c.get('email', '').lower() == contact_addr.lower():
            existing = c
            break

    today = datetime.datetime.now().strftime('%Y-%m-%d')

    if existing:
        existing['total_contacts'] = existing.get('total_contacts', 0) + 1
        if direction == 'OUT':
            existing['sent'] = existing.get('sent', 0) + 1
        else:
            existing['received'] = existing.get('received', 0) + 1
        existing['last_contact'] = today
        # Name updaten nur wenn neuer Name echte Erweiterung des alten ist
        if contact_name:
            existing_name = existing.get('name') or ''
            if not existing_name:
                existing['name'] = contact_name
            elif (len(contact_name) > len(existing_name)
                    and _is_strict_name_extension(existing_name, contact_name)):
                existing['name'] = contact_name
        # Titel/Telefon nur setzen wenn noch leer
        if direction == 'IN' and body:
            title, phone = _extract_signature_info(body)
            if title and not existing.get('title'):
                existing['title'] = title
            if phone and not existing.get('phone'):
                existing['phone'] = phone
    else:
        title, phone = (None, None)
        if direction == 'IN' and body:
            title, phone = _extract_signature_info(body)
        new_contact = {
            'name': contact_name,
            'email': contact_addr,
            'company': _company_from_domain(contact_addr),
            'title': title,
            'phone': phone,
            'total_contacts': 1,
            'sent': 1 if direction == 'OUT' else 0,
            'received': 1 if direction == 'IN' else 0,
            'first_contact': today,
            'last_contact': today,
        }
        contacts.append(new_contact)

    data['contacts'] = contacts
    data['total_contacts'] = len(contacts)
    data['generated'] = datetime.datetime.now().isoformat()

    try:
        with open(contacts_path, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"  Fehler beim Schreiben von contacts.json: {e}")


# ── Kern-Verarbeitung ────────────────────────────────────────────────────────

def process_eml(eml_path, processed):
    eml_name = os.path.basename(eml_path)
    if eml_name in processed:
        return False

    try:
        with open(eml_path, 'rb') as f:
            msg = email.message_from_bytes(f.read())

        subject = decode_str(msg.get('Subject', '(kein Betreff)'))
        sender = decode_str(msg.get('From', ''))
        to = decode_str(msg.get('To', ''))
        date_raw = str(msg.get('Date', ''))

        sender_addr = extract_email_addr(sender)

        # Richtung + Kontakt bestimmen
        if is_own(sender_addr):
            direction = "OUT"
            contact = extract_email_addr(to.split(',')[0])
        else:
            direction = "IN"
            contact = sender_addr

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        body, html_body, attachments = extract_body_and_attachments(msg)
        agent = route_agent(direction, sender, to)

        memory_dir = os.path.join(BASE, agent, "memory")
        os.makedirs(memory_dir, exist_ok=True)

        # Neues Dateinamen-Schema
        contact_clean = clean_for_filename(contact, 40)
        subject_clean = clean_for_filename(subject, 55)
        email_filename = f"{timestamp}_{direction}_{contact_clean}_{subject_clean}.txt"

        # 1) Anhaenge ZUERST speichern — damit wir ihre finalen Namen
        #    im Email-Text referenzieren koennen. Um Kollisionen mit
        #    gleichnamigen Anhaengen anderer Mails zu vermeiden, bekommt
        #    jeder Anhang einen Timestamp+Direction-Prefix, der exakt zum
        #    Email-Filename passt (ohne Subject). Beispiel:
        #        2026-04-20_11-05-12_IN_yuliya_at_onventis_nl__proposal.pdf
        saved_attachments = []
        att_prefix = f"{timestamp}_{direction}_{contact_clean}__"
        for att_name, att_data in attachments:
            safe_att = re.sub(r'[^\w.-]', '_', att_name)
            final_name = f"{att_prefix}{safe_att}"
            att_path = os.path.join(memory_dir, final_name)
            with open(att_path, 'wb') as f:
                f.write(att_data)
            saved_attachments.append(final_name)

        # 2) Header + Body fuer .txt
        separator = '\u2500' * 60
        if saved_attachments:
            anh_line = f"Anhaenge: {len(saved_attachments)} ({', '.join(saved_attachments)})\n"
        else:
            anh_line = "Anhaenge: 0\n"
        # EML-Source-Header: pointer auf die Original-.eml in
        # email_inbox/processed/. Backend kann das fuer HTML-Rendering und
        # MIME-Reparse heranziehen, falls die HTML-Companion-Datei fehlt.
        eml_src_line = f"EML-Source: {eml_name}\n"
        content = (f"Von: {sender}\n"
                   f"An: {to}\n"
                   f"Betreff: {subject}\n"
                   f"Datum: {date_raw}\n"
                   f"Richtung: {direction}\n"
                   f"Kontakt: {contact}\n"
                   f"Agent: {agent}\n"
                   f"Importiert: {timestamp}\n"
                   f"{anh_line}"
                   f"{eml_src_line}"
                   f"{separator}\n\n{body}")

        primary_path = os.path.join(memory_dir, email_filename)
        with open(primary_path, 'w') as f:
            f.write(content)

        # 2b) HTML-Companion-File schreiben, wenn die Mail einen text/html-
        # Part hatte. Frontend rendert das via /api/messages/<id> body_html.
        # Filename: gleicher Stamm wie die .txt, nur Endung .html.
        if html_body:
            html_path = primary_path[:-4] + ".html"
            try:
                with open(html_path, 'w') as f:
                    f.write(html_body)
            except Exception as e:
                print(f"  Warning: html-companion write failed for {email_filename}: {e}")

        # 3) Globale Kopie nach email_inbox/all_emails/ — identischer Text,
        #    damit andere Agenten bei Bedarf Zugriff bekommen koennen.
        try:
            os.makedirs(GLOBAL_EMAIL_DIR, exist_ok=True)
            global_path = os.path.join(GLOBAL_EMAIL_DIR, email_filename)
            with open(global_path, 'w') as f:
                f.write(content)
        except Exception as e:
            print(f"  Warning: global-copy failed for {email_filename}: {e}")

        # Kontakt-Tracking: contacts.json aktualisieren
        if not is_own(contact):
            contact_name = _extract_name_from_raw(sender if direction == "IN" else to.split(',')[0])
            try:
                update_contacts_json(memory_dir, contact, contact_name, direction, body)
            except Exception as e:
                print(f"  Kontakt-Update Fehler: {e}")

        # Index aktualisieren — robustly: direct API first, then a touch
        # fallback so the next reader rebuilds the index.
        _trigger_index_update_for(memory_dir, email_filename)

        processed.add(eml_name)
        save_processed(processed)

        # Move .eml out of inbox root so ls shows only pending mail
        try:
            os.makedirs(PROCESSED_SUBDIR, exist_ok=True)
            dest = os.path.join(PROCESSED_SUBDIR, eml_name)
            if os.path.exists(dest):
                base, ext = os.path.splitext(eml_name)
                dest = os.path.join(PROCESSED_SUBDIR, f"{base}_{timestamp}{ext}")
            os.rename(eml_path, dest)
        except Exception as e:
            print(f"  Warning: move-to-processed failed for {eml_name}: {e}")

        print(f"  [{direction}] {subject[:50]} -> {agent} ({len(saved_attachments)} Anhaenge)")
        return True

    except Exception as e:
        print(f"  Fehler bei {eml_name}: {e}")
        return False

# ── Main Loop ────────────────────────────────────────────────────────────────

def _migrate_processed_emls(processed):
    """One-time cleanup: move already-processed .eml files out of inbox root.

    Historically process_eml left the .eml in place, which bloated inbox to 21k+
    files. Any .eml whose name is in the processed set is moved to PROCESSED_SUBDIR.
    """
    os.makedirs(PROCESSED_SUBDIR, exist_ok=True)
    moved = 0
    try:
        entries = os.listdir(WATCH_DIR)
    except Exception as e:
        print(f"[MIGRATE] listdir failed: {e}", flush=True)
        return
    for fname in entries:
        if not fname.endswith('.eml'):
            continue
        if fname not in processed:
            continue
        src = os.path.join(WATCH_DIR, fname)
        dest = os.path.join(PROCESSED_SUBDIR, fname)
        if os.path.exists(dest):
            continue  # already migrated
        try:
            os.rename(src, dest)
            moved += 1
        except Exception as e:
            print(f"[MIGRATE] move failed for {fname}: {e}", flush=True)
    if moved:
        print(f"[MIGRATE] Moved {moved} already-processed .eml files to {PROCESSED_SUBDIR}", flush=True)


# How often the watcher scans the iCloud inbox folder. Apple Mail's rule writes
# .eml files there as soon as a mail arrives, so a tighter loop means freshly
# received mails show up in the agent memory within seconds.
POLL_INTERVAL_SEC = 2

# Optional: ask Apple Mail to fetch new mail explicitly. Without this the
# watcher only sees what Mail's own polling has already pulled, which on
# battery / energy-saver schedules can lag for minutes. We keep it cheap by
# only firing every FORCE_SYNC_EVERY iterations of the watch loop.
FORCE_SYNC_EVERY = 30  # ~ once per minute when POLL_INTERVAL_SEC=2


def force_apple_mail_sync():
    """Tell Apple Mail to immediately check all accounts for new messages.
    Best-effort — failures are silently swallowed (Mail not running, AppleScript
    permission denied, etc.). Triggers do not block the watcher."""
    try:
        subprocess.run(
            ['osascript', '-e', 'tell application "Mail" to check for new mail'],
            capture_output=True, timeout=10,
        )
    except Exception:
        pass


def _trigger_index_update_for(memory_dir, email_filename):
    """Update the per-agent search index for a single email file.

    The PyInstaller-frozen app cannot import `search_engine` cleanly because
    its module-level threads spin up a heavy embedding pipeline. We try the
    direct API first; if it fails we degrade gracefully — `update_all_indexes`
    in the web server will pick the new file up on its next pass."""
    if not index_single_file:
        return
    try:
        index_single_file(os.path.dirname(memory_dir), email_filename)
        return
    except Exception as e:
        print(f"  index_single_file({email_filename}) failed: {e}", flush=True)
    # Last resort: invalidate the index file so the next reader rebuilds it.
    try:
        idx_file = os.path.join(os.path.dirname(memory_dir), '.search_index.json')
        if os.path.exists(idx_file):
            os.utime(idx_file, None)  # touch to mark stale
    except Exception:
        pass


def main():
    os.makedirs(WATCH_DIR, exist_ok=True)
    processed = load_processed()
    get_own_addresses()  # Einmal beim Start laden/cachen

    print(f"""
Email Watcher v2 gestartet
{'─' * 45}
Ordner: {WATCH_DIR}
Log:    {PROCESSED_LOG}
Junk-Filter: Apple Mail Regel (vorgelagert)
Polling: alle {POLL_INTERVAL_SEC}s, Apple Mail Force-Sync alle {FORCE_SYNC_EVERY * POLL_INTERVAL_SEC}s
Control+C zum Beenden.
{'─' * 45}
""", flush=True)

    _migrate_processed_emls(processed)

    loop_iter = 0
    while True:
        try:
            loop_iter += 1
            if loop_iter % FORCE_SYNC_EVERY == 1:
                # First iteration and every ~minute thereafter: nudge Apple
                # Mail so we don't sit and wait for its own poll schedule.
                force_apple_mail_sync()
            for fname in sorted(os.listdir(WATCH_DIR)):
                if not fname.endswith('.eml'):
                    continue
                # Reconcile: .eml in inbox root is authoritative. If it's also
                # in `processed` (crash between save_processed and the move),
                # drop the processed entry so process_eml re-runs and moves it.
                if fname in processed:
                    print(f"[RECONCILE] {fname} marked processed but still in inbox — re-processing", flush=True)
                    processed.discard(fname)
                    save_processed(processed)
                process_eml(os.path.join(WATCH_DIR, fname), processed)
            time.sleep(POLL_INTERVAL_SEC)
        except KeyboardInterrupt:
            print("\nEmail Watcher beendet.")
            break
        except Exception as e:
            print(f"Fehler: {e}")
            time.sleep(10)


if __name__ == '__main__':
    main()
