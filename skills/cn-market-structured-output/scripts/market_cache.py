#!/usr/bin/env python3
"""Differentiated-TTL cache for kimi-market-v1 analysis outputs.

Goal: within a freshness window, the same target + mode returns the previous
result directly (skip search + generation). Financial data is time-sensitive,
so TTL is per-mode, and us_stock_options is market-aware (short intraday, valid
until next open when the market is closed).

Usage:
  market_cache.py lookup <mode> <target>            # prints {"hit":bool,...}; exit 0 hit / 1 miss
  market_cache.py store  <mode> <target> <json>     # store a final JSON file
  market_cache.py path   <mode> <target>            # print the cache file path

Cache dir: $KIMI_MARKET_CACHE_DIR or ~/.kimi_openclaw/workspace/cache
"""
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

CACHE_DIR = Path(
    os.environ.get(
        "KIMI_MARKET_CACHE_DIR",
        Path.home() / ".kimi_openclaw" / "workspace" / "cache",
    )
)

# Per-mode TTL in seconds. us_stock_options is handled specially (market-aware).
TTL_SECONDS = {
    "catalyst": 24 * 3600,
    "single_stock": 24 * 3600,
    "sector_tree": 24 * 3600,
    "sector_stock_map": 24 * 3600,
}
DEFAULT_TTL = 24 * 3600
US_OPTIONS_INTRADAY_TTL = 3600  # 1h while the US market is open


# 噪声词：不同问法（"分析XX最新刷新" vs "XX"）必须归一到同一缓存键
_NOISE = re.compile(
    r"(分析|最新|刷新|重新分析|重新|请帮我|帮我|请|一下|的|股票|个股|走势|"
    r"怎么样|如何|看看|研报|深度|价值|投资|价格|目标价|是否值得买|值得买|买入|"
    r"analyze|analysis|stock|please|the)",
    re.IGNORECASE,
)


def normalize_target(target):
    """Stable cache key from a free-text target — phrasing-invariant.

    优先提取**股票代码**作为 canonical key（最稳定），这样
    '分析三花智控(002050)最新刷新' / '002050' / '三花智控 002050' 命中同一缓存：
      1) A股 6 位代码        -> 该代码
      2) 港股带前导 0 的代码 -> 该代码（避开 2024/2025 这类年份）
      3) 纯英文 ticker(≤5)   -> 大写（美股，如 NVDA）
      4) 否则用去噪+去标点的名称做短 hash（'中国平安' 与 ' 中国平安 ' 仍碰撞）
    """
    raw = (target or "").strip()
    # 1) A 股 6 位代码（年份不会是 6 位，安全）
    m = re.search(r"(?<![0-9])[036]\d{5}(?![0-9])", raw) or re.search(r"(?<![0-9])\d{6}(?![0-9])", raw)
    if m:
        return m.group(0)
    # 2) 港股带前导 0 的代码（0700/00700），年份 20xx/19xx 不以 0 开头
    m = re.search(r"(?<![0-9])0\d{3,4}(?![0-9])", raw)
    if m:
        return m.group(0)
    # 3) 去噪后若是 ≤5 位纯英文 ticker（美股）
    cleaned = _NOISE.sub("", raw)
    letters = re.sub(r"[^A-Za-z]", "", cleaned)
    if letters and len(letters) <= 5 and not re.search(r"[一-鿿]", cleaned):
        return letters.upper()
    # 4) 名称兜底：去噪 + 去标点 + lower，再短 hash（可读前缀 + 防碰撞）
    name = re.sub(r"[\s\(\)（）【】\[\]，,。.\-_/、:：]+", "", _NOISE.sub("", raw)).lower()
    if not name:
        name = re.sub(r"\s+", "", raw.lower())
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:8]
    prefix = re.sub(r"[^0-9a-z一-鿿]+", "", name)[:20]
    return f"{prefix}-{digest}" if prefix else digest


def cache_path(mode, target):
    return CACHE_DIR / mode / f"{normalize_target(target)}.json"


def _us_market_open(dt_et):
    """True if dt (US/Eastern) is within regular session 09:30-16:00, Mon-Fri.

    Holiday calendar is intentionally omitted (documented limitation); on a holiday
    this only makes the cache slightly more conservative (treats it as a short day).
    """
    if dt_et.weekday() >= 5:
        return False
    minutes = dt_et.hour * 60 + dt_et.minute
    return 9 * 60 + 30 <= minutes < 16 * 60


def _et_now_and_cached(cached_epoch):
    try:
        from zoneinfo import ZoneInfo

        et = ZoneInfo("America/New_York")
    except Exception:
        et = timezone.utc  # fallback: treat as UTC (approximate)
    return datetime.now(et), datetime.fromtimestamp(cached_epoch, et)


def is_fresh(mode, cached_epoch):
    age = time.time() - cached_epoch
    if mode == "us_stock_options":
        now_et, cached_et = _et_now_and_cached(cached_epoch)
        if _us_market_open(now_et):
            return age < US_OPTIONS_INTRADAY_TTL  # intraday: 1h
        # Market closed now: valid as long as no new session opened since caching,
        # i.e. the cache was written during the same closed/overnight window.
        if _us_market_open(cached_et):
            return False  # cached intraday, now closed -> a session boundary passed
        # both closed: fresh only if same calendar "market day boundary" (< 20h guard)
        return age < 20 * 3600
    ttl = TTL_SECONDS.get(mode, DEFAULT_TTL)
    return age < ttl


def lookup(mode, target):
    path = cache_path(mode, target)
    if not path.exists():
        return None
    try:
        meta = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    cached_epoch = meta.get("_cachedAt", 0)
    if not is_fresh(mode, cached_epoch):
        return None
    doc = meta.get("doc")
    if isinstance(doc, dict):
        qc = doc.get("qualityControl")
        if not isinstance(qc, dict):
            qc = {}
            doc["qualityControl"] = qc
        qc["servedFromCache"] = True
        qc["cacheAgeSeconds"] = int(time.time() - cached_epoch)
        qc["cachedAt"] = meta.get("_cachedAtIso")
    return doc


def store(mode, target, json_file):
    path = cache_path(mode, target)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = json.loads(Path(json_file).read_text(encoding="utf-8"))
    now = time.time()
    meta = {
        "_cachedAt": now,
        "_cachedAtIso": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "target": target,
        "doc": doc,
    }
    path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    return path


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__, file=sys.stderr)
        return 2
    op = args[0]
    if op == "lookup" and len(args) == 3:
        doc = lookup(args[1], args[2])
        if doc is None:
            print(json.dumps({"hit": False}, ensure_ascii=False))
            return 1
        print(json.dumps({"hit": True, "doc": doc}, ensure_ascii=False))
        return 0
    if op == "store" and len(args) == 4:
        path = store(args[1], args[2], args[3])
        print(json.dumps({"stored": str(path)}, ensure_ascii=False))
        return 0
    if op == "path" and len(args) == 3:
        print(str(cache_path(args[1], args[2])))
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
