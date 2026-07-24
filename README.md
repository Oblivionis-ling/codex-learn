# Codex Learn

`$learn` 是一个面向 Codex 的多模态知识萃取 Skill。给它一条文章、图文帖、音频或视频链接，它会按内容类型生成简洁、实用、不过度堆资料的 Obsidian 笔记。

```text
$learn https://example.com/content
```

## 它会做什么

- 处理普通网页、微信公众号、Bilibili、小红书以及本地多模态文件。
- 优先使用官方正文、字幕和元数据；必要时使用本地高质量 ASR、OCR、抽帧和视觉核验。
- 技术类总结“是什么、怎么操作、实测是否可行”，只在这类内容中运行最小实验。
- 普通知识和生活百科类只保留简洁全文总结与少量要点。
- 好物、资源或技巧清单完整列出每一项，并逐项说明“是什么”和“为什么”。
- 穿搭、妆容、发型等视觉内容先简短总结，再为每个方案保留一张代表性原图。
- 只复制最终笔记实际引用的图片；转写、候选帧、证据表和中间附件默认在验收后删除。
- Mermaid 结构图和知识关系仅在确实有助理解时生成。

## 速度优化

- 部署使用依赖指纹；环境和模型未变化时，重复 `provision` 会直接走快速路径。
- `large-v3` 自动选择 CUDA/float16 或 CPU/int8，并使用批量推理。
- 多段媒体、多个图片和多个关键帧分别在单一进程中批量处理，避免重复加载模型。
- OCR 使用 RapidOCR + PP-OCRv6/ONNX；低置信度结果强制回看原图，不用速度交换事实准确性。
- 获取顺序为“元数据/正文/官方字幕 → 必要媒体 → 关键帧/OCR”，减少不必要的下载和计算。

## 安装

将仓库克隆到任意位置，然后让 Codex 的个人 Skill 目录指向 `skill/learn`。

Windows PowerShell 示例：

```powershell
git clone https://github.com/<owner>/codex-learn.git <local-repository>
New-Item -ItemType Junction `
  -Path "$HOME\.codex\skills\learn" `
  -Target "<local-repository>\skill\learn"
```

重启或刷新 Codex 后直接调用：

```text
$learn <链接或本地文件>
```

## 首次使用

第一次运行时，Skill 会检查本地配置，并只询问两个位置：

1. 独立运行工作区，用于任务证据、下载、沙盒和共享模型缓存；
2. Obsidian Vault，用于最终笔记和附件。

路径写入操作系统本地配置，不进入仓库：

- Windows：`%LOCALAPPDATA%\codex-learn\settings.json`
- macOS/Linux：`$XDG_CONFIG_HOME/codex-learn/settings.json` 或 `~/.config/codex-learn/settings.json`
- 可用 `CODEX_LEARN_CONFIG` 覆盖配置文件位置。

也可以手动配置：

```text
<python> skill/learn/scripts/bootstrap.py configure \
  --workspace <runtime-workspace> \
  --vault <obsidian-vault> \
  --notes-subdir Learn
```

当来源需要转写、OCR、媒体处理或绘图时，首次运行会安装隔离的本地工具链并下载高质量模型：

```text
<python> skill/learn/scripts/bootstrap.py provision
<python> skill/learn/scripts/bootstrap.py doctor --json
```

如果默认 Python 包下载节点较慢，可在首次部署时传入本地区域可用的镜像：

```text
<python> skill/learn/scripts/bootstrap.py provision --pip-index <index-url>
```

隔离环境和模型保存在运行工作区的共享 `cache/` 中。首次下载可能较久，后续任务复用缓存。

## Obsidian 输出

笔记自动选择一种结构：

- `technical`：技术是什么 → 怎么操作 → 可行性验证；
- `overview`：全文总结 → 要点；
- `catalog`：简短总览 → 完整清单；
- `visual`：简单总结 → 逐项展示，每项一张图。

最终笔记不再默认包含原文摘录、时间轴、主张证据表、局限、转写附件或补充附件。附件目录自动读取 Vault 的 `.obsidian/app.json`；仅被笔记引用的图片会复制到 `Learn/<job-id>/`。

渲染完成后，`job.py finalize` 会先检查 Markdown 和所有本地图片，再删除当前任务的转写、证据 JSON、候选帧、联系表和沙盒中间文件；共享模型缓存不会被清理。

## 隐私与边界

- 不需要单独的模型 API Key；模型推理和工作流由当前 Codex 会话与本地工具完成。
- 不导出浏览器 Cookie、Token、密码、私信或账户资料。
- 不绕过登录、验证码、付费墙或平台访问控制。
- 运行目录、Vault 内容、下载媒体、模型缓存和本机配置均被排除在 Git 之外。

## 项目结构

```text
skill/learn/
  SKILL.md
  agents/openai.yaml
  assets/obsidian-note-template.md
  references/
  scripts/
tests/
config/settings.example.json
```

## 开发验证

使用符合本机工作区规则的 Python 运行：

```text
<python> -m unittest discover -s tests -v
<python> <skill-creator>/scripts/quick_validate.py skill/learn
```
