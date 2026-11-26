"""Plot selected historical PublicTest results from the published aggregate table."""
import argparse
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "results/t4_step2_analysis_20261104/data/model_comparison.csv"
MILESTONES = (
    ("t2_baseline_20261030", "T2 · BasicCNN"),
    ("t3_04_bn_aug_mps_s42", "T3 · CNN + BN"),
    ("t3_05_resnet_aug_mps_s42", "T3 · Residual parent"),
    ("t3_06_unweighted_s42", "T3 · Selected fine-tune"),
    ("t37_w16_s101", "T3.7 · w16"),
    ("t37_w32_s101", "T3.7 · w32"),
    ("w32_tta", "T3.8 · w32 + flip"),
    ("double_tta", "T3.8 · Two models + flip"),
    ("triple_tta", "T3.8 · Three models + flip"),
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    with SOURCE.open(encoding="utf-8-sig") as stream:
        rows = {row["id"]: row for row in csv.DictReader(stream)}
    values = [float(rows[key]["accuracy"]) * 100 for key, _ in MILESTONES]
    assert all(rows[key]["split"] == "PublicTest" and rows[key]["samples"] == "3589"
               for key, _ in MILESTONES)

    background, foreground, grid = "#151917", "#f4f2e9", "#3d4940"
    fig, ax = plt.subplots(figsize=(12.2, 6.4), dpi=160)
    fig.patch.set_facecolor(background)
    ax.set_facecolor(background)
    fig.subplots_adjust(left=.27, right=.91, top=.77, bottom=.17)
    fig.text(.065,.92,"HISTORICAL VALIDATION  /  PUBLICTEST",family="monospace",
             fontsize=10, color="#d2f08a", weight="bold")
    fig.text(.065,.842,"From the first CNN to the frozen ensemble",
             fontsize=23,color=foreground,weight="bold")
    for index, value in enumerate(values):
        highlight = index == len(values)-1
        ax.hlines(index,50,value,color="#72806e" if not highlight else "#bedc79", linewidth=1.1)
        ax.scatter(value,index,s=90 if highlight else 45,c="#d2f08a" if highlight else "#c8cbbf",zorder=3)
        ax.text(value+.52,index,f"{value:.2f}%",va="center",fontsize=10, color=foreground,weight="bold" if highlight else "normal")
    ax.set_yticks(range(len(values)),[label for _,label in MILESTONES],fontsize=10)
    ax.set_xlim(50,77)
    ax.set_ylim(-.6,len(values)-.4)
    ax.invert_yaxis()
    ax.xaxis.set_major_formatter(PercentFormatter(xmax=100,decimals=0))
    ax.tick_params(axis="both",color=grid,labelcolor=foreground,length=0,pad=9)
    ax.xaxis.grid(color=grid,linewidth=.65)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_visible(False)
    fig.text(.065,.058,
             "Same 3,589 validation records · Selected milestones, varied training budgets and inference setups.",
             color="#b6bfb3",fontsize=9)
    with args.output.open("xb") as stream:
        fig.savefig(stream,format="png",facecolor=background)


if __name__ == "__main__":
    main()
