"""Inference-only regression tests; never import or execute a training entry point."""
import ast
import copy
import inspect
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import torch
from PIL import Image

from evaluation import fusion as math
from evaluation.inference import (Ensemble, InferenceError, ROOT, checked_file, preprocess_pixels,
                          read_image, read_manifest, saved_results, validate_checkpoint)


class FrozenMath(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)

    def test_original_functions_preserved(self):
        diff = json.loads((ROOT / 'results/t4_step3_inference_20261104/integration_diff.json').read_text())
        for row in diff['extracted_functions']:
            source = (ROOT / row['source']).read_text()
            function = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef)
                            and n.name == row['function'])
            old = ast.get_source_segment(source, function).replace('old.equal_probability_mean', 'equal_probability_mean')
            self.assertEqual(ast.dump(ast.parse(old)), ast.dump(ast.parse(inspect.getsource(getattr(math, row['function'])))))

    def test_equal_six_probabilities_and_not_logits(self):
        generator = torch.Generator().manual_seed(4311)
        logits = {k+s: torch.randn(3, 7, generator=generator, dtype=torch.float64) * 4
                  for k in ('w32', 't3', 'w16') for s in ('_raw', '_flip')}
        views = {k: z.log_softmax(1) for k, z in logits.items()}
        _, baseline, actual = math.calculate(views)
        self.assertTrue(torch.allclose(actual.exp(), sum(p.exp() for p in views.values()) / 6, atol=1e-15, rtol=0))
        self.assertFalse(torch.allclose(actual.exp(), (sum(logits.values()) / 6).softmax(1)))
        w16 = math.equal_probability_mean(views['w16_raw'], views['w16_flip'])
        self.assertFalse(torch.allclose(actual.exp(), (baseline.exp() + w16.exp()) / 2))

    def test_extreme_logits(self):
        p = torch.tensor([[10000., -10000., 0., 1., 2., 3., 4.]], dtype=torch.float64).log_softmax(1)
        self.assertTrue(torch.allclose(math.equal_three_model_mean(p, p, p), p, atol=1e-12, rtol=0))

    def test_invalid_probabilities_and_alignment(self):
        p = torch.zeros(3, 7, dtype=torch.float64).log_softmax(1)
        for args in [(p, p), (p, p, p[:1]), (p, p, p+1), (p, p, p*float('nan'))]:
            with self.subTest(shapes=[v.shape for v in args]), self.assertRaises(ValueError):
                math.equal_three_model_mean(*args)

    def test_horizontal_flip_is_width_axis(self):
        x = torch.arange(2304).float().reshape(1, 1, 48, 48) / 2304
        self.assertTrue(torch.equal(math.horizontal_flip(x)[0, 0, :, 0], x[0, 0, :, -1]))
        self.assertTrue(torch.equal(math.horizontal_flip(math.horizontal_flip(x)), x))


