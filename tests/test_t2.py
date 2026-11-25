"""Behavioral tests of training, split isolation, checkpointing and inference."""
import contextlib
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from src.dataset import EmotionDataset, LABELS
from src.model import BasicCNN, load_model
from src.predict import predict_tensor, preprocess_pixels
from src.train import TrainConfig, build_loader, is_better, run_epoch, set_seed, train


class CNNTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(2)

    def test_seven_logits_and_actual_learning(self):
        set_seed(42)
        model = BasicCNN()
        images = torch.zeros(7, 1, 48, 48)
        for label in range(7):
            images[label, :, label * 6:label * 6 + 6, :] = 1
        labels = torch.arange(7)
        criterion = nn.CrossEntropyLoss()
        model.eval()
        initial = criterion(model(images), labels).item()
        optimizer = torch.optim.Adam(model.parameters(), lr=0.005)
        for _ in range(20):
            optimizer.zero_grad()
            logits = model(images)
            self.assertEqual(tuple(logits.shape), (7, 7))
            loss = criterion(logits, labels)
            loss.backward()
            optimizer.step()
        self.assertLess(criterion(model(images), labels).item(), initial * 0.6)
        with self.assertRaises(ValueError):
            model(torch.zeros(2, 3, 48, 48))

    def test_validation_is_frozen_and_sample_weighted(self):
        # Unequal final batch: accuracy must be 2/3, not mean(1, 0)=1/2.
        model = BasicCNN()
        with torch.no_grad():
            for parameter in model.parameters():
                parameter.zero_()
            model.classifier[-1].bias[0] = 2
        images = torch.zeros(3, 1, 48, 48)
        labels = torch.tensor([0, 0, 1])
        loader = DataLoader(TensorDataset(images, labels), batch_size=2)
        before = {key: value.clone() for key, value in model.state_dict().items()}
        result = run_epoch(model, loader, nn.CrossEntropyLoss(), torch.device('cpu'))
        self.assertEqual(result['correct'], 2)
        self.assertEqual(result['accuracy'], 2 / 3)
        expected = nn.CrossEntropyLoss()(model(images), labels).item()
        self.assertAlmostEqual(result['loss'], expected, places=6)
        self.assertFalse(model.training)
        self.assertTrue(all(p.grad is None for p in model.parameters()))
        for key, value in model.state_dict().items():
            self.assertTrue(torch.equal(value, before[key]))

    def test_checkpoint_selection_rule(self):
        previous = {'accuracy': 0.5, 'loss': 1.0}
        self.assertTrue(is_better({'accuracy': 0.6, 'loss': 1.2}, previous))
        self.assertTrue(is_better({'accuracy': 0.5, 'loss': 0.9}, previous))
        self.assertFalse(is_better({'accuracy': 0.4, 'loss': 0.1}, previous))
        self.assertFalse(is_better(previous, previous))

    def test_prediction_preprocessing_and_invalid_inputs(self):
        image = preprocess_pixels(np.full((48, 48), 255, dtype=np.uint8))
        self.assertEqual(image.dtype, torch.float32)
        self.assertEqual(tuple(image.shape), (1, 48, 48))
        self.assertTrue(torch.all(image == 1))
        model = BasicCNN()
        result = predict_tensor(model, image)[0]
        self.assertEqual(tuple(result['probabilities']), LABELS)
        self.assertAlmostEqual(sum(result['probabilities'].values()), 1.0, places=6)
        self.assertEqual(result['emotion'], LABELS[result['label']])
        self.assertEqual(result, predict_tensor(model, image)[0])
        for bad in [np.zeros((47, 48)), np.full((48, 48), np.nan),
                    np.full((48, 48), 256), np.full((48, 48), -1)]:
            with self.assertRaises(ValueError):
                preprocess_pixels(bad)
        for bad in [torch.zeros(1, 1, 48, 48, dtype=torch.float64),
                    torch.full((1, 1, 48, 48), float('nan')),
                    torch.full((1, 1, 48, 48), 2.0), torch.zeros(0, 1, 48, 48)]:
            with self.assertRaises(ValueError):
                predict_tensor(model, bad)

    def test_end_to_end_save_reload_predict_and_private_isolation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'tiny.csv'
            with path.open('w', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(['emotion', 'Usage', 'pixels'])
                for split, repeats in [('Training', 2), ('PublicTest', 1)]:
                    for _ in range(repeats):
                        for label in range(7):
                            pixels = np.zeros((48, 48), dtype=np.uint8)
                            pixels[label * 6:label * 6 + 6] = 255
                            writer.writerow([label, split, ' '.join(map(str, pixels.flatten()))])
                # Any attempt to interpret these reserved fields must fail.
                writer.writerow(['INVALID', 'PrivateTest', 'INVALID'])
            config = TrainConfig(str(path), str(root / 'run'), str(root / 'weights'),
                                 epochs=2, batch_size=5, threads=2)
            with contextlib.redirect_stdout(io.StringIO()):
                summary = train(config)
            self.assertTrue(summary['reload_verified'])
            self.assertEqual(summary['best_validation'], summary['reloaded_validation'])
            self.assertEqual(summary['best_validation']['samples'], 7)
            self.assertFalse(summary['private_test_used'])
            metadata = json.loads((root / 'run/config.json').read_text())
            self.assertEqual(metadata['train_samples'], 14)
            self.assertEqual(metadata['val_samples'], 7)
            rows = [json.loads(line) for line in (root / 'run/metrics.jsonl').read_text().splitlines()]
            selected = max(rows, key=lambda row: (row['val_accuracy'], -row['val_loss']))
            self.assertEqual(summary['best_epoch'], selected['epoch'])
            loaded, checkpoint = load_model(summary['best_checkpoint'])
            original, _ = load_model(root / f"weights/epoch_{summary['best_epoch']:03d}.pt")
            images, _ = next(iter(build_loader(path, 'PublicTest', 5)))
            self.assertTrue(torch.equal(loaded(images), original(images)))
            self.assertEqual(len(predict_tensor(loaded, images)), 5)
            for split in ['PrivateTest', 'unknown']:
                with self.assertRaises(ValueError):
                    build_loader(path, split, 2)
            # Inference preprocessing agrees exactly with the T1 loader.
            dataset = EmotionDataset(path, 'PublicTest')
            raw = np.zeros((48, 48), dtype=np.uint8)
            raw[:6] = 255
            self.assertTrue(torch.equal(dataset[0][0], preprocess_pixels(raw)))
            checkpoint['labels'] = list(reversed(LABELS))
            bad_path = root / 'incompatible.pt'
            with bad_path.open('xb') as file:
                torch.save(checkpoint, file)
            with self.assertRaises(ValueError):
                load_model(bad_path)
            existing_summary = (root / 'run/summary.json').read_bytes()
            with self.assertRaises(FileExistsError):
                train(config)
            self.assertEqual(existing_summary, (root / 'run/summary.json').read_bytes())


if __name__ == '__main__':
    unittest.main()
