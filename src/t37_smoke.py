"""Real batch CPU profiling and optimizer/RNG continuation check; no formal results."""
import time,json,resource,tempfile
from pathlib import Path
import torch
from src.t37_models import ResNet18
from src.t37_train import augment
from src.t3_train import load_split
from src.train import write_json

def main():
 torch.set_num_threads(4);data=load_split('data/icml_face_data_副本.csv','Training');x,y=data.tensors[0][:128],data.tensors[1][:128];rows=[]
 for w in (16,32):
  torch.manual_seed(101);m=ResNet18(w);o=torch.optim.SGD(m.parameters(),lr=.005,momentum=.9,nesterov=True,weight_decay=.0005);g=torch.Generator().manual_seed(20101);times=[]
  def step(model,opt,image):
   opt.zero_grad();loss=torch.nn.functional.cross_entropy(model(image),y);loss.backward()
   assert all(torch.isfinite(p.grad).all() for p in model.parameters() if p.grad is not None)
   opt.step();return loss.item()
  for i in range(8):
   t=time.perf_counter();loss=step(m,o,augment(x,g));times.append(time.perf_counter()-t)
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'resume.pt';torch.save({'model':m.state_dict(),'optimizer':o.state_dict(),'rng':torch.get_rng_state(),'aug':g.get_state()},p)
   cp=torch.load(p,weights_only=True);image=augment(x,g);step(m,o,image);expected={k:v.clone() for k,v in m.state_dict().items()}
   n=ResNet18(w);n.load_state_dict(cp['model']);opt=torch.optim.SGD(n.parameters(),lr=.005,momentum=.9,nesterov=True,weight_decay=.0005);opt.load_state_dict(cp['optimizer']);torch.set_rng_state(cp['rng']);g.set_state(cp['aug']);step(n,opt,augment(x,g))
   assert all(torch.equal(expected[k],v) for k,v in n.state_dict().items())
  row={'width':w,'parameters':sum(p.numel() for p in m.parameters()),'batch':128,'step_seconds':times,'steady_mean_seconds':sum(times[2:])/6,'process_peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'resume_exact_cpu':True,'last_smoke_loss':loss};rows.append(row);print(json.dumps(row),flush=True)
 write_json('results/t37_audit_20261030/smoke.json',{'device':'cpu','mps_available':torch.backends.mps.is_available(),'rows':rows,'note':'RSS process high water includes dataset and both profiling models; not GPU or isolated model memory. Smoke only.'})
if __name__=='__main__':main()
