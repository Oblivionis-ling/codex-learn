# Platform routing

## Routing principle

Start with the most authoritative structured representation. Use browser interaction when a page is dynamic, rendering is itself evidence, or the content is visible only in the user's existing signed-in session. Escalate to media download, local ASR, keyframes, and OCR only as needed, but prefer completeness and accuracy over first-run speed.

## Bilibili

1. Read the public video metadata: title, pages, duration, author, description, `bvid`, and `cid`.
2. Query official and automatic subtitles for every relevant page. Preserve subtitle timestamps.
3. If no usable subtitle exists, retrieve the public playable media with an appropriate CLI and transcribe the audio locally with the configured high-quality ASR model.
4. Use transcript anchors and scene changes to select frames showing prompts, project names, procedures, outputs, metrics, comparisons, and conclusions.
5. OCR only frames whose visible text materially affects a claim. Cross-check names, numbers, and code against the original-resolution frame.
6. Keep a frame's timestamp and a timestamped source link in the evidence bundle.
7. Do not infer outcomes that the creator promises for a later episode or never displays.

## WeChat public articles

1. Extract the title, account, publication time, abstract, and focused article body.
2. Preserve headings, paragraphs, quotes, lists, code, links, captions, and the position of meaningful inline images.
3. Download article images from their rendered or lazy-load source URLs in reading order. Exclude avatars, QR-code promotions, reaction UI, ads, and related articles unless requested.
4. OCR screenshots, diagrams, tables, and charts only when they add information absent from the article text.
5. Connect each retained image to its surrounding paragraph or heading through `locator` or `artifact_ref`.
6. Treat blocked, expired, deleted, or account-restricted pages as inaccessible instead of reconstructing them from snippets.

## Xiaohongshu

1. Resolve the shared URL and determine whether the post is image, video, or mixed media.
2. Prefer visible post text, image order, captions, and platform-provided subtitles.
3. Use the user's existing browser session when sign-in is required. Never export cookies, tokens, messages, or account data.
4. Preserve every information-bearing post image in order; omit unrelated recommendation cards and comments unless requested.
5. For video posts, follow the same transcript-guided keyframe process as Bilibili.
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
- Transcribe audio and video with timestamps, then inspect transcript-guided frames.
- Keep the original file path as a locator for the job, but do not alter the source artifact.

## Quality fallbacks

- Prefer an official transcript over ASR, and ASR over manual inference from sparse frames.
- Use the configured maximum-quality multilingual ASR model unless hardware makes it impossible; record any fallback model and compute mode.
- Use Chinese-capable OCR and retain confidence or uncertainty for material text.
- When many frame candidates exist, generate a contact sheet for selection, then keep only a few original-resolution evidence frames.
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
