"""Entity-level evaluation with seqeval.

We report *entity-level* precision / recall / F1 (not token accuracy). Token
accuracy is misleading here because ~90% of tokens are ``O`` — a model that
predicts ``O`` everywhere would look ~90% accurate while extracting nothing.
seqeval scores whole BIO spans, which is what we actually care about (did we
recover the full survey code, the full date, etc.).
"""

from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np
from seqeval.metrics import (
    classification_report,
    f1_score,
    precision_score,
    recall_score,
)

from .labels import ID2LABEL


def _decode(predictions: np.ndarray, labels: np.ndarray) -> Tuple[List[List[str]], List[List[str]]]:
    """Turn logits/label ids into seqeval string tag sequences, dropping -100."""
    preds = np.argmax(predictions, axis=-1)

    true_labels: List[List[str]] = []
    true_preds: List[List[str]] = []
    for pred_row, label_row in zip(preds, labels):
        cur_preds: List[str] = []
        cur_labels: List[str] = []
        for p, l in zip(pred_row, label_row):
            if l == -100:  # padding / sub-word continuation / special token
                continue
            cur_preds.append(ID2LABEL[int(p)])
            cur_labels.append(ID2LABEL[int(l)])
        true_preds.append(cur_preds)
        true_labels.append(cur_labels)
    return true_labels, true_preds


def compute_metrics(eval_pred) -> Dict[str, float]:
    """``Trainer``-compatible metric callback."""
    predictions, labels = eval_pred
    true_labels, true_preds = _decode(predictions, labels)
    return {
        "precision": precision_score(true_labels, true_preds),
        "recall": recall_score(true_labels, true_preds),
        "f1": f1_score(true_labels, true_preds),
    }


def full_report(eval_pred) -> str:
    """Per-entity ``classification_report`` text (used by evaluate.py)."""
    predictions, labels = eval_pred
    true_labels, true_preds = _decode(predictions, labels)
    return classification_report(true_labels, true_preds, digits=4)
