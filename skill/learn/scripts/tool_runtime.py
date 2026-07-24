#!/usr/bin/env python3
"""Shared runtime selection and JSON helpers for Learn media tools."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from learn_config import absolute_path, load_config


def configured_paths() -> tuple[dict[str, Any], Path, Path]:
    config = load_config(required=True)
    workspace = absolute_path(config["workspace_root"])
    model_root = workspace / "cache" / "models"
    model_root.mkdir(parents=True, exist_ok=True)
    return config, workspace, model_root


def cpu_threads(config: dict[str, Any] | None = None) -> int:
    config = config or {}
    explicit = config.get("cpu_threads")
    if isinstance(explicit, int) and explicit > 0:
        return explicit
    count = os.cpu_count() or 4
    return max(1, min(12, count - 2 if count > 4 else count))


def configure_process_environment(config: dict[str, Any], model_root: Path) -> None:
    threads = str(cpu_threads(config))
    os.environ.setdefault("OMP_NUM_THREADS", threads)
    os.environ.setdefault("OMP_WAIT_POLICY", "PASSIVE")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    os.environ.setdefault("PADDLE_PDX_CACHE_HOME", str(model_root / "paddlex"))


def select_asr_backend(config: dict[str, Any]) -> dict[str, Any]:
    import ctranslate2

    requested = str(config.get("asr_device", "auto")).lower()
    cuda_devices = ctranslate2.get_cuda_device_count()
    if requested == "cuda" and cuda_devices < 1:
        raise RuntimeError("asr_device=cuda was requested but no CUDA device is available")
    use_cuda = requested == "cuda" or (requested == "auto" and cuda_devices > 0)
    device = "cuda" if use_cuda else "cpu"
    configured_compute = str(config.get("asr_compute_type") or "auto").lower()
    compute_type = (
        "float16" if use_cuda else "int8"
    ) if configured_compute == "auto" else configured_compute
    threads = cpu_threads(config)
    default_batch = 16 if use_cuda else max(2, min(6, threads // 2))
    configured_batch = config.get("asr_batch_size")
    batch_size = configured_batch if isinstance(configured_batch, int) and configured_batch > 0 else default_batch
    return {
        "device": device,
        "compute_type": compute_type,
        "cpu_threads": threads,
        "batch_size": batch_size,
        "cuda_devices": cuda_devices,
    }


def write_json_atomic(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def emit(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))
