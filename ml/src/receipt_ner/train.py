"""Fine-tune LayoutLMv3 for receipt field extraction.

Usage::

    python -m receipt_ner.train --config configs/layoutlmv3_base.yaml

The config file externalizes every hyperparameter so runs are reproducible and
diffable. Small physical batch size + gradient accumulation is deliberate:
512-token multimodal batches (text + 224x224 image patches) are memory hungry,
and grad-accum keeps the effective batch reasonable on a single 16GB GPU.
"""

from __future__ import annotations

import argparse
import os

import torch
import yaml
from transformers import (
    LayoutLMv3ForTokenClassification,
    Trainer,
    TrainingArguments,
)

from .collator import build_encoder, get_processor
from .dataset import load_splits
from .labels import ID2LABEL, LABEL2ID, NUM_LABELS
from .metrics import compute_metrics


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fine-tune LayoutLMv3 receipt NER")
    parser.add_argument("--config", default="configs/layoutlmv3_base.yaml")
    args = parser.parse_args()

    cfg = load_config(args.config)

    processor = get_processor(cfg["model_name"])
    datasets = load_splits(cfg["data_dir"], project_root=cfg.get("project_root"))

    encode = build_encoder(processor, max_length=cfg["max_length"])
    encoded = datasets.map(
        encode,
        batched=True,
        remove_columns=datasets["train"].column_names,
        desc="Encoding with LayoutLMv3Processor",
    )
    encoded.set_format("torch")

    model = LayoutLMv3ForTokenClassification.from_pretrained(
        cfg["model_name"],
        num_labels=NUM_LABELS,
        id2label=ID2LABEL,
        label2id=LABEL2ID,
    )

    training_args = TrainingArguments(
        output_dir=cfg["output_dir"],
        per_device_train_batch_size=cfg["train_batch_size"],
        per_device_eval_batch_size=cfg["eval_batch_size"],
        gradient_accumulation_steps=cfg["grad_accum_steps"],
        learning_rate=float(cfg["learning_rate"]),
        num_train_epochs=cfg["num_epochs"],
        warmup_ratio=cfg["warmup_ratio"],
        weight_decay=cfg["weight_decay"],
        eval_strategy="epoch",
        save_strategy="epoch",
        save_total_limit=2,
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        greater_is_better=True,
        logging_steps=cfg.get("logging_steps", 10),
        fp16=torch.cuda.is_available(),
        report_to=cfg.get("report_to", "none"),
        seed=cfg.get("seed", 42),
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=encoded["train"],
        eval_dataset=encoded["val"],
        processing_class=processor,
        compute_metrics=compute_metrics,
    )

    trainer.train()

    trainer.save_model(cfg["output_dir"])
    processor.save_pretrained(cfg["output_dir"])

    test_metrics = trainer.evaluate(encoded["test"], metric_key_prefix="test")
    trainer.log_metrics("test", test_metrics)
    trainer.save_metrics("test", test_metrics)
    print(f"Done. Best model + processor saved to {os.path.abspath(cfg['output_dir'])}")


if __name__ == "__main__":
    main()
