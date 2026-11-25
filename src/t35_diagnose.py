"""T3.5 read-only model/data audit. Never load PrivateTest pixels or labels."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import shutil

import numpy as np
import torch
from torch.nn import functional as F
from torch.utils.data import DataLoader

from src.dataset import EmotionDataset
from src.predict import preprocess_pixels
from src.t3_models import load_t3
from src.t3_train import load_split, metrics_from_cm, sha256
from src.train import select_device, write_json


def collect(model, data, device, output=None):
    model.eval()
    logits, labels = [], []
    with torch.inference_mode():
        for x, y in DataLoader(data, batch_size=256, shuffle=False):
            logits.append(model(x.to(device)).cpu())
            labels.append(y)
    logits, labels = torch.cat(logits), torch.cat(labels)
    p = logits.softmax(1)
    confidence, pred = p.max(1)
    correct = pred == labels
    cm = torch.bincount(labels * 7 + pred, minlength=49).reshape(7, 7)
    ece = 0.
    for i in range(10):
        mask = (confidence > i / 10) & (confidence <= (i + 1) / 10)
        if mask.any():
            ece += mask.float().mean().item() * abs(
                confidence[mask].mean().item() - correct[mask].float().mean().item())
    if output:
        with Path(output).open('xb') as f:
            np.savez_compressed(f, logits=logits.numpy(), labels=labels.numpy())
    return {**metrics_from_cm(cm), 'loss': F.cross_entropy(logits, labels).item(),
            'mean_confidence': confidence.mean().item(), 'ece_10_bins': ece,
            'errors_confidence_above_90pct': int(((~correct) & (confidence > .9)).sum())}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--device', choices=['cpu', 'mps'], default='mps')
    a = p.parse_args()
    out = Path('results/t35_diagnosis_20261030')
    out.mkdir()
    protected = [Path('PROJECT_STATUS.md'), Path('README.md'), Path('requirements.txt')]
    for root in ['src', 'tests', 'configs', 'docs', 'results', 'checkpoints', 'data']:
        protected += [q for q in Path(root).rglob('*') if q.is_file()
                      and '__pycache__' not in q.parts and q.suffix != '.pyc'
                      and out not in q.parents and not q.name.startswith('.DS_Store')]
    write_json(out / 'original_hashes.json', {str(q): sha256(q) for q in sorted(set(protected))})
    with (out / 'PROJECT_STATUS.before_t35.md').open('xb') as f:
        f.write(Path('PROJECT_STATUS.md').read_bytes())
    # Additional old-best backup; original artifact also stays in place.
    with (out / 't3_best_backup.pt').open('xb') as f:
        with Path('checkpoints/t3_06_unweighted_s42/best.pt').open('rb') as src:
            shutil.copyfileobj(src, f)
    torch.set_num_threads(4)
    device = select_device(a.device)
    csv_path = 'data/icml_face_data_副本.csv'
    train, val = load_split(csv_path, 'Training'), load_split(csv_path, 'PublicTest')
    raw = EmotionDataset(csv_path, 'PublicTest')
    preprocessing_equal = all(torch.equal(preprocess_pixels(raw.images[i][0]), val[i][0])
                              for i in range(len(raw)))
    maps = []
    for data in [train, val]:
        groups = defaultdict(list)
        for i, (x, y) in enumerate(data):
            groups[x.numpy().tobytes()].append((i, int(y)))
        maps.append(groups)
    shared = maps[0].keys() & maps[1].keys()
    duplicates = {'training_repeated_rows': sum(len(v) - 1 for v in maps[0].values()),
                  'training_conflicting_pixel_groups': sum(len({y for _, y in v}) > 1 for v in maps[0].values()),
                  'public_repeated_rows': sum(len(v) - 1 for v in maps[1].values()),
                  'shared_exact_pixel_groups': len(shared),
                  'public_rows_also_in_training': sum(len(maps[1][k]) for k in shared),
                  'cross_split_conflicting_groups': sum(len({y for _, y in maps[0][k] + maps[1][k]}) > 1 for k in shared),
                  'action': 'Official splits and labels unchanged; no deduplication or label editing.'}
    models = {}
    for name, path in [('parent50', 'checkpoints/t3_05_resnet_aug_mps_s42/best.pt'),
                       ('best56', 'checkpoints/t3_06_unweighted_s42/best.pt')]:
        model, cp = load_t3(path)
        model.to(device)
        models[name] = {'checkpoint': path, 'sha256': sha256(path), 'epoch': cp['epoch'],
                        'parameters': sum(p.numel() for p in model.parameters()),
                        'fixed_training_eval': collect(model, train, device),
                        'public_eval': collect(model, val, device, out / (name + '_public_logits.npz'))}
        print(name, json.dumps(models[name]), flush=True)
    result = {'device': str(device), 'torch': str(torch.__version__), 'train_samples': len(train),
              'public_samples': len(val), 'private_test_used': False,
              'all_public_preprocessing_equal': preprocessing_equal, 'exact_duplicates': duplicates,
              'models': models}
    write_json(out / 'diagnosis.json', result)
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
