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
    FORBIDDEN_NOTE_SECTIONS = (
        "## 原文图文证据",
        "## 关键原文摘录",
        "## 主张与证据",
        "## 局限与缺失证据",
        "## 补充附件",
        "## 时间轴或文章结构",
    )

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
            config = json.loads(Path(env["CODEX_LEARN_CONFIG"]).read_text(encoding="utf-8"))
            self.assertFalse(config["keep_structured_evidence"])
            self.assertFalse(config["keep_transcript"])

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
            self.assertEqual(result["content_profile"], "technical")
            self.assertEqual(len(result["attachments"]), 2)
            self.assertEqual(result["retained_visuals"], 2)
            self.assertFalse(result["warnings"])
            self.assertIn("![[Attachments/Learn/bilibili-BV1C6M46uEe3/", note)
            self.assertIn("## 可行性验证", note)
            self.assertNotIn("{{", note)
            self.assertNotIn("transcript-", note)
            self.assertNotIn("证据 `", note)
            self.assertNotIn("unused-candidate-frame", note)
            self.assertNotIn("仅用于采集核对", note)
            for section in self.FORBIDDEN_NOTE_SECTIONS:
                self.assertNotIn(section, note)

            expected_sections = (ROOT / "tests" / "expected" / "sample_note_sections.txt").read_text(
                encoding="utf-8"
            ).splitlines()
            for section in expected_sections:
                if section:
                    self.assertIn(section, note)

    def test_overview_catalog_and_visual_profiles_render_only_useful_content(self) -> None:
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
                "--notes-subdir",
                "Notes",
                "--json",
                env=env,
            )

            cases = {
                "overview_evidence.json": ("overview", 0),
                "catalog_evidence.json": ("catalog", 0),
                "visual_evidence.json": ("visual", 2),
            }
            rendered_notes: dict[str, str] = {}
            for fixture_name, (profile, visual_count) in cases.items():
                evidence = FIXTURES / fixture_name
                validated = self.run_script("job.py", "validate", "--evidence", str(evidence), env=env)
                report = json.loads(validated.stdout)
                self.assertTrue(report["valid"], report)
                rendered = self.run_script("render_note.py", "--evidence", str(evidence), env=env)
                result = json.loads(rendered.stdout)
                note = Path(result["output"]).read_text(encoding="utf-8")
                rendered_notes[profile] = note
                self.assertEqual(result["content_profile"], profile)
                self.assertEqual(result["retained_visuals"], visual_count)
                self.assertEqual(len(result["attachments"]), visual_count)
                self.assertNotIn("{{", note)
                for section in self.FORBIDDEN_NOTE_SECTIONS:
                    self.assertNotIn(section, note)

            overview_note = rendered_notes["overview"]
            self.assertIn("## 全文总结", overview_note)
            self.assertIn("## 要点", overview_note)
            self.assertNotIn("## 可行性验证", overview_note)

            catalog_bundle = json.loads((FIXTURES / "catalog_evidence.json").read_text(encoding="utf-8"))
            catalog_note = rendered_notes["catalog"]
            self.assertIn("## 完整清单", catalog_note)
            self.assertEqual(catalog_note.count("\n### "), len(catalog_bundle["content_items"]))
            for item in catalog_bundle["content_items"]:
                self.assertIn(item["name"], catalog_note)
                self.assertIn(item["what"], catalog_note)
                self.assertIn(item["why"], catalog_note)
            self.assertNotIn("## 可行性验证", catalog_note)

            visual_bundle = json.loads((FIXTURES / "visual_evidence.json").read_text(encoding="utf-8"))
            visual_note = rendered_notes["visual"]
            self.assertIn("## 逐项展示", visual_note)
            self.assertEqual(visual_note.count("![["), len(visual_bundle["content_items"]))
            for item in visual_bundle["content_items"]:
                self.assertIn(item["name"], visual_note)
                self.assertIn(item["what"], visual_note)
            self.assertNotIn("00:", visual_note)

    def test_profile_validation_rejects_incomplete_compact_notes(self) -> None:
        env = os.environ.copy()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)

            catalog = json.loads((FIXTURES / "catalog_evidence.json").read_text(encoding="utf-8"))
            del catalog["content_items"][0]["why"]
            catalog_path = root / "bad-catalog.json"
            catalog_path.write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")

            catalog_count = json.loads(
                (FIXTURES / "catalog_evidence.json").read_text(encoding="utf-8")
            )
            catalog_count["source_item_count"] = 19
            catalog_count_path = root / "bad-catalog-count.json"
            catalog_count_path.write_text(
                json.dumps(catalog_count, ensure_ascii=False), encoding="utf-8"
            )

            visual = json.loads((FIXTURES / "visual_evidence.json").read_text(encoding="utf-8"))
            visual["content_items"][1]["visual_id"] = visual["content_items"][0]["visual_id"]
            visual_path = root / "bad-visual.json"
            visual_path.write_text(json.dumps(visual, ensure_ascii=False), encoding="utf-8")

            overview = json.loads((FIXTURES / "overview_evidence.json").read_text(encoding="utf-8"))
            overview["experiment"] = {"status": "planned"}
            overview_path = root / "bad-overview.json"
            overview_path.write_text(json.dumps(overview, ensure_ascii=False), encoding="utf-8")

            for path, expected in (
                (catalog_path, "why is required for catalog"),
                (catalog_count_path, "does not match content_items"),
                (visual_path, "unique visual_id"),
                (overview_path, "must not include experiment"),
            ):
                completed = subprocess.run(
                    [sys.executable, str(SCRIPTS / "job.py"), "validate", "--evidence", str(path)],
                    capture_output=True,
                    text=True,
                    env=env,
                )
                self.assertNotEqual(completed.returncode, 0)
                self.assertIn(expected, completed.stdout)

    def test_finalize_removes_intermediates_after_note_visual_validation(self) -> None:
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
                "--notes-subdir",
                "Notes",
                "--json",
                env=env,
            )
            initialized = self.run_script(
                "job.py",
                "init",
                "--url",
                "https://example.invalid/finalize-test",
                "--title",
                "收尾测试",
                env=env,
            )
            job = json.loads(initialized.stdout)
            manifest_path = Path(job["manifest"])
            job_dir = Path(job["paths"]["job_dir"])
            work_dir = Path(job["paths"]["work_dir"])
            sandbox_dir = Path(job["paths"]["sandbox_dir"])
            (work_dir / "transcript.json").write_text("{}", encoding="utf-8")
            (work_dir / "contact-sheet.png").write_bytes(b"temporary")
            (sandbox_dir / "raw-result.txt").write_text("temporary", encoding="utf-8")
            shared_cache = workspace / "cache" / "shared-model.bin"
            shared_cache.write_bytes(b"shared")
            other_work = workspace / "_work" / "other-job" / "keep.txt"
            other_work.parent.mkdir(parents=True)
            other_work.write_text("keep", encoding="utf-8")

            evidence_path = job_dir / "evidence.json"
            evidence_path.write_text(
                json.dumps(
                    {
                        "content_profile": "overview",
                        "source": {
                            "url": "https://example.invalid/finalize-test",
                            "platform": "web",
                            "title": "收尾测试",
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            visual_path = vault / "Attachments" / "Learn" / job["job_id"] / "kept.svg"
            visual_path.parent.mkdir(parents=True)
            visual_path.write_bytes((FIXTURES / "source-diagram.svg").read_bytes())
            note_path = vault / "Notes" / "收尾测试.md"
            note_path.parent.mkdir(parents=True, exist_ok=True)
            note_path.write_text(
                "# 收尾测试\n\n## 全文总结\n\n已完成。\n\n"
                f"![[{visual_path.relative_to(vault).as_posix()}]]\n",
                encoding="utf-8",
            )

            finalized = self.run_script(
                "job.py",
                "finalize",
                "--manifest",
                str(manifest_path),
                "--evidence",
                str(evidence_path),
                "--note",
                str(note_path),
                env=env,
            )
            result = json.loads(finalized.stdout)
            compact = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertTrue(result["finalized"])
            self.assertEqual(result["retained_visuals"], 1)
            self.assertFalse(work_dir.exists())
            self.assertFalse(sandbox_dir.exists())
            self.assertFalse(evidence_path.exists())
            self.assertEqual([path.name for path in job_dir.iterdir()], ["job.json"])
            self.assertEqual(compact["status"], "complete")
            self.assertEqual(compact["content_profile"], "overview")
            self.assertNotIn("paths", compact)
            self.assertTrue(note_path.is_file())
            self.assertTrue(visual_path.is_file())
            self.assertTrue(shared_cache.is_file())
            self.assertTrue(other_work.is_file())

    def test_render_failure_rolls_back_newly_copied_visuals(self) -> None:
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
            bundle = json.loads((FIXTURES / "visual_evidence.json").read_text(encoding="utf-8"))
            bundle["original_images"][0]["local_path"] = str(FIXTURES / "outfit-blue.svg")
            bundle["original_images"][1]["local_path"] = str(root / "missing.svg")
            evidence = root / "bad-render.json"
            evidence.write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")

            completed = subprocess.run(
                [sys.executable, str(SCRIPTS / "render_note.py"), "--evidence", str(evidence)],
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("cannot be rendered", completed.stdout)
            destination = vault / "Attachments" / "Learn" / bundle["job_id"]
            self.assertFalse(destination.exists())

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
