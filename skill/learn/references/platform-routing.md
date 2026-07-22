# Platform routing

## Routing principle

Start with the most authoritative structured representation. Infer the content profile early so acquisition serves the final note instead of collecting every possible artifact. Use browser interaction when a page is dynamic, the visuals are the content, or the content is visible only in the user's existing signed-in session. Escalate to media download, local ASR, keyframes, and OCR only as needed, but prefer completeness and accuracy over first-run speed.

Fetch independent metadata and subtitle endpoints concurrently. Do not download media until subtitle and article-text routes are exhausted. Reuse one authenticated browser tab and one local model process per source instead of reopening them for each artifact.

## Bilibili

1. Read the public video metadata: title, pages, duration, author, description, `bvid`, and `cid`.
2. Query official and automatic subtitles for every relevant page. Use subtitle timestamps transiently for navigation; do not retain a timestamped transcript attachment.
3. If no usable subtitle exists, retrieve the smallest public media stream that preserves the needed modality. Use concurrent fragment download when supported, then transcribe all pages in one `transcribe.py` call.
4. For `technical`, select only frames needed to explain a step or result. For `visual`, identify every variant and select one representative frame per item. For `overview` and `catalog`, avoid frames unless they materially improve the note.
5. OCR only frames whose visible text materially affects a claim. Cross-check names, numbers, and code against the original-resolution frame.
6. Keep a frame's timestamp only in transient working data; the final caption uses a reader-facing description without timestamp or evidence ID.
7. Do not infer outcomes that the creator promises for a later episode or never displays.

## WeChat public articles

1. Extract the title, account, publication time, abstract, and focused article body.
2. Preserve headings, paragraphs, lists, code, links, and captions long enough to build the selected profile. Do not create a permanent excerpt section.
3. Download only images selected for the final note from their rendered or lazy-load source URLs. Exclude avatars, QR-code promotions, reaction UI, ads, and related articles.
4. Collect screenshots, diagrams, tables, and charts first, then OCR the selected set in one `ocr_images.py` call only when they add information absent from the article text.
5. Connect each retained image to its surrounding paragraph or heading through `locator` or `artifact_ref`.
6. Treat blocked, expired, deleted, or account-restricted pages as inaccessible instead of reconstructing them from snippets.

## Xiaohongshu

1. Resolve the shared URL and determine whether the post is image, video, or mixed media.
2. Prefer visible post text, image order, captions, and platform-provided subtitles.
3. Use the user's existing browser session when sign-in is required. Never export cookies, tokens, messages, or account data.
4. For `visual`, preserve one representative post image for every variant in order. For `catalog`, ensure every item is captured but retain item images only when recognition depends on appearance.
5. For video posts, follow the same subtitle-first and profile-directed batched keyframe process as Bilibili.
6. If login or CAPTCHA blocks access, ask the user to open/sign in or attach the media. Do not attempt to bypass it.

## Generic web pages

1. Extract metadata and the main content container.
2. Remove navigation, cookie notices, advertisements, related content, and comments unless requested.
3. Preserve semantic article structure and meaningful figures with captions and nearby paragraph locators.
4. Follow only a small number of directly relevant links for claim verification.
5. Prefer official documentation and primary sources over search snippets and aggregators.

## Local files

- Use the native text layer for PDF, DOCX, PPTX, and spreadsheets when available.
- Render and visually inspect pages when layout, diagrams, screenshots, or tables are material.
- Transcribe audio and video with temporary timestamps, inspect profile-relevant frames, then delete the transcript after the note is verified.
- Keep the original file path as a locator for the job, but do not alter the source artifact.

## Quality fallbacks

- Prefer an official transcript over ASR, and ASR over manual inference from sparse frames.
- Use the configured maximum-quality multilingual ASR model with automatic CUDA/CPU compute selection; record the backend and compute mode.
- Use RapidOCR/PP-OCRv6 for selected images. Visually review missing text and every line below the configured confidence threshold.
- When many frame candidates exist, generate a contact sheet for selection, then delete it and retain only the final profile-referenced original-resolution frames.
- If a visual cannot be archived, record the missing file or inaccessible URL explicitly.

## Failure states

Return one of these acquisition states instead of fabricating content:

- `complete_multimodal`
- `partial_multimodal`
- `metadata_only`
- `text_only`
- `transcript_only`
- `authentication_required`
- `captcha_required`
- `source_unavailable`
