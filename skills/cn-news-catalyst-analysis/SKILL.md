---
name: cn-news-catalyst-analysis
description: Use this skill when the user provides or asks about an industry news item, market rumor, research note, meeting minutes, "小作文", policy item, product launch, supplier-chain clue, or overseas tech-giant catalyst and wants A-share transmission analysis, source verification, industry-chain mapping, beneficiary stock ranking, short-term theme value, market-style fit, or catalyst-driven trading ideas. DEFAULT OUTPUT IS ONE kimi-market-v1 JSON OBJECT (mode=news_event/memo_research/sector_stock_map/sector_tree); 收到自然语言催化剂提问也必须先读 SKILL.md 与 cn-market-structured-output/references/protocol.md，再返回完整 JSON，其中 reportMarkdown 是完整催化剂报告。不要直接输出简短 Markdown 摘要。
---

# cn-news-catalyst-analysis

Use this skill for catalyst-first China/A-share analysis: verify a news item or rumor, map its industry-chain impact, identify A-share beneficiaries, and separate industrial value from short-term trading value.

## MUST（开工前必读，不可跳过）

1. 默认产出 **一个合法 kimi-market-v1 JSON 对象**，按输入选 `mode=news_event/memo_research/sector_stock_map/sector_tree`，外面不裹 Markdown 代码围栏。
2. 动手前先读：本文件全文 → `references/framework.md` → `cn-market-structured-output/references/protocol.md`。
3. `reportMarkdown` 必须是 **完整催化剂报告**（消息核实、消息价值、产业链全景、受益排序、短期交易价值、风格切换、操作策略、风险与失效条件）。
4. 从 `reportMarkdown` 标题生成 `reportSections` + `reportSectionTree`，再补 `analysis / sourceVerification / decomposition / stocks / keyValidationPoints / dataPath / qualityControl`。
5. 如果 Java payload 提供 `taskNo`/`bizId`/`autoPersist`/`ingest`，必须在 JSON 中填 `persistContract`；落库只通过 `cn-market-writeback` + 后端 `AiMarketMapper`。
6. 数据走 AnySearch 优先；传闻必须核实并在 `analysis.riskWarning` 标注证伪风险；缺数据标 `待验证`，**禁止编造**链接、时间、订单、市占率、股价、市场风格信号。
7. 仅当用户明确说「用自然语言/口语/不要 JSON」时，才只输出 Markdown。

## Default Return Contract

Return one valid JSON object by default. Use `/Users/doublej_w/.kimi_openclaw/workspace/skills/cn-market-structured-output/references/protocol.md`.

Mode selection:

- `sector_tree`: sector-to-subsector generation.
- `sector_stock_map`: sector/subsector-to-stock mapping.
- `news_event`: news, rumor, policy, product launch, or overseas catalyst.
- `memo_research`: meeting minutes, expert calls, broker reports, company notes, or industry notes.

Only use Markdown/natural language if the user explicitly asks for a prose report, quick chat answer, or non-JSON explanation.

Preserve the original full catalyst report in `reportMarkdown`, then derive `reportSections` and `reportSectionTree` from the Markdown headings; structured fields extend the report, they do not replace it.

## Required Workflow

