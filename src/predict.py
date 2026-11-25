"""Predict a permitted CSV sample or an already cropped 48 x 48 .npy face."""
import argparse
import json
import numpy as np
import torch
from src.dataset import EmotionDataset, LABELS
from src.model import load_model
from src.train import select_device

LABELS_ZH = ('愤怒', '厌恶', '恐惧', '快乐', '悲伤', '惊喜', '中立')


def preprocess_pixels(pixels):
    """Same normalization as T1; caller supplies raw 0-255 grayscale values."""
    values = np.asarray(pixels)
    if (values.shape != (48, 48) or values.dtype.kind not in 'uif'
            or not np.isfinite(values).all() or values.min() < 0 or values.max() > 255):
        raise ValueError('Expected finite numeric 48 x 48 grayscale values in [0, 255]')
    return torch.from_numpy(values.astype(np.float32, copy=True)).unsqueeze(0).div_(255.0)


def predict_tensor(model, images):
    if images.ndim == 3:
        images = images.unsqueeze(0)
    if (images.ndim != 4 or tuple(images.shape[1:]) != (1, 48, 48)
            or images.shape[0] == 0 or images.dtype != torch.float32
            or not torch.isfinite(images).all() or images.min() < 0 or images.max() > 1):
        raise ValueError('Expected nonempty float32 [N,1,48,48] images in [0,1]')
    model.eval()
    with torch.inference_mode():
        probabilities = model(images.to(next(model.parameters()).device)).softmax(dim=1).cpu()
    results = []
    for scores in probabilities:
        label = scores.argmax().item()
        results.append({'label': label, 'emotion': LABELS[label], 'emotion_zh': LABELS_ZH[label],
                        'probability': scores[label].item(),
                        'probabilities': {name: scores[i].item() for i, name in enumerate(LABELS)}})
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('checkpoint')
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument('--csv-path')
    inputs.add_argument('--image-npy', help='Raw 0-255 values; no automatic face detection')
    parser.add_argument('--split', choices=['Training', 'PublicTest'], default='PublicTest')
    parser.add_argument('--index', type=int, default=0, help='Zero-based index within the split')
    parser.add_argument('--device', choices=['cpu', 'mps', 'cuda'], default='cpu')
    parser.add_argument('--threads', type=int, default=4)
    args = parser.parse_args()
    if args.threads < 1 or args.index < 0:
        parser.error('threads must be positive; index must be nonnegative')
    torch.set_num_threads(args.threads)
    model, checkpoint = load_model(args.checkpoint, select_device(args.device))
    if args.csv_path:
        dataset = EmotionDataset(args.csv_path, args.split)
        if args.index >= len(dataset):
            parser.error('index is out of range')
        image, label = dataset[args.index]
        output = {'split': args.split, 'index': args.index, 'true_label': label,
                  'true_emotion': LABELS[label]}
    else:
        image = preprocess_pixels(np.load(args.image_npy, allow_pickle=False))
        output = {'image_npy': args.image_npy}
    output.update(predict_tensor(model, image)[0])
    output['checkpoint_epoch'] = checkpoint['epoch']
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
