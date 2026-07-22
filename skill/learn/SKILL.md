---
name: learn
description: Extract traceable, verifiable knowledge from public articles, image posts, audio or video links, and local multimodal files; preserve useful source visuals and timestamped keyframes; test the smallest risky idea in a local sandbox; and create an illustrated Obsidian note with Mermaid structure and knowledge graphs. Use when the user invokes $learn with a link or file, or asks to learn from, verify, experiment with, or archive web, WeChat, Xiaohongshu, Bilibili, video, audio, screenshots, or attachments.
---

# Learn

Turn one source into reusable knowledge, a small verification result, and an illustrated Obsidian note. Keep acquisition, source facts, interpretation, external verification, and experiment results visibly separate.

## Invocation contract

Accept the shortest form directly:

```text
$learn <link-or-local-file>
```

Do not require the user to restate the workflow. Infer the platform, process all material modalities needed for the claims, run a safe minimal experiment when feasible, write the note, then answer with the conclusion and output path.

## Runtime readiness

Run `scripts/bootstrap.py status --json` with the Python selected by the active workspace instructions. Run `provision` only when `provision_current` is false; never reinstall tools before every source.

If no local configuration exists:

1. Ask only for a dedicated runtime workspace and an Obsidian Vault if the user has not already supplied them.
2. Run `scripts/bootstrap.py configure --workspace <path> --vault <path>`. Optionally supply `--notes-subdir`.
3. Store paths only in the OS-local config returned by the script. Never write them into this Skill, repository files, prompts, or examples.
4. Run `scripts/bootstrap.py provision` once when local ASR, OCR, video acquisition, or plotting tools are needed. It uses a dependency fingerprint and returns immediately on unchanged reruns.
5. Run `scripts/bootstrap.py doctor --deep --json` after first installation or a tool failure. Use the fast `doctor --json` for routine checks.

The default quality profile keeps `large-v3` ASR and uses PP-OCRv6 through RapidOCR/ONNX. Reuse the shared model and dependency cache between jobs.

## Workspace boundary

1. Resolve runtime paths from the OS-local config or an explicit path for this invocation.
2. Do not scan parent workspaces or unrelated repositories.
3. Put durable job state in `jobs/<job-id>/`, disposable downloads and frames in `_work/<job-id>/`, sandbox experiments in `sandbox/<job-id>/`, reusable models and tools in `cache/`, and fallback notes in `output/`.
4. Write to a Vault only when it is configured or explicitly supplied. Respect `.obsidian/app.json` for the attachment folder.
5. Never persist cookies, tokens, browser profiles, passwords, API keys, or private account data.
6. Delete only the resolved per-job `_work/<job-id>` after final files pass verification. Preserve shared caches and experiment evidence referenced by the note.

Initialize each source with `scripts/job.py init --url <url>`. Read `references/platform-routing.md` before platform-specific acquisition or when a route fails.

## Fast execution

Read `references/performance.md` before a video job, a batch of images, or performance troubleshooting.

1. Fetch independent metadata and subtitle endpoints concurrently, but stop once authoritative text is sufficient.
2. Prefer official subtitles over media download and ASR. Do not OCR article text already present in the DOM.
3. Read `runtime_python` from `bootstrap.py status`; run heavy scripts with that interpreter.
4. Pass all pages or media parts for one source to a single process so the model loads once:
   - `scripts/transcribe.py <media...> --output <transcript.json>`
   - `scripts/ocr_images.py <images...> --output <ocr.json>`
   - `scripts/extract_keyframes.py --video <video> --timestamps <seconds...> --output-dir <frames>`
5. On CPU-only machines, do not run ASR and OCR simultaneously. Parallelize network retrieval, not competing model inference.
6. Request word timestamps only when exact word-level alignment is material; segment timestamps are the default.

## Acquire the source

Use the most authoritative available representation, escalating until the material claims are supported:

