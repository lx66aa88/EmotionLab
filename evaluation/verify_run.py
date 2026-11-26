"""Audit completed T3 artifacts without reopening any dataset split."""
import argparse
import csv
import json
import math
from pathlib import Path
from training.cnn_experiment import sha256
from training.baseline import write_json


def verify(name):
    run = Path('results') / name
    meta = json.loads((run / 'config.json').read_text())
    summary = json.loads((run / 'summary.json').read_text())
    rows = list(csv.DictReader((run / 'metrics.csv').open()))
    assert len(rows) == summary['epochs_completed']
    assert summary['reload_verified'] and not summary['private_test_used']
    assert all(int(r['train_samples']) == 28709 and int(r['val_samples']) == 3589 for r in rows)
    assert [int(r['epoch']) for r in rows] == list(range(meta['config'].get('start_epoch', 0) + 1,
                                                       summary['last_epoch'] + 1))
    assert sha256(summary['best_checkpoint']) == summary['checkpoint_sha256']
    assert all(sha256(run / 'source' / Path(p).name) == h for p, h in meta['source_sha256'].items())
    candidates = [(float(r['val_accuracy']), -float(r['val_loss']), int(r['epoch'])) for r in rows]
    if meta['config'].get('initialize_from') and meta['config'].get('include_initial_candidate', True):
        initial = json.loads((run / 'initial_validation.json').read_text())
        candidates.append((initial['accuracy'], -initial['loss'], meta['config']['start_epoch']))
    winner = max(candidates, key=lambda v: (v[0], v[1], -v[2]))
    selected = summary['best_validation']
    assert winner[2] == summary['best_epoch']
    assert winner[0] == selected['accuracy'] and math.isclose(-winner[1], selected['loss'], abs_tol=1e-7)
    cm = selected['confusion_matrix']
    assert sum(map(sum, cm)) == 3589
    assert sum(cm[i][i] for i in range(7)) == selected['correct']
    assert math.isclose(sum(c['f1'] for c in selected['per_class']) / 7, selected['macro_f1'])
    return {'experiment': name, 'passed': True, 'logged_epochs': len(rows),
            'checkpoint_hash_verified': True, 'source_snapshots_verified': True,
            'selection_rule_verified': True, 'samples_verified': True}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', required=True)
    p.add_argument('runs', nargs='+')
    a = p.parse_args()
    result = {'experiments': [verify(name) for name in a.runs], 'private_test_used': False}
    write_json(a.output, result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
