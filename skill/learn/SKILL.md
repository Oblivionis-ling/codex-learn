---
name: learn
description: "Turn public articles, image posts, audio or video links, and local multimodal files into compact, practical Obsidian notes whose structure adapts to the content: explain what a technology is, how to use it, and whether it works; briefly summarize general knowledge; enumerate every item in recommendation lists with what it is and why it matters; and pair every variant in visual showcases such as outfits with one representative source image. Run a minimal sandbox validation only for technical content, archive only visuals used by the final note, and discard transcripts and intermediate evidence by default. Use when the user invokes $learn with a link or file, or asks to learn from or archive web, WeChat, Xiaohongshu, Bilibili, video, audio, screenshots, or attachments."
---

# Learn

Turn one source into a concise, useful Obsidian note. Acquire enough of every material modality to understand the source, then keep only the final note and the visuals it actually uses.

## Invocation contract

Accept the shortest form directly:

```text
$learn <link-or-local-file>
```

Do not ask the user to choose a template. Infer the platform and content profile, process the necessary modalities, write the note, verify it, and return the conclusion and output path.

## Runtime readiness

Run `scripts/bootstrap.py status --json` with the Python selected by the active workspace instructions. Run `provision` only when `provision_current` is false.

If no local configuration exists:

1. Ask only for a dedicated runtime workspace and an Obsidian Vault if they were not already supplied.
2. Run `scripts/bootstrap.py configure --workspace <path> --vault <path>`. Optionally supply `--notes-subdir`.
3. Store paths only in the OS-local config returned by the script. Never write them into this Skill, repository files, prompts, or examples.
4. Run `scripts/bootstrap.py provision` once when local ASR, OCR, video acquisition, or plotting tools are needed.
5. Run `scripts/bootstrap.py doctor --deep --json` after first installation or a tool failure. Use `doctor --json` for routine checks.

The quality profile keeps `large-v3` ASR and PP-OCRv6 through RapidOCR/ONNX. Reuse shared models and dependencies between jobs.

## Workspace boundary

1. Resolve runtime paths from OS-local configuration or an explicit path for this invocation.
2. Do not scan parent workspaces, unrelated repositories, or unrelated Vault content.
3. Put transient acquisition files in `_work/<job-id>/`, the technical experiment in `sandbox/<job-id>/`, shared models in `cache/`, and only a small job manifest in `jobs/<job-id>/` after completion.
4. Write to a Vault only when configured or explicitly supplied. Respect `.obsidian/app.json` for its attachment folder.
5. Never persist cookies, tokens, browser profiles, passwords, API keys, or private account data.

Initialize each source with `scripts/job.py init --url <url>`. Read `references/platform-routing.md` before platform-specific acquisition or when a route fails.

## Classify before synthesis

Read `references/content-profiles.md` and choose exactly one `content_profile`:

- `technical`: a tool, method, workflow, code technique, AI capability, or setup whose feasibility can be tested;
- `overview`: general knowledge, life advice, commentary, explanation, or narrative best served by a short whole-source summary;
- `catalog`: a list of products, tips, destinations, recipes, resources, or recommendations where every item matters;
- `visual`: outfits, makeup, hairstyles, décor, before/after examples, visual designs, or other showcases where the variants cannot be understood well without images.

When profiles overlap, choose the one that determines what the reader must retain. A list of visually distinct outfits is `visual`; a list of small household accessories is `catalog`; a tutorial containing several steps is `technical`.

Read `references/report-templates.md` after choosing the profile. For `technical`, choose a concise tool/Skill introduction, an actionable tutorial/workflow, or a comparison/research/feasibility assessment. Start with a concrete conclusion and omit sections that do not help the reader. A `technical` note may omit `怎么操作` when the source offers no useful reader actions.

## Acquire only what the profile needs

Use the most authoritative available representation, escalating only as necessary:

1. Platform metadata, official article body, captions, subtitles, or public API.
2. Focused browser content when rendering or an existing signed-in session is required.
3. Public media plus one batched ASR call when no usable transcript exists.
4. Batched keyframe extraction and OCR only for visually material frames.

Prefer official text and subtitles over media download. Do not bypass login, CAPTCHA, paywalls, geographic restrictions, or access controls. If the body is inaccessible, report the precise state instead of inferring it from a title or snippet.

For `catalog`, make sure every item presented by the source is captured. For `visual`, identify every presented variant and select one non-redundant representative original image or frame for each. For `technical`, capture the inputs, steps, dependencies, expected output, and the smallest testable claim.

