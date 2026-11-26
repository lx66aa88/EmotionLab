"""Frozen T3.7 training, epoch-boundary resume and finite-gradient checks."""

from data_processing.augmentation import seeded_augment as augment
import argparse, json, math, time, shutil, platform
from pathlib import Path
import torch
from torch.nn import functional as F
from torch.utils.data import DataLoader
from data_processing.dataset import LABELS
from training.cnn_experiment import load_split, sha256, metrics_from_cm
from training.baseline import write_json
from model_design.resnet18 import ResNet18, load


def lr_at(epoch, c):
    if epoch <= 5:
        return 0.005 + (0.05 - 0.005) * (epoch - 1) / 4
    return 0.00001 + (0.05 - 0.00001) * 0.5 * (1 + math.cos(math.pi * (epoch - 5) / 95))


def evaluate(model, data, batch=128, output=None):
    model.eval()
    cm = torch.zeros(7, 7, dtype=torch.long)
    total = 0.0
    logits_all = []
    labels_all = []
    with torch.inference_mode():
        for x, y in DataLoader(data, batch_size=batch):
            logits = model(x.to(next(model.parameters()).device)).cpu()
            total += F.cross_entropy(logits, y, reduction="sum").item()
            cm += torch.bincount(y * 7 + logits.argmax(1), minlength=49).reshape(7, 7)
            logits_all.append(logits)
            labels_all.append(y)
    logits = torch.cat(logits_all)
    labels = torch.cat(labels_all)
    prob = logits.softmax(1)
    confidence, pred = prob.max(1)
    ece = 0.0
    for i in range(15):
        mask = (confidence > i / 15) & (confidence <= (i + 1) / 15)
        if mask.any():
            ece += mask.float().mean().item() * abs(
                confidence[mask].mean().item()
                - (pred[mask] == labels[mask]).float().mean().item()
            )
    result = {**metrics_from_cm(cm), "loss": total / len(data), "ece_15_bins": ece}
    if output:
        import numpy as np

        np.savez_compressed(output, logits=logits.numpy(), labels=labels.numpy())
    return result


