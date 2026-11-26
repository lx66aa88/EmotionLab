"""HUMAN SIGNAL: localhost I/O adapter over the unchanged, frozen T4 Ensemble.

No datasets, training, face detection, resize, color conversion or disk uploads.
"""

import json
import time

from fastapi import Request
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse

from evaluation.inference import InferenceError, ROOT
from backend.services.grayscale_input import MAX_BYTES, decode_image

VERSION = "HUMAN SIGNAL / T5.1 · frozen T3.8"
SAMPLES = ROOT / "results/t4_step3_inference_20261104/examples"
DISCLAIMER = "模型输出概率，不代表真实内心情绪；概率未经校准，不用于心理或医疗诊断。"


def line(event, **payload):
    return (
        json.dumps({"event": event, **payload}, ensure_ascii=False, allow_nan=False)
        + "\n"
    )


def register(app):
    async def body(request):
        # Streaming size cap also covers requests without Content-Length.
        chunks, size = [], 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > MAX_BYTES:
                raise InferenceError("图片超过 1 MB，请选择 48×48 灰度人脸。")
            chunks.append(chunk)
        return b"".join(chunks)

    @app.exception_handler(InferenceError)
    async def input_error(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=422)

    @app.get("/api/health")
    def health():
        return {
            "status": "ready",
            "version": VERSION,
            "model_loads": app.state.model_loads,
            "models": [
                {k: m[k] for k in ("key", "epoch", "parameters")}
                for m in app.state.engine.info
            ],
            "labels": app.state.engine.manifest["labels"],
            "validation": app.state.validation,
            "disclaimer": DISCLAIMER,
            "input": "48×48 / L / cropped face / ≤1 MB",
        }

    @app.get("/api/examples/{index}")
    def example(index: int):
        if (
            index not in (0, 1, 2)
            or not (SAMPLES / ("public_%s.png" % index)).is_file()
        ):
            return JSONResponse({"detail": "样例不存在。"}, status_code=404)
        return FileResponse(SAMPLES / ("public_%s.png" % index), media_type="image/png")

    @app.post("/api/inspect")
    async def inspect(request: Request):
        started = time.perf_counter()
        _, preview = decode_image(await body(request))
        return {**preview, "inspect_ms": (time.perf_counter() - started) * 1000}

    @app.post("/api/analyze")
    async def analyze(request: Request):
        raw = await body(request)
        if app.state.lock.locked():
            return JSONResponse(
                {"detail": "仪器正在分析另一张图片，请稍后重试。"}, status_code=409
            )

        def events():
            started = time.perf_counter()
            try:
                yield line("stage", stage="check", label="输入检查")
                tensor, preview = decode_image(raw)
                yield line(
                    "stage", stage="preprocess", label="图像预处理", input=preview
                )
                yield line("stage", stage="infer", label="模型推理")
                # Never hold the model lock across a streamed yield. A disconnected
                # client cannot leave the cached engine permanently locked.
                if not app.state.lock.acquire(blocking=False):
                    yield line("error", detail="仪器正在分析另一张图片，请稍后重试。")
                    return
                try:
                    output = app.state.engine.predict(tensor)
                finally:
                    app.state.lock.release()
                yield line("stage", stage="compose", label="结果生成")
                yield line(
                    "result",
                    prediction=output["predictions"][0],
                    inference_ms=output["audit"]["inference_seconds"] * 1000,
                    total_ms=(time.perf_counter() - started) * 1000,
                    version=VERSION,
                    input_sha256=preview["sha256"],
                    model_weights=output["model_weights"],
                    view_weights=output["view_weights"],
                    audit=output["audit"],
                    disclaimer=DISCLAIMER,
                )
            except InferenceError as exc:
                yield line("error", detail=str(exc))
            except Exception:
                # Do not expose local paths, image contents or internals in the browser.
                yield line(
                    "error",
                    detail="本次推理未完成。请重试；若仍失败，请查看本地服务终端。",
                )
                import traceback

                traceback.print_exc()

        return StreamingResponse(
            events(),
            media_type="application/x-ndjson",
            headers={"X-Accel-Buffering": "no"},
        )
