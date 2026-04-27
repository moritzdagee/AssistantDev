#!/usr/bin/env python3
"""Backfill HTML-Companion-Files fuer bestehende .txt-Mails.

Fuer jede .txt-Mail in `<datalake>/<agent>/memory/` ohne korrespondierende
.html-Datei: versucht das Original-.eml in `email_inbox/processed/` zu
matchen (ueber EML-Source-Header oder ueber Timestamp+Subject-Heuristik)
und schreibt den text/html-Part als Companion .html.

Usage:
  python3 scripts/backfill_email_html.py [--dry-run] [--agent <name>]

Idempotent: ueberschreibt bestehende .html-Companions nicht.
"""

import argparse
import email
import os
import re
import sys
from glob import glob

DATALAKE = os.path.expanduser(
    "~/Library/Mobile Documents/com~apple~CloudDocs/Downloads shared/claude_datalake"
)
PROCESSED_DIR = os.path.join(DATALAKE, "email_inbox", "processed")

# Agents mit Inbox (Watcher-Routing-Targets)
AGENTS = ["privat", "signicat", "trustedcarrier", "standard"]


def find_eml_for_txt(txt_path, eml_files_index):
    """Versucht den passenden .eml-File zu finden.

    1. Falls EML-Source-Header in der .txt steht: direkter Lookup.
    2. Sonst: Heuristik via Subject-Match (filename-stem).
    """
    try:
        with open(txt_path, "rb") as fh:
            head = fh.read(8192).decode("utf-8", errors="replace")
    except Exception:
        return None

    # 1) EML-Source-Header
    m = re.search(r"^EML-Source:\s*(.+)$", head, re.MULTILINE)
    if m:
        eml_name = m.group(1).strip()
        candidate = os.path.join(PROCESSED_DIR, eml_name)
        if os.path.isfile(candidate):
            return candidate

    # 2) Heuristik: Filename-Stem matchen
    txt_base = os.path.basename(txt_path).replace(".txt", "")
    # txt: 2026-04-09_12-15-23_IN_naoresponda_at_zen_floripa_br_Cobrana_finalizada
    # eml: 2026-04-01_11-34-00_Cobrana_finalizada
    # Subject-Teil isolieren (ab dem 4. Underscore-Block)
    parts = txt_base.split("_")
    if len(parts) > 4:
        subject_clean = "_".join(parts[4:])[:30]
        # Suche EMLs mit aehnlichem Subject-Suffix
        for eml_name in eml_files_index:
            if subject_clean.lower() in eml_name.lower():
                return os.path.join(PROCESSED_DIR, eml_name)
    return None


def extract_html_from_eml(eml_path):
    try:
        with open(eml_path, "rb") as fh:
            msg = email.message_from_bytes(fh.read())
    except Exception:
        return None
    for part in msg.walk():
        if (part.get_content_type() == "text/html"
                and "attachment" not in str(part.get("Content-Disposition", ""))):
            payload = part.get_payload(decode=True)
            if payload:
                try:
                    return payload.decode("utf-8", errors="replace")
                except Exception:
                    return None
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Nur zaehlen, keine Files schreiben")
    parser.add_argument("--agent", default=None,
                        help="Nur einen Agent backfillen (default: alle)")
    parser.add_argument("--limit", type=int, default=0,
                        help="Maximal N Files verarbeiten (0 = alle)")
    args = parser.parse_args()

    # Index der vorhandenen .eml-Filenames fuer Heuristik
    if not os.path.isdir(PROCESSED_DIR):
        print(f"FEHLER: {PROCESSED_DIR} existiert nicht", file=sys.stderr)
        sys.exit(1)
    eml_files_index = os.listdir(PROCESSED_DIR)
    print(f"Index: {len(eml_files_index)} .eml-Files in processed/")

    agents = [args.agent] if args.agent else AGENTS

    total_seen = 0
    total_written = 0
    total_eml_missing = 0
    total_html_missing = 0
    total_already = 0

    for agent in agents:
        memdir = os.path.join(DATALAKE, agent, "memory")
        if not os.path.isdir(memdir):
            continue
        txt_files = sorted([f for f in os.listdir(memdir) if f.endswith(".txt")
                            and not f.startswith(("konversation_", "whatsapp_", "kchat_"))])
        print(f"\n[{agent}] {len(txt_files)} .txt-Mails")
        for fname in txt_files:
            if args.limit and total_seen >= args.limit:
                break
            total_seen += 1
            txt_path = os.path.join(memdir, fname)
            html_path = txt_path[:-4] + ".html"
            if os.path.exists(html_path):
                total_already += 1
                continue
            eml_path = find_eml_for_txt(txt_path, eml_files_index)
            if not eml_path:
                total_eml_missing += 1
                continue
            html_body = extract_html_from_eml(eml_path)
            if not html_body:
                total_html_missing += 1
                continue
            if args.dry_run:
                total_written += 1
                continue
            try:
                with open(html_path, "w") as fh:
                    fh.write(html_body)
                total_written += 1
                if total_written % 100 == 0:
                    print(f"  ... {total_written} HTMLs geschrieben")
            except Exception as e:
                print(f"  Write-Fehler {fname}: {e}")

    print()
    print(f"Gesehen:               {total_seen}")
    print(f"HTML schon vorhanden:  {total_already}")
    print(f"Kein .eml gefunden:    {total_eml_missing}")
    print(f"Kein HTML im .eml:     {total_html_missing}")
    print(f"HTML geschrieben:      {total_written} ({'DRY-RUN' if args.dry_run else 'committed'})")


if __name__ == "__main__":
    main()
