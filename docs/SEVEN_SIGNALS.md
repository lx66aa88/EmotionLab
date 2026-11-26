# Seven Signals

Seven pieces turn the fixed class index into a ribbon sculpture. [`signals.js`](../frontend/seven-signals/signals.js) owns index, material palette, named form, timing, geometry construction and the Chinese visual note. [`geometry.js`](../frontend/seven-signals/geometry.js) turns centerline/width control points into ribbon surfaces. [`SignalSculpture.jsx`](../frontend/seven-signals/SignalSculpture.jsx) layers SVG paths, metallic gradients, and motion. Abstract forms are artistic associations with the classifier labels.

| Index and category | Piece | Shape and motion |
| --- | --- | --- |
| 0 Angry | Fault / 断层 | Staggered facets compress across an oblique axis before releasing |
| 1 Disgust | Recoil / 回折 | Off-center loops roll inward while leaving an open gap |
| 2 Fear | Filament / 牵丝 | Two groups of fine ribbons with offset movement along a long axis |
| 3 Happy | Bloom / 舒展 | Fan surfaces open from below, spread light, and gather again |
| 4 Sad | Fall / 沉降 | Long bowed ribbons hang and their weight appears to settle |
| 5 Surprise | Burst / 迸开 | Pointed forms expand quickly around a hollow center and fall back with gaps |
| 6 Neutral | Plane / 基面 | Layered horizontal loops retain composure while spacing shifts slightly |

The standalone [preview](../frontend/seven-signals/Preview.jsx) lets users select labels with arrows, Home and End. It ships without backend, model, camera or dataset access. Reduced motion and still display controls are provided. In the product, [`SevenSignals.jsx`](../frontend/src/components/SevenSignals.jsx) maps PHOTO, LIVE or frozen outcomes to the same library and adapts visual transitions to the observation state. T6.3 documented interaction, editorial and motion references in [credits](REFERENCES.md). [Gallery](PRODUCT_GALLERY.md) · [Run the standalone gallery](GETTING_STARTED.md).
