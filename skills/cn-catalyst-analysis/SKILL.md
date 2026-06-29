---
name: cn-catalyst-analysis
description: Use this skill when the user provides or asks about an industry news item, market rumor, "小作文", policy item, product launch, supplier-chain clue, overseas tech-giant catalyst (mode=news_event), OR meeting minutes, broker/research report, expert call, company memo, or industry note (mode=memo_research), and wants A-share transmission analysis, source verification, industry-chain mapping, beneficiary stock ranking, short-term theme value, market-style fit, or catalyst-driven trading ideas. DEFAULT OUTPUT IS ONE kimi-market-v1 JSON OBJECT (mode=news_event 或 memo_research)；收到自然语言催化剂提问也必须先读 SKILL.md 与 cn-market-structured-output/references/protocol.md，再返回完整 JSON，其中 reportMarkdown 是**精简催化剂要点**（结构化字段 decomposition/stocks/analysis 才是主渲染源且须完整）。最终回答必须直接是 JSON 对象本身（以 `{` 开头、`}` 结尾），禁止任何开场白/过程叙述。把板块拆子板块或板块映射个股，改用 cn-sector-mapping skill。
---

# cn-catalyst-analysis

Use this skill for catalyst-first China/A-share analysis: verify a news item, rumor, or research/memo source, map its industry-chain impact, identify A-share beneficiaries, and separate industrial value from short-term trading value. It owns `mode=news_event`（新闻/传闻/政策/新品/海外催化）与 `mode=memo_research`（纪要/研报/专家交流/公司或行业纪要）。Sector decomposition（`sector_tree`/`sector_stock_map`）在 cn-sector-mapping skill。

## 🔴 执行协议（最高优先级，覆盖下方一切“自己写 JSON”的旧表述）

**你是数据检索员，不是报告撰写员。** `analysis/decomposition/industryChainPanorama/stocks` 等结构化字段一律由并发脚本 `parallel_sections.py` 生成，**严禁你自己手写**。严格按 4 步，做完第 4 步**立即结束**：

1. **选 mode**：新闻/传闻/政策/新品/海外催化 → `news_event`；纪要/研报/专家交流/公司或行业纪要 → `memo_research`。
2. **检索**：`batch_search` 并发查事件真伪、最早发布时间与来源、产业链传导、A股受益标的，1–2 轮收尾。
3. **写 brief** 存到 `/tmp/kc_brief_catalyst.json`：
   ```json
   {"title":"事件/纪要标题","facts":{"事件":"..","真伪":"..","产业链传导":"..","市场风格":".."},
    "earliestPublishTime":"news_event必填:全网最早发布时间","earliestSourceUrl":"news_event必填:最早来源URL",
    "researchCategory":"memo_research必填:行业纪要/公司纪要/专家交流/券商研报/专题研报 五选一",
    "stocks":[{"name":"中际旭创","code":"300308","segment":"光模块","investmentLogic":"800G放量"}],
    "dataSources":["AnySearch ..","Kimi Search .."],
    "reportMarkdown":"≥1000字精简催化剂研报，规范 #/##/### 标题"}
   ```
4. **跑脚本并停**：`python3 ~/.kimi_openclaw/workspace/skills/cn-market-structured-output/scripts/parallel_sections.py /tmp/kc_brief_catalyst.json -o /tmp/kc_final_catalyst.json --mode <news_event|memo_research>`。**脚本只运行一次**；它打印到 stdout 的 JSON 就是最终答案，**立刻一字不改作为回复并结束**，前后不加任何文字。

**绝对禁止**：自己手写 stocks/decomposition/analysis；**第二次运行脚本**；脚本输出之外补充分析；运行脚本后继续检索/思考/校验。脚本返回有效 JSON 后唯一动作=把它作为回复、结束。**仅当脚本非零退出/报错时**才回退手写。

## MUST（开工前必读，不可跳过）

