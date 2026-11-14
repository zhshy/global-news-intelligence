# 安装与配置

本仓库包含 Claude Code / Codex 共用的 Agent Skill。

## 在本仓库内使用

克隆仓库后，在项目根目录启动 Claude Code 或 Codex。Skill 已分别放在：
- Codex：`.agents/skills/global-news-intelligence/SKILL.md`
- Claude Code：`.claude/skills/global-news-intelligence/SKILL.md`

## 安装为个人全局 Skill

macOS / Linux：

```bash
git clone https://github.com/zhshy/global-news-intelligence.git
mkdir -p ~/.agents/skills/global-news-intelligence ~/.claude/skills/global-news-intelligence
cp global-news-intelligence/.agents/skills/global-news-intelligence/SKILL.md ~/.agents/skills/global-news-intelligence/SKILL.md
cp global-news-intelligence/.claude/skills/global-news-intelligence/SKILL.md ~/.claude/skills/global-news-intelligence/SKILL.md
```

## 配置每日新闻档案

1. 在 GitHub 仓库 Settings → Secrets and variables → Actions 添加 `OPENAI_API_KEY`。
2. 可选添加 Actions variable：`OPENAI_MODEL`，默认 `gpt-4.1-mini`。
3. 在 Settings → Actions → General 开启允许 GitHub Actions 写入仓库内容。
4. 确认 `.github/workflows/daily-news.yml` 位于默认分支。
5. 在 Actions 页面手动运行一次 workflow_dispatch，分别测试 morning 和 evening。

不设置 API Key 时，工作流仍会采集 RSS/GDELT 并保存来源清单，但不会生成 AI 深度分析。请勿把 API Key 写入仓库文件或提交到 Git。
