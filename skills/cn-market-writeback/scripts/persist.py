#!/usr/bin/env python3
import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}
SUPPORTED_MODES = {
    "sector_tree",
    "sector_stock_map",
    "news_event",
    "memo_research",
    "single_stock",
}


def load_json(path):
    if path == "-":
        return json.loads(sys.stdin.read())
    return json.loads(Path(path).read_text(encoding="utf-8"))


def nested(data, *keys):
    cur = data
    for key in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def resolve_url(envelope, cli_url):
    return (
        nested(envelope, "persistContract", "ingest", "url")
        or nested(envelope, "ingest", "url")
        or cli_url
        or ""
    ).strip()


def resolve_token(envelope, cli_token):
    return (
        nested(envelope, "persistContract", "ingest", "token")
        or nested(envelope, "ingest", "token")
        or cli_token
        or ""
    ).strip()


def validate_envelope(envelope):
    errors = []
    if not isinstance(envelope, dict):
        return ["root must be an object"]
    if envelope.get("schemaVersion") != "kimi-market-v1":
        errors.append("schemaVersion must be kimi-market-v1")
    mode = envelope.get("mode")
    if mode not in SUPPORTED_MODES:
        errors.append("mode must be a supported China-market mode")
    contract = envelope.get("persistContract")
    if not isinstance(contract, dict):
        errors.append("persistContract must be present")
    else:
        if contract.get("bizType") != mode:
            errors.append("persistContract.bizType must equal mode")
        if not contract.get("taskNo"):
            errors.append("persistContract.taskNo is required")
    return errors


def build_body(envelope):
    contract = envelope.get("persistContract") or {}
    return {
        "taskNo": contract.get("taskNo") or envelope.get("taskNo"),
        "bizType": contract.get("bizType") or envelope.get("mode"),
        "bizId": contract.get("bizId") if "bizId" in contract else envelope.get("bizId"),
        "result": envelope,
    }


def post_json(url, token, body, timeout):
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json",
    }
    if token:
        headers["X-Ingest-Token"] = token
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        text = resp.read().decode("utf-8", errors="replace")
        return resp.status, text


def parse_response(text):
    if not text:
        return {}
    try:
        return json.loads(text)
    except Exception:
        return {"raw": text}


def persist(envelope, url, token, retries, timeout, backoff):
    body = build_body(envelope)
    attempts = 0
    last_error = None
    for attempt in range(retries + 1):
        attempts = attempt + 1
        try:
            status, text = post_json(url, token, body, timeout)
            response = parse_response(text)
            return {
                "success": 200 <= status < 300,
                "httpStatus": status,
                "attempts": attempts,
                "persisted": bool(response.get("persisted", 200 <= status < 300)),
                "idempotent": bool(response.get("idempotent", False)),
                "ids": response.get("ids", {}),
                "response": response,
            }
        except urllib.error.HTTPError as exc:
            text = exc.read().decode("utf-8", errors="replace")
            response = parse_response(text)
            last_error = {
                "httpStatus": exc.code,
                "error": response or {"raw": text},
            }
            if exc.code not in RETRYABLE_STATUS:
                break
        except Exception as exc:
            last_error = {"error": str(exc)}
        if attempt < retries:
            time.sleep(backoff * (2 ** attempt))
    return {
        "success": False,
        "attempts": attempts,
        "persisted": False,
        "idempotent": False,
        "error": last_error,
    }


def main():
    parser = argparse.ArgumentParser(description="Persist kimi-market-v1 envelope to ai-trading ingest")
    parser.add_argument("json_file", help="Envelope JSON path, or '-' for stdin")
    parser.add_argument("--url", default="", help="Fallback ingest URL")
    parser.add_argument("--token", default="", help="Fallback ingest token")
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--backoff", type=float, default=1.0)
    args = parser.parse_args()

    try:
        envelope = load_json(args.json_file)
    except Exception as exc:
        print(json.dumps({"success": False, "error": f"invalid json: {exc}"}, ensure_ascii=False))
        return 2

    errors = validate_envelope(envelope)
    url = resolve_url(envelope, args.url)
    token = resolve_token(envelope, args.token)
    if not url:
        errors.append("ingest url is required")
    if not token:
        errors.append("ingest token is required")
    if errors:
        print(json.dumps({"success": False, "errors": errors}, ensure_ascii=False, indent=2))
        return 2

    result = persist(envelope, url, token, max(args.retries, 0), args.timeout, max(args.backoff, 0))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
