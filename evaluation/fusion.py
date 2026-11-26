"""T3.8 inference and probability arithmetic, extracted without numerical changes.

Sources and exact function comparisons: T4.3 integration_diff.json.
No study entry points, training imports, or resource/controller dependencies.
"""
import csv
import hashlib
import math
from pathlib import Path
import time
import numpy as np
import torch

def validate_images(x):
    if x.dtype != torch.float32 or x.ndim != 4 or tuple(x.shape[1:]) != (1, 48, 48) or len(x) == 0:
        raise ValueError('Expected nonempty float32 N,1,48,48')
    if not torch.isfinite(x).all() or x.min() < 0 or x.max() > 1:
        raise ValueError('Images must be finite in [0,1]')


def horizontal_flip(x):
    validate_images(x)
    flipped = x.flip(-1).contiguous()
    if flipped.shape != x.shape:
        raise AssertionError('Flip changed input shape')
    return flipped


def validate_log_probs(logp):
    if logp.ndim != 2 or logp.shape[1] != 7 or not torch.isfinite(logp).all():
        raise ValueError('Expected finite N,7 log probabilities')
    if not torch.allclose(logp.logsumexp(1), torch.zeros(len(logp), dtype=logp.dtype), atol=1e-10, rtol=0):
        raise ValueError('Probabilities must sum to one')


def equal_probability_mean(*log_probs):
    if len(log_probs) != 2 or log_probs[0].shape != log_probs[1].shape:
        raise ValueError('Exactly two aligned probability arrays are required')
    for p in log_probs:
        validate_log_probs(p)
    # log((softmax(z1)+softmax(z2))/2), NOT softmax((z1+z2)/2).
    result = torch.logsumexp(torch.stack(log_probs), dim=0) - math.log(2)
    validate_log_probs(result)
    return result


def state_sha256(model):
    digest = hashlib.sha256()
    for name, value in model.state_dict().items():
        digest.update(name.encode())
        digest.update(value.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def infer_view(model, images, batch_size=16, flip=False):
    validate_images(images)
    if batch_size < 1:
        raise ValueError('Positive batch size required')
    model.eval()
    original_state = state_sha256(model)
    logits_all, times, shapes = [], [], set()
    with torch.inference_mode():
        for start in range(0, len(images), batch_size):
            x = images[start:start + batch_size]
            begin = time.perf_counter()
            transformed = horizontal_flip(x) if flip else x
            if transformed.shape != x.shape:
                raise AssertionError('Invalid transformed shape')
            logits = model(transformed)
            if logits.shape != (len(x), 7) or not torch.isfinite(logits).all():
                raise ValueError('Model must output finite N,7 logits')
            logp = logits.double().log_softmax(1)
            times.append(time.perf_counter() - begin)
            shapes.add(tuple(transformed.shape))
            logits_all.append((logits.cpu(), logp.cpu()))
    if state_sha256(model) != original_state:
        raise RuntimeError('Inference changed weights or BN buffers')
    return (torch.cat([z[0] for z in logits_all]), torch.cat([z[1] for z in logits_all]),
            {'inference_seconds': sum(times), 'batch_seconds': times,
             'observed_shapes': sorted(shapes), 'samples': len(images),
             'state_unchanged': True, 'grad_enabled_inside': False})


def load_public(csv_path, split='PublicTest', limit=None):
    # Reject before opening the file. Never parse Training/Private pixels/labels.
    if split != 'PublicTest':
        raise ValueError('Only PublicTest inference is permitted')
    if limit is not None and limit < 1:
        raise ValueError('Positive limit required')
    images, labels, lines, groups = [], [], [], []
    group_map = {}
    with Path(csv_path).open(newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        if not {'emotion', 'Usage', 'pixels'}.issubset(reader.fieldnames or []):
            raise ValueError('Missing dataset fields')
        for line_number, row in enumerate(reader, 2):
            if row['Usage'] != split:
                continue
            label = int(row['emotion'])
            pixels = [int(v) for v in row['pixels'].split()]
            if label not in range(7) or len(pixels) != 2304 or min(pixels) < 0 or max(pixels) > 255:
                raise ValueError('Invalid PublicTest record at CSV line %d' % line_number)
            raw = np.asarray(pixels, dtype=np.uint8)
            key = raw.tobytes()
            if key not in group_map:
                group_map[key] = len(group_map)
            groups.append(group_map[key])
            images.append(raw.reshape(1, 48, 48))
            labels.append(label)
            lines.append(line_number)
            if limit is not None and len(labels) == limit:
                break
    if not labels or (limit is not None and len(labels) != limit):
        raise ValueError('Not enough PublicTest rows')
    x = torch.from_numpy(np.stack(images)).float().div_(255)
    validate_images(x)
    return x, torch.tensor(labels), np.arange(len(labels)), np.asarray(lines), np.asarray(groups)


def equal_three_model_mean(*logps):
    if len(logps) != 3 or any(x.shape != logps[0].shape for x in logps):
        raise ValueError('Exactly three aligned model probability arrays required')
    for p in logps:
        validate_log_probs(p)
    mean = torch.logsumexp(torch.stack(logps), dim=0) - math.log(3)
    validate_log_probs(mean)
    return mean


def calculate(views):
    tta = {key: equal_probability_mean(views[key+'_raw'], views[key+'_flip'])
           for key in ('w32', 't3', 'w16')}
    baseline = equal_probability_mean(tta['w32'], tta['t3'])
    candidate = equal_three_model_mean(tta['w32'], tta['t3'], tta['w16'])
    return tta, baseline, candidate


