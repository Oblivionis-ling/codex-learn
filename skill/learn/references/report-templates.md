# Report templates

Choose one template by what the reader needs to keep. Keep the note shorter than the source: name the subject and its point directly, then include only details that help the reader understand, use, or judge it. Do not turn acquisition work, promotional claims, generic cautions, or every available section into note content. Keep caveats that change what the reader can conclude or do.

The `technical` profile has three presentation forms. Choose between them before writing; the other profiles each use one form.

## 1. Tool or Skill introduction (`technical`)

Use when the source introduces a tool, Skill, repository, model, or product and the reader mainly needs to know what it does and whether it is useful.

```markdown
## 技术是什么
[名称] 是 [类型]，可以 [核心功能/解决的问题]，适合 [用途或对象]。[有帮助时，补一个核实过的关键信息。]

## 怎么操作
[仅保留读者实际要采取的关键动作；没有必要操作时省略整节。]

## 可行性验证
[有价值且可核实时，用一两句话说清检查了什么、结果是什么、结论边界在哪里。]
```

Do not add an operation demonstration just because the source contains screenshots. For a Skill listing or introduction, omit generic usage walkthroughs; keep an installation or invocation step only when it materially helps the reader try it. Use a real product/workflow image only when it communicates more than the surrounding text.

## 2. Tutorial or workflow (`technical`)

Use when the source teaches a process the reader may want to reproduce.

```markdown
## 技术是什么
[方法/工作流] 能用 [关键方式] 达成 [结果]；开始前只需知道 [必要前提]。

## 怎么操作
1. [必要动作]。
2. [必要动作；省去可由默认值、常识或前文推出的内容。]

## 可行性验证
[一两句话：实际检查/运行了什么，观察到什么，以及这能或不能证明什么。]
```

Keep only the steps needed to reproduce the useful result. Combine routine actions; omit generic warnings and long narration. Run the smallest safe check for the source's central feasibility claim. The note reports the outcome, not the full test log.

## 3. Comparison, research, or feasibility assessment (`technical`)

Use when the reader needs a recommendation, a choice between options, or a concise assessment of whether a claim or deployment is viable.

```markdown
## 结论
[直接回答该选什么、是否值得做或已验证到哪一步；区分事实与未验证主张。]

## 适用判断
- [适合的场景/方案，以及决定性原因。]
- [主要成本、依赖或限制；仅留会改变决策的信息。]

## 可行性验证
[一两句话概括实际验证结果及其边界。]
```

Use a short list instead of a comparison table unless the reader must compare several dimensions side by side. Do not reproduce a research log, claim/evidence table, or every source citation in the note. Put only decision-changing evidence in the summary.

For this presentation, set `summary.presentation` to `evaluation`, put the recommendation or finding in `summary.overview`, and put decision-changing reasons in `summary.decision_points`.

## 4. General summary (`overview`)

Use for explanations, commentary, interviews, stories, or a source whose examples support one main idea rather than an independently useful list.

```markdown
## 全文总结
[通常用一个短段落交代主题、核心观点和它对读者的意义。]

## 要点
- [只留总结没有包含、值得记住或采取的内容。]
```

Omit `要点` when it would repeat the paragraph. A numbered set of examples is not automatically a catalogue; use this form when the examples mainly explain one shared idea. A structure diagram is optional and should clarify relationships or flow.

## 5. Recommendations or catalogue (`catalog`)

Use when the source offers independently useful items and the reader benefits from choosing among them.

```markdown
## 简短总览
[这份清单是什么，适合什么需要或场景。]

## 完整清单
### [项目名称]
[是什么，以及它为什么/适合何时使用；通常一两句话。]
```

Include every independent recommendation in source order; do not silently turn the source into a top-N list. Keep each entry compact. If the items are only examples of one idea and readers do not need to compare them individually, choose `overview` instead. Include item images only when appearance helps recognition or choice.

For an AMA, interview, or FAQ whose individual exchanges are worth keeping, use the same `catalog` profile with `summary.catalog_format` set to `qa`. Preserve each useful question and answer; group by topic only when it improves navigation. Do not force a “why useful” field onto answers.

```markdown
## 简短总览
[问答来源的主题范围和最值得记住的共同结论。]

## 完整清单
### [问题]
**回答：** [压缩后的回答；保留说话者的实际观点。]
```

## 6. Visual showcase (`visual`)

Use when the differences between looks, designs, arrangements, or before/after states are the main information.

```markdown
## 简单总结
[共同主题、风格或选择逻辑。]

## 逐项展示
### [方案名称]
![一张有代表性的来源图片]
[一两句话说出可见特点，以及值得注意的效果/搭配逻辑。]
```

Cover every distinct variant, in source order, with one useful original image per variant. Prefer the actual interface or result when that is the point of the source. Skip banners, promotional cards, duplicates, and screenshots that add no information.

## Shared editing rules

- Start with a concrete subject and action: say what the thing is, what it does, and what problem or need it addresses. Avoid vague hooks such as “黑科技”.
- Prefer the user's own concise rewrites as style examples when available; preserve their intended emphasis and wording level.
- Make headings conditional. Do not render an empty or low-value section to satisfy a fixed outline.
- Keep precise numbers, prerequisites, and limitations only when they change the reader's understanding or decision.
- Put source images beside the point they support. Do not create a separate `操作示意` section by default.
