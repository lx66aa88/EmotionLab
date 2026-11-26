"""Exercise real Training and PublicTest DataLoaders without a model."""

import argparse
import torch
from data_processing.dataset import EmotionDataset, make_loader

parser = argparse.ArgumentParser()
parser.add_argument("csv_path")
args = parser.parse_args()
for split, expected in [("Training", 28709), ("PublicTest", 3589)]:
    loader = make_loader(args.csv_path, split, batch_size=32)
    assert len(loader.dataset) == expected, (split, len(loader.dataset))
    images, labels = next(iter(loader))
    assert images.shape == (32, 1, 48, 48)
    assert images.dtype == torch.float32 and 0 <= images.min() <= images.max() <= 1
    assert labels.shape == (32,) and labels.dtype == torch.int64
    print(
        split,
        "samples:",
        len(loader.dataset),
        "batch:",
        tuple(images.shape),
        "labels:",
        tuple(labels.shape),
    )
try:
    EmotionDataset(args.csv_path, "PrivateTest")
except ValueError:
    print("PrivateTest rejection: PASS")
else:
    raise AssertionError("PrivateTest must be rejected")
