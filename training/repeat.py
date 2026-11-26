"""Freeze the seed42 winner, then repeat identical hyperparameters on seeds43/44."""

import json
from pathlib import Path
import subprocess
import sys

from training.baseline import write_json


def main():
    candidates = []
    for filename in ["a_cosine", "b_smooth_ema", "c_photo_smooth_ema"]:
        config_path = Path("configs/t35") / (filename + "_s42.json")
        cfg = json.loads(config_path.read_text())
        summary = json.loads(
            (Path("results") / cfg["name"] / "summary.json").read_text()
        )
        result = summary["streams"][summary["canonical_stream"]]["best_validation"]
        candidates.append(
            {
                "configuration": filename,
                "config_path": str(config_path),
                "accuracy": result["accuracy"],
                "loss": result["loss"],
                "macro_f1": result["macro_f1"],
            }
        )
    winner = max(candidates, key=lambda c: (c["accuracy"], -c["loss"]))
    write_json(
        "results/t35_final_20261030/repeat_selection.json",
        {
            "seed42_canonical_results": candidates,
            "winner": winner,
            "rule": "Highest seed42 canonical Accuracy; ties lower CE. Fixed winner before new seeds. No new hyperparameters.",
            "repeat_seeds": [43, 44],
            "matched_control_seed43": winner["configuration"] != "a_cosine",
        },
    )
    planned = [(winner["configuration"], 43), (winner["configuration"], 44)]
    if winner["configuration"] != "a_cosine":
        planned.append(("a_cosine", 43))
    for filename, seed in planned:
        cfg = json.loads((Path("configs/t35") / (filename + "_s42.json")).read_text())
        cfg["seed"] = seed
        cfg["name"] = cfg["name"].rsplit("_s", 1)[0] + "_s" + str(seed)
        config_path = Path("configs/t35") / (filename + "_s" + str(seed) + ".json")
        write_json(config_path, cfg)
        print("START", str(config_path), flush=True)
        subprocess.run(
            [sys.executable, "-u", "-m", "training.ema_finetune", str(config_path)],
            check=True,
        )
        print("DONE", str(config_path), flush=True)


if __name__ == "__main__":
    main()
