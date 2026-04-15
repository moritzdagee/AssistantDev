#!/usr/bin/env python3
"""
Patch web_server.py for two bugs:
1. Remove numberOfVideos from Veo API call
2. Fix context-bleeding: replace CREATE_WHATSAPP/EMAIL/SLACK blocks with
   execution markers so the LLM knows the action was already performed
"""

filepath = '/Users/moritzcremer/AssistantDev/src/web_server.py'

with open(filepath, 'r') as f:
    content = f.read()

changes = 0

# =============================================================
# Bug 1: Remove numberOfVideos from Veo API call
# =============================================================
old_veo = '"parameters": {"aspectRatio": "16:9", "numberOfVideos": 1}'
new_veo = '"parameters": {"aspectRatio": "16:9"}'

count = content.count(old_veo)
if count == 0:
    print("ERROR: numberOfVideos pattern not found!")
    exit(1)
content = content.replace(old_veo, new_veo)
print(f"Bug 1: Removed numberOfVideos ({count} occurrence(s))")
changes += count

# =============================================================
# Bug 2: Context-Bleeding — replace CREATE_WHATSAPP blocks with
# execution marker instead of silently removing them
# =============================================================

# Fix 2a: CREATE_EMAIL — after successful execution, insert marker
old_email_ok = """                    send_email_draft(spec)
                    created_emails.append({'ok': True, 'subject': spec.get('subject',''), 'to': spec.get('to',''), 'body': spec.get('body','')})
                    text = text[:eidx] + text[jend+1:]
                    ei = eidx"""

new_email_ok = """                    send_email_draft(spec)
                    created_emails.append({'ok': True, 'subject': spec.get('subject',''), 'to': spec.get('to',''), 'body': spec.get('body','')})
                    marker = f'\\n[E-Mail-Draft an {spec.get("to","")} erstellt — Aktion ausgefuehrt]\\n'
                    text = text[:eidx] + marker + text[jend+1:]
                    ei = eidx + len(marker)"""

count = content.count(old_email_ok)
if count == 0:
    print("WARNING: CREATE_EMAIL ok-block not found (may have changed)")
else:
    content = content.replace(old_email_ok, new_email_ok)
    print(f"Bug 2a: Patched CREATE_EMAIL ok-block ({count} occurrence(s))")
    changes += count

# Fix 2a-err: CREATE_EMAIL — after failed execution, insert error marker
old_email_err = """                    created_emails.append({'ok': False, 'subject': spec.get('subject',''), 'to': '', 'error': str(ee), 'body': spec.get('body','')})
                    text = text[:eidx] + text[jend+1:]
                    ei = eidx"""

new_email_err = """                    created_emails.append({'ok': False, 'subject': spec.get('subject',''), 'to': '', 'error': str(ee), 'body': spec.get('body','')})
                    marker = '\\n[E-Mail-Erstellung fehlgeschlagen]\\n'
                    text = text[:eidx] + marker + text[jend+1:]
                    ei = eidx + len(marker)"""

count = content.count(old_email_err)
if count > 0:
    content = content.replace(old_email_err, new_email_err)
    print(f"Bug 2a-err: Patched CREATE_EMAIL error-block ({count} occurrence(s))")
    changes += count

# Fix 2b: CREATE_WHATSAPP — after successful execution, insert marker
old_wa_ok = """                    wspec = json.loads(json_str)
                    agent_name = state.get('agent', 'standard')
                    wa_to, wa_phone = send_whatsapp_draft(wspec, agent_name)
                    created_whatsapps.append({'ok': True, 'to': wa_to, 'phone': wa_phone, 'clipboard_fallback': wa_phone is None})
                    text = text[:widx] + text[wjend+1:]
                    wi = widx"""

new_wa_ok = """                    wspec = json.loads(json_str)
                    agent_name = state.get('agent', 'standard')
                    wa_to, wa_phone = send_whatsapp_draft(wspec, agent_name)
                    created_whatsapps.append({'ok': True, 'to': wa_to, 'phone': wa_phone, 'clipboard_fallback': wa_phone is None})
                    marker = f'\\n[WhatsApp an {wa_to} vorbereitet — Aktion ausgefuehrt]\\n'
                    text = text[:widx] + marker + text[wjend+1:]
                    wi = widx + len(marker)"""

count = content.count(old_wa_ok)
if count == 0:
    print("WARNING: CREATE_WHATSAPP ok-block not found")
else:
    content = content.replace(old_wa_ok, new_wa_ok)
    print(f"Bug 2b: Patched CREATE_WHATSAPP ok-block ({count} occurrence(s))")
    changes += count

