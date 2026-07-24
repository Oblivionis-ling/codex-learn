# Compact render bundle schema

Use UTF-8 JSON with `schema_version: 1`. Keep it only until the final note and selected visuals pass verification, then delete it unless the user explicitly asks to retain working evidence.

## Top-level shape

```json
{
  "schema_version": 1,
  "job_id": "platform-source-id",
  "status": "analyzed",
  "content_profile": "technical|overview|catalog|visual",
  "tags": [],
  "source": {},
  "summary": {},
  "source_item_count": 0,
  "content_items": [],
  "experiment": {},
  "original_images": [],
  "keyframes": [],
  "experiment_figures": [],
  "concepts": [],
  "edges": [],
  "artifacts": [],
  "claims": []
}
```

`artifacts` and `claims` are optional transient acquisition aids. The renderer never writes them into the note. Do not populate them when a compact summary can be grounded directly from the acquired source.

## Source

Required:

```json
{
  "url": "https://example.invalid/source",
  "platform": "bilibili|wechat|xiaohongshu|web|local",
  "title": "Source title"
}
```

Optional fields: `author`, `published_at`, `retrieved_at`, `duration_seconds`, and `acquisition_state`.

## Summary

Common fields:

```json
{
  "one_sentence": "Concise conclusion",
  "overview": "Compact whole-source synthesis",
  "key_points": ["Only useful takeaways"],
  "procedure": ["Executable technical step"],
  "visual_ids": ["optional-selected-visual"]
}
```

- `overview` is required for every profile.
- `procedure` is required and non-empty only for `technical`.
- `key_points` is mainly for `overview`; omit it when it repeats the overview.
- `visual_ids` is optional and must reference selected items from the visual collections.

An optional `summary_diagram` may contain Mermaid code. Supply it only when the diagram improves technical or conceptual understanding; the renderer does not auto-generate one.

## Content items

`source_item_count` and `content_items` are required for `catalog` and `visual`, and omitted otherwise. The item count must match the number of variants or list entries identified in the source.

Each item uses:

```json
{
  "name": "Recognizable item name",
  "what": "What it is, contains, or looks like",
  "why": "Why it is useful, recommended, or visually effective",
  "notes": "Optional concrete selection or usage note",
  "visual_id": "required-for-visual; optional-for-catalog"
}
```

- Preserve source order.
- `catalog` requires `name`, `what`, and `why` for every item.
- `visual` requires `name`, `what`, and a unique valid `visual_id`; `why` is optional.
- Do not shorten a source's numbered list by silently dropping items.

## Technical experiment

Use only when `content_profile` is `technical`:

```json
{
  "status": "completed|inconclusive|failed|not_run",
  "input": "Concrete test input",
  "success_condition": "Observable pass condition",
  "method": ["Executed step"],
  "result": "Observed result",
  "elapsed_seconds": 12.3,
  "errors": [],
  "conclusion": "What the result establishes"
}
```

Use `not_run` only when local execution is unsafe or impossible; include the authoritative check performed and the concrete reason in `result` and `conclusion`. Do not add `experiment` for other profiles.

## Visual collections

`original_images`, `keyframes`, and `experiment_figures` use this base shape:

```json
{
  "id": "visual-001",
  "local_path": "relative/or/absolute/file.png",
  "source_url": "https://example.invalid/optional-original.png",
  "caption": "Short reader-facing caption",
  "timestamp_seconds": 49
}
```

- Provide `local_path` for a visual that must be archived locally; `source_url` is a fallback.
- Keep timestamp and locator internally when useful for acquisition, but the note caption does not display them.
- `experiment_figures` are valid only for `technical`.
- A visual is copied only when referenced by `summary.visual_ids`, `content_items[].visual_id`, or the technical experiment figure collection.

## Optional knowledge links

```json
{
  "concepts": [{"name": "AI Agent", "aliases": ["智能体"]}],
  "edges": [{"from": "AI Agent", "relation": "管理", "to": "长文本项目"}]
}
```

Use only meaningful reusable concepts. Render a relationship graph only when at least three non-trivial edges exist.

## Transient evidence rules

When extraction needs raw ASR/OCR or claim checks, `artifacts` may carry IDs, modalities, locators, text, and confidence, and `claims` may reference those IDs. Validate references before synthesis. Never set them as note sections, never copy them as attachments, and delete the bundle and transcripts after final verification by default.