1. 默认产出 **一个合法 kimi-market-v1 JSON 对象**，按输入选 `mode=news_event` 或 `mode=memo_research`，外面不裹 Markdown 代码围栏。
1.1. **可见输出的第一个字符必须是 `{`，最后一个字符必须是 `}`**。所有检索、构思、规划、校验、组装 JSON 的过程必须内部静默完成，禁止流出任何自然语言过程句（如“正在构建…分析”“我已收集到足够信息”“下面是JSON”）。**必须在同一条回复里一次性直接输出完整 JSON**；即使研究未完全完成，也直接产出当前可得的完整 JSON，缺失字段填 `待验证`。
1.1.1. **Gateway 入口硬约束**：当用户消息第一行是 `cn-catalyst-analysis`，第二行起才是真正问题时，第一行只作为 skill 触发标记，忽略后处理后续问题。payload/prompt 含 `mode=news_event/memo_research` 时必须按该 mode 输出完整 JSON。任何过程性句子都禁止作为可见输出。
1.2. **执行预算（防被 KimiClaw 终止 / terminated）——最高优先级**：分析必须**又快又短地收尾**。
   - **工具并行优先**：用 `batch_search` 把来源发现/核实/产业链/受益股等多条 query 一次性并发；AnySearch 与 `kimi_search` **同时并行**互补覆盖、交叉验证（冲突以官方/交易所/权威媒体/AnySearch 原文为准），`kimi_finance` 核验行情。**绝不逐条串行**。检索控制在约 1–2 轮并发批次内；达到预算或检索变慢就**立即停止**。
   - `news_event`/`memo_research` **紧凑但不可过短**：`reportMarkdown` 控制在 **1000–1400 中文字（不得低于 1000，否则 validator 不过）**；`reportSections[].contentMarkdown` 每节 ≤ 约 120 中文字；`stocks` ≤ 8 只。覆盖消息核实、产业链传导、受益标的、风险四类要点写足要点即可达 1000 字。
   - 检索失败/信息不全时，用已有信息 + 缺失项标 `待验证` **直接产出完整 JSON**——宁可多字段 `待验证`，也绝不拖长到被 terminated。
2. **缓存优先(省时关键)**：分析前先查缓存(见 `## Cache`)，命中未过期直接返回缓存的本地 JSON、跳过搜索与生成；未命中才分析、末步写缓存。用户明确说「最新/刷新/重新分析」时跳过查命中。
3. 动手前先读：本文件全文 →（拿不准时）`references/framework.md` / `cn-market-structured-output/references/protocol.md`。
4. **输出加速（reportSections/reportSectionTree 不手写）**：先写精简 `reportMarkdown`（规范 `#/##/###` 标题）+ 业务字段（`analysis / sourceVerification / decomposition / stocks / keyValidationPoints / dataPath / qualityControl`），`reportSections`/`reportSectionTree` 填空数组 `[]`，由末步脚本 `markdown_report_to_json.py` 补全。脚本不可用时 `[]` 也可直接交付（后端不读这两字段）。
5. 如果 Java payload 提供 `taskNo`/`bizId`/`autoPersist`/`ingest`，必须在 JSON 填 `persistContract`。**一旦输出 persistContract 就必须完整**：`bizType`(=mode) + `targetTables` + `writeMode` 三者齐全，取 protocol §6.3(news_event)/§6.4(memo_research) 的 Persistence target 值（news_event 的 writeMode=`upsert_by_taskNo_newsId_stockCode`、targetTables=`["news_analysis","news_related_stock","news","stock_basic"]`；memo_research 的 writeMode=`upsert_by_taskNo_reportId_stockCode`、targetTables=`["research_analysis","research_related_stock","research_report","stock_basic"]`），**缺 writeMode 会校验不过**。无 payload 时可整体省略 persistContract。落库只通过 `cn-market-writeback` + `AiMarketMapper`；payload 含 `persistManagedBy="java-gateway"` 或 `writebackPolicy="return_json_only"` 时**禁止**调 `cn-market-writeback`，只返回完整 JSON。
6. 数据走 AnySearch + kimi_search 并行；传闻必须核实并在 `analysis.riskWarning` 标注证伪风险；缺数据标 `待验证`，**禁止编造**链接、时间、订单、市占率、股价、市场风格信号。
7. **需求1（news_event 强制，必须真做、不许直接填待验证）**：取该新闻**全网最早对外公布时间** + 最早来源 URL，写入 `analysis.earliestPublishTime`（ISO-8601）/ `analysis.earliestSourceUrl`。**硬流程**：
   - ① 搜索该事件，挑出 **2–4 个最可能首发的候选源**（官方站 / 权威媒体原文，排除转载、聚合、知乎/微博等二手）。
   - ② 调脚本逐源 `extract` 抓原文并按「元数据 → 正文 dateline → URL 日期」三级解析、跨源取最早：
     ```bash
     python3 ~/.kimi_openclaw/workspace/skills/cn-market-structured-output/scripts/extract_publish_date.py "<url1>" "<url2>" "<url3>"
     ```
     直接用它返回的 `earliestPublishTime` / `earliestSourceUrl`。
   - ③ 仅当脚本对所有候选都返回 `null`（确实一个日期都解析不到）时，才填 `待验证`。**禁止跳过 ①②、禁止凭空填待验证。**
