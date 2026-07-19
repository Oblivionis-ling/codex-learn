# Evidence schema

Use UTF-8 JSON with `schema_version: 1`. Keep the bundle in the job directory; it may contain runtime-local media paths and therefore should not be committed.

## Top-level fields

```json
{
  "schema_version": 1,
  "job_id": "platform-source-id",
  "status": "analyzed",
  "tags": [],
  "source": {},
  "artifacts": [],
  "summary": {},
  "summary_diagram": {},
  "claims": [],
  "experiment": {},
  "original_images": [],
  "keyframes": [],
  "experiment_figures": [],
  "attachments": [],
  "concepts": [],
  "edges": [],
  "limitations": []
}
```

## Source

Required:

```json
{
  "url": "https://example.invalid/source",
  "platform": "bilibili|wechat|xiaohongshu|web|local",
  "title": "Source title"
}
```

Optional source fields include `author`, `published_at`, `duration_seconds`, `description`, `retrieved_at`, and `acquisition_state`.

## Artifacts

Every artifact has a unique ID and a precise locator:

```json
{
  "id": "transcript-0042",
  "modality": "metadata|article|transcript|image|keyframe|ocr|external|experiment",
  "locator": "00:49-01:02",
  "text": "Raw extracted text",
  "description": "Visible or structural observation",
  "local_path": null,
  "confidence": 0.91,
  "include_in_note": true
}
```

Use `text` for extracted language and `description` for visual or structural observations. Do not overwrite raw ASR/OCR when correcting it; create a correction artifact that references the original. `include_in_note` forces a key excerpt into the rendered note.

## Summary and content structure

```json
{
  "summary": {
    "one_sentence": "One grounded conclusion",
    "key_points": ["Reusable point"],
    "timeline": [
      {
        "seconds": 49,
        "label": "Business model explanation",
        "evidence_refs": ["transcript-0042"]
      }
    ]
  },
  "summary_diagram": {
    "type": "mermaid",
    "code": "flowchart TD\n  A[Source] --> B[Idea]"
  }
}
```

`summary_diagram` is optional. When absent, the renderer creates a Mermaid structure diagram from `summary.key_points` or the timeline.

## Claims

```json
{
  "id": "claim-001",
  "statement": "A precise claim",
  "kind": "source_fact|interpretation|external_fact|recommendation",
  "evidence_refs": ["frame-0212", "transcript-0148"],
  "evidence_level": "A|B|C|D",
  "verification": "verified|partially_verified|unverified|contradicted",
  "missing_evidence": ""
}
```

Evidence levels:

- `A`: current primary or official evidence, or a directly reproducible result.
- `B`: clearly shown or stated in the source with cross-modal support.
- `C`: a single-source assertion, subjective experience, or plausible inference.
- `D`: missing result, unsupported prediction, or claim contradicted by available evidence.

Every A/B claim needs at least one valid `evidence_ref`. Profitability, audience response, platform policy, price, and eligibility claims need outcome data or current authoritative documentation.

## Minimal experiment

```json
{
  "status": "planned|running|completed|inconclusive|failed|not_run",
  "hypothesis": "Smallest risky assumption",
  "example": "Controlled example",
  "steps": ["Step 1"],
  "metrics": ["elapsed_minutes", "edit_minutes", "error_count"],
  "success_criteria": ["Measurable threshold"],
  "stop_criteria": ["Safety or cost boundary"],
  "result": "Grounded result summary",
  "observations": ["Raw observation"]
}
```

Use `completed` only after execution. A plan is not a result.

## Visuals and attachments

The four visual collections use the same base item:

```json
{
  "id": "frame-0049",
  "artifact_ref": "frame-artifact-0049",
  "local_path": "relative/or/absolute/file.png",
  "source_url": "https://example.invalid/optional-original.png",
  "caption": "What this image shows and why it matters",
  "locator": "Section 2, after paragraph 3",
  "timestamp_seconds": 49
}
```

- `original_images`: information-bearing source images in reading order.
- `keyframes`: selected video frames; include `timestamp_seconds`.
- `experiment_figures`: charts, screenshots, contact sheets, comparisons, or result diagrams created by the sandbox experiment.
- `attachments`: useful supporting files that are not part of the three visual groups.

Provide `local_path` whenever the image should be archived into Obsidian. `source_url` is a fallback embed and provenance link, not proof that the image was preserved locally. Each item requires a unique `id`, and should have a caption. Use `artifact_ref` to connect the visual to a normalized evidence artifact.

## Concepts and graph edges

```json
{
  "concepts": [
    {"name": "AI Agent", "aliases": ["智能体", "Agent"]}
  ],
  "edges": [
    {"from": "AI Agent", "relation": "管理", "to": "长文本项目"}
  ]
}
```

Normalize aliases before creating a new Obsidian concept node. Render the relationship graph when there are at least three meaningful edges.
