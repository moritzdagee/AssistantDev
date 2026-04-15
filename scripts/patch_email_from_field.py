#!/usr/bin/env python3
"""Patch web_server.py to add 'from' field support to CREATE_EMAIL and CREATE_EMAIL_REPLY."""

FILE = 'src/web_server.py'

with open(FILE, 'r') as f:
    lines = f.readlines()

content = ''.join(lines)

# ============================================================
# 1. Patch send_email_draft (both copies at ~278 and ~994)
#    Add sender extraction and AppleScript sender line
# ============================================================

# Add "sender = spec.get('from', '')" after "cc = spec.get('cc', '')" in send_email_draft
# We need to be careful: only add in send_email_draft, not send_email_reply
# Strategy: find all occurrences of the cc line, then check context

changes = 0

# 1a. Add sender variable in send_email_draft
# Find pattern: "    cc      = spec.get('cc', '')\n\n    # Escape for AppleScript"
old_draft_cc = "    cc      = spec.get('cc', '')\n\n    # Escape for AppleScript"
new_draft_cc = "    cc      = spec.get('cc', '')\n    sender  = spec.get('from', '')\n\n    # Escape for AppleScript"
count = content.count(old_draft_cc)
print(f"send_email_draft cc pattern: {count} matches")
if count >= 2:
    content = content.replace(old_draft_cc, new_draft_cc)
    changes += count
else:
    print("ERROR: Expected at least 2 matches for send_email_draft cc pattern")
    exit(1)

# 1b. Add sender_line variable after cc_line in send_email_draft
old_cc_line_var = """    cc_line = f'\\n        make new cc recipient at end of cc recipients with properties {{address:\\"{esc(cc)}\\"}}' if cc else ''

    script = f'''tell application "Mail"
    set newMessage to make new outgoing message with properties {{subject:"{esc(subject)}", content:"{esc(body)}", visible:true}}
    tell newMessage
        make new to recipient at end of to recipients with properties {{address:"{esc(to)}"}}{cc_line}
    end tell
    activate
end tell'''"""

new_cc_line_var = """    cc_line = f'\\n        make new cc recipient at end of cc recipients with properties {{address:\\"{esc(cc)}\\"}}' if cc else ''
    sender_line = f'\\n    set sender of newMessage to "{esc(sender)}"' if sender else ''

    script = f'''tell application "Mail"
    set newMessage to make new outgoing message with properties {{subject:"{esc(subject)}", content:"{esc(body)}", visible:true}}
    tell newMessage
        make new to recipient at end of to recipients with properties {{address:"{esc(to)}"}}{cc_line}
    end tell{sender_line}
    activate
end tell'''"""

count = content.count(old_cc_line_var)
print(f"send_email_draft script pattern: {count} matches")
if count >= 2:
    content = content.replace(old_cc_line_var, new_cc_line_var)
    changes += count
else:
    print("ERROR: Expected at least 2 matches for send_email_draft script pattern")
    exit(1)

# ============================================================
# 2. Patch send_email_reply - add from/sender support
# ============================================================

# 2a. Add sender extraction
old_reply_vars = """    cc      = spec.get('cc', '')
    message_id = spec.get('message_id', '')"""
new_reply_vars = """    cc      = spec.get('cc', '')
    sender  = spec.get('from', '')
    message_id = spec.get('message_id', '')"""

count = content.count(old_reply_vars)
print(f"send_email_reply vars pattern: {count} matches")
if count >= 1:
    content = content.replace(old_reply_vars, new_reply_vars)
    changes += count

# 2b. Add sender to the reply branch (set sender of replyMsg)
# After the "end tell" of replyMsg and before "else"
old_reply_tell = """            set content to "{esc(body)}"{cc_lines}
        end tell
    else"""
new_reply_tell = """            set content to "{esc(body)}"{cc_lines}
        end tell
        {f'set sender of replyMsg to "{esc(sender)}"' if sender else ''}
    else"""

count = content.count(old_reply_tell)
print(f"reply tell block pattern: {count} matches")
if count >= 1:
    content = content.replace(old_reply_tell, new_reply_tell)
    changes += count