8. **需求2（memo_research 强制）**：必须由 kimiclaw 对纪要/研报统一归类，写入 `analysis.researchCategory`，五选一：`行业纪要 | 公司纪要 | 专家交流 | 券商研报 | 专题研报`。
9. 仅当用户明确说「用自然语言/口语/不要 JSON」时，才只输出 Markdown。

## Cache（缓存：JSON 落本地，先查后写）

`mode` 用本次实际产出的 `news_event` 或 `memo_research`。`target` = 该催化剂/纪要的**稳定标识** = `主体+核心事件`（如 `英伟达-Vera-Rubin`、`某券商-AI算力深度`）。同一事件用同一短语，避免重复全量分析。TTL：两者 24 小时。缓存落 `~/.kimi_openclaw/workspace/cache/<mode>/`。

**第 0 步——查缓存**（在任何搜索之前，`<mode>` 替换为实际模式）：

```bash
python3 ~/.kimi_openclaw/workspace/skills/cn-market-structured-output/scripts/market_cache.py \
  lookup <mode> "<主体+核心事件>"
```
- `{"hit": true, "doc": {...}}` → 直接把 `doc` 作为最终 JSON 返回并结束（已自动标 `qualityControl.servedFromCache=true`）。
- `{"hit": false}`（退出码 1）→ 正常走完整分析。

**末步——写缓存**（标题树脚本生成最终 JSON 之后）：

```bash
python3 ~/.kimi_openclaw/workspace/skills/cn-market-structured-output/scripts/market_cache.py \
  store <mode> "<同一 target>" <final.json>
```

## Default Return Contract

Return one valid JSON object by default. Use `~/.kimi_openclaw/workspace/skills/cn-market-structured-output/references/protocol.md`.

Mode selection:

- `news_event`: news, rumor, policy, product launch, or overseas catalyst.
- `memo_research`: meeting minutes, expert calls, broker reports, company notes, or industry notes.

Both are catalyst/message modes: keep the full message-verification, authenticity, market-style, and short-term trading-value framework. Keep `reportMarkdown` **concise**; the structured fields (`analysis`/`decomposition`/`stocks`/...) are the primary render source and must be complete. Cap `reportMarkdown` ~1200 Chinese chars, each `reportSections[].contentMarkdown` ~120, `stocks` ≤ 8.

Only use Markdown/natural language if the user explicitly asks for a prose report, quick chat answer, or non-JSON explanation.

## Required Workflow

