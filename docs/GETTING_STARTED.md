# Install and run

## Environment

The pinned target verified for this archive is macOS 27.0.1 arm64, CPython 3.9.6, PyTorch 2.8.0, NumPy 2.0.2, Pillow 11.3.0, FastAPI 0.115.14, Uvicorn 0.34.3, OpenCV headless 4.11.0.86, Node 24.22.1, npm 11.19.1, React 19.2 and Vite 7.2.2. Vite 7 also documents a Node 20.19+ or 22.12+ floor. Other OS/toolchain combinations need independent checks. Standard JPEG/PNG and the 48 × 48 CLI work without the ImageIO binary.

### Standalone art gallery

The gallery is one way to explore a freshly cloned archive before obtaining classifier files.

```sh
npm ci
npm run gallery -- --port 8786
```

Open `http://127.0.0.1:8786/`. Use the class chooser and motion controls.

### Classifier files

Install within a new virtual environment from the repository root.

```sh
python3.9 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-web.txt
python -m evaluation.cli results
```

The last command verifies the historical summary and prints PublicTest data from disk. It needs no checkpoint. Use `requirements-inference.txt` for the classifier CLI only. `requirements.txt` preserves the original minimal training record.

For inference, request an authorized transfer from the project maintainers. The repository provides file names and SHA-256 checks in [the frozen manifest](../configs/inference/best_triple.json). There is currently no public download route for the three classifier checkpoints. Place the exact artifacts as follows:

```text
checkpoints/t3_06_unweighted_s42/best.pt
checkpoints/t37_w16_s101/best.pt
checkpoints/t37_w32_s101/best.pt
```

The included YuNet ONNX is a separate face locator. Its provenance and MIT notice are in [models](../models/face_detection_yunet/). The original CSV is unnecessary for CLI, web and gallery. For lawful dataset acquisition and preparation, see [data pipeline](DATA_PIPELINE.md).

### Image CLI

```sh
python -m evaluation.cli check
python examples/make_smoke_image.py smoke-48.png
python -m evaluation.cli predict --image smoke-48.png
```

The smoke file is an original synthetic grayscale pattern. It has no ground truth. A real CLI prediction needs an authorized, already cropped 48 × 48 L-mode image or a compatible 48 × 48 NumPy array.

### Integrated product

From the root, with the venv active and the authorized checkpoints installed:

```sh
npm ci
npm run build
python -m backend.server --port 8797
```

Open `http://127.0.0.1:8797/`. The experiments page is `http://127.0.0.1:8797/experiments/`. Upload a JPEG/PNG you have permission to process. Click the camera button in LIVE or the challenge if you want camera input. Stop the service with Ctrl+C. The backend registers all routes before mounting the frontend assets.

## Tests and recovery

```sh
python -m unittest discover -s tests -t . -v
npm test
```

Some frozen-checkpoint assertions skip when the files are absent. See [validation](TESTING_AND_VALIDATION.md) for the verified scope.

| Symptom | Check |
| --- | --- |
| `python3.9` unavailable or wheel resolution fails | Use a local interpreter of the tested architecture/version. Check `python -m pip check` in the new venv. |
| Frontend builds but API returns a static 404 | Use the backend URL above for the integrated app. `vite preview` alone serves only static assets. |
| Checkpoint checksum or configuration rejected | Compare exact files to the frozen manifest. Have the maintainer review the approved artifacts. |
| Camera option unavailable | Open the local loopback URL, check browser permission and close other camera consumers. |
| Serve port already in use | Use another unused loopback port and the same port in the browser. |
| HEIC/HEIF or fallback TIFF conversion fails | The optional adapter requires a matching macOS arm64 decoder binary and platform sandbox. The bundled Swift source and [historical build record](../native/t53/BUILD.json) document it. Use JPEG/PNG as the portable path. |
| Older staged UI shows unavailable sample thumbnails | The T7.2 entry uses user upload; pre-T7 sample-browsing endpoints depend on classroom-only example image files. |
