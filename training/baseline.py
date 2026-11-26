"""Train only on Training; select checkpoints only with PublicTest."""

import argparse
import csv
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import platform
import random
import shutil
import time

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, Subset

from data_processing.dataset import EmotionDataset, LABELS
from model_design.basic_cnn import BasicCNN, load_model


@dataclass
class TrainConfig:
    csv_path: str
    run_dir: str
    checkpoint_dir: str
    epochs: int = 15
    batch_size: int = 128
    learning_rate: float = 0.001
    weight_decay: float = 0.0001
    seed: int = 42
    threads: int = 4
    device: str = "cpu"
    train_limit: int = 0
    val_limit: int = 0


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8") as file:
        json.dump(value, file, ensure_ascii=False, indent=2, allow_nan=False)
        file.write("\n")


def select_device(name):
    if name == "cpu":
        return torch.device("cpu")
    if name == "mps" and torch.backends.mps.is_available():
        return torch.device("mps")
    if name == "cuda" and torch.cuda.is_available():
        return torch.device("cuda")
    raise ValueError(f"Device is unavailable or unsupported: {name}")


def set_seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    # Fail rather than silently use a known nondeterministic operation.
    torch.use_deterministic_algorithms(True)
    if torch.backends.cudnn.is_available():
        torch.backends.cudnn.benchmark = False


def build_loader(csv_path, split, batch_size, seed=42, limit=0):
    dataset = EmotionDataset(csv_path, split)
    if limit < 0:
        raise ValueError("Sample limit must be nonnegative")
    if limit:
        # Reproducible subset for smoke checks only, never a new data split.
        indices = torch.randperm(
            len(dataset), generator=torch.Generator().manual_seed(seed)
        )
        dataset = Subset(dataset, indices[:limit].tolist())
    return DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=(split == "Training"),
        num_workers=0,
        generator=torch.Generator().manual_seed(seed),
    )


def run_epoch(model, loader, criterion, device, optimizer=None):
    training = optimizer is not None
    model.train(training)
    loss_sum, correct, count = 0.0, 0, 0
    context = torch.enable_grad() if training else torch.inference_mode()
    with context:
        for images, labels in loader:
            images, labels = images.to(device), labels.to(device)
            if training:
                optimizer.zero_grad(set_to_none=True)
            logits = model(images)
            loss = criterion(logits, labels)
            if not torch.isfinite(loss):
                raise RuntimeError("Non-finite loss; training aborted")
            if training:
                loss.backward()
                optimizer.step()
            batch_count = labels.size(0)
            # Weight by samples, including a smaller final batch.
            loss_sum += loss.item() * batch_count
            correct += (logits.argmax(dim=1) == labels).sum().item()
            count += batch_count
    if count == 0:
        raise ValueError("Cannot evaluate an empty loader")
    return {
        "loss": loss_sum / count,
        "accuracy": correct / count,
        "correct": correct,
        "samples": count,
    }


def is_better(candidate, previous):
    """Highest accuracy wins; tied accuracy uses lower cross-entropy."""
    return previous is None or (candidate["accuracy"], -candidate["loss"]) > (
        previous["accuracy"],
        -previous["loss"],
    )


