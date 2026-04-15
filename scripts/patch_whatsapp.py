#!/usr/bin/env python3
"""Patch send_whatsapp_draft in web_server.py to add macOS Contacts lookup."""

import re

filepath = '/Users/moritzcremer/AssistantDev/src/web_server.py'

with open(filepath, 'r') as f:
    content = f.read()

# The old function (exact match)
old_function = '''def send_whatsapp_draft(spec, agent_name=None):
    """Opens WhatsApp with a pre-filled message. Looks up phone in contacts.json."""
    import subprocess
    import urllib.parse

    to_name = spec.get('to', '')
    message = spec.get('message', '')
    phone = spec.get('phone', '')  # Optional direct phone

    # If no direct phone, look up in contacts.json
    if not phone and to_name and agent_name:
        parent = agent_name.split('_')[0] if '_' in agent_name else agent_name
        contacts_path = os.path.join(BASE, parent, "memory", "contacts.json")
        if os.path.exists(contacts_path):
            try:
                with open(contacts_path) as f:
                    cdata = json.load(f)
                to_lower = to_name.lower()
                for c in cdata.get('contacts', []):
                    cname = (c.get('name') or '').lower()
                    if to_lower in cname or cname in to_lower:
                        if c.get('phone'):
                            phone = c['phone']
                            break
            except Exception:
                pass

    if not phone:
        # Fallback: copy message to clipboard and just open WhatsApp
        if message:
            subprocess.run(['pbcopy'], input=message.encode('utf-8'), timeout=5)
        subprocess.run(['open', '-a', 'WhatsApp'], capture_output=True, text=True, timeout=10)
        return to_name, None  # None signals clipboard fallback

    # Normalize phone: remove spaces, dashes, dots, leading +
    phone_clean = re.sub(r'[\\s./-]', '', phone).lstrip('+')

    encoded_msg = urllib.parse.quote(message)
    whatsapp_url = f"whatsapp://send?phone={phone_clean}&text={encoded_msg}"

    result = subprocess.run(['open', whatsapp_url], capture_output=True, text=True, timeout=10)
    if result.returncode != 0:
        raise Exception(f"WhatsApp konnte nicht geoeffnet werden: {result.stderr.strip()}")
    return to_name, phone'''

new_function = '''def send_whatsapp_draft(spec, agent_name=None):
    """Opens WhatsApp with a pre-filled message. Looks up phone in contacts.json, then macOS Contacts."""
    import subprocess
    import urllib.parse

    to_name = spec.get('to', '')
    message = spec.get('message', '')
    phone = spec.get('phone', '')  # Optional direct phone

    # Step 1: Look up in agent's contacts.json
    if not phone and to_name and agent_name:
        parent = agent_name.split('_')[0] if '_' in agent_name else agent_name
        contacts_path = os.path.join(BASE, parent, "memory", "contacts.json")
        if os.path.exists(contacts_path):
            try:
                with open(contacts_path) as f:
                    cdata = json.load(f)
                to_lower = to_name.lower()
                for c in cdata.get('contacts', []):
                    cname = (c.get('name') or '').lower()
                    if to_lower in cname or cname in to_lower:
                        if c.get('phone'):
                            phone = c['phone']
                            break
            except Exception:
                pass

    # Step 2: Look up in ALL agents' contacts.json files (cross-agent)
    if not phone and to_name:
        try:
            to_lower = to_name.lower()
            for agent_dir in os.listdir(BASE):
                cpath = os.path.join(BASE, agent_dir, "memory", "contacts.json")
                if os.path.isfile(cpath):
                    try:
                        with open(cpath) as f:
                            cdata = json.load(f)
                        for c in cdata.get('contacts', []):
                            cname = (c.get('name') or '').lower()
                            if to_lower in cname or cname in to_lower:
                                if c.get('phone'):
                                    phone = c['phone']
                                    break
                    except Exception:
                        continue
                if phone:
                    break
        except Exception:
            pass

    # Step 3: Look up in macOS Contacts app via AppleScript
    if not phone and to_name:
        try:
            script = f"""
            tell application "Contacts"
                set matchedPeople to every person whose name contains "{to_name}"
                if (count of matchedPeople) > 0 then
                    set thePerson to item 1 of matchedPeople
                    set thePhones to phones of thePerson
                    if (count of thePhones) > 0 then
                        set theNumber to value of item 1 of thePhones
                        return theNumber
                    end if
                end if
                return ""
            end tell
            """
            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True, text=True, timeout=10
            )
            found_phone = result.stdout.strip()
            if found_phone:
                phone = found_phone
        except Exception:
            pass

    if not phone:
        # Fallback: copy message to clipboard and just open WhatsApp
        if message:
            subprocess.run(['pbcopy'], input=message.encode('utf-8'), timeout=5)
        subprocess.run(['open', '-a', 'WhatsApp'], capture_output=True, text=True, timeout=10)
        return to_name, None  # None signals clipboard fallback

    # Normalize phone: remove spaces, dashes, dots, leading +
    phone_clean = re.sub(r'[\\s./-]', '', phone).lstrip('+')

    encoded_msg = urllib.parse.quote(message)
    whatsapp_url = f"whatsapp://send?phone={phone_clean}&text={encoded_msg}"

    result = subprocess.run(['open', whatsapp_url], capture_output=True, text=True, timeout=10)
    if result.returncode != 0:
        raise Exception(f"WhatsApp konnte nicht geoeffnet werden: {result.stderr.strip()}")
    return to_name, phone'''

if old_function not in content:
    print("ERROR: Old function not found in file! Manual check needed.")
    exit(1)

content = content.replace(old_function, new_function)

# Also update the frontend status messages
old_status_ok = "if (wa && wa.ok && wa.clipboard_fallback) addStatusMsg('\\u260E WhatsApp geoeffnet \\u2014 Nachricht in Zwischenablage kopiert (kein Kontakt). Bitte einf\\u00fcgen und absenden.');"
new_status_ok = "if (wa && wa.ok && wa.clipboard_fallback) addStatusMsg('\\u260E WhatsApp geoeffnet \\u2014 Keine Nummer fuer \\u201c'+wa.to+'\\u201d gefunden. Nachricht in Zwischenablage \\u2014 bitte manuell einfuegen.');"

old_status_chat = "else if (wa && wa.ok) addStatusMsg('\\u260E WhatsApp geoeffnet \\u2014 Nachricht an '+wa.to+' ist vorausgefuellt. Bitte manuell absenden.');"
new_status_chat = "else if (wa && wa.ok) addStatusMsg('\\u260E WhatsApp geoeffnet \\u2014 Chat mit '+wa.to+' wird geoeffnet. Bitte auf Senden klicken.');"

if old_status_ok in content:
    content = content.replace(old_status_ok, new_status_ok)
    print("OK: Updated clipboard_fallback status message")
else:
    print("WARNING: clipboard_fallback status message not found")

if old_status_chat in content:
    content = content.replace(old_status_chat, new_status_chat)
    print("OK: Updated chat-opened status message")
else:
    print("WARNING: chat-opened status message not found")

with open(filepath, 'w') as f:
    f.write(content)

print("OK: Patched send_whatsapp_draft successfully")
