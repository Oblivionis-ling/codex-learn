# Codex Learn

`$learn` 是一个面向 Codex 的多模态知识萃取 Skill。给它一条文章、图文帖、音频或视频链接，它会尽量读完正文和媒体，保留可追溯证据，做一个最小验证实验，并把结果写成图文并茂的 Obsidian 笔记。

```text
$learn https://example.com/content
```

## 它会做什么

- 处理普通网页、微信公众号、Bilibili、小红书以及本地多模态文件。
- 优先使用官方正文、字幕和元数据；必要时使用本地高质量 ASR、OCR、抽帧和视觉核验。
- 区分来源事实、解释、外部事实和建议，不把作者主张自动当成已验证事实。
- 在独立沙盒里验证最小风险假设，并保存实验图、对比图或截图。
- 将原文图片、视频关键帧和实验图复制到 Obsidian 附件目录并嵌入笔记。
- 自动生成 Mermaid 内容结构图、Obsidian 双链和知识关系图。

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

隔离环境和模型保存在运行工作区的共享 `cache/` 中。首次下载可能较久，后续任务复用缓存。

## Obsidian 输出

笔记包含：

- 一句话结论与内容结构图；
- 时间轴或文章结构；
- 带证据 ID 和定位的原文摘录；
- 原文图片、视频关键帧及时间戳；
- 可复用知识与主张证据表；
- 最小验证实验、结果和实验图；
- 局限、双链和知识关系图。

附件目录自动读取 Vault 的 `.obsidian/app.json`。本地图片会复制到该目录下的 `Learn/<job-id>/`，笔记使用 Obsidian 嵌入语法。

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
