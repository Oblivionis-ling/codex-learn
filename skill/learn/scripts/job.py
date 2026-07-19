#!/usr/bin/env python3
"""Initialize Learn jobs and validate multimodal evidence bundles."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from learn_config import configured_workspace


PLATFORM_HOSTS = {
    "bilibili": ("bilibili.com", "b23.tv"),
    "wechat": ("mp.weixin.qq.com",),
    "xiaohongshu": ("xiaohongshu.com", "xhslink.com"),
}
VISUAL_COLLECTIONS = ("original_images", "keyframes", "experiment_figures", "attachments")
EVIDENCE_KINDS = {"source_fact", "interpretation", "external_fact", "recommendation"}
EVIDENCE_LEVELS = {"A", "B", "C", "D"}
VERIFICATION_STATES = {"verified", "partially_verified", "unverified", "contradicted"}


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
) -> int:
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
    return count


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
    if not isinstance(summary, dict) or not summary.get("one_sentence"):
        warnings.append("summary.one_sentence is missing")
        summary = summary if isinstance(summary, dict) else {}

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
    if experiment and not isinstance(experiment, dict):
        errors.append("experiment must be an object")
    elif experiment:
        allowed_status = {"planned", "running", "completed", "inconclusive", "failed", "not_run"}
        if experiment.get("status", "planned") not in allowed_status:
            errors.append("experiment.status is invalid")
        if experiment.get("status") == "completed" and not experiment.get("result"):
            warnings.append("completed experiment has no result summary")

    visual_count = validate_visuals(bundle, artifact_ids, duration, errors, warnings)
    report = {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "counts": {"artifacts": len(artifacts), "claims": len(claims), "visuals": visual_count},
        "evidence": str(path),
    }
    dump_json(report)
    return 0 if not errors else 1


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
