#!/usr/bin/env python3
"""Entferne Test-Artefakte aus Agent-Konversationsordnern.

Sucht in allen `<datalake>/<agent>/konversation_*.txt` nach Dateien, die
ausschliesslich aus Test-Mustern bestehen (z.B. "Sag nur das Wort: TESTOK",
"/find test") und verschiebt sie nach
`~/AssistantDev/backups/<timestamp>_test_artifacts/<agent>/`.

Safety: verschiebt (nicht loescht), sodass jederzeit restorable.

Benutzung:
  python3 scripts/cleanup_test_conversations.py --dry-run   # nur Liste
  python3 scripts/cleanup_test_conversations.py             # live move
"""
from __future__ import annotations

import argparse
import datetime
import os
import shutil
import sys


BASE = os.path.expanduser(
    "~/Library/Mobile Documents/com~apple~CloudDocs/Downloads shared/claude_datalake"
)
AGENTS_DIR = os.path.join(BASE, "config", "agents")
BACKUPS_ROOT = os.path.expanduser("~/AssistantDev/backups")


# User-Nachrichten, die nur in Test-Durchlaeufen vorkommen.
# Matched, wenn die Du:-Zeile EXAKT einem dieser Eintraege entspricht.
TEST_USER_PATTERNS = frozenset({
    "Sag nur das Wort: TESTOK",
    "/find test",
    "Antworte NUR mit: TEST_OK",
    "Say hello",
    "TEST",
    "test",
})

# Maximale Dateigroesse fuer Test-Artefakte (Bytes). Echte Konversationen
# sind meist deutlich groesser; Test-Durchlaeufe produzieren je nach
# Agent-Antwort bis ~2-3 KB (z.B. `/find test` mit 5 Treffern im Search-
# Feedback-Block). Konservative Obergrenze: 3.5 KB.
MAX_TEST_SIZE = 3500


def _list_agent_dirs() -> list[str]:
    """Liste Agent-Ordner im Datalake (jeder Ordner, der ein memory/ hat)."""
    if not os.path.isdir(BASE):
        return []
    dirs = []
    for entry in sorted(os.listdir(BASE)):
        full = os.path.join(BASE, entry)
        if not os.path.isdir(full):
            continue
        if entry.startswith('.') or entry in (
            'config', 'email_inbox', 'webclips', 'calendar', 'whatsapp'
        ):
            continue
        if os.path.isdir(os.path.join(full, 'memory')):
            dirs.append(full)
        else:
            # auch Ordner ohne memory/ enthalten konversation_*.txt (siehe
            # signicat — Memory liegt im memory/-Unterordner, Konversationen
            # aber direkt im Agent-Ordner).
            if any(f.startswith('konversation_') and f.endswith('.txt')
                   for f in os.listdir(full)):
                dirs.append(full)
    return dirs


def _is_test_artifact(fpath: str) -> bool:
    """True, wenn die Konversation eindeutig ein Test-Artefakt ist.

    Kriterien (alle muessen greifen):
    - Dateigroesse <= MAX_TEST_SIZE.
    - Genau ein "Du:"-Block, und dessen Text exact in TEST_USER_PATTERNS.
    - Keine "Von:"/"An:"/"CREATE_"/URL-Pattern im Body (keine echten Outputs).
    """
    try:
        if os.path.getsize(fpath) > MAX_TEST_SIZE:
            return False
        with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
    except OSError:
        return False

    # Alle "Du:"-Zeilen sammeln. ALLE User-Messages muessen zu den
    # Test-Mustern gehoeren — sonst ist es keine reine Test-Konversation.
    du_lines = [line for line in content.splitlines() if line.startswith('Du: ')]
    if not du_lines:
        return False
    for du in du_lines:
        user_msg = du[4:].strip()
        if user_msg not in TEST_USER_PATTERNS:
            return False
    # Marker nur im User-Teil (Du:) pruefen — Assistant-Antworten duerfen
    # Betreff/Subject/Links enthalten (z.B. `/find test` findet echte Mails).
    for du in du_lines:
        msg = du[4:].strip().lower()
        if any(m in msg for m in ('create_email', 'create_file', 'create_image',
                                  'create_video', 'create_whatsapp', 'http://',
                                  'https://')):
            return False
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--dry-run', action='store_true',
                    help='Nur auflisten, nicht verschieben')
    ap.add_argument('--agent', default=None,
                    help='Nur einen Agent bereinigen (z.B. signicat)')
    args = ap.parse_args()

    ts = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    backup_root = os.path.join(BACKUPS_ROOT, f'{ts}_test_artifacts')

    agents = _list_agent_dirs()
    if args.agent:
        agents = [a for a in agents if os.path.basename(a) == args.agent]
        if not agents:
            print(f'FEHLER: Agent "{args.agent}" nicht gefunden', file=sys.stderr)
            sys.exit(1)

    grand_total = 0
    per_agent = {}
    for agent_dir in agents:
        agent_name = os.path.basename(agent_dir)
        artifacts = []
        try:
            for fname in os.listdir(agent_dir):
                if not (fname.startswith('konversation_') and fname.endswith('.txt')):
                    continue
                fpath = os.path.join(agent_dir, fname)
                if _is_test_artifact(fpath):
                    artifacts.append(fpath)
        except OSError:
            continue
        per_agent[agent_name] = len(artifacts)
        grand_total += len(artifacts)
        if not artifacts:
            continue
        if args.dry_run:
            print(f'[DRY-RUN] {agent_name}: {len(artifacts)} Test-Artefakte (Beispiel: {os.path.basename(artifacts[0])})')
            continue
        # Verschiebe
        target_dir = os.path.join(backup_root, agent_name)
        os.makedirs(target_dir, exist_ok=True)
        for src in artifacts:
            dst = os.path.join(target_dir, os.path.basename(src))
            shutil.move(src, dst)
        print(f'  {agent_name}: {len(artifacts)} Dateien → {target_dir}')

    print()
    print('=' * 60)
    mode = 'DRY-RUN' if args.dry_run else 'Verschoben'
    print(f'{mode}: {grand_total} Test-Artefakte ueber {sum(1 for v in per_agent.values() if v)} Agents.')
    if not args.dry_run and grand_total > 0:
        print(f'Backup-Pfad: {backup_root}')
    # Uebersicht
    for a, n in per_agent.items():
        print(f'  {a}: {n}')


if __name__ == '__main__':
    main()
