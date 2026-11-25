#!/bin/sh
set -eu

T72_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
T72_WEB="$T72_ROOT/web/human-signal"
T72_DIST="$T72_WEB/dist-t72"
T72_URL=http://127.0.0.1:8797/
cd "$T72_ROOT"

case "${1:-}" in
  '') T72_MODE=start ;;
  --check) T72_MODE=check ;;
  *) echo '用法：sh scripts/start_t72.sh [--check]' >&2; exit 2 ;;
esac
[ "$#" -le 1 ] || { echo '用法：sh scripts/start_t72.sh [--check]' >&2; exit 2; }

for T72_DEP in .venv/bin/python .t51-deps/fastapi .t52-deps/cv2; do
  if [ ! -e "$T72_DEP" ] || [ ! -x "$T72_DEP" ]; then
    echo "缺少或无法使用 ${T72_DEP}。请参阅 docs/T83_START_STOP.md；课堂启动不会下载依赖。" >&2
    exit 2
  fi
done

T72_PREFLIGHT=0
.venv/bin/python -I -B scripts/t83_preflight.py "$T72_MODE" || T72_PREFLIGHT=$?
case "$T72_PREFLIGHT" in
  0) ;;
  10) exit 0 ;;
  *) exit "$T72_PREFLIGHT" ;;
esac

export PYTHONPATH="$T72_ROOT/.t52-deps:$T72_ROOT/.t51-deps:$T72_ROOT"
export PYTHONNOUSERSITE=1
if [ "$T72_MODE" = check ]; then
  .venv/bin/python -B -c 'import fastapi, uvicorn, cv2; print("FastAPI", fastapi.__version__, "· Uvicorn", uvicorn.__version__, "· OpenCV", cv2.__version__)' ||
    { echo 'Web 依赖无法导入。请参阅 docs/T83_START_STOP.md。' >&2; exit 2; }
  exec .venv/bin/python -B -m src.classroom check
fi

echo "HUMAN SIGNAL T7.2 · $T72_URL"
echo "课堂实验图表 · ${T72_URL}experiments/"
exec .venv/bin/python -B -m src.t62_web --port 8797 --dist "$T72_DIST" --classroom-experiments
