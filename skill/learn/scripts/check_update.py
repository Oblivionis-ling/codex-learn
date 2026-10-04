#!/usr/bin/env python3
"""Check the latest stable Learn release once per local day, then continue."""

from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path, PurePosixPath
from typing import Any, Iterator

from learn_config import config_path


REPOSITORY = "Oblivionis-ling/codex-learn"
PACKAGE_PATH = PurePosixPath("skill/learn")
NETWORK_TIMEOUT = 5
NETWORK_BUDGET = 20
MAX_ARCHIVE_BYTES = 8 * 1024 * 1024
MAX_PACKAGE_BYTES = 32 * 1024 * 1024


class UpdateError(Exception):
    """An expected update failure with a non-sensitive reason code."""


def version_tuple(value: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", value)
    if not match:
        raise UpdateError("invalid_version")
    return tuple(int(part) for part in match.groups())


def current_version(root: Path) -> str:
    value = (root / "VERSION").read_text(encoding="utf-8").strip()
    version_tuple(value)
    return value


def read_state(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def write_state(path: Path, data: dict[str, Any]) -> None:
    temporary = path.with_suffix(".tmp")
    try:
        temporary.write_text(json.dumps(data, ensure_ascii=False) + "\n", encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def update_lock(path: Path) -> Iterator[bool]:
    """Use a process lock so an interrupted updater leaves no stale lock."""
    with path.open("a+b") as handle:
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            yield False
            return
        try:
            yield True
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def download(url: str, limit: int, deadline: float) -> bytes:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise UpdateError("network_timeout")
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "codex-learn-updater", "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(request, timeout=min(NETWORK_TIMEOUT, remaining)) as response:
        chunks: list[bytes] = []
        size = 0
        while True:
            if time.monotonic() >= deadline:
                raise UpdateError("network_timeout")
            chunk = response.read1(64 * 1024)
            if not chunk:
                return b"".join(chunks)
            size += len(chunk)
            if size > limit:
                raise UpdateError("download_too_large")
            chunks.append(chunk)


def release_package(payload: bytes, expected_version: str) -> dict[str, tuple[bytes, int]]:
    import zipfile

    files: dict[str, tuple[bytes, int]] = {}
    total = 0
    archive_root = ""
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        if len(archive.infolist()) > 2000:
            raise UpdateError("invalid_archive")
        for info in archive.infolist():
            path = PurePosixPath(info.filename)
            if path.is_absolute() or "\\" in info.filename or any(p in (".", "..") or ":" in p for p in path.parts):
                raise UpdateError("invalid_archive_path")
            if len(path.parts) < 4 or PurePosixPath(*path.parts[1:3]) != PACKAGE_PATH:
                continue
            if archive_root and archive_root != path.parts[0]:
                raise UpdateError("invalid_archive")
            archive_root = path.parts[0]
            if info.is_dir():
                continue
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise UpdateError("archive_symlink")
            relative = PurePosixPath(*path.parts[3:]).as_posix()
            if any(p.startswith(".") or p == "__pycache__" for p in path.parts[3:]):
                raise UpdateError("invalid_package_path")
            if relative in files:
                raise UpdateError("duplicate_package_path")
            total += info.file_size
            if total > MAX_PACKAGE_BYTES:
                raise UpdateError("package_too_large")
            data = archive.read(info)
            if relative.endswith(".py"):
                ast.parse(data, filename=relative)
            files[relative] = (data, stat.S_IMODE(mode) or 0o644)
    required = {"SKILL.md", "VERSION", "scripts/check_update.py"}
    if not required.issubset(files):
        raise UpdateError("incomplete_package")
    if files["VERSION"][0].decode("utf-8").strip() != expected_version:
        raise UpdateError("release_version_mismatch")
    skill = files["SKILL.md"][0].decode("utf-8")
    frontmatter = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)", skill, re.DOTALL)
    if not frontmatter or not re.search(r"(?m)^name:\s*learn\s*$", frontmatter.group(1)):
        raise UpdateError("invalid_skill")
    return files


def git_repository(root: Path) -> Path | None:
    for ancestor in (root, *root.parents):
        if (ancestor / ".git").exists():
            if root != ancestor / Path(PACKAGE_PATH.as_posix()):
                raise UpdateError("unrecognized_git_install")
            return ancestor
    return None


def run_git(repository: Path, *arguments: str, timeout: int = 10) -> str:
    environment = os.environ.copy()
    environment["GIT_TERMINAL_PROMPT"] = "0"
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout, env=environment,
    )
    if result.returncode:
        raise UpdateError("git_update_failed")
    return result.stdout.strip()


def update_git(repository: Path, root: Path, tag: str, files: dict[str, tuple[bytes, int]], state_dir: Path) -> None:
    if run_git(repository, "status", "--porcelain", "--untracked-files=all"):
        raise UpdateError("local_git_changes")
    before = run_git(repository, "rev-parse", "HEAD")
    run_git(repository, "fetch", "--no-tags", f"https://github.com/{REPOSITORY}.git", f"refs/tags/{tag}", timeout=15)
    fetched = run_git(repository, "rev-parse", "FETCH_HEAD^{commit}")
    if run_git(repository, "show", f"{fetched}:skill/learn/VERSION") != files["VERSION"][0].decode("utf-8").strip():
        raise UpdateError("release_version_mismatch")
    run_git(repository, "merge-base", "--is-ancestor", before, fetched)
    if run_git(repository, "status", "--porcelain", "--untracked-files=all") or run_git(repository, "rev-parse", "HEAD") != before:
        raise UpdateError("local_git_changes")
    temporary_root = state_dir / "_tmp"
    temporary_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="git-hooks-", dir=temporary_root) as empty_hooks:
        hook_option = f"core.hooksPath={empty_hooks}"
        try:
            run_git(repository, "-c", hook_option, "merge", "--ff-only", "--no-edit", fetched, timeout=15)
            if current_version(root) != files["VERSION"][0].decode("utf-8").strip():
                raise UpdateError("installed_version_mismatch")
        except Exception:
            run_git(repository, "-c", hook_option, "reset", "--hard", before)
            raise


