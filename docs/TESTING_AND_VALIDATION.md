# Testing and validation

Published tests exercise data shape and split handling, CPU inference and digest failures, photo decoding/crop guards, client framing and cancellation, classifier presentation, game state and the sculpture contract. Training-component tests can use tiny temporary datasets. Follow the commands below for a strictly inference-only release check.

```sh
PYTHONPATH=tests python -m unittest -v test_t1 test_t43_inference test_t52_faces
node --test web/human-signal/tests/*.test.mjs web/human-signal/seven-signals/tests/contract.test.mjs
```

| Evidence | Verified behavior | Conditions |
| --- | --- | --- |
| T4 unified inference | Manifest/hash rejection, model reconstruction, independent reload and probability equivalence | Original allowed validation and fixed inputs |
| T5 PHOTO/LIVE | Gray crop agreement, image size/format paths, no-face and multi-face states, stale frame, busy serialization and capture release | Historical model, compatibility and browser acceptance recorded separately |
| T6 Seven Signals | Label/index alignment, standalone selection, pause, reduced-motion support, raw/smoothed presentation and separate freeze | Contract tests plus visual/browser review |
| T7 challenge | Seven rounds, timer and retry branches, stale/ambiguous inputs, exact score ledger and closed track | T7.2 controlled 200/700, T7.3 11 controlled games / 77 rounds / 631.59 s |
| T8 local release | Build, health, PHOTO recovery, LIVE, separate freeze, track stop, four original charts and process recovery | T8.3 physical Chrome LIVE/freeze and camera release; T8.4 controlled browser flows and process-level network isolation. Safari physical-camera coverage remained open |
| T9 freeze | Exact release/model identifiers, synthetic evaluation and historical cache agreement | No final independent test result |
| T10 review | 26 frozen inference tests, 43 selected frontend/art tests, 6/6 dataset-independent weight/config hashes, aggregate metric recomputation | Historical local record, no official mixed CSV read |
| T11 archive checks | Fresh dependency install and both Vite builds, 40 Python tests with authorized local checkpoints, 55 Node unit tests, CLI status/results/predict | Separate venv and publish copy on macOS arm64. Browser results and source details are in the [product gallery](PRODUCT_GALLERY.md) |

The release copy replaces classroom photos and sample-dependent probabilities in frontend logic tests with geometric images or explicitly synthetic vectors. The optional historical native decoder suite needs separate original fixtures and its approved helper. The release Python inference suite can run without checkpoints, with real-weight cases skipped. Aggregate metrics were recomputed from the retained confusion matrix. T11 used synthetic and authorized fixture inputs and left the frozen weights unchanged.

Physical classroom use, other machines, Safari with a physical participant and physical network disconnection need their own acceptance. See [limitations](LIMITATIONS.md).