1. Get the current date before analyzing recent news, market reaction, price moves, regulatory events, or relative time windows.
2. Read `references/framework.md`.
3. Identify the input type: official announcement, media report, research note, meeting minutes, market rumor, social-media "小作文", policy item, product launch, or overseas company catalyst.
4. **AnySearch 优先**：先读 `anysearch` skill 与其 `runtime.conf`，做来源发现、垂直搜索、batch_search 和 `extract` 全文抓取；`kimi_finance` 用于行情反应核验；**不要默认使用 `kimi_search`**，仅当 AnySearch 连续失败且在 `dataPath` 注明后才可 fallback。
5. Verify the message using the strongest available sources: official company/regulator/exchange sources first, then major financial media or industry media, then market-price cross-checks. Do not treat unverified rumors as facts.
6. If the catalyst involves overseas giants such as NVIDIA, Microsoft, Tesla, Apple, Google, AMD, Broadcom, TSMC, or ASML, explicitly analyze the transmission path into A-shares: direct supplier, indirect supplier, industry-chain bottleneck, domestic substitution, or pure sentiment mapping.
7. Build the industry-chain map before ranking stocks. Identify upstream/midstream/downstream roles, bottleneck links, value-transfer efficiency, domestic-substitution status, and global competition.
8. Separate three rankings when relevant: industry-chain value, company fundamental benefit, and short-term trading value. Do not assume the highest industry value stock is the best short-term trade.
9. Judge whether the core conflict is industrial change or market-style rotation. If industrial change is dominant, do not mechanically exclude large industry leaders from the top candidates.
10. If current market-style data is unavailable, mark it as unavailable and give a conditional style plan instead of fabricating limit-up height, market-cap distribution, Dragon-Tiger list behavior, yellow/white line divergence, or drawdown statistics.
11. Read `/Users/doublej_w/.kimi_openclaw/workspace/skills/cn-market-structured-output/references/protocol.md` before composing the final answer and choose:
   - `mode="sector_tree"` for sector-to-subsector generation.
   - `mode="sector_stock_map"` for sector/subsector-to-stock mapping.
   - `mode="news_event"` for news, rumor, policy, product launch, or overseas catalyst.
   - `mode="memo_research"` for meeting minutes, expert calls, broker reports, company notes, or industry notes.
12. After identifying concrete tickers that need deeper single-company analysis, recommend using `cn-stock-analysis` for A/HK names or `us-stock-options-analysis` for US-listed names.
13. Build `persistContract` from the incoming payload when present:
   - `taskNo`: idempotency key from Java.
   - `bizId`: sector/subsector/news/report id from Java.
   - `autoPersist`: default `false`; if `true`, call `cn-market-writeback` after validation.
   - `ingest.url` and token: use only the provided payload; never hardcode an ingest host.
14. If `autoPersist=false`, return the complete JSON and ask the user whether to persist. On confirmation, call `cn-market-writeback` with the same complete envelope.

## Output Rules

- Default to JSON with the common envelope and mode-specific fields from `protocol.md`.
- Include `reportMarkdown` with the complete human-readable catalyst report.
- Include heading-based document fields: `reportFormat="markdown-heading-tree-v1"`, `reportTitle`, `reportSections`, and `reportSectionTree`.
- `reportSections` must mirror the actual Markdown headings (`#`, `##`, `###`...), with `id`, `parentId`, `headingPath`, `headingMarkdown`, `childrenIds`, line numbers, and `contentMarkdown`. Do not compress the original report into only short fields.
- Put the credibility verdict in `sourceVerification.verificationStatus`, `analysis.authenticityLevel`, and `analysis.riskWarning`.
- If the source is a rumor or no authoritative source is found, put the required warning at the start of `analysis.riskWarning`.
- Always separate message truth, industry value, A-share transmission, beneficiary ranking, short-term trading value, risk, and invalidation inside `analysis`, `decomposition`, `stocks`, and `keyValidationPoints`.
- Add a brief data-path note in `dataPath`: AnySearch / Kimi Search / Kimi Finance / manual source unavailable, so the user can see which layer produced each important fact.
- Cite source labels for all important facts: official source, exchange filing, media outlet/date, industry report/date, quote source/date, or "source unavailable".
- For each recommended stock, state its exact industry-chain position and why that position benefits from the catalyst.
- Include invalidation conditions: official denial, no price confirmation, key leader breaking trend, Dragon-Tiger list deterioration, theme fails to spread, or industry-chain transmission proves false.
- Keep the answer proportional: full framework for serious catalyst research; concise version for quick "这消息怎么看" questions.
- For mode payloads that may be persisted, include `persistContract.mapper="AiMarketMapper"` and the target tables defined by `protocol.md`.
- Return one valid JSON object only. Do not wrap in Markdown fences. Mark unsupported claims as `待验证`.

## Guardrails

- This is investment research support, not guaranteed investment advice.
- Do not fabricate links, publication times, orders, customer relationships, market share, stock prices, or market-style signals.
- Do not convert a rumor into a buy recommendation without an explicit uncertainty warning.
- Do not mechanically prefer small caps; adapt ranking to market style and catalyst type.
- Do not ignore industry leaders when the catalyst changes technology routes, standards, cost structure, or supply-chain access.
- Do not equate overseas-company good news with direct A-share benefit; prove the transmission path or mark it as sentiment-only.
