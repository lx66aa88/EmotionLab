"""Independent T3 experiments. Fixed official splits, exclusive output creation."""

from data_processing.augmentation import augment
from evaluation.metrics import metrics_from_cm
import argparse
import csv
import hashlib
import json
import math
import platform
import random
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
from torch.utils.data import DataLoader, TensorDataset
from data_processing.dataset import EmotionDataset, LABELS
from model_design.basic_cnn import load_model
from training.baseline import is_better, set_seed, write_json
from model_design.cnn_variants import make_model, load_t3


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1048576), b""):
            h.update(chunk)
    return h.hexdigest()


def load_split(path, split):
    # EmotionDataset rejects PrivateTest before opening the CSV; no cache of it.
    data = EmotionDataset(path, split)
    images = torch.from_numpy(np.stack(data.images)).float().div_(255)
    return TensorDataset(images, torch.tensor(data.labels, dtype=torch.long))


def epoch(model, loader, optimizer=None, augmentation=False, weights=None):
    training = optimizer is not None
    model.train(training)
    cm = torch.zeros(7, 7, dtype=torch.long)
    ce_sum, objective_sum, count = 0.0, 0.0, 0
    device = next(model.parameters()).device
    with torch.enable_grad() if training else torch.inference_mode():
        for images, labels in loader:
            if training and augmentation:
                images = augment(images)
            images, labels = images.to(device), labels.to(device)
            if training:
                optimizer.zero_grad(set_to_none=True)
            logits = model(images)
            ce = F.cross_entropy(logits, labels, reduction="none")
            # Explicit per-sample weighted objective; ordinary CE remains comparable.
            objective = ce.mean() if weights is None else (ce * weights[labels]).mean()
            if not torch.isfinite(objective):
                raise RuntimeError("Non-finite loss")
            if training:
                objective.backward()
                optimizer.step()
            n = len(labels)
            ce_sum += ce.detach().sum().item()
            objective_sum += objective.item() * n
            count += n
            codes = (labels * 7 + logits.detach().argmax(1)).cpu()
            cm += torch.bincount(codes, minlength=49).reshape(7, 7)
    result = metrics_from_cm(cm)
    return {**result, "loss": ce_sum / count, "objective": objective_sum / count}


