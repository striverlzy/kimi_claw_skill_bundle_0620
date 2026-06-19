# 完整样例（2026-06-10 实测）

三份样例均来自 Kimi Desktop gateway（端口 18679）真实跑通结果，已通过 `validate_market_output.py` 校验。

## 1. us-stock-options-analysis

**输入**：`分析NVDA`

**JSON**：`samples/kimi_claw_example_us_stock_options_full_2026-06-10.json`

**Markdown**：`samples/kimi_claw_example_us_stock_options_full_2026-06-10.md`

| 字段 | 值 |
|------|-----|
| mode | `us_stock_options` |
| status | `complete` |
| overallScore | 8.7 |
| recommendation | 买入 |
| reportSections | 15 节（完整十二章 + H1） |
| 搜索 | AnySearch finance.news/quote/fundamental |
| 期权 | `options.dataAvailable=false` |

## 2. cn-stock-analysis

**输入**：`分析贵州茅台`

**JSON**：`samples/kimi_claw_example_cn_stock_analysis_full_2026-06-10.json`

**Markdown**：`samples/kimi_claw_example_cn_stock_analysis_full_2026-06-10.md`

| 字段 | 值 |
|------|-----|
| mode | `single_stock` |
| status | `complete` |
| stockCode | 600519 |
| overallScore | 8.2 |
| recommendation | 买入 |
| reportSections | 11 节 |
| 搜索 | AnySearch 公告 + kimi_search 分析师目标价 |

## 3. cn-news-catalyst-analysis

**输入**：`英伟达发布新一代 Vera Rubin AI 芯片，分析对 A 股算力产业链的影响与受益标的`

**JSON**：`samples/kimi_claw_example_cn_news_catalyst_full_2026-06-10.json`

**Markdown**：`samples/kimi_claw_example_cn_news_catalyst_full_2026-06-10.md`

| 字段 | 值 |
|------|-----|
| mode | `news_event` |
| status | `complete` |
| authenticityLevel | 高 |
| verificationStatus | verified |
| stocks | 5 只（中际旭创/天孚通信/新易盛/工业富联/光迅科技） |
| reportSections | 18 节 |

## Markdown → JSON 转换

若只有 Markdown 报告，可用脚本补全 `reportSections`：

```bash
python3 skills/cn-market-structured-output/scripts/markdown_report_to_json.py \
  samples/kimi_claw_example_cn_stock_analysis_full_2026-06-10.md \
  --base-json samples/kimi_claw_example_cn_stock_analysis_full_2026-06-10.json \
  --output samples/kimi_claw_example_cn_stock_analysis_full_2026-06-10.json
```
