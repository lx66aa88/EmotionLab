#!/bin/sh
set -eu
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ] || [ ! -f frontend/dist/index.html ]; then
  echo "请先按 docs/GETTING_STARTED.md 安装依赖并运行 npm run build。"
  exit 1
fi
echo '浏览器打开 http://127.0.0.1:8797/ 。在此窗口按 Control-C 可停止。'
exec .venv/bin/python -m backend.server --port 8797