def train(config_path):
    cfg = json.loads(Path(config_path).read_text())
    name = cfg["name"]
    if Path(name).name != name:
        raise ValueError("Experiment name must be a single path component")
    run = Path("results") / name
    ckpt_dir = Path("checkpoints") / name
    if run.exists() or ckpt_dir.exists():
        raise FileExistsError(
            "Choose a new experiment name; existing runs are protected"
        )
    if cfg["model"] not in ("basic", "batchnorm", "resnet18_w16"):
        raise ValueError("Unsupported model")
    run.mkdir()
    ckpt_dir.mkdir()
    started = time.perf_counter()
    torch.set_num_threads(cfg.get("threads", 4))
    set_seed(cfg["seed"])
    device = torch.device(cfg.get("device", "cpu"))
    if device.type not in ("cpu", "mps") or (
        device.type == "mps" and not torch.backends.mps.is_available()
    ):
        raise ValueError("Requested device unavailable")
    data = load_split(cfg["csv_path"], "Training")
    val = load_split(cfg["csv_path"], "PublicTest")
    counts = torch.bincount(data.tensors[1], minlength=7)
    generator = torch.Generator().manual_seed(cfg["seed"])
    train_loader = DataLoader(
        data, batch_size=cfg["batch_size"], shuffle=True, generator=generator
    )
    val_loader = DataLoader(val, batch_size=cfg["batch_size"], shuffle=False)
    model = make_model(cfg["model"]).to(device)
    start_epoch = cfg.get("start_epoch", 0)
    initialization = "random initialization"
    if cfg.get("initialize_from"):
        cp = torch.load(cfg["initialize_from"], map_location="cpu", weights_only=True)
        expected = "BasicCNN" if cp["format_version"] == 1 else cp["config"]["model"]
        if expected not in ("BasicCNN", cfg["model"]) or (
            expected == "BasicCNN" and cfg["model"] != "basic"
        ):
            raise ValueError("Model architecture mismatch")
        if (
            tuple(cp["labels"]) != LABELS
            or cp["preprocessing"] != "float32 / 255; [N,1,48,48]"
            or cp["data_sha256"] != sha256(cfg["csv_path"])
        ):
            raise ValueError("Source checkpoint label/preprocessing/data mismatch")
        model.load_state_dict(cp["model_state_dict"], strict=True)
        if cp["epoch"] != start_epoch:
            raise ValueError("Starting epoch must match source weights")
        initialization = (
            "weights-only fine-tuning; optimizer/scheduler/RNG reset, NOT exact resume"
        )
    elif start_epoch:
        raise ValueError("Nonzero starting epoch requires source weights")
    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=cfg["learning_rate"],
        weight_decay=cfg.get("weight_decay", 0.0001),
    )
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer,
        mode="max",
        factor=0.5,
        patience=cfg.get("lr_patience", 3),
        min_lr=1e-6,
    )
    weights = None
    if cfg.get("class_weight_power", 0):
        weights = (counts.float().sum() / (7 * counts.float())) ** cfg[
            "class_weight_power"
        ]
        weights /= (weights * counts).sum() / counts.sum()
        weights = weights.to(device)
    source_files = list(Path("src").glob("*.py"))
    metadata = {
        "config": cfg,
        "config_sha256": sha256(config_path),
        "initialization": initialization,
        "labels": list(LABELS),
        "data_sha256": sha256(cfg["csv_path"]),
        "source_sha256": {str(p): sha256(p) for p in source_files},
        "parameters": sum(p.numel() for p in model.parameters()),
        "architecture": str(model),
        "training_counts": counts.tolist(),
        "class_weights": weights.tolist() if weights is not None else None,
        "train_samples": len(data),
        "val_samples": len(val),
        "private_test_used": False,
        "validation_augmentation": False,
        "selection": "PublicTest accuracy, ties lower ordinary CE; no TTA",
        "scheduler": "ReduceLROnPlateau(max accuracy, factor=.5)",
        "early_stopping": "epochs since best accuracy/loss improvement",
        "environment": {
            "python": platform.python_version(),
            "torch": str(torch.__version__),
            "numpy": np.__version__,
            "device": str(device),
            "threads": torch.get_num_threads(),
            "deterministic": True,
        },
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    write_json(run / "config.json", metadata)
    # Source snapshots survive subsequent work; no original code is changed.
    (run / "source").mkdir()
    for p in source_files:
        with (run / "source" / p.name).open("xb") as f:
            f.write(p.read_bytes())
    initial = epoch(model, val_loader)
    write_json(run / "initial_validation.json", initial)
    best = (
        initial
        if (cfg.get("initialize_from") and cfg.get("include_initial_candidate", True))
        else None
    )
    best_epoch = start_epoch if best else None
    best_path = None
    stale = 0

    def save_checkpoint(ep, result):
        path = ckpt_dir / f"epoch_{ep:03d}.pt"
        payload = {
            "format_version": 3,
            "config": cfg,
            "labels": list(LABELS),
            "epoch": ep,
            "preprocessing": "float32 / 255; [N,1,48,48]",
            "data_sha256": metadata["data_sha256"],
            "validation": result,
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "scheduler_state_dict": scheduler.state_dict(),
            "torch_rng_state": torch.get_rng_state(),
            "loader_rng_state": generator.get_state(),
            "python_rng_state": random.getstate(),
            "mps_rng_state": (
                torch.mps.get_rng_state() if device.type == "mps" else None
            ),
            "selection_best_epoch": best_epoch,
            "epochs_without_improvement": stale,
        }
        with path.open("xb") as f:
            torch.save(payload, f)
        return path

    if best:
        best_path = save_checkpoint(start_epoch, best)
    fields = [
        "epoch",
        "train_loss",
        "train_objective",
        "train_accuracy",
        "train_macro_f1",
        "train_samples",
        "val_loss",
        "val_accuracy",
        "val_macro_f1",
        "val_correct",
        "val_samples",
        "learning_rate",
        "epoch_seconds",
        "new_best",
    ]
    with (run / "metrics.csv").open("x", newline="") as f, (run / "metrics.jsonl").open(
        "x"
    ) as jf:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for ep in range(start_epoch + 1, cfg["max_epoch"] + 1):
            tick = time.perf_counter()
            lr = optimizer.param_groups[0]["lr"]
            tr = epoch(
                model, train_loader, optimizer, cfg.get("augmentation", False), weights
            )
            va = epoch(model, val_loader)
            improved = is_better(va, best)
            scheduler.step(va["accuracy"])
            stale = 0 if improved else stale + 1
            if improved:
                best, best_epoch = va, ep
                best_path = save_checkpoint(ep, va)
            row = {
                "epoch": ep,
                **{
                    "train_" + k: tr[k]
                    for k in ["loss", "objective", "accuracy", "macro_f1", "samples"]
                },
                **{
                    "val_" + k: va[k]
                    for k in ["loss", "accuracy", "macro_f1", "correct", "samples"]
                },
                "learning_rate": lr,
                "epoch_seconds": time.perf_counter() - tick,
                "new_best": improved,
            }
            writer.writerow(row)
            jf.write(json.dumps({**row, "validation": va}, allow_nan=False) + "\n")
            f.flush()
            jf.flush()
            print(json.dumps(row), flush=True)
            if stale >= cfg.get("early_stopping", 10):
                break
    final = ckpt_dir / "best.pt"
    with best_path.open("rb") as src, final.open("xb") as dst:
        shutil.copyfileobj(src, dst)
    loaded, _ = load_t3(final)
    loaded.to(device)
    reloaded = epoch(loaded, val_loader)
    if reloaded["confusion_matrix"] != best["confusion_matrix"] or not math.isclose(
        reloaded["loss"], best["loss"], abs_tol=1e-7
    ):
        raise RuntimeError("Reload disagrees with selected model")
    write_json(run / "best_validation.json", reloaded)
    summary = {
        "best_epoch": best_epoch,
        "epochs_completed": ep - start_epoch,
        "last_epoch": ep,
        "stop_reason": (
            "early_stopping" if stale >= cfg.get("early_stopping", 10) else "max_epoch"
        ),
        "best_validation": reloaded,
        "reload_verified": True,
        "elapsed_seconds": time.perf_counter() - started,
        "best_checkpoint": str(final.resolve()),
        "checkpoint_sha256": sha256(final),
        "private_test_used": False,
    }
    write_json(run / "summary.json", summary)
    print(json.dumps(summary), flush=True)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config")
    train(parser.parse_args().config)


if __name__ == "__main__":
    main()
