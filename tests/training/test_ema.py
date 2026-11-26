"""T3.5 tests: EMA math, BN isolation, smoothed objective, training artifacts."""
import json
import math
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import torch
from torch import nn
from torch.nn import functional as F
from torch.utils.data import DataLoader, TensorDataset

from model_design.cnn_variants import make_model
from training.ema_finetune import augment_t35, refresh_bn, train, training_epoch, update_ema
from training.cnn_experiment import sha256
from data_processing.dataset import LABELS
from evaluation.compare_runs import paired_comparison
import numpy as np


class T35Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)

    def test_ema_exact_math_no_gradients(self):
        left, right = nn.Linear(2, 1), nn.Linear(2, 1)
        with torch.no_grad():
            for p in left.parameters(): p.fill_(2)
            for p in right.parameters(): p.fill_(6)
        update_ema(left, right, .75)
        for p in left.parameters():
            self.assertTrue(torch.equal(p, torch.full_like(p, 3)))
            self.assertIsNone(p.grad)

    def test_bn_refresh_disables_dropout_freezes_parameters_uses_only_given_data(self):
        model = nn.Sequential(nn.BatchNorm2d(1), nn.Dropout(.9), nn.Flatten(), nn.Linear(2304, 7))
        before = [p.clone() for p in model.parameters()]
        x = torch.full((4, 1, 48, 48), .25)
        seen = []
        handle = model[1].register_forward_hook(lambda m, args, out: seen.append(m.training))
        refresh_bn(model, DataLoader(TensorDataset(x, torch.zeros(4).long()), batch_size=2))
        handle.remove()
        self.assertEqual(seen, [False, False])
        self.assertTrue(torch.allclose(model[0].running_mean, torch.tensor([.25])))
        self.assertEqual(model[0].momentum, .1)
        for p, old in zip(model.parameters(), before):self.assertTrue(torch.equal(p, old))
        self.assertFalse(model.training)

    def test_smoothing_objective_separate_from_ordinary_ce(self):
        torch.manual_seed(2)
        model = nn.Sequential(nn.Flatten(), nn.Linear(2304, 7))
        x, y = torch.rand(4, 1, 48, 48), torch.tensor([0, 2, 3, 6])
        loader = DataLoader(TensorDataset(x, y), batch_size=4)
        with patch('training.ema_finetune.augment_t35', side_effect=lambda x, _: x):
            expected = model(x).detach()
            m = training_epoch(model, loader, torch.optim.SGD(model.parameters(), lr=0), .05, False)
        self.assertAlmostEqual(m['loss'], F.cross_entropy(expected, y).item(), places=6)
        self.assertAlmostEqual(m['objective'], F.cross_entropy(expected, y, label_smoothing=.05).item(), places=6)

    def test_photometric_bounded_reproducible_nonmutating(self):
        x = torch.rand(8, 1, 48, 48); old = x.clone()
        torch.manual_seed(3); a = augment_t35(x, True)
        torch.manual_seed(3); b = augment_t35(x, True)
        self.assertTrue(torch.equal(a, b))
        self.assertTrue(torch.equal(x, old))
        self.assertTrue(bool((a >= 0).all() and (a <= 1).all()))

    def test_paired_statistics_known_discordant_cases(self):
        with tempfile.TemporaryDirectory() as td:
            y=np.zeros(100,dtype=np.int64)
            old=np.zeros((100,7));new=np.zeros((100,7))
            old[:,0]=1;new[:,0]=1
            old[:10,0]=0;old[:10,1]=1
            a,b=Path(td)/'old.npz',Path(td)/'new.npz'
            np.savez(a,logits=old,labels=y);np.savez(b,logits=new,labels=y)
            result=paired_comparison(a,b)
            self.assertEqual(result['new_correct_old_wrong'],10)
            self.assertEqual(result['old_correct_new_wrong'],0)
            self.assertAlmostEqual(result['accuracy_delta'],.1)
            self.assertAlmostEqual(result['mcnemar_exact_two_sided_p'],2/1024)
            self.assertGreater(result['paired_bootstrap_95pct'][0],0)
            same=paired_comparison(a,a)
            self.assertEqual(same['paired_bootstrap_95pct'],[0.,0.])
            self.assertEqual(same['mcnemar_exact_two_sided_p'],1.)

    def test_integration_two_streams_splits_reload_and_exclusive_output(self):
        previous = Path.cwd()
        try:
            with tempfile.TemporaryDirectory() as td:
                os.chdir(td)
                for root in ['results','checkpoints','src']:Path(root).mkdir()
                Path('synthetic.csv').write_text('fixture')
                cfg = dict(name='t35_test',csv_path='synthetic.csv',model='resnet18_w16',initialize_from='parent.pt',
                           epochs=2,learning_rate=.0001,min_lr=.00001,weight_decay=.0001,batch_size=4,
                           threads=1,device='cpu',seed=4,label_smoothing=.05,ema=True,ema_decay=.995,photometric=True)
                model = make_model('resnet18_w16')
                torch.save(dict(format_version=3,config={'model':'resnet18_w16'},labels=list(LABELS),epoch=50,
                                preprocessing='float32 / 255; [N,1,48,48]',data_sha256=sha256('synthetic.csv'),
                                model_state_dict=model.state_dict()), 'parent.pt')
                Path('config.json').write_text(json.dumps(cfg))
                data = TensorDataset(torch.rand(8,1,48,48),torch.arange(8)%7)
                with patch('training.ema_finetune.load_split', return_value=data) as load:
                    result=train('config.json')
                self.assertEqual([c.args[1] for c in load.call_args_list],['Training','PublicTest'])
                self.assertEqual(set(result['streams']),{'online','ema'})
                for stream in result['streams'].values(): self.assertTrue(stream['reload_verified'])
                with self.assertRaises(FileExistsError):train('config.json')
        finally:os.chdir(previous)


if __name__ == '__main__':unittest.main()
