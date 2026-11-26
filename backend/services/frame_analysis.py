"""Ephemeral LIVE adapter. Frozen detector/crop/model rules are imported, never copied.

No sessions, frame history, file writes, video/audio capture or network clients.
Tracking is spatial continuity, not identity recognition.
"""

import base64
from io import BytesIO
import math
import time

import numpy as np
from PIL import Image

from backend.services.grayscale_input import decode_image
from backend.services.face_detection import PhotoError

MAX_FRAME_BYTES = 2 * 1024 * 1024
MAX_FRAME_EDGE = 960
MAX_FRAME_PIXELS = 960 * 960


def vector(value, count):
    if not value:
        return None
    try:
        numbers = [float(v) for v in value.split(",")]
        if len(numbers) != count or not all(
            math.isfinite(v) and 0 <= v <= 1 for v in numbers
        ):
            raise ValueError()
        if count == 4 and min(numbers[2:]) <= 0:
            raise ValueError()
        return numbers
    except (ValueError, TypeError):
        raise PhotoError("跟踪坐标无效，请重新选择目标。", "tracking", 422)


def validate_frame(raw):
    if not raw or len(raw) > MAX_FRAME_BYTES:
        raise PhotoError("采样帧为空或超过 2 MiB。", "frame_bytes", 413)
    try:
        with Image.open(BytesIO(raw)) as image:
            if (
                image.format not in ("JPEG", "PNG")
                or getattr(image, "n_frames", 1) != 1
            ):
                raise PhotoError("实时采样仅支持单帧 JPEG / PNG。", "frame_format")
            w, h = image.size
            if min(w, h) < 48 or max(w, h) > MAX_FRAME_EDGE or w * h > MAX_FRAME_PIXELS:
                raise PhotoError("采样长边须在 48–960 像素以内。", "frame_size", 413)
    except PhotoError:
        raise
    except (OSError, ValueError, Image.DecompressionBombError) as exc:
        raise PhotoError("采样帧无法解码，请重试。", "frame_decode") from exc


def overlap(a, b):
    x = max(0, min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0]))
    y = max(0, min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1]))
    intersection = x * y
    return intersection / max(1e-12, a[2] * a[3] + b[2] * b[3] - intersection)


def select_face(faces, previous=None, point=None):
    if point:
        candidates = [
            f
            for f in faces
            if f["normalized_box"][0] <= point[0] <= sum(f["normalized_box"][::2])
            and f["normalized_box"][1] <= point[1] <= sum(f["normalized_box"][1::2])
        ]
        return max(candidates, key=lambda f: f["detection_score"], default=None)
    if previous:
        # A lost target is never silently replaced with a different visible person.
        best = max(
            faces, key=lambda f: overlap(previous, f["normalized_box"]), default=None
        )
        if best and overlap(previous, best["normalized_box"]) >= 0.15:
            return best
        return None
    return max(faces, key=lambda f: f["box"][2] * f["box"][3], default=None)


def process_frame(
    raw, detector, engine, frame_id, captured_at, previous=None, point=None
):
    started = time.perf_counter()
    validate_frame(raw)
    detected = detector.detect(raw)  # Exact T52 dual scale YuNet + square-edge-v1.
    w, h = detected["photo"]["width"], detected["photo"]["height"]
    faces = [
        {k: f[k] for k in ("id", "box", "detection_score")} for f in detected["faces"]
    ]
    for face in faces:
        x, y, fw, fh = face["box"]
        face["normalized_box"] = [
            max(0.0, min(1.0, x / w)),
            max(0.0, min(1.0, y / h)),
            max(1e-6, min(1.0, fw / w)),
            max(1e-6, min(1.0, fh / h)),
        ]
    selected = select_face(faces, previous, point)
    output = {
        "frame_id": frame_id,
        "captured_at": captured_at,
        "frame_size": [w, h],
        "faces": faces,
        "selected_id": selected["id"] if selected else None,
        "detect_ms": detected["detect_ms"],
        "inference_ms": None,
        "raw_prediction": None,
        "status": "no_face" if not faces else "target_lost",
        "message": (
            "未检测到人脸"
            if not faces
            else "跟踪目标暂时消失，请回到画面或重新选择目标。"
        ),
        "tracking": "largest face initially; IoU >= 0.15 continuity; explicit selection; no identity recognition",
    }
    if selected:
        original = next(f for f in detected["faces"] if f["id"] == selected["id"])
        crop = base64.b64decode(original["input_preview"].split(",")[1])
        tensor, preview = decode_image(crop)  # Unchanged T4 float32 /255, [1,1,48,48].
        import cv2

        pixels = np.asarray(preview["pixels"], dtype=np.uint8).reshape(48, 48)
        sharpness = float(cv2.Laplacian(pixels, cv2.CV_64F).var())
        contrast = float(pixels.std())
        output.update(
            input_preview=original["input_preview"],
            input_sha256=preview["sha256"],
            crop=original["crop"],
            selected_box=selected["normalized_box"],
            quality={
                "sharpness": sharpness,
                "contrast": contrast,
                "rule": "display gate only: Laplacian variance >= 12 and gray std >= 8",
            },
        )
        if sharpness < 12 or contrast < 8:
            output.update(
                status="low_quality",
                message="人脸模糊或光线不足，请保持清晰、正面无遮挡。",
            )
        else:
            prediction = engine.predict(tensor)
            output.update(
                status="ok",
                message="正在观测当前目标",
                raw_prediction=prediction["predictions"][0],
                inference_ms=prediction["audit"]["inference_seconds"] * 1000,
                model_weights=prediction["model_weights"],
                view_weights=prediction["view_weights"],
                audit=prediction["audit"],
            )
    output["total_ms"] = (time.perf_counter() - started) * 1000
    return output