class InputContract(unittest.TestCase):
    def test_preprocessing_exact(self):
        values = (np.arange(2304) % 256).reshape(48, 48).astype(np.uint8)
        actual = preprocess_pixels(values)
        self.assertEqual(actual.shape, (1, 1, 48, 48))
        self.assertEqual(actual.dtype, torch.float32)
        self.assertTrue(torch.equal(actual.flatten(), torch.from_numpy(values.copy()).flatten().float() / 255))

    def test_invalid_pixels(self):
        for pixels in [np.zeros((47, 48)), np.zeros((48, 48, 3)), np.full((48,48), np.nan),
                       np.full((48,48), np.inf), np.full((48,48), -1), np.full((48,48), 256),
                       np.full((48,48), 'x'), np.zeros((48,48), dtype=bool)]:
            with self.subTest(shape=pixels.shape), self.assertRaises(InferenceError):
                preprocess_pixels(pixels)

    def test_png_npy_same_raw_pixels(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = (np.arange(2304) % 256).astype(np.uint8).reshape(48,48)
            Image.fromarray(raw).save(Path(tmp) / 'face.png')
            np.save(Path(tmp) / 'face.npy', raw)
            self.assertTrue(torch.equal(read_image(Path(tmp) / 'face.png'), read_image(Path(tmp) / 'face.npy')))

    def test_wrong_image_size_and_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name, array in [('color.png', np.zeros((48,48,3),dtype=np.uint8)),
                                ('large.png', np.zeros((49,48),dtype=np.uint8))]:
                p = Path(tmp) / name; Image.fromarray(array).save(p)
                with self.assertRaises(InferenceError): read_image(p)

    def test_missing_corrupt_and_pickle_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'bad.png'; p.write_bytes(b'invalid image')
            with self.assertRaises(InferenceError): read_image(p)
            with self.assertRaises(InferenceError): read_image(Path(tmp) / 'absent.png')
            p = Path(tmp) / 'object.npy'; np.save(p, np.array([{'x':1}], dtype=object))
            with self.assertRaises(InferenceError): read_image(p)

    def test_private_rejected_before_open(self):
        with patch('pathlib.Path.open', side_effect=AssertionError('must not open')):
            with self.assertRaisesRegex(ValueError, 'Only PublicTest'):
                math.load_public('does-not-exist.csv', split='PrivateTest')

    def test_other_split_payloads_not_parsed(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'synthetic.csv'
            p.write_text('emotion,Usage,pixels\nBAD,PrivateTest,BAD\nBAD,Training,BAD\n0,PublicTest,' + ' '.join(['0']*2304)+'\n')
            images, labels, *_ = math.load_public(p)
            self.assertEqual(images.shape, (1,1,48,48)); self.assertEqual(labels.tolist(), [0])


class FrozenContracts(unittest.TestCase):
    def test_labels_and_saved_metrics(self):
        m = read_manifest(); r = saved_results()
        self.assertEqual(m['labels'], ['Angry','Disgust','Fear','Happy','Sad','Surprise','Neutral'])
        self.assertEqual((r['metrics']['correct'], r['metrics']['samples']), (2606,3589))

    def test_manifest_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'configs/inference'; p.mkdir(parents=True)
            shutil.copy2(ROOT/'configs/inference/best_triple.json', p/'best_triple.json')
            with (p/'best_triple.json').open('a') as f: f.write(' ')
            with self.assertRaisesRegex(InferenceError, 'SHA-256'): read_manifest(tmp)

    def test_missing_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'configs/inference'; p.mkdir(parents=True)
            shutil.copy2(ROOT/'configs/inference/best_triple.json', p/'best_triple.json')
            with self.assertRaisesRegex(InferenceError, '文件缺失'): Ensemble(tmp)

    def test_corrupted_model_rejected_before_deserialization(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'configs/inference'; p.mkdir(parents=True)
            shutil.copy2(ROOT/'configs/inference/best_triple.json', p/'best_triple.json')
            s = read_manifest()['models'][0]; p=Path(tmp)/s['checkpoint']; p.parent.mkdir(parents=True)
            p.write_bytes(b'corrupt checkpoint')
            with patch('torch.load', side_effect=AssertionError('must reject before loading')):
                with self.assertRaisesRegex(InferenceError, 'SHA-256'): Ensemble(tmp)

    def test_metadata_rejects_wrong_config_labels_epoch(self):
        m = read_manifest(); s = m['models'][0]
        cp = {'format_version':s['format_version'],'epoch':s['epoch'],'labels':m['labels'],
              'preprocessing':m['preprocessing'],'data_sha256':m['data_sha256'],'config':s['config']}
        validate_checkpoint(cp, s, m)
        for key, value in [('format_version',3),('epoch',1),('labels',m['labels'][::-1]),
                           ('preprocessing','wrong'),('data_sha256','wrong'),('config',{'width':16})]:
            with self.subTest(key=key), self.assertRaises(InferenceError):
                validate_checkpoint({**cp, key:value}, s, m)

    def test_external_config_corruption(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'config.json';p.write_text('{}')
            with self.assertRaisesRegex(InferenceError, 'SHA-256'): checked_file(tmp,'config.json','a'*64)

    def test_entry_imports_no_training_modules(self):
        # These modules must remain independent of every study/train controller.
        for name in ['inference.py', 'fusion.py', 'cli.py']:
            tree=ast.parse((ROOT/'evaluation'/name).read_text())
            for node in ast.walk(tree):
                if isinstance(node,ast.ImportFrom):
                    self.assertNotIn('train',node.module or '')
                if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute):
                    self.assertNotIn(node.func.attr, ['backward','step','train'])


class RealModelInference(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if any(not (ROOT / model['checkpoint']).is_file()
               for model in read_manifest()['models']):
            raise unittest.SkipTest('Approved frozen weights are required for real-model tests.')
        cls.engine=Ensemble()
        cls.image=preprocess_pixels((np.arange(2304)%256).astype(np.uint8).reshape(48,48))

    def test_three_correct_models_load(self):
        self.assertEqual(list(self.engine.models), ['w32','t3','w16'])
        for key, model in self.engine.models.items():
            self.assertFalse(any(m.training for m in model.modules()))
            self.assertFalse(any(p.requires_grad for p in model.parameters()))

    def test_real_forward_eval_inference_mode_no_grad_no_update(self):
        observed=[]
        def hook(model, args, output):
            observed.append((model.training, torch.is_grad_enabled(),torch.is_inference_mode_enabled(), output.requires_grad))
        handles=[model.register_forward_hook(hook) for model in self.engine.models.values()]
        try:
            with patch.object(torch.Tensor,'backward',side_effect=AssertionError('training forbidden')):
                arrays, audit=self.engine.infer(self.image)
        finally:
            for handle in handles: handle.remove()
        self.assertEqual(observed, [(False,False,True,False)]*6)
        self.assertTrue(all(s['unchanged'] for s in audit['model_states'].values()))
        self.assertTrue(all(p.grad is None for model in self.engine.models.values() for p in model.parameters()))

    def test_repeated_real_input_bitwise_equal(self):
        a,_=self.engine.infer(self.image); b,_=self.engine.infer(self.image)
        for key in a: self.assertTrue(np.array_equal(a[key],b[key]),key)

    def test_seven_valid_ordered_probabilities(self):
        result=self.engine.predict(self.image)['predictions'][0]
        self.assertEqual([p['label'] for p in result['probabilities']],list(range(7)))
        self.assertEqual([p['emotion'] for p in result['probabilities']],read_manifest()['labels'])
        probs=np.array([p['probability'] for p in result['probabilities']])
        self.assertTrue(np.isfinite(probs).all());self.assertTrue((probs>=0).all());self.assertTrue((probs<=1).all())
        self.assertAlmostEqual(probs.sum(),1.,places=12);self.assertEqual(result['label'],int(probs.argmax()))

    def test_incompatible_structure_reports_clear_error(self):
        from model_design.resnet18 import load as original
        def incompatible(path):
            # Actual strict state_dict loader rejects the intentionally incompatible width.
            cp=torch.load(path,map_location='cpu',weights_only=True)
            cp['config']['width']=16
            with patch('model_design.resnet18.torch.load',return_value=cp): return original(path)
        with patch('evaluation.inference.load_t37',side_effect=incompatible):
            with self.assertRaisesRegex(InferenceError,'结构不兼容'): Ensemble()

    def test_bad_logits_are_rejected(self):
        model=self.engine.models['w32']
        with patch.object(model,'forward',return_value=torch.full((1,7),float('nan'))):
            with self.assertRaisesRegex(ValueError,'finite'): self.engine.infer(self.image)

    def test_training_mode_is_rejected(self):
        model=self.engine.models['w32']
        model.training=True
        try:
            with self.assertRaisesRegex(InferenceError,'eval'): self.engine.infer(self.image)
        finally: model.eval()


if __name__=='__main__':
    unittest.main()
