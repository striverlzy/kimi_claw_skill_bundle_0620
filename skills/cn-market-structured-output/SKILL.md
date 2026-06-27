---
name: cn-market-structured-output
description: Use this skill when the user asks for structured JSON, frontend/backend/API-ready output, database persistence fields, examples, schemas, or normalized output rules for China market sector mapping, news/memo analysis, A-share beneficiary lists, or single-stock deep research.
---

# cn-market-structured-output

Use this skill as the output protocol layer for China-market research tasks. It does not replace the research skills; it normalizes their final answer into strict JSON when the user asks for frontend, backend, API, database, schema, or structured output.

## Required Workflow

1. Identify the output mode:
   - `sector_tree`: sector to sub-sector candidates.
   - `sector_stock_map`: sector/sub-sector to industry-chain map and stock candidates.
   - `news_event`: news, rumor, policy, product launch, or overseas catalyst.
   - `memo_research`: meeting minutes, expert call, broker report, company memo, or industry note.
   - `single_stock`: one A/HK/China-listed stock deep analysis.
   - `us_stock_options`: one US-listed stock with fundamental plus options timing.
2. Read `references/protocol.md`.
3. Use the relevant research skill for analysis:
   - `cn-catalyst-analysis` for `news_event` and `memo_research`.
   - `cn-sector-mapping` for `sector_tree` and `sector_stock_map`.
   - `cn-stock-analysis` for `single_stock`.
   - `us-stock-options-analysis` for `us_stock_options`.
4. Return one valid JSON object only. Do not wrap it in Markdown fences. The first visible character must be `{` and the last visible character must be `}`.
4.1. Do not emit planning, search summaries, tool summaries, or transition text before the JSON. Forbidden visible phrases include: “我将构建”, “正在构建”, “基于搜索到的信息”, “现在基于收集的信息”, “我已经收集了足够的信息”, “下面是 JSON”, “Now I'll construct”, and “Let me compile”. If any such text is about to be produced, delete it and output the JSON object directly.
5. If live data is unavailable, use `"待更新"` for realtime market fields and `"待验证"` for unsupported claims. Do not invent stock codes, prices, market caps, orders, customers, or market share.
6. For analysis modes other than `sector_tree`, compose the concise Markdown report first (规范 `#/##/###` 标题层级), set `reportSections` and `reportSectionTree` to `[]`, and let the end-step script derive `reportFormat`/`reportTitle`/`reportSections`/`reportSectionTree` from the Markdown headings（输出加速）。**优先用脚本补全**；脚本不可用时空数组 `[]` 也可交付——后端落库不读这两个字段、前端以 `reportMarkdown` + 结构化字段渲染，不要为补全而手写大段嵌套树或阻塞输出。
7. 输出加速末步：把含 `reportMarkdown` 的草稿 JSON（其余业务字段齐全、两个 section 字段为 `[]`）交给脚本回填——`scripts/markdown_report_to_json.py draft.json -o final.json`（脚本自动识别草稿、保留草稿所有字段，仅补全标题树）；也兼容旧用法 `scripts/markdown_report_to_json.py report.md --base-json output.json --output output.json`。
8. When validating a saved output file, run `scripts/validate_market_output.py <json-file>`.
9. **Cache (differentiated TTL)**: research skills `scripts/market_cache.py lookup <mode> <target>` before analyzing — a fresh hit returns the persisted local JSON (`qualityControl.servedFromCache=true`) and skips search+generation — and `scripts/market_cache.py store <mode> <target> <final.json>` after generating. TTL: 24h for `news_event`/`memo_research`/`single_stock`/`sector_*`; market-aware for `us_stock_options` (1h intraday US/Eastern 09:30–16:00, else until next open). Cache dir `~/.kimi_openclaw/workspace/cache/<mode>/`. Skip lookup when the user asks for the latest/refreshed data.

New-requirement fields (enforced by validator):

- `news_event`: `analysis.earliestPublishTime` + `analysis.earliestSourceUrl` (全网最早发布时间 + 最早来源完整 URL；未找到填 `待验证`).
- `memo_research`: `analysis.researchCategory` ∈ `{行业纪要, 公司纪要, 专家交流, 券商研报, 专题研报}`.

## Output Rules

- Always include `schemaVersion`, `mode`, `generatedAt`, `asOfDate`, `status`, `qualityControl`, and `dataPath`.
- The answer must start directly with `{"schemaVersion":"kimi-market-v1"` or the pretty-printed equivalent beginning with `{`. No visible prose may appear before or after the JSON object.
- Use Chinese field values by default, but keep JSON keys in camelCase English for frontend compatibility.
- Preserve the full report with the heading-based document fields: `reportFormat="markdown-heading-tree-v1"`, `reportTitle`, `reportMarkdown`, `reportSections`, and `reportSectionTree`.
- For `news_event` and `memo_research`, the "full report" must be a compact report: keep `reportMarkdown` around 1200 Chinese characters, keep each `reportSections[].contentMarkdown` around 120 Chinese characters, and keep `stocks` at no more than 8 entries unless the caller explicitly asks for more.
- `reportSections` must be generated from actual Markdown headings, with stable `id`, `parentId`, `headingPath`, `headingMarkdown`, `childrenIds`, line numbers, and `contentMarkdown`.
- `reportSectionTree` must be the nested version of the same `reportSections`, not a separate summary.
- For every stock item, include both primary frontend fields (`name`, `code`, `marketValue`) and compatibility aliases (`stockName`, `stockCode`, `marketCap`) when the mode contains `stocks`.
- Important facts must carry source labels or be marked `待验证`.
- `gain` must be `"待更新"` unless a reliable realtime quote source was actually used.
- `verificationStatus` must be one of `已验证`, `部分验证`, `待验证`, or `数据冲突`.
- `needManualReview` must be `true` when the task depends on rumor, unverified screenshots, unverifiable customer/order data, or incomplete market data.
- Do not stream a long article before finishing the JSON. When output budget is tight, prioritize a complete closing `}` over additional prose.
