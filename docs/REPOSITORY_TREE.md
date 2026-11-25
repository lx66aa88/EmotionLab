# Repository tree

[中文工程导航](INDEX.zh-CN.md) · [Setup](GETTING_STARTED.md) · [Experiment ledger](../experiments/README.md)

The tree is generated from the release index. Historical run names preserve the original evidence and runtime paths.

```text
EmotionLab/
├── assets/
│   ├── screenshots/
│   │   ├── challenge.png
│   │   ├── frozen.png
│   │   ├── home.png
│   │   ├── live.png
│   │   ├── photo.png
│   │   └── seven-signals.png
│   ├── accuracy-progression.png
│   ├── banner.svg
│   ├── README.md
│   ├── seven-signals-collection.png
│   └── seven-signals-motion.gif
├── configs/
│   ├── inference/
│   │   └── best_triple.json
│   ├── t3/
│   │   ├── 01_continue.json
│   │   ├── 02_augment.json
│   │   ├── 03_basic_aug_mps.json
│   │   ├── 04_bn_aug_mps.json
│   │   ├── 05_resnet_aug_mps.json
│   │   ├── 06_unweighted.json
│   │   ├── 07_weighted.json
│   │   ├── 08_unweighted_s43.json
│   │   └── 09_weighted_s43.json
│   ├── t35/
│   │   ├── a_cosine_s42.json
│   │   ├── a_cosine_s43.json
│   │   ├── b_smooth_ema_s42.json
│   │   ├── c_photo_smooth_ema_s42.json
│   │   ├── c_photo_smooth_ema_s43.json
│   │   └── c_photo_smooth_ema_s44.json
│   └── t37/
│       ├── w16_s101.json
│       ├── w16_s202.json
│       ├── w16_s303.json
│       ├── w32_s101.json
│       ├── w32_s202.json
│       └── w32_s303.json
├── docs/
│   ├── DATA_PIPELINE.md
│   ├── ENSEMBLE_INFERENCE.md
│   ├── EXPERIMENTS.md
│   ├── GAME_DESIGN.md
│   ├── GETTING_STARTED.md
│   ├── INDEX.zh-CN.md
│   ├── LIMITATIONS.md
│   ├── MODEL_ARCHITECTURE.md
│   ├── PRODUCT_DESIGN.md
│   ├── PRODUCT_GALLERY.md
│   ├── PROJECT_HISTORY.md
│   ├── PROJECT_HISTORY.zh-CN.md
│   ├── REFERENCES.md
│   ├── REPOSITORY_TREE.md
│   ├── REQUIREMENTS.md
│   ├── SEVEN_SIGNALS.md
│   ├── SYSTEM_ARCHITECTURE.md
│   ├── TEAM_AND_CONTRIBUTIONS.md
│   ├── TESTING_AND_VALIDATION.md
│   └── TRAINING_PIPELINE.md
├── examples/
│   ├── make_smoke_image.py
│   └── README.md
├── experiments/
│   └── README.md
├── models/
│   └── face_detection_yunet/
│       ├── face_detection_yunet_2023mar.onnx
│       ├── LICENSE
│       └── SOURCE.json
├── native/
│   └── t53/
│       ├── BUILD.json
│       ├── PhotoDecoder.swift
│       └── SOURCES.md
├── results/
│   ├── t2_baseline_20261030/
│   │   ├── metrics.jsonl
│   │   └── summary.json
│   ├── t35_a_cosine_s42/
│   │   ├── metrics.jsonl
│   │   └── summary.json
│   ├── t35_a_cosine_s43/
│   │   ├── metrics.jsonl
│   │   └── summary.json
│   ├── t35_b_smooth_ema_s42/
│   │   ├── metrics.jsonl
│   │   └── summary.json
│   ├── t35_c_photo_smooth_ema_s42/
│   │   ├── metrics.jsonl
│   │   └── summary.json
│   ├── t35_c_photo_smooth_ema_s43/
│   │   ├── metrics.jsonl
│   │   └── summary.json
│   ├── t35_c_photo_smooth_ema_s44/
│   │   ├── metrics.jsonl
│   │   └── summary.json
│   ├── t37_w16_s101/
│   │   ├── metrics.jsonl
│   │   └── summary.json
│   ├── t37_w32_s101/
│   │   ├── metrics.jsonl
│   │   └── summary.json
│   ├── t38_inference_20261030/
│   │   └── inference.py
│   ├── t38_triple_tta_20261104/
│   │   ├── run01/
│   │   │   └── summary.json
│   │   └── study.py
│   ├── t3_01_continue_s42/
│   │   ├── metrics.jsonl
│   │   └── summary.json
│   ├── t3_02_augment_s42/
│   │   ├── metrics.jsonl
│   │   └── summary.json
│   ├── t3_03_basic_aug_mps_s42/
│   │   ├── metrics.jsonl
│   │   └── summary.json
│   ├── t3_04_bn_aug_mps_s42/
│   │   ├── metrics.jsonl
│   │   └── summary.json
│   ├── t3_05_resnet_aug_mps_s42/
│   │   ├── metrics.jsonl
│   │   └── summary.json
│   ├── t3_06_unweighted_s42/
│   │   ├── metrics.jsonl
│   │   └── summary.json
│   ├── t3_07_weighted_s42/
│   │   ├── metrics.jsonl
│   │   └── summary.json
│   ├── t3_08_unweighted_s43/
│   │   ├── metrics.jsonl
│   │   └── summary.json
│   ├── t3_09_weighted_s43/
│   │   ├── metrics.jsonl
│   │   └── summary.json
│   ├── t4_step2_analysis_20261104/
│   │   ├── data/
│   │   │   ├── all_training_results.csv
│   │   │   ├── best_per_class.csv
│   │   │   ├── class_changes.csv
│   │   │   ├── class_support.csv
│   │   │   ├── confusion_counts.csv
│   │   │   ├── confusion_normalized.csv
│   │   │   ├── error_confusions.csv
│   │   │   ├── fixed_training_vs_public.csv
│   │   │   ├── inference_cost.csv
│   │   │   ├── main_comparison.csv
│   │   │   ├── model_comparison.csv
│   │   │   ├── paired_changes.csv
│   │   │   └── training_epochs.csv
│   │   └── figures/
│   │       ├── class_metrics.png
│   │       ├── class_recall_comparison.png
│   │       ├── class_support.png
│   │       ├── confusion_counts.png
│   │       ├── confusion_normalized.png
│   │       ├── fixed_eval_gap.png
│   │       ├── inference_cost.png
│   │       ├── key_1.png
│   │       ├── key_2.png
│   │       ├── key_3.png
│   │       ├── key_4.png
│   │       ├── learning_rates.png
│   │       ├── model_accuracy_f1.png
│   │       ├── model_ce.png
│   │       ├── model_training_cost.png
│   │       ├── paired_changes.png
│   │       ├── public_accuracy.png
│   │       ├── public_loss_ce.png
│   │       ├── t35_all_curves.png
│   │       ├── t3_all_curves.png
│   │       ├── train_accuracy.png
│   │       └── train_loss_ce.png
│   ├── t4_step3_inference_20261104/
│   │   └── integration_diff.json
│   └── README.md
├── scripts/
│   ├── plot_portfolio_accuracy.py
│   ├── start_t72.sh
│   └── t83_preflight.py
├── src/
│   ├── __init__.py
│   ├── audit.py
│   ├── check_environment.py
│   ├── classroom.py
│   ├── dataset.py
│   ├── ensemble.py
│   ├── ensemble_math.py
│   ├── model.py
│   ├── predict.py
│   ├── smoke_loader.py
│   ├── t35_compare.py
│   ├── t35_diagnose.py
│   ├── t35_evaluate.py
│   ├── t35_make_report.py
│   ├── t35_plot.py
│   ├── t35_repeat.py
│   ├── t35_select.py
│   ├── t35_train.py
│   ├── t37_evaluate.py
│   ├── t37_models.py
│   ├── t37_run.py
│   ├── t37_smoke.py
│   ├── t37_train.py
│   ├── t3_evaluate.py
│   ├── t3_models.py
│   ├── t3_plot.py
│   ├── t3_predict.py
│   ├── t3_run.py
│   ├── t3_train.py
│   ├── t3_verify.py
│   ├── t51_web.py
│   ├── t52_faces.py
│   ├── t52_web.py
│   ├── t53_photos.py
│   ├── t53_web.py
│   ├── t54_live.py
│   ├── t54_web.py
│   ├── t62_web.py
│   ├── t83_experiments.py
│   ├── train.py
│   └── validate.py
├── tests/
│   ├── test_t1.py
│   ├── test_t2.py
│   ├── test_t3.py
│   ├── test_t35.py
│   ├── test_t37.py
│   ├── test_t43_inference.py
│   ├── test_t52_faces.py
│   └── test_t53_photos.py
├── web/
│   └── human-signal/
│       ├── public/
│       │   ├── fonts/
│       │   │   ├── Archivo-OFL.txt
│       │   │   ├── Archivo-Variable.ttf
│       │   │   ├── IBMPlexMono-OFL.txt
│       │   │   └── IBMPlexMono-Regular.ttf
│       │   └── mark.svg
│       ├── seven-signals/
│       │   ├── tests/
│       │   │   └── contract.test.mjs
│       │   ├── geometry.js
│       │   ├── index.html
│       │   ├── main.jsx
│       │   ├── mark.svg
│       │   ├── preview.css
│       │   ├── Preview.jsx
│       │   ├── sculpture.css
│       │   ├── signals.js
│       │   ├── SignalSculpture.jsx
│       │   └── vite.config.js
│       ├── src/
│       │   ├── components/
│       │   │   ├── ExpressionChallenge.jsx
│       │   │   ├── ExpressionChallengeT72.jsx
│       │   │   ├── FrozenFrame.jsx
│       │   │   ├── LiveSpectrum.jsx
│       │   │   ├── LiveStudy.jsx
│       │   │   ├── PhotoStudy.jsx
│       │   │   ├── PhotoStudy53.jsx
│       │   │   ├── ProcessRail.jsx
│       │   │   ├── SevenSignals.css
│       │   │   ├── SevenSignals.jsx
│       │   │   ├── SignalField.jsx
│       │   │   ├── SignalSpectrum.jsx
│       │   │   └── Spectrum.jsx
│       │   ├── App.jsx
│       │   ├── AppT52.jsx
│       │   ├── AppT53.jsx
│       │   ├── AppT54.jsx
│       │   ├── AppT62.jsx
│       │   ├── AppT621.jsx
│       │   ├── AppT63.jsx
│       │   ├── AppT71.jsx
│       │   ├── AppT72.jsx
│       │   ├── challengeGame.js
│       │   ├── challengeGameT72.js
│       │   ├── challengeSignal.js
│       │   ├── frozenAnalysis.js
│       │   ├── liveSession.js
│       │   ├── main.jsx
│       │   ├── photoPreparation.js
│       │   ├── photoPreparation53.js
│       │   ├── signalPresentation.js
│       │   ├── styles-t52.css
│       │   ├── styles-t53.css
│       │   ├── styles-t54.css
│       │   ├── styles-t621.css
│       │   ├── styles-t63.css
│       │   ├── styles-t71.css
│       │   ├── styles-t72.css
│       │   ├── styles.css
│       │   └── useChallengeT72.js
│       ├── tests/
│       │   ├── fixtures/
│       │   │   ├── geometry.jpg
│       │   │   ├── geometry.png
│       │   │   ├── geometry.tiff
│       │   │   └── oriented.jpg
│       │   ├── liveSession.test.mjs
│       │   ├── photoPreparation.test.mjs
│       │   ├── photoPreparation53.test.mjs
│       │   ├── t62-signal.test.mjs
│       │   ├── t71-challenge.test.mjs
│       │   └── t72-challenge.test.mjs
│       ├── classroom-experiments.html
│       ├── index.html
│       ├── package-lock.json
│       ├── package.json
│       ├── vite.config.js
│       ├── vite.t53.config.js
│       ├── vite.t54.config.js
│       ├── vite.t62.config.js
│       ├── vite.t63.config.js
│       ├── vite.t71.config.js
│       └── vite.t72.config.js
├── .gitattributes
├── .gitignore
├── PROJECT_STATUS.md
├── README.md
├── README.zh-CN.md
├── requirements-inference.txt
├── requirements-t3-plots.txt
├── requirements-t51-web.lock.txt
├── requirements-t51-web.txt
├── requirements-t52-web.lock.txt
├── requirements-web.txt
└── requirements.txt
```