1. Platform metadata, public API, purpose-built connector, or CLI.
2. Official article body, chapters, captions, subtitles, transcript, and downloadable source images.
3. Focused page content through a browser when rendering or an existing signed-in session is required.
4. Public media plus one batched local speech-to-text invocation when no usable transcript exists.
5. One batched extraction pass for transcript-guided keyframes, then one OCR process for only the visually material frames.

Do not bypass login, CAPTCHA, paywalls, geographic restrictions, or access controls. If the source is inaccessible, preserve the precise failure state and do not synthesize from a title or search snippet.

## Normalize evidence

Create one UTF-8 evidence bundle following `references/evidence-schema.md`.

- Give each artifact a stable ID and a precise paragraph, image, page, or timestamp locator.
- Keep metadata, article text, narration, ASR, OCR, visible UI state, visual inference, and external sources distinct.
- Preserve raw ASR/OCR observations; record corrections separately.
- Download meaningful article images in reading order.
- Keep video frames that substantiate a key claim, show a step or result, or make the note easier to understand. Record timestamps.
- Link claims to evidence IDs and label source facts, interpretations, external facts, and recommendations.

Validate with `scripts/job.py validate --evidence <bundle.json>` before synthesis.

## Select visuals

For articles, preserve the original order and paragraph/image locator. Omit decorative banners, avatars, ads, and recommendation cards unless requested.

For video:

1. Anchor candidates to statements about names, numbers, prompts, workflows, demonstrations, comparisons, and conclusions.
2. Add sparse scene-change coverage for visually important silent sections.
3. Inspect candidates at original resolution and keep only non-redundant explanatory frames.
4. Extract all selected timestamps with `scripts/extract_keyframes.py` instead of launching FFmpeg or Python once per frame.
5. Caption each frame with timestamp and what it proves; do not treat a visible UI as independent external verification.

## Synthesize and verify

Separate four layers:

- `source_fact`: directly stated or visibly demonstrated by the source.
- `interpretation`: a reasoned conclusion derived from evidence.
- `external_fact`: checked against a current authoritative source.
- `recommendation`: a proposed action or experiment.

Use the evidence levels in `references/evidence-schema.md`. Prices, policies, product capabilities, profitability, and audience outcomes require current authoritative evidence or real result data. Preserve unsupported claims as unverified.

## Run the minimal sandbox experiment

Test the smallest risky assumption, not the whole business or workflow.

1. State the hypothesis, controlled example, metrics, success criteria, and stop criteria before execution.
2. Run only safe local or explicitly authorized actions inside `sandbox/<job-id>/`.
3. Record environment, inputs, commands or method, raw outputs, elapsed time, errors, and human editing effort.
4. When results can be visualized, generate a PNG or SVG chart, comparison, screenshot, or contact sheet and list it under `experiment_figures`.
5. Distinguish process feasibility from real-world adoption, audience response, or profit.
6. If the claim cannot be tested locally, provide a runnable experiment plan and mark it `planned`, never `completed`.

## Render the Obsidian note

Follow `references/output-contract.md` and use `scripts/render_note.py --evidence <bundle.json>`.

The rendered note should include, when available:

- source metadata and one-sentence conclusion;
- article outline or timestamped video timeline;
- original source images and timestamped keyframes with captions;
- an automatically generated Mermaid content-structure diagram or an authored `summary_diagram`;
- reusable knowledge and claim/evidence assessment;
- minimal experiment design, result, and embedded experiment figures;
- limitations, precise locators, `[[wikilinks]]`, and a compact relationship graph;
- the original URL.

The renderer copies local visuals into the configured Vault attachment folder and uses Obsidian embeds. Missing visual files become warnings; do not silently claim they were archived.

## Complete and clean up

1. Verify the evidence JSON, Markdown note, Mermaid fences, and every embedded local attachment.
2. Preserve the evidence bundle, transcript when useful, experiment results, and note-linked visuals.
3. Remove per-job raw media, extracted audio, rejected frames, previews, and one-off files only after verification.
4. Preserve reusable ASR/OCR models and dependencies.
5. Return the acquisition completeness, conclusion, experiment outcome, note path, missing or unverified claims, and cleanup status.
