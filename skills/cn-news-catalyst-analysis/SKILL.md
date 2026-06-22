---
name: cn-news-catalyst-analysis
description: Use this skill when the user provides or asks about an industry news item, market rumor, research note, meeting minutes, "小作文", policy item, product launch, supplier-chain clue, or overseas tech-giant catalyst and wants A-share transmission analysis, source verification, industry-chain mapping, beneficiary stock ranking, short-term theme value, market-style fit, or catalyst-driven trading ideas. DEFAULT OUTPUT IS ONE kimi-market-v1 JSON OBJECT (mode=news_event/memo_research/sector_stock_map/sector_tree); 收到自然语言催化剂提问也必须先读 SKILL.md 与 cn-market-structured-output/references/protocol.md，再返回完整 JSON，其中 reportMarkdown 是**精简催化剂要点**（每部分几句要点，不写长篇；结构化字段 decomposition/stocks/analysis 才是主渲染源且须完整）。最终回答必须直接是 JSON 对象本身（以 `{` 开头、`}` 结尾），禁止任何开场白/过程叙述（如“正在构建…分析”“我已收集到足够信息”），禁止先声明再补 JSON。不要直接输出简短 Markdown 摘要。
---

# cn-news-catalyst-analysis

Use this skill for catalyst-first China/A-share analysis and pure industry-chain sector decomposition. `news_event`/`memo_research` use the message verification framework; `sector_stock_map`/`sector_tree` use the industry-chain framework and must not run message-truth, market-style, or short-term trading-value ranking.

## MUST（开工前必读，不可跳过）

1. 默认产出 **一个合法 kimi-market-v1 JSON 对象**，按输入选 `mode=news_event/memo_research/sector_stock_map/sector_tree`，外面不裹 Markdown 代码围栏。
1.1. **最终回答的第一个字符必须是 `{`，最后一个字符必须是 `}`**。禁止输出“现在我已收集到足够的信息”“正在构建…分析”“下面是JSON”“分析如下”等任何开场白、过程叙述或结束语；禁止先声明再补 JSON。**必须在同一条回复里一次性直接输出完整 JSON**；即使研究尚未完全完成，也要直接产出当前可得的完整 JSON，缺失字段填 `待验证`，绝不允许只回一句开场白后停下。
1.2. **执行预算（防被 KimiClaw 终止 / terminated）——最高优先级**：分析必须**又快又短地收尾**。
   - 工具调用（AnySearch/extract/kimi_finance 等）**累计不超过 4 次**；**禁止**对同一来源反复重试或无限检索；达到上限或检索变慢就**立即停止检索**。
   - `reportMarkdown` 保持**精简**（每个板块几句要点即可，不写长篇全文）；`decomposition`/`stocks` 等结构化字段才是前端主渲染来源。
   - 检索失败/信息不全时，用已有信息 + 把缺失项标 `待验证` **直接产出完整 JSON**——**宁可多字段 `待验证`，也绝不能把任务拖长到被 terminated**。
2. 动手前先读：本文件全文 → `references/framework.md` → `cn-market-structured-output/references/protocol.md`。
3. `reportMarkdown` 一律**精简**（每板块几句要点，不写长篇，避免生成过长被 terminated）：`news_event`/`memo_research` 覆盖（消息核实、消息价值、产业链全景、受益排序、短期交易价值、风格切换、操作策略、风险与失效条件）的**要点**；`sector_stock_map`/`sector_tree` 覆盖（产业链全景、上游核心、中游三档、下游价值量、核心标的综合排序、关键验证点）的**要点**，不做消息真伪验证/市场风格/短线交易价值排序。结构化字段(decomposition/stocks/...)才是主渲染来源，务必完整。
4. 从 `reportMarkdown` 标题生成 `reportSections` + `reportSectionTree`，再补 `analysis / sourceVerification / decomposition / stocks / keyValidationPoints / dataPath / qualityControl`。
5. 如果 Java payload 提供 `taskNo`/`bizId`/`autoPersist`/`ingest`，必须在 JSON 中填 `persistContract`；落库只通过 `cn-market-writeback` + 后端 `AiMarketMapper`。
6. `news_event`/`memo_research` 数据走 AnySearch 优先；传闻必须核实并在 `analysis.riskWarning` 标注证伪风险；缺数据标 `待验证`，**禁止编造**链接、时间、订单、市占率、股价、市场风格信号。`sector_stock_map`/`sector_tree` 不做 AnySearch 依赖调整，按现有可用来源补产业链事实。
7. 仅当用户明确说「用自然语言/口语/不要 JSON」时，才只输出 Markdown。

## Default Return Contract

Return one valid JSON object by default. Use `~/.kimi_openclaw/workspace/skills/cn-market-structured-output/references/protocol.md`.

Mode selection:

- `sector_tree`: sector-to-subsector generation.
- `sector_stock_map`: sector/subsector-to-stock mapping.
- `news_event`: news, rumor, policy, product launch, or overseas catalyst.
- `memo_research`: meeting minutes, expert calls, broker reports, company notes, or industry notes.

Mode framework split:

- `sector_tree` and `sector_stock_map`: pure industry-chain modes. Skip message source verification, information-increment reset, market-style judgement, short-term trading-value ranking, and style-switch plans. Output top-level `stocks` and frontend decomposition shape from protocol.md.
- `news_event` and `memo_research`: catalyst/message modes. Keep the full message verification, authenticity, market-style, and short-term trading-value framework.

Only use Markdown/natural language if the user explicitly asks for a prose report, quick chat answer, or non-JSON explanation.