# Fix 2b-err: CREATE_WHATSAPP — after failed execution
old_wa_err = """                    created_whatsapps.append({'ok': False, 'to': wspec.get('to',''), 'error': str(we)})
                    text = text[:widx] + text[wjend+1:]
                    wi = widx"""

new_wa_err = """                    created_whatsapps.append({'ok': False, 'to': wspec.get('to',''), 'error': str(we)})
                    marker = '\\n[WhatsApp-Erstellung fehlgeschlagen]\\n'
                    text = text[:widx] + marker + text[wjend+1:]
                    wi = widx + len(marker)"""

count = content.count(old_wa_err)
if count > 0:
    content = content.replace(old_wa_err, new_wa_err)
    print(f"Bug 2b-err: Patched CREATE_WHATSAPP error-block ({count} occurrence(s))")
    changes += count

# Fix 2c: CREATE_SLACK — after successful execution
old_sl_ok = """                    created_slacks.append({'ok': True, 'target': sl_target, 'clipboard_only': sl_clipboard})
                    text = text[:sidx] + text[sjend+1:]
                    si = sidx"""

new_sl_ok = """                    created_slacks.append({'ok': True, 'target': sl_target, 'clipboard_only': sl_clipboard})
                    marker = f'\\n[Slack-Nachricht an {sl_target} vorbereitet — Aktion ausgefuehrt]\\n'
                    text = text[:sidx] + marker + text[sjend+1:]
                    si = sidx + len(marker)"""

count = content.count(old_sl_ok)
if count > 0:
    content = content.replace(old_sl_ok, new_sl_ok)
    print(f"Bug 2c: Patched CREATE_SLACK ok-block ({count} occurrence(s))")
    changes += count

# Fix 2c-err: CREATE_SLACK — after failed execution
old_sl_err = """                    created_slacks.append({'ok': False, 'target': sspec.get('channel', sspec.get('to', '')), 'error': str(se)})
                    text = text[:sidx] + text[sjend+1:]
                    si = sidx"""

new_sl_err = """                    created_slacks.append({'ok': False, 'target': sspec.get('channel', sspec.get('to', '')), 'error': str(se)})
                    marker = '\\n[Slack-Erstellung fehlgeschlagen]\\n'
                    text = text[:sidx] + marker + text[sjend+1:]
                    si = sidx + len(marker)"""

count = content.count(old_sl_err)
if count > 0:
    content = content.replace(old_sl_err, new_sl_err)
    print(f"Bug 2c-err: Patched CREATE_SLACK error-block ({count} occurrence(s))")
    changes += count

# =============================================================
# Bug 2d: Add system prompt instruction to avoid re-triggering
# =============================================================
old_wa_instruction = """WICHTIG: WhatsApp-Nachrichten werden NIEMALS automatisch gesendet. Die App wird nur geoeffnet mit vorausgefuelltem Text. Der Nutzer muss manuell auf Senden klicken. Verwende dies wenn der Nutzer sagt: 'schreib auf WhatsApp', 'WhatsApp an', 'schick per WhatsApp'."""

new_wa_instruction = """WICHTIG: WhatsApp-Nachrichten werden NIEMALS automatisch gesendet. Die App wird nur geoeffnet mit vorausgefuelltem Text. Der Nutzer muss manuell auf Senden klicken. Verwende dies wenn der Nutzer sagt: 'schreib auf WhatsApp', 'WhatsApp an', 'schick per WhatsApp'.

KEINE WIEDERHOLUNG: Wenn im Verlauf bereits eine Aktion ausgefuehrt wurde (erkennbar an '[... — Aktion ausgefuehrt]'), erzeuge diese Aktion NICHT erneut. Jede CREATE_EMAIL, CREATE_WHATSAPP, CREATE_SLACK und CREATE_VIDEO Aktion darf nur EINMAL pro expliziter Nutzer-Anfrage erzeugt werden. Wenn der Nutzer eine NEUE Anfrage stellt (z.B. Video generieren statt WhatsApp), fuehre NUR die neue Aktion aus."""

count = content.count(old_wa_instruction)
if count > 0:
    content = content.replace(old_wa_instruction, new_wa_instruction)
    print(f"Bug 2d: Added anti-repeat instruction to system prompt ({count} occurrence(s))")
    changes += count
else:
    print("WARNING: WhatsApp instruction block not found for anti-repeat patch")

with open(filepath, 'w') as f:
    f.write(content)

print(f"\nTotal changes: {changes}")
print("DONE: Patched successfully")
