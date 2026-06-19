# 美股数据源说明

V4 分析由 **自然语言 + AnySearch + kimi_finance** 驱动。

## 默认数据路径

1. **AnySearch** `finance.news` → 新闻、催化
2. **AnySearch** `extract` → IR、SEC、财报、分析师页正文
3. **AnySearch** `finance.quote` / `finance.fundamental` / `finance.calendar` → 行情与摘要
4. **kimi_finance** → `TICKER.US` 实时价交叉验证
5. **期权链** → 有结构化源才填第六~八章；否则 `options.dataAvailable=false`

## 搜索优先级

AnySearch 优先；`kimi_search` 仅作 AnySearch 连续失败后的 fallback，并在 `dataPath.notes` 说明。

## 期权数据

当前环境通常无免费期权链。无链时第六~八章保留框架、标明不可判断，禁止编造 P/C、IV、Max Pain 等。

`scripts/us_market_data.py` 仅为本地调试辅助，不是 agent 主链路。
