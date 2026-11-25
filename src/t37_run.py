"""Sequential frozen route-1 controller. Additional seeds require seed101 gate."""
import json,traceback
from pathlib import Path
import numpy as np
from src.t37_train import train
from src.t3_train import sha256,load_split
from src.train import write_json
OUT=Path('results/t37_audit_20261030')
def summary(w,s):return json.loads(Path(f'results/t37_w{w}_s{s}/summary.json').read_text())
def integrity():
 old=json.loads((OUT/'original_hashes.json').read_text()); checks={p:sha256(p)==h for p,h in old.items() if p!='PROJECT_STATUS.md'};write_json(OUT/('integrity_'+str(__import__('time').time_ns())+'.json'),checks)
 if not all(checks.values()):raise RuntimeError('Protected artifacts changed')
def main():
 try:
  integrity()
  for s in [101,202,303]:
   for w in [16,32]:
    name=f't37_w{w}_s{s}';path=Path('results')/name
    if (path/'summary.json').exists():continue
    train(f'configs/t37/w{w}_s{s}.json',resume=(Path('checkpoints')/name/'last.pt').exists())
   a,b=[summary(w,s)['best_validation'] for w in [16,32]]
   gate=b['accuracy']-a['accuracy']>=.005 and b['macro_f1']-a['macro_f1']>=-.005
   write_json(OUT/f'gate_seed{s}.json',{'passed':gate,'accuracy_delta':b['accuracy']-a['accuracy'],'f1_delta':b['macro_f1']-a['macro_f1']})
   if s==101 and not gate:break
  seeds=[s for s in [101,202,303] if Path(f'results/t37_w32_s{s}/summary.json').exists()]
  rows=[summary(w,s) for s in seeds for w in [16,32]]
  adopt=False; evidence={}
  if len(seeds)==3:
   a=[summary(16,s)['best_validation'] for s in seeds];b=[summary(32,s)['best_validation'] for s in seeds]
   new=np.load('results/t37_w32_s101/public_predictions.npz');old=np.load('results/t35_diagnosis_20261030/best56_public_logits.npz')
   if not np.array_equal(new['labels'],old['labels']):raise ValueError('Label ordering mismatch')
   data=load_split('data/icml_face_data_副本.csv','PublicTest');_,groups=np.unique(data.tensors[0].numpy().reshape(len(data),-1),axis=0,return_inverse=True)
   delta=(new['logits'].argmax(1)==new['labels']).astype(int)-(old['logits'].argmax(1)==old['labels']).astype(int)
   sums=np.bincount(groups,weights=delta);counts=np.bincount(groups);rng=np.random.default_rng(370101);boot=[]
   for _ in range(20000):
    idx=rng.integers(0,len(sums),len(sums));boot.append(sums[idx].sum()/counts[idx].sum())
   ci=np.quantile(boot,[.025,.975]).tolist()
   criteria={'matched_mean_accuracy_plus_1pp':np.mean([v['accuracy'] for v in b])-np.mean([v['accuracy'] for v in a])>=.01,'paired_positive_at_least_2':sum(y['accuracy']>x['accuracy'] for x,y in zip(a,b))>=2,'matched_f1_no_more_than_half_pp_drop':np.mean([v['macro_f1'] for v in b])-np.mean([v['macro_f1'] for v in a])>=-.005,'old_mean_accuracy_plus_half_pp':np.mean([v['accuracy'] for v in b])>=2453/3589+.005,'all_above_old':all(v['accuracy']>2453/3589 for v in b),'old_mean_f1_no_more_than_half_pp_drop':np.mean([v['macro_f1'] for v in b])>=.65979284-.005,'seed101_group_bootstrap_lower_positive':ci[0]>0}
   adopt=all(criteria.values());evidence={'criteria':criteria,'seed101_group_bootstrap_95pct':ci,'repeats':20000,'caveat':'Public selection reused; descriptive conservative adoption, no independent test claim'}
  write_json(OUT/'comparison.json',{'runs':rows,'adopt':adopt,'evidence':evidence,'private_test_used':False})
  integrity()
  text=['# T3.7 真实实验结果','',f'正式采用 w32：{adopt}。未满足全部标准时保留旧 T3 模型。','','|宽度|种子|Accuracy|Macro F1|CE|最佳轮次|权重 SHA256|','|---|---|---|---|---|---|---|']
  for r in rows:
   v=r['best_validation'];text.append(f"|{r['config']['width']}|{r['config']['seed']}|{v['accuracy']:.8%}|{v['macro_f1']:.8%}|{v['loss']:.8f}|{r['best_epoch']}|{r['sha256']}|")
  text+=['','旧 T3：Accuracy 68.347729%；Macro F1 65.979284%。','各类 Precision/Recall/F1、混淆矩阵见每项 summary.json；逐轮 LR、Loss、指标见 metrics.jsonl。',json.dumps(evidence,ensure_ascii=False,indent=2)]
  (OUT/'REPORT.md').write_text('\n'.join(text))
  with Path('PROJECT_STATUS.md').open('a') as f:f.write('\n\n## T3.7 — 完成\n\n'+ '\n'.join(text[2:])+'\n本轮到此停止，未进入 T4–T9，未使用 PrivateTest。\n')
 except BaseException:
  (OUT/'failure.txt').write_text(traceback.format_exc());raise
if __name__=='__main__':main()