1. Current date: use it if already provided; only look it up if truly absent.
2. **第 0 步先查缓存**（见 `## Cache`）；命中即返回，未命中再继续。
3. Identify the input type and mode (`news_event` vs `memo_research`).
4. **数据并行获取**：用 `batch_search` 一次并发多条 query 做来源发现/垂直搜索，对关键来源用 `extract` 全文抓取；AnySearch 与 `kimi_search` 并行互补、交叉验证；`kimi_finance` 核验行情。达到 MUST 1.2 的有界预算或检索变慢即停。
5. Verify the message with the strongest sources: official company/regulator/exchange first, then major financial/industry media, then market-price cross-checks. Do not treat unverified rumors as facts.
6. **news_event 必须确定全网最早发布时间 + 最早来源 URL**（需求1，填 `analysis.earliestPublishTime` / `analysis.earliestSourceUrl`）；**memo_research 必须归类**（需求2，填 `analysis.researchCategory` 五选一）。memo_research 同时补 institution / researcherOrSpeaker / researchType 等来源字段。
7. If the catalyst involves overseas giants (NVIDIA/Microsoft/Tesla/Apple/Google/AMD/Broadcom/TSMC/ASML), analyze the A-share transmission path: direct supplier, indirect supplier, bottleneck, domestic substitution, or pure sentiment mapping.
8. Build the industry-chain map before ranking stocks (upstream/midstream/downstream, bottlenecks, value transfer, domestic substitution, global competition).
9. Separate three rankings when relevant: industry-chain value, fundamental benefit, short-term trading value. If market-style data is unavailable, mark it and give a conditional plan instead of fabricating.
10. Choose `mode="news_event"` or `mode="memo_research"`, write `reportMarkdown` + 业务字段（`reportSections`/`reportSectionTree` 留 `[]`）。
11. After identifying concrete tickers needing deeper analysis, recommend `cn-stock-analysis`（A/HK）或 `us-stock-options-analysis`（US）。
12. Build `persistContract` from the payload when present（bizType = 实际 mode；ingest.url/token 只用 payload，不硬编码）。若 `persistManagedBy="java-gateway"` / `writebackPolicy="return_json_only"`，只返回 JSON、不调 `cn-market-writeback`；否则仅当 `autoPersist=true` 才调 writeback 发送同一份完整信封。**永远一次性直接输出完整 JSON，绝不向用户提问或等待二次交互。**
13. **输出加速末步（生成标题树）**：把草稿 JSON（`reportSections=[]` 等）写临时文件，运行脚本回填得最终交付 JSON：
    ```bash
    python3 ~/.kimi_openclaw/workspace/skills/cn-market-structured-output/scripts/markdown_report_to_json.py <draft.json> -o <final.json>
    ```
    脚本保留所有业务字段（含 `persistContract`/`decomposition`/`stocks`），仅补 `reportSections`/`reportSectionTree`/`reportTitle`/`reportFormat`。
14. **末步写缓存**（见 `## Cache` 的 store）。

## Output Rules

- Default to JSON with the common envelope and mode-specific fields from `protocol.md`. Include a **concise** `reportMarkdown`; structured fields are the primary render source and must be complete.
- `reportSections`/`reportSectionTree` 默认 `[]`，由末步脚本补全（脚本不可用时空数组亦可交付）。
- Put credibility in `sourceVerification.verificationStatus`, `analysis.authenticityLevel`, `analysis.riskWarning`. Rumor / no authoritative source → required warning at the start of `analysis.riskWarning`.
- **news_event**：`analysis.earliestPublishTime` + `analysis.earliestSourceUrl` 必填（需求1）。
- **memo_research**：`analysis.researchCategory`（行业纪要/公司纪要/专家交流/券商研报/专题研报）必填（需求2）。
- Add a brief `dataPath` note. Cite source labels for important facts. For each stock, state its chain position and why it benefits. Include invalidation conditions.
- For persisted payloads, include `persistContract.mapper="AiMarketMapper"` and the target tables from `protocol.md`.
- Return one valid JSON object only. Do not wrap in Markdown fences. Mark unsupported claims as `待验证`. Never continue generating prose after `reportMarkdown`; close the JSON object.

## Guardrails

- Investment research support, not guaranteed advice.
- Do not fabricate links, publication times, orders, customer relationships, market share, stock prices, or market-style signals.
- Do not convert a rumor into a buy recommendation without an explicit uncertainty warning.
- Do not mechanically prefer small caps; adapt to market style and catalyst type.
- Do not ignore industry leaders when the catalyst changes technology routes, standards, cost structure, or supply-chain access.
- Do not equate overseas-company good news with direct A-share benefit; prove the transmission path or mark it as sentiment-only.
