#!/usr/bin/env python3
"""Configure and provision the local runtime used by the Learn skill."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import venv
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from learn_config import (
    absolute_path,
    config_path,
    load_config,
    obsidian_attachment_folder,
    save_config,
)


RUNTIME_DIRS = ("jobs", "_work", "cache", "output", "sandbox")


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def emit(data: dict[str, Any], as_json: bool = True) -> None:
    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return
    for key, value in data.items():
        print(f"{key}: {value}")


def ensure_inside(root: Path, candidate: Path, label: str) -> None:
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"{label} must stay inside the configured Vault: {candidate}") from exc


def configure(args: argparse.Namespace) -> int:
    workspace = absolute_path(args.workspace)
    vault = absolute_path(args.vault)
    if workspace == vault:
        raise ValueError("The runtime workspace and Obsidian Vault must be different directories")

    workspace.mkdir(parents=True, exist_ok=True)
    vault.mkdir(parents=True, exist_ok=True)
    for name in RUNTIME_DIRS:
        (workspace / name).mkdir(parents=True, exist_ok=True)

    attachment_folder = args.attachments
    if not attachment_folder or attachment_folder == "auto":
        attachment_folder = obsidian_attachment_folder(vault)
    attachment_folder = attachment_folder.strip().replace("\\", "/").strip("/") or "."
    notes_subdir = args.notes_subdir.strip().replace("\\", "/").strip("/") or "Learn"

    notes_path = (vault / notes_subdir).resolve()
    attachments_path = (vault if attachment_folder == "." else vault / attachment_folder).resolve()
    ensure_inside(vault, notes_path, "notes_subdir")
    ensure_inside(vault, attachments_path, "attachment_folder")
    notes_path.mkdir(parents=True, exist_ok=True)
    attachments_path.mkdir(parents=True, exist_ok=True)

    existing = load_config(required=False)
    data: dict[str, Any] = {
        "schema_version": 1,
        "configured_at": existing.get("configured_at", now_iso()),
        "updated_at": now_iso(),
        "workspace_root": str(workspace),
        "obsidian_vault": str(vault),
        "notes_subdir": notes_subdir,
        "attachment_folder": attachment_folder,
        "quality_profile": "maximum",
        "asr_model": "large-v3",
        "ocr_profile": "PP-OCRv5",
        "keep_structured_evidence": True,
        "keep_transcript": True,
        "keep_raw_media": False,
    }
    if existing.get("runtime_python"):
        data["runtime_python"] = existing["runtime_python"]
    path = save_config(data)
    emit(
        {
            "configured": True,
            "config": str(path),
            "workspace_root": str(workspace),
            "obsidian_vault": str(vault),
            "notes_subdir": notes_subdir,
            "attachment_folder": attachment_folder,
            "next": "Run bootstrap.py provision when local media tools are needed.",
        },
        args.json,
    )
    return 0


def status(args: argparse.Namespace) -> int:
    path = config_path()
    if not path.exists():
        emit({"configured": False, "config": str(path)}, args.json)
        return 1
    try:
        data = load_config(required=True)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        emit({"configured": False, "config": str(path), "error": str(exc)}, args.json)
        return 1

    workspace = absolute_path(data.get("workspace_root", "."))
    vault_value = data.get("obsidian_vault")
    vault = absolute_path(vault_value) if vault_value else None
    result = {
        "configured": True,
        "config": str(path),
        "workspace_root": str(workspace),
        "workspace_exists": workspace.is_dir(),
        "obsidian_vault": str(vault) if vault else None,
        "vault_exists": bool(vault and vault.is_dir()),
        "quality_profile": data.get("quality_profile"),
        "asr_model": data.get("asr_model"),
        "ocr_profile": data.get("ocr_profile"),
        "runtime_python": data.get("runtime_python"),
    }
    emit(result, args.json)
    return 0 if result["workspace_exists"] and result["vault_exists"] else 1


def runtime_python(workspace: Path) -> Path:
    if os.name == "nt":
        return workspace / "cache" / "runtime" / ".venv" / "Scripts" / "python.exe"
    return workspace / "cache" / "runtime" / ".venv" / "bin" / "python"


def run_checked(command: list[str], env: dict[str, str] | None = None) -> None:
    subprocess.run(command, check=True, env=env)


def provision(args: argparse.Namespace) -> int:
    config = load_config(required=True)
    workspace = absolute_path(config["workspace_root"])
    workspace.mkdir(parents=True, exist_ok=True)
    python_path = runtime_python(workspace)
    if not python_path.exists():
        python_path.parent.parent.mkdir(parents=True, exist_ok=True)
        venv.EnvBuilder(with_pip=True).create(python_path.parent.parent)

    requirements = Path(__file__).resolve().parent.parent / "requirements-quality.txt"
    run_checked([str(python_path), "-m", "pip", "install", "--upgrade", "pip", "wheel"])
    run_checked([str(python_path), "-m", "pip", "install", "-r", str(requirements)])

    model_cache = workspace / "cache" / "models" / "faster-whisper"
    model_cache.mkdir(parents=True, exist_ok=True)
    ocr_cache = workspace / "cache" / "models" / "paddlex"
    ocr_cache.mkdir(parents=True, exist_ok=True)
    if not args.skip_model_download:
        environment = os.environ.copy()
        environment["LEARN_MODEL_CACHE"] = str(model_cache)
        environment["LEARN_ASR_MODEL"] = str(config.get("asr_model", "large-v3"))
        environment["PADDLE_PDX_CACHE_HOME"] = str(ocr_cache)
        code = (
            "import os; from faster_whisper import WhisperModel; "
            "WhisperModel(os.environ['LEARN_ASR_MODEL'], device='cpu', compute_type='int8', "
            "download_root=os.environ['LEARN_MODEL_CACHE']); print('ASR model ready')"
        )
        run_checked([str(python_path), "-c", code], env=environment)
        ocr_code = (
            "from paddleocr import PaddleOCR; "
            "PaddleOCR(lang='ch', ocr_version='PP-OCRv5', "
            "use_doc_orientation_classify=False, use_doc_unwarping=False, "
            "use_textline_orientation=True); print('OCR models ready')"
        )
        run_checked([str(python_path), "-c", ocr_code], env=environment)

    config["runtime_python"] = str(python_path.resolve())
    config["provisioned_at"] = now_iso()
    save_config(config)
    emit(
        {
            "provisioned": True,
            "runtime_python": str(python_path.resolve()),
            "asr_model": config.get("asr_model"),
            "asr_model_cached": not args.skip_model_download,
            "ocr_model_cached": not args.skip_model_download,
        },
        args.json,
    )
    return 0


def doctor(args: argparse.Namespace) -> int:
    try:
        config = load_config(required=True)
    except (OSError, ValueError, json.JSONDecodeError, FileNotFoundError) as exc:
        emit({"healthy": False, "error": str(exc), "config": str(config_path())}, args.json)
        return 1

    workspace = absolute_path(config["workspace_root"])
    python_path = Path(config.get("runtime_python") or runtime_python(workspace))
    checks: dict[str, Any] = {
        "workspace": workspace.is_dir(),
        "vault": absolute_path(config["obsidian_vault"]).is_dir(),
        "runtime_python": python_path.is_file(),
        "system_ffmpeg": bool(shutil.which("ffmpeg")),
    }
    if python_path.is_file():
        code = (
            "import importlib.util,json; names=['yt_dlp','faster_whisper','paddleocr',"
            "'imageio_ffmpeg','PIL','cv2','matplotlib']; "
            "print(json.dumps({n: importlib.util.find_spec(n) is not None for n in names}))"
        )
        try:
            completed = subprocess.run(
                [str(python_path), "-c", code],
                check=True,
                capture_output=True,
                text=True,
            )
            checks.update(json.loads(completed.stdout.strip()))
        except (subprocess.SubprocessError, json.JSONDecodeError) as exc:
            checks["runtime_imports"] = f"failed: {exc}"

    required = (
        "workspace",
        "vault",
        "runtime_python",
        "yt_dlp",
        "faster_whisper",
        "paddleocr",
        "imageio_ffmpeg",
        "PIL",
        "cv2",
        "matplotlib",
    )
    healthy = all(checks.get(name) is True for name in required)
    emit({"healthy": healthy, "checks": checks, "config": str(config_path())}, args.json)
    return 0 if healthy else 1


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)

    configure_parser = commands.add_parser("configure", help="write OS-local paths and create runtime directories")
    configure_parser.add_argument("--workspace", required=True)
    configure_parser.add_argument("--vault", required=True)
    configure_parser.add_argument("--notes-subdir", default="Learn")
    configure_parser.add_argument("--attachments", default="auto")
    configure_parser.add_argument("--json", action="store_true")
    configure_parser.set_defaults(func=configure)

    status_parser = commands.add_parser("status", help="show whether local configuration is ready")
    status_parser.add_argument("--json", action="store_true")
    status_parser.set_defaults(func=status)

    provision_parser = commands.add_parser("provision", help="install the reusable maximum-quality local toolchain")
    provision_parser.add_argument("--skip-model-download", action="store_true")
    provision_parser.add_argument("--json", action="store_true")
    provision_parser.set_defaults(func=provision)

    doctor_parser = commands.add_parser("doctor", help="check local media and visualization capabilities")
    doctor_parser.add_argument("--json", action="store_true")
    doctor_parser.set_defaults(func=doctor)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        return args.func(args)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        emit({"ok": False, "error": str(exc)}, getattr(args, "json", True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
