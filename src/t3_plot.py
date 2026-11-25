"""Plot only recorded T3 results with matplotlib; no training/data access."""
import argparse
import csv
import json
from pathlib import Path


def main():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('runs', nargs='+')
    a = parser.parse_args()
    out = Path(a.output)
    out.mkdir(parents=True, exist_ok=False)
    base = json.loads(Path('results/t3_audit_20261030/t2_public_metrics.json').read_text())
    baseline_rows = list(csv.DictReader(Path('results/t2_baseline_20261030/metrics.csv').open()))
    records = [{'name': 'T2 baseline', 'epoch': 15, 'accuracy': base['accuracy'],
                'macro_f1': base['macro_f1'], 'loss': base['loss'], 'seconds': 316.625552375,
                'parameters': 319239, 'metrics': base}]
    fig, axes = plt.subplots(len(a.runs), 3, figsize=(15, 3.2 * len(a.runs)), squeeze=False)
    for i, run_name in enumerate(a.runs):
        run = Path('results') / run_name
        cfg = json.loads((run / 'config.json').read_text())
        result = json.loads((run / 'summary.json').read_text())
        best = result['best_validation']
        rows = list(csv.DictReader((run / 'metrics.csv').open()))
        if cfg['config'].get('initialize_from') == 'checkpoints/t2_baseline_20261030/best.pt':
            rows = baseline_rows + rows
        x = [int(r['epoch']) for r in rows]
        for j, metric in enumerate(['loss', 'accuracy']):
            for split in ['train', 'val']:
                y = [float(r[f'{split}_{metric}']) for r in rows]
                axes[i, j].plot(x, y, label=split)
            axes[i, j].axvline(result['best_epoch'], color='gray', ls=':', lw=1)
            if cfg['config'].get('initialize_from') == 'checkpoints/t2_baseline_20261030/best.pt':
                axes[i, j].axvline(15.5, color='black', ls='--', lw=.8,
                                   label='Weights-only fine-tuning starts')
            axes[i, j].set(title=f'{run_name}: {metric}', xlabel='Epoch')
            axes[i, j].legend()
            axes[i, j].grid(alpha=.2)
        lr = [float(r['learning_rate']) for r in rows]
        axes[i, 2].plot(x, lr)
        axes[i, 2].set(title='Learning rate', xlabel='Epoch', yscale='log')
        records.append({'name': run_name, 'epoch': result['best_epoch'],
                        **{k: best[k] for k in ['accuracy', 'macro_f1', 'loss']},
                        'seconds': result['elapsed_seconds'], 'parameters': cfg['parameters'],
                        'metrics': best})
    fig.tight_layout()
    fig.savefig(out / 'learning_curves.png', dpi=150)
    plt.close(fig)
    winner = max(records, key=lambda r: (r['accuracy'], -r['loss']))
    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    labels = [r['name'] for r in base['per_class']]
    for ax, rec in zip(axes, [records[0], winner]):
        cm = np.array(rec['metrics']['confusion_matrix'])
        norm = cm / cm.sum(1, keepdims=True)
        ax.imshow(norm, vmin=0, vmax=1, cmap='Blues')
        for row in range(7):
            for col in range(7):
                ax.text(col, row, f'{cm[row,col]}\n{norm[row,col]:.0%}', ha='center', va='center',
                        color='white' if norm[row,col] > .5 else 'black', fontsize=8)
        ax.set(xticks=range(7), yticks=range(7), xticklabels=labels, yticklabels=labels,
               xlabel='Predicted label', ylabel='True label', title=rec['name'])
        ax.tick_params(axis='x', rotation=40)
    fig.tight_layout()
    fig.savefig(out / 'confusion_comparison.png', dpi=170)
    plt.close(fig)
    with (out / 'comparison.csv').open('x', newline='') as f:
        fields = ['name', 'epoch', 'accuracy', 'macro_f1', 'loss', 'seconds', 'parameters']
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows({k: r[k] for k in fields} for r in records)
    with (out / 'per_class.csv').open('x', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['experiment', 'label', 'name', 'support', 'precision', 'recall', 'f1'])
        writer.writeheader()
        for rec in records:
            writer.writerows({'experiment': rec['name'], **r} for r in rec['metrics']['per_class'])
    with (out / 'comparison.json').open('x') as f:
        json.dump({'records': records, 'selected': winner['name'],
                   'improvement_percentage_points': (winner['accuracy'] - base['accuracy']) * 100}, f, indent=2)


if __name__ == '__main__':
    main()
