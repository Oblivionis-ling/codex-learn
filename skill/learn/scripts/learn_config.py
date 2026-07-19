#!/usr/bin/env python3
"""OS-local configuration helpers for the Learn skill."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


CONFIG_ENV = "CODEX_LEARN_CONFIG"
APP_DIR_NAME = "codex-learn"


def config_path() -> Path:
    override = os.environ.get(CONFIG_ENV)
    if override:
        return Path(override).expanduser().resolve()
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return (base / APP_DIR_NAME / "settings.json").resolve()


def load_config(required: bool = False) -> dict[str, Any]:
    path = config_path()
    if not path.exists():
        if required:
            raise FileNotFoundError(
                f"Learn is not configured. Run bootstrap.py configure first. Expected: {path}"
            )
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Learn config must be a JSON object: {path}")
    return data


def save_config(data: dict[str, Any]) -> Path:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)
    return path


def absolute_path(value: str | Path) -> Path:
    return Path(value).expanduser().resolve()


def obsidian_attachment_folder(vault: Path, fallback: str = "Attachments") -> str:
    app_json = vault / ".obsidian" / "app.json"
    if not app_json.exists():
        return fallback
    try:
        data = json.loads(app_json.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return fallback
    value = data.get("attachmentFolderPath")
    return value.strip().replace("\\", "/") if isinstance(value, str) and value.strip() else fallback


def configured_workspace(explicit: str | None = None) -> Path:
    if explicit:
        return absolute_path(explicit)
    config = load_config(required=True)
    value = config.get("workspace_root")
    if not value:
        raise ValueError("workspace_root is missing from the Learn config")
    return absolute_path(value)


def configured_vault(explicit: str | None = None) -> Path | None:
    if explicit:
        return absolute_path(explicit)
    config = load_config(required=False)
    value = config.get("obsidian_vault")
    return absolute_path(value) if value else None
