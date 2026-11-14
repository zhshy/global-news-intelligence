#!/usr/bin/env python3
"""Collect RSS and GDELT items, deduplicate, and write a source-grounded report."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import feedparser
import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo("Asia/Shanghai")
UTC = timezone.utc
CONFIG = ROOT / "config" / "sources.yaml"


def clean(value: str, limit: int = 1200) -> str:
    value = re.sub(r"<[^>]+>", " ", value or "")
    value = re.sub(r"\s+", " ", value).strip()
    return value[:limit]


def parse_date(entry) -> datetime | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    try:
        import calendar
        return datetime.fromtimestamp(calendar.timegm(parsed), tz=UTC)
    except Exception:
        return None


def normalize_url(url: str) -> str:
    url = (url or "").strip()
    return url.split("#", 1)[0]


def item_id(item: dict) -> str:
    key = (item.get("url") or item.get("title") or "").lower()
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def collect_rss(start: datetime, end: datetime) -> list[dict]:
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}
    items: list[dict] = []
    for region, sources in (config.get("regions") or {}).items():
        for source in sources or []:
            name = source.get("name", "Unknown source")
            url = source.get("url", "")
            if not url:
                continue
            try:
                parsed = feedparser.parse(url)
                if getattr(parsed, "bozo", False) and not parsed.entries:
                    print(f"WARN RSS parse failed: {name}: {getattr(parsed, 'bozo_exception', '')}")
                for entry in parsed.entries:
                    published = parse_date(entry)
                    if published and not (start <= published <= end):
                        continue
                    link = normalize_url(entry.get("link", ""))
                    if not link:
                        continue
                    items.append({
                        "region": region,
                        "country": source.get("country", "Unknown"),
                        "source": name,
                        "title": clean(entry.get("title", ""), 400),
                        "summary": clean(entry.get("summary", "") or entry.get("description", "")),
                        "published_utc": published.isoformat() if published else None,
                        "url": link,
                        "method": "RSS",
                    })
            except Exception as exc:
                print(f"WARN source failed: {name}: {exc}")
    return items


def collect_gdelt(start: datetime, end: datetime) -> list[dict]:
    # GDELT DOC API complements RSS discovery; results are leads, not verified facts.
    query = '(war OR election OR sanctions OR diplomacy OR trade OR energy OR "central bank" OR missile OR ceasefire)'
    params = {
        "query": query,
        "mode": "ArtList",
        "format": "json",
        "maxrecords": 75,
        "sort": "DateDesc",
        "startdatetime": start.strftime("%Y%m%d%H%M%S"),
        "enddatetime": end.strftime("%Y%m%d%H%M%S"),
    }
    try:
        response = requests.get("https://api.gdeltproject.org/api/v2/doc/doc", params=params, timeout=35)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        print(f"WARN GDELT unavailable: {exc}")
        return []
    results = []
    for row in payload.get("articles", []) or []:
        url = normalize_url(row.get("url", ""))
        if not url:
            continue
        results.append({
            "region": "gdelt_discovery",
            "country": row.get("sourcecountry", "Unknown"),
            "source": row.get("domain", urlparse(url).netloc),
            "title": clean(row.get("title", ""), 400),
            "summary": "",
            "published_utc": row.get("seendate"),
            "url": url,
            "method": "GDELT discovery (not independently verified)",
        })
    return results


def deduplicate(items: list[dict]) -> list[dict]:
    seen = set()
    output = []
    for item in sorted(items, key=lambda x: x.get("published_utc") or "", reverse=True):
        key = re.sub(r"[^a-z0-9]+", " ", (item.get("title") or "").lower()).strip()
        if not key:
            continue
        compact = " ".join(key.split()[:18])
        if compact in seen:
            continue
        seen.add(compact)
        item["id"] = item_id(item)
        output.append(item)
    return output


def generate_ai_analysis(items: list[dict], edition: str, window_start: datetime, window_end: datetime) -> str | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    compact_items = items[:120]
    prompt = f"""
你是严谨的全球新闻研究员。请仅根据提供的新闻条目撰写简体中文全球新闻简报。
版本：{edition}。时间窗口：{window_start.astimezone(TZ).isoformat()} 至 {window_end.astimezone(TZ).isoformat()}。
全球覆盖，重点关注美国、中国、俄罗斯、欧洲和中东。
按事件聚类，不按媒体罗列。输出：全球要闻速览、重点地区动态、跨国媒体视角对比、深度分析、未来24-72小时观察清单、来源链接。
必须遵守：
- 只能陈述输入材料支持的事实，不得补造背景、数字、引文或来源。
- 同一事件的多个来源才可做媒体比较；来源不足时明确说不足，不能虚构“三方观点”。
- 区分官方声明、媒体报道、当事方指控、未证实信息和分析推测。
- 不根据媒体所属国家臆断立场。
- 每条新闻保留来源名称、标题和URL。
- 如果只有标题或RSS摘要，明确标注“仅依据标题/摘要，未核验原文”。
- 对军事和伤亡信息采取特别谨慎的措辞。
新闻数据：
{json.dumps(compact_items, ensure_ascii=False)}
"""
    try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "你是严谨、谨慎、重视来源的国际新闻分析员。"},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.2,
            },
            timeout=180,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as exc:
        print(f"WARN AI analysis unavailable: {exc}")
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--edition", choices=["morning", "evening"], required=True)
    args = parser.parse_args()

    now = datetime.now(TZ)
    hours = 12 if args.edition == "morning" else 14
    end = now.astimezone(UTC)
    start = end - timedelta(hours=hours)

    items = deduplicate(collect_rss(start, end) + collect_gdelt(start, end))
    edition_cn = "早间版" if args.edition == "morning" else "晚间版"
    report = generate_ai_analysis(items, edition_cn, start, end)

    if not report:
        lines = [
            f"# 全球新闻情报{edition_cn}",
            "",
            f"- 生成时间：{now.isoformat()}",
            f"- 采集窗口：{start.astimezone(TZ).isoformat()} 至 {end.astimezone(TZ).isoformat()}",
            f"- 采集条目：{len(items)}",
            "",
            "> 当前未配置或无法使用 OPENAI_API_KEY。以下为新闻采集清单，不是 AI 深度分析报告。",
            "",
            "## 新闻条目",
        ]
        for item in items[:150]:
            published = item.get("published_utc") or "发布时间未提供"
            lines.extend([
                f"### {item['title'] or '无标题'}",
                f"- 来源：{item['source']}（{item['country']}）",
                f"- 发布时间：{published}",
                f"- 类型：{item['method']}",
                f"- 摘要：{item.get('summary') or '来源未提供摘要'}",
                f"- 原文：{item['url']}",
                "",
            ])
        report = "\n".join(lines)

    date_path = now.strftime("%Y/%m")
    filename = f"{now.strftime('%Y-%m-%d')}-{args.edition}.md"
    out_dir = ROOT / "reports" / date_path
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / filename).write_text(report.rstrip() + "\n", encoding="utf-8")
    (out_dir / f"{now.strftime('%Y-%m-%d')}-{args.edition}-sources.json").write_text(
        json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Wrote {out_dir / filename} with {len(items)} items")


if __name__ == "__main__":
    main()
