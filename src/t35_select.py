"""Apply the recorded conservative T3.5 adoption policy to completed evidence."""
import json
from pathlib import Path
import statistics

from src.t3_train import sha256
from src.train import write_json


def main():
    out=Path('results/t35_final_20261030')
    rows=json.loads((out/'comparison.json').read_text())
    pairs=json.loads((out/'paired_comparisons.json').read_text())
    repeat=json.loads((out/'repeat_selection.json').read_text())
    winner='t35_'+repeat['winner']['configuration']
    repeats=[r for r in rows if r['canonical'] and r['name'].rsplit('_s',1)[0]==winner]
    if {r['seed'] for r in repeats}!={42,43,44}:raise ValueError('Missing predeclared repeat seeds')
    old=next(r for r in rows if r['name']=='t3_06_unweighted_s42')
    criterion={
        'all_three_seeds_above_old_best':all(r['accuracy']>old['accuracy'] for r in repeats),
        'mean_accuracy_above_old_best':statistics.mean(r['accuracy'] for r in repeats)>old['accuracy'],
        'seed42_paired_interval_lower_above_zero':pairs[winner+'_s42']['paired_bootstrap_95pct'][0]>0}
    adopted=all(criterion.values())
    selected=max(repeats,key=lambda r:(r['accuracy'],-r['loss'])) if adopted else old
    highest=max(rows,key=lambda r:(r['accuracy'],-r['loss']))
    grouped={}
    for base in ['t35_a_cosine','t35_b_smooth_ema','t35_c_photo_smooth_ema']:
        r=[v for v in rows if v['canonical'] and v['name'].rsplit('_s',1)[0]==base]
        grouped[base]={'seeds':[v['seed'] for v in r],'n':len(r)}
        for metric in ['accuracy','macro_f1','loss','elapsed_seconds']:
            vals=[v[metric] for v in r]
            grouped[base][metric+'_mean']=statistics.mean(vals)
            grouped[base][metric+'_sample_std']=statistics.stdev(vals) if len(vals)>1 else None
        grouped[base]['accuracy_min']=min(v['accuracy'] for v in r)
        grouped[base]['accuracy_max']=max(v['accuracy'] for v in r)
    new_rows=[r for r in rows if r['name'].startswith('t35_')]
    costs={r['name']:r['elapsed_seconds'] for r in new_rows}
    updates={r['name']:r['epochs_completed'] for r in new_rows}
    result={'current_selected_model':selected,'current_checkpoint_sha256':sha256(selected['best_checkpoint']),
            'new_recipe_adopted':adopted,'adoption_conditions':criterion,
            'highest_observed_validation_model':highest,
            'repeated_recipe':winner,'seed_statistics':grouped,
            'stable_above_70_in_fixed_parent_repeats':all(r['accuracy']>.7 for r in repeats),
            'architecture_multiseed_from_scratch_verified':False,
            't35_experiment_count':len(costs),'t35_parameter_update_epochs':sum(updates.values()),
            't35_total_training_run_seconds':sum(costs.values()),
            'parent_training_seconds':json.loads(Path('results/t3_05_resnet_aug_mps_s42/summary.json').read_text())['elapsed_seconds'],
            'private_test_used':False,'scope_stopped_at':'T3.5',
            'caveat':'PublicTest has been used for adaptive selection; bootstrap is descriptive and duplicate images violate iid; repeats share the same seed42 parent.'}
    write_json(out/'selected_model.json',result)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
