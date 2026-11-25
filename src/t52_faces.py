"""Local photo adapter v1. No emotion model, datasets, files or network writes."""
import base64
import hashlib
from io import BytesIO
import math
from pathlib import Path
import threading
import time
import warnings

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / 'models/face_detection_yunet/face_detection_yunet_2023mar.onnx'
MODEL_SHA = '8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4'
MAX_BYTES = 20 * 1024 * 1024
MAX_PIXELS = 25_000_000
MAX_SIDE = 20_000
MAX_FACES = 32
MAX_CROP_PIXELS = 40_000_000
FORMATS = ('JPEG', 'PNG', 'BMP', 'TIFF', 'WEBP')
HEIF_HINT = '当前环境不支持 HEIC/HEIF（含 HEIF 系列）。请在 Mac「预览」中打开，选择「文件 → 导出 → JPEG 或 PNG」后上传；也可在 iPhone「设置 → 相机 → 格式」选择「兼容性最佳」拍摄新照片。'


class PhotoError(ValueError):
    def __init__(self, message, code='invalid_photo', status=422):
        super().__init__(message)
        self.code, self.status = code, status


def png(image):
    buffer = BytesIO()
    image.save(buffer, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(buffer.getvalue()).decode('ascii')


def decode_photo(raw):
    if not raw:
        raise PhotoError('照片为空，请重新选择。', 'empty')
    if len(raw) > MAX_BYTES:
        raise PhotoError('普通照片不得超过 20 MiB。请在本机导出较小的 JPEG 或 PNG。', 'byte_limit', 413)
    # Detect the ISO-BMFF container before Pillow; never trust a filename or MIME.
    if raw[4:8] == b'ftyp':
        raise PhotoError(HEIF_HINT, 'heif_unsupported')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as original:
                fmt, size = original.format, original.size
                if fmt not in FORMATS:
                    raise PhotoError('支持单帧 JPEG、PNG、WebP、BMP、TIFF；不支持 GIF、动图或此文件格式。', 'format')
                if size[0] * size[1] > MAX_PIXELS or max(size) > MAX_SIDE:
                    raise PhotoError('照片超过 2500 万像素或单边 20000 像素。请本机缩小后上传；4800 万像素原片需先导出较小版本。', 'pixel_limit', 413)
                if getattr(original, 'n_frames', 1) != 1:
                    raise PhotoError('请使用单帧照片，不支持动图或多页 TIFF。', 'frames')
                orientation = original.getexif().get(274, 1)
                original.load()
                oriented = ImageOps.exif_transpose(original)
                try:
                    if oriented.mode == 'RGBA' or 'transparency' in oriented.info or oriented.mode in ('LA', 'PA'):
                        rgba = oriented.convert('RGBA')
                        background = Image.new('RGBA', rgba.size, (255, 255, 255, 255))
                        background.alpha_composite(rgba)
                        rgb = background.convert('RGB')
                        rgba.close(); background.close()
                    else:
                        rgb = oriented.convert('RGB')
                    # No EXIF, ICC, names or user metadata in returned previews.
                    rgb.info.clear()
                finally:
                    oriented.close()
        return rgb, {'format': fmt, 'original_size': list(size), 'oriented_size': list(rgb.size),
                     'exif_orientation': orientation if orientation in range(1, 9) else None,
                     'orientation_applied': orientation in range(2, 9), 'metadata_removed': True,
                     'alpha_background': 'white'}
    except PhotoError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise PhotoError('照片像素过多，请在本机缩小至 2500 万像素以内。', 'pixel_limit', 413) from exc
    except (OSError, ValueError, SyntaxError, UnidentifiedImageError, OverflowError) as exc:
        raise PhotoError('照片无法解码、格式不支持或文件已损坏。请重新导出 JPEG/PNG；HEIC/HEIF 请先用 Mac「预览」转换。', 'decode') from exc


def square_crop(image, box):
    """Unclipped detector box -> fixed square with edge replication, never stretch."""
    x, y, w, h = map(float, box)
    if not all(math.isfinite(v) for v in (x, y, w, h)) or min(w, h) <= 0:
        raise PhotoError('检测框无效，请换一张照片。', 'box')
    width, height = image.size
    side = int(math.ceil(max(w, h) * 1.25))
    if side > 2 * max(width, height) or side * side > MAX_CROP_PIXELS:
        raise PhotoError('检测框或方形裁剪范围过大，请在本机缩小照片后重试。', 'box')
    left, top = math.floor(x + w / 2 - side / 2), math.floor(y + h / 2 - side / 2)
    right, bottom = left + side, top + side
    x0, y0, x1, y1 = max(0, left), max(0, top), min(width, right), min(height, bottom)
    if x1 <= x0 or y1 <= y0:
        raise PhotoError('人脸框在图像外，请换一张照片。', 'box')
    padding = [x0 - left, y0 - top, right - x1, bottom - y1]
    with image.crop((x0, y0, x1, y1)) as region:
        values = np.asarray(region)
        values = np.pad(values, ((padding[1], padding[3]), (padding[0], padding[2]), (0, 0)), mode='edge')
    square = Image.fromarray(values)
    with square.convert('L') as gray:
        model_input = gray.resize((48, 48), Image.Resampling.LANCZOS)
    display = square.copy(); display.thumbnail((224, 224), Image.Resampling.LANCZOS)
    data = {'crop_preview': png(display), 'input_preview': png(model_input),
            'crop': {'strategy': 'square-edge-v1', 'box': [left, top, side, side],
                     'padding_ltrb': padding, 'margin_factor': 1.25, 'padding': 'replicate edge',
                     'grayscale': 'Pillow RGB.convert(L)', 'resize': 'Pillow LANCZOS 48x48',
                     'mode': 'L', 'size': [48, 48], 'alignment': 'none',
                     'normalization': 'unchanged T4 float32 / 255 after confirmation'}}
    square.close(); display.close(); model_input.close()
    return data


class FaceDetector:
    """Immutable resources, lazy failure, serialized by the web request guard."""
    def __init__(self, path=MODEL):
        self.path = Path(path)
        self._detector = None
        self._lock = threading.Lock()

    def load(self):
        with self._lock:
            if self._detector is None:
                if not self.path.is_file():
                    raise PhotoError('本地人脸检测模型缺失。请按 T5.2 运行指南恢复固定资源；仍可使用预裁剪入口。启动不会自动下载。', 'detector_missing', 503)
                if hashlib.sha256(self.path.read_bytes()).hexdigest() != MODEL_SHA:
                    raise PhotoError('本地人脸检测模型 SHA-256 不匹配，请恢复已核验原件；仍可使用预裁剪入口。', 'detector_hash', 503)
                try:
                    import cv2
                    if cv2.__version__ != '4.11.0':
                        raise PhotoError('OpenCV 版本不匹配，需要隔离安装的 4.11.0.86。', 'detector_version', 503)
                    cv2.setNumThreads(1)
                    self._detector = cv2.FaceDetectorYN.create(str(self.path), '', (320, 320), .9, .3, 5000,
                                                              cv2.dnn.DNN_BACKEND_OPENCV, cv2.dnn.DNN_TARGET_CPU)
                except (ImportError, OSError) as exc:
                    raise PhotoError('本地 OpenCV 检测依赖不可用，请按 T5.2 指南准备；原推理环境无需升级。', 'detector_dependency', 503) from exc
                except PhotoError:
                    raise
                except Exception as exc:
                    raise PhotoError('本地人脸检测器无法加载，请恢复固定版本资源；仍可使用预裁剪入口。', 'detector_load', 503) from exc
        return self._detector

    def info(self):
        try:
            self.load()
            ready, detail = True, ''
        except PhotoError as exc:
            ready, detail = False, str(exc)
        return {'ready': ready, 'detail': detail, 'detector': 'YuNet 2023mar / OpenCV 4.11.0',
                'sha256': MODEL_SHA, 'max_bytes': MAX_BYTES, 'max_pixels': MAX_PIXELS,
                'formats': list(FORMATS), 'heif_supported': False, 'max_faces': MAX_FACES,
                'natural_photo_accuracy_validated': False}

    def detect(self, raw):
        started = time.perf_counter()
        detector = self.load()
        image, orientation = decode_photo(raw)
        try:
            import cv2
            width, height = image.size
            boxes, scores = [], []
            for edge in (960, 320):
                factor = min(1., edge / max(width, height))
                target = (max(32, round(width * factor)), max(32, round(height * factor)))
                with image.resize(target, Image.Resampling.LANCZOS) as small:
                    bgr = cv2.cvtColor(np.array(small), cv2.COLOR_RGB2BGR)
                detector.setInputSize(target)
                _, faces = detector.detect(bgr)
                del bgr
                if faces is not None:
                    for row in faces:
                        box = [float(row[0]) * width / target[0], float(row[1]) * height / target[1],
                               float(row[2]) * width / target[0], float(row[3]) * height / target[1]]
                        if all(math.isfinite(v) for v in box) and min(box[2:]) > 0 and math.isfinite(float(row[14])):
                            boxes.append(box); scores.append(float(row[14]))
            indices = cv2.dnn.NMSBoxes(boxes, scores, .9, .3) if boxes else []
            indices = np.asarray(indices, dtype=int).reshape(-1).tolist()
            if len(indices) > MAX_FACES:
                raise PhotoError('检测到超过 32 张人脸。请使用更小群体的照片，或先在本机裁出所需区域再上传。', 'too_many_faces')
            candidates = []
            for index in sorted(indices, key=lambda i: (boxes[i][0], boxes[i][1])):
                box = boxes[index]
                # Skip impossible detections, but retain original edge coordinates for square padding.
                if box[0] >= width or box[1] >= height or box[0]+box[2] <= 0 or box[1]+box[3] <= 0:
                    continue
                candidates.append({'id': len(candidates) + 1, 'box': box, 'detection_score': scores[index], **square_crop(image, box)})
            preview = image.copy(); preview.thumbnail((1280, 1280), Image.Resampling.LANCZOS)
            photo = {'preview': png(preview), 'width': width, 'height': height,
                     'preview_size': list(preview.size), **orientation}
            preview.close()
            return {'photo': photo, 'faces': candidates, 'count': len(candidates),
                    'detector': self.info(), 'detection': {'score_threshold': .9, 'nms_threshold': .3,
                    'long_edges': [960, 320], 'ordering': 'left-to-right then top-to-bottom'},
                    'detect_ms': (time.perf_counter()-started)*1000,
                    'notice': '普通照片仅用于演示预测，自然照片准确率未独立验证。',
                    'message': '' if candidates else '没有检测到人脸，未运行表情分类。请使用光线清晰、正面无遮挡的照片，或返回预裁剪 48×48 灰度入口。'}
        except PhotoError:
            raise
        except Exception as exc:
            raise PhotoError('本地人脸检测未完成，请换一张清晰照片；仍可使用预裁剪入口。', 'detection_failed') from exc
        finally:
            image.close()
