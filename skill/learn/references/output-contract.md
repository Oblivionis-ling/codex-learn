# Output contract

Return two layers: a concise conversational result and a detailed Obsidian note.

## Conversational result

Lead with the result. Include:

1. acquisition completeness (`complete_multimodal`, partial, text-only, and so on);
2. the one-sentence conclusion;
3. the most useful article sections or timestamps;
4. reusable knowledge separated from unverified source claims;
5. the minimal experiment outcome, or an explicit `planned` status;
6. the note path, archived visual count, missing material, and cleanup status.

The conversation must remain understandable without opening the note.

## Obsidian note

Use `assets/obsidian-note-template.md`. Include:

- YAML frontmatter with source, platform, author, publication date, retrieval date, status, and tags;
- one-sentence conclusion and a Mermaid content-structure diagram;
- article outline or timestamped video timeline;
- selected original text excerpts with evidence IDs and locators;
- original source images in reading order and timestamped video keyframes;
- reusable knowledge;
- a claim table with type, evidence level, verification state, evidence IDs, and missing evidence;
- the minimal experiment design, execution status, result, and embedded experiment figures;
- limitations and missing material;
- normalized `[[wikilinks]]` and a compact relationship graph when at least three relations exist;
- the original source URL and supporting attachments.

When a Vault is configured, copy local visuals into its configured attachment folder under a job-specific `Learn` subfolder, then use Obsidian embeds. Do not embed a nonexistent local file. External image URLs may be used as a clearly non-local fallback.

Use this filename pattern:

```text
<sanitized-title>_来源笔记_YYYYMMDD.md
```

Do not label generated files `最终版`.

## Quality gates

- Do not summarize inaccessible body content from a title or search snippets alone.
- Do not merge narration, OCR, visible UI state, and external verification into one unattributed claim.
- Do not present process completion as business success.
- Do not present a future test or promised follow-up as a completed result.
- Do not mark current policies or prices verified without a current official source.
- Ensure every A/B claim points to evidence.
- Mention material ASR/OCR uncertainty and model fallback.
- Verify every copied attachment exists and every Markdown placeholder is resolved.
- Confirm the note has balanced Mermaid code fences and no machine-local path in its prose or frontmatter unless the user explicitly wants one.
