# 安装说明

## 1. 解压

```bash
unzip kimi_claw_skill_bundle_2026-06-10.zip
cd kimi_claw_skill_bundle_2026-06-10
```

## 2. 安装 skills

默认安装到 `~/.kimi_openclaw/workspace/skills`：

```bash
bash install.sh
```

或指定 workspace：

```bash
KIMI_OPENCLAW_WORKSPACE=/path/to/workspace bash install.sh
```

## 3. 配置 AnySearch

推荐安装时直接写入 key：

```bash
ANYSEARCH_API_KEY="你的_anysearch_key" bash install.sh
```

安装脚本会：
- 写入 `skills/anysearch/.env`（权限 600）
- 自动生成 `skills/anysearch/runtime.conf`（Node CLI）

**不要把真实 key 打进 zip 或提交 Git。**

## 4. 重启 Kimi Desktop

安装 skill 后，**彻底退出并重开 Kimi Desktop**（macOS：`Cmd+Q`，不是关窗口），让 gateway 重新扫描 skills 目录。

## 5. 验证样例

```bash
python3 skills/cn-market-structured-output/scripts/validate_market_output.py \
  samples/kimi_claw_example_us_stock_options_full_2026-06-10.json

python3 skills/cn-market-structured-output/scripts/validate_market_output.py \
  samples/kimi_claw_example_cn_stock_analysis_full_2026-06-10.json

python3 skills/cn-market-structured-output/scripts/validate_market_output.py \
  samples/kimi_claw_example_cn_news_catalyst_full_2026-06-10.json
```

均应返回 `"valid": true`。

## 6. 使用方式

在 Kimi Desktop 新开对话，直接提问：

```text
分析NVDA
分析贵州茅台
英伟达发布 Vera Rubin AI 芯片，对 A 股算力产业链有什么影响？
```

默认输出完整 `kimi-market-v1` JSON。需要自然语言时明确说：

```text
用自然语言总结，不要 JSON
```
