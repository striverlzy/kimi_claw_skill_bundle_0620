---
name: us-stock-options-analysis
description: Use this skill when the user asks to analyze a US stock, US-listed ticker, US equity portfolio, or asks for a combined fundamental plus options-market analysis including valuation, target prices, options sentiment, max pain, IV, put/call ratio, OI walls, gamma exposure, skew, or timing signals. Trigger on natural language like "分析NVDA" or "分析一下特斯拉". DEFAULT OUTPUT IS ONE kimi-market-v1 JSON OBJECT (mode=us_stock_options); 收到「分析NVDA」这类自然语言也必须先读 SKILL.md 与 cn-market-structured-output/references/protocol.md，再返回完整 JSON，其中 reportMarkdown 是**精简版 V4 报告**（保留十二章标题、每章只写关键要点；结构化字段 sections/options 才是前端主渲染源）。最终回答必须直接是 JSON 对象本身（以 `{` 开头、`}` 结尾），禁止任何开场白/过程叙述（如“正在生成完整报告”“先整理关键数据，然后输出 JSON”），禁止先声明再补 JSON。不要直接输出简短 Markdown 摘要。
---

# us-stock-options-analysis

美股中长期投资分析 skill，严格遵循 **V4 基本面+期权双维度框架**（见 `references/framework.md`）。

核心理念：基本面决定买什么、持有多久；期权决定何时买、何时卖；不做期权交易，只用期权数据优化时机。

## 🔴 执行协议（最高优先级，覆盖下方一切“自己写 JSON”的旧表述）

**你是数据检索员，不是报告撰写员。** 9 个 `sections` 与 `options` 一律由并发脚本 `parallel_sections.py` 生成，**严禁你自己手写**。严格按 4 步，做完第 4 步**立即结束**：

1. **检索**：`batch_search` 并发查美股基本面（财务/估值/分析师目标价/催化/风险）与期权面（IV/PCR/max pain/OI walls/gamma/skew），1–2 轮收尾。
2. **写 brief** 存到 `/tmp/kc_brief_<ticker>.json`：
   ```json
   {"stockName":"..","stockCode":"NVDA","market":"美股",
    "lockedNumbers":{"currentPrice":"$..","overallScore":<0-100>,"recommendation":"强烈买入/买入/持有/观望/回避"},
    "facts":{"公司概况":"..","财务":"..","估值与目标价":"..","竞争":"..","增长催化":"..","风险":".."},
    "optionsData":"IV/ivRank/PCR/maxPain/callWall/putWall/gammaExposure/skew 等已查到的期权数据",
    "dataSources":["AnySearch ..","Kimi Search .."],
    "reportMarkdown":"≥1000字精简版 V4 十二章报告，规范 #/##/### 标题"}
   ```
3. **跑脚本**：`python3 ~/.kimi_openclaw/workspace/skills/cn-market-structured-output/scripts/parallel_sections.py /tmp/kc_brief_<ticker>.json -o /tmp/kc_final_<ticker>.json --mode us_stock_options`
4. **交付并停**：**脚本只运行一次**；它打印到 stdout 的完整 JSON 就是最终答案，**立刻把它一字不改作为你的回复并结束本次任务**，前后不加任何文字。

**绝对禁止**：自己手写 sections/options；**第二次运行脚本**；脚本输出之外补充分析；运行脚本后继续检索/思考/校验。脚本一旦返回有效 JSON，你的唯一动作就是把它作为回复、结束。**仅当脚本非零退出/报错时**才回退手写。

## MUST（开工前必读，不可跳过）

