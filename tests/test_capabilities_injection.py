#!/usr/bin/env python3
"""Unit-Tests fuer src/capabilities_template.py.

Laeuft wahlweise mit `python3 tests/test_capabilities_injection.py`
oder `python3 -m unittest tests/test_capabilities_injection.py`
oder `python3 -m pytest tests/test_capabilities_injection.py -v`.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

# Ermoegliche Import von src/capabilities_template.py
_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
sys.path.insert(0, os.path.join(_REPO, "src"))

import capabilities_template as ct  # noqa: E402


SAMPLE_USER_CONTENT = (
    "Du bist ein Test-Agent.\n"
    "Sprich Deutsch. Sei praezise.\n"
    "\n"
    "## SPEZIAL-REGELN\n"
    "- Regel 1\n"
    "- Regel 2\n"
)


def _sample_models_config() -> dict:
    return {
        "providers": {
            "anthropic": {
                "name": "Anthropic",
                "api_key": "x",
                "models": [{"id": "claude-sonnet-4-6", "name": "Claude Sonnet 4.6"}],
            },
            "gemini": {
                "name": "Gemini",
                "api_key": "y",
                "models": [{"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash"}],
                "image_model": "imagen-4.0-generate-001",
                "video_model": "veo-3.1-generate-preview",
            },
        }
    }


def _sample_block() -> str:
    cfg = {
        "agent_name": "testagent",
        "parent_agent": "testagent",
        "models_config": _sample_models_config(),
        "datalake_base": "/tmp/datalake",
        "claude_outputs_path": "/tmp/claude_outputs",
    }
    return ct.get_capabilities_block(cfg)


class SplitPromptTests(unittest.TestCase):
    def test_split_prompt_with_separator(self):
        content = SAMPLE_USER_CONTENT.rstrip() + "\n\n" + ct.SEPARATOR + "\n\n## SYSTEM\n- foo\n"
        user, system = ct.split_agent_prompt(content)
        self.assertIn("Du bist ein Test-Agent.", user)
        self.assertNotIn(ct.SEPARATOR, user, "User-Section darf Trennzeichen nicht enthalten")
        self.assertTrue(system.startswith(ct.SEPARATOR), "System-Section startet mit Trennzeichen")
        self.assertIn("## SYSTEM", system)

    def test_split_prompt_without_separator(self):
        user, system = ct.split_agent_prompt(SAMPLE_USER_CONTENT)
        self.assertEqual(user, SAMPLE_USER_CONTENT)
        self.assertEqual(system, "")

    def test_split_prompt_empty(self):
        user, system = ct.split_agent_prompt("")
        self.assertEqual(user, "")
        self.assertEqual(system, "")

    def test_split_prompt_only_separator(self):
        user, system = ct.split_agent_prompt(ct.SEPARATOR + "\nfoo\n")
        self.assertEqual(user, "")
        self.assertTrue(system.startswith(ct.SEPARATOR))


class CapabilitiesBlockTests(unittest.TestCase):
    def test_block_starts_with_separator(self):
        block = _sample_block()
        self.assertTrue(block.startswith(ct.SEPARATOR))

    def test_block_contains_key_sections(self):
        block = _sample_block()
        for marker in [
            "## MEMORY & SUCHE",
            "## DATEI-ERSTELLUNG",
            "## BILD & VIDEO",
            "## KALENDER & TOOLS",
            "## AKTIVE MODELLE & PROVIDER",
            "## WORKING MEMORY",
            "## PFADE (WICHTIG)",
            "CREATE_FILE:docx",
            "CREATE_IMAGE",
            "CREATE_VIDEO",
        ]:
            self.assertIn(marker, block, f"Block enthaelt {marker!r} nicht")

    def test_block_lists_active_models(self):
        block = _sample_block()
        self.assertIn("Claude Sonnet 4.6", block)
        self.assertIn("Gemini 2.5 Flash", block)
        self.assertIn("imagen-4.0-generate-001", block)
        self.assertIn("veo-3.1-generate-preview", block)

    def test_block_uses_agent_paths(self):
        block = _sample_block()
        self.assertIn("/tmp/datalake/testagent/memory", block)
        self.assertIn("/tmp/datalake/testagent/working_memory", block)
        self.assertIn("/tmp/claude_outputs", block)

    def test_subagent_shares_parent_memory(self):
        cfg = {
            "agent_name": "signicat_lamp",
            "parent_agent": "signicat",
            "sub_label": "lamp",
            "models_config": _sample_models_config(),
            "datalake_base": "/tmp/datalake",
        }
        block = ct.get_capabilities_block(cfg)
        self.assertIn("/tmp/datalake/signicat/memory", block)
        # Sub-Agents bekommen eigenen WM-Pfad mit "_lamp"
        self.assertIn("/tmp/datalake/signicat/working_memory/_lamp", block)


class MigrateAgentFileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        )
        self.path = self.tmp.name
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        try:
            os.unlink(self.path)
        except OSError:
            pass

    def _write(self, content: str):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(content)

    def _read(self) -> str:
        with open(self.path, "r", encoding="utf-8") as f:
            return f.read()

    def test_user_section_preserved(self):
        self._write(SAMPLE_USER_CONTENT)
        block = _sample_block()
        changed = ct.migrate_agent_file(self.path, block)
        self.assertTrue(changed)

        after = self._read()
        user, system = ct.split_agent_prompt(after)
        # User-Section ist byte-identisch zum Original (modulo trailing whitespace)
        self.assertEqual(user.rstrip(), SAMPLE_USER_CONTENT.rstrip())
        self.assertIn(ct.SEPARATOR, system)

    def test_system_section_updated(self):
        """Zweite Migration mit geaendertem Block tauscht die System-Section aus."""
        self._write(SAMPLE_USER_CONTENT)
        # Erste Injection
        block_v1 = _sample_block()
        ct.migrate_agent_file(self.path, block_v1)
        after_v1 = self._read()

        # Zweite Injection mit anderem Provider-Set
        cfg_v2 = {
            "agent_name": "testagent",
            "parent_agent": "testagent",
            "datalake_base": "/tmp/datalake",
            "claude_outputs_path": "/tmp/claude_outputs",
            "models_config": {
                "providers": {
                    "openai": {
                        "name": "OpenAI",
                        "models": [{"id": "gpt-4o", "name": "GPT-4o"}],
                    }
                }
            },
        }
        block_v2 = ct.get_capabilities_block(cfg_v2)
        changed = ct.migrate_agent_file(self.path, block_v2)
        self.assertTrue(changed)
        after_v2 = self._read()
        self.assertNotEqual(after_v1, after_v2)
        self.assertIn("GPT-4o", after_v2)
        self.assertNotIn("Claude Sonnet 4.6", after_v2)
        # Trennzeichen darf nur einmal vorkommen
        self.assertEqual(after_v2.count(ct.SEPARATOR), 1)

    def test_no_double_injection(self):
        """Auch nach mehreren Migrationen gibt es nur genau EIN Trennzeichen."""
        self._write(SAMPLE_USER_CONTENT)
        block = _sample_block()
        for _ in range(5):
            ct.migrate_agent_file(self.path, block)
        after = self._read()
        self.assertEqual(after.count(ct.SEPARATOR), 1)

    def test_idempotent_same_block(self):
        """Identischer Block-Inhalt → zweite Migration schreibt nicht."""
        self._write(SAMPLE_USER_CONTENT)
        block = _sample_block()
        first = ct.migrate_agent_file(self.path, block)
        second = ct.migrate_agent_file(self.path, block)
        self.assertTrue(first)
        self.assertFalse(second, "Zweiter Aufruf mit identischem Block darf keine Schreib-I/O ausloesen")

    def test_separator_never_in_user_content(self):
        """User kann keinen Text enthalten, der dem Separator vorausgeht — die
        Migration interpretiert dann alles nach dem Separator als System-Teil
        (das ist by design). Testet dass user-Content oberhalb intakt bleibt."""
        content = "Hallo User\n" + ct.SEPARATOR + "\nalt-system\n"
        self._write(content)
        ct.migrate_agent_file(self.path, _sample_block())
        user, system = ct.split_agent_prompt(self._read())
        self.assertIn("Hallo User", user)
        self.assertNotIn("alt-system", user)
        self.assertNotIn("alt-system", system)


class InjectCapabilitiesOnStartupTests(unittest.TestCase):
    def test_updates_all_txt_files_and_ignores_backups(self):
        tmpdir = tempfile.mkdtemp()
        self.addCleanup(lambda: _rmtree(tmpdir))

        # 2 normale Agenten, 1 Sub-Agent, 1 Backup
        agents = {
            "agentA.txt": "User-Content-A\n",
            "agentA_sub.txt": "User-Content-SUB\n",
            "agentB.txt": "User-Content-B\n",
            "agentA.txt.backup_20260101_000000": "DO-NOT-TOUCH",
        }
        for name, content in agents.items():
            with open(os.path.join(tmpdir, name), "w", encoding="utf-8") as f:
                f.write(content)

        # Fake models.json
        models_path = os.path.join(tmpdir, "models.json")
        with open(models_path, "w", encoding="utf-8") as f:
            import json
            json.dump(_sample_models_config(), f)

        n = ct.inject_capabilities_on_startup(
            agents_dir=tmpdir,
            models_file=models_path,
            datalake_base="/tmp/datalake",
            verbose=False,
        )
        self.assertEqual(n, 3)  # 3 echte Agent-Dateien, Backup ignoriert

        # Zweiter Aufruf: nichts darf sich aendern
        n2 = ct.inject_capabilities_on_startup(
            agents_dir=tmpdir,
            models_file=models_path,
            datalake_base="/tmp/datalake",
            verbose=False,
        )
        self.assertEqual(n2, 0, "Zweiter Aufruf mit identischem Ergebnis = 0 writes")

        # User-Sections blieben erhalten
        for name in ("agentA.txt", "agentA_sub.txt", "agentB.txt"):
            with open(os.path.join(tmpdir, name), "r", encoding="utf-8") as f:
                content = f.read()
            user, _system = ct.split_agent_prompt(content)
            self.assertIn(agents[name].rstrip(), user)

        # Sub-Agent bekommt Parent-Memory-Pfad
        with open(os.path.join(tmpdir, "agentA_sub.txt"), "r", encoding="utf-8") as f:
            sub_content = f.read()
        self.assertIn("/tmp/datalake/agentA/memory", sub_content)
        self.assertIn("working_memory/_sub", sub_content)

        # Backup wurde nicht angefasst
        with open(os.path.join(tmpdir, "agentA.txt.backup_20260101_000000"), "r", encoding="utf-8") as f:
            bak = f.read()
        self.assertEqual(bak, "DO-NOT-TOUCH")

    def test_missing_dir_returns_zero(self):
        n = ct.inject_capabilities_on_startup(
            agents_dir="/nonexistent/path/xyz",
            models_file=None,
            verbose=False,
        )
        self.assertEqual(n, 0)


def _rmtree(path):
    import shutil
    try:
        shutil.rmtree(path)
    except OSError:
        pass


if __name__ == "__main__":
    unittest.main(verbosity=2)
