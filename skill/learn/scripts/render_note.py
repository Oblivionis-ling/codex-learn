#!/usr/bin/env python3
"""Render an illustrated Obsidian note from a validated Learn evidence bundle."""

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


def yaml_string(value: object) -> str:
    return str(value or "").replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def escape_table(value: object) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", "<br>")


def bullets(items: list[object], empty: str = "- 暂无") -> str:
    return "\n".join(f"- {item}" for item in items) if items else empty


def numbered(items: list[object], empty: str = "- 暂无") -> str:
    return "\n".join(f"{index}. {item}" for index, item in enumerate(items, 1)) if items else empty


def format_time(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, seconds_part = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds_part:02d}" if hours else f"{minutes:02d}:{seconds_part:02d}"


def timestamp_link(bundle: dict, seconds: float) -> str:
    source = bundle.get("source", {})
    url = source.get("url", "")
    stamp = format_time(seconds)
    if source.get("platform") == "bilibili" and url:
        separator = "&" if "?" in url else "?"
        return f"[{stamp}]({url}{separator}t={int(seconds)})"
    return stamp


def timeline_markdown(bundle: dict) -> str:
    timeline = bundle.get("summary", {}).get("timeline", [])
    rows: list[str] = []
    for item in timeline:
        if not isinstance(item, dict):
            continue
        label = item.get("label", "")
        seconds = item.get("seconds")
        if isinstance(seconds, (int, float)):
            rows.append(f"- {timestamp_link(bundle, seconds)}：{label}")
        elif item.get("locator"):
            rows.append(f"- {item['locator']}：{label}")
        elif label:
            rows.append(f"- {label}")
    return "\n".join(rows) if rows else "- 本来源未提供可用的时间轴或文章结构。"


def source_excerpts_markdown(bundle: dict) -> str:
    referenced: set[str] = set()
    for claim in bundle.get("claims", []):
        if isinstance(claim, dict):
            referenced.update(str(item) for item in claim.get("evidence_refs", []))
    for item in bundle.get("summary", {}).get("timeline", []):
        if isinstance(item, dict):
            referenced.update(str(ref) for ref in item.get("evidence_refs", []))

    rows: list[str] = []
    for artifact in bundle.get("artifacts", []):
        if not isinstance(artifact, dict) or not artifact.get("text"):
            continue
        if referenced and artifact.get("id") not in referenced and not artifact.get("include_in_note"):
            continue
        text = str(artifact["text"]).strip()
        if len(text) > 800:
            text = text[:797].rstrip() + "…"
        quoted = "\n".join(f"> {line}" if line else ">" for line in text.splitlines())
        locator = artifact.get("locator", "位置未知")
        modality = artifact.get("modality", "evidence")
        rows.append(f"{quoted}\n>\n> — `{artifact.get('id', '')}` · {modality} · {locator}")
        if len(rows) >= 12:
            break
    return "\n\n".join(rows) if rows else "- 没有选入笔记的原文摘录；详见结构化证据文件。"


def claims_markdown(bundle: dict) -> str:
    rows = [
        "| 主张 | 类型 | 证据等级 | 验证状态 | 证据定位 | 缺失证据 |",
        "|---|---|---:|---|---|---|",
    ]
    for claim in bundle.get("claims", []):
        if not isinstance(claim, dict):
            continue
        values = [
            claim.get("statement", ""),
            claim.get("kind", ""),
            claim.get("evidence_level", ""),
            claim.get("verification", ""),
            ", ".join(str(ref) for ref in claim.get("evidence_refs", [])),
            claim.get("missing_evidence", ""),
        ]
        rows.append("| " + " | ".join(escape_table(value) for value in values) + " |")
    return "\n".join(rows) if len(rows) > 2 else "- 暂无可评估主张。"


