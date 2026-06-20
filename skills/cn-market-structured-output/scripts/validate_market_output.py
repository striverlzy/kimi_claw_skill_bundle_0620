#!/usr/bin/env python3
import json
import sys
from pathlib import Path

try:
    from markdown_report_to_json import parse_markdown_report
except ImportError:
    parse_markdown_report = None


VALID_MODES = {
    "sector_tree",
    "sector_stock_map",
    "news_event",
    "memo_research",
    "single_stock",
    "us_stock_options",
}

VALID_STATUS = {"complete", "partial", "needs_manual_review"}
VALID_VERIFICATION = {"已验证", "部分验证", "待验证", "数据冲突"}
VALID_RELATION = {"T0", "T1", "T2", "T3", "T4"}
SECTOR_TREE_CATEGORIES = {"上游材料", "上游设备", "中游制造", "中游工艺", "下游应用", "技术路线", "市场题材分支", "其他"}
CHINA_PERSIST_MODES = {
    "sector_tree",
    "sector_stock_map",
    "news_event",
    "memo_research",
    "single_stock",
}

COMMON_REQUIRED = {
    "schemaVersion",
    "mode",
    "generatedAt",
    "asOfDate",
    "language",
    "status",
    "dataPath",
    "qualityControl",
}

REPORT_REQUIRED = {
    "reportFormat",
    "reportTitle",
    "reportMarkdown",
    "reportSections",
    "reportSectionTree",
}

MODE_REQUIRED = {
    "sector_tree": {"sectorName", "existingSubSectors", "candidates"},
    "sector_stock_map": {"sectorName", "subSectorName", "decomposition", "stocks"} | REPORT_REQUIRED,
    "news_event": {
        "analysis",
        "sourceVerification",
        "contentTags",
        "industryChainPanorama",
        "decomposition",
        "downstreamValueMeasurements",
        "keyValidationPoints",
        "stocks",
    } | REPORT_REQUIRED,
    "memo_research": {
        "analysis",
        "sourceVerification",
        "contentTags",
        "industryChainPanorama",
        "decomposition",
        "downstreamValueMeasurements",
        "keyValidationPoints",
        "stocks",
    } | REPORT_REQUIRED,
    "single_stock": {
        "stockName",
        "stockCode",
        "market",
        "overallScore",
        "recommendation",
        "targetReturn",
        "stopLoss",
        "sections",
        "dataSources",
    } | REPORT_REQUIRED,
    "us_stock_options": {
        "stockName",
        "stockCode",
        "market",
        "overallScore",
        "recommendation",
        "sections",
        "dataSources",
        "options",
    } | REPORT_REQUIRED,
}

STOCK_REQUIRED = {
    "rank",
    "name",
    "code",
    "stockName",
    "stockCode",
    "market",
    "marketValue",
    "marketCap",
    "gain",
    "relationLevel",
    "relationScore",
    "segment",
    "coreStatus",
    "investmentLogic",
    "linkages",
    "scoreDetail",
    "evidenceType",
    "verificationStatus",
    "sourceLinks",
    "keyValidationPoints",
    "deepReport",
    "source",
    "needManualReview",
    "reviewStatus",
    "status",
}


def add_missing(errors, path, obj, required):
    missing = sorted(required - set(obj))
    for key in missing:
        errors.append(f"{path}.{key}: missing")


def validate_stock(errors, stock, idx):
    path = f"stocks[{idx}]"
    if not isinstance(stock, dict):
        errors.append(f"{path}: must be object")
        return
    add_missing(errors, path, stock, STOCK_REQUIRED)
    if stock.get("relationLevel") not in VALID_RELATION:
        errors.append(f"{path}.relationLevel: invalid")
    if stock.get("verificationStatus") not in VALID_VERIFICATION:
        errors.append(f"{path}.verificationStatus: invalid")
    if stock.get("gain") not in {"待更新", None} and not stock.get("sourceLinks"):
        errors.append(f"{path}.gain: non-placeholder gain needs sourceLinks")
    alias_pairs = {
        "stockName": "name",
        "stockCode": "code",
        "marketCap": "marketValue",
        "changePercent": "gain",
        "chainStage": "segment",
        "corePosition": "coreStatus",
    }
    for alias, source in alias_pairs.items():
        if alias in stock and source in stock and stock.get(alias) != stock.get(source):
            if {alias, source} == {"stockCode", "code"} and normalize_stock_code(stock.get(alias)) == normalize_stock_code(stock.get(source)):
                continue
            errors.append(f"{path}.{alias}: must equal {source}")
    rank = stock.get("relationLevelRank")
    if rank is not None and not isinstance(rank, int):
        errors.append(f"{path}.relationLevelRank: must be integer when present")
    score_detail = stock.get("scoreDetail")
    if isinstance(score_detail, dict):
        for key in ("technologyBarrier", "domesticSubstitution", "earningsElasticity"):
            if key not in score_detail:
                errors.append(f"{path}.scoreDetail.{key}: missing")
        if "valuationSpace" not in score_detail and "valuationSafety" not in score_detail:
            errors.append(f"{path}.scoreDetail.valuationSpace: missing")