def train(config):
    if (
        min(config.epochs, config.batch_size, config.threads) < 1
        or min(config.train_limit, config.val_limit, config.seed) < 0
        or not math.isfinite(config.learning_rate)
        or config.learning_rate <= 0
        or not math.isfinite(config.weight_decay)
        or config.weight_decay < 0
    ):
        raise ValueError("Invalid training configuration")
    device = select_device(config.device)
    run_dir, checkpoint_dir = Path(config.run_dir), Path(config.checkpoint_dir)
    if run_dir.resolve() == checkpoint_dir.resolve():
        raise ValueError("Use separate log and checkpoint directories")
    # Refuse to overwrite earlier experiments or user files.
    if run_dir.exists() or checkpoint_dir.exists():
        raise FileExistsError("Run/checkpoint directory exists; choose new paths")
    run_dir.mkdir(parents=True)
    checkpoint_dir.mkdir(parents=True)
    torch.set_num_threads(config.threads)
    set_seed(config.seed)
    started = time.perf_counter()
    train_loader = build_loader(
        config.csv_path, "Training", config.batch_size, config.seed, config.train_limit
    )
    val_loader = build_loader(
        config.csv_path, "PublicTest", config.batch_size, config.seed, config.val_limit
    )
    model = BasicCNN().to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(
        model.parameters(), lr=config.learning_rate, weight_decay=config.weight_decay
    )
    digest = hashlib.sha256()
    with Path(config.csv_path).open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    source_hashes = {
        str(path): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(Path("src").glob("*.py"))
    }
    metadata = {
        "config": asdict(config),
        "labels": list(LABELS),
        "architecture": str(model),
        "parameters": sum(p.numel() for p in model.parameters()),
        "loss": "CrossEntropyLoss(mean)",
        "optimizer": "Adam",
        "selection": "highest PublicTest accuracy; ties: lower PublicTest loss",
        "data_sha256": digest.hexdigest(),
        "source_sha256": source_hashes,
        "train_samples": len(train_loader.dataset),
        "val_samples": len(val_loader.dataset),
        "smoke_run": bool(config.train_limit or config.val_limit),
        "private_test_used": False,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "python": platform.python_version(),
            "torch": str(torch.__version__),
            "numpy": np.__version__,
            "platform": platform.platform(),
            "device": str(device),
            "threads": torch.get_num_threads(),
            "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
        },
    }
    write_json(run_dir / "config.json", metadata)
    best, best_epoch, best_path = None, None, None
    with (run_dir / "metrics.csv").open("x", newline="") as csv_file, (
        run_dir / "metrics.jsonl"
    ).open("x") as json_file:
        fields = [
            "epoch",
            "train_loss",
            "train_accuracy",
            "train_correct",
            "train_samples",
            "val_loss",
            "val_accuracy",
            "val_correct",
            "val_samples",
            "learning_rate",
            "epoch_seconds",
            "new_best",
        ]
        writer = csv.DictWriter(csv_file, fieldnames=fields)
        writer.writeheader()
        for epoch in range(1, config.epochs + 1):
            epoch_start = time.perf_counter()
            training = run_epoch(model, train_loader, criterion, device, optimizer)
            validation = run_epoch(model, val_loader, criterion, device)
            improved = is_better(validation, best)
            if improved:
                best, best_epoch = validation.copy(), epoch
                best_path = checkpoint_dir / f"epoch_{epoch:03d}.pt"
                checkpoint = {
                    "format_version": 1,
                    "architecture": "BasicCNN",
                    "labels": list(LABELS),
                    "preprocessing": "float32 / 255; [N,1,48,48]",
                    "epoch": epoch,
                    "validation": best,
                    "config": asdict(config),
                    "data_sha256": digest.hexdigest(),
                    "model_state_dict": {
                        key: value.detach().cpu().clone()
                        for key, value in model.state_dict().items()
                    },
                }
                with best_path.open("xb") as file:
                    torch.save(checkpoint, file)
            row = {
                "epoch": epoch,
                **{"train_" + k: v for k, v in training.items()},
                **{"val_" + k: v for k, v in validation.items()},
                "learning_rate": optimizer.param_groups[0]["lr"],
                "epoch_seconds": time.perf_counter() - epoch_start,
                "new_best": improved,
            }
            writer.writerow(row)
            json_file.write(json.dumps(row, allow_nan=False) + "\n")
            csv_file.flush()
            json_file.flush()
            print(json.dumps(row, allow_nan=False), flush=True)
    final_path = checkpoint_dir / "best.pt"
    with best_path.open("rb") as source, final_path.open("xb") as target:
        shutil.copyfileobj(source, target)
    # Re-evaluate the artifact from disk, rather than assuming save/load worked.
    loaded, checkpoint = load_model(final_path, device)
    reloaded = run_epoch(loaded, val_loader, criterion, device)
    if reloaded["correct"] != best["correct"] or not math.isclose(
        reloaded["loss"], best["loss"], rel_tol=1e-6, abs_tol=1e-7
    ):
        raise RuntimeError("Reloaded checkpoint metrics disagree with selected model")
    summary = {
        "best_epoch": best_epoch,
        "best_validation": best,
        "reloaded_validation": reloaded,
        "reload_verified": True,
        "best_checkpoint": str(final_path.resolve()),
        "checkpoint_sha256": hashlib.sha256(final_path.read_bytes()).hexdigest(),
        "elapsed_seconds": time.perf_counter() - started,
        "epochs_completed": config.epochs,
        "private_test_used": False,
    }
    write_json(run_dir / "summary.json", summary)
    print(json.dumps(summary), flush=True)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--checkpoint-dir", required=True)
    for name, default in [
        ("epochs", 15),
        ("batch_size", 128),
        ("seed", 42),
        ("threads", 4),
        ("train_limit", 0),
        ("val_limit", 0),
    ]:
        parser.add_argument("--" + name.replace("_", "-"), type=int, default=default)
    parser.add_argument("--learning-rate", type=float, default=0.001)
    parser.add_argument("--weight-decay", type=float, default=0.0001)
    parser.add_argument("--device", choices=["cpu", "mps", "cuda"], default="cpu")
    train(TrainConfig(**vars(parser.parse_args())))


if __name__ == "__main__":
    main()
