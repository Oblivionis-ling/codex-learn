# Learning cards

Produce one compact review card for each new learning note. Synthesize it from the acquired source and the finished note, then render it in code with `scripts/render_card.py`. Pillow is already part of the local toolchain. Use source photographs only when the visual profile requires them; no image-generation service, browser screenshot service, model API, or network font is needed.

## Choose the information

Write a short subject title and one useful takeaway. Add only the details needed to understand or recall that takeaway. A diagram and its surrounding text should contribute different information. Do not fill every available slot, repeat the opening in each point, or shorten by dropping conditions that change the conclusion.

| Profile | Useful card content |
|---|---|
| `technical` | What the tool or method helps with; an optional short sequence; two or three essential actions or selection reasons. Keep the observed result's material scope, including whether a result is historical. |
| `overview` | The central idea, relationship, or cause and effect. Use a sequence or loop only when it explains the source. Add two or three distinctions the reader needs. |
| `catalog` | Up to four source items, each with its recognizable name and one useful selection reason. Supply each item's one-based `item_number`. The renderer labels complete versus selected coverage. |
| `visual` | One or two representative acquired images and at most two practical points. The renderer preserves the whole image and labels image coverage. Full item-by-item coverage remains in the note. |

The card supplements the note. Keep every required catalog entry, useful Q&A exchange, and visual variant in the note even when the card selects a subset. A catalog card must not present a sample as the complete list. For Q&A, the point label can be a short version of its question and the text its grounded answer.

## Bundle fields

Add `learning_card` to every newly synthesized render bundle:

```json
{
  "learning_card": {
    "title": "Short, specific subject",
    "takeaway": "One grounded conclusion in familiar language",
    "points": [
      {"label": "A useful distinction", "text": "The detail needed to remember or use it"}
    ],
    "flow": ["First action", "Next action", "Result"],
    "loop": false,
    "scope": "A condition or observation that changes the conclusion"
  }
}
```

- `title` and `takeaway` are required plain text. An intentional newline may separate title clauses.
- `points` is optional, with at most four `{label, text}` objects. For a catalog, require a unique `item_number` on every point, matching an entry in `content_items`.
- `flow` is optional, with two to four short labels. Set `loop: true` only for an actual recurring process. Omit a flow that merely repeats the takeaway.
- `scope` is optional. Keep concrete prerequisites, historical attribution, or uncertainty when they affect meaning; omit generic cautions.
- For `visual`, supply `visual_ids` with one or two IDs from the content items. Those IDs need valid acquired `local_path` images. Use at most two points and omit `flow`.

The renderer uses a 1080 × 1350 layout, measured CJK text wrapping, large readable text, and profile-specific accents. It reports overflow instead of truncating sentences, hiding items, or shrinking text indefinitely. If it reports density, rewrite the card or select fewer points, then render again. Read the actual output before finalizing; the script checks layout and references, not semantic quality.

## Render and retain

`render_note.py --evidence <bundle.json>` generates both formats in the note's attachment directory, embeds the PNG near the beginning of the note, and links the SVG. Its JSON result includes `learning_card.png` and `learning_card.svg`. `job.py finalize` verifies both files before cleaning working materials. Old bundles without `learning_card` remain readable for compatibility; new tasks include it by default.

To create a card on its own:

```text
<python> scripts/render_card.py --evidence <bundle.json> --output <card.png> --svg-output <card.svg>
```

The PNG is portable. The SVG preserves editable text and shapes, embeds any source photographs, and links to the original public source. Its text appearance depends on the viewer's fonts. The source URL is also stored in PNG metadata; machine-local source and font paths are not added to either card's text or metadata.

Use the workspace-selected Python and reuse the configured runtime. Fonts are detected locally on Windows, macOS, and common Linux Noto CJK installations. If needed, pass `--font` to the standalone renderer or set `LEARN_CARD_FONT`; `LEARN_CARD_BOLD_FONT` optionally selects its bold companion. Report a missing font rather than producing unreadable glyphs.
