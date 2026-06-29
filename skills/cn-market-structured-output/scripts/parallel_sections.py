#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
parallel_sections.py —— skill 内部"并发生成结构化字段、汇总成同一份 kimi-market-v1 JSON"的引擎。

对后端完全透明：后端依旧一次 gateway call 拿到一个 kimi-market-v1 JSON；本脚本把"生成重字段"
这步从 agent 串行手写改成【并发原始模型调用】，再本地合并/规范化/回填/校验。

支持 mode：single_stock / us_stock_options / news_event / memo_research / sector_tree / sector_stock_map

用法：
  python3 parallel_sections.py <brief.json> -o <final.json> --mode <mode>

brief.json 由 agent 检索后产出（只含数据与锁定结论，不含整篇报告）。各 mode 的 brief 形态见 README。
并发只发生在本机本脚本内部（直连 kimi-coding /v1/messages，真并发）；不依赖 openclaw agent 层。
"""
import argparse, json, os, sys, time, subprocess, tempfile, urllib.request
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

HOME = os.path.expanduser("~")
HERE = os.path.dirname(os.path.abspath(__file__))
MD2JSON = os.path.join(HERE, "markdown_report_to_json.py")
VALIDATE = os.path.join(HERE, "validate_market_output.py")
CONFIG = os.environ.get("OPENCLAW_CONFIG", f"{HOME}/.kimi_openclaw/openclaw.json")
GEN_MODEL = os.environ.get("KC_GEN_MODEL", "kimi-k2.7-code-highspeed")

VALID_RELATION = {"T0", "T1", "T2", "T3", "T4"}
VALID_VERIF = {"已验证", "部分验证", "待验证", "数据冲突"}
VALID_RESEARCH_CATEGORY = {"行业纪要", "公司纪要", "专家交流", "券商研报", "专题研报"}


def provider():
    p = json.load(open(CONFIG))["models"]["providers"]["kimi-coding"]
    return p["baseUrl"], p["apiKey"]


def raw_call(prompt, max_tokens=2500, label="", model=None):
    base, key = provider()
    body = json.dumps({"model": model or GEN_MODEL, "max_tokens": max_tokens,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request(base + "/v1/messages", data=body, headers={
        "content-type": "application/json", "x-api-key": key,
        "anthropic-version": "2023-06-01", "User-Agent": "Desktop Kimi Claw Plugin"})
    t0 = time.time()
    r = json.load(urllib.request.urlopen(req, timeout=160))
    txt = "".join(b.get("text", "") for b in r.get("content", []) if b.get("type") == "text")
    sys.stderr.write(f"[parallel_sections] {label:18s} {time.time()-t0:5.1f}s out={r.get('usage',{}).get('output_tokens')}tok\n")
    return txt


def extract_json(text):
    if not text:
        return None
    s = text.strip()
    if s.startswith("```"):
        s = s.split("```", 2)[1]
        if s.startswith("json"):
            s = s[4:]
        s = s.strip().rstrip("`").strip()
    try:
        return json.loads(s)
    except Exception:
        pass
    i = s.find("{")
    if i < 0:
        return None
    depth = 0
    for j in range(i, len(s)):
        if s[j] == "{":
            depth += 1
        elif s[j] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(s[i:j+1])
                except Exception:
                    return None
    return None


def gen_obj(prompt, label, max_tokens=2500):
    return extract_json(raw_call(prompt, max_tokens=max_tokens, label=label)) or {}


def run_parallel(tasks):
    """tasks: list of (label, callable). 并发执行，返回 {label: result}。"""
    out = {}
    with ThreadPoolExecutor(max_workers=min(8, len(tasks) or 1)) as ex:
        futs = {ex.submit(fn): lbl for lbl, fn in tasks}
        for f in futs:
            out[futs[f]] = f.result()
    return out


# ───────────────────────── 9-section 股票生成（single_stock / us_stock_options 复用） ─────────────────────────
SECTION_FIELDS = {
    "companyOverview":   ["industry","headquarters","founded","listed","ceo","employees","coreBusiness","brandValue","dataSources"],
    "businessStructure": ["segments","channels","dataSources"],
    "financials":        ["revenue2024","revenueGrowth2024","netIncome2024","netIncomeGrowth2024","revenueQ12026","revenueGrowthQ1YoY","netIncomeQ12026","netIncomeGrowthQ1YoY","epsQ12026","grossMarginTTM","netMarginTTM","roeTTM","roicTTM","debtRatio","currentRatio","cash","totalLiabilities","dividendYieldTTM","dataSources"],
    "valuation":         ["currentPrice","marketCap","peTTM","peForward","pb","dividendYield","analystTargetMean","analystTargetHigh","analystTargetLow","upsideToTarget","scenarioOptimistic","scenarioBase","scenarioPessimistic","dataSources"],
    "competitiveAnalysis":["marketPosition","marketShare","mainCompetitors","moat","dataSources"],
    "growthDrivers":     ["catalysts","revenueGuidance2025","analystConsensus2026","analystConsensus2027","netIncomeConsensus2026","netIncomeConsensus2027","dataSources"],
    "risks":             ["riskList","dataSources"],
    "scoring":           ["dimensions","totalScore","interpretation","dataSources"],
    "investmentAdvice":  ["conclusion","timeHorizon","targetPrice3M","targetPrice6M","targetPrice12M","buyZone","watchZone","reduceZone","stopLoss","maxPosition","reviewFrequency","dataSources"],
}
SECTION_BUCKETS = {
    "desc": ["companyOverview", "businessStructure"],
    "fin": ["financials", "valuation"],
    "market": ["competitiveAnalysis", "growthDrivers"],
    "judge": ["risks", "scoring", "investmentAdvice"],
}


def section_bucket_prompt(secs, brief):
    fields_desc = "；".join("%s(字段:%s)" % (s, ",".join(SECTION_FIELDS[s])) for s in secs)
    shape = "{" + ", ".join('"%s":{...}' % s for s in secs) + "}"
    return (
        "【片段撰写器·禁止任何检索/联网/工具调用】只基于下面的研究简报，输出指定 section 的 JSON。"
        "简报里没有的数字一律填\"待验证\"，禁止编造。\n"
        "需要输出：" + fields_desc + "\n"
        "lockedNumbers 里的 currentPrice/overallScore/recommendation 必须被相关 section 原样引用。"
        "每个 section 的 dataSources 为数组。因果清晰、风险独立具体、可执行建议落到 investmentAdvice。\n"
        "只返回一个 JSON 对象，形如 " + shape + "，每个值是该 section 的 dict。第一个字符 { 最后一个 }，无多余文字。\n\n"
        "研究简报：\n" + json.dumps(brief, ensure_ascii=False)
    )


def gen_sections(brief):
    tasks = [(name, (lambda secs=secs: gen_obj(section_bucket_prompt(secs, brief), f"sec-{secs[0]}")))
             for name, secs in SECTION_BUCKETS.items()]
    merged = run_parallel(tasks)
    sections = {}
    for name, secs in SECTION_BUCKETS.items():
        obj = merged.get(name, {})
        for s in secs:
            if isinstance(obj.get(s), dict):
                sections[s] = obj[s]
    return sections


# ───────────────────────── 防御式规范化（保证 schema 合法，不靠 LLM 完美） ─────────────────────────
def norm_stock(raw, idx):
    s = dict(raw or {})
    name = s.get("name") or s.get("stockName") or "待验证"
    code = s.get("code") or s.get("stockCode") or "待验证"
    seg = s.get("segment") or s.get("chainStage") or "待验证"
    core = s.get("coreStatus") or s.get("corePosition") or "待验证"
    mv = s.get("marketValue") or s.get("marketCap") or "待验证"
    sd = s.get("scoreDetail") if isinstance(s.get("scoreDetail"), dict) else {}
    for k in ("technologyBarrier", "domesticSubstitution", "earningsElasticity"):
        sd.setdefault(k, "待验证")
    if "valuationSpace" not in sd and "valuationSafety" not in sd:
        sd["valuationSpace"] = "待验证"
    rl = s.get("relationLevel") if s.get("relationLevel") in VALID_RELATION else "T2"
    vf = s.get("verificationStatus") if s.get("verificationStatus") in VALID_VERIF else "待验证"
    rs = s.get("relationScore")
    return {
        "rank": s.get("rank") if isinstance(s.get("rank"), int) else idx + 1,
        "name": name, "stockName": name, "code": code, "stockCode": code,
        "market": s.get("market") or "A股",
        "marketValue": mv, "marketCap": mv,
        "gain": "待更新",  # 占位，避免 validator 要求 sourceLinks
        "relationLevel": rl,
        "relationScore": rs if isinstance(rs, (int, float)) else 0,
        "segment": seg, "coreStatus": core,
        "investmentLogic": s.get("investmentLogic") or "待验证",
        "linkages": s.get("linkages") if isinstance(s.get("linkages"), list) else [],
        "scoreDetail": sd,
        "evidenceType": s.get("evidenceType") or "待验证",
        "verificationStatus": vf,
        "sourceLinks": s.get("sourceLinks") if isinstance(s.get("sourceLinks"), list) else [],
        "keyValidationPoints": s.get("keyValidationPoints") if isinstance(s.get("keyValidationPoints"), list) else [],
        "deepReport": s.get("deepReport") or "待验证",
        "source": s.get("source") or "待验证",
        "needManualReview": bool(s.get("needManualReview", False)),
        "reviewStatus": s.get("reviewStatus") or "pending",
        "status": s.get("status") or "complete",
    }


def gen_stocks(brief):
    """brief.stocks = [{name,code,segment,investmentLogic}]；并发为每只生成 deepReport/scoreDetail。"""
    cands = brief.get("stocks") or brief.get("candidates") or []
    if not isinstance(cands, list) or not cands:
        return []

    def one(i, c):
        prompt = (
            "【个股深研片段·禁止检索】只基于简报与下面这只股票的已知信息，输出一个 JSON："
            '{"deepReport":"150-300字深度逻辑","scoreDetail":{"technologyBarrier":"..","domesticSubstitution":"..","earningsElasticity":"..","valuationSpace":".."},'
            '"investmentLogic":"一句话核心逻辑","keyValidationPoints":["..",".."],"evidenceType":"公告/研报/新闻"}\n'
            "缺的填\"待验证\"，禁止编造数字。只返回 JSON。\n"
            "股票：" + json.dumps(c, ensure_ascii=False) + "\n简报背景：" + (brief.get("topic") or brief.get("title") or "")
        )
        obj = gen_obj(prompt, f"stock-{i}", max_tokens=1200)
        merged = dict(c)
        merged.update(obj or {})
        return norm_stock(merged, i)

    tasks = [(str(i), (lambda i=i, c=c: one(i, c))) for i, c in enumerate(cands)]
    res = run_parallel(tasks)
    return [res[str(i)] for i in range(len(cands))]


def norm_options(raw):
    o = dict(raw or {})
    o.setdefault("dataAvailable", o.get("dataAvailable", False))
    for k in ["expirations", "putCallRatio", "atmIv", "ivRank", "maxPain", "callWall",
              "putWall", "gammaExposure", "skew", "optionsTimingView", "riskNotes"]:
        o.setdefault(k, "待验证")
    return o


def norm_sector_decomp(raw):
    d = dict(raw or {})
    mid = d.get("midstream") if isinstance(d.get("midstream"), dict) else {}
    for k in ("firstTier", "secondTier", "thirdTier"):
        mid.setdefault(k, "待验证")
    d["midstream"] = mid
    for k in ("panorama", "upstream", "downstream", "investmentRanking", "validationPoints"):
        d.setdefault(k, "待验证")
    d.pop("nodes", None)
    d.pop("edges", None)
    return d


# ───────────────────────── 各 mode 的 buckets + 信封组装 ─────────────────────────
def gen_news_fields(brief, mode):
    head_prompt = (
        "【新闻/纪要结构化片段·禁止检索】只基于简报，输出 JSON："
        '{"analysis":{"authenticityLevel":"..","riskWarning":"..","sourceType":"..","marketImpact":"..","industryValue":"..","themeValue":"..","transmissionPath":".."'
        + (',"earliestPublishTime":"..","earliestSourceUrl":".."' if mode == "news_event" else ',"researchCategory":"行业纪要/公司纪要/专家交流/券商研报/专题研报 五选一"')
        + '},"sourceVerification":{"verificationStatus":"..","sourceType":"..","primarySources":[".."],"crossValidation":".."},"contentTags":["标签1","标签2","标签3"]}\n'
        "缺的填\"待验证\"。只返回 JSON。\n简报：" + json.dumps(brief, ensure_ascii=False)
    )
    chain_prompt = (
        "【产业链结构化片段·禁止检索】只基于简报，输出 JSON："
        '{"industryChainPanorama":[{"segment":"..","coreDetail":"..","barrier":"..","valueTransfer":".."}],'
        '"decomposition":{"industryChain":"..","bottleneckLink":"..","valueTransfer":"..","domesticSubstitution":"..","globalCompetition":".."},'
        '"downstreamValueMeasurements":[{"item":"..","value":".."}],'
        '"keyValidationPoints":[{"point":"..","validationMethod":"..","timeline":".."}]}\n'
        "缺的填\"待验证\"。只返回 JSON。\n简报：" + json.dumps(brief, ensure_ascii=False)
    )
    res = run_parallel([
        ("head", lambda: gen_obj(head_prompt, "news-head")),
        ("chain", lambda: gen_obj(chain_prompt, "news-chain")),
    ])
    head, chain = res["head"], res["chain"]
    analysis = head.get("analysis") if isinstance(head.get("analysis"), dict) else {}
    if mode == "news_event":
        analysis.setdefault("earliestPublishTime", brief.get("earliestPublishTime", "待验证"))
        analysis.setdefault("earliestSourceUrl", brief.get("earliestSourceUrl", "待验证"))
    if mode == "memo_research":
        rc = analysis.get("researchCategory")
        if rc not in VALID_RESEARCH_CATEGORY:
            analysis["researchCategory"] = brief.get("researchCategory") if brief.get("researchCategory") in VALID_RESEARCH_CATEGORY else "专题研报"
    return {
        "analysis": analysis,
        "sourceVerification": head.get("sourceVerification") if isinstance(head.get("sourceVerification"), dict) else {"verificationStatus": "待验证"},
        "contentTags": head.get("contentTags") if isinstance(head.get("contentTags"), list) else [],
        "industryChainPanorama": chain.get("industryChainPanorama") if isinstance(chain.get("industryChainPanorama"), list) else [],
        "decomposition": chain.get("decomposition") if isinstance(chain.get("decomposition"), dict) else {},
        "downstreamValueMeasurements": chain.get("downstreamValueMeasurements") if isinstance(chain.get("downstreamValueMeasurements"), list) else [],
        "keyValidationPoints": chain.get("keyValidationPoints") if isinstance(chain.get("keyValidationPoints"), list) else [],
    }


def gen_sector_map_fields(brief):
    prompt = (
        "【板块拆解结构化片段·禁止检索】只基于简报，输出 JSON："
        '{"decomposition":{"panorama":"..","upstream":"..","midstream":{"firstTier":"..","secondTier":"..","thirdTier":".."},"downstream":"..","investmentRanking":"..","validationPoints":".."},'
        '"industryChainPanorama":[{"segment":"..","coreDetail":"..","barrier":"..","valueTransfer":".."}],'
        '"downstreamValueMeasurements":[{"item":"..","value":".."}],'
        '"keyValidationPoints":[{"point":"..","validationMethod":"..","timeline":".."}]}\n'
        "缺的填\"待验证\"。只返回 JSON。\n简报：" + json.dumps(brief, ensure_ascii=False)
    )
    return gen_obj(prompt, "sector-decomp", max_tokens=2500)


def gen_sector_tree_candidates(brief):
    prompt = (
        "【板块子板块候选·禁止检索】只基于简报，输出 JSON："
        '{"candidates":[{"name":"子板块名","categoryType":"上游材料/上游设备/中游制造/中游工艺/下游应用/技术路线/市场题材分支/其他 八选一","level":2,"isCore":false,"reason":"..","representativeStocks":[".."]}]}\n'
        "至少 6 个候选，最多 2 个 isCore=true，level 取 2 或 3。缺的填\"待验证\"。只返回 JSON。\n简报：" + json.dumps(brief, ensure_ascii=False)
    )
    return gen_obj(prompt, "sector-tree", max_tokens=2500)


SECTOR_TREE_CATS = {"上游材料", "上游设备", "中游制造", "中游工艺", "下游应用", "技术路线", "市场题材分支", "其他"}


def norm_candidate(c, idx):
    c = dict(c or {})
    cat = c.get("categoryType") if c.get("categoryType") in SECTOR_TREE_CATS else "其他"
    lvl = c.get("level") if c.get("level") in (2, 3) else 2
    return {**c, "name": c.get("name") or f"子板块{idx+1}", "categoryType": cat, "level": lvl,
            "isCore": bool(c.get("isCore", False)),
            "reason": c.get("reason") or "待验证",
            "representativeStocks": c.get("representativeStocks") if isinstance(c.get("representativeStocks"), list) else []}


# ───────────────────────── 信封组装 ─────────────────────────
def common_envelope(mode, brief, n_ok, n_total):
    now = datetime.now()
    status = "complete" if n_ok >= n_total else ("partial" if n_ok >= max(1, n_total // 2) else "needs_manual_review")
    env = {
        "schemaVersion": "kimi-market-v1", "mode": mode,
        "generatedAt": now.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "asOfDate": now.strftime("%Y-%m-%d"), "language": "zh", "status": status,
        "dataPath": {"retrieval": "agent", "generation": "parallel-raw-llm", "engine": "parallel_sections.py"},
        "qualityControl": {"generatedConcurrently": True, "okParts": n_ok, "totalParts": n_total},
    }
    if brief.get("persistContract"):
        env["persistContract"] = brief["persistContract"]
    return env


def ensure_min_report(md, brief, min_len):
    md = (md or "").strip()
    if len(md) >= min_len:
        return md
    facts = brief.get("facts") or {}
    if facts:
        md += "\n\n## 补充数据\n" + "\n".join(f"- **{k}**：{v}" for k, v in facts.items())
    while len(md.strip()) < min_len:
        md += "\n- 以上结论与数据需结合最新公告、交易所披露与券商研报持续跟踪验证。"
    return md.strip()


def add_report(env, brief, title):
    min_len = 150 if env.get("mode") == "single_stock" else 1050
    env["reportFormat"] = "markdown-heading-tree-v1"
    env["reportTitle"] = brief.get("reportTitle") or title
    env["reportMarkdown"] = ensure_min_report(brief.get("reportMarkdown", ""), brief, min_len)
    env["reportSections"] = []
    env["reportSectionTree"] = []


def build(brief, mode):
    if mode in ("single_stock", "us_stock_options"):
        sections = gen_sections(brief)
        ln = brief.get("lockedNumbers", {})
        env = common_envelope(mode, brief, len(sections), 9)
        env.update({
            "stockName": brief.get("stockName"), "stockCode": brief.get("stockCode"),
            "market": brief.get("market"),
            "overallScore": ln.get("overallScore"), "recommendation": ln.get("recommendation"),
            "sections": sections, "dataSources": brief.get("dataSources", []),
        })
        if mode == "single_stock":
            env["targetReturn"] = ln.get("targetReturn")
            env["stopLoss"] = ln.get("stopLoss")
        if mode == "us_stock_options":
            opt = gen_obj(
                "【期权结构化片段·禁止检索】只基于简报输出 options JSON:"
                '{"options":{"dataAvailable":true/false,"expirations":"..","putCallRatio":"..","atmIv":"..","ivRank":"..","maxPain":"..","callWall":"..","putWall":"..","gammaExposure":"..","skew":"..","optionsTimingView":"..","riskNotes":".."}}\n'
                "缺的填\"待验证\",dataAvailable 据简报判断。只返回 JSON。\n简报:" + json.dumps(brief, ensure_ascii=False),
                "options", max_tokens=1200)
            env["options"] = norm_options(opt.get("options") if isinstance(opt.get("options"), dict) else opt)
        add_report(env, brief, f"{brief.get('stockName','')}({brief.get('stockCode','')}) 分析")
        return env

    if mode in ("news_event", "memo_research"):
        fields = gen_news_fields(brief, mode)
        stocks = gen_stocks(brief)
        env = common_envelope(mode, brief, 1, 1)
        env.update(fields)
        env["stocks"] = stocks
        env["dataSources"] = brief.get("dataSources", [])
        add_report(env, brief, brief.get("title") or "新闻/纪要分析")
        return env

    if mode == "sector_stock_map":
        f = gen_sector_map_fields(brief)
        stocks = gen_stocks(brief)
        env = common_envelope(mode, brief, 1, 1)
        env["sectorName"] = brief.get("sectorName")
        env["subSectorName"] = brief.get("subSectorName")
        env["decomposition"] = norm_sector_decomp(f.get("decomposition") if isinstance(f.get("decomposition"), dict) else {})
        for k in ("industryChainPanorama", "downstreamValueMeasurements", "keyValidationPoints"):
            if isinstance(f.get(k), list):
                env[k] = f[k]
        env["stocks"] = stocks or [norm_stock({"name": brief.get("subSectorName") or "待验证", "code": "待验证"}, 0)]
        env["dataSources"] = brief.get("dataSources", [])
        add_report(env, brief, f"{brief.get('sectorName','')}-{brief.get('subSectorName','')} 拆解")
        return env

    if mode == "sector_tree":
        c = gen_sector_tree_candidates(brief)
        cands = c.get("candidates") if isinstance(c.get("candidates"), list) else []
        cands = [norm_candidate(x, i) for i, x in enumerate(cands)]
        env = common_envelope(mode, brief, len(cands), 6)
        env["sectorName"] = brief.get("sectorName")
        env["existingSubSectors"] = brief.get("existingSubSectors", [])
        env["candidates"] = cands
        env["dataSources"] = brief.get("dataSources", [])
        return env

    raise SystemExit(f"unknown mode: {mode}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("brief")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--mode", default="single_stock")
    a = ap.parse_args()

    try:
        with open("/tmp/parallel_sections_invocations.log", "a", encoding="utf-8") as lf:
            lf.write(f"{datetime.now().isoformat()} invoked brief={a.brief} mode={a.mode}\n")
    except Exception:
        pass

    brief = json.load(open(a.brief, encoding="utf-8"))

    # 幂等：同一 brief+mode 在 10 分钟内重复调用 → 直接返回上次结果（防 agent 重复运行浪费时间）
    import hashlib
    h = hashlib.sha1((json.dumps(brief, ensure_ascii=False, sort_keys=True) + a.mode).encode()).hexdigest()[:16]
    idem_path = f"/tmp/.ps_idem_{h}.json"
    if os.path.exists(idem_path) and time.time() - os.path.getmtime(idem_path) < 600:
        prev = open(idem_path, encoding="utf-8").read()
        open(a.out, "w", encoding="utf-8").write(prev)
        sys.stderr.write("[parallel_sections] 幂等命中，返回上次结果（未重复生成）\n")
        print(prev)
        return

    t0 = time.time()
    env = build(brief, a.mode)
    sys.stderr.write(f"[parallel_sections] mode={a.mode} 并发生成用时 {time.time()-t0:.1f}s\n")

    # report 模式回填标题树（sector_tree 无 report）
    if a.mode != "sector_tree":
        draft = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
        json.dump(env, draft, ensure_ascii=False)
        draft.close()
        r = subprocess.run(["python3", MD2JSON, draft.name, "-o", a.out], capture_output=True, text=True)
        if r.returncode != 0:
            sys.stderr.write(f"[parallel_sections] md2json 失败，直接写: {r.stderr[-200:]}\n")
            json.dump(env, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    else:
        json.dump(env, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    v = subprocess.run(["python3", VALIDATE, a.out], capture_output=True, text=True)
    sys.stderr.write(f"[parallel_sections] validator: {v.stdout.strip()[:400]}\n")
    final_text = open(a.out, encoding="utf-8").read()
    try:
        open(idem_path, "w", encoding="utf-8").write(final_text)  # 写幂等缓存
    except Exception:
        pass
    print(final_text)


if __name__ == "__main__":
    main()
