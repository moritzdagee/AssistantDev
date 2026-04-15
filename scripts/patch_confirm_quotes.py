#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fix the quote escaping in showSubagentConfirmation onclick handlers."""

filepath = '/Users/moritzcremer/AssistantDev/src/web_server.py'

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# The problem: \' inside a Python string inside HTML onclick
# Solution: use &apos; for HTML attribute context

old_btn1 = """  inner += '<button onclick="confirmSubagent(\\'' + data.confirmation_id + '\\',true)" style="background:#4a8a4a;color:#fff;border:none;padding:6px 16px;border-radius:4px;cursor:pointer;margin-right:8px;">\\u2713 Ja, weiterleiten</button>';"""

new_btn1 = """  inner += '<button onclick="confirmSubagent(&apos;' + data.confirmation_id + '&apos;,true)" style="background:#4a8a4a;color:#fff;border:none;padding:6px 16px;border-radius:4px;cursor:pointer;margin-right:8px;">\\u2713 Ja, weiterleiten</button>';"""

old_btn2 = """  inner += '<button onclick="confirmSubagent(\\'' + data.confirmation_id + '\\',false)" style="background:#555;color:#fff;border:none;padding:6px 16px;border-radius:4px;cursor:pointer;">\\u2717 Nein, selbst antworten</button>';"""

new_btn2 = """  inner += '<button onclick="confirmSubagent(&apos;' + data.confirmation_id + '&apos;,false)" style="background:#555;color:#fff;border:none;padding:6px 16px;border-radius:4px;cursor:pointer;">\\u2717 Nein, selbst antworten</button>';"""

c1 = content.count(old_btn1)
c2 = content.count(old_btn2)

if c1 > 0:
    content = content.replace(old_btn1, new_btn1)
    print(f"Fixed button 1 ({c1})")
else:
    print("WARNING: Button 1 pattern not found")

if c2 > 0:
    content = content.replace(old_btn2, new_btn2)
    print(f"Fixed button 2 ({c2})")
else:
    print("WARNING: Button 2 pattern not found")

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("DONE")
