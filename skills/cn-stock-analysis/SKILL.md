---
name: cn-stock-analysis
description: Use this skill when the user asks to analyze A-share, Hong Kong, or China-listed stocks, asks whether a Chinese stock is worth buying, asks for target prices, portfolio allocation, replacement/addition decisions, or requests a domestic stock research report using a fundamental-analysis framework. DEFAULT OUTPUT IS ONE kimi-market-v1 JSON OBJECT (mode=single_stock); 收到「分析XX」这类自然语言也必须直接返回 JSON 对象本身，禁止开场白、过程叙述、Markdown 围栏或先解释后 JSON。reportMarkdown 精简，优先保证 sections(9模块)/overallScore/recommendation 可渲染。
---

# cn-stock-analysis

Use this skill for China/HK stock analysis and portfolio-fit decisions.

## 🔴 执行协议（最高优先级，覆盖下方一切“自己写 JSON”的旧表述）

**你是数据检索员，不是报告撰写员。** 9 个 `sections` 一律由并发脚本 `parallel_sections.py` 生成，**严禁你自己手写 sections**。严格按 4 步执行，做完第 4 步**立即结束**：

1. **检索**：用 `batch_search` 并发查关键数据（现价/财务/估值/分析师目标价/风险/催化），1–2 轮收尾。
2. **写 brief**：把数据写成 brief JSON 存到 `/tmp/kc_brief_<code>.json`（字段见 Required Workflow 第 8 步）。写完**别再写 sections**。
3. **跑脚本**：运行
   `python3 ~/.kimi_openclaw/workspace/skills/cn-market-structured-output/scripts/parallel_sections.py /tmp/kc_brief_<code>.json -o /tmp/kc_final_<code>.json --mode single_stock`
4. **交付并停**：把第 3 步命令打到 stdout 的那个完整 JSON **一字不改**作为最终回复，前后不加任何文字，然后**立即结束本次任务**。

**绝对禁止**：自己手写 9 个 sections；在脚本输出之外补充分析；运行脚本后继续检索或思考。脚本的 stdout 就是最终答案。**仅当脚本非零退出/报错时**才回退自己手写。

## MUST（开工前必读，不可跳过）

1. 最终交付 **一个合法 kimi-market-v1 JSON 对象本身**（由上面执行协议的脚本产出），`mode="single_stock"`，外面不裹 Markdown 代码围栏。
1.0.1. **Gateway 入口硬约束**：当用户消息第一行是 `cn-stock-analysis`，第二行或后续内容才是真正问题时，第一行只作为 skill 触发标记，必须忽略这行后处理后续问题。即使输入很短（如 `分析 贵州茅台`），也必须直接返回完整 `mode="single_stock"` JSON。绝对禁止把“现在我开始构建报告”“我已收集到足够信息”“Let me compile”等过程性句子作为最终回复；如果已经准备输出这些句子，立刻改为输出 JSON。
1.1. **执行预算（防被 KimiClaw 终止 / terminated）——最高优先级**：本分析必须**又快又短地收尾**。
   - **工具并行优先**：用 `batch_search` 把多条 query 一次性并发发出；AnySearch 与 `kimi_search` 可**同时并行**互补覆盖、交叉验证（冲突以官方/交易所/AnySearch 原文为准），`kimi_finance` 取实时行情。**绝不逐条串行等待**。
   - **有界预算**：检索控制在约 1–2 轮并发批次内（等价于以往 ≤4 次调用的耗时上限）；**禁止**对同一来源反复重试或无限检索。检索缓慢、失败或信息不全时**立即停止检索**，用已有信息 + 把缺失项标 `待验证` 直接产出完整 JSON——**宁可多个字段 `待验证`，也绝不能把任务拖长到被 terminated**。
   - 不要做"完整十步长文"；直接、尽快地一次性吐出完整结构化 JSON（9 个 `sections` + 评分 + 建议），`reportMarkdown` 保持短。
