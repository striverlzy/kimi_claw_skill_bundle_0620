# KimiClaw Market Structured Output Protocol v1

## 1. Purpose

This protocol turns market research into API-ready JSON. It is based on the local P1-P5 prompt files, but is simplified into one consistent envelope and a few mode-specific payloads.

For these three research skills, this protocol is the default return format:

- `cn-stock-analysis`
- `cn-news-catalyst-analysis`
- `us-stock-options-analysis`

Use normal Markdown only when the user explicitly asks for a prose report, quick chat answer, or non-JSON explanation.

## 2. Common Envelope

Every structured response must be one valid JSON object with this envelope:

```json
{
  "schemaVersion": "kimi-market-v1",
  "mode": "sector_tree|sector_stock_map|news_event|memo_research|single_stock|us_stock_options",
  "generatedAt": "ISO-8601 timestamp",
  "asOfDate": "YYYY-MM-DD",
  "language": "zh-CN",
  "status": "complete|partial|needs_manual_review",
  "dataPath": {
    "search": "AnySearch|Kimi Search|未使用|不可用",
    "marketData": "Kimi Finance|行情源名称|未使用|不可用",
    "filings": "交易所/公告/SEC/不可用",
    "notes": ["简要说明使用了哪些来源层"]
  },
  "qualityControl": {
    "dataFreshness": "realtime|recent|stale|unknown",
    "sourceCoverage": "strong|medium|weak",
    "hallucinationRisk": "low|medium|high",
    "missingFields": [],
    "manualReviewReasons": []
  },
  "persistContract": {
    "bizType": "sector_tree|sector_stock_map|news_event|memo_research|single_stock",
    "bizId": "由 Java payload 注入；未知时填 null",
    "taskNo": "由 Java payload 注入；未知时填空字符串",
    "autoPersist": false,
    "ingest": {
      "url": "由 Java payload.ingest.url 注入；Skill 不得硬编码地址",
      "tokenRequired": true
    },
    "idempotencyKey": "taskNo + bizType + bizId",
    "mapper": "AiMarketMapper",
    "targetTables": []
  }
}
```

Rules:

- JSON is an extension layer, not a replacement for the original report.
- `persistContract` is required for all China-market modes (`sector_tree`, `sector_stock_map`, `news_event`, `memo_research`, `single_stock`) when the payload contains `taskNo` or `ingest`. It is optional for historical samples and `us_stock_options`.
- Skill-side writeback must call `cn-market-writeback` with the complete JSON envelope. Java ingest and gateway fallback both map through `AiMarketMapper`; do not create alternate field names or partial writeback payloads.
- Every analysis mode except `sector_tree` must preserve the full original report:
  - `reportMarkdown`: complete human-readable report body.
  - `reportFormat`: must be `markdown-heading-tree-v1`.
  - `reportTitle`: the first Markdown H1 title.
  - `reportSections`: flat section table generated from Markdown headings.
  - `reportSectionTree`: nested section tree generated from the same headings.
- `status=complete` only when required fields are filled with sourced or clearly marked data.
- `status=partial` when analysis is useful but some sources or market fields are missing.
- `status=needs_manual_review` when rumor, screenshots, private notes, conflicting data, or unsupported stock relations materially affect the result.

Report preservation schema:

```json
{
  "reportFormat": "markdown-heading-tree-v1",
  "reportTitle": "完整报告标题",
  "reportMarkdown": "# 完整报告标题\n\n完整正文...",
  "reportSections": [
    {
      "order": 1,
      "id": "s001",
      "level": 2,
      "title": "业务结构与战略定位",
      "headingMarkdown": "## 业务结构与战略定位",
      "anchor": "业务结构与战略定位",
      "headingPath": ["完整报告标题", "业务结构与战略定位"],
      "parentId": "s000",
      "childrenIds": ["s002", "s003"],
      "contentMarkdown": "只保留该标题下、下一个标题前的正文、表格和要点。",
      "content": "必须与 contentMarkdown 相同，保留兼容字段。",
      "startLine": 12,
      "contentStartLine": 13,
      "contentEndLine": 20,
      "blockEndLine": 45
    }
  ],
  "reportSectionTree": [
    {
      "id": "s001",
      "level": 1,
      "title": "完整报告标题",
      "children": []
    }
  ]
}
```