def experiment_markdown(bundle: dict) -> str:
    experiment = bundle.get("experiment", {})
    if not experiment:
        return "- 尚未设计验证实验。"
    sections = [
        f"**状态：** `{experiment.get('status', 'planned')}`",
        f"\n**假设：** {experiment.get('hypothesis', '')}",
    ]
    if experiment.get("example"):
        sections.append(f"\n**受控示例：** {experiment['example']}")
    if experiment.get("steps"):
        sections.append("\n**步骤：**\n\n" + numbered(experiment["steps"]))
    if experiment.get("metrics"):
        sections.append("\n**指标：**\n\n" + bullets(experiment["metrics"]))
    if experiment.get("success_criteria"):
        sections.append("\n**成功标准：**\n\n" + bullets(experiment["success_criteria"]))
    if experiment.get("stop_criteria"):
        sections.append("\n**停止标准：**\n\n" + bullets(experiment["stop_criteria"]))
    if experiment.get("result"):
        sections.append(f"\n**实验结果：** {experiment['result']}")
    if experiment.get("observations"):
        sections.append("\n**观察记录：**\n\n" + bullets(experiment["observations"]))
    return "\n".join(sections)


def mermaid_label(value: object, limit: int = 72) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    text = text.replace('"', "'").replace("|", "／").replace("`", "'")
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text


def summary_diagram_markdown(bundle: dict) -> str:
    provided = bundle.get("summary_diagram")
    if isinstance(provided, dict) and provided.get("type", "mermaid") == "mermaid" and provided.get("code"):
        code = str(provided["code"]).replace("```", "").strip()
        return f"```mermaid\n{code}\n```"

    source = bundle.get("source", {})
    summary = bundle.get("summary", {})
    items = [str(item) for item in summary.get("key_points", []) if str(item).strip()]
    if not items:
        items = [
            str(item.get("label"))
            for item in summary.get("timeline", [])
            if isinstance(item, dict) and item.get("label")
        ]
    if not items:
        return "- 当前证据不足，尚未生成内容结构图。"

    lines = ["```mermaid", "flowchart TD", f'    ROOT["{mermaid_label(source.get("title", "来源"))}"]']
    for index, item in enumerate(items[:8], 1):
        lines.append(f'    ROOT --> K{index}["{mermaid_label(item)}"]')
    lines.append("```")
    return "\n".join(lines)


def graph_markdown(bundle: dict) -> tuple[str, str]:
    concepts = bundle.get("concepts", [])
    names = [item.get("name") for item in concepts if isinstance(item, dict) and item.get("name")]
    wikilinks = bullets([f"[[{name}]]" for name in names], "- 暂无规范化概念节点。")
    edges = [edge for edge in bundle.get("edges", []) if isinstance(edge, dict)]
    if len(edges) < 3:
        return wikilinks, "- 关系少于三条，本次不额外绘制知识关系图。"

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
    return wikilinks, "\n".join(lines)


def safe_filename(value: str, fallback: str = "untitled", limit: int = 90) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", value).strip(" ._")
    return (name or fallback)[:limit]


def resolve_source_file(value: str, evidence_dir: Path) -> Path:
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (evidence_dir / path).resolve()


class AttachmentWriter:
    def __init__(self, output_path: Path, vault: Path | None, attachment_folder: str, job_id: str):
        self.output_path = output_path
        self.vault = vault
        self.warnings: list[str] = []
        self.copied: list[str] = []
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

    def copy_and_embed(self, item: dict, evidence_dir: Path, visual: bool = True) -> str:
        caption = str(item.get("caption") or item.get("description") or item.get("id") or "附件")
        local_value = item.get("local_path")
        source_url = item.get("source_url")
        embed = ""
        if local_value:
            source = resolve_source_file(str(local_value), evidence_dir)
            if source.is_file():
                digest = hashlib.sha256(source.read_bytes()).hexdigest()[:10]
                suffix = source.suffix.lower()
                target_name = f"{safe_filename(source.stem, 'attachment', 70)}-{digest}{suffix}"
                self.destination.mkdir(parents=True, exist_ok=True)
                target = self.destination / target_name
                if not target.exists():
                    shutil.copy2(source, target)
                self.copied.append(str(target))
                relative = f"{self.wiki_root}/{target_name}"
                if self.mode == "wiki":
                    embed = f"![[{relative}]]" if visual or suffix in IMAGE_SUFFIXES else f"[[{relative}|{caption}]]"
                else:
                    embed = f"![{caption}]({relative})" if visual or suffix in IMAGE_SUFFIXES else f"[{caption}]({relative})"
            else:
                self.warnings.append(f"附件文件不存在：{source}")
        if not embed and source_url:
            embed = f"![{caption}]({source_url})" if visual else f"[{caption}]({source_url})"
        if not embed:
            return f"- ⚠️ 未归档附件：{caption}"

        details: list[str] = []
        if item.get("locator"):
            details.append(str(item["locator"]))
        if isinstance(item.get("timestamp_seconds"), (int, float)):
            details.append(format_time(item["timestamp_seconds"]))
        evidence_ref = item.get("artifact_ref")
        if evidence_ref:
            details.append(f"证据 `{evidence_ref}`")
        suffix_text = f"（{' · '.join(details)}）" if details else ""
        return f"{embed}\n\n*{caption}{suffix_text}*"


