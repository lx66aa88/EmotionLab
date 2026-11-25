"""Last fixed candidate: three model TTA probabilities, each model weight 1/3."""
import argparse
import csv
import datetime
import importlib.util
import json
import math
import os
from pathlib import Path
import time
import numpy as np
import torch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location('double_study', ROOT/'results/t38_double_tta_20261104/study.py')
double = importlib.util.module_from_spec(spec)
spec.loader.exec_module(double)
old = double.old
from inference import validate_log_probs


def equal_three_model_mean(*logps):
    if len(logps) != 3 or any(x.shape != logps[0].shape for x in logps):
        raise ValueError('Exactly three aligned model probability arrays required')
    for p in logps:
        validate_log_probs(p)
    mean = torch.logsumexp(torch.stack(logps), dim=0) - math.log(3)
    validate_log_probs(mean)
    return mean


def calculate(views):
    tta = {key: old.equal_probability_mean(views[key+'_raw'], views[key+'_flip'])
           for key in ('w32', 't3', 'w16')}
    baseline = old.equal_probability_mean(tta['w32'], tta['t3'])
    candidate = equal_three_model_mean(tta['w32'], tta['t3'], tta['w16'])
    return tta, baseline, candidate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--compare-to')
    args = parser.parse_args()
    out = Path(args.output)
    out.mkdir(exist_ok=False)
    start = time.perf_counter()
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    config = json.loads((HERE/'protocol.json').read_text())
    protected = json.loads((HERE/'protected_before.json').read_text())
    assert all(old.sha256(ROOT/k) == v for k, v in protected.items())
    assert config['model_weights'] == [1/3]*3 and config['view_weights'] == [.5, .5]
    old.write(out/'protocol.json', config)
    data_started = time.perf_counter()
    images, labels, ids, lines, groups = old.load_public(ROOT/config['csv_path'])
    data_seconds = time.perf_counter() - data_started
    assert len(labels) == 3589
    arrays = {'labels': labels.numpy(), 'sample_ids': ids, 'csv_lines': lines, 'pixel_groups': groups}
    views, costs, models, loading = {}, {}, [], {}
    for m in config['models']:
        path = ROOT/m['checkpoint']
        assert old.sha256(path) == m['sha256']
        load_start = time.perf_counter()
        model, cp = (old.load37 if m['format_version'] == 37 else old.load_t3)(path)
        loading[m['key']] = time.perf_counter()-load_start
        assert cp['format_version'] == m['format_version'] and cp['epoch'] == m['epoch']
        assert tuple(cp['labels']) == old.LABELS == tuple(config['labels'])
        assert cp['preprocessing'] == config['preprocessing'] and cp['data_sha256'] == config['data_sha256']
        assert all(torch.isfinite(v).all() for v in model.state_dict().values())
        model.eval().requires_grad_(False)
        before = old.state_sha256(model)
        for flip in (False, True):
            name = m['key']+('_flip' if flip else '_raw')
            print('start', name, flush=True)
            logits, logp, timing = old.infer_view(model, images, 128, flip)
            views[name] = logp
            arrays[name+'_logits'], arrays[name+'_log_probs'] = logits.numpy(), logp.numpy()
            costs[name] = timing
            print('done', name, timing['inference_seconds'], flush=True)
        assert old.state_sha256(model) == before and old.sha256(path) == m['sha256']
        # Verify original-image behavior against the exact historical checkpoint record.
        raw = old.score(views[m['key']+'_raw'], labels)
        assert raw['confusion_matrix'] == m['historical_validation']['confusion_matrix']
        assert abs(raw['cross_entropy']-m['historical_validation']['loss']) < 1e-5
        models.append({**m, 'state_before': before, 'state_after': old.state_sha256(model),
                       'weight_and_state_unchanged': True, 'raw_reproduces_historical': True,
                       'observed_labels': cp['labels'], 'observed_preprocessing': cp['preprocessing']})
        del model, cp
    mix_start = time.perf_counter()
    tta, baseline, candidate = calculate(views)
    mix_seconds = time.perf_counter()-mix_start
    logps = {'double_tta_baseline': baseline, 'triple_tta_candidate': candidate,
             **{key+'_tta_diagnostic': p for key,p in tta.items()}}
    results = {key: old.score(p, labels) for key,p in logps.items()}
    # Compare to the existing 72.053497% experiment, not a different data subset.
    with np.load(ROOT/'results/t38_double_tta_20261104/run01/predictions.npz') as previous:
        for key in ('labels', 'sample_ids', 'csv_lines', 'pixel_groups'):
            assert np.array_equal(previous[key], arrays[key]), 'Historical sample alignment mismatch: '+key
        for key in ('w32_raw', 'w32_flip', 't3_raw', 't3_flip'):
            assert np.array_equal(previous[key+'_logits'], arrays[key+'_logits']), 'Historical logits mismatch'
        assert np.array_equal(previous['double_tta_ensemble_log_probs'], baseline.numpy())
    assert results['double_tta_baseline']['correct'] == 2586
    previous_result = json.loads((ROOT/'results/t38_double_tta_20261104/run01/summary.json').read_text())
    assert results['double_tta_baseline'] == previous_result['results']['double_tta_ensemble']
    for key, logp in logps.items():
        arrays[key+'_probabilities'], arrays[key+'_log_probs'] = logp.exp().numpy(), logp.numpy()
    changes = old.paired_changes(baseline, candidate, labels)
    stats = double.grouped_bootstrap(baseline, candidate, labels, groups, 20000, 381105)
    reload_check = None
    if args.compare_to:
        prev = Path(args.compare_to)
        with np.load(prev/'predictions.npz') as p:
            assert set(p.files) == set(arrays)
            assert all(np.array_equal(p[k],v) for k,v in arrays.items()), 'Independent prediction mismatch'
        prev_summary = json.loads((prev/'summary.json').read_text())
        assert results == prev_summary['results'] and changes == prev_summary['paired_changes']
        assert stats == prev_summary['paired_group_bootstrap']
        reload_check = {'all_arrays_bitwise_equal': True, 'all_metrics_identical': True,
                        'previous_run': str(prev)}
    with (out/'predictions.npz').open('xb') as f:
        np.savez_compressed(f, **arrays)
    bpred, cpred = baseline.argmax(1), candidate.argmax(1)
    records = [{'public_index': int(ids[i]), 'csv_line': int(lines[i]), 'label': int(labels[i]),
                'baseline_prediction': int(bpred[i]), 'candidate_prediction': int(cpred[i]),
                'changed': bool(bpred[i] != cpred[i])} for i in range(len(labels))]
    for name, subset in [('predictions.csv',records),('changes.csv',[r for r in records if r['changed']])]:
        with (out/name).open('x',newline='') as f:
            writer = csv.DictWriter(f,fieldnames=list(records[0]))
            writer.writeheader(); writer.writerows(subset)
    after = {key: old.sha256(ROOT/key) for key in protected}
    assert protected == after, 'Protected artifacts changed'
    old.write(out/'protected_after.json', after)
    durations = {k:v['inference_seconds'] for k,v in costs.items()}
    baseline_seconds = sum(durations[k] for k in ['w32_raw','w32_flip','t3_raw','t3_flip'])
    gain = results['triple_tta_candidate']['correct']-2586
    summary = {'checked_at': datetime.datetime.now().astimezone().isoformat(),
               'samples': len(labels), 'models': models, 'results': results,
               'paired_changes': changes, 'paired_group_bootstrap': stats,
               'view_timings': costs, 'probability_mixing_seconds': mix_seconds,
               'method_forward_component_seconds': {'double_tta_baseline': baseline_seconds,
                                                     'triple_tta_candidate': sum(durations.values())+mix_seconds},
               'data_loading_seconds': data_seconds, 'model_loading_seconds': loading,
               'wall_seconds': time.perf_counter()-start, 'threads': torch.get_num_threads(),
               'process_niceness': os.getpriority(os.PRIO_PROCESS,0), 'device': 'cpu',
               'independent_reload': reload_check, 'net_correct_gain': gain,
               'reaches_73': results['triple_tta_candidate']['correct'] >= 2620,
               'remaining_correct_to_73': max(0,2620-results['triple_tta_candidate']['correct']),
               'recommended_validation_candidate': 'triple_tta_candidate' if gain>0 else 'double_tta_baseline',
               'protected_files_unchanged': True, 'private_test_used': False, 'training_executed': False,
               'source_sha256': old.sha256(__file__), 'protocol_sha256': old.sha256(HERE/'protocol.json'),
               'caveat': 'Public repeatedly selected; single fixed new candidate does not remove past selection bias. Independent reload is reproducibility, not independent test performance.'}
    old.write(out/'summary.json', summary)
    print(json.dumps({'results':results,'paired_changes':changes,'reload':reload_check}),flush=True)


if __name__=='__main__':
    main()
