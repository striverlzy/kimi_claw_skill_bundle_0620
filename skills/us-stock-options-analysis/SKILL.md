---
name: us-stock-options-analysis
description: Use this skill when the user asks to analyze a US stock, US-listed ticker, US equity portfolio, or asks for a combined fundamental plus options-market analysis including valuation, target prices, options sentiment, max pain, IV, put/call ratio, OI walls, gamma exposure, skew, or timing signals. Trigger on natural language like "分析NVDA" or "分析一下特斯拉". DEFAULT OUTPUT IS ONE kimi-market-v1 JSON OBJECT (mode=us_stock_options); 收到「分析NVDA」这类自然语言也必须先读 SKILL.md 与 cn-market-structured-output/references/protocol.md，再返回完整 JSON，其中 reportMarkdown 是完整 V4 十二章报告。不要直接输出简短 Markdown 摘要。
---

# us-stock-options-analysis

美股中长期投资分析 skill，严格遵循 **V4 基本面+期权双维度框架**（见 `references/framework.md`）。

核心理念：基本面决定买什么、持有多久；期权决定何时买、何时卖；不做期权交易，只用期权数据优化时机。

## MUST（开工前必读，不可跳过）

1. 本 skill 默认产出 **一个合法 kimi-market-v1 JSON 对象**，`mode="us_stock_options"`，外面不裹 Markdown 代码围栏。
2. 动手前先读：本文件全文 → `references/report_template.md` → `cn-market-structured-output/references/protocol.md`。
3. `reportMarkdown` 必须是 **完整 V4 十二章**（`结论摘要 / 0 / 一~十二`），不得用「1. 2. 3.」旧编号，不得省略期权三章。
4. 从 `reportMarkdown` 标题生成 `reportSections` + `reportSectionTree`，再补 `sections / options / recommendation / overallScore / dataPath / qualityControl`。
5. 数据走 AnySearch 优先；缺数据标 `待验证`，期权缺失标 `options.dataAvailable=false`，**禁止编造**。
6. 仅当用户明确说「用自然语言/口语/不要 JSON」时，才只输出 Markdown。

## Default Return Contract

**默认必须返回一个合法 JSON 对象**，不得返回短 Markdown 摘要。

- 协议：`/Users/doublej_w/.kimi_openclaw/workspace/skills/cn-market-structured-output/references/protocol.md`
- `mode="us_stock_options"`
- `reportMarkdown` 必须是 **完整 V4 十二步报告**（见 `references/report_template.md`）
- 从 `reportMarkdown` 标题生成 `reportSections` / `reportSectionTree`
- 只有用户**明确要求**自然语言、短答、或非 JSON 时，才可只输出 Markdown

用户只说「分析 NVDA」「分析NVDA」「看看 NVDA 值不值得买」→ 视为请求 **完整 V4 JSON 研报**，不是 smoke test。

## Required Workflow

自然语言触发，不要求用户跑脚本。

1. **取当前日期**，确认 ticker、投资期限、风险偏好、是否已有持仓。
2. **读框架与模板**：`references/framework.md`、`references/report_template.md`。
3. **读 JSON 协议**：`cn-market-structured-output/references/protocol.md`。
4. **数据获取（AnySearch 优先，禁止默认 kimi_search）**：
   - 读 `anysearch` skill 与其 `runtime.conf`（Node CLI）
   - 读 `references/anysearch_us_stock.md`
   - 主路径：`finance.news` + `extract`（IR/SEC/财报/分析师页）+ `kimi_finance`（`TICKER.US` 实时价）
   - 补充：`finance.quote` / `finance.fundamental` / `finance.calendar`
   - `kimi_search` 仅当 AnySearch 连续失败且在 `dataPath.notes` 说明后才可 fallback
5. **撰写完整 `reportMarkdown`**：按 `report_template.md` 的 H1/H2 顺序，覆盖十二步 + 九维评分检查清单全部 13 项。
6. **期权模块**：
   - 有结构化期权链：分析近月（5–10 天）+ 远月（25–35 天），计算 P/C、IV、Max Pain、OI Wall、Gamma、Skew
   - 无期权链：`options.dataAvailable=false`，第六~八章仍保留并写明不可判断，**禁止编造**
7. **合成 JSON**：填充 `sections`、`options`、`recommendation`、`overallScore`、`dataPath`、`qualityControl`。
8. **自检**：JSON 可解析；标题树与 Markdown 一致；缺数据字段标 `待验证`。

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

每章须含 v4 要求的表格与「因为 A，所以 B」逻辑链。不得用「1. 基本信息」「2. 业务结构」等旧编号替代「一、二、三…」。

## Output Rules

- 默认：`mode="us_stock_options"` 单 JSON 对象，无 Markdown 代码围栏
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