Markdown-to-JSON rules:

- Compose the full `reportMarkdown` first.
- Parse only Markdown ATX headings (`#`, `##`, `###`, up to `######`) to create the report structure.
- `reportSections` is a flat ordered table. It must be enough to reconstruct the document by sorting by `order` and concatenating `headingMarkdown + "\n\n" + contentMarkdown`.
- `reportSectionTree` is the same structure nested by heading level for frontend rendering.
- `contentMarkdown` contains only the immediate body under the heading before the next heading. Child sections live in their own section objects.
- Empty parent sections are allowed when their content is represented entirely by child headings, but the section object must still exist.
- Do not manually invent section titles that are not present in `reportMarkdown`.
- Use `scripts/markdown_report_to_json.py` when converting saved Markdown examples or backfilling JSON files.

For `cn-stock-analysis`, preserve the original full research report style: conclusion, business composition, competitive comparison, recent financials, future growth, valuation, risks, investment conclusion, portfolio allocation, and nine-factor score.

For `cn-news-catalyst-analysis`, preserve the original catalyst report style only for `news_event` and `memo_research`: message confirmation, message value, industry-chain panorama, beneficiary ranking, short-term trading value, style-switch plan, operation strategy, risks and invalidation. For `sector_stock_map` and `sector_tree`, use a pure industry-chain report style and do not require sourceVerification, market-style judgement, or short-term trading fields.

For `us-stock-options-analysis`, preserve the original fundamental-plus-options report style: fundamentals, valuation, options sentiment, options key levels, fundamental-options cross-check, risks, recommendation, portfolio allocation, and score.

## 3. Stock Item Schema

Use this schema whenever `stocks` is present:

```json
{
  "rank": 1,
  "name": "公司名称",
  "code": "6位A股代码或市场代码",
  "stockName": "公司名称",
  "stockCode": "6位A股代码或市场代码",
  "market": "A股|港股|美股|待验证",
  "marketValue": "待更新",
  "marketCap": "待更新",
  "gain": "待更新",
  "changePercent": "待更新",
  "marketCapValue": null,
  "gainValue": null,
  "isLimitUp": false,
  "relationLevel": "T0|T1|T2|T3|T4",
  "relationLevelRank": 0,
  "relationScore": 0,
  "segment": "产业链位置",
  "chainStage": "产业链位置",
  "coreStatus": "核心地位",
  "corePosition": "核心地位",
  "investmentLogic": "一句话投资逻辑",
  "linkages": ["子板块或标签(T等级)"],
  "scoreDetail": {
    "technologyBarrier": 0,
    "domesticSubstitution": 0,
    "earningsElasticity": 0,
    "valuationSafety": 0,
    "styleFit": 0
  },
  "evidenceType": "公司公告|交易所公告|券商研报|公开新闻|产业调研|待验证",
  "verificationStatus": "已验证|部分验证|待验证|数据冲突",
  "sourceLinks": [],
  "keyValidationPoints": [],
  "deepReport": "",
  "source": "",
  "needManualReview": false,
  "reviewStatus": "pending|passed|failed|not_required",
  "status": "active|candidate|excluded"
}
```

T-level definitions:

- `T0`: direct core beneficiary or industry-chain bottleneck leader.
- `T1`: important participant with clear but not irreplaceable benefit.
- `T2`: related company with partial exposure or weaker earnings elasticity.
- `T3`: indirect relation, sentiment or secondary mapping.
- `T4`: weak concept relation; include only when the user asks for broad coverage.

Compatibility rules for `AiMarketMapper`:

