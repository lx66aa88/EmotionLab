# Experiment evidence

[Experiment interpretation](../docs/EXPERIMENTS.md) explains selection decisions. CSV metrics are fractions unless units say otherwise. Matrix rows are actual labels and columns are predictions.

| Evidence | Location |
| --- | --- |
| 32-way comparison and cost | [Full comparison](../results/t4_step2_analysis_20261104/data/model_comparison.csv) · [training costs](../results/t4_step2_analysis_20261104/data/all_training_results.csv) · [inference costs](../results/t4_step2_analysis_20261104/data/inference_cost.csv) |
| Epoch history | [Per-epoch table](../results/t4_step2_analysis_20261104/data/training_epochs.csv) · [T2](../results/t2_baseline_20261030/) · [T3](../results/t3_06_unweighted_s42/) · [T3.5](../results/t35_c_photo_smooth_ema_s42/) · [w16](../results/t37_w16_s101/) · [w32](../results/t37_w32_s101/) |
| Accuracy | [Training](../results/t4_step2_analysis_20261104/figures/train_accuracy.png) · [PublicTest](../results/t4_step2_analysis_20261104/figures/public_accuracy.png) |
| Ordinary CE and scheduler | [Training CE](../results/t4_step2_analysis_20261104/figures/train_loss_ce.png) · [PublicTest CE](../results/t4_step2_analysis_20261104/figures/public_loss_ce.png) · [learning rates](../results/t4_step2_analysis_20261104/figures/learning_rates.png) |
| Comparative curves | [T2](../results/t4_step2_analysis_20261104/figures/key_1.png) · [T3](../results/t4_step2_analysis_20261104/figures/key_2.png) · [w16](../results/t4_step2_analysis_20261104/figures/key_3.png) · [w32](../results/t4_step2_analysis_20261104/figures/key_4.png) · [T3 recipes](../results/t4_step2_analysis_20261104/figures/t3_all_curves.png) · [T3.5](../results/t4_step2_analysis_20261104/figures/t35_all_curves.png) |
| Errors and class support | [Counts](../results/t4_step2_analysis_20261104/data/confusion_counts.csv) · [normalized](../results/t4_step2_analysis_20261104/data/confusion_normalized.csv) · [per class](../results/t4_step2_analysis_20261104/data/best_per_class.csv) · [paired corrections](../results/t4_step2_analysis_20261104/data/paired_changes.csv) |
| Frozen runtime | [Manifest](../configs/inference/best_triple.json) · [archived summary](../results/t38_triple_tta_20261104/run01/summary.json) |

Original row-level predictions, input faces, interruption traces and course material remain in the controlled archive. This directory links aggregate evidence and existing per-epoch numeric logs.
