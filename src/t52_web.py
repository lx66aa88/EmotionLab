"""T5.2 extension. Reuse untouched T5.1 inspect/analyze and T4 Ensemble."""
import threading
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from src.t51_web import create_app
from src.t52_faces import FaceDetector, PhotoError, MAX_BYTES, ROOT

DIST = ROOT / 'web/human-signal/dist-t52'


def create_photo_app():
    app = create_app()
    # Register extension routes before the static catch-all. T5.1 factory is unchanged.
    app.router.routes = [route for route in app.router.routes if getattr(route, 'name', '') != 'human-signal']
    detector, guard = FaceDetector(), threading.Lock()

    @app.exception_handler(PhotoError)
    async def photo_error(request, exc):
        return JSONResponse({'detail': str(exc), 'code': exc.code}, status_code=exc.status)

    @app.get('/api/photo-info')
    def photo_info():
        return detector.info()

    @app.post('/api/detect')
    async def detect(request: Request):
        if not guard.acquire(blocking=False):
            raise PhotoError('本机正在处理另一张照片，请稍后重试。', 'busy', 409)
        chunks, raw = [], b''
        try:
            length = request.headers.get('content-length')
            if length and (not length.isdigit() or int(length) > MAX_BYTES):
                raise PhotoError('普通照片不得超过 20 MiB，请在本机缩小后上传。', 'byte_limit', 413)
            size = 0
            async for chunk in request.stream():
                size += len(chunk)
                if size > MAX_BYTES:
                    raise PhotoError('普通照片不得超过 20 MiB，请在本机缩小后上传。', 'byte_limit', 413)
                chunks.append(chunk)
            raw = b''.join(chunks)
            chunks.clear()
            # Starlette shields the worker until completion; reset cannot unlock a running detector.
            return await run_in_threadpool(detector.detect, raw)
        finally:
            raw = b''
            chunks.clear()
            guard.release()

    if DIST.is_dir():
        app.mount('/', StaticFiles(directory=DIST, html=True), name='human-signal-t52')
    return app


app = create_photo_app()

if __name__ == '__main__':
    import argparse
    import uvicorn
    parser = argparse.ArgumentParser(description='HUMAN SIGNAL T5.2，本机普通照片确认与原三模型推理。')
    parser.add_argument('--port', type=int, default=8772)
    args = parser.parse_args()
    if not DIST.is_dir():
        parser.error('缺少 T5.2 构建资源，请先按 docs/T52_RUNBOOK.md 准备。')
    uvicorn.run(app, host='127.0.0.1', port=args.port, access_log=False, log_level='info')
