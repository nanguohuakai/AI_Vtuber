#!/usr/bin/env bash
set -euo pipefail

PROFILE_DIR="$(pwd)/.chrome-profile"
URL="https://claude.ai/new"
PORT="${CHROME_DEBUG_PORT:-9222}"

mkdir -p "$PROFILE_DIR"

if command -v google-chrome >/dev/null 2>&1; then
  CHROME_BIN="google-chrome"
elif command -v chromium-browser >/dev/null 2>&1; then
  CHROME_BIN="chromium-browser"
elif command -v chromium >/dev/null 2>&1; then
  CHROME_BIN="chromium"
else
  echo "未找到 Chrome/Chromium，可手动使用 remote debugging 参数启动。"
  exit 1
fi

"$CHROME_BIN" \
  --remote-debugging-address=127.0.0.1 \
  --remote-debugging-port="$PORT" \
  --remote-allow-origins='*' \
  --user-data-dir="$PROFILE_DIR" \
  --no-first-run \
  --no-default-browser-check \
  "$URL"
