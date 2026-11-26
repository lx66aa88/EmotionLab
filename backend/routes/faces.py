"""T5.2 extension. Reuse untouched T5.1 inspect/analyze and T4 Ensemble."""

import threading
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from backend.services.face_detection import FaceDetector, PhotoError, MAX_BYTES


def register(app):
    detector, guard = FaceDetector(), threading.Lock()

    @app.exception_handler(PhotoError)
    async def photo_error(request, exc):
        return JSONResponse(
            {"detail": str(exc), "code": exc.code}, status_code=exc.status
        )

    @app.get("/api/photo-info")
    def photo_info():
        return detector.info()

    @app.post("/api/detect")
    async def detect(request: Request):
        if not guard.acquire(blocking=False):
            raise PhotoError("本机正在处理另一张照片，请稍后重试。", "busy", 409)
        chunks, raw = [], b""
        try:
            length = request.headers.get("content-length")
            if length and (not length.isdigit() or int(length) > MAX_BYTES):
                raise PhotoError(
                    "普通照片不得超过 20 MiB，请在本机缩小后上传。", "byte_limit", 413
                )
            size = 0
            async for chunk in request.stream():
                size += len(chunk)
                if size > MAX_BYTES:
                    raise PhotoError(
                        "普通照片不得超过 20 MiB，请在本机缩小后上传。",
                        "byte_limit",
                        413,
                    )
                chunks.append(chunk)
            raw = b"".join(chunks)
            chunks.clear()
            # Starlette shields the worker until completion; reset cannot unlock a running detector.
            return await run_in_threadpool(detector.detect, raw)
        finally:
            raw = b""
            chunks.clear()
            guard.release()
