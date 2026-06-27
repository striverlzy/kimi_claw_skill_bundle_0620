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


def normalize_target(target):
    """Stable cache key piece from a free-text target.

    Stocks usually arrive as a code (NVDA / 601318) or a stable name; we lowercase,
    strip spaces/punctuation, and hash so '中国平安' and ' 中国平安 ' collide while
    staying human-readable via a short prefix.
    """
    raw = target.strip().lower()
    collapsed = re.sub(r"\s+", "", raw)
    digest = hashlib.sha1(collapsed.encode("utf-8")).hexdigest()[:12]
    prefix = re.sub(r"[^0-9a-z一-鿿]+", "-", raw)[:40].strip("-")
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
