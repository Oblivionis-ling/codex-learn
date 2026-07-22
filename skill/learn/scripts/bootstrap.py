#!/usr/bin/env python3
"""Configure, provision, and diagnose the optimized local Learn runtime."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
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


PROVISION_SCHEMA = 2
RUNTIME_GENERATION = "runtime-v2"
RUNTIME_DIRS = ("jobs", "_work", "cache", "output", "sandbox")
REQUIRED_MODULES = ("yt_dlp", "faster_whisper", "rapidocr", "imageio_ffmpeg", "PIL", "cv2", "matplotlib")
REQUIRED_DISTRIBUTIONS = (
    "yt-dlp",
    "faster-whisper",
    "rapidocr",
    "imageio-ffmpeg",
    "Pillow",
    "matplotlib",
)


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


def runtime_python(workspace: Path) -> Path:
    if os.name == "nt":
        return workspace / "cache" / RUNTIME_GENERATION / ".venv" / "Scripts" / "python.exe"
    return workspace / "cache" / RUNTIME_GENERATION / ".venv" / "bin" / "python"


def runtime_site_packages(python_path: Path) -> Path:
    if os.name == "nt":
        return python_path.parent.parent / "Lib" / "site-packages"
    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    return python_path.parent.parent / "lib" / version / "site-packages"


def requirements_path() -> Path:
    return Path(__file__).resolve().parent.parent / "requirements-quality.txt"


def requirements_fingerprint() -> str:
    digest = hashlib.sha256()
    digest.update(requirements_path().read_bytes())
    digest.update(f"|schema={PROVISION_SCHEMA}|python={sys.version_info.major}.{sys.version_info.minor}".encode())
    return digest.hexdigest()


def provision_state_path(workspace: Path) -> Path:
    return workspace / "cache" / RUNTIME_GENERATION / "provision-state.json"


def load_state(workspace: Path) -> dict[str, Any]:
    path = provision_state_path(workspace)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_state(workspace: Path, data: dict[str, Any]) -> None:
    path = provision_state_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def asr_model_ready(workspace: Path, model_name: str) -> bool:
    cache = workspace / "cache" / "models" / "faster-whisper"
    if not cache.is_dir():
        return False
    expected = f"faster-whisper-{model_name}".lower()
    return any(expected in str(path.parent).lower() for path in cache.rglob("model.bin"))


def rapidocr_ready(python_path: Path) -> bool:
    models = runtime_site_packages(python_path) / "rapidocr" / "models"
    return all(
        (models / name).is_file()
        for name in (
            "PP-OCRv6_det_small.onnx",
            "PP-OCRv6_rec_small.onnx",
            "ch_ppocr_mobile_v2.0_cls_mobile.onnx",
        )
    )


def ffmpeg_ready(python_path: Path) -> bool:
    package = runtime_site_packages(python_path) / "imageio_ffmpeg" / "binaries"
    return package.is_dir() and any(path.is_file() for path in package.iterdir())


def state_current(workspace: Path, python_path: Path, config: dict[str, Any]) -> bool:
    state = load_state(workspace)
    return bool(
        python_path.is_file()
        and state.get("schema_version") == PROVISION_SCHEMA
        and state.get("requirements_fingerprint") == requirements_fingerprint()
        and state.get("asr_model") == config.get("asr_model", "large-v3")
        and state.get("ocr_engine") == "rapidocr"
    )


def run_checked(command: list[str], env: dict[str, str] | None = None) -> None:
    subprocess.run(command, check=True, env=env)


def dependency_probe(python_path: Path) -> dict[str, Any]:
    code = (
        "import importlib,importlib.metadata,json; "
        f"mods={list(REQUIRED_MODULES)!r}; dists={list(REQUIRED_DISTRIBUTIONS)!r}; "
        "results={}; errors={}; "
        "exec(\"for m in mods:\\n try:\\n  importlib.import_module(m); results[m]=True\\n except Exception as e:\\n  results[m]=False; errors[m]=str(e)\"); "
        "print(json.dumps({'modules':results,'errors':errors,"
        "'versions':{d:importlib.metadata.version(d) for d in dists}}))"
    )
    completed = subprocess.run(
        [str(python_path), "-c", code], check=True, capture_output=True, text=True
    )
    return json.loads(completed.stdout.strip())


def hardware_probe(python_path: Path) -> dict[str, Any]:
    code = (
        "import ctranslate2,os,json; c=ctranslate2.get_cuda_device_count(); "
        "print(json.dumps({'cpu_count':os.cpu_count(),'cuda_devices':c,"
        "'asr_device':'cuda' if c else 'cpu','asr_compute_type':'float16' if c else 'int8'}))"
    )
    completed = subprocess.run(
        [str(python_path), "-c", code], check=True, capture_output=True, text=True
    )
    return json.loads(completed.stdout.strip())


def optimized_config(existing: dict[str, Any]) -> dict[str, Any]:
    data = dict(existing)
    data.update(
        {
            "quality_profile": "maximum",
            "asr_model": "large-v3",
            "asr_device": data.get("asr_device", "auto"),
            "asr_compute_type": data.get("asr_compute_type", "auto"),
            "asr_batch_size": data.get("asr_batch_size", "auto"),
            "ocr_engine": "rapidocr",
            "ocr_profile": "PP-OCRv6-small",
            "keep_structured_evidence": True,
            "keep_transcript": True,
            "keep_raw_media": False,
        }
    )
    return data


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
    data = optimized_config(existing)
    data.update(
        {
            "schema_version": 1,
            "configured_at": existing.get("configured_at", now_iso()),
            "updated_at": now_iso(),
            "workspace_root": str(workspace),
            "obsidian_vault": str(vault),
            "notes_subdir": notes_subdir,
            "attachment_folder": attachment_folder,
        }
    )
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
            "next": "Run bootstrap.py provision once; unchanged reruns use the fingerprint fast path.",
        },
        args.json,
    )
    return 0


def status(args: argparse.Namespace) -> int:
    path = config_path()
    if not path.exists():
        emit({"configured": False, "config": str(path)}, args.json)
        return 1
    data = load_config(required=True)
    workspace = absolute_path(data.get("workspace_root", "."))
    vault_value = data.get("obsidian_vault")
    vault = absolute_path(vault_value) if vault_value else None
    python_path = Path(data.get("runtime_python") or runtime_python(workspace))
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
        "runtime_python": str(python_path),
        "provision_current": state_current(workspace, python_path, data),
    }
    emit(result, args.json)
    return 0 if result["workspace_exists"] and result["vault_exists"] else 1


def prefetch_asr(python_path: Path, workspace: Path, model_name: str, environment: dict[str, str]) -> None:
    environment["LEARN_MODEL_CACHE"] = str(workspace / "cache" / "models" / "faster-whisper")
    environment["LEARN_ASR_MODEL"] = model_name
    code = (
        "import os; from faster_whisper import WhisperModel; "
        "WhisperModel(os.environ['LEARN_ASR_MODEL'],device='cpu',compute_type='int8',"
        "download_root=os.environ['LEARN_MODEL_CACHE']); print('ASR model ready')"
    )
    run_checked([str(python_path), "-c", code], env=environment)


def verify_rapidocr(python_path: Path, environment: dict[str, str]) -> None:
    code = "from rapidocr import RapidOCR; RapidOCR(); print('RapidOCR models ready')"
    run_checked([str(python_path), "-c", code], env=environment)


def provision(args: argparse.Namespace) -> int:
    started = time.perf_counter()
    config = optimized_config(load_config(required=True))
    workspace = absolute_path(config["workspace_root"])
    workspace.mkdir(parents=True, exist_ok=True)
    python_path = runtime_python(workspace)
    current = state_current(workspace, python_path, config)
    model_name = str(config.get("asr_model", "large-v3"))
    models_ready = asr_model_ready(workspace, model_name) and rapidocr_ready(python_path)
    if current and models_ready and not args.force:
        config["runtime_python"] = str(python_path.resolve())
        config["ocr_engine"] = "rapidocr"
        config["ocr_profile"] = "PP-OCRv6-small"
        if args.pip_index:
            config["pip_index"] = args.pip_index
        save_config(config)
        emit(
            {
                "provisioned": True,
                "fast_path": True,
                "dependencies": "unchanged",
                "models": "cached",
                "elapsed_seconds": round(time.perf_counter() - started, 3),
                "runtime_python": str(python_path.resolve()),
            },
            args.json,
        )
        return 0

    created_runtime = False
    if not python_path.exists():
        python_path.parent.parent.mkdir(parents=True, exist_ok=True)
        venv.EnvBuilder(with_pip=True).create(python_path.parent.parent)
        created_runtime = True

    dependency_action = "adopted"
    if not args.adopt_existing:
        command = [
            str(python_path),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--prefer-binary",
            "-r",
            str(requirements_path()),
        ]
        pip_index = args.pip_index or config.get("pip_index") or os.environ.get("CODEX_LEARN_PIP_INDEX")
        if pip_index:
            command[5:5] = ["--index-url", pip_index]
        run_checked(command)
        dependency_action = "installed"

    probe = dependency_probe(python_path)
    missing = [name for name, available in probe["modules"].items() if not available]
    if missing:
        detail = "; ".join(f"{name}: {probe['errors'].get(name, 'unavailable')}" for name in missing)
        raise RuntimeError(f"runtime modules failed: {detail}")

    environment = os.environ.copy()
    environment.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    asr_action = "cached"
    ocr_action = "cached"
    if not args.skip_model_download:
        if args.force or not asr_model_ready(workspace, model_name):
            prefetch_asr(python_path, workspace, model_name, environment)
            asr_action = "downloaded"
        if args.force or not rapidocr_ready(python_path):
            verify_rapidocr(python_path, environment)
            ocr_action = "verified"

    hardware = hardware_probe(python_path)
    state = {
        "schema_version": PROVISION_SCHEMA,
        "requirements_fingerprint": requirements_fingerprint(),
        "provisioned_at": now_iso(),
        "python": str(python_path.resolve()),
        "asr_model": model_name,
        "ocr_engine": "rapidocr",
        "ocr_profile": "PP-OCRv6-small",
        "dependency_versions": probe["versions"],
        "hardware": hardware,
    }
    save_state(workspace, state)
    config["runtime_python"] = str(python_path.resolve())
    config["provisioned_at"] = now_iso()
    config["ocr_engine"] = "rapidocr"
    config["ocr_profile"] = "PP-OCRv6-small"
    if args.pip_index:
        config["pip_index"] = args.pip_index
    save_config(config)
    emit(
        {
            "provisioned": True,
            "fast_path": False,
            "runtime_created": created_runtime,
            "dependencies": dependency_action,
            "asr_model": asr_action,
            "ocr_model": ocr_action,
            "hardware": hardware,
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "runtime_python": str(python_path.resolve()),
        },
        args.json,
    )
    return 0


def deep_probe(python_path: Path, workspace: Path) -> dict[str, Any]:
    environment = os.environ.copy()
    environment["LEARN_MODEL_CACHE"] = str(workspace / "cache" / "models" / "faster-whisper")
    environment["LEARN_ASR_MODEL"] = str(load_config(required=True).get("asr_model", "large-v3"))
    probe_path = workspace / "_work" / "doctor-probe.png"
    probe_path.parent.mkdir(parents=True, exist_ok=True)
    environment["LEARN_OCR_PROBE"] = str(probe_path)
    code = (
        "import os,json; from pathlib import Path; from PIL import Image,ImageDraw; "
        "from rapidocr import RapidOCR; from faster_whisper import WhisperModel; import imageio_ffmpeg; "
        "p=Path(os.environ['LEARN_OCR_PROBE']); "
        "im=Image.new('RGB',(640,160),'white'); ImageDraw.Draw(im).text((30,60),'Learn OCR 123',fill='black',stroke_width=1); im.save(p); "
        "o=RapidOCR()(p); "
        "WhisperModel(os.environ['LEARN_ASR_MODEL'],device='cpu',compute_type='int8',"
        "download_root=os.environ['LEARN_MODEL_CACHE'],local_files_only=True); "
        "print(json.dumps({'ocr_inference':o is not None,'asr_model_load':True,"
        "'ffmpeg':Path(imageio_ffmpeg.get_ffmpeg_exe()).is_file()}))"
    )
    try:
        completed = subprocess.run(
            [str(python_path), "-c", code],
            check=True,
            capture_output=True,
            text=True,
            env=environment,
        )
    finally:
        probe_path.unlink(missing_ok=True)
    lines = [line for line in completed.stdout.splitlines() if line.strip().startswith("{")]
    if not lines:
        raise RuntimeError("deep probe returned no JSON result")
    return json.loads(lines[-1])


def doctor(args: argparse.Namespace) -> int:
    started = time.perf_counter()
    config = load_config(required=True)
    workspace = absolute_path(config["workspace_root"])
    python_path = Path(config.get("runtime_python") or runtime_python(workspace))
    model_name = str(config.get("asr_model", "large-v3"))
    checks: dict[str, Any] = {
        "workspace": workspace.is_dir(),
        "vault": absolute_path(config["obsidian_vault"]).is_dir(),
        "runtime_python": python_path.is_file(),
        "provision_state": state_current(workspace, python_path, config),
        "asr_model": asr_model_ready(workspace, model_name),
        "rapidocr_models": rapidocr_ready(python_path),
        "bundled_ffmpeg": ffmpeg_ready(python_path),
        "system_ffmpeg": bool(shutil.which("ffmpeg")),
    }
    if args.deep and all(checks[key] for key in ("runtime_python", "asr_model", "rapidocr_models")):
        try:
            checks["deep"] = deep_probe(python_path, workspace)
        except (subprocess.SubprocessError, ValueError, json.JSONDecodeError, RuntimeError) as exc:
            checks["deep"] = {"ok": False, "error": str(exc)}
    required = ("workspace", "vault", "runtime_python", "provision_state", "asr_model", "rapidocr_models", "bundled_ffmpeg")
    healthy = all(checks.get(name) is True for name in required)
    if args.deep:
        deep = checks.get("deep", {})
        healthy = healthy and isinstance(deep, dict) and all(
            deep.get(key) is True for key in ("ocr_inference", "asr_model_load", "ffmpeg")
        )
    emit(
        {
            "healthy": healthy,
            "deep": args.deep,
            "checks": checks,
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "config": str(config_path()),
        },
        args.json,
    )
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

    status_parser = commands.add_parser("status", help="show configuration and provision fingerprint state")
    status_parser.add_argument("--json", action="store_true")
    status_parser.set_defaults(func=status)

    provision_parser = commands.add_parser("provision", help="idempotently install the optimized local toolchain")
    provision_parser.add_argument("--skip-model-download", action="store_true")
    provision_parser.add_argument("--force", action="store_true")
    provision_parser.add_argument("--adopt-existing", action="store_true")
    provision_parser.add_argument("--pip-index")
    provision_parser.add_argument("--json", action="store_true")
    provision_parser.set_defaults(func=provision)

    doctor_parser = commands.add_parser("doctor", help="check cached tools; use --deep after installation or failures")
    doctor_parser.add_argument("--deep", action="store_true")
    doctor_parser.add_argument("--json", action="store_true")
    doctor_parser.set_defaults(func=doctor)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        return args.func(args)
    except (OSError, ValueError, subprocess.CalledProcessError, RuntimeError) as exc:
        emit({"ok": False, "error": str(exc)}, getattr(args, "json", True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
