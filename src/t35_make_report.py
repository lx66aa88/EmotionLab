"""Generate the final Chinese T3.5 report from completed, verified artifacts."""
import json
from pathlib import Path
import statistics


ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/t35_final_20261030'


def read(p):return json.loads((ROOT/p).read_text())
def pct(x):return f'{x*100:.4f}%'
def link(label,path):return f'[{label}]({ROOT/path})'


def main():
    selected=read('results/t35_final_20261030/selected_model.json')
    rows=read('results/t35_final_20261030/comparison.json')
    pairs=read('results/t35_final_20261030/paired_comparisons.json')
    diag=read('results/t35_diagnosis_20261030/diagnosis.json')
    old=next(r for r in rows if r['name']=='t3_06_unweighted_s42')
    current=selected['current_selected_model'];highest=selected['highest_observed_validation_model']
    winner=selected['repeated_recipe'];case=winner+'_s42'
    candidate=read('results/t35_final_20261030/'+case+'_mps.json')
    rep=[r for r in rows if r['canonical'] and r['name'].rsplit('_s',1)[0]==winner]
    arows=[r for r in rows if r['canonical'] and r['name'].startswith('t35_a_cosine_s')]
    matched=['| 同一微调种子 | C正式EMA−A Accuracy | C−A Macro F1 | C−A CE |',
             '| --- | --- | --- | --- |']
    for arow in arows:
        crow=next((r for r in rep if r['seed']==arow['seed']),None)
        if crow:
            matched.append(f"| {arow['seed']} | {(crow['accuracy']-arow['accuracy'])*100:+.4f}个百分点 | {(crow['macro_f1']-arow['macro_f1'])*100:+.4f}个百分点 | {crow['loss']-arow['loss']:+.6f} |")
    delta=pairs[case];ci=delta['paired_bootstrap_95pct']
    old_eval=diag['models']['best56']['public_eval']
    groups=read('results/t35_diagnosis_20261030/duplicate_strata.json')
    status_updated='## T3.5 — 完成' in (ROOT/'PROJECT_STATUS.md').read_text()
    assert status_updated,'Append the actual completed status before publishing the report'
    configs=[read(str(p.relative_to(ROOT))) for p in (ROOT/'configs/t35').glob('*.json')]
    signatures={json.dumps({k:v for k,v in c.items() if k not in ['name','seed']},sort_keys=True) for c in configs}
    assert len(signatures)==3
    table=['| 实验/种子 | 权重 | Accuracy | Macro F1 | 普通验证CE | 本次更新/最佳局部轮 | 本次运行秒 |',
           '| --- | --- | --- | --- | --- | --- | --- |']
    for r in rows:
        stream=r['stream']+('（正式）' if r['canonical'] else '（消融）')
        table.append(f"| {r['name']} | {stream} | {pct(r['accuracy'])} | {pct(r['macro_f1'])} | {r['loss']:.6f} | {r['epochs_completed']}/{r['best_local_epoch']} | {r['elapsed_seconds']:.2f} |")
    perclass=['| 类别 | 旧Recall | C seed42 Recall | 旧F1 | C seed42 F1 |','| --- | --- | --- | --- | --- |']
    for o,n in zip(old_eval['per_class'],candidate['per_class']):
        perclass.append(f"| {o['name']} | {pct(o['recall'])} | {pct(n['recall'])} | {pct(o['f1'])} | {pct(n['f1'])} |")
    confusion=['| 真实→预测 | T3最佳 | C seed42 EMA |','| --- | --- | --- |']
    for i,j in [(4,6),(6,4),(2,4),(4,2),(2,6),(6,2)]:
        confusion.append(f"| {old_eval['per_class'][i]['name']}→{old_eval['per_class'][j]['name']} | {old_eval['confusion_matrix'][i][j]} | {candidate['confusion_matrix'][i][j]} |")
    index=[]
    for r in rows:
        if not r['name'].startswith('t35_') or not r['canonical']:continue
        name=r['name']
        index.append(f"- **{name}**："+' · '.join([
            link('完整配置','results/'+name+'/config.json'),link('逐轮CSV','results/'+name+'/metrics.csv'),
            link('JSONL/逐类混淆','results/'+name+'/metrics.jsonl'),link('真实控制台','results/'+name+'.console.log'),
            link('汇总','results/'+name+'/summary.json'),link('源代码快照','results/'+name+'/source'),
            f"[正式流最佳权重]({r['best_checkpoint']})"]))
    adopted='采用新配方' if selected['new_recipe_adopted'] else '保留原T3最佳模型，不把单次更高值改报为稳定提升'
    condition_labels={'all_three_seeds_above_old_best':'三个种子都超过旧最佳',
                      'mean_accuracy_above_old_best':'均值超过旧最佳',
                      'seed42_paired_interval_lower_above_zero':'seed42成对区间下界高于0'}
    condition_text='；'.join(condition_labels[k]+('：通过' if v else '：未通过')
                            for k,v in selected['adoption_conditions'].items())
    text=f'''# EmotionLab T3.5 — 残差CNN专项诊断与有限优化

日期：2026-10-30（韩国时间）。**T3.5已完成，{adopted}。当前正式PublicTest Accuracy为{pct(current['accuracy'])}，Macro F1为{pct(current['macro_f1'])}，普通CE为{current['loss']:.6f}。本次未实现稳定超过70%。**

新增实验中单次最高为 **{pct(highest['accuracy'])} / Macro F1 {pct(highest['macro_f1'])}**（{highest['name']}、{highest['stream']}），只作为候选保存。正式流、消融流与最终采用分开报告。无PrivateTest访问/模型选择，无外部数据/预训练，无T4–T9。

## 1. 先诊断后训练：限制准确率的真实证据

已检查原T3报告、best.pt、confusion_comparison.png、PROJECT_STATUS、模型/训练/推理代码、9组配置及逐轮日志。先完成独立诊断，再运行三配置。详见{link('训练前诊断','results/t35_diagnosis_20261030/DIAGNOSIS.md')}、{link('原始诊断JSON','results/t35_diagnosis_20261030/diagnosis.json')}。

1. **后期过拟合和过度自信有直接证据。** 固定epoch50/56权重，关闭增强和Dropout，对完整Training eval：85.0221%→87.0668%，CE .407214→.350529；Public为67.7905%→68.3477%，CE 1.057993→1.148308。epoch56同状态训练/验证差18.7190个百分点。Public ECE（10箱）.11959→.14050，错误且置信度>90%的样本224→308。不能把旧逐轮训练指标当作固定模型评估。
2. **没有容量不足是主要瓶颈的证据。** 当前宽16/32/64/128的残差CNN有700791参数，训练拟合明显强于验证，本轮不增加容量。不能据此证明所有类别已充分拟合或更宽网络必定无效。
3. **原调度的后期收益有限。** 原50轮中前39轮LR=.001，第40轮降至.0005，第49轮至.00025；小LR有阶段性收益，但后续短微调CE继续变差。原Dropout=.3、Adam weight_decay=.0001、翻转/反射平移已有正则化。本轮检验固定小LR平滑衰减、温和目标正则化和时间权重平均。
4. **未发现足以解释上限的明显训练实现错误。** 检查了zero_grad/backward/step、七类raw logits交叉熵、eval/inference_mode、BN状态、逐样本汇总、选模和重载。全3589张Public的加载与推理预处理逐项一致：float32/255、1×48×48；增强只用于Training。/255是本模型原有约定，不能仅凭未做均值方差标准化认定存在bug。
5. **类别混淆集中但原因未证实。** 旧最佳Fear/Sad/Neutral召回54.44%/54.52%/66.56%；三类互相混淆426次，占1136个错误的37.50%。没有据此擅自归因于遮挡、光照或错标。

## 2. 数据审计及评估限制

Training有1236个像素完全重复的额外行、39组同像素不同标签；Public有26个额外重复行。跨Training/Public有270个完全相同像素组，涉及280张Public图片，其中13组标签冲突。仅处理允许划分的图像和标签，没有解析PrivateTest像素/标签，没有修改CSV、去重或重划分。

旧模型在280张完全重复Public图片上为251/280（89.64%）；其余3309张为2202/3309（66.55%）。这是事后诊断分组，**不用于选模或替代完整官方Public成绩**；两组难度可能不同，不能量化重复带来的因果提升。它提示Public的独立性有限。来源：{link('重复分组诊断','results/t35_diagnosis_20261030/duplicate_strata.json')}。

T3无加权seed42/43为68.3477%/68.1806%，均值68.2641%、样本标准差.1182个百分点，均来自同一个seed42 epoch50父模型。新种子重复也共享这个父模型，不能称为架构从头训练的多种子验证。

## 3. 有限实验设计与完整结果

仅三种新超参数配置；共{selected['t35_experiment_count']}次完整运行、**{selected['t35_parameter_update_epochs']}轮参数更新**。这不是单个模型训练了这些轮数。每次完整Training28709/Public3589，18轮、batch256、Adam重置、weight_decay=.0001、MPS、固定cosine LR .00015→.000005；从相同epoch50父权重出发，不是精确恢复优化器。

- **A**：原翻转/±4px反射平移、普通CE，无EMA，作为调度/预算配方对照。
- **B**：A基础上Label Smoothing=.05、每step EMA decay=.995；每轮同时记录普通权重和EMA。EMA验证前仅用完整无增强Training重估BN，Dropout关闭。
- **C**：B再加每图对比度[.9,1.1]、亮度偏移[-.05,.05]并截断[0,1]。不增加旋转、遮挡或类别加权。

A正式流online，B/C正式流EMA，普通权重作消融。各流按Accuracy优先、平手普通CE低选轮，父模型不算本支更新后的最佳；不把各轮最高F1/最低Loss拼成一行。EMA只保存一套模型，推理不是多模型融合。EMA+BN重估的效果不能单独归因于EMA参数平均。

{chr(10).join(table)}

旧T3行最佳轮次为累计编号；T3.5为本次局部1–18轮，累计编号=50+局部轮。同一新实验的online/EMA行共用一次训练，运行秒数重复展示，不能重复相加。

## 4. 每项改动是否真正改善

- A seed42与旧最佳Accuracy相同，Macro F1略降，CE更低；修正137个旧错误且新增137个错误，净增0。仅调整小LR/预算没有提高该种子准确率。相对T3同时改变了调度和轮数，不能作单因素归因。
- B seed42普通权重68.4035%、F1 65.1816%、CE1.021114；相对A的68.3477%/65.7449%/1.087227，Label Smoothing主要降低CE，微小Accuracy变化伴随Macro F1下降，不能称为全面改善。
- B seed42 EMA68.3756%，低于该组普通权重最高68.4035%；二者最佳轮次不同。逐轮JSONL保留同轮对照，EMA配方没有显示稳定的Accuracy优势。
- C seed42正式EMA68.4870%，相对B正式EMA68.3756%多4张，但Macro F1下降。普通权重单次68.6542%也需重复证据，不能仅按最高点采用。
- C seed42的ECE（10箱）为{candidate['ece_10_bins']:.5f}，相对旧模型.14050下降；错误且置信度>90%的数量为{candidate['errors_confidence_above_90pct']}（旧308）。整个配方改善了过度自信表现，但这不等同于准确率稳定提升，也不能把组合配方的收益全部归因于单个方法。
- 对C seed42选中EMA再次关闭增强/Dropout重评完整Training：Accuracy {pct(candidate['fixed_training_eval']['accuracy'])}、CE {candidate['fixed_training_eval']['loss']:.6f}；对应Public为{pct(candidate['accuracy'])}、CE {candidate['loss']:.6f}，准确率差{(candidate['fixed_training_eval']['accuracy']-candidate['accuracy'])*100:.4f}个百分点。泛化差距仍在，不能声称正则化已解决过拟合。
- **最终采用判断**：{condition_text}。按记录的保守规则，{adopted}。原规则及制定时点见{link('采用规则','results/t35_diagnosis_20261030/SELECTION_POLICY.md')}，未伪称所有采用条件都在首个训练step前预注册。

本轮只检验已过拟合父模型上的短微调，不能据此否定从头训练阶段使用Label Smoothing、EMA或增强的价值。

## 5. 重复种子、成对比较与不确定性

锁定{winner}后只改seed43/44；重复正式流Accuracy为{', '.join(str(r['seed'])+'='+pct(r['accuracy']) for r in rep)}。均值 **{pct(statistics.mean(r['accuracy'] for r in rep))}**，样本标准差 **{statistics.stdev(r['accuracy'] for r in rep)*100:.4f}个百分点**；Macro F1均值{pct(statistics.mean(r['macro_f1'] for r in rep))}。A匹配对照：{', '.join(str(r['seed'])+'='+pct(r['accuracy']) for r in arows)}。

C seed42相对原T3最佳：修正{delta['new_correct_old_wrong']}个错误、新增{delta['old_correct_new_wrong']}个错误，净增{delta['net_additional_correct']}张（{delta['accuracy_delta']*100:.4f}个百分点）；20000次成对bootstrap 95%区间 **[{ci[0]*100:.4f}, {ci[1]*100:.4f}]个百分点**；McNemar双侧描述性p={delta['mcnemar_exact_two_sided_p']:.6f}。区间跨0，未证明真实提升。各重复的成对统计见{link('完整成对比较','results/t35_final_20261030/paired_comparisons.json')}。

{chr(10).join(matched)}

这里比较的是各正式流按相同规则选中的最佳轮次，不是假称同一epoch的单因素因果实验。

固定旧预测在理想独立抽样下Wilson95%区间约[66.81%,69.85%]。这些区间/p值没有校正多次Public选模、重复图像或公共验证反复使用，不能作为独立测试结论。seed42筛选配置的赢家偏差也未消除。本轮计算预算实际完成，不以资源不足掩盖不理想结果；未开展独立从头训练多种子。

## 6. Sad、Fear、Neutral及类别权衡

{chr(10).join(confusion)}

{chr(10).join(perclass)}

C seed42的Sad召回增加伴随Fear/Neutral召回下降，Disgust仅56张验证样本，少量变化会明显改变Macro F1。当前配方没有证据表明已解决三类决策边界。类别表是同一选中模型的结果。

![真实训练曲线]({OUT/'learning_curves.png'})

![旧最佳与C seed42混淆矩阵]({OUT/'confusion_comparison.png'})

## 7. 训练成本、验证与原件保护

新增实验运行时间合计 **{selected['t35_total_training_run_seconds']:.2f}秒（{selected['t35_total_training_run_seconds']/60:.2f}分钟）**，按唯一实验计，不重复累计online/EMA；包含加载/验证/保存/重载，不含全部诊断、CPU独立复核、报告工作。共同父模型训练额外{selected['parent_training_seconds']:.2f}秒。与T3比较须计父模型成本；不同环境负载下的墙钟时间不是隔离的速度基准。

20项自动化测试通过，包含原T1/T2/T3的14项和本轮6项；源码编译检查通过。编译缓存定向到临时可写目录。每次实验结束从磁盘重载两流/正式流，另以独立命令完整验证所有正式流MPS；A seed42、C seed42及最终正式模型另做CPU重载。混淆矩阵须一致，普通CE允许1e-6量级浮点差异。

配置/源代码快照哈希、父权重哈希、每轮样本数/连续轮次、最佳选模、F1/混淆算术及独立重载已核对。见{link('实验验收','results/t35_final_20261030/artifact_checks.json')}、{link('测试日志','results/t35_diagnosis_20261030/tests_20.txt')}。

原T2/T3全量工程/配置/日志/结果/权重、原CSV保持不变；状态文件先备份后仅追加T3.5节，没有删除、覆盖或批量移动原成果。旧最佳额外备份为{link('t3_best_backup.pt','results/t35_diagnosis_20261030/t3_best_backup.pt')}，状态原件为{link('PROJECT_STATUS.before_t35.md','results/t35_diagnosis_20261030/PROJECT_STATUS.before_t35.md')}。完整哈希验收见本目录original_integrity_before_status.json及final_integrity.json。

当前正式权重：[{Path(current['best_checkpoint']).name}]({current['best_checkpoint']})；SHA-256 `{selected['current_checkpoint_sha256']}`。本次单次最高候选权重：[{highest['name']} / {highest['stream']}]({highest['best_checkpoint']})，没有覆盖旧模型。

## 8. 交付索引与下一步

{link('完整比较CSV','results/t35_final_20261030/comparison.csv')} · {link('固定选择清单/种子统计','results/t35_final_20261030/selected_model.json')} · {link('重复前锁定依据','results/t35_final_20261030/repeat_selection.json')} · {link('复现指南及代码入口','docs/T35_GUIDE.md')} · {link('项目最新状态','PROJECT_STATUS.md')}

{chr(10).join(index)}

仍存在过拟合/置信度偏高、Fear/Sad/Neutral混淆、少数类样本少、验证独立性有限、共享父模型种子证据有限等问题。后续若继续模型专项，优先在不改官方划分的前提下，经老师确认检查Training冲突样本；用独立从头训练的重复实验评估训练阶段正则化和容量，而不是继续从已过拟合权重小幅调参。现有低CE候选有校准价值，但不能据此宣传准确率已稳定提高。

**本任务在T3.5停止：不进入T4–T9，不运行PrivateTest。**
'''
    with (OUT/'REPORT.md').open('x') as f:f.write(text)
    print(OUT/'REPORT.md')


if __name__=='__main__':main()
