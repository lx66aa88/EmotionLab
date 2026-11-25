"""Independent T3.5 reload; full PublicTest only, exclusive output files."""
import argparse
from pathlib import Path

import torch

from src.t3_models import load_t3
from src.t3_train import load_split, sha256
from src.t35_diagnose import collect
from src.train import select_device, write_json


def main():
    p = argparse.ArgumentParser()
    p.add_argument('checkpoint')
    p.add_argument('--output', required=True)
    p.add_argument('--device', choices=['cpu', 'mps'], default='cpu')
    p.add_argument('--csv', default='data/icml_face_data_副本.csv')
    p.add_argument('--training-eval', action='store_true')
    a = p.parse_args()
    if Path(a.output).exists() or Path(a.output + '.npz').exists():
        raise FileExistsError('Independent evaluation outputs already exist')
    torch.set_num_threads(4)
    model, cp = load_t3(a.checkpoint)
    if cp['data_sha256'] != sha256(a.csv):
        raise ValueError('Data checksum mismatch')
    device = select_device(a.device)
    model.to(device)
    result = {'checkpoint': str(Path(a.checkpoint).resolve()), 'checkpoint_sha256': sha256(a.checkpoint),
              'device': str(device), 'split': 'PublicTest', 'private_test_used': False,
              **collect(model, load_split(a.csv, 'PublicTest'), device, a.output + '.npz')}
    if a.training_eval:
        result['fixed_training_eval'] = collect(model, load_split(a.csv, 'Training'), device)
    write_json(a.output, result)
    print({k: result[k] for k in ['checkpoint','device','accuracy','macro_f1','loss','samples']})


if __name__ == '__main__':
    main()
