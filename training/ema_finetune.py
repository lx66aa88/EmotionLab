"""Bounded T3.5 fine-tuning. New paths only; official Training/PublicTest only."""

from data_processing.augmentation import augment_t35
import argparse
import copy
import csv
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
from torch.nn import functional as F
from torch.utils.data import DataLoader

from data_processing.dataset import LABELS
from model_design.cnn_variants import load_t3
from training.cnn_experiment import augment, epoch, load_split, metrics_from_cm, sha256
from training.baseline import is_better, select_device, set_seed, write_json


@torch.no_grad()
def update_ema(averaged, online, decay):
    for target, source in zip(averaged.parameters(), online.parameters()):
        target.mul_(decay).add_(source, alpha=1 - decay)
    # Running statistics are recalculated on Training before each validation.
    for target, source in zip(averaged.buffers(), online.buffers()):
        target.copy_(source)


@torch.no_grad()
def refresh_bn(model, train_loader):
    """Re-estimate EMA BN from unaugmented Training only; Dropout stays disabled.

    Cumulative batch statistics (including final smaller batch), fixed batch size
    and order. No labels are used. This is part of the EMA recipe, not tuning.
    """
    model.eval()
    norms = [m for m in model.modules() if isinstance(m, nn.BatchNorm2d)]
    momenta = [m.momentum for m in norms]
    try:
        for m in norms:
            m.reset_running_stats()
            m.momentum = None
            m.train()
        device = next(model.parameters()).device
        for x, _ in train_loader:
            model(x.to(device))
    finally:
        for m, momentum in zip(norms, momenta):
            m.momentum = momentum
        model.eval()


def training_epoch(
    model, loader, optimizer, smoothing, photometric, ema=None, decay=0.995
):
    model.train()
    cm = torch.zeros(7, 7, dtype=torch.long)
    ce_sum = objective_sum = count = 0
    device = next(model.parameters()).device
    for x, y in loader:
        x = augment_t35(x, photometric).to(device)
        y = y.to(device)
        optimizer.zero_grad(set_to_none=True)
        logits = model(x)
        ce = F.cross_entropy(logits, y)
        objective = F.cross_entropy(logits, y, label_smoothing=smoothing)
        if not torch.isfinite(objective):
            raise RuntimeError("Non-finite objective")
        objective.backward()
        optimizer.step()
        if ema is not None:
            update_ema(ema, model, decay)
        n = len(y)
        ce_sum += ce.detach().item() * n
        objective_sum += objective.detach().item() * n
        count += n
        cm += torch.bincount(
            (y * 7 + logits.detach().argmax(1)).cpu(), minlength=49
        ).reshape(7, 7)
    return {
        **metrics_from_cm(cm),
        "loss": ce_sum / count,
        "objective": objective_sum / count,
    }


