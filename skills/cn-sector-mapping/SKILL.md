---
name: cn-sector-mapping
description: Use this skill when the user wants to break a China/A-share sector or theme into sub-sectors (mode=sector_tree), or map a sector/sub-sector into an industry-chain decomposition and A-share stock candidates (mode=sector_stock_map). This is the lightweight pure industry-chain tooling layer (sector → sub-sectors → stocks). DEFAULT OUTPUT IS ONE kimi-market-v1 JSON OBJECT (mode=sector_tree 或 sector_stock_map)；先读 SKILL.md 与 cn-market-structured-output/references/protocol.md 再返回完整 JSON。最终回答必须直接是 JSON 对象本身（以 `{` 开头、`}` 结尾），禁止任何开场白/过程叙述。需要核实新闻/研报/纪要催化剂、出催化剂研报时改用 cn-catalyst-analysis skill。
---

# cn-sector-mapping

Pure industry-chain decomposition tooling — a two-step pipeline:

1. `sector_tree`: expand a sector/theme into candidate sub-sectors.
2. `sector_stock_map`: take a sector/sub-sector and produce an industry-chain decomposition + ranked A-share stock candidates.

These are **pure industry-chain modes**: do NOT run message-truth verification, information-increment reset, market-style judgement, short-term trading-value ranking, or style-switch plans. For那些 use `cn-catalyst-analysis`.

## 🔴 执行协议（最高优先级，覆盖下方一切“自己写 JSON”的旧表述）

**你是数据检索员，不是报告撰写员。** `candidates/decomposition/stocks` 等结构化字段一律由并发脚本 `parallel_sections.py` 生成，**严禁你自己手写**。严格按 4 步，做完第 4 步**立即结束**：

1. **选 mode**：把板块拆成子板块 → `sector_tree`；给定板块/子板块映射个股 → `sector_stock_map`。
2. **检索**：`batch_search` 并发查产业链结构与 A股标的，1–2 轮收尾。
3. **写 brief** 存到 `/tmp/kc_brief_sector.json`：
   ```json
   {"sectorName":"AI算力",
    "existingSubSectors":["sector_tree用:已有子板块列表"],
    "subSectorName":"sector_stock_map用:目标子板块,如 光模块",
    "stocks":[{"name":"中际旭创","code":"300308","segment":"光模块","investmentLogic":"800G放量"}],
    "facts":{"产业链":"..","上中下游":"..","国产替代":".."},
    "dataSources":["AnySearch ..","Kimi Search .."],
    "reportMarkdown":"sector_stock_map需≥1000字精简拆解(sector_tree可省)，规范 #/##/### 标题"}
   ```
4. **跑脚本并停**：`python3 ~/.kimi_openclaw/workspace/skills/cn-market-structured-output/scripts/parallel_sections.py /tmp/kc_brief_sector.json -o /tmp/kc_final_sector.json --mode <sector_tree|sector_stock_map>`。**脚本只运行一次**；它打印到 stdout 的 JSON 就是最终答案，**立刻一字不改作为回复并结束**，前后不加任何文字。

**绝对禁止**：自己手写 candidates/decomposition/stocks；**第二次运行脚本**；脚本输出之外补充分析；运行脚本后继续检索/思考。脚本返回有效 JSON 后唯一动作=把它作为回复、结束。**仅当脚本非零退出/报错时**才回退手写。

## MUST（开工前必读，不可跳过）

1. 默认产出 **一个合法 kimi-market-v1 JSON 对象**，按任务选 `mode=sector_tree` 或 `mode=sector_stock_map`，外面不裹 Markdown 代码围栏。
1.1. **可见输出第一个字符必须是 `{`，最后一个字符必须是 `}`**。板块拆解不是聊天报告，禁止先解释“将构建产业链 JSON”。完成必要检索后，第一段可见内容必须直接是 `{"schemaVersion":"kimi-market-v1","mode":"sector_stock_map"...}` 或 `{...,"mode":"sector_tree"...}`。资料不足仍输出 `status:"partial"` 的完整 JSON，并在 `qualityControl`/`dataPath.notes` 标注缺口，不得用自然语言说明资料不足。
1.2. **执行预算（防 terminated）**：`batch_search` 并发取数，AnySearch 与 `kimi_search` 并行互补；约 1–2 轮并发批次内收尾，检索变慢即停；缺数据标 `待验证` 直接产出完整 JSON。
2. **缓存优先(省时关键)**：分析前先查缓存(见 `## Cache`)，命中未过期直接返回缓存的本地 JSON、跳过搜索与生成；未命中才分析、末步写缓存。用户明确说「最新/刷新」时跳过查命中。
3. **`sector_tree` 不需要 `reportMarkdown`**（它是“生成”不是“分析”）；`sector_stock_map` 需保留精简 `reportMarkdown`，`reportSections`/`reportSectionTree` 填 `[]` 由末步脚本补全（脚本不可用时空数组亦可，后端不读此字段）。
4. 如果 Java payload 提供 `taskNo`/`bizId`/`autoPersist`/`ingest`，必须填 `persistContract`（`sector_tree`→targetTables `["hot_sub_sector"]`、writeMode `candidate_upsert_pending_review`；`sector_stock_map`→targetTables `["hot_sub_sector","sector_related_stock","stock_basic"]`、writeMode `upsert_by_bizId_and_stockCode`，详见 protocol §6.1/§6.2）；落库只通过 `cn-market-writeback` + `AiMarketMapper`。若 payload 含 `persistManagedBy="java-gateway"` 或 `writebackPolicy="return_json_only"`，禁止调 `cn-market-writeback`，只返回完整 JSON。
5. **数据并行**：AnySearch 与 `kimi_search` 同时并发（`batch_search`），缺数据标 `待验证`，**禁止编造**股票代码、市占率、订单、价格。
6. 仅当用户明确说「用自然语言/口语/不要 JSON」时，才只输出 Markdown。

