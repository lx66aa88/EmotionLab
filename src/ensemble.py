"""Frozen T3.8 three-model inference. No optimizer, backward, or training imports."""
import hashlib
import json
from pathlib import Path
import platform
import sys
import time

import numpy as np
import torch

from src.dataset import LABELS
from src.t3_models import load_t3
from src.t37_models import load as load_t37
from src.ensemble_math import calculate, infer_view, state_sha256, validate_images

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = 'configs/inference/best_triple.json'
MANIFEST_SHA256 = '87e71265e82cc01ba103339a2cd0e0e65d1c20ee73cde5e359871dcff0635333'
PREPROCESSING = 'float32 / 255; [N,1,48,48]'
LABELS_ZH = ('愤怒', '厌恶', '恐惧', '快乐', '悲伤', '惊喜', '中立')


class InferenceError(ValueError):
    """Actionable contract, file, input, or inference failure."""


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as file:
        for block in iter(lambda: file.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def checked_file(root, relative, expected_sha):
    path = Path(root) / relative
    if not path.is_file():
        raise InferenceError('文件缺失：%s；请从原工程/备份恢复，勿重新训练。' % path)
    if sha256(path) != expected_sha:
        raise InferenceError('SHA-256 不匹配：%s；文件可能损坏或版本错误，请恢复已核验原件。' % path)
    return path


def read_manifest(root=ROOT):
    path = checked_file(root, MANIFEST_PATH, MANIFEST_SHA256)
    manifest = json.loads(path.read_text(encoding='utf-8'))
    if (tuple(manifest['labels']) != LABELS or manifest['preprocessing'] != PREPROCESSING
            or [m['key'] for m in manifest['models']] != ['w32', 't3', 'w16']
            or manifest['model_weights'] != [1 / 3] * 3
            or manifest['view_weights'] != [0.5, 0.5]):
        raise InferenceError('冻结清单的标签、模型或融合规则不兼容。')
    return manifest


def validate_checkpoint(cp, spec, manifest):
    """Compare the entire saved configuration, metadata, and class semantics."""
    if (cp.get('format_version') != spec['format_version'] or cp.get('epoch') != spec['epoch']
            or tuple(cp.get('labels', ())) != LABELS
            or cp.get('preprocessing') != PREPROCESSING
            or cp.get('data_sha256') != manifest['data_sha256']
            or cp.get('config') != spec['config']):
        raise InferenceError('模型 %s 的版本、轮次、标签、预处理、数据摘要或配置不兼容。' % spec['key'])


def preprocess_pixels(pixels):
    """Raw 0..255 grayscale -> float32 /255, exactly as original validation."""
    values = np.asarray(pixels)
    if (values.shape != (48, 48) or values.dtype.kind not in 'uif'
            or not np.isfinite(values).all() or values.min() < 0 or values.max() > 255):
        raise InferenceError('输入必须是 48×48 灰度数值，全部有限且在 [0,255]。不自动裁剪或缩放。')
    return torch.from_numpy(values.astype(np.float32, copy=True)).reshape(1, 1, 48, 48).div_(255.0)


def read_image(path):
    path = Path(path)
    if not path.is_file():
        raise InferenceError('输入图片不存在：%s' % path)
    try:
        if path.suffix.lower() == '.npy':
            pixels = np.load(path, allow_pickle=False)
        elif path.suffix.lower() in ('.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff'):
            from PIL import Image
            with Image.open(path) as image:
                if image.mode != 'L' or image.size != (48, 48):
                    raise InferenceError('图片须为 48×48、8位灰度 L 模式；当前为 %s %s。' % (image.size, image.mode))
                pixels = np.array(image)
        else:
            raise InferenceError('不支持此格式；使用 48×48 灰度 PNG 或原始像素 .npy。')
        return preprocess_pixels(pixels)
    except InferenceError:
        raise
    except (OSError, ValueError, EOFError) as exc:
        raise InferenceError('无法读取图片 %s：%s' % (path, exc)) from exc


def environment():
    import importlib.metadata
    import shutil
    return {'python': sys.version, 'executable': sys.executable, 'platform': platform.platform(),
            'torch': torch.__version__, 'numpy': np.__version__,
            'pillow': importlib.metadata.version('Pillow'), 'device': 'cpu',
            'threads': torch.get_num_threads(),
            'deterministic_algorithms': torch.are_deterministic_algorithms_enabled(),
            'disk_free_bytes': shutil.disk_usage(ROOT).free,
            'mps_available': torch.backends.mps.is_available(), 'cuda_available': torch.cuda.is_available()}


class Ensemble:
    def __init__(self, root=ROOT):
        self.root = Path(root)
        self.manifest = read_manifest(self.root)
        torch.set_num_threads(1)
        torch.use_deterministic_algorithms(True)
        self.models, self.info = {}, []
        for spec in self.manifest['models']:
            path = checked_file(self.root, spec['checkpoint'], spec['sha256'])
            config_path = checked_file(self.root, spec['config_path'], spec['config_sha256'])
            if json.loads(config_path.read_text(encoding='utf-8')) != spec['config']:
                raise InferenceError('外部配置与冻结模型配置不一致：%s' % config_path)
            try:
                model, cp = (load_t37 if spec['format_version'] == 37 else load_t3)(path)
                validate_checkpoint(cp, spec, self.manifest)
                count = sum(p.numel() for p in model.parameters())
                if count != spec['parameters'] or state_sha256(model) != spec['state_sha256']:
                    raise InferenceError('模型结构或参数状态摘要不兼容：%s' % spec['key'])
                if not all(torch.isfinite(v).all() for v in model.state_dict().values()):
                    raise InferenceError('模型含非有限参数：%s' % spec['key'])
                model.eval().requires_grad_(False)
                self.models[spec['key']] = model
                self.info.append({k: spec[k] for k in ('key', 'name', 'checkpoint', 'sha256',
                                                       'format_version', 'epoch', 'parameters', 'config_path')})
                del cp  # Optimizer/RNG payloads are never used or restored.
            except InferenceError:
                raise
            except (RuntimeError, ValueError, KeyError, TypeError, OSError, EOFError) as exc:
                raise InferenceError('无法加载模型 %s（权重/结构不兼容）：%s' % (spec['key'], exc)) from exc

    def infer(self, images, batch_size=128):
        validate_images(images)
        if images.device.type != 'cpu':
            raise InferenceError('冻结复现入口仅支持 CPU 输入。')
        if not isinstance(batch_size, int) or batch_size < 1:
            raise InferenceError('batch_size 必须是正整数。')
        views, arrays, timings, states = {}, {}, {}, {}
        started = time.perf_counter()
        for key, model in self.models.items():
            if any(m.training for m in model.modules()) or any(p.requires_grad for p in model.parameters()):
                raise InferenceError('推理模型必须保持 eval() 且 requires_grad=False。')
            before = state_sha256(model)
            for flip in (False, True):
                name = key + ('_flip' if flip else '_raw')
                logits, logp, timing = infer_view(model, images, batch_size, flip)
                arrays[name + '_logits'] = logits.numpy()
                arrays[name + '_log_probs'] = logp.numpy()
                views[name], timings[name] = logp, timing
            after = state_sha256(model)
            if before != after or any(p.grad is not None for p in model.parameters()):
                raise InferenceError('推理修改了模型状态或产生梯度：%s' % key)
            states[key] = {'before': before, 'after': after, 'unchanged': True,
                           'eval': True, 'requires_grad': False, 'parameter_gradients': False}
        _, _, logp = calculate(views)
        arrays['triple_tta_candidate_log_probs'] = logp.numpy()
        arrays['triple_tta_candidate_probabilities'] = logp.exp().numpy()
        return arrays, {'view_timings': timings, 'model_states': states,
                        'inference_seconds': time.perf_counter() - started,
                        'training_executed': False, 'private_test_used': False}

    def predict(self, images):
        arrays, audit = self.infer(images)
        results = []
        for scores in arrays['triple_tta_candidate_probabilities']:
            label = int(scores.argmax())
            results.append({'label': label, 'emotion': LABELS[label], 'emotion_zh': LABELS_ZH[label],
                            'probabilities': [{'label': i, 'emotion': name, 'emotion_zh': LABELS_ZH[i],
                                               'probability': float(scores[i])} for i, name in enumerate(LABELS)],
                            'probability_sum': float(scores.sum())})
        return {'predictions': results, 'models': self.info, 'labels': list(LABELS),
                'preprocessing': PREPROCESSING, 'model_weights': [1 / 3] * 3,
                'view_weights': [0.5, 0.5], 'audit': audit,
                'note': '概率未校准；输入应已裁剪为人脸。合成图仅用于检查流程。'}


def saved_results(root=ROOT):
    manifest = read_manifest(root)
    validation = manifest['validation']
    path = checked_file(root, validation['summary'], validation['summary_sha256'])
    metrics = json.loads(path.read_text(encoding='utf-8'))['results']['triple_tta_candidate']
    if metrics != validation['expected']:
        raise InferenceError('历史验证指标与冻结记录不一致。')
    return {'source': validation['summary'], 'source_sha256': validation['summary_sha256'],
            'split': 'PublicTest', 'metrics': metrics, 'validation_only': True,
            'note': '已保存的验证结果；本命令没有执行新的推理。PrivateTest 最终评估尚未进行。'}
