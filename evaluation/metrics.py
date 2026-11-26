"""Seven-class metrics from an integer confusion matrix."""

from data_processing.dataset import LABELS


def metrics_from_cm(cm):
    cm = cm.double()
    tp = cm.diag()
    support = cm.sum(1)
    precision = tp / cm.sum(0).clamp_min(1)
    recall = tp / support.clamp_min(1)
    f1 = 2 * precision * recall / (precision + recall).clamp_min(1e-15)
    return {
        "accuracy": tp.sum().item() / cm.sum().item(),
        "correct": int(tp.sum()),
        "samples": int(cm.sum()),
        "macro_f1": f1.mean().item(),
        "per_class": [
            {
                "label": i,
                "name": LABELS[i],
                "support": int(support[i]),
                "precision": precision[i].item(),
                "recall": recall[i].item(),
                "f1": f1[i].item(),
            }
            for i in range(7)
        ],
        "confusion_matrix": cm.long().tolist(),
    }
