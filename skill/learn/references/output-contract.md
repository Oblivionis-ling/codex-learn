# Output contract

Return a concise conversational result and one compact Obsidian note.

## Conversational result

Lead with:

1. inferred `content_profile` and acquisition completeness;
2. the useful conclusion;
3. technical validation result when the profile is `technical`;
4. note path, retained visual count, and cleanup status.

Do not repeat the full note, evidence audit, missing-claim inventory, or transcript details in chat.

## Common note shell

Use `assets/obsidian-note-template.md` with:

- compact YAML frontmatter: title, source, platform, author, publication/retrieval dates, profile, and tags;
- a profile-specific body;
- optional compact `[[wikilinks]]` or a relationship graph only when useful;
- the original source URL.

Use this filename pattern:

```text
<sanitized-title>_学习笔记_YYYYMMDD.md
```

Do not label generated files `最终版`.

## Profile bodies

### `technical`

- `## 技术是什么`: `summary.overview`.
- `## 怎么操作`: ordered `summary.procedure`.
- optional explicitly supplied structure diagram when it clarifies a multi-step system.
- optional selected source diagrams/screenshots from `summary.visual_ids`.
- `## 可行性验证`: actual experiment status, input, success condition, result, elapsed time, errors, and conclusion.
- experiment figures only when they clarify the result.

### `overview`

- `## 全文总结`: `summary.overview`.
- `## 要点`: concise `summary.key_points` when non-empty.
- optional selected visual from `summary.visual_ids` only when irreplaceable.

### `catalog`

- `## 简短总览`: `summary.overview`.
- `## 完整清单`: every `content_item` in source order.
- each item uses a level-three heading and explains `是什么` and `为什么`; add `补充` only when `notes` is useful.
- embed an item's image only when it has `visual_id`.

### `visual`

- `## 简单总结`: `summary.overview`.
- `## 逐项展示`: every `content_item` in source order.
- each item uses a level-three heading, embeds its unique `visual_id`, and gives a short description; add `搭配逻辑/效果` only when `why` is present.

## Sections that must not render

Never render these as note sections:

- original text excerpts;
- source evidence blocks or evidence IDs;
- claim/evidence tables or verification levels;
- limitations or missing-evidence lists;
- timestamped transcript/timeline;
- planned experiments for non-technical content;
- generic attachment appendices;
- raw ASR, OCR, or acquisition logs.

## Attachment policy

- Copy only visual IDs referenced by `summary.visual_ids`, `content_items[].visual_id`, or technical experiment figures.
- Do not display timestamps, locators, evidence IDs, or machine-local paths in captions.
- Do not copy transcript files, audio, video, JSON, contact sheets, or unused candidate frames.
- When a Vault is configured, copy selected visuals into its configured attachment folder under a job-specific `Learn` subfolder and use Obsidian embeds.
- Never embed a nonexistent local file. An external image URL is an explicit fallback, not proof of local archival.
- After rendering, run `job.py finalize` so attachment verification happens before per-job transcripts, evidence, candidate frames, and sandbox files are removed.

## Quality gates

- Do not summarize inaccessible body content from a title or snippet.
- `catalog`: `source_item_count`, `content_items`, and rendered item counts must all match.
- `visual`: `source_item_count`, `content_items`, and rendered item counts must all match; every item must render exactly one unique image. Use one combined comparison image for a before/after pair.
- `technical`: do not claim feasibility without an actual result or a concrete authoritative check explaining why local execution was impossible.
- Verify every copied visual exists, every placeholder is resolved, optional Mermaid fences are balanced, and no machine-local path appears in note prose or frontmatter.
