"""Evaluate a fine-tuned checkpoint on the test split.

Writes a machine-readable ``metrics.json`` next to the model and a human
``classification_report`` to ``artifacts/confusion_report.txt``.

Usage::

    python -m receipt_ner.evaluate \
        --model models/layoutlmv3-receipt-ner \
        --config configs/layoutlmv3_base.yaml
"""

from __future__ import annotations

import argparse
import json
import os

import numpy as np
import torch
from seqeval.metrics import classification_report, f1_score, precision_score, recall_score
from transformers import LayoutLMv3ForTokenClassification

from .collator import build_encoder, get_processor
from .dataset import load_splits
from .labels import ID2LABEL
from .metrics import _decode
from .train import load_config


def _predict(model, encoded, batch_size: int = 2):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device).eval()

    all_logits, all_labels = [], []
    columns = ["input_ids", "attention_mask", "bbox", "pixel_values"]
    with torch.no_grad():
        for start in range(0, len(encoded), batch_size):
            chunk = encoded[start:start + batch_size]
            inputs = {c: torch.as_tensor(chunk[c]).to(device) for c in columns}
            logits = model(**inputs).logits.cpu().numpy()
            all_logits.append(logits)
            all_labels.append(np.asarray(chunk["labels"]))
    return np.concatenate(all_logits), np.concatenate(all_labels)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate LayoutLMv3 receipt NER")
    parser.add_argument("--model", default="models/layoutlmv3-receipt-ner")
    parser.add_argument("--config", default="configs/layoutlmv3_base.yaml")
    parser.add_argument("--report", default="artifacts/confusion_report.txt")
    args = parser.parse_args()

    cfg = load_config(args.config)
    processor = get_processor(cfg["model_name"])
    datasets = load_splits(cfg["data_dir"], project_root=cfg.get("project_root"))

    encode = build_encoder(processor, max_length=cfg["max_length"])
    encoded = datasets["test"].map(
        encode, batched=True, remove_columns=datasets["test"].column_names
    )
    encoded.set_format("torch")

    model = LayoutLMv3ForTokenClassification.from_pretrained(args.model)
    logits, labels = _predict(model, encoded, batch_size=cfg["eval_batch_size"])

    true_labels, true_preds = _decode(logits, labels)
    report = classification_report(true_labels, true_preds, digits=4)
    print(report)

    os.makedirs(os.path.dirname(args.report), exist_ok=True)
    with open(args.report, "w", encoding="utf-8") as fh:
        fh.write(report)

    metrics = {
        "precision": precision_score(true_labels, true_preds),
        "recall": recall_score(true_labels, true_preds),
        "f1": f1_score(true_labels, true_preds),
    }
    metrics_path = os.path.join(args.model, "metrics.json")
    with open(metrics_path, "w", encoding="utf-8") as fh:
        json.dump(metrics, fh, indent=2)
    print(f"Wrote {metrics_path} and {args.report}")


if __name__ == "__main__":
    main()
