#!/usr/bin/env python3
"""CRITICAL FIX: JS-String-Literale enthalten echte Newlines statt \\n.
Python rendert \\n in triple-quoted strings als echte Newlines, aber JS
braucht \\n als Escape-Sequence. Fix: alle msg += '\\n...' Stellen in den
handleCalendarCommand und handleCanvaCommand Funktionen reparieren.
"""
import os, re
WS = os.path.expanduser("~/AssistantDev/src/web_server.py")
src = open(WS).read()

# Finde alle JS-Zeilen die msg += '\n...' oder let msg = '...\n' enthalten
# Diese sind innerhalb der Python HTML-Template-String und muessen \\n haben
# (damit Python ein literales \n ausgibt, das JS als Escape interpretiert)

count = 0

# Pattern: In JS-Codezeilen innerhalb des HTML-Templates,
# finde Strings die \n (echtes Newline INNERHALB eines JS-Strings) enthalten.
# D.h. eine Zeile endet mit   msg += '   oder   let msg = '...   und die naechste Zeile
# ist die Fortsetzung des Strings.

# Einfacher Ansatz: Finde alle Vorkommen von \n innerhalb von JS msg-Strings
# und ersetze sie durch \\n

lines = src.split('\n')
new_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    # Erkenne Zeilen die mit einem offenen JS-String enden
    # z.B.: "    let msg = '**... Termine)\n';" wird zu einer Zeile mit \n drin
    # Aber im Python-Source ist das \n ein echtes Newline — also sind es 2 Zeilen:
    # Zeile 1: "    let msg = '**... Termine)"
    # Zeile 2: "';"

    # Suche nach Pattern: eine Zeile endet mit einem offenen single-quoted JS String
    # UND die naechste Zeile setzt den String fort
    stripped = line.rstrip()
    if (("msg +=" in line or "msg =" in line or "let msg" in line) and
        stripped.endswith("'") and not stripped.endswith("\\'") and not stripped.endswith("''") and
        ";" not in stripped.split("'")[-1]):
        # Prüfe ob die nächste Zeile eine Fortsetzung ist
        if i + 1 < len(lines):
            next_line = lines[i + 1]
            next_stripped = next_line.lstrip()
            if next_stripped and (next_stripped[0] in "'\\-*" or next_stripped.startswith("Keine") or
                                  next_stripped.startswith("- ") or next_stripped.startswith("**")):
                # Merge: füge \\n ein statt des Newline
                merged = line.rstrip() + "\\n" + lines[i + 1].lstrip()
                new_lines.append(merged)
                count += 1
                i += 2
                continue

    new_lines.append(line)
    i += 1

if count > 0:
    new_src = '\n'.join(new_lines)
    open(WS, 'w').write(new_src)
    print(f"OK: {count} JS-Newlines repariert")
else:
    print("Keine kaputten Newlines gefunden")
