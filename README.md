# KimiClaw 股票分析 Skill Bundle

打包日期：**2026-06-10**；最近更新：**2026-06-20**（新增 `cn-market-writeback` 落库回写 skill；协议/框架字段对齐 0619 实体）。

本 bundle 包含 KimiClaw 股票/新闻/美股分析链路所需的 6 个 skill、安装脚本，以及 **三份真实跑通的 examples**（NVDA / 贵州茅台 / Vera Rubin 催化剂）。

## 包含内容

```text
skills/
  anysearch/
  cn-stock-analysis/
  cn-news-catalyst-analysis/
  us-stock-options-analysis/
  cn-market-structured-output/
  cn-market-writeback/        # 2026-06-20 新增：分析后调后端 ingest 接口落库
samples/
  kimi_claw_example_us_stock_options_full_2026-06-10.json   # 分析NVDA
  kimi_claw_example_us_stock_options_full_2026-06-10.md
  kimi_claw_example_cn_stock_analysis_full_2026-06-10.json  # 分析贵州茅台
  kimi_claw_example_cn_stock_analysis_full_2026-06-10.md
  kimi_claw_example_cn_news_catalyst_full_2026-06-10.json    # Rubin催化剂
  kimi_claw_example_cn_news_catalyst_full_2026-06-10.md
docs/
  INSTALL.md
  EXAMPLES.md
install.sh
manifest.json
```

## 默认输出

三个核心 skill 默认返回 `schemaVersion="kimi-market-v1"` JSON：

| Skill | mode | 测试 prompt | 实测结果 |
|-------|------|-------------|----------|
| us-stock-options-analysis | `us_stock_options` | 分析NVDA | 8.7/10 买入，完整十二章 |
| cn-stock-analysis | `single_stock` | 分析贵州茅台 | 8.2/10 买入，完整十步 |
| cn-news-catalyst-analysis | `news_event` | Vera Rubin 催化剂 | 5 只标的，消息已验证 |

## 搜索路由

- **主路径**：AnySearch（`finance.news` / `quote` / `fundamental` / `extract`）
- **补充**：kimi_search（深度背景、分析师观点）
- **交叉验证**：kimi_finance（开盘时段实时价）

## 快速安装

```bash
unzip kimi_claw_skill_bundle_2026-06-10.zip
cd kimi_claw_skill_bundle_2026-06-10
ANYSEARCH_API_KEY="你的_key" bash install.sh
```

安装后**彻底退出并重开 Kimi Desktop**（Cmd+Q），让 gateway 重新加载 skills。

## 验证样例

```bash
python3 skills/cn-market-structured-output/scripts/validate_market_output.py \
  samples/kimi_claw_example_us_stock_options_full_2026-06-10.json
```

三个样例均应返回 `"valid": true`。

详见 [docs/INSTALL.md](docs/INSTALL.md) 和 [docs/EXAMPLES.md](docs/EXAMPLES.md)。
