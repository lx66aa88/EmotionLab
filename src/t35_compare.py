"""Summarize completed, independently reloaded T3.5 runs without new selection data."""
import argparse
import csv
import json
import math
from pathlib import Path

import numpy as np

from src.t3_train import sha256
from src.train import write_json


def paired_comparison(baseline_file, candidate_file):
    old, new = np.load(baseline_file), np.load(candidate_file)
    if not np.array_equal(old['labels'], new['labels']):
        raise ValueError('Prediction ordering/labels mismatch')
    labels = old['labels']
    old_correct = old['logits'].argmax(1) == labels
    new_correct = new['logits'].argmax(1) == labels
    gains = int((~old_correct & new_correct).sum())
    losses = int((old_correct & ~new_correct).sum())
    n = len(labels)
    rng = np.random.default_rng(20261030)
    # Paired iid-image bootstrap via sufficient multinomial counts (+1,-1,0).
    samples = rng.multinomial(n, [gains/n, losses/n, 1-(gains+losses)/n], size=20000)
    delta = (samples[:, 0] - samples[:, 1]) / n
    discordant = gains + losses
    low = min(gains, losses)
    exact_p = min(1., 2 * sum(math.exp(math.lgamma(discordant + 1) - math.lgamma(k + 1)
                                      - math.lgamma(discordant-k+1) - discordant*math.log(2))
                                for k in range(low+1))) if discordant else 1.
    return {'new_correct_old_wrong': gains, 'old_correct_new_wrong': losses,
            'net_additional_correct': gains-losses, 'accuracy_delta': (gains-losses)/n,
            'paired_bootstrap_95pct': np.quantile(delta, [.025, .975]).tolist(),
            'mcnemar_exact_two_sided_p': exact_p, 'bootstrap_repeats': 20000,
            'caveat': 'Descriptive only: iid-image assumption; no correction for adaptive Public selection, duplicate images, or multiple comparisons.'}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output-dir', default='results/t35_final_20261030')
    a = p.parse_args()
    out = Path(a.output_dir)
    out.mkdir(exist_ok=True)
    baseline_npz = 'results/t35_diagnosis_20261030/best56_public_logits.npz'
    rows, checks, pairs = [], [], {}
    for old in ['t3_05_resnet_aug_mps_s42', 't3_06_unweighted_s42', 't3_08_unweighted_s43']:
        result = json.loads((Path('results')/old/'summary.json').read_text())
        val = result['best_validation']
        rows.append({'name':old, 'seed':42 if old != 't3_08_unweighted_s43' else 43,
                     'stream':'online', 'canonical':True, 'accuracy':val['accuracy'],
                     'macro_f1':val['macro_f1'], 'loss':val['loss'], 'best_local_epoch':result['best_epoch'],
                     'epochs_completed':result['epochs_completed'], 'elapsed_seconds':result['elapsed_seconds'],
                     'best_checkpoint':result['best_checkpoint']})
    for summary_path in sorted(Path('results').glob('t35_*/summary.json')):
        folder = summary_path.parent
        summary = json.loads(summary_path.read_text())
        metadata = json.loads((folder/'config.json').read_text())
        cfg = metadata['config']
        for source, digest in metadata['source_sha256'].items():
            assert sha256(folder/'source'/Path(source).name) == digest
        configs = [c for c in Path('configs/t35').glob('*.json')
                   if json.loads(c.read_text())['name'] == summary['name']]
        assert len(configs)==1 and sha256(configs[0])==metadata['config_sha256']
        assert sha256(cfg['initialize_from'])==metadata['parent_sha256']
        logs = [json.loads(s) for s in (folder/'metrics.jsonl').read_text().splitlines()]
        assert len(logs) == cfg['epochs'] == summary['epochs_completed']
        assert [v['local_epoch'] for v in logs] == list(range(1,len(logs)+1))
        assert all(v['train_samples'] == 28709 and all(m['samples']==3589 for m in v['validation'].values()) for v in logs)
        assert summary['private_test_used'] is False
        for kind, stream in summary['streams'].items():
            val = stream['best_validation']
            best = max(logs, key=lambda v:(v['validation'][kind]['accuracy'],-v['validation'][kind]['loss']))
            assert stream['best_local_epoch'] == best['local_epoch']
            assert val['confusion_matrix'] == best['validation'][kind]['confusion_matrix']
            assert math.isclose(val['macro_f1'],sum(c['f1'] for c in val['per_class'])/7,abs_tol=1e-12)
            assert sum(map(sum,val['confusion_matrix'])) == 3589
            assert sha256(stream['best_checkpoint']) == stream['checkpoint_sha256']
            canonical = kind == summary['canonical_stream']
            row = {'name':summary['name'],'seed':cfg['seed'],'stream':kind,'canonical':canonical,
                   'accuracy':val['accuracy'],'macro_f1':val['macro_f1'],'loss':val['loss'],
                   'best_local_epoch':stream['best_local_epoch'],'epochs_completed':summary['epochs_completed'],
                   'elapsed_seconds':summary['elapsed_seconds'],'best_checkpoint':stream['best_checkpoint']}
            rows.append(row)
            if canonical:
                independent = out/(summary['name']+'_mps.json')
                cpueval = json.loads(independent.read_text())
                assert cpueval['confusion_matrix'] == val['confusion_matrix']
                assert math.isclose(cpueval['loss'],val['loss'],rel_tol=1e-6,abs_tol=1e-7)
                pairs[summary['name']] = paired_comparison(baseline_npz, str(independent)+'.npz')
            checks.append({'name':summary['name'],'stream':kind,'passed':True})
    with (out/'comparison.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    write_json(out/'comparison.json',rows)
    write_json(out/'paired_comparisons.json',pairs)
    write_json(out/'artifact_checks.json',checks)
    protected=json.loads(Path('results/t35_diagnosis_20261030/original_hashes.json').read_text())
    integrity={path:sha256(path)==digest for path,digest in protected.items()}
    write_json(out/'original_integrity_before_status.json',integrity)
    assert all(integrity.values()),'Original artifacts changed'
    print(json.dumps({'rows':rows,'paired':pairs,'protected_files':len(integrity)},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