1. 本 skill 默认产出 **一个合法 kimi-market-v1 JSON 对象**，`mode="us_stock_options"`，外面不裹 Markdown 代码围栏。
1.1. **最终回答的第一个字符必须是 `{`，最后一个字符必须是 `}`**。禁止输出“现在数据充足，我来生成报告”“先整理所有关键数据，然后输出 JSON”“下面是JSON”“分析如下”等任何开场白、过程叙述或结束语；禁止先声明再补 JSON。**必须在同一条回复里一次性直接输出完整 JSON**；即使期权链或财报细节不完整，也要直接产出当前可得的完整 JSON，缺失字段填 `待验证` / `options.dataAvailable=false`，绝不允许只回一句开场白后停下。
1.1.1. **Gateway 入口硬约束**：当用户消息第一行是 `us-stock-options-analysis`，第二行或后续内容才是真正问题时，第一行只作为 skill 触发标记，必须忽略这行后处理后续问题。即使输入很短（如 `分析 NVDA`），也必须直接返回完整 `mode="us_stock_options"` JSON。绝对禁止把 `Let me compile the complete analysis`、`I have gathered enough data`、`Now I have enough data` 等过程性英文/中文句子作为最终回复；如果已经准备输出这些句子，立刻改为输出 JSON。
1.2. **执行预算（防 terminated）——最高优先级**：**工具并行优先**——用 `batch_search` 把多条 query 一次性并发发出，AnySearch 与 `kimi_search` 可**同时并行**互补覆盖、交叉验证（冲突以 IR/SEC/官方/AnySearch 原文为准），`kimi_finance` 取 `TICKER.US` 实时价；**绝不逐条串行等待**。检索控制在约 1–2 轮并发批次内（等价于以往 ≤4 次调用的耗时上限），达到预算、检索变慢、期权链不可得时立即停止检索并输出 JSON。**`reportMarkdown` 必须精简**：保留十二章标题，但每章只写 1-3 句关键要点 + 关键数字，**不写长表格、不逐章长篇复述、不展开全部九维13项**（这些放结构化 `sections`/`options`，前端主要渲染结构化字段）。**输出越短越快越能在 KimiClaw 单任务预算内跑完，宁可精简也绝不能因报告过长被 terminated。**
2. 动手前先读：本文件全文 → `references/report_template.md` → `cn-market-structured-output/references/protocol.md`。
3. `reportMarkdown` **保留 V4 十二章标题顺序**（`结论摘要 / 0 / 一~十二`，不得用「1. 2. 3.」旧编号、不得省略期权三章标题），但每章**只写关键要点**，不强制长表格。
4. **输出加速（reportSections/reportSectionTree 不手写）**：先写好精简 `reportMarkdown`（保留十二章 `#/##` 标题顺序）+ 业务字段（`sections / options / recommendation / overallScore / dataPath / qualityControl`），`reportSections` 与 `reportSectionTree` 先填空数组 `[]`，由末步脚本 `markdown_report_to_json.py` 自动补全标题树（见 Required Workflow 末步）。**优先用脚本补全**；若运行时无法跑脚本，**空数组 `[]` 也可直接交付**——后端落库不读这两个字段、前端以 `reportMarkdown` + 结构化 `sections`/`options` 渲染；不要为补全而手写大段嵌套树或阻塞输出。
5. 数据走 AnySearch 优先；缺数据标 `待验证`，期权缺失标 `options.dataAvailable=false`，**禁止编造**。
6. 仅当用户明确说「用自然语言/口语/不要 JSON」时，才只输出 Markdown。
7. **缓存优先(省时关键)**：分析前先查缓存(见 `## Cache`)，命中未过期直接返回缓存的本地 JSON、跳过搜索与生成；未命中才分析、末步写缓存。用户明确说「最新/刷新/重新分析」时跳过查命中。

## Cache（缓存：JSON 落本地，先查后写）

`target` = 美股 ticker（如 `NVDA`）。**TTL 市场感知**：美股盘中（美东 9:30–16:00）只缓存 1 小时（期权/IV/股价时效强）；盘后沿用至次日开盘。缓存落 `~/.kimi_openclaw/workspace/cache/us_stock_options/`。

```bash
# 第 0 步（搜索前）
python3 ~/.kimi_openclaw/workspace/skills/cn-market-structured-output/scripts/market_cache.py lookup us_stock_options "<TICKER>"
#   {"hit":true,"doc":{...}} → 直接返回 doc 结束（已标 servedFromCache/cacheAge）；{"hit":false}(退出码1) → 继续分析
# 末步（标题树脚本生成最终 JSON 之后）
python3 ~/.kimi_openclaw/workspace/skills/cn-market-structured-output/scripts/market_cache.py store us_stock_options "<同一 TICKER>" <final.json>
```

## Default Return Contract

**默认必须返回一个合法 JSON 对象**，不得返回短 Markdown 摘要。

- 协议：`~/.kimi_openclaw/workspace/skills/cn-market-structured-output/references/protocol.md`
- `mode="us_stock_options"`
- `reportMarkdown` 是 **精简版 V4 报告**：保留 `report_template.md` 的十二章标题顺序，每章关键要点即可，不写长表格/长篇
- 从 `reportMarkdown` 标题生成 `reportSections` / `reportSectionTree`
- 只有用户**明确要求**自然语言、短答、或非 JSON 时，才可只输出 Markdown

用户只说「分析 NVDA」「分析NVDA」「看看 NVDA 值不值得买」→ 视为请求 **V4 JSON 研报（精简正文 + 完整结构化字段）**，不是 smoke test。

## Required Workflow

自然语言触发，不要求用户跑脚本。

