"""T5.3 local input extension, preserving the T51/T52 APIs and running services."""

import asyncio
import gc
from io import BytesIO

from fastapi import Request
from starlette.requests import ClientDisconnect
from backend.services.face_detection import PhotoError
from backend.services.photo_decoder import (
    MAX_BYTES,
    MAX_PIXELS,
    MAX_SIDE,
    check_helper,
    prepare_native,
)


def register(app, decoder=prepare_native):
    guard = asyncio.Lock()

    @app.get("/api/photo-compat")
    async def compatibility():
        try:
            spec = check_helper()
            ready, detail = True, ""
        except PhotoError as exc:
            ready, detail, spec = False, str(exc), {}
        return {
            "ready": ready,
            "detail": detail,
            "version": "t53-imageio-v1",
            "formats": ["HEIC", "HEIF", "TIFF"],
            "max_bytes": MAX_BYTES,
            "max_pixels": MAX_PIXELS,
            "max_side": MAX_SIDE,
            "output_edge": 4096,
            "output_bytes": 12 * 1024 * 1024,
            "binary_sha256": spec.get("binary_sha256"),
            "storage": (
                "memory and pipes; helper OS denies file writes and network"
                if decoder is prepare_native
                else "memory and pipes; verified inherited OS restrictions deny file writes and external network"
            ),
        }

    @app.post("/api/prepare-photo")
    async def prepare(request: Request):
        if guard.locked():
            raise PhotoError(
                "本机正在适配上一张照片，正在释放资源，请稍后重试。", "busy", 409
            )
        async with guard:
            length = request.headers.get("content-length")
            if length and (not length.isdigit() or int(length) > MAX_BYTES):
                raise PhotoError("原照片超过 128 MiB 的保护范围。", "byte_limit", 413)
            # BytesIO avoids retaining a list of 128 MiB chunks plus a joined copy.
            with BytesIO() as buffer:
                try:
                    async for chunk in request.stream():
                        if buffer.tell() + len(chunk) > MAX_BYTES:
                            raise PhotoError(
                                "原照片超过 128 MiB 的保护范围。", "byte_limit", 413
                            )
                        buffer.write(chunk)
                    return await decoder(buffer.getvalue(), request.is_disconnected)
                except ClientDisconnect as exc:
                    raise PhotoError("已取消本次照片上传。", "cancelled", 499) from exc
                finally:
                    # Pipe transports can form cycles with source-sized buffers;
                    # collect after closing the input, including cancellation.
                    buffer.close()
                    gc.collect()
