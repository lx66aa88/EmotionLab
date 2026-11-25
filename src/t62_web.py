"""Serve the integrated T6.2 frontend using the existing local PHOTO and LIVE APIs."""
import argparse
from pathlib import Path

import uvicorn

from src.t52_faces import ROOT
from src.t54_web import create_live_app

DIST = ROOT / 'web/human-signal/dist-t62'


def main():
    parser = argparse.ArgumentParser(description='HUMAN SIGNAL T6.2 / Seven Signals')
    parser.add_argument('--port', type=int, default=8787)
    parser.add_argument('--dist', type=Path, default=DIST)
    parser.add_argument('--classroom-experiments', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('端口必须为 1–65535 的整数。')
    if not (args.dist / 'index.html').is_file():
        parser.error('缺少 T6.2 前端构建，请使用 scripts/start_t62.sh。')
    app = create_live_app(args.dist)
    if args.classroom_experiments:
        from src.t83_experiments import attach_experiments
        attach_experiments(app)
    uvicorn.run(app, host='127.0.0.1', port=args.port,
                access_log=False, log_level='info')


if __name__ == '__main__':
    main()
