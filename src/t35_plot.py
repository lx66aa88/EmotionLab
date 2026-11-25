"""Draw only recorded T3.5 metrics; no interpolation or fabricated epochs."""
import argparse
import json
import os
from pathlib import Path

os.environ.setdefault('MPLCONFIGDIR','/private/tmp/emotionlab_t35_mpl')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from src.dataset import LABELS


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--candidate',required=True)
    p.add_argument('--output-dir',default='results/t35_final_20261030')
    a=p.parse_args()
    out=Path(a.output_dir)
    curves=out/'learning_curves.png'
    confusion=out/'confusion_comparison.png'
    if curves.exists() or confusion.exists():raise FileExistsError('Plots already exist')
    fig,axes=plt.subplots(2,3,figsize=(15,8),sharex=True)
    for column,name in enumerate(['a_cosine','b_smooth_ema','c_photo_smooth_ema']):
        folder=Path('results')/('t35_'+name+'_s42')
        logs=[json.loads(s) for s in (folder/'metrics.jsonl').read_text().splitlines()]
        x=[v['local_epoch'] for v in logs]
        axes[0,column].plot(x,[v['train_accuracy']*100 for v in logs],label='Training (aug+dropout)',alpha=.6)
        axes[1,column].plot(x,[v['train_loss'] for v in logs],label='Training ordinary CE',alpha=.6)
        for kind in logs[0]['validation']:
            axes[0,column].plot(x,[v['validation'][kind]['accuracy']*100 for v in logs],label=kind+' Public')
            axes[1,column].plot(x,[v['validation'][kind]['loss'] for v in logs],label=kind+' Public')
        axes[0,column].axhline(68.34772917247144,color='gray',linestyle='--',label='T3 best')
        axes[0,column].axhline(70,color='green',linestyle=':',label='70%')
        axes[0,column].set_title(name+' seed42')
        for row in range(2):axes[row,column].grid(alpha=.2);axes[row,column].legend(fontsize=7)
        axes[1,column].set_xlabel('Fine-tuning epoch (common epoch50 parent)')
    axes[0,0].set_ylabel('Accuracy (%)')
    axes[1,0].set_ylabel('Ordinary cross-entropy')
    fig.tight_layout();fig.savefig(curves,dpi=150);plt.close(fig)
    old=json.loads(Path('results/t35_diagnosis_20261030/diagnosis.json').read_text())['models']['best56']['public_eval']
    new=json.loads(Path(a.candidate).read_text())
    fig,axes=plt.subplots(1,2,figsize=(14,6))
    for ax,result,title in zip(axes,[old,new],['T3 best 68.35%','T3.5 candidate %.2f%%'%(new['accuracy']*100)]):
        cm=np.array(result['confusion_matrix']);pct=cm/cm.sum(1,keepdims=True)
        ax.imshow(pct,cmap='Blues',vmin=0,vmax=1)
        ax.set_xticks(range(7),LABELS,rotation=45,ha='right');ax.set_yticks(range(7),LABELS)
        ax.set_xlabel('Predicted label');ax.set_ylabel('True label');ax.set_title(title)
        for i in range(7):
            for j in range(7):ax.text(j,i,f'{cm[i,j]}\n{pct[i,j]:.0%}',ha='center',va='center',fontsize=8,color='white' if pct[i,j]>.55 else 'black')
    fig.tight_layout();fig.savefig(confusion,dpi=150);plt.close(fig)


if __name__=='__main__':main()