- `stockName` must equal `name`; `stockCode` must equal `code`.
- `marketCap` must equal `marketValue`; `changePercent` must equal `gain`.
- `chainStage` must equal `segment`; `corePosition` must equal `coreStatus`.
- `relationLevelRank` is optional in model output. If present, use T0=0, T1=1, T2=2, T3=3, T4=4, unknown=9. Java will derive it when missing.
- `marketCapValue`, `gainValue`, and `isLimitUp` are optional numeric snapshots. Use them only when backed by reliable market data; otherwise use `null`/`false` and let `stock_basic` refresh fill them.
- `deepReport` should be an object or JSON-compatible string containing `whyRankHere`, `chainPositionDetail`, `barrierDetail`, `earningsElasticityDetail`, `sourceEvidence`, and `keyTrackingPoints` when the stock appears in a sector/news/research relation list.

Scoring default:

- `technologyBarrier` 30%
- `domesticSubstitution` 25%
- `earningsElasticity` 25%
- `valuationSafety` 20%
- `styleFit` can be included for short-term ranking but must not overwrite industry facts.

## 4. Source Verification Schema

Use this for `news_event`, `memo_research`, and any output based on non-obvious source claims:

```json
{
  "sourceVerification": {
    "foundOriginal": false,
    "originalSourceName": "待验证",
    "originalSourceUrl": "",
    "sourceType": "官方公告|交易所公告|权威媒体|券商研报|专家交流|产业纪要|网传小作文|市场传闻|待验证",
    "crossCheckSources": [],
    "credibilityScore": 0,
    "credibilityReason": "为什么给这个可信度",
    "suspiciousPoints": [],
    "verificationStatus": "已验证|部分验证|待验证|数据冲突"
  }
}
```

If no official or authoritative source is found, put this sentence at the front of `analysis.riskWarning`:

`该消息来源为市场传闻，尚未找到官方或权威媒体确认，存在证伪风险。`

## 5. Industry Decomposition Schema

Use this for `sector_stock_map`, `news_event`, and `memo_research`:

```json
{
  "industryChainPanorama": [],
  "decomposition": {
    "title": "产业链拆解标题",
    "panorama": [
      {
        "segment": "上游材料|上游设备|中游制造|下游应用|技术路线|其他",
        "coreDetail": "核心细分方向",
        "barrier": "壁垒描述",
        "valueTransfer": "高|中|低|待验证"
      }
    ],
    "upstream": [
      {
        "order": 1,
        "company": "公司名称",
        "code": "代码",
        "segment": "环节",
        "coreStatus": "核心地位"
      }
    ],
    "upstreamKeyData": "上游关键数据，缺来源则标待验证",
    "midstream": {
      "firstTier": [],
      "secondTier": [],
      "thirdTier": [],
      "techGap": "技术差距或待验证"
    },
    "downstream": [
      {
        "scenario": "应用场景",
        "dosage": "用量/价值量，缺来源填待验证",
        "driver": "驱动因素"
      }
    ],
    "investmentRanking": [
      {
        "order": 1,
        "company": "公司名称",
        "logic": "排序理由"
      }
    ],
    "validationPoints": []
  },
  "downstreamValueMeasurements": [],
  "keyValidationPoints": []
}
```

## 6. Mode Payloads

### 6.1 `sector_tree`

Use for sector-to-subsector generation.

Required fields:

```json
{
  "sectorName": "主板块",
  "existingSubSectors": [],
  "candidates": [
    {
      "name": "子板块名称",
      "level": 2,
      "description": "一句话产业定位",
      "categoryType": "上游材料|上游设备|中游制造|中游工艺|下游应用|技术路线|市场题材分支|其他",
      "isCore": false,
      "reason": "为什么应该加入"
    }
  ]
}
```

Persistence target:

```json
{
  "persistContract": {
    "bizType": "sector_tree",
    "targetTables": ["hot_sub_sector"],
    "writeMode": "candidate_upsert_pending_review"
  }
}
```

Rules:

- Produce at least 6 candidates unless the input scope is too narrow.
- Cover upstream, midstream, and downstream when applicable.
- Mark only 1-2 candidates as `isCore=true`.
- Do not duplicate existing sub-sector names.
- This is a pure industry-chain mode. Do not output message authenticity, market-style judgement, short-term trading-value ranking, or style-switch plans.
- `categoryType` must be one of `上游材料|上游设备|中游制造|中游工艺|下游应用|技术路线|市场题材分支|其他`.
- Use `level=2` for broad industry-chain links and `level=3` for concrete sub-segments, technologies, materials, processes, or applications.

