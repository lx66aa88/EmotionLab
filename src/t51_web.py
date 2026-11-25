"""HUMAN SIGNAL: localhost I/O adapter over the unchanged, frozen T4 Ensemble.

No datasets, training, face detection, resize, color conversion or disk uploads.
"""
from contextlib import asynccontextmanager
from io import BytesIO
from pathlib import Path
import base64
import hashlib
import json
import threading
import time

import numpy as np
from PIL import Image, UnidentifiedImageError
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from src.ensemble import Ensemble, InferenceError, preprocess_pixels, saved_results, ROOT

VERSION = 'HUMAN SIGNAL / T5.1 · frozen T3.8'
MAX_BYTES = 1024 * 1024
SAMPLES = ROOT / 'results/t4_step3_inference_20261104/examples'
DIST = ROOT / 'web/human-signal/dist'
DISCLAIMER = '模型输出概率，不代表真实内心情绪；概率未经校准，不用于心理或医疗诊断。'


def decode_image(raw):
    """Same image contract as T4 read_image; bytes transport only."""
    if not raw or len(raw) > MAX_BYTES:
        raise InferenceError('请选择不超过 1 MB 的图片。')
    try:
        with Image.open(BytesIO(raw)) as image:
            if image.format not in ('PNG', 'JPEG', 'BMP', 'TIFF'):
                raise InferenceError('支持 PNG、JPEG、BMP、TIFF；不支持动图、WebP 或其他文件。')
            if image.mode != 'L' or image.size != (48, 48):
                raise InferenceError('需要已裁剪的 48×48、8 位灰度（L 模式）人脸。当前为 %s × %s，%s 模式。本阶段不自动裁剪、缩放或转灰度；可先试用下方样例。' % (*image.size, image.mode))
            if getattr(image, 'n_frames', 1) != 1:
                raise InferenceError('请选择单帧图片。')
            pixels = np.array(image)
    except InferenceError:
        raise
    except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise InferenceError('图片无法解码或已损坏，请重新选择有效的 48×48 灰度人脸。') from exc
    # The sole normalization call is the original T4 implementation.
    tensor = preprocess_pixels(pixels)
    preview = BytesIO()
    Image.fromarray(pixels).save(preview, format='PNG')
    return tensor, {
        'width': 48, 'height': 48, 'mode': 'L', 'sha256': hashlib.sha256(raw).hexdigest(),
        'preview': 'data:image/png;base64,' + base64.b64encode(preview.getvalue()).decode('ascii'),
        'pixels': pixels.reshape(-1).tolist(), 'range': [float(tensor.min()), float(tensor.max())],
        'preprocessing': 'float32 / 255; [1,1,48,48]', 'face_detection': False,
    }


def line(event, **payload):
    return json.dumps({'event': event, **payload}, ensure_ascii=False, allow_nan=False) + '\n'


def create_app():
    @asynccontextmanager
    async def lifespan(app):
        app.state.engine = Ensemble()
        app.state.lock = threading.Lock()
        app.state.model_loads = 1
        app.state.validation = saved_results()
        yield
        app.state.engine = None

    app = FastAPI(title='EmotionLab — HUMAN SIGNAL', lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['localhost', '127.0.0.1', '[::1]'])

    @app.middleware('http')
    async def local_only(request, call_next):
        if request.client and request.client.host not in ('127.0.0.1', '::1', 'testclient'):
            return JSONResponse({'detail': '仅允许本机访问。'}, status_code=403)
        origin = request.headers.get('origin')
        if origin and origin != str(request.base_url).rstrip('/'):
            return JSONResponse({'detail': '仅允许同源本机请求。'}, status_code=403)
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Content-Security-Policy'] = "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; font-src 'self'; connect-src 'self'; script-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
        return response

    async def body(request):
        # Streaming size cap also covers requests without Content-Length.
        chunks, size = [], 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > MAX_BYTES:
                raise InferenceError('图片超过 1 MB，请选择 48×48 灰度人脸。')
            chunks.append(chunk)
        return b''.join(chunks)

    @app.exception_handler(InferenceError)
    async def input_error(request, exc):
        return JSONResponse({'detail': str(exc)}, status_code=422)

    @app.get('/api/health')
    def health():
        return {'status': 'ready', 'version': VERSION, 'model_loads': app.state.model_loads,
                'models': [{k: m[k] for k in ('key', 'epoch', 'parameters')} for m in app.state.engine.info],
                'labels': app.state.engine.manifest['labels'], 'validation': app.state.validation,
                'disclaimer': DISCLAIMER, 'input': '48×48 / L / cropped face / ≤1 MB'}

    @app.get('/api/examples/{index}')
    def example(index: int):
        if index not in (0, 1, 2):
            return JSONResponse({'detail': '样例不存在。'}, status_code=404)
        return FileResponse(SAMPLES / ('public_%s.png' % index), media_type='image/png')

    @app.post('/api/inspect')
    async def inspect(request: Request):
        started = time.perf_counter()
        _, preview = decode_image(await body(request))
        return {**preview, 'inspect_ms': (time.perf_counter() - started) * 1000}

    @app.post('/api/analyze')
    async def analyze(request: Request):
        raw = await body(request)
        if app.state.lock.locked():
            return JSONResponse({'detail': '仪器正在分析另一张图片，请稍后重试。'}, status_code=409)

        def events():
            started = time.perf_counter()
            try:
                yield line('stage', stage='check', label='输入检查')
                tensor, preview = decode_image(raw)
                yield line('stage', stage='preprocess', label='图像预处理', input=preview)
                yield line('stage', stage='infer', label='模型推理')
                # Never hold the model lock across a streamed yield. A disconnected
                # client cannot leave the cached engine permanently locked.
                if not app.state.lock.acquire(blocking=False):
                    yield line('error', detail='仪器正在分析另一张图片，请稍后重试。')
                    return
                try:
                    output = app.state.engine.predict(tensor)
                finally:
                    app.state.lock.release()
                yield line('stage', stage='compose', label='结果生成')
                yield line('result', prediction=output['predictions'][0],
                           inference_ms=output['audit']['inference_seconds'] * 1000,
                           total_ms=(time.perf_counter() - started) * 1000,
                           version=VERSION, input_sha256=preview['sha256'],
                           model_weights=output['model_weights'], view_weights=output['view_weights'],
                           audit=output['audit'], disclaimer=DISCLAIMER)
            except InferenceError as exc:
                yield line('error', detail=str(exc))
            except Exception:
                # Do not expose local paths, image contents or internals in the browser.
                yield line('error', detail='本次推理未完成。请重试；若仍失败，请查看本地服务终端。')
                import traceback
                traceback.print_exc()

        return StreamingResponse(events(), media_type='application/x-ndjson', headers={'X-Accel-Buffering': 'no'})

    if DIST.is_dir():
        app.mount('/', StaticFiles(directory=DIST, html=True), name='human-signal')
    return app


app = create_app()

if __name__ == '__main__':
    import argparse
    import uvicorn
    parser = argparse.ArgumentParser(description='HUMAN SIGNAL：本机 T5.1 页面，保留 T4 推理。')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    if not DIST.is_dir():
        parser.error('缺少已构建页面，请先运行 scripts/setup_t51.sh。')
    uvicorn.run(app, host='127.0.0.1', port=args.port, access_log=False, log_level='info')
