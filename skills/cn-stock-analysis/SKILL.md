---
name: cn-stock-analysis
description: Use this skill when the user asks to analyze A-share, Hong Kong, or China-listed stocks, asks whether a Chinese stock is worth buying, asks for target prices, portfolio allocation, replacement/addition decisions, or requests a domestic stock research report using a fundamental-analysis framework. DEFAULT OUTPUT IS ONE kimi-market-v1 JSON OBJECT (mode=single_stock); 收到「分析XX」这类自然语言也必须直接返回 JSON 对象本身，禁止开场白、过程叙述、Markdown 围栏或先解释后 JSON。reportMarkdown 精简，优先保证 sections(9模块)/overallScore/recommendation 可渲染。
---

# cn-stock-analysis

Use this skill for China/HK stock analysis and portfolio-fit decisions.

## MUST（开工前必读，不可跳过）

1. 默认产出 **一个合法 kimi-market-v1 JSON 对象本身**，`mode="single_stock"`，外面不裹 Markdown 代码围栏。
1.1. **执行预算（防被 KimiClaw 终止 / terminated）——最高优先级**：本分析必须**又快又短地收尾**。
   - 工具调用（AnySearch/extract/kimi_finance 等）**累计不超过 4 次**；**禁止**对同一来源反复重试或无限检索。
   - 检索缓慢、失败或信息不全时**立即停止检索**，用已有信息 + 把缺失项标 `待验证` 直接产出完整 JSON——**宁可多个字段 `待验证`，也绝不能把任务拖长到被 terminated**。
   - 不要做"完整十步长文"；直接、尽快地一次性吐出完整结构化 JSON（9 个 `sections` + 评分 + 建议），`reportMarkdown` 保持短。
2. 动手前先读：本文件全文 → `references/framework.md` → `cn-market-structured-output/references/protocol.md`。
3. **最终回答的第一个字符必须是 `{`，最后一个字符必须是 `}`**。禁止输出“现在我开始构建报告”“下面是JSON”“分析如下”等任何开场白、过程叙述或结束语。
4. `reportMarkdown` 必须精简，保留结论、关键证据、主要风险和操作建议即可；不要输出超长十步全文。优先保证 `sections / recommendation / overallScore / targetReturn / stopLoss / dataSources` 完整。
5. 从精简 `reportMarkdown` 标题生成 `reportSections` + `reportSectionTree`，再补 `sections / recommendation / overallScore / targetReturn / stopLoss / dataSources`。
5. 如果 Java payload 提供 `taskNo`/`bizId`/`autoPersist`/`ingest`，必须在 JSON 中填 `persistContract`；落库只通过 `cn-market-writeback` + 后端 `AiMarketMapper`。
6. 数据走 AnySearch 优先；缺数据标 `待验证`，**禁止编造**价格、财务、目标价、市占率。
7. 仅当用户明确说「用自然语言/口语/不要 JSON」时，才只输出 Markdown。

## Default Return Contract

Return one valid JSON object by default. Use `~/.kimi_openclaw/workspace/skills/cn-market-structured-output/references/protocol.md` and output `mode="single_stock"`. `reportMarkdown` should be concise; structured `sections` are the primary render source.

Only use Markdown/natural language if the user explicitly asks for a prose report, quick chat answer, or non-JSON explanation.

## Required Workflow

