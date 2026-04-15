#!/usr/bin/env python3
"""Fix: search result checkboxes should default to unchecked."""

SRC = "/Users/moritzcremer/AssistantDev/src/web_server.py"

with open(SRC, 'r') as f:
    code = f.read()

changes = 0

# Remove auto-check of first 5 results
old = "    if (!isNotif && checkedCount < 5) { cb.checked = true; checkedCount++; }"
new = "    // All unchecked by default — user selects manually"
if old in code:
    code = code.replace(old, new, 1)
    changes += 1
    print("1. Checkbox auto-check removed")

# Update counter text to not show "/ 5"
old = "  if (counter) counter.textContent = checked + ' / 5 ausgewaehlt';"
new = "  if (counter) counter.textContent = checked + ' ausgewaehlt (max 5)';"
if old in code:
    code = code.replace(old, new, 1)
    changes += 1
    print("2. Counter text updated")

with open(SRC, 'w') as f:
    f.write(code)

print(f"\n{changes} fixes applied.")