def train(config, resume=False):
    c = json.loads(Path(config).read_text())
    run = Path("results") / c["name"]
    ck = Path("checkpoints") / c["name"]
    torch.set_num_threads(c["threads"])
    torch.manual_seed(c["seed"])
    torch.use_deterministic_algorithms(True)
    if not resume:
        if run.exists() or ck.exists():
            raise FileExistsError(c["name"])
        run.mkdir()
        ck.mkdir()
        shutil.copy(config, run / "config.json")
        shutil.copytree(
            "src", run / "source", ignore=shutil.ignore_patterns("__pycache__")
        )
    device = torch.device(c["device"])
    model = ResNet18(c["width"]).to(device)
    opt = torch.optim.SGD(
        model.parameters(), lr=0.005, momentum=0.9, nesterov=True, weight_decay=0.0005
    )
    order = torch.Generator().manual_seed(c["seed"] + 10000)
    aug = torch.Generator().manual_seed(c["seed"] + 20000)
    data = load_split(c["csv_path"], "Training")
    val = load_split(c["csv_path"], "PublicTest")
    data_hash = sha256(c["csv_path"])
    start = 1
    best = None
    best_epoch = None
    if resume:
        _, cp = load(ck / "last.pt")
        if cp["config"] != c or cp["data_sha256"] != data_hash:
            raise ValueError("Resume mismatch")
        model.load_state_dict(cp["model"])
        opt.load_state_dict(cp["optimizer"])
        torch.set_rng_state(cp["rng"])
        order.set_state(cp["order_rng"])
        aug.set_state(cp["aug_rng"])
        if device.type == "mps":
            torch.mps.set_rng_state(cp["mps_rng"])
        start = cp["epoch"] + 1
        best = cp["best"]
        best_epoch = cp["best_epoch"]
    write_json(
        run
        / (
            "environment_resume_" + str(time.time_ns()) + ".json"
            if resume
            else "environment.json"
        ),
        {
            "torch": str(torch.__version__),
            "platform": platform.platform(),
            "mps_available": torch.backends.mps.is_available(),
            "device": str(device),
            "parameters": sum(p.numel() for p in model.parameters()),
            "data_sha256": data_hash,
            "private_test_used": False,
        },
    )
    for ep in range(start, c["epochs"] + 1):
        t = time.perf_counter()
        lr = lr_at(ep, c)
        for group in opt.param_groups:
            group["lr"] = lr
        model.train()
        total = 0.0
        correct = 0
        count = 0
        for x, y in DataLoader(data, batch_size=128, shuffle=True, generator=order):
            x = augment(x, aug).to(device)
            y = y.to(device)
            opt.zero_grad(set_to_none=True)
            z = model(x)
            loss = F.cross_entropy(z, y)
            if not torch.isfinite(loss):
                raise RuntimeError("Nonfinite loss")
            loss.backward()
            if not all(
                torch.isfinite(p.grad).all().item()
                for p in model.parameters()
                if p.grad is not None
            ):
                raise RuntimeError("Nonfinite gradient")
            opt.step()
            total += loss.item() * len(y)
            correct += (z.argmax(1) == y).sum().item()
            count += len(y)
        v = evaluate(model, val)
        better = best is None or (v["accuracy"], -v["loss"]) > (
            best["accuracy"],
            -best["loss"],
        )
        if better:
            best = v
            best_epoch = ep
        row = {
            "epoch": ep,
            "lr": lr,
            "train_loss": total / count,
            "train_accuracy": correct / count,
            "train_samples": count,
            "validation": v,
            "seconds": time.perf_counter() - t,
        }
        with (run / "metrics.jsonl").open("a") as f:
            f.write(json.dumps(row) + "\n")
        cp = {
            "format_version": 37,
            "config": c,
            "labels": list(LABELS),
            "preprocessing": "float32 / 255; [N,1,48,48]",
            "data_sha256": data_hash,
            "epoch": ep,
            "model": model.state_dict(),
            "optimizer": opt.state_dict(),
            "rng": torch.get_rng_state(),
            "order_rng": order.get_state(),
            "aug_rng": aug.get_state(),
            "mps_rng": torch.mps.get_rng_state() if device.type == "mps" else None,
            "best": best,
            "best_epoch": best_epoch,
            "scheduler": {
                "granularity": "epoch start",
                "completed_epoch": ep,
                "lr": lr,
            },
        }
        torch.save(cp, ck / "last.tmp")
        (ck / "last.tmp").replace(ck / "last.pt")
        if better:
            shutil.copyfile(ck / "last.pt", ck / f"epoch_{ep:03d}.pt")
            shutil.copyfile(ck / "last.pt", ck / "best.pt")
        print(json.dumps({"name": c["name"], **row}), flush=True)
    final_train = evaluate(model, data)
    write_json(run / "last_training_eval.json", final_train)
    model, cp = load(ck / "best.pt")
    model.to(device)
    v = evaluate(model, val, output=run / "public_predictions.npz")
    if (
        v["confusion_matrix"] != best["confusion_matrix"]
        or abs(v["loss"] - best["loss"]) > 1e-5
    ):
        raise RuntimeError("Reload mismatch")
    write_json(run / "best_training_eval.json", evaluate(model, data))
    write_json(
        run / "summary.json",
        {
            "config": c,
            "best_epoch": best_epoch,
            "best_validation": v,
            "checkpoint": str(ck / "best.pt"),
            "sha256": sha256(ck / "best.pt"),
            "epochs_completed": c["epochs"],
            "private_test_used": False,
        },
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("config")
    p.add_argument("--resume", action="store_true")
    a = p.parse_args()
    train(a.config, a.resume)
