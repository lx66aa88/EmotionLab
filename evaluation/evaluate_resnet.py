import argparse
from model_design.resnet18 import load
from training.resnet_experiment import evaluate
from training.cnn_experiment import load_split,sha256
from training.baseline import write_json
import torch
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('checkpoint');p.add_argument('--csv',default='data/icml_face_data_副本.csv');p.add_argument('--split',choices=['Training','PublicTest'],default='PublicTest');p.add_argument('--output',required=True);a=p.parse_args();torch.set_num_threads(4)
    model,cp=load(a.checkpoint)
    if sha256(a.csv)!=cp['data_sha256']:raise ValueError('Data mismatch')
    write_json(a.output,evaluate(model,load_split(a.csv,a.split),output=a.output+'.npz'))
