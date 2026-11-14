# Global News Intelligence

面向 Claude Code / Codex 的全球新闻情报项目。目标是每天两次采集全球新闻，重点关注美国、中国、俄罗斯、欧洲和中东，按事件聚类，生成中文简报并保存到仓库。

## 功能

- RSS 多源采集，按地区和媒体管理信源。
- GDELT 全球新闻检索补充事件发现。
- 按事件去重，保留来源标题、发布时间和原文链接。
- 可选调用 OpenAI API 生成中文摘要、跨媒体比较和分析。
- GitHub Actions 每天北京时间 07:00、21:00 运行。
- 报告按 `reports/YYYY/MM/YYYY-MM-DD-{morning|evening}.md` 归档。

## 安装 / 本地运行

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/collect_news.py --edition morning
```

晚间版：

```bash
python scripts/collect_news.py --edition evening
```

## GitHub Actions 配置

工作流：`.github/workflows/daily-news.yml`

在仓库 Settings → Secrets and variables → Actions 中添加：

- `OPENAI_API_KEY`：可选。配置后会调用模型生成中文深度分析；未配置时只生成基于来源的采集简报，不会伪装成深度分析。
- `OPENAI_MODEL`：可选，默认 `gpt-4.1-mini`。

工作流使用 GitHub Actions 的 `GITHUB_TOKEN` 自动提交报告。请在 Settings → Actions → General 中允许 Actions 读写仓库内容（必要时）。

## 时间窗口

- 早间版：北京时间前一日 19:00 至当日 07:00。
- 晚间版：北京时间当日 07:00 至 21:00。

GitHub Actions 使用 UTC cron：23:00 UTC（次日北京时间 07:00）和 13:00 UTC（北京时间 21:00）。GitHub 定时任务可能延迟数分钟，且默认分支必须包含工作流文件。

## 质量原则

- 区分事实、官方声明、媒体单一来源、当事方指控和分析推测。
- 不依据媒体所属国家推断其立场。
- 重大事件尽量比较不同国家/地区的独立来源；来源不足时明确说明。
- 不编造标题、引文、来源链接、伤亡数字或事件时间。
- GDELT 的提及量、情绪等指标不等于客观事实或民意调查。
- RSS 摘要不可替代原文核验；无法访问原文时明确标注。

## 目录

- `SKILL.md`：Claude Code / Codex 共用的分析规范。
- `config/sources.yaml`：RSS 信源清单。
- `scripts/collect_news.py`：采集、去重和报告生成。
- `reports/`：自动归档的日报。