1. Get the current date before using current prices, recent earnings, news, or relative time windows.
2. Read `references/framework.md`.
3. Identify the market, company name, ticker, current price if provided, investment horizon, risk preference, and existing portfolio if provided.
4. **AnySearch 优先，但严格限量（≤4 次工具调用，见 MUST 1.1）**：先读 `anysearch` skill 与其 `runtime.conf`，用 finance 垂直搜索和 `extract` 拉**最关键的 1-2 篇**公告/研报/新闻正文即可；`kimi_finance` 负责实时行情；**不要默认使用 `kimi_search`**，仅当 AnySearch 连续失败且在 `dataPath` 注明后才可 fallback。**一旦达到调用上限或检索变慢，立刻停止、直接出 JSON。**
5. Use current and sourceable data whenever tools are available. Do not invent prices, financials, analyst targets, market share, valuation multiples, or customer concentration.
6. If required data cannot be retrieved, explicitly mark it as unavailable and continue with a constrained analysis.
7. Read `~/.kimi_openclaw/workspace/skills/cn-market-structured-output/references/protocol.md` before composing the final answer.
8. **默认走精简模式**：直接产出 9 个 `sections` + `overallScore`/`recommendation`/`targetReturn`/`stopLoss` + 简短 `reportMarkdown`（结论、关键证据、风险、3/6/12 个月观点、仓位、缺数据备注）。**不要写完整十步长文**——长文会拖长生成时间、提高被 terminated 的风险。仅当用户明确要求超长完整报告时才扩写。
9. Build `persistContract` from the incoming payload when present. Use `bizType="single_stock"`, `mapper="AiMarketMapper"`, `targetTables=["stock_analysis"]`, and the supplied `ingest.url`; never hardcode an ingest host.
10. If `autoPersist=true`, validate the JSON then call `cn-market-writeback`. If `autoPersist=false`, return the complete JSON and ask whether to persist; on confirmation, call writeback with the same envelope.

## Output Rules

- Default to `mode="single_stock"` JSON with the common envelope and these top-level fields: `stockName`, `stockCode`, `market`, `overallScore`, `recommendation`, `targetReturn`, `stopLoss`, `sections`, `dataSources`.
- Include concise `reportMarkdown` with conclusion, key evidence, risks, and action plan. Keep it short enough to avoid stream truncation.
- Include heading-based document fields: `reportFormat="markdown-heading-tree-v1"`, `reportTitle`, `reportSections`, and `reportSectionTree`.
- `reportSections` must mirror the actual Markdown headings (`#`, `##`, `###`...), with `id`, `parentId`, `headingPath`, `headingMarkdown`, `childrenIds`, line numbers, and `contentMarkdown`. `contentMarkdown` 保持精简（每节几句要点即可），**不要为了铺满字数而拉长**——结构化 `sections` 才是前端主渲染来源，`reportMarkdown`/`reportSections` 保持短以避免生成超时被终止。
- `sections` must include `companyOverview`, `financials`, `businessStructure`, `competitiveAnalysis`, `growthDrivers`, `valuation`, `risks`, `scoring`, and `investmentAdvice`.
- Lead inside JSON with a direct `recommendation`: 强烈买入 / 买入 / 持有 / 观望 / 回避.
- Every numeric claim should include a source label such as financial report period, exchange/quote source, analyst institution/date, or clearly say "source unavailable".
- Add a short data-path note when tools are used: AnySearch / Kimi Search / Kimi Finance / source unavailable.
- Keep the logic causal: because A, therefore B, so action C.
- Keep risk analysis independent and concrete.
- Put executable portfolio guidance, position size, trigger conditions, target price, and stop-loss in `sections.investmentAdvice`.
- Include optional `stockMeta` aliases (`segment`, `coreStatus`, `chainStage`, `corePosition`, `investmentLogic`) when the request is tied to a relation-card decomposition.
- For persistable gateway requests, include `persistContract.mapper="AiMarketMapper"` and `targetTables=["stock_analysis"]`.
- Return one valid JSON object only. Do not wrap in Markdown fences. Do not output any natural-language preface or progress narration. Mark unsupported data as `待验证` or `source unavailable`.

## Guardrails

- This is investment research support, not guaranteed investment advice.
- Do not hide negative risks.
- For high-valuation stocks, show actual valuation data and avoid unsupported bubble language.
- For geopolitically sensitive names, include a separate risk section.
- If earnings were released recently, include a dedicated earnings-impact section.
- If price moved more than roughly 15% since a prior analysis mentioned by the user, re-evaluate valuation.