def media_markdown(items: object, writer: AttachmentWriter, evidence_dir: Path, visual: bool = True) -> str:
    if not isinstance(items, list) or not items:
        return "- 暂无。"
    rendered = [
        writer.copy_and_embed(item, evidence_dir, visual)
        for item in items
        if isinstance(item, dict)
    ]
    return "\n\n".join(rendered) if rendered else "- 暂无。"


def destination(args: argparse.Namespace, bundle: dict, evidence_path: Path) -> tuple[Path, Path | None, str]:
    config = load_config(required=False)
    vault = absolute_path(args.vault) if args.vault else None
    if vault is None and config.get("obsidian_vault"):
        vault = absolute_path(config["obsidian_vault"])

    source = bundle.get("source", {})
    title = safe_filename(str(source.get("title", "未命名来源")), "未命名来源")
    filename = f"{title}_来源笔记_{datetime.now().strftime('%Y%m%d')}.md"
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
    summary = bundle.get("summary", {})
    writer = AttachmentWriter(output_path, vault, attachment_folder, str(bundle.get("job_id", "job")))
    wikilinks, knowledge_graph = graph_markdown(bundle)
    values = {
        "title": yaml_string(source.get("title", "未命名来源")),
        "source_url": source.get("url", ""),
        "platform": source.get("platform", ""),
        "author": yaml_string(source.get("author", "")),
        "published_at": source.get("published_at", ""),
        "retrieved_at": source.get("retrieved_at") or datetime.now(timezone.utc).date().isoformat(),
        "status": bundle.get("status", "analyzed"),
        "tags": json.dumps(bundle.get("tags", []), ensure_ascii=False),
        "one_sentence": summary.get("one_sentence", ""),
        "timeline": timeline_markdown(bundle),
        "source_excerpts": source_excerpts_markdown(bundle),
        "original_images": media_markdown(bundle.get("original_images"), writer, evidence_path.parent),
        "keyframes": media_markdown(bundle.get("keyframes"), writer, evidence_path.parent),
        "summary_diagram": summary_diagram_markdown(bundle),
        "key_points": bullets(summary.get("key_points", [])),
        "claims_table": claims_markdown(bundle),
        "experiment": experiment_markdown(bundle),
        "experiment_figures": media_markdown(
            bundle.get("experiment_figures"), writer, evidence_path.parent
        ),
        "other_attachments": media_markdown(
            bundle.get("attachments"), writer, evidence_path.parent, visual=False
        ),
        "limitations": bullets(bundle.get("limitations", [])),
        "wikilinks": wikilinks,
        "knowledge_graph": knowledge_graph,
    }
    note = template
    for key, value in values.items():
        note = note.replace("{{" + key + "}}", str(value))

    unresolved = sorted(set(re.findall(r"\{\{[a-zA-Z0-9_]+\}\}", note)))
    if unresolved:
        raise ValueError(f"Unresolved template placeholders: {', '.join(unresolved)}")
    output_path.write_text(note.rstrip() + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output_path),
                "vault": str(vault) if vault else None,
                "attachments": writer.copied,
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
