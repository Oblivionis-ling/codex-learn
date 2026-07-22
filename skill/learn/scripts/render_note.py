#!/usr/bin/env python3
"""Render a compact profile-specific Obsidian note from a Learn bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from learn_config import absolute_path, load_config, obsidian_attachment_folder


IMAGE_SUFFIXES = {".avif", ".bmp", ".gif", ".jpeg", ".jpg", ".png", ".svg", ".webp"}
CONTENT_PROFILES = {"technical", "overview", "catalog", "visual"}
VISUAL_COLLECTIONS = ("original_images", "keyframes", "experiment_figures")


def yaml_string(value: object) -> str:
    return str(value or "").replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def bullets(items: list[object], empty: str = "") -> str:
    return "\n".join(f"- {item}" for item in items if str(item).strip()) or empty


def numbered(items: list[object], empty: str = "") -> str:
    values = [item for item in items if str(item).strip()]
    return "\n".join(f"{index}. {item}" for index, item in enumerate(values, 1)) or empty


def format_duration(seconds: float) -> str:
    value = max(0.0, float(seconds))
    if value < 60:
        return f"{value:.1f} 秒"
    total = int(round(value))
    hours, remainder = divmod(total, 3600)
    minutes, seconds_part = divmod(remainder, 60)
    if hours:
        return f"{hours} 小时 {minutes} 分 {seconds_part} 秒"
    return f"{minutes} 分 {seconds_part} 秒"


def safe_filename(value: str, fallback: str = "untitled", limit: int = 90) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", value).strip(" ._")
    return (name or fallback)[:limit]


def mermaid_label(value: object, limit: int = 72) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    text = text.replace('"', "'").replace("|", "／").replace("`", "'")
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def summary_diagram_markdown(bundle: dict[str, Any]) -> str:
    provided = bundle.get("summary_diagram")
    if not isinstance(provided, dict) or provided.get("type", "mermaid") != "mermaid":
        return ""
    code = str(provided.get("code") or "").replace("```", "").strip()
    return f"```mermaid\n{code}\n```" if code else ""


def knowledge_section_markdown(bundle: dict[str, Any]) -> str:
    concepts = bundle.get("concepts", [])
    names = [
        str(item.get("name"))
        for item in concepts
        if isinstance(item, dict) and item.get("name")
    ]
    edges = [edge for edge in bundle.get("edges", []) if isinstance(edge, dict)]
    if not names and len(edges) < 3:
        return ""

    parts = ["## 相关知识"]
    if names:
        parts.append(bullets([f"[[{name}]]" for name in names]))
    if len(edges) >= 3:
        nodes: dict[str, str] = {}
        lines = ["```mermaid", "graph LR"]
        for edge in edges:
            for value in (str(edge.get("from", "")), str(edge.get("to", ""))):
                if value and value not in nodes:
                    nodes[value] = f"N{len(nodes) + 1}"
        for value, node_id in nodes.items():
            lines.append(f'    {node_id}["{mermaid_label(value)}"]')
        for edge in edges:
            left = str(edge.get("from", ""))
            right = str(edge.get("to", ""))
            relation = mermaid_label(edge.get("relation", "关联"), 32)
            if left in nodes and right in nodes:
                lines.append(f'    {nodes[left]} -->|"{relation}"| {nodes[right]}')
        lines.append("```")
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


def resolve_source_file(value: str, evidence_dir: Path) -> Path:
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (evidence_dir / path).resolve()


class AttachmentWriter:
    def __init__(self, output_path: Path, vault: Path | None, attachment_folder: str, job_id: str):
        self.output_path = output_path
        self.vault = vault
        self.warnings: list[str] = []
        self.copied: list[str] = []
        self.embedded_ids: list[str] = []
        self.created: list[Path] = []
        safe_job = safe_filename(job_id, "job", 64)
        if vault:
            root = vault if attachment_folder in {"", "."} else vault / attachment_folder
            self.destination = (root / "Learn" / safe_job).resolve()
            self.destination.relative_to(vault)
            self.wiki_root = self.destination.relative_to(vault).as_posix()
            self.mode = "wiki"
        else:
            self.destination = output_path.parent / f"{output_path.stem}_assets"
            self.wiki_root = self.destination.name
            self.mode = "markdown"

    def copy_and_embed(self, item: dict[str, Any], evidence_dir: Path) -> str:
        visual_id = str(item.get("id") or "")
        caption = str(item.get("caption") or visual_id or "配图")
        local_value = item.get("local_path")
        source_url = item.get("source_url")
        embed = ""
        if local_value:
            source = resolve_source_file(str(local_value), evidence_dir)
            if source.is_file():
                digest = hashlib.sha256(source.read_bytes()).hexdigest()[:10]
                suffix = source.suffix.lower()
                if suffix not in IMAGE_SUFFIXES:
                    raise ValueError(f"Referenced visual is not an image: {source}")
                target_name = f"{safe_filename(source.stem, 'visual', 70)}-{digest}{suffix}"
                self.destination.mkdir(parents=True, exist_ok=True)
                target = self.destination / target_name
                if not target.exists():
                    shutil.copy2(source, target)
                    self.created.append(target)
                target_text = str(target)
                if target_text not in self.copied:
                    self.copied.append(target_text)
                relative = f"{self.wiki_root}/{target_name}"
                if self.mode == "wiki":
                    embed = f"![[{relative}]]"
                else:
                    embed = f"![{caption}]({relative})"
            else:
                self.warnings.append(f"本地配图不存在，尝试外链回退：{source}")
        if not embed and source_url:
            embed = f"![{caption}]({source_url})"
        if not embed:
            raise ValueError(f"Referenced visual cannot be rendered: {visual_id or caption}")
        if visual_id and visual_id not in self.embedded_ids:
            self.embedded_ids.append(visual_id)
        return f"{embed}\n\n*{caption}*"

    def rollback(self) -> None:
        for path in reversed(self.created):
            path.unlink(missing_ok=True)
        if self.destination.is_dir() and not any(self.destination.iterdir()):
            self.destination.rmdir()


def visual_index(bundle: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for collection in VISUAL_COLLECTIONS:
        for item in bundle.get(collection, []):
            if not isinstance(item, dict) or not item.get("id"):
                continue
            visual_id = str(item["id"])
            if visual_id in result:
                raise ValueError(f"Duplicate visual id: {visual_id}")
            result[visual_id] = item
    return result


def render_visual_ids(
    ids: object,
    visuals: dict[str, dict[str, Any]],
    writer: AttachmentWriter,
    evidence_dir: Path,
) -> str:
    if not isinstance(ids, list):
        return ""
    rendered: list[str] = []
    for value in ids:
        visual_id = str(value)
        item = visuals.get(visual_id)
        if item is None:
            raise ValueError(f"Unknown visual_id: {visual_id}")
        rendered.append(writer.copy_and_embed(item, evidence_dir))
    return "\n\n".join(rendered)


def experiment_markdown(experiment: object) -> str:
    if not isinstance(experiment, dict) or not experiment:
        raise ValueError("technical profile requires an experiment result")
    parts = [f"**状态：** `{experiment.get('status', '')}`"]
    if experiment.get("input"):
        parts.append(f"**测试输入：** {experiment['input']}")
    if experiment.get("success_condition"):
        parts.append(f"**成功条件：** {experiment['success_condition']}")
    if experiment.get("method"):
        parts.append("**实际步骤：**\n\n" + numbered(experiment["method"]))
    if experiment.get("result"):
        parts.append(f"**实际结果：** {experiment['result']}")
    if isinstance(experiment.get("elapsed_seconds"), (int, float)):
        parts.append(f"**耗时：** {format_duration(float(experiment['elapsed_seconds']))}")
    errors = experiment.get("errors")
    if isinstance(errors, list) and errors:
        parts.append("**错误或修正：**\n\n" + bullets(errors))
    if experiment.get("conclusion"):
        parts.append(f"**结论：** {experiment['conclusion']}")
    return "\n\n".join(parts)


def item_text(item: dict[str, Any], visual_profile: bool) -> str:
    parts: list[str] = []
    if item.get("what"):
        label = "组成/特点" if visual_profile else "是什么"
        parts.append(f"**{label}：** {item['what']}")
    if item.get("why"):
        label = "搭配逻辑/效果" if visual_profile else "为什么"
        parts.append(f"**{label}：** {item['why']}")
    if item.get("notes"):
        parts.append(f"**补充：** {item['notes']}")
    return "\n\n".join(parts)


def content_body_markdown(
    bundle: dict[str, Any],
    writer: AttachmentWriter,
    evidence_dir: Path,
) -> str:
    profile = str(bundle.get("content_profile") or "")
    if profile not in CONTENT_PROFILES:
        raise ValueError(f"Invalid or missing content_profile: {profile or '<missing>'}")
    summary = bundle.get("summary", {})
    if not isinstance(summary, dict):
        raise ValueError("summary must be an object")
    overview = str(summary.get("overview") or summary.get("one_sentence") or "").strip()
    if not overview:
        raise ValueError("summary.overview is required")
    visuals = visual_index(bundle)

    if profile == "technical":
        procedure = summary.get("procedure", [])
        if not isinstance(procedure, list) or not procedure:
            raise ValueError("technical profile requires summary.procedure")
        parts = ["## 技术是什么", overview]
        diagram = summary_diagram_markdown(bundle)
        if diagram:
            parts.extend(["### 结构图", diagram])
        selected = render_visual_ids(summary.get("visual_ids", []), visuals, writer, evidence_dir)
        if selected:
            parts.extend(["### 操作示意", selected])
        parts.extend(["## 怎么操作", numbered(procedure), "## 可行性验证", experiment_markdown(bundle.get("experiment"))])
        figures = [
            str(item.get("id"))
            for item in bundle.get("experiment_figures", [])
            if isinstance(item, dict) and item.get("id")
        ]
        rendered_figures = render_visual_ids(figures, visuals, writer, evidence_dir)
        if rendered_figures:
            parts.extend(["### 实验图", rendered_figures])
        return "\n\n".join(parts)

    if bundle.get("experiment"):
        raise ValueError(f"{profile} profile must not include an experiment")
    if bundle.get("experiment_figures"):
        raise ValueError(f"{profile} profile must not include experiment figures")

    if profile == "overview":
        parts = ["## 全文总结", overview]
        key_points = summary.get("key_points", [])
        if isinstance(key_points, list) and key_points:
            parts.extend(["## 要点", bullets(key_points)])
        selected = render_visual_ids(summary.get("visual_ids", []), visuals, writer, evidence_dir)
        if selected:
            parts.extend(["## 配图", selected])
        return "\n\n".join(parts)

    items = bundle.get("content_items", [])
    if not isinstance(items, list) or not items:
        raise ValueError(f"{profile} profile requires content_items")
    heading = "## 完整清单" if profile == "catalog" else "## 逐项展示"
    intro = "## 简短总览" if profile == "catalog" else "## 简单总结"
    parts = [intro, overview, heading]
    used_visuals: set[str] = set()
    for index, item in enumerate(items, 1):
        if not isinstance(item, dict):
            raise ValueError(f"content_items[{index - 1}] must be an object")
        name = str(item.get("name") or "").strip()
        if not name:
            raise ValueError(f"content_items[{index - 1}].name is required")
        entry = [f"### {index}. {name}"]
        visual_id = str(item.get("visual_id") or "")
        if profile == "visual":
            if not visual_id:
                raise ValueError(f"visual item requires visual_id: {name}")
            if visual_id in used_visuals:
                raise ValueError(f"visual_id must be unique per item: {visual_id}")
            used_visuals.add(visual_id)
        if visual_id:
            entry.append(render_visual_ids([visual_id], visuals, writer, evidence_dir))
        details = item_text(item, profile == "visual")
        if details:
            entry.append(details)
        parts.append("\n\n".join(entry))
    return "\n\n".join(parts)


def destination(args: argparse.Namespace, bundle: dict[str, Any], evidence_path: Path) -> tuple[Path, Path | None, str]:
    config = load_config(required=False)
    vault = absolute_path(args.vault) if args.vault else None
    if vault is None and config.get("obsidian_vault"):
        vault = absolute_path(config["obsidian_vault"])

    source = bundle.get("source", {})
    title = safe_filename(str(source.get("title", "未命名来源")), "未命名来源")
    filename = f"{title}_学习笔记_{datetime.now().strftime('%Y%m%d')}.md"
    if args.output:
        output_path = absolute_path(args.output)
    elif vault:
        notes_subdir = args.notes_subdir or config.get("notes_subdir") or "Learn"
        output_path = (vault / str(notes_subdir) / filename).resolve()
        output_path.relative_to(vault)
    elif config.get("workspace_root"):
        output_path = absolute_path(config["workspace_root"]) / "output" / filename
    else:
        output_path = evidence_path.parent / filename

    attachment_folder = args.attachments or config.get("attachment_folder")
    if not attachment_folder and vault:
        attachment_folder = obsidian_attachment_folder(vault)
    return output_path.resolve(), vault, str(attachment_folder or "Attachments")


def render(args: argparse.Namespace) -> int:
    evidence_path = absolute_path(args.evidence)
    bundle = json.loads(evidence_path.read_text(encoding="utf-8"))
    template_path = (
        absolute_path(args.template)
        if args.template
        else Path(__file__).resolve().parent.parent / "assets" / "obsidian-note-template.md"
    )
    template = template_path.read_text(encoding="utf-8")
    output_path, vault, attachment_folder = destination(args, bundle, evidence_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    source = bundle.get("source", {})
    profile = str(bundle.get("content_profile") or "")
    writer = AttachmentWriter(output_path, vault, attachment_folder, str(bundle.get("job_id", "job")))
    try:
        values = {
            "title": yaml_string(source.get("title", "未命名来源")),
            "source_url": yaml_string(source.get("url", "")),
            "platform": yaml_string(source.get("platform", "")),
            "author": yaml_string(source.get("author", "")),
            "published_at": yaml_string(source.get("published_at", "")),
            "retrieved_at": yaml_string(
                source.get("retrieved_at") or datetime.now(timezone.utc).date().isoformat()
            ),
            "content_profile": yaml_string(profile),
            "tags": json.dumps(bundle.get("tags", []), ensure_ascii=False),
            "content_body": content_body_markdown(bundle, writer, evidence_path.parent),
            "knowledge_section": knowledge_section_markdown(bundle),
        }
        note = template
        for key, value in values.items():
            note = note.replace("{{" + key + "}}", str(value))

        unresolved = sorted(set(re.findall(r"\{\{[a-zA-Z0-9_]+\}\}", note)))
        if unresolved:
            raise ValueError(f"Unresolved template placeholders: {', '.join(unresolved)}")
        note = re.sub(r"\n{3,}", "\n\n", note).rstrip() + "\n"
        output_path.write_text(note, encoding="utf-8")
    except Exception:
        writer.rollback()
        raise
    print(
        json.dumps(
            {
                "output": str(output_path),
                "vault": str(vault) if vault else None,
                "content_profile": profile,
                "attachments": writer.copied,
                "retained_visuals": len(writer.embedded_ids),
                "warnings": writer.warnings,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--output")
    parser.add_argument("--template")
    parser.add_argument("--vault")
    parser.add_argument("--notes-subdir")
    parser.add_argument("--attachments")
    try:
        return render(parser.parse_args())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
