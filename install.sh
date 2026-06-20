#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="${KIMI_OPENCLAW_WORKSPACE:-$HOME/.kimi_openclaw/workspace}"
TARGET="$WORKSPACE/skills"
STAMP="$(date +%Y%m%d-%H%M%S)"

mkdir -p "$TARGET"

# 自动遍历 skills/ 下所有技能目录安装（含 cn-market-writeback 等新增技能，避免漏装）
shopt -s nullglob
for src in "$ROOT/skills/"*/; do
  src="${src%/}"
  skill="$(basename "$src")"
  [[ -f "$src/SKILL.md" ]] || continue
  dst="$TARGET/$skill"
  if [[ -e "$dst" ]]; then
    backup="$dst.backup-$STAMP"
    mv "$dst" "$backup"
    echo "Backed up existing $skill to $backup"
  fi
  cp -R "$src" "$dst"
  echo "Installed $skill -> $dst"
done
shopt -u nullglob

chmod +x "$TARGET/cn-market-writeback/scripts/persist.py" 2>/dev/null || true

chmod +x "$TARGET/cn-market-structured-output/scripts/validate_market_output.py" 2>/dev/null || true
chmod +x "$TARGET/cn-market-structured-output/scripts/markdown_report_to_json.py" 2>/dev/null || true
chmod +x "$TARGET/anysearch/scripts/"*.sh 2>/dev/null || true
chmod +x "$TARGET/anysearch/scripts/"*.py 2>/dev/null || true

# 生成 anysearch runtime.conf（Node CLI）
ANYSEARCH_DIR="$TARGET/anysearch"
NODE_BIN="$(command -v node || true)"
if [[ -z "$NODE_BIN" ]]; then
  echo "Warning: node not found in PATH. Please edit $ANYSEARCH_DIR/runtime.conf manually." >&2
elif [[ ! -f "$ANYSEARCH_DIR/runtime.conf" ]]; then
  cat > "$ANYSEARCH_DIR/runtime.conf" <<EOF
# AnySearch Runtime Configuration
Runtime: node
Command: $NODE_BIN $ANYSEARCH_DIR/scripts/anysearch_cli.js
EOF
  echo "Created $ANYSEARCH_DIR/runtime.conf (Node CLI)"
fi

# 配置 AnySearch API Key
if [[ -n "${ANYSEARCH_API_KEY:-}" ]]; then
  {
    echo "# AnySearch API Key Configuration"
    echo "ANYSEARCH_API_KEY=${ANYSEARCH_API_KEY}"
  } > "$ANYSEARCH_DIR/.env"
  chmod 600 "$ANYSEARCH_DIR/.env"
  echo "Wrote AnySearch key to $ANYSEARCH_DIR/.env from ANYSEARCH_API_KEY environment variable."
elif [[ ! -f "$ANYSEARCH_DIR/.env" && -f "$ANYSEARCH_DIR/.env.example" ]]; then
  cp "$ANYSEARCH_DIR/.env.example" "$ANYSEARCH_DIR/.env"
  chmod 600 "$ANYSEARCH_DIR/.env"
  echo "Created $ANYSEARCH_DIR/.env from .env.example. Fill in ANYSEARCH_API_KEY locally."
fi

echo "Done."
echo "Tip: restart Kimi Desktop (Cmd+Q then reopen) if skills were installed while the app was running."