### 6.2 `sector_stock_map`

Use for sector/sub-sector to stock candidates.

Required fields:

```json
{
  "sectorName": "主板块",
  "subSectorName": "子板块",
  "decomposition": {
    "panorama": [],
    "upstream": [],
    "midstream": {"firstTier": [], "secondTier": [], "thirdTier": []},
    "downstream": [],
    "investmentRanking": [],
    "validationPoints": []
  },
  "stocks": [
    {
      "code": "6位代码",
      "name": "公司名称",
      "relationLevel": "T0|T1|T2|T3|T4",
      "relationScore": 0,
      "segment": "产业链位置",
      "coreStatus": "核心地位",
      "investmentLogic": "投资逻辑",
      "linkages": []
    }
  ]
}
```

Persistence target:

```json
{
  "persistContract": {
    "bizType": "sector_stock_map",
    "targetTables": ["hot_sub_sector", "sector_related_stock", "stock_basic"],
    "writeMode": "upsert_by_bizId_and_stockCode"
  }
}
```

Rules:

- Prefer at least 10 stock candidates.
- If fewer than 10 are supportable, output fewer and explain in `qualityControl.manualReviewReasons`.
- Do not invent codes. If code cannot be verified, exclude the stock or mark `needManualReview=true`.
- This is a pure industry-chain mode. Do not output message authenticity, market-style judgement, short-term trading-value ranking, or style-switch plans.
- `stocks` must be top-level. Do not put the primary stock list only under `payload.stocks`.
- `decomposition` must use the frontend-compatible shape from section 5 (`panorama`, `upstream`, `midstream.firstTier/secondTier/thirdTier`, `downstream`, `investmentRanking`, `validationPoints`). Do not output only `{nodes,edges}`.

### 6.3 `news_event`

Use for news, rumors, policies, product launches, screenshots, PDFs, or URLs.

Required fields:

```json
{
  "analysis": {
    "promptVersion": "message-analysis-kimi-v1",
    "displayTitle": "",
    "displaySummary": "",
    "newsValue": "",
    "coreLogic": "",
    "catalystType": "",
    "authenticityLevel": "高|中|低|待验证",
    "authenticityScore": 0,
    "sourceReliability": "",
    "suspiciousPoints": [],
    "needManualVerify": false,
    "newsQualityLevel": "高|中|低",
    "newsQualityScore": 0,
    "coreValue": "",
    "marketAttentionReason": "",
    "shortTermTradeValue": "",
    "midLongTermValue": "",
    "isNewCatalyst": false,
    "isRepeatedNews": false,
    "displayPriority": "high|medium|low",
    "oneSentenceSummary": "",
    "keyPoints": [],
    "mainBenefitDirection": "",
    "mainRisk": "",
    "mainSector": "",
    "subSectors": [],
    "hotScoreTotal": 0,
    "hotScoreDetail": {},
    "mainTags": [],
    "riskWarning": "",
    "showAuthenticityBadge": true,
    "showManualVerifyBadge": false,
    "auditConfidence": "高|中|低",
    "missingInformation": [],
    "reviewSuggestions": [],
    "marketImpact": "",
    "riskTips": []
  },
  "sourceVerification": {},
  "contentTags": [],
  "industryChainPanorama": [],
  "decomposition": {},
  "downstreamValueMeasurements": [],
  "keyValidationPoints": [],
  "stocks": []
}
```

Persistence target:

```json
{
  "persistContract": {
    "bizType": "news_event",
    "targetTables": ["news_analysis", "news_related_stock", "news", "stock_basic"],
    "writeMode": "upsert_by_taskNo_newsId_stockCode"
  }
}
```

### 6.4 `memo_research`

Use for meeting minutes, broker reports, expert calls, company notes, and industry notes.

Use the same structure as `news_event`, but `analysis` must include:

- `researchType`
- `institution`
- `researcherOrSpeaker`
- `sourceName`
- `sourceUrl`
- `authenticityReason`
- `researchQualityLevel`
- `researchQualityScore`
- `mainIncrementalInfo`
- `hotLogic`
- `companyAnalysis`
- `industryAnalysis`
- `trackingIndicators`
- `hotScore`