def validate_report_sections(errors, doc):
    if doc.get("reportFormat") != "markdown-heading-tree-v1":
        errors.append("reportFormat: must be markdown-heading-tree-v1")
    if not isinstance(doc.get("reportTitle"), str) or not doc.get("reportTitle").strip():
        errors.append("reportTitle: missing")

    report = doc.get("reportMarkdown")
    min_report_len = 120 if doc.get("mode") == "single_stock" else 1000
    if not isinstance(report, str) or len(report.strip()) < min_report_len:
        errors.append("reportMarkdown: missing or too short")

    sections = doc.get("reportSections")
    if not isinstance(sections, list) or not sections:
        errors.append("reportSections: must be non-empty array")
        return

    required = {
        "order",
        "id",
        "level",
        "title",
        "headingMarkdown",
        "anchor",
        "headingPath",
        "parentId",
        "childrenIds",
        "contentMarkdown",
        "content",
        "startLine",
        "contentStartLine",
        "contentEndLine",
        "blockEndLine",
    }
    ids = set()
    for idx, section in enumerate(sections):
        if not isinstance(section, dict):
            errors.append(f"reportSections[{idx}]: must be object")
            continue
        add_missing(errors, f"reportSections[{idx}]", section, required)
        section_id = section.get("id")
        if section_id in ids:
            errors.append(f"reportSections[{idx}].id: duplicate")
        ids.add(section_id)
        if section.get("order") != idx + 1:
            errors.append(f"reportSections[{idx}].order: must be sequential from 1")
        level = section.get("level")
        if not isinstance(level, int) or level < 1 or level > 6:
            errors.append(f"reportSections[{idx}].level: must be integer 1-6")
        heading = section.get("headingMarkdown")
        if isinstance(level, int) and isinstance(heading, str) and heading:
            if not heading.startswith("#" * level + " "):
                errors.append(f"reportSections[{idx}].headingMarkdown: does not match level")
        if not isinstance(section.get("headingPath"), list) or not section.get("headingPath"):
            errors.append(f"reportSections[{idx}].headingPath: must be non-empty array")
        if not isinstance(section.get("childrenIds"), list):
            errors.append(f"reportSections[{idx}].childrenIds: must be array")
        if section.get("content") != section.get("contentMarkdown"):
            errors.append(f"reportSections[{idx}].content: must equal contentMarkdown")

    for idx, section in enumerate(sections):
        if not isinstance(section, dict):
            continue
        parent_id = section.get("parentId")
        if parent_id is not None and parent_id not in ids:
            errors.append(f"reportSections[{idx}].parentId: unknown parent")
        for child_id in section.get("childrenIds", []):
            if child_id not in ids:
                errors.append(f"reportSections[{idx}].childrenIds: unknown child {child_id}")

    tree = doc.get("reportSectionTree")
    if not isinstance(tree, list) or not tree:
        errors.append("reportSectionTree: must be non-empty array")
    elif doc.get("reportTitle") and tree[0].get("title") != doc.get("reportTitle"):
        errors.append("reportSectionTree[0].title: must match reportTitle")

    if parse_markdown_report and isinstance(report, str) and isinstance(sections, list) and sections:
        expected = parse_markdown_report(report)
        if doc.get("reportTitle") != expected.get("reportTitle"):
            errors.append("reportTitle: does not match first Markdown heading")
        expected_sections = expected.get("reportSections", [])
        if len(sections) != len(expected_sections):
            errors.append("reportSections: count does not match Markdown headings")
            return
        compare_keys = {
            "order",
            "id",
            "level",
            "title",
            "headingMarkdown",
            "anchor",
            "parentId",
            "childrenIds",
            "headingPath",
            "contentMarkdown",
            "content",
            "startLine",
            "contentStartLine",
            "contentEndLine",
            "blockEndLine",
        }
        for idx, (actual, expected_section) in enumerate(zip(sections, expected_sections)):
            if not isinstance(actual, dict):
                continue
            for key in compare_keys:
                if actual.get(key) != expected_section.get(key):
                    errors.append(f"reportSections[{idx}].{key}: does not match Markdown")
        if tree != expected.get("reportSectionTree"):
            errors.append("reportSectionTree: does not match Markdown heading tree")


def normalize_stock_code(value):
    if value is None:
        return ""
    text = str(value).strip().upper().replace(" ", "")
    if len(text) >= 6 and text[:6].isdigit():
        return text[:6]
    return text


