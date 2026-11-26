"""Compose the local application and serve the production frontend."""

import argparse
import threading
from contextlib import asynccontextmanager
from pathlib import Path
import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from evaluation.inference import Ensemble, ROOT, saved_results
from backend.routes import classification, faces, photo_conversion, live, charts

DIST = ROOT / "frontend/dist"


def create_app(dist=DIST, classroom_experiments=True):
    @asynccontextmanager
    async def lifespan(app):
        app.state.engine = Ensemble()
        app.state.lock = threading.Lock()
        app.state.model_loads = 1
        app.state.validation = saved_results()
        yield
        app.state.engine = None

    app = FastAPI(
        title="EmotionLab — HUMAN SIGNAL",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]"]
    )

    @app.middleware("http")
    async def local_only(request, call_next):
        if request.client and request.client.host not in (
            "127.0.0.1",
            "::1",
            "testclient",
        ):
            return JSONResponse({"detail": "仅允许本机访问。"}, status_code=403)
        origin = request.headers.get("origin")
        if origin and origin != str(request.base_url).rstrip("/"):
            return JSONResponse({"detail": "仅允许同源本机请求。"}, status_code=403)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; font-src 'self'; connect-src 'self'; script-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
        )
        response.headers["Permissions-Policy"] = (
            "camera=(self), microphone=(), geolocation=()"
        )
        response.headers[
            "Content-Security-Policy"
        ] += "; media-src 'self' blob:; form-action 'self'"
        return response

    classification.register(app)
    faces.register(app)
    photo_conversion.register(app)
    live.register(app)
    if classroom_experiments:
        charts.attach_experiments(app)
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")
    return app


def main():
    parser = argparse.ArgumentParser(description="HUMAN SIGNAL 本机服务")
    parser.add_argument("--port", type=int, default=8797)
    parser.add_argument("--dist", type=Path, default=DIST)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("端口须在 1 至 65535 内")
    if not (args.dist / "index.html").is_file():
        parser.error("请先在项目根目录运行 npm ci 和 npm run build")
    uvicorn.run(
        create_app(args.dist), host="127.0.0.1", port=args.port, access_log=False
    )


if __name__ == "__main__":
    main()