## Cache（缓存：JSON 落本地，先查后写）

`mode` 用实际产出的 `sector_tree` 或 `sector_stock_map`。`target` = 板块名（`sector_stock_map` 用 `板块-子板块`，如 `AI算力-光模块`）。TTL：两者 24 小时。缓存落 `~/.kimi_openclaw/workspace/cache/<mode>/`。

```bash
# 第 0 步（搜索前）
python3 ~/.kimi_openclaw/workspace/skills/cn-market-structured-output/scripts/market_cache.py lookup <mode> "<板块名 或 板块-子板块>"
#   {"hit":true,"doc":{...}} → 直接返回 doc 结束；{"hit":false}(退出码1) → 继续分析
# 末步（生成最终 JSON 后）
python3 ~/.kimi_openclaw/workspace/skills/cn-market-structured-output/scripts/market_cache.py store <mode> "<同一 target>" <final.json>
```

## Required Workflow

1. **第 0 步先查缓存**（见 `## Cache`）；命中即返回。
2. Decide the mode (`sector_tree` vs `sector_stock_map`) from input scope.
3. **数据并行**：把子板块发现、龙头公司、产业链环节相关 query 一次性并发（`batch_search`），AnySearch + `kimi_search` 互补；需要 AnySearch 参数细节再读 `anysearch` skill。
4. For `sector_tree`: ≥6 candidate sub-sectors（input 太窄除外），覆盖上中下游，`categoryType` 取 protocol §6.1 枚举之一，`level` 用 2（产业链大环节）或 3（具体细分），最多 1–2 个 `isCore=true`，不重复已有子板块。
5. For `sector_stock_map`: 先建 `decomposition`（protocol §5 前端形态：panorama / upstream / midstream.firstTier·secondTier·thirdTier / downstream / investmentRanking / validationPoints），再排 `stocks`（顶层、≥10 优先、用完整 stock schema、不编造代码、不足在 `qualityControl.manualReviewReasons` 说明）；写精简 `reportMarkdown`、`reportSections`/`reportSectionTree` 留 `[]`。
6. Recommend `cn-stock-analysis`（A/HK）/ `us-stock-options-analysis`（US）做个股深度；催化剂核实改用 `cn-catalyst-analysis`。
7. Build `persistContract` from payload when present（bizType=实际 mode）。`persistManagedBy="java-gateway"` / `writebackPolicy="return_json_only"` 时只返回 JSON、不调 writeback；否则仅 `autoPersist=true` 才调 `cn-market-writeback`。**一次性直接输出完整 JSON，不提问、不等待。**
8. **输出加速末步（仅 `sector_stock_map`）**：草稿 JSON 写临时文件后跑脚本回填标题树：
   ```bash
   python3 ~/.kimi_openclaw/workspace/skills/cn-market-structured-output/scripts/markdown_report_to_json.py <draft.json> -o <final.json>
   ```
   `sector_tree` 无 reportMarkdown，跳过此步。
9. **末步写缓存**（见 `## Cache` 的 store）。

## Output Rules

- Default to JSON with the common envelope and mode-specific fields from `protocol.md`.
- `sector_tree`: `sectorName`, `existingSubSectors`, `candidates`（≥6，含 `categoryType`/`level`/`isCore`/`reason`）。
- `sector_stock_map`: `sectorName`, `subSectorName`, `decomposition`（前端形态）, top-level `stocks`, 以及 `reportSections`/`reportSectionTree`（留 `[]` 由脚本补）。
- For每个 stock，主字段（`name`/`code`/`marketValue`）+ 兼容别名（`stockName`/`stockCode`/`marketCap`/`changePercent`/`chainStage`/`corePosition`）须一致（`AiMarketMapper` 要求）。
- Important facts 带来源或标 `待验证`；`gain` 无可靠实时源时填 `待更新`。
- For persisted payloads, include `persistContract.mapper="AiMarketMapper"` 与 protocol 定义的 target tables。
- Return one valid JSON object only. Do not wrap in Markdown fences.

## Guardrails

- Investment research support, not guaranteed advice.
- 不编造股票代码、市值、价格、订单、市占率。
- `sector_tree` 不重复已有子板块名；不要为凑数塞弱概念股，覆盖不足在 `qualityControl` 标注。
- 纯产业链模式：不做消息真伪、市场风格、短线交易价值排序。
