"""Local-only T54 service. Composes untouched T53 photo APIs with a bounded LIVE route."""

import math
import threading
from io import BytesIO

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from starlette.requests import ClientDisconnect

from backend.services.face_detection import FaceDetector, PhotoError
from backend.services.frame_analysis import MAX_FRAME_BYTES, process_frame, vector


def register(app):
    detector, guard = FaceDetector(), threading.Lock()

    @app.get("/api/live/info")
    def info():
        return {
            "version": "t54-live-v1",
            "detector": detector.info(),
            "max_frame_bytes": MAX_FRAME_BYTES,
            "max_frame_edge": 960,
            "initial_interval_ms": 333,
            "minimum_interval_ms": 250,
            "storage": "ephemeral RAM only; no frame logs, audio, recording or external upload",
            "raw_output": "unchanged T4 three-model two-view equal-weight TTA",
            "display": "client EMA alpha=0.45; reset on lost/changed target, pause, close and stale timeout",
        }

    @app.post("/api/live/frame")
    async def frame(
        request: Request,
        frame_id: int,
        captured_at: float,
        track: str = "",
        point: str = "",
    ):
        if (
            frame_id < 0
            or frame_id > 2**53 - 1
            or not math.isfinite(captured_at)
            or captured_at < 0
        ):
            raise PhotoError("帧编号或时间戳无效。", "frame_id")
        previous, selection = vector(track, 4), vector(point, 2)
        if not guard.acquire(blocking=False):
            raise PhotoError("正在处理上一帧，本帧已丢弃。", "busy", 409)
        model_locked = False
        try:
            # Share the exact T51 model lock. A PHOTO inference can never overlap LIVE.
            if not app.state.lock.acquire(blocking=False):
                raise PhotoError("模型忙碌，本帧已丢弃。", "busy", 409)
            model_locked = True
            length = request.headers.get("content-length")
            if length and (not length.isdigit() or int(length) > MAX_FRAME_BYTES):
                raise PhotoError("采样帧超过 2 MiB。", "frame_bytes", 413)
            with BytesIO() as buffer:
                async for chunk in request.stream():
                    if buffer.tell() + len(chunk) > MAX_FRAME_BYTES:
                        raise PhotoError("采样帧超过 2 MiB。", "frame_bytes", 413)
                    buffer.write(chunk)
                if await request.is_disconnected():
                    raise PhotoError("实时请求已取消。", "cancelled", 499)
                return await run_in_threadpool(
                    process_frame,
                    buffer.getvalue(),
                    detector,
                    app.state.engine,
                    frame_id,
                    captured_at,
                    previous,
                    selection,
                )
        except ClientDisconnect as exc:
            raise PhotoError("实时请求已取消。", "cancelled", 499) from exc
        except PhotoError:
            raise
        except Exception:
            return JSONResponse(
                {
                    "code": "unavailable",
                    "detail": "本机分析暂时不可用，请稍后恢复分析。",
                },
                status_code=503,
            )
        finally:
            if model_locked:
                app.state.lock.release()
            guard.release()