2. 动手前先读：本文件全文 → `references/framework.md` → `cn-market-structured-output/references/protocol.md`。
3. **最终回答的第一个字符必须是 `{`，最后一个字符必须是 `}`**。禁止输出“现在我开始构建报告”“下面是JSON”“分析如下”等任何开场白、过程叙述或结束语。
4. `reportMarkdown` 必须精简，保留结论、关键证据、主要风险和操作建议即可；不要输出超长十步全文。优先保证 `sections / recommendation / overallScore / targetReturn / stopLoss / dataSources` 完整。
5. **输出加速（reportSections/reportSectionTree 不手写）**：先写好精简 `reportMarkdown`（规范 `#/##/###` 标题层级）+ 业务字段（`sections / recommendation / overallScore / targetReturn / stopLoss / dataSources`），`reportSections` 与 `reportSectionTree` 先填空数组 `[]`，由末步脚本 `markdown_report_to_json.py` 自动补全标题树（见 Required Workflow 末步）。**优先用脚本补全**；若运行时无法跑脚本，**空数组 `[]` 也可直接交付**——后端落库不读这两个字段、前端以 `reportMarkdown` + 结构化 `sections` 渲染；**不要为补全而手写大段嵌套树，也不要因此阻塞输出**。
5. 如果 Java payload 提供 `taskNo`/`bizId`/`autoPersist`/`ingest`，必须在 JSON 中填 `persistContract`；落库只通过 `cn-market-writeback` + 后端 `AiMarketMapper`。若 payload 含 `persistManagedBy="java-gateway"` 或 `writebackPolicy="return_json_only"`，说明 Java 会在收到 JSON 后负责落库，**本 skill 禁止调用 `cn-market-writeback`，只返回完整 JSON**。
6. 数据走 AnySearch 优先；缺数据标 `待验证`，**禁止编造**价格、财务、目标价、市占率。
7. 仅当用户明确说「用自然语言/口语/不要 JSON」时，才只输出 Markdown。
8. **缓存优先(省时关键)**：分析前先查缓存(见 `## Cache`)，命中未过期直接返回缓存的本地 JSON、跳过搜索与生成；未命中才分析、末步写缓存。用户明确说「最新/刷新/重新分析」时跳过查命中。

## Cache（缓存：JSON 落本地，先查后写）

`target` = 股票代码或名称（如 `601318` 或 `贵州茅台`）。TTL：`single_stock` 24 小时。缓存落 `~/.kimi_openclaw/workspace/cache/single_stock/`。

```bash
# 第 0 步（搜索前）
python3 ~/.kimi_openclaw/workspace/skills/cn-market-structured-output/scripts/market_cache.py lookup single_stock "<股票代码或名称>"
#   {"hit":true,"doc":{...}} → 直接返回 doc 结束（已标 servedFromCache）；{"hit":false}(退出码1) → 继续分析
# 末步（标题树脚本生成最终 JSON 之后）
python3 ~/.kimi_openclaw/workspace/skills/cn-market-structured-output/scripts/market_cache.py store single_stock "<同一 target>" <final.json>
```

## Default Return Contract

Return one valid JSON object by default. Use `~/.kimi_openclaw/workspace/skills/cn-market-structured-output/references/protocol.md` and output `mode="single_stock"`. `reportMarkdown` should be concise; structured `sections` are the primary render source.

Only use Markdown/natural language if the user explicitly asks for a prose report, quick chat answer, or non-JSON explanation.

## Required Workflow

1. Current date: if it is already provided in the input/context, use it directly; do not spend an extra tool call or turn just to fetch the date. Only look it up when truly absent and needed for current prices, recent earnings, news, or relative time windows.
2. Read `references/framework.md`.
3. Identify the market, company name, ticker, current price if provided, investment horizon, risk preference, and existing portfolio if provided.
4. **数据并行获取（见 MUST 1.1 的有界预算）**：先读 `anysearch` skill 与其 `runtime.conf`，用 `batch_search` 一次并发多条 finance 垂直搜索 query，对最关键的 1-2 篇公告/研报/新闻用 `extract` 抓正文；**AnySearch 与 `kimi_search` 可并行**互补覆盖、结果交叉验证（冲突以官方/交易所/AnySearch 原文为准，并在 `dataPath` 注明）；`kimi_finance` 负责实时行情。**一旦达到预算或检索变慢，立刻停止、直接出 JSON。**
5. Use current and sourceable data whenever tools are available. Do not invent prices, financials, analyst targets, market share, valuation multiples, or customer concentration.
6. If required data cannot be retrieved, explicitly mark it as unavailable and continue with a constrained analysis.
7. Read `~/.kimi_openclaw/workspace/skills/cn-market-structured-output/references/protocol.md` before composing the final answer.
8. **写 brief（你唯一要写的内容；写完别再写 sections，直接进第 11 步跑脚本）**：把检索结果压成 brief JSON 写入 `/tmp/kc_brief_<code>.json`：
   ```json
   {
     "stockName":"..","stockCode":"..","market":"A股/港股",
     "lockedNumbers":{"currentPrice":"..","overallScore":<0-100>,"recommendation":"强烈买入/买入/持有/观望/回避","targetReturn":"..","stopLoss":".."},
     "facts":{"公司概况":"..","财务":"2024及最新季度营收/利润/毛利/ROE等原始数字","主营结构":"..","竞争格局与份额":"..","增长催化与一致预期":"..","估值倍数与分析师目标价":"..","风险":["..",".."],"评分维度":".."},
     "dataSources":["AnySearch ..","Kimi Search .."],
     "reportMarkdown":"<300-600字精简研报，规范 #/##/### 标题：结论/关键证据/风险/3-6-12月观点/仓位>",
     "persistContract":{ "见第 9 步，存在 payload 时带上" }
   }
   ```
   `facts` 尽量覆盖九维度原始数字（缺的标 `待验证`、禁止编造）；`lockedNumbers` 定下后所有 section 都会引用它。