def train(config_path):
    cfg = json.loads(Path(config_path).read_text())
    name = cfg["name"]
    if Path(name).name != name or not name.startswith("t35_"):
        raise ValueError("Use a single new t35_ experiment name")
    run, ckpts = Path("results") / name, Path("checkpoints") / name
    if run.exists() or ckpts.exists():
        raise FileExistsError("Existing results/checkpoints are protected")
    if (
        cfg["epochs"] < 1
        or not 0 <= cfg["label_smoothing"] < 1
        or not 0 <= cfg["ema_decay"] < 1
        or cfg["batch_size"] < 1
        or cfg["learning_rate"] <= 0
        or cfg["min_lr"] < 0
        or cfg["min_lr"] > cfg["learning_rate"]
    ):
        raise ValueError("Invalid T3.5 configuration")
    torch.set_num_threads(cfg.get("threads", 4))
    device = select_device(cfg["device"])
    set_seed(cfg["seed"])
    started = time.perf_counter()
    model, parent = load_t3(cfg["initialize_from"])
    if (
        parent["config"]["model"] != cfg["model"]
        or sha256(cfg["csv_path"]) != parent["data_sha256"]
    ):
        raise ValueError("Parent model/data mismatch")
    run.mkdir()
    ckpts.mkdir()
    model.to(device)
    data, val = load_split(cfg["csv_path"], "Training"), load_split(
        cfg["csv_path"], "PublicTest"
    )
    generator = torch.Generator().manual_seed(cfg["seed"])
    loader = DataLoader(
        data, batch_size=cfg["batch_size"], shuffle=True, generator=generator
    )
    # Auxiliary passes must not consume training augmentation/Dropout RNG.
    fixed_loader = DataLoader(
        data,
        batch_size=cfg["batch_size"],
        shuffle=False,
        generator=torch.Generator().manual_seed(0),
    )
    val_loader = DataLoader(
        val,
        batch_size=cfg["batch_size"],
        shuffle=False,
        generator=torch.Generator().manual_seed(0),
    )
    ema = copy.deepcopy(model).eval().requires_grad_(False) if cfg["ema"] else None
    optimizer = torch.optim.Adam(
        model.parameters(), lr=cfg["learning_rate"], weight_decay=cfg["weight_decay"]
    )

    # Fixed budget/trajectory; no validation-dependent scheduler or early stopping.
    def set_lr(local_epoch):
        fraction = (local_epoch - 1) / max(1, cfg["epochs"] - 1)
        lr = cfg["min_lr"] + 0.5 * (cfg["learning_rate"] - cfg["min_lr"]) * (
            1 + math.cos(math.pi * fraction)
        )
        for group in optimizer.param_groups:
            group["lr"] = lr
        return lr

    files = list(Path("src").glob("*.py"))
    write_json(
        run / "config.json",
        {
            "config": cfg,
            "config_sha256": sha256(config_path),
            "parent_sha256": sha256(cfg["initialize_from"]),
            "parent_epoch": parent["epoch"],
            "data_sha256": parent["data_sha256"],
            "source_sha256": {str(p): sha256(p) for p in files},
            "initialization": "weights only; Adam/RNG reset; not exact resume; common fixed seed42 parent",
            "parameters": sum(p.numel() for p in model.parameters()),
            "train_samples": len(data),
            "val_samples": len(val),
            "private_test_used": False,
            "validation_augmentation": False,
            "selection": "within each declared online/EMA stream: highest PublicTest accuracy, ties lower ordinary CE; parent excluded",
            "ema": "per optimizer step; BN recalibrated from unaugmented Training only before PublicTest; dropout disabled",
            "environment": {
                "python": platform.python_version(),
                "torch": str(torch.__version__),
                "numpy": np.__version__,
                "device": str(device),
                "threads": torch.get_num_threads(),
                "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
            },
        },
    )
    (run / "source").mkdir()
    for p in files:
        with (run / "source" / p.name).open("xb") as f:
            f.write(p.read_bytes())
    initial = epoch(model, val_loader)
    write_json(run / "initial_validation.json", initial)
    best = {"online": None, **({"ema": None} if ema is not None else {})}
    best_paths, best_epochs = {}, {}

    def save(candidate, kind, ep, result):
        path = ckpts / f"{kind}_epoch_{ep:03d}.pt"
        payload = {
            "format_version": 3,
            "config": cfg,
            "labels": list(LABELS),
            "epoch": parent["epoch"] + ep,
            "local_epoch": ep,
            "weight_kind": kind,
            "preprocessing": "float32 / 255; [N,1,48,48]",
            "data_sha256": parent["data_sha256"],
            "validation": result,
            "model_state_dict": candidate.state_dict(),
            "online_model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "torch_rng_state": torch.get_rng_state(),
            "loader_rng_state": generator.get_state(),
            "python_rng_state": random.getstate(),
            "mps_rng_state": (
                torch.mps.get_rng_state() if device.type == "mps" else None
            ),
            "resume_supported": False,
        }
        with path.open("xb") as f:
            torch.save(payload, f)
        return path

    fields = [
        "local_epoch",
        "epoch",
        "learning_rate",
        "train_loss",
        "train_objective",
        "train_accuracy",
        "train_samples",
        "online_loss",
        "online_accuracy",
        "online_macro_f1",
        "ema_loss",
        "ema_accuracy",
        "ema_macro_f1",
        "epoch_seconds",
    ]
    with (run / "metrics.csv").open("x", newline="") as f, (run / "metrics.jsonl").open(
        "x"
    ) as jf:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for ep in range(1, cfg["epochs"] + 1):
            tick = time.perf_counter()
            lr = set_lr(ep)
            tr = training_epoch(
                model,
                loader,
                optimizer,
                cfg["label_smoothing"],
                cfg["photometric"],
                ema,
                cfg["ema_decay"],
            )
            evaluations = {"online": epoch(model, val_loader)}
            if ema is not None:
                refresh_bn(ema, fixed_loader)
                evaluations["ema"] = epoch(ema, val_loader)
            for kind, result in evaluations.items():
                if is_better(result, best[kind]):
                    best[kind], best_epochs[kind] = result, ep
                    best_paths[kind] = save(
                        model if kind == "online" else ema, kind, ep, result
                    )
            row = {
                "local_epoch": ep,
                "epoch": parent["epoch"] + ep,
                "learning_rate": lr,
                "train_loss": tr["loss"],
                "train_objective": tr["objective"],
                "train_accuracy": tr["accuracy"],
                "train_samples": tr["samples"],
                **{
                    kind + "_" + metric: result[metric]
                    for kind, result in evaluations.items()
                    for metric in ["loss", "accuracy", "macro_f1"]
                },
                "epoch_seconds": time.perf_counter() - tick,
            }
            writer.writerow(row)
            jf.write(
                json.dumps(
                    {**row, "training": tr, "validation": evaluations}, allow_nan=False
                )
                + "\n"
            )
            f.flush()
            jf.flush()
            print(json.dumps(row), flush=True)
    streams = {}
    for kind in best:
        final = ckpts / (
            "best.pt"
            if kind == ("ema" if ema is not None else "online")
            else "online_best.pt"
        )
        with best_paths[kind].open("rb") as src, final.open("xb") as dst:
            shutil.copyfileobj(src, dst)
        reloaded, _ = load_t3(final)
        result = epoch(reloaded.to(device), val_loader)
        if result["confusion_matrix"] != best[kind][
            "confusion_matrix"
        ] or not math.isclose(
            result["loss"], best[kind]["loss"], rel_tol=1e-6, abs_tol=1e-7
        ):
            raise RuntimeError("Independent reload disagrees")
        streams[kind] = {
            "best_local_epoch": best_epochs[kind],
            "best_validation": result,
            "best_checkpoint": str(final.resolve()),
            "checkpoint_sha256": sha256(final),
            "reload_verified": True,
        }
    summary = {
        "name": name,
        "streams": streams,
        "epochs_completed": cfg["epochs"],
        "elapsed_seconds": time.perf_counter() - started,
        "private_test_used": False,
        "canonical_stream": "ema" if ema is not None else "online",
    }
    write_json(run / "summary.json", summary)
    print(json.dumps(summary), flush=True)
    return summary


def main():
    p = argparse.ArgumentParser()
    p.add_argument("config")
    a = p.parse_args()
    cfg = json.loads(Path(a.config).read_text())
    console = Path("results") / (cfg["name"] + ".console.log")
    if console.exists():
        raise FileExistsError("Existing console protected")
    # Keep actual stdout/stderr, with exclusive creation and no shell redirection.
    import contextlib

    with console.open("x", buffering=1) as f, contextlib.redirect_stdout(
        f
    ), contextlib.redirect_stderr(f):
        train(a.config)


if __name__ == "__main__":
    main()
