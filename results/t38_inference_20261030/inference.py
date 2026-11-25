"""Fixed CPU-only PublicTest inference. No training or T3.7 mutation.

TTA and model fusion average probabilities, implemented in log space using
logsumexp for numerical stability. CrossEntropy = mean(-log p_true).
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time

import numpy as np
import torch

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT))
from src.dataset import LABELS
from src.t3_models import load_t3
from src.t3_train import metrics_from_cm, sha256
from resource_check import require_safe_snapshot

PREPROCESSING = 'float32 / 255; [N,1,48,48]'
METHODS = ('baseline_raw', 'baseline_flip_tta', 'ensemble_raw_equal')


def write_json(path, data):
    with Path(path).open('x', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, allow_nan=False)


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


def score(logp, labels):
    validate_log_probs(logp)
    if labels.shape != (len(logp),) or labels.dtype != torch.int64 or not ((labels >= 0) & (labels < 7)).all():
        raise ValueError('Invalid aligned seven-class labels')
    cm = torch.bincount(labels * 7 + logp.argmax(1), minlength=49).reshape(7, 7)
    return {**metrics_from_cm(cm), 'cross_entropy': -logp[torch.arange(len(labels)), labels].mean().item()}


def paired_changes(base, candidate, labels):
    a, b = base.argmax(1), candidate.argmax(1)
    corrected = int(((a != labels) & (b == labels)).sum())
    damaged = int(((a == labels) & (b != labels)).sum())
    return {'changed': int((a != b).sum()), 'corrected': corrected, 'damaged': damaged,
            'changed_but_both_wrong': int(((a != b) & (a != labels) & (b != labels)).sum()),
            'net_correct_gain': corrected - damaged}


def grouped_bootstrap(base, other, labels, groups, repeats=20000, seed=3801):
    delta = ((other.argmax(1) == labels).long() - (base.argmax(1) == labels).long()).numpy()
    sums, counts = np.bincount(groups, weights=delta), np.bincount(groups)
    rng = np.random.default_rng(seed)
    samples = np.empty(repeats)
    for i in range(repeats):
        idx = rng.integers(0, len(counts), size=len(counts))
        samples[i] = sums[idx].sum() / counts[idx].sum()
    return {'delta_accuracy_95pct': np.quantile(samples, [.025, .975]).tolist(),
            'pixel_groups': len(counts), 'repeats': repeats, 'seed': seed,
            'caveat': 'Descriptive PublicTest uncertainty; does not remove adaptive selection or train/public dependence.'}


def load_checked_model(spec, manifest, project):
    path = project / spec['checkpoint']
    if sha256(path) != spec['sha256']:
        raise ValueError('Checkpoint SHA-256 mismatch')
    model, cp = load_t3(path)
    if (tuple(cp['labels']) != tuple(manifest['labels']) or cp['preprocessing'] != manifest['preprocessing']
            or cp['data_sha256'] != manifest['data_sha256']
            or cp.get('weight_kind', 'online') != spec['weight_kind']):
        raise ValueError('Model/data/labels/preprocessing/stream contract mismatch')
    if not all(torch.isfinite(v).all() for v in model.state_dict().values()):
        raise ValueError('Nonfinite checkpoint tensor')
    model.requires_grad_(False)
    return model.eval(), cp


def compare_saved_runs(old_dir, arrays, results):
    old_dir = Path(old_dir)
    old_summary = json.loads((old_dir / 'summary.json').read_text())
    with np.load(old_dir / 'predictions.npz') as previous:
        if set(previous.files) != set(arrays):
            raise ValueError('Independent run output fields differ')
        for k, v in arrays.items():
            same = (np.allclose(previous[k], v, rtol=0, atol=1e-10)
                    if np.issubdtype(v.dtype, np.floating) else np.array_equal(previous[k], v))
            if not same:
                raise ValueError('Independent reload mismatch: ' + k)
    for name in results:
        old = old_summary['results'][name]
        new = results[name]
        if old['confusion_matrix'] != new['confusion_matrix'] or abs(old['cross_entropy'] - new['cross_entropy']) > 1e-10:
            raise ValueError('Independent metric mismatch')
    return {'matched': True, 'compared_to': str(old_dir.resolve()),
            'all_samples_logits_probabilities_and_metrics_checked': True, 'absolute_tolerance': 1e-10}


def run(manifest_path, output, mode='smoke', resource_snapshot=None, compare_to=None, project=PROJECT):
    started = time.perf_counter()
    manifest_path, output = Path(manifest_path), Path(output)
    m = json.loads(manifest_path.read_text())
    if (m['split'] != 'PublicTest' or tuple(m['labels']) != LABELS or m['preprocessing'] != PREPROCESSING
            or m['methods'] != list(METHODS) or len(m['models']) != 2 or m['threads'] != 1
            or m['device'] != 'cpu' or mode not in ('smoke', 'full')):
        raise ValueError('Unsupported protocol; fixed CPU PublicTest study only')
    if mode == 'full':
        if not resource_snapshot:
            raise RuntimeError('Full inference needs a fresh safe resource check')
        resources = require_safe_snapshot(resource_snapshot)
    else:
        resources = json.loads(Path(resource_snapshot).read_text()) if resource_snapshot else None
    # Never overwrite a complete, failed or partial run.
    output.mkdir(parents=False, exist_ok=False)
    write_json(output / 'manifest.json', m)
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    csv_path = project / m['csv_path']
    if sha256(csv_path) != m['data_sha256']:
        raise ValueError('Original CSV checksum mismatch')
    begin = time.perf_counter()
    images, labels, ids, lines, groups = load_public(csv_path, limit=m['smoke_samples'] if mode == 'smoke' else None)
    load_seconds = time.perf_counter() - begin
    if mode == 'full' and len(labels) != m['expected_samples']:
        raise ValueError('Full evaluation must contain all 3589 samples')
    views, view_cost, model_meta, load_cost, warmup_cost, single_cost = {}, {}, [], {}, {}, {}
    for index, spec in enumerate(m['models']):
        begin = time.perf_counter()
        model, cp = load_checked_model(spec, m, project)
        load_cost[spec['name']] = time.perf_counter() - begin
        prefix = 'baseline' if index == 0 else 'aux'
        begin = time.perf_counter()
        with torch.inference_mode():
            model(torch.zeros(min(m['batch_size'], len(images)), 1, 48, 48))
        warmup_cost[prefix] = time.perf_counter() - begin
        for flipped in ([False, True] if index == 0 else [False]):
            key = prefix + ('_flip' if flipped else '_raw')
            logits, logp, timing = infer_view(model, images, m['batch_size'], flip=flipped)
            views[key] = (logits, logp)
            view_cost[key] = timing
            # A single observed end-to-end forward latency under current load.
            _, _, single = infer_view(model, images[:1], 1, flip=flipped)
            single_cost[key] = single['inference_seconds']
        model_meta.append({**spec, 'epoch': cp['epoch'], 'weight_kind_observed': cp.get('weight_kind', 'online'),
                           'checkpoint_validation': cp['validation'], 'preprocessing': cp['preprocessing'],
                           'labels': cp['labels'], 'state_sha256_after_inference': state_sha256(model),
                           'no_parameter_or_buffer_updates': True,
                           'checkpoint_hash_unchanged': sha256(project / spec['checkpoint']) == spec['sha256']})
        del model, cp
    base, flip, aux = [views[k][1] for k in ['baseline_raw', 'baseline_flip', 'aux_raw']]
    t = time.perf_counter()
    tta = equal_probability_mean(base, flip)
    tta_mix_seconds = time.perf_counter() - t
    t = time.perf_counter()
    ensemble = equal_probability_mean(base, aux)
    ensemble_mix_seconds = time.perf_counter() - t
    logps = {'baseline_raw': base, 'baseline_flip_tta': tta, 'ensemble_raw_equal': ensemble,
             'auxiliary_raw_diagnostic': aux}
    results = {name: score(logp, labels) for name, logp in logps.items()}
    raw_seconds = view_cost['baseline_raw']['inference_seconds']
    costs = {
        'baseline_raw': (raw_seconds, 1, single_cost['baseline_raw']),
        'baseline_flip_tta': (raw_seconds + view_cost['baseline_flip']['inference_seconds'] + tta_mix_seconds,
                              2, single_cost['baseline_raw'] + single_cost['baseline_flip']),
        'ensemble_raw_equal': (raw_seconds + view_cost['aux_raw']['inference_seconds'] + ensemble_mix_seconds,
                               2, single_cost['baseline_raw'] + single_cost['aux_raw']),
        'auxiliary_raw_diagnostic': (view_cost['aux_raw']['inference_seconds'], 1, single_cost['aux_raw']),
    }
    for name, (seconds, forwards, latency) in costs.items():
        results[name]['cost'] = {'cached_component_inference_seconds': seconds,
            'seconds_per_image_at_batch16': seconds / len(labels), 'image_forwards': len(labels) * forwards,
            'forward_multiplier': forwards, 'single_image_forward_components_seconds': latency,
            'note': 'CPU1, one observation under contention; process niceness recorded in summary; loading/warmup separate; single-image sum excludes probability-mix overhead.'}
    changes = {name: paired_changes(base, logps[name], labels) for name in METHODS[1:]}
    full_baseline_matches = None
    statistical = {}
    if mode == 'full':
        full_baseline_matches = (results['baseline_raw']['correct'] == 2453
                                 and abs(results['baseline_raw']['macro_f1'] - m['models'][0]['historical_macro_f1']) < 1e-12)
        if not full_baseline_matches:
            raise RuntimeError('Full original-image baseline does not reproduce formal model')
        statistical = {name: grouped_bootstrap(base, logps[name], labels, groups,
                       m['adoption_rule']['bootstrap_repeats'], m['adoption_rule']['bootstrap_seed']) for name in METHODS[1:]}
    arrays = {'sample_ids': ids, 'csv_lines': lines, 'pixel_group_ids': groups, 'labels': labels.numpy()}
    for name, logp in logps.items():
        arrays[name + '_log_probs'] = logp.numpy()
        arrays[name + '_probabilities'] = logp.exp().numpy()
    for name, (logits, _) in views.items():
        arrays[name + '_logits'] = logits.numpy()
    reload_check = compare_saved_runs(compare_to, arrays, results) if compare_to else {'matched': None, 'reason': 'No independent comparison requested'}
    with (output / 'predictions.npz').open('xb') as f:
        np.savez_compressed(f, **arrays)
    rows = []
    for i in range(len(labels)):
        preds = [int(logps[k][i].argmax()) for k in METHODS]
        rows.append({'sample_id': int(ids[i]), 'csv_line': int(lines[i]), 'true_label': int(labels[i]),
                     **dict(zip(METHODS, preds)), 'tta_changed': preds[0] != preds[1],
                     'ensemble_changed': preds[0] != preds[2]})
    for filename, subset in [('predictions.csv', rows), ('changes.csv', [r for r in rows if r['tta_changed'] or r['ensemble_changed']])]:
        with (output / filename).open('x', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(subset)
    adoption = {}
    rule = m['adoption_rule']
    for name in METHODS[1:]:
        a, b = results['baseline_raw'], results[name]
        criteria = {'full_dataset': mode == 'full', 'baseline_reproduced': full_baseline_matches is True,
            'independent_reload': reload_check['matched'] is True,
            'accuracy_gain': b['accuracy'] - a['accuracy'] >= rule['minimum_accuracy_gain_pp'] / 100,
            'macro_f1_guard': b['macro_f1'] - a['macro_f1'] >= -rule['maximum_macro_f1_drop_pp'] / 100,
            'all_class_recall_guard': all(y['recall'] - x['recall'] >= -rule['maximum_any_class_recall_drop_pp'] / 100
                                       for x, y in zip(a['per_class'], b['per_class'])),
            'latency_guard': b['cost']['single_image_forward_components_seconds'] <= rule['maximum_single_image_inference_seconds'],
            'paired_interval_guard': name in statistical and statistical[name]['delta_accuracy_95pct'][0] > 0}
        adoption[name] = {'criteria': criteria, 'adopt': all(criteria.values()),
                          'decision_status': 'pending_full_evaluation' if mode == 'smoke' else ('adopt' if all(criteria.values()) else 'not_all_criteria_met')}
    summary = {'protocol_version': m['protocol_version'], 'mode': mode, 'full_public_evaluation': mode == 'full',
        'observed_at_utc': datetime.now(timezone.utc).isoformat(), 'samples': len(labels), 'split': 'PublicTest',
        'sample_selection': m['smoke_selection'] if mode == 'smoke' else 'All PublicTest rows, original CSV order',
        'manifest_sha256': sha256(manifest_path), 'source_sha256': sha256(__file__),
        'data_sha256': m['data_sha256'], 'models': model_meta, 'resources': resources,
        'torch_version': str(torch.__version__), 'device': 'cpu', 'threads': torch.get_num_threads(),
        'process_niceness': os.getpriority(os.PRIO_PROCESS, 0),
        'gradients_or_training_executed': False, 'private_test_used': False,
        'results': results, 'prediction_changes': changes, 'paired_group_statistics': statistical,
        'independent_reload': reload_check, 'adoption': adoption,
        'data_loading_seconds': load_seconds, 'model_loading_seconds': load_cost, 'warmup_seconds': warmup_cost,
        'view_costs': view_cost, 'study_wall_seconds': time.perf_counter() - started,
        'timing_caveat': 'Components cached once for fairness; costs for different methods share raw inference and cannot be summed as independent runs.',
        'target_73_reached': (max(results[k]['accuracy'] for k in METHODS) >= .73) if mode == 'full' else None,
        'comparison_caveat': 'Smoke subset is not comparable to 68.347729% full PublicTest and cannot establish generalization or adoption.' if mode == 'smoke' else 'Same full official PublicTest and baseline; validation reused for selection, not an independent test.'}
    write_json(output / 'summary.json', summary)
    print(json.dumps({'mode': mode, 'samples': len(labels), 'results': {k: {q: v[q] for q in ['accuracy', 'macro_f1', 'cross_entropy']} for k, v in results.items()}}, ensure_ascii=False))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', default=str(Path(__file__).with_name('manifest.json')))
    parser.add_argument('--output', required=True)
    parser.add_argument('--mode', choices=['smoke', 'full'], default='smoke')
    parser.add_argument('--resource-snapshot')
    parser.add_argument('--compare-to')
    args = parser.parse_args()
    # Errors are kept in the caller's exclusive console log. A refused existing
    # output directory is never changed, even to add an error file.
    run(args.manifest, args.output, args.mode, args.resource_snapshot, args.compare_to)


if __name__ == '__main__':
    main()
