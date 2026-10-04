# Write so the reader understands

Apply this guide to all Learn profiles, including item descriptions, captions, steps, and validation. Write in the user's requested language. Assume the reader is new to the subject unless the user establishes another audience. The goal is to understand the source and act on it with less effort; length alone cannot show that this goal was met.

## Familiar words and necessary terms

- Prefer common words and concrete verbs when they express the same meaning. Describe what a thing does before introducing its abstract category.
- Keep exact product names, commands, parameter names, and technical distinctions that the reader needs for identification, use, or accuracy.
- Explain an indispensable unfamiliar term briefly where it first helps understanding. Give its function in the current context; a longer label or acronym expansion alone is not an explanation.
- If a sentence contains several new terms, explain their relationship in connected sentences instead of stacking labels. Remove a term if it adds no useful information.
- Use one stable name for each concept throughout the note. Do not rotate synonyms for variety. Do not merge distinct concepts or different levels of certainty to make the vocabulary uniform.
- Do not add a large glossary by default. A necessary explanation belongs beside the point it supports.

For example:

> 这个工具先从你的资料中找到相关段落，再让模型据此回答。这种“先检索、再生成”的方法叫检索增强生成（RAG）。

This explains the operation before naming the technique. Use it only when the source supports that operation.

## Sentences with clear relationships

- Give a sentence one main idea. Split chains of claims, nested qualifications, or several independent actions into sentences the reader can follow in order.
- Say who does what, to which object, and under which necessary condition. Prefer direct actions to abstract phrases such as “实现能力提升”.
- Put a prerequisite before an action when the reader must know it first. Keep cause and effect connected; splitting a sentence must not hide that relationship.
- Keep paragraphs coherent. Short sentences do not require turning every sentence into a bullet or every trivial action into a separate step.
- Preserve numbers, negation, exceptions, comparison baselines, and uncertainty that change the meaning. Distinguish a creator's claim from an independently observed result.

For example, replace a vague claim about a “download workflow loop” with:

> 原型下载并解析了一份 5 页 PDF。这说明该下载流程能够运行；其他文献和平台的覆盖率仍未验证。

This keeps both the observation and its limit. Removing the second sentence would change the conclusion.

## Remove repeated meaning

- Read the planned note as a whole, not only field by field. A different phrasing of an earlier sentence is still repetition unless it adds a useful distinction.
- Give each section a job: explain the subject, supply necessary actions or items, then report evidence that changes the conclusion. Merge or omit optional sections that add nothing.
- Delete filler, empty praise, stacked adjectives, repeated conclusions, and generic cautions unrelated to the reader's decision.
- Define a necessary term once. Do not repeat the definition in the opening, steps, captions, and validation.
- In technical validation, state the observation in `result` and its scope in `conclusion`. Keep raw testing and acquisition details in transient evidence.
- Keep every independent catalog item, useful Q&A exchange, and visual variant required by the chosen profile. Deduplication applies to repeated meaning, not distinct source content.

For the STE topic, the opening can be this compact:

> ASD-STE100 是航空维修文档使用的一套写作规则。它限制常用词的含义，并要求短句和直接的操作指令，目的是减少误读。Karpathy 建议用这些规则约束模型的解释，让输出更容易理解。

The later steps can show how to request that style. Validation should add what was checked and what remains uncertain, rather than repeat this introduction or expand into a history of the standard.

## Final reading pass

Check these questions against the acquired source before rendering, then check the actual note again:

1. Can a new reader explain what the subject is and why it matters without looking up several terms? Resolve the necessary terms locally.
2. Are actions, relationships, prerequisites, and certainty still correct? Restore missing meaning before shortening further.
3. Does each paragraph and section add something? Remove repeated explanations and conclusions.
4. Are the profile's essential facts, items, and visuals still complete? Do not trade coverage for brevity.

This is a synthesis and editing task. A sentence-length checker cannot establish semantic clarity, factual fidelity, or absence of repeated meaning. Do not mechanically split text or impose a fixed Chinese character ceiling. An explanation may need more words to become understandable.

## Basis and limits

These instructions combine Learn's reader-focused templates with the user's requests for fewer unexplained terms and less repeated meaning. They draw on STE's emphasis on simple vocabulary, stable terminology, short sentences, and direct instructions. Learn states the rules explicitly; it does not rely on a model knowing the standard from its name.

The official STE FAQ permits industry-specific technical terms and says that its basic principles can be adopted in other writing. Learn adapts those principles to learning notes. It does not reproduce the controlled dictionary or claim ASD-STE100 compliance. English word-count rules do not define Chinese character limits. Karpathy's experience and the video's shorter answer example do not prove that every model response becomes clearer or shorter.

- [Source video](https://www.bilibili.com/video/BV1huHv6zEpo/)
- [Karpathy's original post](https://x.com/karpathy/status/2105819303471976479)
- [Official STE FAQ](https://www.asd-ste100.org/faq.html)
- [Official description of STE](https://www.asd-ste100.org/about_STE.html)