## Prepare a compact render bundle

Read `references/plain-language.md` before drafting `summary` and `content_items`. Write for a reader who is new to the subject: use familiar words, explain necessary terms where they first matter, and use one stable name for each concept. Make sentences easy to follow while preserving facts, causal links, conditions, and uncertainty.

Review the whole planned note before validation. Remove repeated explanations and conclusions across sections; each section should add information the reader needs. State the observed experiment result once, then use the conclusion to explain its scope. Optimize for understanding, not minimum length. English word-count limits are not Chinese character limits.

Follow `references/evidence-schema.md`. Use artifacts, transcripts, locators, and claim checks only as transient working material needed to avoid hallucination; do not render them as sections and do not retain them by default.

The render bundle must contain:

- `content_profile`;
- a grounded `summary.one_sentence` and `summary.overview`;
- `summary.procedure` for `technical` only when useful reader actions exist;
- `source_item_count` and every `content_item` for `catalog` or `visual`;
- one valid `visual_id` per `visual` item;
- a real experiment result for `technical` when a safe local test is feasible;
- only intentional knowledge links and relations.

Validate it with `scripts/job.py validate --evidence <bundle.json>` before rendering.

## Select visuals economically

1. Never archive decorative banners, avatars, ads, recommendation cards, duplicate frames, or contact sheets used only for selection.
2. `visual`: archive exactly one representative image per content item unless two views are essential to understand a before/after pair.
3. `catalog`: archive an item image only when appearance materially helps recognition; text-only lists are valid.
4. `technical`: archive only diagrams or screenshots needed to perform the steps, plus useful experiment-result figures.
5. `overview`: default to no archived image; keep one only when it materially carries information that the summary cannot replace.
6. Do not show timestamps, evidence IDs, or local paths in image captions.

Use `scripts/extract_keyframes.py` and `scripts/ocr_images.py` in batches. Read `references/performance.md` for video, image batches, or performance troubleshooting.

## Validate only technical content

For `technical`, test the smallest risky assumption inside `sandbox/<job-id>/`:

1. State the test input and success condition.
2. Run a safe local or explicitly authorized test.
3. Record the actual result, elapsed time, errors, and any necessary human correction.
4. Create an experiment figure only when it communicates the result better than text.
5. Distinguish “the technique runs” from adoption, revenue, popularity, or other real-world outcomes.

If a technical claim cannot be tested locally, perform the smallest authoritative check available and state the concrete reason; do not present a plan as a completed test.

Do not create an experiment section, sandbox, experiment figure, or planned experiment for `overview`, `catalog`, or `visual` content.

## Render the Obsidian note

Follow `references/output-contract.md` and run `scripts/render_note.py --evidence <bundle.json>`.

The renderer chooses the note body from `content_profile` and its matching report template:

- `technical`: the selected presentation form in `references/report-templates.md`;
- `overview`: 全文总结 → optional 要点 or 内容结构图;
- `catalog`: 简短总览 → 完整清单，每项说明“是什么”和“为什么”;
- `visual`: 简单总结 → 逐项展示，每项一张来源图片和简短说明.

Keep optional Mermaid structure or knowledge relations only when they materially improve understanding. Never add empty sections. Never render source excerpts, claim/evidence tables, limitations, full timelines, transcripts, or generic supporting attachments.

Use `references/report-templates.md` for the final note shape. Keep test inputs, commands, OCR/ASR details, timings, and routine corrections in transient evidence unless a detail changes the conclusion; the note should state the observed result and its scope in a sentence or two.

## Verify and clean up

1. Verify the Markdown, optional Mermaid fences, and every embedded attachment.
   Re-read the rendered prose using `references/plain-language.md`: resolve unexplained necessary terms, overloaded sentences, and semantic repetition without removing needed facts or list items. The renderer preserves supplied wording; it does not assess understanding.
2. Confirm that every `visual` content item has exactly one rendered image and every `catalog` item appears in the note.
3. Run `scripts/job.py finalize --manifest <job.json> --evidence <bundle.json> --note <note.md>`. This verifies the note and local embeds before deleting anything.
4. Preserve only the final note, its copied visuals, and the compact manifest written by `finalize`. Delete raw media, extracted audio, transcripts, OCR output, evidence bundles, candidate/rejected frames, contact sheets, previews, and unreferenced experiment files.
5. Preserve shared ASR/OCR models and dependencies.
6. Return the content profile, acquisition completeness, concise conclusion, note path, retained visual count, and cleanup status.
