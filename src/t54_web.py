"""Local-only T54 service. Composes untouched T53 photo APIs with a bounded LIVE route."""
import math
import threading
from io import BytesIO

from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from starlette.requests import ClientDisconnect

from src.t53_web import create_compat_app
from src.t52_faces import FaceDetector, PhotoError, ROOT
from src.t54_live import MAX_FRAME_BYTES, process_frame, vector

DIST = ROOT / 'web/human-signal/dist-t54'


def create_live_app(dist=DIST):
    app = create_compat_app()
    app.router.routes = [r for r in app.router.routes if getattr(r, 'name', '') != 'human-signal-t53']
    detector, guard = FaceDetector(), threading.Lock()

    @app.middleware('http')
    async def live_privacy(request, call_next):
        response = await call_next(request)
        # Inherited CSP restricts all fetches to this same localhost origin.
        response.headers['Content-Security-Policy'] = response.headers.get('Content-Security-Policy', '') + "; media-src 'self' blob:; form-action 'self'"
        response.headers['Permissions-Policy'] = 'camera=(self), microphone=(), geolocation=()'
        return response

    @app.get('/api/live/info')
    def info():
        return {'version': 't54-live-v1', 'detector': detector.info(), 'max_frame_bytes': MAX_FRAME_BYTES,
                'max_frame_edge': 960, 'initial_interval_ms': 333, 'minimum_interval_ms': 250,
                'storage': 'ephemeral RAM only; no frame logs, audio, recording or external upload',
                'raw_output': 'unchanged T4 three-model two-view equal-weight TTA',
                'display': 'client EMA alpha=0.45; reset on lost/changed target, pause, close and stale timeout'}

    @app.post('/api/live/frame')
    async def frame(request: Request, frame_id: int, captured_at: float, track: str = '', point: str = ''):
        if frame_id < 0 or frame_id > 2**53-1 or not math.isfinite(captured_at) or captured_at < 0:
            raise PhotoError('帧编号或时间戳无效。', 'frame_id')
        previous, selection = vector(track, 4), vector(point, 2)
        if not guard.acquire(blocking=False):
            raise PhotoError('正在处理上一帧，本帧已丢弃。', 'busy', 409)
        model_locked = False
        try:
            # Share the exact T51 model lock. A PHOTO inference can never overlap LIVE.
            if not app.state.lock.acquire(blocking=False):
                raise PhotoError('模型忙碌，本帧已丢弃。', 'busy', 409)
            model_locked = True
            length = request.headers.get('content-length')
            if length and (not length.isdigit() or int(length) > MAX_FRAME_BYTES):
                raise PhotoError('采样帧超过 2 MiB。', 'frame_bytes', 413)
            with BytesIO() as buffer:
                async for chunk in request.stream():
                    if buffer.tell()+len(chunk) > MAX_FRAME_BYTES:
                        raise PhotoError('采样帧超过 2 MiB。', 'frame_bytes', 413)
                    buffer.write(chunk)
                if await request.is_disconnected():
                    raise PhotoError('实时请求已取消。', 'cancelled', 499)
                return await run_in_threadpool(process_frame, buffer.getvalue(), detector, app.state.engine,
                                              frame_id, captured_at, previous, selection)
        except ClientDisconnect as exc:
            raise PhotoError('实时请求已取消。', 'cancelled', 499) from exc
        except PhotoError:
            raise
        except Exception:
            return JSONResponse({'code': 'unavailable', 'detail': '本机分析暂时不可用，请稍后恢复分析。'}, status_code=503)
        finally:
            if model_locked:
                app.state.lock.release()
            guard.release()

    if dist.is_dir():
        app.mount('/', StaticFiles(directory=dist, html=True), name='human-signal-t54')
    return app


app = create_live_app()

if __name__ == '__main__':
    import argparse
    import uvicorn
    parser = argparse.ArgumentParser(description='HUMAN SIGNAL T5.4：仅本机实时摄像头与照片')
    parser.add_argument('--port', type=int, default=8774)
    args = parser.parse_args()
    if not DIST.is_dir():
        parser.error('缺少 dist-t54；请参阅 docs/T54_RUNBOOK.md。')
    uvicorn.run(app, host='127.0.0.1', port=args.port, access_log=False, log_level='info')
