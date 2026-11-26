"""Predict a cropped raw 48x48 grayscale .npy image with a T3 checkpoint."""
import argparse
import json
import numpy as np
import torch
from evaluation.predict_baseline import preprocess_pixels, predict_tensor
from model_design.cnn_variants import load_t3
from training.baseline import select_device


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('checkpoint')
    p.add_argument('--image-npy', required=True)
    p.add_argument('--device', choices=['cpu', 'mps'], default='cpu')
    p.add_argument('--threads', type=int, default=4)
    a = p.parse_args()
    if a.threads < 1:
        p.error('threads must be positive')
    torch.set_num_threads(a.threads)
    model, cp = load_t3(a.checkpoint)
    model.to(select_device(a.device))
    image = preprocess_pixels(np.load(a.image_npy, allow_pickle=False))
    result = {**predict_tensor(model, image)[0], 'checkpoint_epoch': cp['epoch'],
              'model': cp['config']['model'], 'image_npy': a.image_npy,
              'note': 'Uncalibrated softmax scores; input must already be a cropped face.'}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
