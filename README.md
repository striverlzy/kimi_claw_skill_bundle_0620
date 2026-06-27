# KimiClaw 股票分析 Skill Bundle

打包日期：**2026-06-10**；最近更新：**2026-06-24**（基于 0624 writeback 版合并：催化剂 skill 拆分为 `cn-catalyst-analysis` + `cn-sector-mapping`；新增 `market_cache.py` 差异化 TTL 缓存；新闻类加「全网最早发布时间+来源URL」、纪要类加「统一归类标签」两项需求）。

本 bundle 包含 KimiClaw 股票/新闻/美股分析链路所需的 7 个 skill、安装脚本，以及 **三份真实跑通的 examples**（NVDA / 贵州茅台 / Vera Rubin 催化剂）。

## 包含内容

```text
skills/
  anysearch/
  cn-stock-analysis/
  cn-catalyst-analysis/       # news_event + memo_research（含两项新需求）
  cn-sector-mapping/          # sector_tree + sector_stock_map
  us-stock-options-analysis/
  cn-market-structured-output/   # 协议 + validator + markdown_report_to_json + market_cache
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

核心分析 skill 默认返回 `schemaVersion="kimi-market-v1"` JSON：

| Skill | mode | 测试 prompt | 实测结果 |
|-------|------|-------------|----------|
| us-stock-options-analysis | `us_stock_options` | 分析NVDA | 8.7/10 买入，完整十二章 |
| cn-stock-analysis | `single_stock` | 分析贵州茅台 | 8.2/10 买入，完整十步 |
| cn-catalyst-analysis | `news_event` / `memo_research` | Vera Rubin 催化剂 | 5 只标的，消息已验证 |
| cn-sector-mapping | `sector_tree` / `sector_stock_map` | AI算力板块拆子板块+映射个股 | 产业链拆解 + 个股候选 |

**新需求**：`news_event` 必带「全网最早发布时间 `earliestPublishTime` + 最早来源 URL `earliestSourceUrl`」；`memo_research` 必带统一归类 `researchCategory`（行业纪要/公司纪要/专家交流/券商研报/专题研报）。
**缓存**：同一标的同 mode 命中差异化 TTL（基本面类 24h、美股期权盘中 1h）则直接读本地 JSON、跳过搜索生成。

## 搜索路由（双引擎并行，非主备串行）

- **并发双引擎**：AnySearch（`finance.news`/`quote`/`fundamental`/`extract`）与 kimi_search（广度覆盖、中文资讯、信源发现）**每次同时并发**（`batch_search` 批量），互补 + 交叉验证。
- **交叉验证**：kimi_finance（开盘时段实时价）；A 股 `finance.quote` 仅取实时报价时可回退 Kimi Finance。

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