9. Build `persistContract` from the incoming payload when present. Use `bizType="single_stock"`, `mapper="AiMarketMapper"`, `targetTables=["stock_analysis"]`, and the supplied `ingest.url`; never hardcode an ingest host. If `persistManagedBy="java-gateway"` or `writebackPolicy="return_json_only"`, set the contract for audit but **do not call `cn-market-writeback`**.
10. **永远一次性直接输出完整 JSON，绝不向用户提问、确认、澄清或等待二次交互。** 落库由后端决定：仅当 payload 明确 `autoPersist=true` 且没有 `persistManagedBy="java-gateway"` / `writebackPolicy="return_json_only"` 时，才校验后调 `cn-market-writeback` 发送同一份完整信封；其他情况**只返回完整 JSON 即可，不要问"是否落库"、不要停下等用户**（落库由后端 ingest 或管理端确认 UI 处理）。信息不足用 `待验证` 填满，照样输出**完整可解析**的 JSON。
11. **跑并发脚本并交付（必须执行，做完立即结束）**：
    ```bash
    python3 ~/.kimi_openclaw/workspace/skills/cn-market-structured-output/scripts/parallel_sections.py /tmp/kc_brief_<code>.json -o /tmp/kc_final_<code>.json --mode single_stock
    ```
    脚本内部把 9 个 section 分桶**并发调用模型**生成、强制引用 `lockedNumbers`、合并成完整信封、回填 `reportSections/reportSectionTree`、自检校验，并把最终 JSON 打到 **stdout**。**把该 stdout 的 JSON 一字不改作为最终回复，前后不加任何文字，然后立即结束**（含 `schemaVersion/mode/sections(9)/overallScore/recommendation/targetReturn/stopLoss/dataSources/report*`，且 `dataPath.generation="parallel-raw-llm"`）。脚本成功后按 `## Cache` 末步 `market_cache.py store` 写缓存。**仅当脚本报错/非零退出**时才回退自己手写 9 段，绝不交付不完整 JSON。

## Output Rules

- Default to `mode="single_stock"` JSON with the common envelope and these top-level fields: `stockName`, `stockCode`, `market`, `overallScore`, `recommendation`, `targetReturn`, `stopLoss`, `sections`, `dataSources`.
- Include concise `reportMarkdown` with conclusion, key evidence, risks, and action plan. Keep it short enough to avoid stream truncation.
- Include heading-based document fields: `reportFormat="markdown-heading-tree-v1"`, `reportTitle`, `reportSections`, and `reportSectionTree`.
- `reportSections` 默认填 `[]`，由末步脚本从 `reportMarkdown` 标题自动生成（含 `id`、`parentId`、`headingPath`、`headingMarkdown`、`childrenIds`、行号、`contentMarkdown`）；只需保持 `reportMarkdown` 的 `#/##/###` 标题层级规范。`contentMarkdown` 会随精简正文自然简短，**不要为了铺满字数而拉长**——结构化 `sections` 才是前端主渲染来源，`reportMarkdown`/`reportSections` 保持短以避免生成超时被终止。脚本不可用时空数组亦可（后端不读此字段入库、前端以 `reportMarkdown` 渲染）。
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
