# 美股 AnySearch 数据手册

美股 V4 分析**必须优先 AnySearch**，禁止默认 `kimi_search`。`kimi_finance` 负责 `TICKER.US` 实时价交叉验证。

## CLI 入口

读 `anysearch/runtime.conf`，当前为 Node：

```bash
node ~/.kimi_openclaw/workspace/skills/anysearch/scripts/anysearch_cli.js
```

## 推荐调用顺序（主路径）

### 1. 新闻与催化（首选，无需 cn_code）

```bash
node .../anysearch_cli.js search "NVDA" \
  --domain finance --sub_domain finance.news \
  --sdp type=stock,symbol=NVDA --max_results 8
```

### 2. 行情与基本面摘要

```bash
node .../anysearch_cli.js batch_search \
  --queries '[{"query":"NVDA","domain":"finance","sub_domain":"finance.quote","sub_domain_params":"type=stock,symbol=NVDA,cn_code="},{"query":"NVDA","domain":"finance","sub_domain":"finance.fundamental","sub_domain_params":"type=overview,symbol=NVDA,cn_code="}]'
```

> `cn_code=` 是 AnySearch 对美股的 API 兼容参数，仅作 fallback 传参，不是业务逻辑。

### 3. 财报日历

```bash
node .../anysearch_cli.js search "NVDA earnings" \
  --domain finance --sub_domain finance.calendar \
  --sdp type=earnings,symbol=NVDA --max_results 5
```

### 4. 正文提取（IR / SEC / 研报）

对 search 结果中的官方 URL 执行：

```bash
node .../anysearch_cli.js extract "https://investor.nvidia.com/..."
node .../anysearch_cli.js extract "https://www.sec.gov/Archives/edgar/data/..."
```

### 5. 实时价交叉验证

调用 `kimi_finance`：`NVDA.US`，`realtime_price`。

## 数据映射到 V4 章节

| V4 章节 | 主要数据源 |
|---------|-----------|
| 一~二 | extract（10-K/10-Q/IR）+ finance.news |
| 三~四 | extract 财报 + finance.fundamental |
| 五 | finance.fundamental + finance.quote + kimi_finance |
| 六~八 | 期权链（当前多数环境不可用） |
| 九 | news + 财报 + 宏观搜索 |
| 十~十二 | 综合前述数据 |

## 禁止行为

- 不使用 `finance.us_stock`（不存在）
- AnySearch 可用时不调用 `kimi_search`
- 不编造期权指标
