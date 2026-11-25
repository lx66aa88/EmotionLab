import unittest,tempfile
from pathlib import Path
import torch
from src.t37_models import ResNet18,load
from src.t37_train import lr_at,augment
from src.dataset import EmotionDataset,LABELS
class Checks(unittest.TestCase):
 def test_contract(self):
  torch.set_num_threads(4)
  self.assertEqual(LABELS,('Angry','Disgust','Fear','Happy','Sad','Surprise','Neutral'))
  with self.assertRaises(ValueError):EmotionDataset('/missing','PrivateTest')
  for w in (16,32):
   m=ResNet18(w);z=m(torch.rand(2,1,48,48));self.assertEqual(tuple(z.shape),(2,7));z.square().mean().backward()
   self.assertTrue(all(torch.isfinite(p.grad).all() for p in m.parameters() if p.grad is not None))
   with tempfile.TemporaryDirectory() as t:
    p=Path(t)/'cp.pt';torch.save(dict(format_version=37,config={'width':w},labels=LABELS,preprocessing='float32 / 255; [N,1,48,48]',model=m.state_dict()),p);m.eval();n,_=load(p);x=torch.rand(2,1,48,48);self.assertTrue(torch.equal(m(x),n(x)))
 def test_schedule_rng(self):
  self.assertEqual(lr_at(1,{}),.005);self.assertAlmostEqual(lr_at(5,{}),.05);self.assertAlmostEqual(lr_at(100,{}),.00001)
  self.assertTrue(all(lr_at(i,{})>lr_at(i+1,{}) for i in range(5,100)))
  a=torch.Generator().manual_seed(101);b=torch.Generator().manual_seed(101);x=torch.rand(4,1,48,48);self.assertTrue(torch.equal(augment(x,a),augment(x,b)))
if __name__=='__main__':unittest.main()