def update_directory(root: Path, files: dict[str, tuple[bytes, int]], state_dir: Path, version: str) -> None:
    """Stage on the installation's volume, preserve a backup, then swap directories."""
    if state_dir.is_relative_to(root):
        raise UpdateError("state_inside_skill")
    backups = state_dir / "backups"
    backups.mkdir(exist_ok=True)
    transaction = Path(tempfile.mkdtemp(prefix=f".{root.name}-update-", dir=root.parent)).resolve()
    try:
        if transaction.parent != root.parent or transaction == root:
            raise UpdateError("invalid_update_target")
        staged, previous = transaction / "new", transaction / "previous"
        staged.mkdir()
        for relative, (data, mode) in files.items():
            target = staged / relative
            if not target.resolve().is_relative_to(staged):
                raise UpdateError("invalid_update_target")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            target.chmod(mode)
        if any((staged / name).read_bytes() != data for name, (data, _) in files.items()):
            raise UpdateError("staged_package_mismatch")
        backup = backups / f"{version}-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{transaction.name.rsplit('-', 1)[-1]}"
        shutil.copytree(root, backup, symlinks=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        root.rename(previous)
        try:
            staged.rename(root)
        except Exception:
            previous.rename(root)
            raise
    finally:
        # A completed swap remains successful if removal of its duplicate files fails.
        if root.is_dir() and transaction.parent == root.parent and transaction != root:
            shutil.rmtree(transaction, ignore_errors=True)


def failure_reason(error: Exception) -> str:
    if isinstance(error, UpdateError):
        return str(error)
    if isinstance(error, PermissionError):
        return "permission_denied"
    if isinstance(error, (TimeoutError, subprocess.TimeoutExpired)):
        return "update_timeout"
    if isinstance(error, urllib.error.URLError):
        return "network_error"
    return "update_failed"


def check_update() -> dict[str, Any]:
    root = Path(__file__).resolve().parent.parent
    result: dict[str, Any] = {"status": "failed", "reload_skill": False, "skill_file": str(root / "SKILL.md")}
    try:
        installed = current_version(root)
        result["installed_version"] = installed
        identifier = hashlib.sha256(os.fsencode(os.path.normcase(str(root)))).hexdigest()[:16]
        state_dir = config_path().parent / "updates" / identifier
        state_dir.mkdir(parents=True, exist_ok=True)
        state_file = state_dir / "state.json"
        today = date.today().isoformat()
        with update_lock(state_dir / "update.lock") as acquired:
            if not acquired:
                return {**result, "status": "busy"}
            if read_state(state_file).get("checked_on") == today:
                return {**result, "status": "already_checked"}
            # Record the attempt before networking, including timeouts and crashes.
            write_state(state_file, {"checked_on": today, "status": "checking", "installed_version": installed})
            try:
                deadline = time.monotonic() + NETWORK_BUDGET
                release = json.loads(download(f"https://api.github.com/repos/{REPOSITORY}/releases/latest", 256 * 1024, deadline))
                if not isinstance(release, dict) or release.get("draft") or release.get("prerelease"):
                    raise UpdateError("invalid_release")
                tag = release.get("tag_name")
                if not isinstance(tag, str):
                    raise UpdateError("invalid_release")
                latest = ".".join(str(part) for part in version_tuple(tag))
                result["latest_version"] = latest
                if version_tuple(latest) <= version_tuple(installed):
                    result["status"] = "up_to_date"
                else:
                    repository = git_repository(root)
                    payload = download(f"https://codeload.github.com/{REPOSITORY}/zip/refs/tags/{tag}", MAX_ARCHIVE_BYTES, deadline)
                    files = release_package(payload, latest)
                    if repository:
                        update_git(repository, root, tag, files, state_dir)
                    else:
                        update_directory(root, files, state_dir, installed)
                    result.update(status="updated", installed_version=latest, previous_version=installed, reload_skill=True)
            except Exception as error:
                result.update(status="failed", reason=failure_reason(error))
            # A state write failure must not hide a completed update and its reload signal.
            try:
                write_state(state_file, {"checked_on": today, **{k: v for k, v in result.items() if k != "skill_file"}})
            except OSError:
                pass
    except Exception as error:
        result["reason"] = failure_reason(error)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit the invocation result as JSON")
    args = parser.parse_args()
    result = check_update()
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        for key, value in result.items():
            print(f"{key}: {value}")
    # Updates are optional; a failed check must not stop the learning task.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
