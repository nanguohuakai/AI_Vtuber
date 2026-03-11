#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
OUTPUT_FILE="$ROOT_DIR/data/model_cookies.json"
CDP_ENDPOINT="${CDP_ENDPOINT:-http://127.0.0.1:9222}"
TARGET_URL="${TARGET_URL:-https://claude.ai}"

mkdir -p "$(dirname "$OUTPUT_FILE")"

if [ $# -gt 0 ]; then
  MODELS_CSV="$1"
else
  read -r -p "请输入要绑定 Cookie 的 model 名称（多个用逗号分隔）: " MODELS_CSV
fi

if [ -z "${MODELS_CSV// /}" ]; then
  echo "未提供 model，退出。"
  exit 1
fi

python - "$MODELS_CSV" "$OUTPUT_FILE" "$CDP_ENDPOINT" "$TARGET_URL" <<'PY'
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

models_csv, output_file, cdp_endpoint, target_url = sys.argv[1:5]
models = [m.strip() for m in models_csv.split(",") if m.strip()]
if not models:
    raise SystemExit("未解析到有效 model")

with sync_playwright() as pw:
    browser = pw.chromium.connect_over_cdp(cdp_endpoint)
    context = browser.contexts[0] if browser.contexts else browser.new_context()
    cookies = context.cookies([target_url])
    browser.close()

if not cookies:
    raise SystemExit("未获取到 Cookie。请确认已在调试浏览器中完成 Claude 登录。")

output = Path(output_file)
if output.exists():
    content = json.loads(output.read_text(encoding="utf-8"))
    if not isinstance(content, dict):
        content = {}
else:
    content = {}

for model in models:
    content[model] = {
        "site": target_url,
        "cookies": cookies,
    }

output.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"已写入 {output}，models: {', '.join(models)}")
PY
