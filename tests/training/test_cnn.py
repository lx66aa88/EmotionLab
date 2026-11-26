"""T3 metric arithmetic, augmentation, model updates and split isolation."""
import csv
import math
import json
import os
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

import torch
from torch.utils.data import DataLoader, TensorDataset
from model_design.cnn_variants import make_model, load_t3
from training.cnn_experiment import augment, epoch, load_split, metrics_from_cm, train


class T3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)

    def test_metrics_missing_classes_and_known_errors(self):
        cm = torch.zeros(7, 7, dtype=torch.long)
        cm[0, 0], cm[0, 1], cm[1, 1] = 2, 1, 1
        m = metrics_from_cm(cm)
        self.assertEqual(m['accuracy'], .75)
        self.assertAlmostEqual(m['macro_f1'], (.8 + 2 / 3) / 7)
        self.assertEqual(m['per_class'][0]['support'], 3)

    def test_training_only_augmentation_preserves_input(self):
        x = torch.rand(16, 1, 48, 48)
        before = x.clone()
        torch.manual_seed(7)
        a = augment(x)
        torch.manual_seed(7)
        b = augment(x)
        self.assertTrue(torch.equal(a, b))
        self.assertTrue(torch.equal(x, before))
        self.assertFalse(torch.equal(a, x))
        self.assertEqual(a.shape, x.shape)
        self.assertTrue(bool((a >= 0).all() and (a <= 1).all()))

    def test_bn_validation_frozen_and_weighted_loss(self):
        torch.manual_seed(42)
        model = make_model('batchnorm')
        x, y = torch.rand(5, 1, 48, 48), torch.tensor([0, 1, 1, 2, 6])
        loader = DataLoader(TensorDataset(x, y), batch_size=3)
        before = {k: v.clone() for k, v in model.state_dict().items()}
        weights = torch.tensor([1., 2., 3., 4., 5., 6., 7.])
        m = epoch(model, loader, weights=weights)
        with torch.inference_mode():
            ce = torch.nn.functional.cross_entropy(model(x), y, reduction='none')
        self.assertAlmostEqual(m['loss'], ce.mean().item(), places=6)
        self.assertTrue(math.isclose(m['objective'], (ce * weights[y]).mean().item(), rel_tol=1e-6))
        for k, v in model.state_dict().items():
            self.assertTrue(torch.equal(before[k], v))
        self.assertEqual(m, epoch(model, loader, weights=weights))

    def test_models_seven_logits_and_gradients(self):
        for name in ['basic', 'batchnorm', 'resnet18_w16']:
            model = make_model(name)
            x, y = torch.rand(3, 1, 48, 48), torch.tensor([0, 3, 6])
            self.assertEqual(tuple(model(x).shape), (3, 7))
            before = next(model.parameters()).clone()
            optimizer = torch.optim.Adam(model.parameters(), lr=.001)
            epoch(model, DataLoader(TensorDataset(x, y), batch_size=3), optimizer, True)
            self.assertFalse(torch.equal(before, next(model.parameters())))

    def test_batchnorm_control_has_matched_initial_conv_and_linear_weights(self):
        torch.manual_seed(42)
        basic = make_model('basic')
        torch.manual_seed(42)
        bn = make_model('batchnorm')
        selected = lambda m: [layer for layer in m.modules()
                              if isinstance(layer, (torch.nn.Conv2d, torch.nn.Linear))]
        for left, right in zip(selected(basic), selected(bn)):
            self.assertTrue(torch.equal(left.weight, right.weight))
            self.assertTrue(torch.equal(left.bias, right.bias))

    def test_private_poison_skipped_and_loading_refused(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'data.csv'
            with p.open('w', newline='') as f:
                w = csv.writer(f)
                w.writerow(['emotion', 'Usage', 'pixels'])
                for split in ['Training', 'PublicTest']:
                    w.writerow([3, split, ' '.join(['128'] * 2304)])
                w.writerow(['DO NOT PARSE', 'PrivateTest', 'DO NOT PARSE'])
            for split in ['Training', 'PublicTest']:
                self.assertEqual(len(load_split(p, split)), 1)
            with self.assertRaises(ValueError):
                load_split(p, 'PrivateTest')

    def test_t3_training_save_reload_and_existing_directory_protection(self):
        previous = Path.cwd()
        try:
            with tempfile.TemporaryDirectory() as td:
                os.chdir(td)
                Path('results').mkdir()
                Path('checkpoints').mkdir()
                Path('src').mkdir()
                Path('synthetic.csv').write_text('synthetic fixture; not real data')
                cfg = {'name': 'test_run', 'csv_path': 'synthetic.csv', 'model': 'batchnorm',
                       'max_epoch': 2, 'learning_rate': .001, 'batch_size': 4, 'seed': 42,
                       'threads': 1, 'augmentation': True, 'class_weight_power': .5}
                Path('config.json').write_text(json.dumps(cfg))
                data = TensorDataset(torch.rand(8, 1, 48, 48), torch.arange(8) % 7)
                with patch('training.cnn_experiment.load_split', return_value=data) as mocked:
                    result = train('config.json')
                    self.assertEqual([c.args[1] for c in mocked.call_args_list], ['Training', 'PublicTest'])
                    self.assertTrue(result['reload_verified'])
                    model, cp = load_t3(result['best_checkpoint'])
                    self.assertIn('optimizer_state_dict', cp)
                    self.assertEqual(epoch(model, DataLoader(data, batch_size=4))['confusion_matrix'],
                                     result['best_validation']['confusion_matrix'])
                    with self.assertRaises(FileExistsError):
                        train('config.json')
        finally:
            os.chdir(previous)


if __name__ == '__main__':
    unittest.main()
