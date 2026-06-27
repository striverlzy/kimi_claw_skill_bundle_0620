#!/usr/bin/env python3
"""Resolve the earliest public publish time + source URL for a news event.

需求1 的取证助手。anysearch 的搜索结果不带结构化日期，所以对候选源逐个 `extract`
抓原文，再按可靠度从高到低解析发布时间，跨源取最早一条：

  1) 结构化元数据  datePublished / article:published_time / og:* / JSON-LD uploadDate
  2) 正文 dateline 2026年3月16日 / 2026-03-16 / "太平洋时间…" / English month
  3) URL 内嵌日期  /2026/03/16/ , /20260316/ , -2026-03-16-

Usage:
  extract_publish_date.py <url> [<url> ...]
      对每个 URL 跑 anysearch extract，解析并返回全网最早发布时间 + 来源 URL。
  extract_publish_date.py --content-file <md> --url <url>
      不联网：解析已抓好的 markdown 文本（配合该 url 的 URL 日期）。

Output (JSON):
  {"earliestPublishTime": "YYYY-MM-DD"|"YYYY-MM-DDTHH:MM:SS…"|null,
   "earliestSourceUrl": "<url>"|null,
   "perUrl": [{"url":…, "date":…, "method":"meta|dateline|url|null"}],
   "note": "…"}

退出码：0 = 取到至少一个日期；1 = 全部未取到（调用方应填 待验证）。
"""
import json
import os
import re
import subprocess
import sys

ANYSEARCH_CLI = os.path.expanduser(
    "~/.kimi_openclaw/workspace/skills/anysearch/scripts/anysearch_cli.js"
)

MONTHS = {
    m: i + 1
    for i, m in enumerate(
        [
            "january", "february", "march", "april", "may", "june",
            "july", "august", "september", "october", "november", "december",
        ]
    )
}
MONTHS.update({m[:3]: i for m, i in MONTHS.items()})


def _iso(y, m, d, tail=""):
    try:
        y, m, d = int(y), int(m), int(d)
    except (TypeError, ValueError):
        return None
    if not (2000 <= y <= 2100 and 1 <= m <= 12 and 1 <= d <= 31):
        return None
    return f"{y:04d}-{m:02d}-{d:02d}{tail}"


def _norm_iso_string(s):
    """Normalize an ISO-ish metadata timestamp to YYYY-MM-DD[THH:MM:SS]."""
    m = re.match(r"\s*(\d{4})-(\d{1,2})-(\d{1,2})(?:[T ](\d{2}:\d{2}(?::\d{2})?))?", s)
    if not m:
        return None
    tail = "T" + m.group(4) if m.group(4) else ""
    return _iso(m.group(1), m.group(2), m.group(3), tail)


def date_from_meta(text):
    """Most reliable: structured publish metadata embedded in the page."""
    patterns = [
        r'"datePublished"\s*:\s*"([^"]+)"',
        r'"uploadDate"\s*:\s*"([^"]+)"',
        r'(?:article:published_time|og:published_time|pubdate|publishdate)["\']?\s*[,:]?\s*content=["\']([^"\']+)["\']',
        r'(?:article:published_time|og:published_time)["\']?\s*[:=]\s*["\']([^"\']+)["\']',
    ]
    for pat in patterns:
        for hit in re.findall(pat, text, re.I):
            iso = _norm_iso_string(hit)
            if iso:
                return iso
    return None


def date_from_dateline(text):
    """Datelines / inline dates. Return the EARLIEST plausible one near the top."""
    # Only scan the leading chunk where datelines live (avoid body noise like
    # "回顾 2019 年" deep in the article). Top ~1500 chars.
    head = text[:1500]
    found = []
    # 中文 2026年3月16日
    for y, m, d in re.findall(r"(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", head):
        iso = _iso(y, m, d)
        if iso:
            found.append(iso)
    # ISO / 2026-03-16 / 2026/03/16 / 2026.03.16
    for y, m, d in re.findall(r"(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})", head):
        iso = _iso(y, m, d)
        if iso:
            found.append(iso)
    # English: March 16, 2026  /  Mar. 16 2026
    for mon, d, y in re.findall(r"([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s+(20\d{2})", head):
        mi = MONTHS.get(mon.lower())
        if mi:
            iso = _iso(y, mi, d)
            if iso:
                found.append(iso)
    # English: 16 March 2026
    for d, mon, y in re.findall(r"(\d{1,2})\s+([A-Za-z]{3,9})\.?\s+(20\d{2})", head):
        mi = MONTHS.get(mon.lower())
        if mi:
            iso = _iso(y, mi, d)
            if iso:
                found.append(iso)
    return min(found) if found else None


def date_from_url(url):
    """URL-embedded date: /2026/03/16/ , /20260316/ , -2026-03-16-."""
    m = re.search(r"/(20\d{2})/(\d{1,2})/(\d{1,2})(?:/|\b)", url)
    if m:
        return _iso(*m.groups())
    # 紧凑 8 位日期，前后不被其它数字包裹（允许后接字母，如 qq /20260616A07...）
    m = re.search(r"(?<![0-9])(20\d{2})(\d{2})(\d{2})(?![0-9])", url)
    if m:
        return _iso(*m.groups())
    m = re.search(r"(20\d{2})[-.](\d{2})[-.](\d{2})", url)
    if m:
        return _iso(*m.groups())
    return None


def resolve_one(url, content=None):
    """Best publish date for a single source, by reliability tier."""
    if content:
        d = date_from_meta(content)
        if d:
            return d, "meta"
        d = date_from_dateline(content)
        if d:
            return d, "dateline"
    d = date_from_url(url)
    if d:
        return d, "url"
    return None, "null"


def run_extract(url):
    if not os.path.exists(ANYSEARCH_CLI):
        return None
    try:
        out = subprocess.run(
            ["node", ANYSEARCH_CLI, "extract", url],
            capture_output=True, text=True, timeout=60,
        )
        return out.stdout or ""
    except Exception:
        return None


def main():
    args = sys.argv[1:]
    content_file = None
    fixed_url = None
    urls = []
    i = 0
    while i < len(args):
        if args[i] == "--content-file":
            content_file = args[i + 1]; i += 2
        elif args[i] == "--url":
            fixed_url = args[i + 1]; i += 2
        else:
            urls.append(args[i]); i += 1

    per = []
    if content_file:
        try:
            content = open(content_file, encoding="utf-8", errors="ignore").read()
        except Exception as exc:
            print(json.dumps({"error": f"content-file: {exc}"}, ensure_ascii=False))
            return 2
        url = fixed_url or (urls[0] if urls else "")
        d, method = resolve_one(url, content)
        per.append({"url": url, "date": d, "method": method})
    else:
        if not urls:
            print(__doc__, file=sys.stderr)
            return 2
        for url in urls:
            content = run_extract(url)
            d, method = resolve_one(url, content)
            per.append({"url": url, "date": d, "method": method})

    dated = [p for p in per if p["date"]]
    if dated:
        best = min(dated, key=lambda p: p["date"])
        result = {
            "earliestPublishTime": best["date"],
            "earliestSourceUrl": best["url"],
            "perUrl": per,
            "note": f"earliest of {len(dated)}/{len(per)} dated source(s); method={best['method']}",
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print(json.dumps({
        "earliestPublishTime": None,
        "earliestSourceUrl": None,
        "perUrl": per,
        "note": "no date resolved from any source — caller should fill 待验证",
    }, ensure_ascii=False, indent=2))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