Keep `reportMarkdown` **concise** (key points per section, no long prose), then derive `reportSections` and `reportSectionTree` from the Markdown headings; the structured fields (`decomposition`/`stocks`/`analysis`/...) are the primary render source and must be complete, while `reportMarkdown` stays short so the task finishes within KimiClaw's per-task budget and is never terminated.

## Required Workflow

1. Current date: if it is already provided in the input/context, use it directly — do NOT spend an extra tool call or turn just to fetch the date. Only look it up if truly absent.
2. Read `references/framework.md`.
3. Identify the input type and mode. If mode is `sector_tree` or `sector_stock_map`, switch to the pure industry-chain workflow in `references/framework.md` and do not apply message verification / short-term trading framework.
4. **AnySearch 优先**：先读 `anysearch` skill 与其 `runtime.conf`，做来源发现、垂直搜索、batch_search 和 `extract` 全文抓取；`kimi_finance` 用于行情反应核验；**不要默认使用 `kimi_search`**，仅当 AnySearch 连续失败且在 `dataPath` 注明后才可 fallback。
5. Verify the message using the strongest available sources: official company/regulator/exchange sources first, then major financial media or industry media, then market-price cross-checks. Do not treat unverified rumors as facts.
6. If the catalyst involves overseas giants such as NVIDIA, Microsoft, Tesla, Apple, Google, AMD, Broadcom, TSMC, or ASML, explicitly analyze the transmission path into A-shares: direct supplier, indirect supplier, industry-chain bottleneck, domestic substitution, or pure sentiment mapping.
7. Build the industry-chain map before ranking stocks. Identify upstream/midstream/downstream roles, bottleneck links, value-transfer efficiency, domestic-substitution status, and global competition.
8. Separate three rankings when relevant: industry-chain value, company fundamental benefit, and short-term trading value. Do not assume the highest industry value stock is the best short-term trade.
9. Judge whether the core conflict is industrial change or market-style rotation. If industrial change is dominant, do not mechanically exclude large industry leaders from the top candidates.
10. If current market-style data is unavailable, mark it as unavailable and give a conditional style plan instead of fabricating limit-up height, market-cap distribution, Dragon-Tiger list behavior, yellow/white line divergence, or drawdown statistics.
11. Read `~/.kimi_openclaw/workspace/skills/cn-market-structured-output/references/protocol.md` before composing the final answer and choose:
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
14. **永远一次性直接输出完整 JSON，绝不向用户提问、确认、澄清或等待二次交互。** 落库完全由后端决定：`autoPersist=true` 时（且 payload 带 `ingest.url`）才调 `cn-market-writeback` 发送同一份完整信封；`autoPersist=false` 时**只返回完整 JSON 即可，不要问"是否落库"、不要停下等用户**（落库由后端 ingest 或管理端确认 UI 处理，与本 skill 无关）。信息不足就用 `待验证` 填满字段，照样输出**完整可解析**的 JSON。

## Output Rules

- Default to JSON with the common envelope and mode-specific fields from `protocol.md`.
- Include a **concise** `reportMarkdown` (key points only); the structured fields are the primary render source and must be complete and valid.
- Include heading-based document fields: `reportFormat="markdown-heading-tree-v1"`, `reportTitle`, `reportSections`, and `reportSectionTree`.
- `reportSections` must mirror the actual Markdown headings (`#`, `##`, `###`...), with `id`, `parentId`, `headingPath`, `headingMarkdown`, `childrenIds`, line numbers, and concise `contentMarkdown`. Keep the heading coverage complete, but keep section prose short; detailed rankings and evidence belong in structured fields.
- Put the credibility verdict in `sourceVerification.verificationStatus`, `analysis.authenticityLevel`, and `analysis.riskWarning`.
- If the source is a rumor or no authoritative source is found, put the required warning at the start of `analysis.riskWarning`.
- Always separate message truth, industry value, A-share transmission, beneficiary ranking, short-term trading value, risk, and invalidation inside `analysis`, `decomposition`, `stocks`, and `keyValidationPoints`.
- Add a brief data-path note in `dataPath`: AnySearch / Kimi Search / Kimi Finance / manual source unavailable, so the user can see which layer produced each important fact.
- Cite source labels for all important facts: official source, exchange filing, media outlet/date, industry report/date, quote source/date, or "source unavailable".
- For each recommended stock, state its exact industry-chain position and why that position benefits from the catalyst.
- Include invalidation conditions: official denial, no price confirmation, key leader breaking trend, Dragon-Tiger list deterioration, theme fails to spread, or industry-chain transmission proves false.
- Keep the answer proportional while always respecting the execution budget: serious catalyst research should keep full coverage in structured fields, with concise `reportMarkdown`; quick "这消息怎么看" questions may be even shorter but must still return valid JSON by default.
- For mode payloads that may be persisted, include `persistContract.mapper="AiMarketMapper"` and the target tables defined by `protocol.md`.
- Return one valid JSON object only. Do not wrap in Markdown fences. Mark unsupported claims as `待验证`.

## Guardrails

- This is investment research support, not guaranteed investment advice.
- Do not fabricate links, publication times, orders, customer relationships, market share, stock prices, or market-style signals.
- Do not convert a rumor into a buy recommendation without an explicit uncertainty warning.
- Do not mechanically prefer small caps; adapt ranking to market style and catalyst type.
- Do not ignore industry leaders when the catalyst changes technology routes, standards, cost structure, or supply-chain access.
- Do not equate overseas-company good news with direct A-share benefit; prove the transmission path or mark it as sentiment-only.
