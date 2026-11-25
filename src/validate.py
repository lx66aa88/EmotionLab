"""Evaluate a frozen checkpoint on PublicTest only (never PrivateTest)."""
import argparse
import json
import torch
from src.model import load_model
from src.train import build_loader, run_epoch, select_device


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv_path')
    parser.add_argument('checkpoint')
    parser.add_argument('--batch-size', type=int, default=128)
    parser.add_argument('--threads', type=int, default=4)
    parser.add_argument('--device', choices=['cpu', 'mps', 'cuda'], default='cpu')
    args = parser.parse_args()
    if args.threads < 1 or args.batch_size < 1:
        parser.error('threads and batch size must be positive')
    torch.set_num_threads(args.threads)
    device = select_device(args.device)
    model, checkpoint = load_model(args.checkpoint, device)
    loader = build_loader(args.csv_path, 'PublicTest', args.batch_size)
    metrics = run_epoch(model, loader, torch.nn.CrossEntropyLoss(), device)
    print(json.dumps({'split': 'PublicTest', 'checkpoint_epoch': checkpoint['epoch'],
                      **metrics}, indent=2))


if __name__ == '__main__':
    main()
