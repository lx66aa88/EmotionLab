"""Bounded native photo preparation, isolated from the frozen classifier.

All image bytes travel through pipes. The helper runs with OS-denied network and
file writes. No uploaded image or crop is stored. Request disconnect kills and
reaps the child before the serialization guard can be released.
"""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import platform
import warnings
from io import BytesIO
from PIL import Image

from src.t52_faces import PhotoError, ROOT

MAX_BYTES = 128 * 1024 * 1024
MAX_PIXELS = 100_000_000
MAX_SIDE = 32_768
TIMEOUT = 45
HELPER = ROOT / 'bin/t53/photo-decoder'
RESOURCE = ROOT / 'native/t53/BUILD.json'
PROFILE = '(version 1)(allow default)(deny network*)(deny file-write*)(deny file-read-data (subpath "%s"))' % (ROOT / 'data')


def check_helper():
    try:
        spec = json.loads(RESOURCE.read_text())
        if platform.system() != 'Darwin' or platform.machine() != 'arm64':
            raise ValueError('platform')
        if hashlib.sha256(HELPER.read_bytes()).hexdigest() != spec['binary_sha256']:
            raise ValueError('hash')
        if not os.access(HELPER, os.X_OK):
            raise ValueError('executable')
    except (OSError, ValueError, KeyError) as exc:
        raise PhotoError('本机照片解码资源不可用，请按 T53 运行指南恢复固定资源；无需改原推理环境。', 'decoder_missing', 503) from exc
    return spec


async def prepare_native(raw, disconnected=None, timeout=TIMEOUT, inherited_sandbox=False):
    if not raw:
        raise PhotoError('照片为空，请重新选择。', 'empty')
    if len(raw) > MAX_BYTES:
        raise PhotoError('原照片超过 128 MiB 的保护范围。', 'byte_limit', 413)
    check_helper()
    # TIFF directory/strip checks need no full pixel decode. Do this before native decoding.
    if raw[:2] in (b'II', b'MM'):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', Image.DecompressionBombWarning)
                with Image.open(BytesIO(raw)) as source:
                    width, height = source.size
                    if width * height > MAX_PIXELS or max(width, height) > MAX_SIDE:
                        raise PhotoError('这张照片超过 1 亿像素或单边 32768 像素的内存保护范围。', 'pixel_limit', 413)
                    try:
                        source.seek(1)
                    except EOFError:
                        source.seek(0)
                    else:
                        raise PhotoError('请选择单帧照片，不支持多页 TIFF。', 'frames')
                    offsets = source.tag_v2.get(273, source.tag_v2.get(324, ()))
                    counts = source.tag_v2.get(279, source.tag_v2.get(325, ()))
                    if not offsets or len(offsets) != len(counts) or any(a < 0 or b < 1 or a + b > len(raw) for a, b in zip(offsets, counts)):
                        raise PhotoError('TIFF 像素数据不完整或布局不支持。', 'decode')
        except PhotoError:
            raise
        except Image.DecompressionBombError as exc:
            raise PhotoError('照片像素超过内存保护范围。', 'pixel_limit', 413) from exc
        except (OSError, ValueError, SyntaxError, OverflowError) as exc:
            raise PhotoError('TIFF 元数据损坏或格式不支持。', 'decode') from exc
    # The OS-isolated acceptance runner verifies inherited restrictions before
    # using this injection point: macOS forbids applying a second sandbox.
    command = [str(HELPER)] if inherited_sandbox else ['/usr/bin/sandbox-exec', '-p', PROFILE, str(HELPER)]
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            env={'PATH': '/usr/bin:/bin', 'TMPDIR': '/nonexistent-emotionlab-t53'})
    except OSError as exc:
        raise PhotoError('本机解码进程无法启动，请按 T53 运行指南核对本地权限与资源。', 'decoder_launch', 503) from exc
    task = asyncio.create_task(process.communicate(raw))
    started = asyncio.get_running_loop().time()
    try:
        while not task.done():
            if disconnected and await disconnected():
                raise PhotoError('已取消本次照片转换。', 'cancelled', 499)
            if asyncio.get_running_loop().time() - started > timeout:
                raise PhotoError('本机照片转换超时，请换较小照片。', 'timeout', 422)
            await asyncio.wait({task}, timeout=.05)
        output, _ = await task
        if len(output) > 18 * 1024 * 1024:
            raise PhotoError('本机照片转换输出超限。', 'output_limit')
        try:
            data = json.loads(output)
        except (ValueError, UnicodeError) as exc:
            raise PhotoError('本机照片解码未完成，文件可能损坏或资源不足。', 'decode') from exc
        if process.returncode:
            code = data.get('code', 'decode')
            raise PhotoError(data.get('detail', '本机照片解码失败。'), code, 413 if code in ('pixel_limit', 'byte_limit') else 422)
        if not isinstance(data.get('jpeg'), str) or not isinstance(data.get('info'), dict):
            raise PhotoError('本机照片转换结果无效。', 'decode')
        return data
    finally:
        if process.returncode is None:
            process.kill()
        # communicate is drained to avoid leaving a pipe transport/child behind.
        await asyncio.shield(task)
        await process.wait()
