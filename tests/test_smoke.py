from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
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

    def test_provision_fingerprint_uses_fast_path(self) -> None:
        sys.path.insert(0, str(SCRIPTS))
        try:
            import bootstrap
        finally:
            sys.path.pop(0)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "runtime"
            vault = root / "vault"
            vault.mkdir()
            env = os.environ.copy()
            env["CODEX_LEARN_CONFIG"] = str(root / "local" / "settings.json")
            self.run_script(
                "bootstrap.py",
                "configure",
                "--workspace",
                str(workspace),
                "--vault",
                str(vault),
                "--json",
                env=env,
            )

            python_path = bootstrap.runtime_python(workspace)
            python_path.parent.mkdir(parents=True)
            python_path.write_bytes(b"fake-runtime")
            site_packages = bootstrap.runtime_site_packages(python_path)
            rapid_models = site_packages / "rapidocr" / "models"
            rapid_models.mkdir(parents=True)
            (rapid_models / "PP-OCRv6_det_small.onnx").write_bytes(b"det")
            (rapid_models / "PP-OCRv6_rec_small.onnx").write_bytes(b"rec")
            (rapid_models / "ch_ppocr_mobile_v2.0_cls_mobile.onnx").write_bytes(b"cls")
            asr = (
                workspace
                / "cache"
                / "models"
                / "faster-whisper"
                / "models--Systran--faster-whisper-large-v3"
                / "snapshots"
                / "fixture"
            )
            asr.mkdir(parents=True)
            (asr / "model.bin").write_bytes(b"model")
            bootstrap.save_state(
                workspace,
                {
                    "schema_version": bootstrap.PROVISION_SCHEMA,
                    "requirements_fingerprint": bootstrap.requirements_fingerprint(),
                    "asr_model": "large-v3",
                    "ocr_engine": "rapidocr",
                },
            )

            started = time.perf_counter()
            completed = self.run_script("bootstrap.py", "provision", "--json", env=env)
            wall_seconds = time.perf_counter() - started
            result = json.loads(completed.stdout)
            self.assertTrue(result["fast_path"])
            self.assertEqual(result["dependencies"], "unchanged")
            self.assertLess(result["elapsed_seconds"], 1.0)
            self.assertLess(wall_seconds, 2.0)

    def test_optimized_media_scripts_have_cli(self) -> None:
        env = os.environ.copy()
        for script in ("transcribe.py", "ocr_images.py", "extract_keyframes.py"):
            completed = subprocess.run(
                [sys.executable, str(SCRIPTS / script), "--help"],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertIn("usage:", completed.stdout.lower())

    def test_batch_transcription_reuses_one_process_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "runtime"
            vault = root / "vault"
            vault.mkdir()
            fake_modules = root / "fake-modules"
            fake_modules.mkdir()
            (fake_modules / "ctranslate2.py").write_text(
                "def get_cuda_device_count():\n    return 0\n", encoding="utf-8"
            )
            (fake_modules / "faster_whisper.py").write_text(
                """
from types import SimpleNamespace

class WhisperModel:
    loads = 0
    def __init__(self, *args, **kwargs):
        type(self).loads += 1

class BatchedInferencePipeline:
    def __init__(self, model):
        assert model.loads == 1
    def transcribe(self, audio, **kwargs):
        segment = SimpleNamespace(
            start=0.0,
            end=1.0,
            text=' fixture transcript ',
            avg_logprob=-0.1,
            no_speech_prob=0.01,
            words=None,
        )
        info = SimpleNamespace(language='en', language_probability=0.99, duration=1.0)
        return iter([segment]), info
""".lstrip(),
                encoding="utf-8",
            )
            env = os.environ.copy()
            env["CODEX_LEARN_CONFIG"] = str(root / "local" / "settings.json")
            env["PYTHONPATH"] = str(fake_modules) + os.pathsep + env.get("PYTHONPATH", "")
            self.run_script(
                "bootstrap.py",
                "configure",
                "--workspace",
                str(workspace),
                "--vault",
                str(vault),
                "--json",
                env=env,
            )
            media = [root / "a.wav", root / "b.wav"]
            for path in media:
                path.write_bytes(b"fixture")
            output = root / "transcript.json"
            completed = self.run_script(
                "transcribe.py",
                str(media[0]),
                str(media[1]),
                "--output",
                str(output),
                env=env,
            )
            result = json.loads(completed.stdout)
            transcript = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(result["ok"])
            self.assertEqual(result["files"], 2)
            self.assertEqual(transcript["backend"]["device"], "cpu")
            self.assertEqual([len(item["segments"]) for item in transcript["files"]], [1, 1])


if __name__ == "__main__":
    unittest.main()
