#!/usr/bin/env python3
"""Initialize Learn jobs and validate multimodal evidence bundles."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from learn_config import configured_workspace, load_config


PLATFORM_HOSTS = {
    "bilibili": ("bilibili.com", "b23.tv"),
    "wechat": ("mp.weixin.qq.com",),
    "xiaohongshu": ("xiaohongshu.com", "xhslink.com"),
}
VISUAL_COLLECTIONS = ("original_images", "keyframes", "experiment_figures")
CONTENT_PROFILES = {"technical", "overview", "catalog", "visual"}
EVIDENCE_KINDS = {"source_fact", "interpretation", "external_fact", "recommendation"}
EVIDENCE_LEVELS = {"A", "B", "C", "D"}
VERIFICATION_STATES = {"verified", "partially_verified", "unverified", "contradicted"}
OBSIDIAN_EMBED_RE = re.compile(r"!\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
MARKDOWN_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")


def detect_platform(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme in {"", "file"} and (parsed.scheme == "file" or Path(value).expanduser().exists()):
        return "local"
    host = parsed.netloc.lower().split(":", 1)[0]
    for platform, hosts in PLATFORM_HOSTS.items():
        if any(host == item or host.endswith("." + item) for item in hosts):
            return platform
    return "web"


def source_identifier(value: str, platform: str) -> str:
    patterns = {
        "bilibili": r"(BV[0-9A-Za-z]+)",
        "xiaohongshu": r"/(?:explore|discovery/item)/([0-9a-fA-F]{16,32})",
        "wechat": r"/s/([^/?#]+)",
    }
    pattern = patterns.get(platform)
    if pattern:
        match = re.search(pattern, value)
        if match:
            return re.sub(r"[^0-9A-Za-z_-]+", "-", match.group(1))[:64]
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def dump_json(data: object, path: Path | None = None) -> None:
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if path:
        path.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)


def init_job(args: argparse.Namespace) -> int:
    root = configured_workspace(args.workspace)
    platform = args.platform or detect_platform(args.url)
    identifier = source_identifier(args.url, platform)
    job_id = f"{platform}-{identifier}"

    paths = {
        "job_dir": root / "jobs" / job_id,
        "work_dir": root / "_work" / job_id,
        "sandbox_dir": root / "sandbox" / job_id,
        "output_dir": root / "output",
        "cache_dir": root / "cache",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)

    manifest = {
        "schema_version": 1,
        "job_id": job_id,
        "status": "created",
        "created_at": now_iso(),
        "source": {"url": args.url, "platform": platform, "title": args.title or ""},
        "paths": {key: str(value) for key, value in paths.items()},
    }
    manifest_path = paths["job_dir"] / "job.json"
    dump_json(manifest, manifest_path)
    dump_json({"manifest": str(manifest_path), **manifest})
    return 0


def validate_visuals(
    bundle: dict,
    artifact_ids: set[str],
    duration: float | int | None,
    errors: list[str],
    warnings: list[str],
) -> tuple[int, set[str]]:
    count = 0
    visual_ids: set[str] = set()
    for collection in VISUAL_COLLECTIONS:
        items = bundle.get(collection, [])
        if not isinstance(items, list):
            errors.append(f"{collection} must be an array")
            continue
        count += len(items)
        for index, item in enumerate(items):
            prefix = f"{collection}[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{prefix} must be an object")
                continue
            item_id = item.get("id")
            if not item_id:
                errors.append(f"{prefix}.id is required")
            elif item_id in visual_ids:
                errors.append(f"duplicate visual id: {item_id}")
            else:
                visual_ids.add(item_id)
            if not item.get("local_path") and not item.get("source_url"):
                errors.append(f"{prefix} requires local_path or source_url")
            artifact_ref = item.get("artifact_ref")
            if artifact_ref and artifact_ref not in artifact_ids:
                errors.append(f"{prefix}.artifact_ref is missing from artifacts: {artifact_ref}")
            if not item.get("caption"):
                warnings.append(f"{prefix} has no caption")
            seconds = item.get("timestamp_seconds")
            if (
                collection == "keyframes"
                and isinstance(seconds, (int, float))
                and isinstance(duration, (int, float))
                and not 0 <= seconds <= duration
            ):
                errors.append(f"{prefix}.timestamp_seconds is outside source duration")
    return count, visual_ids


def validate_bundle(args: argparse.Namespace) -> int:
    path = Path(args.evidence).expanduser().resolve()
    try:
        bundle = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        dump_json({"valid": False, "errors": [str(exc)], "warnings": []})
        return 1

    errors: list[str] = []
    warnings: list[str] = []
    if bundle.get("schema_version") != 1:
        errors.append("schema_version must be 1")

    source = bundle.get("source")
    if not isinstance(source, dict):
        errors.append("source must be an object")
        source = {}
    for key in ("url", "platform", "title"):
        if not source.get(key):
            errors.append(f"source.{key} is required")

    content_profile = bundle.get("content_profile")
    if content_profile not in CONTENT_PROFILES:
        errors.append(f"content_profile must be one of {sorted(CONTENT_PROFILES)}")

    artifacts = bundle.get("artifacts", [])
    if not isinstance(artifacts, list):
        errors.append("artifacts must be an array")
        artifacts = []
    artifact_ids: set[str] = set()
    for index, artifact in enumerate(artifacts):
        prefix = f"artifacts[{index}]"
        if not isinstance(artifact, dict):
            errors.append(f"{prefix} must be an object")
            continue
        artifact_id = artifact.get("id")
        if not artifact_id:
            errors.append(f"{prefix}.id is required")
        elif artifact_id in artifact_ids:
            errors.append(f"duplicate artifact id: {artifact_id}")
        else:
            artifact_ids.add(artifact_id)
        if not artifact.get("modality"):
            errors.append(f"{prefix}.modality is required")
        if not artifact.get("locator"):
            warnings.append(f"{prefix} has no locator")

    claims = bundle.get("claims", [])
    if not isinstance(claims, list):
        errors.append("claims must be an array")
        claims = []
    for index, claim in enumerate(claims):
        prefix = f"claims[{index}]"
        if not isinstance(claim, dict):
            errors.append(f"{prefix} must be an object")
            continue
        if not claim.get("statement"):
            errors.append(f"{prefix}.statement is required")
        if claim.get("kind") not in EVIDENCE_KINDS:
            errors.append(f"{prefix}.kind must be one of {sorted(EVIDENCE_KINDS)}")
        if claim.get("evidence_level") not in EVIDENCE_LEVELS:
            errors.append(f"{prefix}.evidence_level must be A, B, C, or D")
        if claim.get("verification") not in VERIFICATION_STATES:
            errors.append(f"{prefix}.verification is invalid")
        refs = claim.get("evidence_refs", [])
        if not isinstance(refs, list):
            errors.append(f"{prefix}.evidence_refs must be an array")
            refs = []
        missing = sorted({ref for ref in refs if ref not in artifact_ids})
        if missing:
            errors.append(f"{prefix} references missing artifacts: {', '.join(missing)}")
        if claim.get("evidence_level") in {"A", "B"} and not refs:
            errors.append(f"{prefix} level A/B requires evidence_refs")
        if claim.get("verification") in {"verified", "partially_verified"} and not refs:
            errors.append(f"{prefix} verified state requires evidence_refs")

    summary = bundle.get("summary")
    if not isinstance(summary, dict):
        errors.append("summary must be an object")
        summary = {}
    if not summary.get("one_sentence"):
        warnings.append("summary.one_sentence is missing")
    if not summary.get("overview"):
        errors.append("summary.overview is required")
    presentation = summary.get("presentation")
    if content_profile == "technical" and presentation not in (
        None,
        "introduction",
        "workflow",
        "evaluation",
    ):
        errors.append("technical summary.presentation must be introduction, workflow, or evaluation")
    decision_points = summary.get("decision_points", [])
    if content_profile == "technical" and decision_points is not None and not isinstance(decision_points, list):
        errors.append("technical summary.decision_points must be a list when present")
    if content_profile == "technical" and presentation != "evaluation" and decision_points:
        warnings.append("summary.decision_points is used only by technical evaluation presentation")
    procedure = summary.get("procedure", [])
    if content_profile == "technical" and procedure is not None and not isinstance(procedure, list):
        errors.append("technical summary.procedure must be a list when present")
    if content_profile == "technical" and presentation == "evaluation" and procedure:
        warnings.append("summary.procedure is ignored by technical evaluation presentation")
    if content_profile != "technical" and procedure:
        warnings.append(f"{content_profile} profile ignores summary.procedure")
    catalog_format = summary.get("catalog_format")
    if content_profile == "catalog" and catalog_format not in (None, "recommendations", "qa"):
        errors.append("catalog summary.catalog_format must be recommendations or qa")
    if content_profile != "catalog" and catalog_format:
        warnings.append(f"{content_profile} profile ignores summary.catalog_format")

    duration = source.get("duration_seconds")
    timeline = summary.get("timeline", [])
    if isinstance(duration, (int, float)) and isinstance(timeline, list):
        for index, item in enumerate(timeline):
            seconds = item.get("seconds") if isinstance(item, dict) else None
            if isinstance(seconds, (int, float)) and not 0 <= seconds <= duration:
                errors.append(f"summary.timeline[{index}].seconds is outside source duration")

    summary_diagram = bundle.get("summary_diagram")
    if summary_diagram is not None:
        if not isinstance(summary_diagram, dict):
            errors.append("summary_diagram must be an object")
        elif summary_diagram.get("type", "mermaid") != "mermaid" or not summary_diagram.get("code"):
            errors.append("summary_diagram requires type=mermaid and non-empty code")

    experiment = bundle.get("experiment", {})
    if content_profile == "technical":
        if not isinstance(experiment, dict) or not experiment:
            errors.append("technical profile requires experiment")
        else:
            allowed_status = {"completed", "inconclusive", "failed", "not_run"}
            status = experiment.get("status")
            if status not in allowed_status:
                errors.append(f"experiment.status must be one of {sorted(allowed_status)}")
            for field in ("result", "conclusion"):
                if not experiment.get(field):
                    errors.append(f"technical experiment requires {field}")
            if status != "not_run":
                for field in ("input", "success_condition"):
                    if not experiment.get(field):
                        errors.append(f"executed technical experiment requires {field}")
                method = experiment.get("method")
                if not isinstance(method, list) or not method:
                    errors.append("executed technical experiment requires non-empty method")
    elif experiment:
        errors.append(f"{content_profile} profile must not include experiment")

    visual_count, visual_ids = validate_visuals(bundle, artifact_ids, duration, errors, warnings)
    if content_profile != "technical" and bundle.get("experiment_figures"):
        errors.append(f"{content_profile} profile must not include experiment_figures")

    selected_visual_ids = summary.get("visual_ids", [])
    if selected_visual_ids and not isinstance(selected_visual_ids, list):
        errors.append("summary.visual_ids must be an array")
        selected_visual_ids = []
    missing_summary_visuals = sorted({str(item) for item in selected_visual_ids if str(item) not in visual_ids})
    if missing_summary_visuals:
        errors.append(f"summary.visual_ids reference missing visuals: {', '.join(missing_summary_visuals)}")

    content_items = bundle.get("content_items", [])
    source_item_count = bundle.get("source_item_count")
    if content_profile in {"catalog", "visual"}:
        if not isinstance(content_items, list) or not content_items:
            errors.append(f"{content_profile} profile requires non-empty content_items")
            content_items = []
        if not isinstance(source_item_count, int) or isinstance(source_item_count, bool) or source_item_count < 1:
            errors.append(f"{content_profile} profile requires positive integer source_item_count")
        elif source_item_count != len(content_items):
            errors.append(
                f"source_item_count ({source_item_count}) does not match content_items ({len(content_items)})"
            )
    elif content_items:
        errors.append(f"{content_profile} profile must not include content_items")
    elif source_item_count not in (None, 0):
        errors.append(f"{content_profile} profile must not include source_item_count")
    used_item_visuals: set[str] = set()
    if isinstance(content_items, list):
        for index, item in enumerate(content_items):
            prefix = f"content_items[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{prefix} must be an object")
                continue
            is_qa_catalog = content_profile == "catalog" and catalog_format == "qa"
            required_fields = ("question", "answer") if is_qa_catalog else ("name", "what")
            for field in required_fields:
                if not item.get(field):
                    errors.append(f"{prefix}.{field} is required")
            if content_profile == "catalog" and not is_qa_catalog and not item.get("why"):
                errors.append(f"{prefix}.why is required for catalog")
            visual_id = str(item.get("visual_id") or "")
            if content_profile == "visual" and not visual_id:
                errors.append(f"{prefix}.visual_id is required for visual")
            if visual_id:
                if visual_id not in visual_ids:
                    errors.append(f"{prefix}.visual_id is missing from visual collections: {visual_id}")
                if content_profile == "visual" and visual_id in used_item_visuals:
                    errors.append(f"visual items must use unique visual_id values: {visual_id}")
                used_item_visuals.add(visual_id)

    report = {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "counts": {
            "artifacts": len(artifacts),
            "claims": len(claims),
            "visuals": visual_count,
            "content_items": len(content_items) if isinstance(content_items, list) else 0,
        },
        "evidence": str(path),
    }
    dump_json(report)
    return 0 if not errors else 1


def ensure_inside(root: Path, candidate: Path, label: str) -> Path:
    resolved_root = root.expanduser().resolve()
    resolved = candidate.expanduser().resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(f"{label} must stay inside {resolved_root}: {resolved}") from exc
    return resolved


def note_visuals(note_path: Path, vault: Path | None) -> list[Path]:
    text = note_path.read_text(encoding="utf-8")
    if "{{" in text:
        raise ValueError("note contains unresolved template placeholders")
    if text.count("```mermaid") > text.count("```"):
        raise ValueError("note has an unclosed Mermaid fence")

    visuals: list[Path] = []
    for value in OBSIDIAN_EMBED_RE.findall(text):
        if vault is None:
            raise ValueError(f"cannot resolve Obsidian embed without a configured Vault: {value}")
        visuals.append(ensure_inside(vault, vault / value, "Obsidian embed"))
    for value in MARKDOWN_IMAGE_RE.findall(text):
        target = value.strip().strip("<>")
        if urlparse(target).scheme in {"http", "https", "data"}:
            continue
        visuals.append((note_path.parent / target).resolve())
    missing = [str(path) for path in visuals if not path.is_file()]
    if missing:
        raise ValueError(f"note references missing local visuals: {', '.join(missing)}")
    return list(dict.fromkeys(visuals))


def remove_path(path: Path) -> None:
    if path.is_symlink():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def finalize_job(args: argparse.Namespace) -> int:
    root = configured_workspace(args.workspace)
    manifest_path = ensure_inside(root / "jobs", Path(args.manifest), "manifest")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    paths = manifest.get("paths", {})
    job_id = str(manifest.get("job_id") or "")
    if not job_id:
        raise ValueError("manifest.job_id is required")

    expected_job = (root / "jobs" / job_id).resolve()
    job_dir = ensure_inside(root / "jobs", Path(paths.get("job_dir", expected_job)), "job_dir")
    if job_dir != expected_job:
        raise ValueError(f"manifest job_dir does not match job_id: {job_dir}")
    work_dir = ensure_inside(root / "_work", Path(paths.get("work_dir", root / "_work" / job_id)), "work_dir")
    sandbox_dir = ensure_inside(
        root / "sandbox", Path(paths.get("sandbox_dir", root / "sandbox" / job_id)), "sandbox_dir"
    )

    note_path = Path(args.note).expanduser().resolve()
    if not note_path.is_file():
        raise ValueError(f"note does not exist: {note_path}")
    config = load_config(required=False)
    vault_value = config.get("obsidian_vault")
    vault = Path(vault_value).expanduser().resolve() if vault_value else None
    if vault and vault.is_dir():
        try:
            note_path.relative_to(vault)
        except ValueError:
            vault = None
    visuals = note_visuals(note_path, vault)

    profile = args.content_profile
    source = manifest.get("source", {})
    if args.evidence:
        evidence_path = Path(args.evidence).expanduser().resolve()
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        profile = profile or evidence.get("content_profile")
        source = evidence.get("source") or source
    if profile not in CONTENT_PROFILES:
        raise ValueError(f"content_profile must be one of {sorted(CONTENT_PROFILES)}")

    deleted: list[str] = []
    for path in (work_dir, sandbox_dir):
        if path.exists():
            deleted.append(str(path))
            remove_path(path)
    if job_dir.exists():
        for child in job_dir.iterdir():
            if child.resolve() == manifest_path:
                continue
            deleted.append(str(child))
            remove_path(child)
    job_dir.mkdir(parents=True, exist_ok=True)
    compact = {
        "schema_version": 1,
        "job_id": job_id,
        "status": "complete",
        "completed_at": now_iso(),
        "content_profile": profile,
        "source": source,
        "note_path": str(note_path),
        "retained_visual_count": len(visuals),
    }
    dump_json(compact, manifest_path)
    dump_json(
        {
            "finalized": True,
            "manifest": str(manifest_path),
            "note": str(note_path),
            "content_profile": profile,
            "retained_visuals": len(visuals),
            "deleted": deleted,
            "shared_cache_preserved": True,
        }
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="initialize a source job")
    init_parser.add_argument("--url", required=True)
    init_parser.add_argument("--workspace", help="override the OS-local configured workspace")
    init_parser.add_argument(
        "--platform", choices=["bilibili", "wechat", "xiaohongshu", "web", "local"]
    )
    init_parser.add_argument("--title")
    init_parser.set_defaults(func=init_job)

    validate_parser = subparsers.add_parser("validate", help="validate an evidence bundle")
    validate_parser.add_argument("--evidence", required=True)
    validate_parser.set_defaults(func=validate_bundle)

    finalize_parser = subparsers.add_parser(
        "finalize", help="verify a rendered note, delete per-job intermediates, and compact the manifest"
    )
    finalize_parser.add_argument("--manifest", required=True)
    finalize_parser.add_argument("--note", required=True)
    finalize_parser.add_argument("--evidence")
    finalize_parser.add_argument("--content-profile", choices=sorted(CONTENT_PROFILES))
    finalize_parser.add_argument("--workspace", help="override the OS-local configured workspace")
    finalize_parser.set_defaults(func=finalize_job)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return args.func(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        dump_json({"ok": False, "error": str(exc)})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
