from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skill" / "learn"
SCRIPTS = SKILL / "scripts"
FIXTURES = ROOT / "tests" / "fixtures"


class LearnSmokeTest(unittest.TestCase):
    def run_script(self, script: str, *args: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPTS / script), *args],
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )

    def test_config_validate_and_render_illustrated_note(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "runtime"
            vault = root / "vault"
            (vault / ".obsidian").mkdir(parents=True)
            (vault / ".obsidian" / "app.json").write_text(
                json.dumps({"attachmentFolderPath": "Attachments"}), encoding="utf-8"
            )
            env = os.environ.copy()
            env["CODEX_LEARN_CONFIG"] = str(root / "local" / "settings.json")

            self.run_script(
                "bootstrap.py",
                "configure",
                "--workspace",
                str(workspace),
                "--vault",
                str(vault),
                "--notes-subdir",
                "Notes",
                "--json",
                env=env,
            )
            status = self.run_script("bootstrap.py", "status", "--json", env=env)
            self.assertTrue(json.loads(status.stdout)["configured"])

            validated = self.run_script(
                "job.py", "validate", "--evidence", str(FIXTURES / "sample_evidence.json"), env=env
            )
            self.assertTrue(json.loads(validated.stdout)["valid"])

            rendered = self.run_script(
                "render_note.py", "--evidence", str(FIXTURES / "sample_evidence.json"), env=env
            )
            result = json.loads(rendered.stdout)
            note_path = Path(result["output"])
            note = note_path.read_text(encoding="utf-8")
            self.assertTrue(note_path.is_file())
            self.assertEqual(len(result["attachments"]), 3)
            self.assertFalse(result["warnings"])
            self.assertIn("```mermaid\nflowchart TD", note)
            self.assertIn("![[Attachments/Learn/bilibili-BV1C6M46uEe3/", note)
            self.assertIn("实验结果：", note)
            self.assertNotIn("{{", note)

            expected_sections = (ROOT / "tests" / "expected" / "sample_note_sections.txt").read_text(
                encoding="utf-8"
            ).splitlines()
            for section in expected_sections:
                if section:
                    self.assertIn(section, note)


if __name__ == "__main__":
    unittest.main()
