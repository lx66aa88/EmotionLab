# System architecture

```mermaid
flowchart LR
  A["Course CSV"] --> B["Parse rows / augment Training"]
  B --> C["Train CNNs in PyTorch"]
  C --> D["Select checkpoints on PublicTest"]
  D --> E["Frozen T3 + w16 + w32"]
  I["Photo or sampled camera frame"] --> J["Decode, YuNet box and square crop"]
  J --> K["48 × 48 gray input"]
  K --> L["CPU ensemble with horizontal flip"]
  E --> L
  L --> M["Seven-class probability distribution"]
  M --> N["HUMAN SIGNAL interface"]
```

Coursework begins with cropped grayscale faces. Product input adapters also handle ordinary photos and sampled camera frames. These paths converge at the same tensor normalization and classifier.

```mermaid
flowchart TD
  R["React App"] --> P["PhotoStudy"]
  R -->|"Permission and sampling"| V["LiveSession"]
  P -->|"Detect, confirm, inspect, analyze"| S["Loopback FastAPI"]
  V -->|"POST /api/live/frame"| S
  V -->|"Capture one frame"| F["FrozenAnalysis"]
  F -->|"Independently detect and analyze"| S
  S --> Q["YuNet where required, then frozen ensemble"]
  Q --> U["Seven-class readout"]
  U --> W["Seven Signals motion"]
  U -->|"LIVE raw frames"| G["T7.2 scoring"]
```

The [server](../backend/server.py) registers classification, face detection, optional photo conversion, live sampling and chart routes before mounting the production frontend. The [React shell](../frontend/src/App.jsx) switches modes. All modes share one process-local model ensemble.

| Route | Implementation | Output or role |
| --- | --- | --- |
| `GET /api/health` | T5.1 | Readiness, labels and stored validation summary |
| `POST /api/inspect`, `/api/analyze` | T5.1 | Gray input validation and streamed inference events |
| `GET /api/photo-info`, `POST /api/detect` | T5.2 | Bounded decoding and face/crop candidates |
| `GET /api/photo-compat`, `POST /api/prepare-photo` | T5.3 | Optional macOS ImageIO subprocess |
| `GET /api/live/info`, `POST /api/live/frame` | T5.4 | Frame observations, tracking and explicit status |
| `GET /experiments/` | T8.3 | Four allowlisted aggregate charts |

[Model structure](MODEL_ARCHITECTURE.md) · [Training](TRAINING_PIPELINE.md) · [Inference](ENSEMBLE_INFERENCE.md) · [Directory tree](REPOSITORY_TREE.md)
