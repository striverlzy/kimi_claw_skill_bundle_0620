---
name: cn-stock-analysis
description: Use this skill when the user asks to analyze A-share, Hong Kong, or China-listed stocks, asks whether a Chinese stock is worth buying, asks for target prices, portfolio allocation, replacement/addition decisions, or requests a domestic stock research report using a fundamental-analysis framework. DEFAULT OUTPUT IS ONE kimi-market-v1 JSON OBJECT (mode=single_stock); 收到「分析XX」这类自然语言也必须先读 SKILL.md 与 cn-market-structured-output/references/protocol.md，再返回完整 JSON，其中 reportMarkdown 是完整十步研报。不要直接输出简短 Markdown 摘要。
---

# cn-stock-analysis

Use this skill for China/HK stock analysis and portfolio-fit decisions.

## MUST（开工前必读，不可跳过）

1. 默认产出 **一个合法 kimi-market-v1 JSON 对象**，`mode="single_stock"`，外面不裹 Markdown 代码围栏。
2. 动手前先读：本文件全文 → `references/framework.md` → `cn-market-structured-output/references/protocol.md`。
3. `reportMarkdown` 必须是 **完整十步研报**（结论摘要、业务结构、竞争对比、近期财务、未来增速、估值、风险、投资结论、组合配置、九因子评分）。
4. 从 `reportMarkdown` 标题生成 `reportSections` + `reportSectionTree`，再补 `sections / recommendation / overallScore / targetReturn / stopLoss / dataSources`。
5. 如果 Java payload 提供 `taskNo`/`bizId`/`autoPersist`/`ingest`，必须在 JSON 中填 `persistContract`；落库只通过 `cn-market-writeback` + 后端 `AiMarketMapper`。
6. 数据走 AnySearch 优先；缺数据标 `待验证`，**禁止编造**价格、财务、目标价、市占率。
7. 仅当用户明确说「用自然语言/口语/不要 JSON」时，才只输出 Markdown。

## Default Return Contract

Return one valid JSON object by default. Use `~/.kimi_openclaw/workspace/skills/cn-market-structured-output/references/protocol.md` and output `mode="single_stock"`. Preserve the original full report in `reportMarkdown`, then derive `reportSections` and `reportSectionTree` from the Markdown headings; structured fields extend the report, they do not replace it.

Only use Markdown/natural language if the user explicitly asks for a prose report, quick chat answer, or non-JSON explanation.

## Required Workflow

1. Get the current date before using current prices, recent earnings, news, or relative time windows.
2. Read `references/framework.md`.
3. Identify the market, company name, ticker, current price if provided, investment horizon, risk preference, and existing portfolio if provided.
4. **AnySearch 优先**：先读 `anysearch` skill 与其 `runtime.conf`，用 finance 垂直搜索和 `extract` 拉公告/研报/新闻正文；`kimi_finance` 负责实时行情；**不要默认使用 `kimi_search`**，仅当 AnySearch 连续失败且在 `dataPath` 注明后才可 fallback。
5. Use current and sourceable data whenever tools are available. Do not invent prices, financials, analyst targets, market share, valuation multiples, or customer concentration.
6. If required data cannot be retrieved, explicitly mark it as unavailable and continue with a constrained analysis.
7. Read `~/.kimi_openclaw/workspace/skills/cn-market-structured-output/references/protocol.md` before composing the final answer.
8. Produce the full ten-step analysis unless the user asks for a quick view. For a quick view, provide conclusion, valuation, risks, 3/6/12-month view, position size, and missing-data notes.
9. Build `persistContract` from the incoming payload when present. Use `bizType="single_stock"`, `mapper="AiMarketMapper"`, `targetTables=["stock_analysis"]`, and the supplied `ingest.url`; never hardcode an ingest host.
10. If `autoPersist=true`, validate the JSON then call `cn-market-writeback`. If `autoPersist=false`, return the complete JSON and ask whether to persist; on confirmation, call writeback with the same envelope.

## Output Rules

- Default to `mode="single_stock"` JSON with the common envelope and these top-level fields: `stockName`, `stockCode`, `market`, `overallScore`, `recommendation`, `targetReturn`, `stopLoss`, `sections`, `dataSources`.
- Include `reportMarkdown` with the complete human-readable ten-step report.
- Include heading-based document fields: `reportFormat="markdown-heading-tree-v1"`, `reportTitle`, `reportSections`, and `reportSectionTree`.
- `reportSections` must mirror the actual Markdown headings (`#`, `##`, `###`...), with `id`, `parentId`, `headingPath`, `headingMarkdown`, `childrenIds`, line numbers, and `contentMarkdown`. Do not compress the original report into only short fields.
- `sections` must include `companyOverview`, `financials`, `businessStructure`, `competitiveAnalysis`, `growthDrivers`, `valuation`, `risks`, `scoring`, and `investmentAdvice`.
- Lead inside JSON with a direct `recommendation`: 强烈买入 / 买入 / 持有 / 观望 / 回避.
- Every numeric claim should include a source label such as financial report period, exchange/quote source, analyst institution/date, or clearly say "source unavailable".
- Add a short data-path note when tools are used: AnySearch / Kimi Search / Kimi Finance / source unavailable.
- Keep the logic causal: because A, therefore B, so action C.
- Keep risk analysis independent and concrete.
- Put executable portfolio guidance, position size, trigger conditions, target price, and stop-loss in `sections.investmentAdvice`.
- Include optional `stockMeta` aliases (`segment`, `coreStatus`, `chainStage`, `corePosition`, `investmentLogic`) when the request is tied to a relation-card decomposition.
- For persistable gateway requests, include `persistContract.mapper="AiMarketMapper"` and `targetTables=["stock_analysis"]`.
- Return one valid JSON object only. Do not wrap in Markdown fences. Mark unsupported data as `待验证` or `source unavailable`.

## Guardrails

- This is investment research support, not guaranteed investment advice.
- Do not hide negative risks.
- For high-valuation stocks, show actual valuation data and avoid unsupported bubble language.
- For geopolitically sensitive names, include a separate risk section.
- If earnings were released recently, include a dedicated earnings-impact section.
- If price moved more than roughly 15% since a prior analysis mentioned by the user, re-evaluate valuation.
