# Performance routing

Use these rules to reduce latency without silently lowering evidence quality.

## Avoid work before optimizing it

1. Read metadata, article text, captions, and official subtitles before downloading media.
2. Stop acquisition escalation when the available representation supports every material claim.
3. Do not OCR decorative images or text already available in a native text layer.
4. Do not generate word timestamps, dense frames, or full-resolution contact sheets unless the task needs them.

## Reuse expensive initialization

- Run `bootstrap.py provision` only when `status` reports `provision_current: false`.
- Keep all parts of one source in one `transcribe.py` invocation; `large-v3` loads once.
- Keep all selected images in one `ocr_images.py` invocation; RapidOCR loads once.
- Give all chosen timestamps to one `extract_keyframes.py` invocation.
- Preserve `cache/` across jobs. Delete only per-job `_work` content.
- If the default package index is slow in the user's region, set `CODEX_LEARN_PIP_INDEX` or pass `bootstrap.py provision --pip-index <url>` once; the explicit provision option is saved only in the OS-local config.

## Hardware policy

- `asr_device: auto` selects CUDA with `float16` when available and CPU with `int8` otherwise.
- Automatic CPU threads leave capacity for the desktop and cap oversubscription.
- Batched ASR defaults to a larger batch on CUDA and a conservative batch on CPU. Reduce `--batch-size` only after an out-of-memory error.
- On CPU-only systems, serialize ASR and OCR. Concurrent model processes compete for memory bandwidth and are usually slower.
- Network metadata and image downloads may run concurrently because they are I/O-bound.

## Network acquisition

- Query official subtitle and metadata endpoints in parallel before starting `yt-dlp`.
- For ASR-only work, download the best audio stream rather than a high-resolution video.
- When video frames are also needed, download one suitable video/audio asset and reuse it for ASR and frames.
- For DASH or HLS media, use up to eight concurrent fragments; avoid concurrent downloads that saturate the link and slow browser/API requests.
- Do not download playlists or unrelated pages when one source item was requested.

## Quality-preserving fast path

- Keep ASR beam size 5 by default.
- Keep segment timestamps; enable word timestamps only for exact quotations or subtitle alignment.
- Keep lossless PNG evidence frames and inspect original resolution only for selected frames.
- Treat RapidOCR output below confidence `0.85`, or an empty result on an information-bearing image, as requiring visual review.
- Escalate ambiguous names, numbers, code, tables, and UI states to original-image inspection instead of trusting a faster OCR guess.

## Measure

Record `elapsed_seconds`, backend, batch size, model load time, media duration, image count, and frame count in job artifacts. Compare repeat runs separately from first-use model downloads. A valid speed claim needs the same source, quality settings, and hardware.
