# Content profiles

Choose one profile from the source's dominant reader need. Do not combine full templates. After selecting `technical`, choose one presentation in `report-templates.md`.

## `technical`

Use for tools, code, AI techniques, configurations, workflows, and reproducible methods. Choose a presentation form: tool/Skill introduction, reproducible tutorial/workflow, or comparison/research/feasibility assessment.

For `introduction` and `workflow`, use this note shape:

1. `技术是什么`: name the subject, say what it does or solves, and include one useful verified fact.
2. Optional `怎么操作`: only the actions the reader needs to reproduce or try it.
3. Concise `可行性验证`: a real result and its scope, usually one or two sentences.

For comparison, research, or feasibility work, choose the `evaluation` presentation instead: lead with the decision, include only decision-changing reasons, and report validation in one or two sentences.

Run the smallest safe experiment that can disprove the key feasibility claim. If local execution is unsafe or impossible, make the smallest authoritative check and state why local testing was not done. Do not render test procedures, raw logs, or routine corrections. Keep a diagram or screenshot only when it helps the reader understand or act.

## `overview`

Use for general knowledge, life advice, explanations, commentary, stories, or non-itemized educational content.

Required note section:

1. `全文总结`: a compact but complete synthesis in one to three short paragraphs.

Optional additions:

- `要点`: only ideas worth remembering or applying that the summary does not repeat.
- A compact structure diagram when it clarifies relationships or flow.

Do not create an experiment, timeline, evidence table, excerpt section, limitations section, or attachment appendix. Default to no image; retain one only when it carries irreplaceable information.

## `catalog`

Use when the source presents independently useful items and readers benefit from comparing, selecting, or looking them up: products, household accessories, tips, recipes, destinations, tools, resources, recommendations, and Q&A collections. A numbered group of examples that supports one general point belongs to `overview` when readers do not need every item separately.

For recommendations, explain what each item is and why it helps. For AMA, interview, or FAQ collections, keep each useful question with its answer; set `summary.catalog_format` to `qa` and group by topic only when it helps navigation.

Required note sections:

1. `简短总览`: what the list is for and how its items are grouped.
2. `完整清单`: include every item presented by the source, in source order.

Record the number identified in the source as `source_item_count`; it must equal the number of `content_items` before rendering.

Each `content_item` must contain:

- `name`: the item's recognizable name;
- `what`: what it is or how it is used;
- `why`: why it is useful, recommended, or noteworthy according to the source;
- `notes`: optional concrete caveat, suitable situation, size/material, or selection advice when useful.

Do not collapse a “20 items” source into a smaller top-ten list. Images are optional and should be retained only when appearance materially helps recognition.

## `visual`

Use when visual differences are the substance: outfits, makeup looks, hairstyles, décor arrangements, design variants, before/after examples, or visual demonstrations.

Required note sections:

1. `简单总结`: the overall theme, season, style, audience, or selection logic.
2. `逐项展示`: one entry for every presented variant, in source order.

Record the number of presented variants as `source_item_count`; it must equal the number of `content_items` before rendering.

Each `content_item` must contain:

- `name`: a concise variant label;
- `what`: the visible composition or defining features;
- `why`: optional styling logic, effect, or suitable situation;
- `visual_id`: one unique representative source image or frame.

Archive one image per item. Crop or select a clearer frame when several items appear together, but do not retain the selection contact sheet. Represent an indivisible before/after pair as one combined comparison image.

## Tie-breakers

- A “summer eight-outfit” video is `visual`, not `catalog`, because the image is essential.
- A “20 useful household accessories” post is `catalog`; add item images only if names alone are insufficient.
- A “five steps to install a local model” video is `technical`, even though it contains a numbered list.
- A “ten facts about sleep” article is `catalog` only when each fact is an independently named item; otherwise use `overview`.
