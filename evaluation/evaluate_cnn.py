"""Independent frozen PublicTest evaluation for T2/T3 artifacts; never PrivateTest."""
import argparse
import json
import torch
from torch.utils.data import DataLoader
from model_design.basic_cnn import load_model
from model_design.cnn_variants import load_t3
from training.cnn_experiment import epoch, load_split, sha256
from training.baseline import write_json
from training.baseline import select_device


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('checkpoint')
    p.add_argument('--csv', default='data/icml_face_data_副本.csv')
    p.add_argument('--output', required=True)
    p.add_argument('--threads', type=int, default=4)
    p.add_argument('--device', choices=['cpu', 'mps'], default='cpu')
    a = p.parse_args()
    torch.set_num_threads(a.threads)
    cp = torch.load(a.checkpoint, map_location='cpu', weights_only=True)
    model, cp = (load_t3(a.checkpoint) if cp.get('format_version') == 3 else load_model(a.checkpoint))
    model.to(select_device(a.device))
    if cp['data_sha256'] != sha256(a.csv):
        raise ValueError('Data checksum mismatch')
    loader = DataLoader(load_split(a.csv, 'PublicTest'), batch_size=128, shuffle=False)
    result = {'split': 'PublicTest', 'checkpoint': a.checkpoint,
              'checkpoint_sha256': sha256(a.checkpoint), 'checkpoint_epoch': cp['epoch'],
              'private_test_used': False, 'device': a.device, **epoch(model, loader)}
    write_json(a.output, result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