def validate_persist_contract(errors, doc):
    contract = doc.get("persistContract")
    mode = doc.get("mode")
    if contract is None:
        if mode in CHINA_PERSIST_MODES and (doc.get("taskNo") or doc.get("ingest")):
            errors.append("persistContract: missing when taskNo/ingest is present")
        return
    if not isinstance(contract, dict):
        errors.append("persistContract: must be object")
        return
    required = {"bizType", "targetTables", "writeMode"}
    add_missing(errors, "persistContract", contract, required)
    if contract.get("bizType") != mode:
        errors.append("persistContract.bizType: must equal mode")
    if contract.get("mapper") not in {None, "AiMarketMapper"}:
        errors.append("persistContract.mapper: must be AiMarketMapper")
    if not isinstance(contract.get("targetTables"), list) or not contract.get("targetTables"):
        errors.append("persistContract.targetTables: must be non-empty array")
    ingest = contract.get("ingest")
    if ingest is not None and not isinstance(ingest, dict):
        errors.append("persistContract.ingest: must be object")


def validate_sector_decomposition(errors, doc):
    decomposition = doc.get("decomposition")
    if not isinstance(decomposition, dict):
        errors.append("decomposition: must be object")
        return
    required = {"panorama", "upstream", "midstream", "downstream", "investmentRanking", "validationPoints"}
    add_missing(errors, "decomposition", decomposition, required)
    midstream = decomposition.get("midstream")
    if not isinstance(midstream, dict):
        errors.append("decomposition.midstream: must be object")
    else:
        add_missing(errors, "decomposition.midstream", midstream, {"firstTier", "secondTier", "thirdTier"})
    if "nodes" in decomposition or "edges" in decomposition:
        errors.append("decomposition: sector_stock_map must use frontend shape, not nodes/edges only")


def validate_sector_tree(errors, doc):
    candidates = doc.get("candidates")
    if not isinstance(candidates, list):
        errors.append("candidates: must be array")
        return
    elif len(candidates) < 6:
        errors.append("candidates: sector_tree should include at least 6 candidates")
    core_count = 0
    for idx, candidate in enumerate(candidates):
        if not isinstance(candidate, dict):
            errors.append(f"candidates[{idx}]: must be object")
            continue
        category = candidate.get("categoryType")
        if category not in SECTOR_TREE_CATEGORIES:
            errors.append(f"candidates[{idx}].categoryType: invalid")
        if candidate.get("isCore") is True:
            core_count += 1
        level = candidate.get("level")
        if level not in {2, 3}:
            errors.append(f"candidates[{idx}].level: must be 2 or 3")
    if core_count > 2:
        errors.append("candidates.isCore: at most 2 core candidates")


def validate_doc(doc):
    errors = []
    if not isinstance(doc, dict):
        return ["root: must be object"]

    add_missing(errors, "root", doc, COMMON_REQUIRED)

    if doc.get("schemaVersion") != "kimi-market-v1":
        errors.append("schemaVersion: must be kimi-market-v1")

    mode = doc.get("mode")
    if mode not in VALID_MODES:
        errors.append("mode: invalid")
        return errors

    if doc.get("status") not in VALID_STATUS:
        errors.append("status: invalid")

    add_missing(errors, "root", doc, MODE_REQUIRED[mode])

    if not isinstance(doc.get("dataPath"), dict):
        errors.append("dataPath: must be object")
    if not isinstance(doc.get("qualityControl"), dict):
        errors.append("qualityControl: must be object")

    if "stocks" in doc:
        stocks = doc["stocks"]
        if not isinstance(stocks, list):
            errors.append("stocks: must be array")
        else:
            for idx, stock in enumerate(stocks):
                validate_stock(errors, stock, idx)

    if mode != "sector_tree":
        validate_report_sections(errors, doc)

    if mode == "sector_tree":
        validate_sector_tree(errors, doc)

    if mode == "sector_stock_map":
        if not isinstance(doc.get("stocks"), list) or not doc.get("stocks"):
            errors.append("stocks: sector_stock_map must include top-level non-empty stocks")
        validate_sector_decomposition(errors, doc)

    if mode == "us_stock_options":
        options = doc.get("options")
        if not isinstance(options, dict):
            errors.append("options: must be object")
        elif "dataAvailable" not in options:
            errors.append("options.dataAvailable: missing")

    validate_persist_contract(errors, doc)

    return errors


def main():
    if len(sys.argv) != 2:
        print("Usage: validate_market_output.py <json-file>", file=sys.stderr)
        return 2

    path = Path(sys.argv[1])
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(json.dumps({"valid": False, "errors": [f"json: {exc}"]}, ensure_ascii=False))
        return 1

    errors = validate_doc(doc)
    print(json.dumps({"valid": not errors, "errors": errors}, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
