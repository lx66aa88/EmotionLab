# HUMAN SIGNAL product design

HUMAN SIGNAL means a visible signal from a classifier. The interface relates the source image, model input, seven scores, and visual interpretation so the viewer can follow how the signal was produced. Graphite and warm-white themes distinguish an observation workspace from the sculpture stage. Small status accents, including the brand's vivid green, mark active controls. Archivo carries the display hierarchy and IBM Plex Mono is used for timings, scores and technical labels. [Styles](../web/human-signal/src/) · [Credits](REFERENCES.md)

| Mode | User flow | Design decision |
| --- | --- | --- |
| PHOTO | Upload → orient/locate → choose the face when needed → confirm gray crop → analyze → show probabilities and sculpture | Expose the transformation from source photo to actual 48 × 48 input. Report decode and detector errors before inference |
| LIVE | Allow camera → sample loop → view raw or EMA probabilities → change target, pause analysis or close camera | Cap concurrent processing, discard stale observations and surface no-face, quality and transport states |
| FROZEN FRAME | Capture from preview → pause sampling → run a new detection/crop/prediction → inspect result → resume or close | Make timing and preprocessing inspectable. A separate single-frame path prevents a smoothed live score from being inherited |
| Seven Signals | Observe material and shape connected to the current class; use the standalone gallery to select any label | Artistic interpretation is explicit and optional |
| Expression Challenge | Enter on demand, start, receive a target, find a stable match, review round and final summaries | Show game target separately from detected raw evidence; preserve access to stop, pause, retry and restart |

[`AppT72.jsx`](../web/human-signal/src/AppT72.jsx) composes the release. [`PhotoStudy53.jsx`](../web/human-signal/src/components/PhotoStudy53.jsx), [`LiveStudy.jsx`](../web/human-signal/src/components/LiveStudy.jsx) and [`FrozenFrame.jsx`](../web/human-signal/src/components/FrozenFrame.jsx) give each state a distinct presentation. The production app stays on loopback and the photo/camera transient media are handled in memory by their intended paths. For media context and caption provenance see [gallery](PRODUCT_GALLERY.md).
