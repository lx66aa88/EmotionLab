"""Validate an uploaded grayscale crop and build the model input and preview."""

import base64
import hashlib
from io import BytesIO

import numpy as np
from PIL import Image, UnidentifiedImageError
from evaluation.inference import InferenceError, preprocess_pixels

MAX_BYTES = 1024 * 1024


def decode_image(raw):
    """Same image contract as T4 read_image; bytes transport only."""
    if not raw or len(raw) > MAX_BYTES:
        raise InferenceError("请选择不超过 1 MB 的图片。")
    try:
        with Image.open(BytesIO(raw)) as image:
            if image.format not in ("PNG", "JPEG", "BMP", "TIFF"):
                raise InferenceError(
                    "支持 PNG、JPEG、BMP、TIFF；不支持动图、WebP 或其他文件。"
                )
            if image.mode != "L" or image.size != (48, 48):
                raise InferenceError(
                    "需要已裁剪的 48×48、8 位灰度（L 模式）人脸。当前为 %s × %s，%s 模式。本阶段不自动裁剪、缩放或转灰度；可先试用下方样例。"
                    % (*image.size, image.mode)
                )
            if getattr(image, "n_frames", 1) != 1:
                raise InferenceError("请选择单帧图片。")
            pixels = np.array(image)
    except InferenceError:
        raise
    except (
        OSError,
        ValueError,
        UnidentifiedImageError,
        Image.DecompressionBombError,
    ) as exc:
        raise InferenceError(
            "图片无法解码或已损坏，请重新选择有效的 48×48 灰度人脸。"
        ) from exc
    # The sole normalization call is the original T4 implementation.
    tensor = preprocess_pixels(pixels)
    preview = BytesIO()
    Image.fromarray(pixels).save(preview, format="PNG")
    return tensor, {
        "width": 48,
        "height": 48,
        "mode": "L",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "preview": "data:image/png;base64,"
        + base64.b64encode(preview.getvalue()).decode("ascii"),
        "pixels": pixels.reshape(-1).tolist(),
        "range": [float(tensor.min()), float(tensor.max())],
        "preprocessing": "float32 / 255; [1,1,48,48]",
        "face_detection": False,
    }