1. **当前日期**：若入参/上下文已提供当前日期则**直接使用，不要为取日期单独检索或额外开一轮**；确认 ticker、投资期限、风险偏好、是否已有持仓。
2. **读框架与模板**：`references/framework.md`、`references/report_template.md`。
3. **读 JSON 协议**：`cn-market-structured-output/references/protocol.md`。
4. **数据并行获取**：
   - 读 `anysearch` skill 与其 `runtime.conf`（Node CLI）、`references/anysearch_us_stock.md`
   - 用 `batch_search` 一次并发多条 query；主路径：`finance.news` + `extract`（IR/SEC/财报/分析师页）+ `kimi_finance`（`TICKER.US` 实时价）；补充：`finance.quote` / `finance.fundamental` / `finance.calendar`
   - **AnySearch 与 `kimi_search` 可并行**互补覆盖、交叉验证（冲突以 IR/SEC/官方/AnySearch 原文为准，并在 `dataPath.notes` 注明）
   - 达到 MUST 1.2 的有界预算或检索变慢即停
5. **撰写精简 `reportMarkdown`**：按 `report_template.md` 的 H1/H2 标题顺序保留十二章，但**每章只写 1-3 句关键要点 + 关键数字**；九维评分明细放结构化 `sections`，正文不逐项复述全部 13 项；不写长表格。
6. **期权模块**：
   - 有结构化期权链：分析近月（5–10 天）+ 远月（25–35 天），计算 P/C、IV、Max Pain、OI Wall、Gamma、Skew
   - 无期权链：`options.dataAvailable=false`，第六~八章仍保留并写明不可判断，**禁止编造**
7. **合成 JSON**：填充 `sections`、`options`、`recommendation`、`overallScore`、`dataPath`、`qualityControl`。
8. **输出加速末步 + 自检**：把组好的 JSON 草稿（`reportSections=[]`、`reportSectionTree=[]`，其余业务字段齐全）写入临时文件，运行脚本回填标题树得到最终交付 JSON：
   ```bash
   python3 ~/.kimi_openclaw/workspace/skills/cn-market-structured-output/scripts/markdown_report_to_json.py <draft.json> -o <final.json>
   ```
   脚本**保留草稿里所有业务字段**（含 `sections`、`options`、评分等），仅补全 `reportSections`/`reportSectionTree`/`reportTitle`/`reportFormat`。交付 `<final.json>`，自检：JSON 可解析、缺数据字段标 `待验证`。若环境无法跑脚本，可直接交付带空数组的 JSON（后端落库与 `sections`/`options` 不依赖这两个字段），无需手写大段标题树。

## reportMarkdown 硬性结构

标题必须与 `references/report_template.md` 一致：

```text
# {公司}（{TICKER}）美股基本面与期权分析报告
## 结论摘要
## 0. 基本信息与数据口径
## 一、业务组成与结构
## 二、竞争关系对比分析
## 三、最近增速与财务表现
## 四、未来增速与财务预期
## 五、股价预估与估值分析
## 六、期权市场情绪分析
## 七、期权关键价位分析
## 八、期权-基本面交叉验证
## 九、核心风险因素
## 十、投资结论与建议
## 十一、组合配置建议
## 十二、九维评分
```

每章**只写 1-3 句关键要点**（含核心数字与「因为 A 所以 B」一句话逻辑），**不强制长表格、不逐章展开**；详细数据进结构化字段。不得用「1. 基本信息」「2. 业务结构」等旧编号替代「一、二、三…」。（保留标题是为了 reportSections 树结构，正文务必短，防 terminated。）

## Output Rules

- 默认：`mode="us_stock_options"` 单 JSON 对象，无 Markdown 代码围栏
- Return one valid JSON object only. Do not output any natural-language preface, progress narration, or “I will now generate JSON” message.
- `reportFormat="markdown-heading-tree-v1"`
- `recommendation` 与 `sections.investmentAdvice.conclusion` 给出直接操作建议
- `overallScore` = 九维加权总分（1–10）
- `options.optionsTimingView`：确认 / 冲突 / 中性 / 不可判断；配合 🟢🟡🔴 写入报告正文
- `dataPath.search` 优先填 `AnySearch`；`dataPath.marketData` 填 `Kimi Finance` 或具体源
- 所有数字标注来源；无源写 `待验证`
- 结尾给出：买入区、观察区、减仓区、失效条件、目标仓位、复核频率
- 不依赖 `scripts/us_market_data.py`（仅本地调试可选）

## V4 特殊规则（Guardrails）

- 投资研究支持，非保证收益承诺
- 默认不推荐投机期权交易；期权仅作时点与风险验证
- IV > 80% 或 Max Pain 偏离 > 30%：风险章必须提示
- P/E > 50：展示实际估值，不主动贴「泡沫」标签
- 地缘敏感标的：单列风险章
- 财报刚发布：单列财报影响章
- 股价较上次分析波动 ±15%：重新评估估值章

## 期权不可用时的标准写法

```json
{
  "options": {
    "dataAvailable": false,
    "optionsTimingView": "不可判断",
    "riskNotes": ["结构化期权链不可用，第六~八章仅保留框架"]
  }
}
```

`reportMarkdown` 第六~八章保留标题与说明，不填虚假 P/C、IV、Max Pain。