Rules:

- Company memo: output only the main company by default. Expand to suppliers/customers/peers only if explicitly mentioned in the source text.
- Broker report: extract rating change, valuation assumptions, target price, and analyst/institution if available.
- Expert call: lower credibility if the expert identity cannot be verified.

Persistence target:

```json
{
  "persistContract": {
    "bizType": "memo_research",
    "targetTables": ["research_analysis", "research_related_stock", "research_report", "stock_basic"],
    "writeMode": "upsert_by_taskNo_reportId_stockCode"
  }
}
```

### 6.5 `single_stock`

Use for one A/HK/China-listed stock deep analysis.

Rendering priority: `single_stock` must be returned as the JSON object itself. Do not prepend prose, progress narration, or Markdown fences. `reportMarkdown` should be concise; the frontend renders primarily from `sections`, `overallScore`, and `recommendation`.

Required fields:

```json
{
  "stockName": "",
  "stockCode": "",
  "market": "A股|港股|中概|待验证",
  "overallScore": 0,
  "recommendation": "强烈买入|买入|持有|观望|回避",
  "targetReturn": "待验证",
  "stopLoss": "-8%",
  "sections": {
    "companyOverview": {},
    "financials": {},
    "businessStructure": {},
    "competitiveAnalysis": {},
    "growthDrivers": {},
    "valuation": {},
    "risks": {},
    "scoring": {},
    "investmentAdvice": {}
  },
  "dataSources": []
}
```

`sections` maps to `stock_analysis` as:

- `companyOverview` -> `stock_analysis.company_overview`
- `financials` -> `stock_analysis.financials`
- `businessStructure` -> `stock_analysis.business_structure`
- `competitiveAnalysis` -> `stock_analysis.competitive_analysis`
- `growthDrivers` -> `stock_analysis.growth_drivers`
- `valuation` -> `stock_analysis.valuation`
- `risks` -> `stock_analysis.risks`
- `scoring` -> `stock_analysis.scoring`
- `investmentAdvice` -> `stock_analysis.investment_advice`

Persistence target:

```json
{
  "persistContract": {
    "bizType": "single_stock",
    "targetTables": ["stock_analysis"],
    "writeMode": "upsert_by_stockCode_taskNo"
  }
}
```

Use the `cn-stock-analysis` framework to fill the sections. `overallScore` is weighted:

- fundamentals 20%
- growthCertainty 20%
- competitiveBarrier 15%
- valuationAttraction 15%
- financialHealth 15%
- catalyst 15%

### 6.6 `us_stock_options`

Use for one US-listed stock when options timing is requested.

Start from `single_stock`, then add:

```json
{
  "options": {
    "dataAvailable": false,
    "expirations": [],
    "putCallRatio": "待验证",
    "atmIv": "待验证",
    "ivRank": "待验证",
    "maxPain": "待验证",
    "callWall": "待验证",
    "putWall": "待验证",
    "gammaExposure": "待验证",
    "skew": "待验证",
    "optionsTimingView": "确认|冲突|中性|不可判断",
    "riskNotes": []
  }
}
```

Never fabricate options-chain data. If unavailable, set `options.dataAvailable=false` and explain in `qualityControl.missingFields`.

## 7. Final Validation Checklist

Before returning structured output:

1. JSON parses as one object.
2. No Markdown fences or extra prose.
3. Required envelope fields are present.
4. Realtime fields are sourced or set to `待更新`.
5. Unsupported claims are marked `待验证`.
6. Stock codes are real or excluded.
7. Source risk is reflected in `qualityControl` and `sourceVerification`.
8. If fewer than required candidates are produced, the reason is stated in `qualityControl.manualReviewReasons`.
9. China-market outputs that include `persistContract` must have `persistContract.mapper="AiMarketMapper"` and an `ingest.url` supplied by payload or left empty for preview-only validation.

For saved JSON files, validate with:

```bash
python3 ~/.kimi_openclaw/workspace/skills/cn-market-structured-output/scripts/validate_market_output.py output.json
```