# 2c. Add sender to fallback new-email blocks inside send_email_reply
# There are two: one inside the if-message_id else clause, one for no-message_id
# Both have the same pattern but inside send_email_reply context

# The "else" fallback inside the message_id found block:
old_fb_inner = """        set newMessage to make new outgoing message with properties {{subject:"{esc(subject)}", content:"{esc(body)}", visible:true}}
        tell newMessage
            make new to recipient at end of to recipients with properties {{address:"{esc(to)}"}}{cc_lines}
        end tell
    end if
    activate
end tell'''
    else:
        # No message_id: fallback to regular new email
        script = f'''tell application "Mail"
    set newMessage to make new outgoing message with properties {{subject:"{esc(subject)}", content:"{esc(body)}", visible:true}}
    tell newMessage
        make new to recipient at end of to recipients with properties {{address:"{esc(to)}"}}{cc_lines}
    end tell
    activate
end tell'''"""

new_fb_inner = """        set newMessage to make new outgoing message with properties {{subject:"{esc(subject)}", content:"{esc(body)}", visible:true}}
        tell newMessage
            make new to recipient at end of to recipients with properties {{address:"{esc(to)}"}}{cc_lines}
        end tell
        {f'set sender of newMessage to "{esc(sender)}"' if sender else ''}
    end if
    activate
end tell'''
    else:
        # No message_id: fallback to regular new email
        sender_line = f'\\n    set sender of newMessage to "{esc(sender)}"' if sender else ''
        script = f'''tell application "Mail"
    set newMessage to make new outgoing message with properties {{subject:"{esc(subject)}", content:"{esc(body)}", visible:true}}
    tell newMessage
        make new to recipient at end of to recipients with properties {{address:"{esc(to)}"}}{cc_lines}
    end tell{sender_line}
    activate
end tell'''"""

count = content.count(old_fb_inner)
print(f"reply fallback pattern: {count} matches")
if count >= 1:
    content = content.replace(old_fb_inner, new_fb_inner)
    changes += count

# ============================================================
# 3. Update system prompt documentation
# ============================================================

old_prompt = '[CREATE_EMAIL:{"to":"empfaenger@example.com","cc":"","subject":"Betreff","body":"E-Mail Text hier"}]'
new_prompt = '[CREATE_EMAIL:{"to":"empfaenger@example.com","cc":"","subject":"Betreff","body":"E-Mail Text hier","from":"optionale-absender@example.com"}]'
count = content.count(old_prompt)
print(f"prompt CREATE_EMAIL: {count} matches")
content = content.replace(old_prompt, new_prompt)

old_prompt_r = '[CREATE_EMAIL_REPLY:{"message_id":"<original-message-id@domain.com>","to":"absender@example.com","cc":"andere@example.com","subject":"Re: Betreff","body":"Antworttext hier","quote_original":true}]'
new_prompt_r = '[CREATE_EMAIL_REPLY:{"message_id":"<original-message-id@domain.com>","to":"absender@example.com","cc":"andere@example.com","subject":"Re: Betreff","body":"Antworttext hier","quote_original":true,"from":"optionale-absender@example.com"}]'
count = content.count(old_prompt_r)
print(f"prompt CREATE_EMAIL_REPLY: {count} matches")
content = content.replace(old_prompt_r, new_prompt_r)

old_doc = "- Falls keine message_id verfuegbar: verwende CREATE_EMAIL als Fallback"
new_doc = """- Falls keine message_id verfuegbar: verwende CREATE_EMAIL als Fallback
- from: (Optional) Absender-E-Mail-Adresse. Wenn angegeben, wird dieser Account in Apple Mail als Sender verwendet. Nur setzen wenn ein bestimmter Absender-Account gewuenscht ist."""
count = content.count(old_doc)
print(f"from doc: {count} matches")
content = content.replace(old_doc, new_doc)

with open(FILE, 'w') as f:
    f.write(content)

print(f"\nTotal changes applied. File written: {FILE}")
