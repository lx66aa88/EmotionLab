"""FER CSV loader. PrivateTest is deliberately unavailable in this module."""

import csv
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader

LABELS = ("Angry", "Disgust", "Fear", "Happy", "Sad", "Surprise", "Neutral")
ALLOWED_SPLITS = ("Training", "PublicTest")


class EmotionDataset(Dataset):
    def __init__(self, csv_path, split):
        if split not in ALLOWED_SPLITS:
            raise ValueError(
                "Only Training and PublicTest are permitted; PrivateTest is reserved."
            )
        self.images, self.labels = [], []
        with Path(csv_path).open(newline="", encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)
            if not {"emotion", "Usage", "pixels"}.issubset(reader.fieldnames or []):
                raise ValueError("CSV must contain emotion, Usage and pixels")
            for line, row in enumerate(reader, 2):
                if row["Usage"] != split:
                    continue
                try:
                    label = int(row["emotion"])
                    values = [int(value) for value in row["pixels"].split()]
                    if (
                        label not in range(7)
                        or len(values) != 2304
                        or any(v < 0 or v > 255 for v in values)
                    ):
                        raise ValueError("invalid label or pixels")
                except (ValueError, AttributeError) as exc:
                    raise ValueError(f"Invalid data at CSV line {line}: {exc}") from exc
                self.images.append(
                    np.asarray(values, dtype=np.uint8).reshape(1, 48, 48)
                )
                self.labels.append(label)
        if not self.labels:
            raise ValueError(f"No rows found for {split}")

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, index):
        image = torch.from_numpy(self.images[index].copy()).float().div_(255.0)
        return image, self.labels[index]


def make_loader(csv_path, split, batch_size=64, num_workers=0):
    return DataLoader(
        EmotionDataset(csv_path, split),
        batch_size=batch_size,
        shuffle=(split == "Training"),
        num_workers=num_workers,
    )
