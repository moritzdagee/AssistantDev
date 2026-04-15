#!/usr/bin/env python3
"""Erstellt memory/attachments/ Unterordner und verschiebt Nicht-Email Dateien.

Interpretation: Email-Kandidaten sind .eml, .txt, .json (Config/Meta).
Alles andere (PDFs, Bilder, CSVs, Office-Dokumente, UUIDs ohne Extension) = Attachments.
"""
import os
import shutil
import datetime

BASE = os.path.expanduser("~/Library/Mobile Documents/com~apple~CloudDocs/Downloads shared/claude_datalake")
AGENTS = ['privat', 'signicat', 'standard', 'trustedcarrier']

# Extensions that stay in memory/ (emails + metadata)
KEEP_EXTS = {'.eml', '.txt', '.json'}

report = []

for agent in AGENTS:
    mem = os.path.join(BASE, agent, 'memory')
    att = os.path.join(mem, 'attachments')
    if not os.path.exists(mem):
        continue
    os.makedirs(att, exist_ok=True)

    moved = 0
    kept = 0
    errors = 0

    for entry in os.scandir(mem):
        if entry.is_dir():
            continue  # Skip subdirs (including attachments itself)
        name = entry.name
        # Skip hidden files
        if name.startswith('.'):
            continue
        # Extract extension (case-insensitive)
        ext = os.path.splitext(name)[1].lower()
        if ext in KEEP_EXTS:
            kept += 1
            continue
        # Move to attachments/
        src = entry.path
        dst = os.path.join(att, name)
        try:
            # Handle name collisions
            if os.path.exists(dst):
                base, ext2 = os.path.splitext(name)
                counter = 1
                while os.path.exists(dst):
                    dst = os.path.join(att, f"{base}_{counter}{ext2}")
                    counter += 1
            shutil.move(src, dst)
            moved += 1
        except Exception as e:
            errors += 1
            print(f"  ERROR moving {name}: {e}")

    line = f"{agent}: verschoben={moved}, behalten={kept}, errors={errors}"
    report.append(line)
    print(line)

print("\n=== SUMMARY ===")
for line in report:
    print(line)
