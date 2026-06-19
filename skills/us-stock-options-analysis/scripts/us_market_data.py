#!/usr/bin/env python3
"""拉取美股 SEC / 行情 / 期权链结构化数据，供 us-stock-options-analysis 使用。"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from typing import Any

SEC_USER_AGENT = "KimiClawResearch contact@example.com"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
REQUEST_TIMEOUT = 20
MAX_RETRIES = 2


def load_env() -> None:
    """从 skill 根目录 .env 加载 key。"""
    env_path = os.path.join(SKILL_DIR, ".env")
    if not os.path.isfile(env_path):
        return
    with open(env_path, "r", encoding="utf-8-sig") as handle:
        for raw in handle:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip().lstrip("\ufeff")
            value = value.strip().strip("\"'")
            if key and value:
                os.environ[key] = value


def http_get_json(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    params: dict[str, str] | None = None,
) -> dict[str, Any]:
    """带重试的 GET JSON 请求。"""
    if params:
        query = urllib.parse.urlencode(params)
        url = f"{url}&{query}" if "?" in url else f"{url}?{query}"

    req_headers = {"Accept": "application/json", "User-Agent": SEC_USER_AGENT}
    if headers:
        req_headers.update(headers)

    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            request = urllib.request.Request(url, headers=req_headers)
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001 - 统一重试
            last_error = exc
            if attempt < MAX_RETRIES:
                time.sleep(0.6 * (attempt + 1))
    raise RuntimeError(f"请求失败: {url} ({last_error})")


def normalize_symbol(symbol: str) -> str:
    """统一为大写 ticker，去掉 .US 后缀。"""
    cleaned = symbol.strip().upper()
    if cleaned.endswith(".US"):
        cleaned = cleaned[:-3]
    return cleaned


def iso_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def lookup_cik(symbol: str) -> str | None:
    """通过 SEC company_tickers.json 查 CIK。"""
    data = http_get_json(
        "https://www.sec.gov/files/company_tickers.json",
        headers={"User-Agent": SEC_USER_AGENT},
    )
    for item in data.values():
        if str(item.get("ticker", "")).upper() == symbol:
            return str(item.get("cik_str", "")).zfill(10)
    return None


def fetch_sec_company(cik: str) -> dict[str, Any]:
    """SEC submissions + companyfacts。"""
    cik10 = cik.zfill(10)
    submissions = http_get_json(
        f"https://data.sec.gov/submissions/CIK{cik10}.json",
        headers={"User-Agent": SEC_USER_AGENT},
    )
    recent = submissions.get("filings", {}).get("recent", {})
    forms = recent.get("form", []) or []
    dates = recent.get("filingDate", []) or []
    accessions = recent.get("accessionNumber", []) or []
    recent_filings = []
    for idx in range(min(8, len(forms))):
        recent_filings.append(
            {
                "form": forms[idx],
                "filingDate": dates[idx] if idx < len(dates) else None,
                "accessionNumber": accessions[idx] if idx < len(accessions) else None,
            }
        )

    fundamentals: dict[str, Any] = {
        "revenue": "待验证",
        "netIncome": "待验证",
        "assets": "待验证",
        "equity": "待验证",
        "source": "SEC companyfacts",
    }
    try:
        facts = http_get_json(
            f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json",
            headers={"User-Agent": SEC_USER_AGENT},
        )
        gaap = facts.get("facts", {}).get("us-gaap", {})
        revenue_keys = [
            "Revenues",
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "SalesRevenueNet",
        ]
        for key in revenue_keys:
            picked = _latest_usd_fact(gaap, key)
            if picked:
                fundamentals["revenue"] = picked
                break
        for key, field in [
            ("NetIncomeLoss", "netIncome"),
            ("Assets", "assets"),
            ("StockholdersEquity", "equity"),
        ]:
            picked = _latest_usd_fact(gaap, key)
            if picked:
                fundamentals[field] = picked
    except Exception as exc:  # noqa: BLE001
        fundamentals["error"] = str(exc)

    return {
        "name": submissions.get("name"),
        "cik": cik10,
        "tickers": submissions.get("tickers", []),
        "recentFilings": recent_filings,
        "fundamentals": fundamentals,
    }


def _latest_usd_fact(gaap: dict[str, Any], key: str) -> dict[str, Any] | None:
    node = gaap.get(key)
    if not node:
        return None
    rows = node.get("units", {}).get("USD", [])
    if not rows:
        return None
    latest = max(rows, key=lambda row: row.get("end", ""))
    return {
        "value": latest.get("val"),
        "end": latest.get("end"),
        "form": latest.get("form"),
        "unit": "USD",
    }


def fetch_polygon_ticker(symbol: str, api_key: str) -> dict[str, Any]:
    return http_get_json(
        f"https://api.polygon.io/v3/reference/tickers/{symbol}",
        params={"apiKey": api_key},
    )


def fetch_polygon_prev_close(symbol: str, api_key: str) -> dict[str, Any] | None:
    data = http_get_json(
        f"https://api.polygon.io/v2/aggs/ticker/{symbol}/prev",
        params={"apiKey": api_key},
    )
    results = data.get("results") or []
    if not results:
        return None
    row = results[0]
    return {
        "price": row.get("c"),
        "open": row.get("o"),
        "high": row.get("h"),
        "low": row.get("l"),
        "volume": row.get("v"),
        "vwap": row.get("vw"),
        "marketTime": _ms_to_iso(row.get("t")),
        "currency": "USD",
        "source": "polygon_prev",
    }


def fetch_yahoo_quote(symbol: str) -> dict[str, Any] | None:
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{urllib.parse.quote(symbol)}?range=1d&interval=1m"
    )
    data = http_get_json(url, headers={"User-Agent": "Mozilla/5.0"})
    results = data.get("chart", {}).get("result") or []
    if not results:
        return None
    meta = results[0].get("meta", {})
    return {
        "price": meta.get("regularMarketPrice"),
        "previousClose": meta.get("previousClose") or meta.get("chartPreviousClose"),
        "currency": meta.get("currency", "USD"),
        "exchangeName": meta.get("exchangeName"),
        "marketTime": _sec_to_iso(meta.get("regularMarketTime")),
        "source": "yahoo_chart",
    }


def fetch_tradier_chain(symbol: str, token: str, *, sandbox: bool = False) -> dict[str, Any]:
    base = "https://sandbox.tradier.com" if sandbox else "https://api.tradier.com"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    quote = http_get_json(f"{base}/v1/markets/quotes", headers=headers, params={"symbols": symbol})
    expirations = http_get_json(
        f"{base}/v1/markets/options/expirations",
        headers=headers,
        params={"symbol": symbol},
    )
    exp_list = expirations.get("expirations", {}).get("date", []) or []
    if isinstance(exp_list, str):
        exp_list = [exp_list]

    spot = _extract_tradier_last(quote, symbol)
    near, medium = pick_target_expirations(exp_list)
    chains: dict[str, Any] = {}
    for label, exp in [("nearTerm", near), ("mediumTerm", medium)]:
        if not exp:
            continue
        chain = http_get_json(
            f"{base}/v1/markets/options/chains",
            headers=headers,
            params={"symbol": symbol, "expiration": exp, "greeks": "true"},
        )
        chains[label] = {"expiration": exp, "raw": chain}

    contracts = []
    for payload in chains.values():
        contracts.extend(_normalize_tradier_contracts(payload.get("raw", {})))

    metrics = compute_options_metrics(contracts, spot)
    return {
        "provider": "tradier",
        "dataAvailable": bool(contracts),
        "spotPrice": spot,
        "expirations": exp_list,
        "selectedExpirations": {"nearTerm": near, "mediumTerm": medium},
        "metrics": metrics,
        "warnings": [] if contracts else ["Tradier 未返回期权合约"],
    }


def fetch_polygon_options_snapshot(symbol: str, api_key: str) -> dict[str, Any]:
    try:
        data = http_get_json(
            f"https://api.polygon.io/v3/snapshot/options/{symbol}",
            params={"apiKey": api_key},
        )
    except RuntimeError as exc:
        message = str(exc)
        if "NOT_AUTHORIZED" in message or "403" in message:
            return {
                "provider": "polygon",
                "dataAvailable": False,
                "warnings": [
                    "Polygon 免费档通常不含 options snapshot（OI/IV/Greeks），需升级 Massive 付费计划。"
                ],
            }
        raise

    if data.get("status") == "NOT_AUTHORIZED":
        return {
            "provider": "polygon",
            "dataAvailable": False,
            "warnings": [data.get("message", "Polygon options 未授权")],
        }

    results = data.get("results") or []
    contracts = _normalize_polygon_snapshot(results)
    spot = _infer_spot_from_contracts(contracts)
    metrics = compute_options_metrics(contracts, spot)
    return {
        "provider": "polygon",
        "dataAvailable": bool(contracts),
        "spotPrice": spot,
        "metrics": metrics,
        "warnings": [] if contracts else ["Polygon snapshot 为空"],
    }


def fetch_alpha_vantage_options(symbol: str, api_key: str) -> dict[str, Any]:
    data = http_get_json(
        "https://www.alphavantage.co/query",
        params={
            "function": "REALTIME_OPTIONS",
            "symbol": symbol,
            "require_greeks": "true",
            "apikey": api_key,
        },
    )
    if "Note" in data or "Information" in data:
        return {
            "provider": "alpha_vantage",
            "dataAvailable": False,
            "warnings": [data.get("Note") or data.get("Information") or "Alpha Vantage 限流或未授权"],
        }
    contracts = _normalize_alpha_vantage_contracts(data)
    if _looks_like_demo_data(contracts):
        return {
            "provider": "alpha_vantage",
            "dataAvailable": False,
            "warnings": ["Alpha Vantage 返回 demo/占位期权数据，需 premium 档 REALTIME_OPTIONS"],
        }
    spot = _infer_spot_from_contracts(contracts)
    metrics = compute_options_metrics(contracts, spot)
    return {
        "provider": "alpha_vantage",
        "dataAvailable": bool(contracts),
        "spotPrice": spot,
        "metrics": metrics,
        "warnings": [] if contracts else ["Alpha Vantage 未返回期权合约"],
    }


def pick_target_expirations(expirations: list[str]) -> tuple[str | None, str | None]:
    """选择近端 5-10 天、中期 25-35 天到期日。"""
    today = date.today()
    parsed: list[tuple[date, str]] = []
    for raw in expirations:
        try:
            exp_date = date.fromisoformat(raw)
        except ValueError:
            continue
        delta = (exp_date - today).days
        if delta >= 0:
            parsed.append((exp_date, raw))
    parsed.sort(key=lambda item: item[0])

    near = _pick_in_range(parsed, 5, 10) or (parsed[0][1] if parsed else None)
    medium = _pick_in_range(parsed, 25, 35) or (
        parsed[min(1, len(parsed) - 1)][1] if len(parsed) > 1 else near
    )
    return near, medium


def _pick_in_range(items: list[tuple[date, str]], low: int, high: int) -> str | None:
    today = date.today()
    candidates = []
    for exp_date, raw in items:
        delta = (exp_date - today).days
        if low <= delta <= high:
            candidates.append((abs(delta - (low + high) / 2), raw))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def compute_options_metrics(contracts: list[dict[str, Any]], spot: float | None) -> dict[str, Any]:
    """基于期权链计算核心指标；缺数据时返回待验证。"""
    if not contracts or not spot:
        return _empty_metrics()

    calls = [c for c in contracts if c.get("type") == "call"]
    puts = [c for c in contracts if c.get("type") == "put"]
    if not calls and not puts:
        return _empty_metrics()

    call_oi = sum(_num(c.get("openInterest")) for c in calls)
    put_oi = sum(_num(c.get("openInterest")) for c in puts)
    call_vol = sum(_num(c.get("volume")) for c in calls)
    put_vol = sum(_num(c.get("volume")) for c in puts)

    put_call_ratio = {
        "openInterest": _safe_ratio(put_oi, call_oi),
        "volume": _safe_ratio(put_vol, call_vol),
    }

    atm = min(contracts, key=lambda c: abs(_num(c.get("strike"), spot) - spot))
    atm_iv_values = [v for v in [_num(atm.get("iv")) for _ in [0]] if v > 0]
    call_atm = min(calls, key=lambda c: abs(_num(c.get("strike"), spot) - spot), default=None)
    put_atm = min(puts, key=lambda c: abs(_num(c.get("strike"), spot) - spot), default=None)
    ivs = [x for x in [_num(call_atm.get("iv")) if call_atm else 0, _num(put_atm.get("iv")) if put_atm else 0] if x > 0]
    atm_iv = round(sum(ivs) / len(ivs), 4) if ivs else "待验证"

    call_wall = _max_oi_strike(calls)
    put_wall = _max_oi_strike(puts)
    max_pain = _calc_max_pain(calls, puts, spot)

    otm_puts = sorted([c for c in puts if _num(c.get("strike")) < spot * 0.95], key=lambda c: _num(c.get("strike")), reverse=True)
    otm_calls = sorted([c for c in calls if _num(c.get("strike")) > spot * 1.05], key=lambda c: _num(c.get("strike")))
    skew = "待验证"
    if otm_puts and otm_calls:
        put_iv = _num(otm_puts[0].get("iv"))
        call_iv = _num(otm_calls[0].get("iv"))
        if put_iv > 0 and call_iv > 0:
            skew = round(put_iv - call_iv, 4)

    gamma_values = [_num(c.get("gamma")) * _num(c.get("openInterest")) * 100 for c in contracts if _num(c.get("gamma")) > 0]
    gamma_exposure = round(sum(gamma_values) * spot, 2) if gamma_values else "待验证"

    return {
        "putCallRatio": put_call_ratio,
        "atmIv": atm_iv,
        "ivRank": "待验证",
        "maxPain": max_pain,
        "callWall": call_wall,
        "putWall": put_wall,
        "gammaExposure": gamma_exposure,
        "skew": skew,
        "contractCount": len(contracts),
    }


def _empty_metrics() -> dict[str, Any]:
    return {
        "putCallRatio": {"openInterest": "待验证", "volume": "待验证"},
        "atmIv": "待验证",
        "ivRank": "待验证",
        "maxPain": "待验证",
        "callWall": "待验证",
        "putWall": "待验证",
        "gammaExposure": "待验证",
        "skew": "待验证",
        "contractCount": 0,
    }


def _normalize_tradier_contracts(raw: dict[str, Any]) -> list[dict[str, Any]]:
    options = raw.get("options", {}).get("option", []) or []
    if isinstance(options, dict):
        options = [options]
    normalized = []
    for opt in options:
        greeks = opt.get("greeks", {}) or {}
        normalized.append(
            {
                "type": str(opt.get("option_type", "")).lower(),
                "strike": _num(opt.get("strike")),
                "expiration": opt.get("expiration_date"),
                "openInterest": _num(opt.get("open_interest")),
                "volume": _num(opt.get("volume")),
                "iv": _num(greeks.get("mid_iv") or opt.get("implied_volatility")),
                "gamma": _num(greeks.get("gamma")),
            }
        )
    return normalized


def _normalize_polygon_snapshot(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    for item in results:
        details = item.get("details", {}) or {}
        day = item.get("day", {}) or {}
        greeks = item.get("greeks", {}) or {}
        normalized.append(
            {
                "type": str(details.get("contract_type", "")).lower(),
                "strike": _num(details.get("strike_price")),
                "expiration": details.get("expiration_date"),
                "openInterest": _num(item.get("open_interest")),
                "volume": _num(day.get("volume")),
                "iv": _num(item.get("implied_volatility")),
                "gamma": _num(greeks.get("gamma")),
            }
        )
    return normalized


def _normalize_alpha_vantage_contracts(data: dict[str, Any]) -> list[dict[str, Any]]:
    rows = data.get("data") or data.get("option_chain") or []
    normalized = []
    for row in rows:
        normalized.append(
            {
                "type": str(row.get("type") or row.get("option_type") or "").lower(),
                "strike": _num(row.get("strike") or row.get("strike_price")),
                "expiration": row.get("expiration") or row.get("expiration_date"),
                "openInterest": _num(row.get("open_interest")),
                "volume": _num(row.get("volume")),
                "iv": _num(row.get("implied_volatility") or row.get("iv")),
                "gamma": _num(row.get("gamma")),
            }
        )
    return normalized


def _looks_like_demo_data(contracts: list[dict[str, Any]]) -> bool:
    for contract in contracts[:5]:
        exp = str(contract.get("expiration", ""))
        if "2099" in exp or "XX" in exp.upper():
            return True
    return False


def _calc_max_pain(calls: list[dict[str, Any]], puts: list[dict[str, Any]], spot: float) -> float | str:
    strikes = sorted({round(_num(c.get("strike")), 2) for c in calls + puts if _num(c.get("strike")) > 0})
    if not strikes:
        return "待验证"

    call_map = {round(_num(c.get("strike")), 2): _num(c.get("openInterest")) for c in calls}
    put_map = {round(_num(c.get("strike")), 2): _num(c.get("openInterest")) for c in puts}

    best_strike = strikes[0]
    best_pain = float("inf")
    for strike in strikes:
        pain = 0.0
        for call_strike, oi in call_map.items():
            if strike > call_strike:
                pain += (strike - call_strike) * oi
        for put_strike, oi in put_map.items():
            if strike < put_strike:
                pain += (put_strike - strike) * oi
        if pain < best_pain:
            best_pain = pain
            best_strike = strike
    return best_strike


def _max_oi_strike(contracts: list[dict[str, Any]]) -> float | str:
    if not contracts:
        return "待验证"
    best = max(contracts, key=lambda c: _num(c.get("openInterest")))
    strike = _num(best.get("strike"))
    return strike if strike > 0 else "待验证"


def _extract_tradier_last(quote: dict[str, Any], symbol: str) -> float | None:
    quotes = quote.get("quotes", {}).get("quote")
    if isinstance(quotes, list):
        item = quotes[0] if quotes else {}
    else:
        item = quotes or {}
    for key in ("last", "close", "bid", "ask"):
        value = _num(item.get(key))
        if value > 0:
            return value
    return None


def _infer_spot_from_contracts(contracts: list[dict[str, Any]]) -> float | None:
    strikes = [_num(c.get("strike")) for c in contracts if _num(c.get("strike")) > 0]
    if not strikes:
        return None
    return sorted(strikes)[len(strikes) // 2]


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_ratio(numerator: float, denominator: float) -> float | str:
    if denominator <= 0:
        return "待验证"
    return round(numerator / denominator, 4)


def _ms_to_iso(value: Any) -> str | None:
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc).isoformat()
    except (TypeError, ValueError):
        return None


def _sec_to_iso(value: Any) -> str | None:
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc).isoformat()
    except (TypeError, ValueError):
        return None


def build_payload(symbol: str) -> dict[str, Any]:
    """组装完整数据包。"""
    warnings: list[str] = []
    sources = {"sec": "skipped", "quote": "error", "options": "unavailable"}

    company: dict[str, Any] = {}
    quote: dict[str, Any] = {
        "price": None,
        "previousClose": None,
        "currency": "USD",
        "marketTime": None,
        "marketCap": None,
        "source": None,
    }
    fundamentals = {
        "revenue": "待验证",
        "netIncome": "待验证",
        "assets": "待验证",
        "equity": "待验证",
        "source": "SEC companyfacts",
    }
    options: dict[str, Any] = {
        "dataAvailable": False,
        "provider": "unavailable",
        "expirations": [],
        "putCallRatio": "待验证",
        "atmIv": "待验证",
        "ivRank": "待验证",
        "maxPain": "待验证",
        "callWall": "待验证",
        "putWall": "待验证",
        "gammaExposure": "待验证",
        "skew": "待验证",
    }

    cik = lookup_cik(symbol)
    if cik:
        try:
            sec = fetch_sec_company(cik)
            company = {
                "name": sec.get("name"),
                "cik": sec.get("cik"),
                "tickers": sec.get("tickers", []),
                "recentFilings": sec.get("recentFilings", []),
            }
            fundamentals = sec.get("fundamentals", fundamentals)
            sources["sec"] = "ok"
        except Exception as exc:  # noqa: BLE001
            sources["sec"] = "error"
            warnings.append(f"SEC 拉取失败: {exc}")
    else:
        sources["sec"] = "error"
        warnings.append(f"未找到 {symbol} 的 SEC CIK")

    polygon_key = os.environ.get("POLYGON_API_KEY", "").strip()
    if polygon_key:
        try:
            ticker = fetch_polygon_ticker(symbol, polygon_key)
            result = ticker.get("results") or {}
            quote["marketCap"] = result.get("market_cap")
            if not company.get("name"):
                company["name"] = result.get("name")
            if not company.get("cik") and result.get("cik"):
                company["cik"] = str(result.get("cik")).zfill(10)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"Polygon ticker 详情失败: {exc}")

        try:
            polygon_quote = fetch_polygon_prev_close(symbol, polygon_key)
            if polygon_quote:
                quote.update(polygon_quote)
                sources["quote"] = "polygon"
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"Polygon 行情失败: {exc}")

    if quote.get("price") is None:
        try:
            yahoo_quote = fetch_yahoo_quote(symbol)
            if yahoo_quote:
                quote.update(yahoo_quote)
                sources["quote"] = yahoo_quote.get("source", "yahoo_chart")
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"Yahoo chart 失败: {exc}")

    tradier_token = os.environ.get("TRADIER_TOKEN", "").strip()
    alpha_key = os.environ.get("ALPHA_VANTAGE_API_KEY", "").strip()
    options_result: dict[str, Any] | None = None

    if tradier_token:
        try:
            options_result = fetch_tradier_chain(symbol, tradier_token)
            sources["options"] = "tradier"
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"Tradier 期权链失败: {exc}")
    elif polygon_key:
        try:
            options_result = fetch_polygon_options_snapshot(symbol, polygon_key)
            sources["options"] = "polygon"
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"Polygon 期权链失败: {exc}")
    elif alpha_key:
        try:
            options_result = fetch_alpha_vantage_options(symbol, alpha_key)
            sources["options"] = "alpha_vantage"
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"Alpha Vantage 期权链失败: {exc}")

    if options_result:
        options["provider"] = options_result.get("provider", "unavailable")
        options["dataAvailable"] = bool(options_result.get("dataAvailable"))
        options["expirations"] = options_result.get("expirations", [])
        warnings.extend(options_result.get("warnings", []))
        metrics = options_result.get("metrics", {})
        if options["dataAvailable"]:
            options["putCallRatio"] = metrics.get("putCallRatio")
            options["atmIv"] = metrics.get("atmIv")
            options["ivRank"] = metrics.get("ivRank")
            options["maxPain"] = metrics.get("maxPain")
            options["callWall"] = metrics.get("callWall")
            options["putWall"] = metrics.get("putWall")
            options["gammaExposure"] = metrics.get("gammaExposure")
            options["skew"] = metrics.get("skew")
            options["selectedExpirations"] = options_result.get("selectedExpirations")
            options["contractCount"] = metrics.get("contractCount")
        else:
            warnings.append("结构化期权链不可用，options.dataAvailable=false")

    return {
        "symbol": symbol,
        "asOf": iso_now(),
        "sources": sources,
        "company": company,
        "quote": quote,
        "fundamentals": fundamentals,
        "options": options,
        "warnings": warnings,
    }


def main() -> int:
    load_env()
    parser = argparse.ArgumentParser(description="拉取美股 SEC/行情/期权结构化数据")
    parser.add_argument("symbol", help="美股 ticker，如 NVDA")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    symbol = normalize_symbol(args.symbol)
    if not re.fullmatch(r"[A-Z][A-Z0-9.\-]*", symbol):
        print(f"非法 ticker: {args.symbol}", file=sys.stderr)
        return 2

    payload = build_payload(symbol)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
