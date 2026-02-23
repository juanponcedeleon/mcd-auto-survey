"""Run a fine-tuned checkpoint on a single receipt image.

Prints the extracted fields as JSON. The ``survey_code`` value is exactly the
format the web app expects (``#####-#####-#####-#####-#####-#``), so this can
be shelled out to from Node (``child_process``) or wrapped by ``serve.py``.

Usage::

    python -m receipt_ner.infer --image data/images/receipt_0001.jpg \
        --model models/layoutlmv3-receipt-ner --json

Exit code is non-zero when no valid survey code could be recovered, which makes
it safe to use in scripts / CI.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Dict

import numpy as np
import torch
from transformers import LayoutLMv3ForTokenClassification

from .collator import get_processor
from .labels import ID2LABEL
from .postprocess import code_span_confidence, to_fields
from .preprocessing import load_image, normalize_box, run_ocr


def _load(model_dir: str):
    processor = get_processor(model_dir)
    model = LayoutLMv3ForTokenClassification.from_pretrained(model_dir)
    model.eval()
    return model, processor


def extract_fields(image_path: str, model, processor) -> Dict:
    words, pixel_boxes, _ = run_ocr(image_path)
    image = load_image(image_path)
    width, height = image.size
    boxes = [normalize_box(box, width, height) for box in pixel_boxes]

    encoding = processor(
        image,
        words,
        boxes=boxes,
        truncation=True,
        padding="max_length",
        max_length=512,
        return_tensors="pt",
    )

    with torch.no_grad():
        logits = model(**encoding).logits[0]
    probs = torch.softmax(logits, dim=-1)
    pred_ids = probs.argmax(dim=-1)

    # Map the (sub-word) predictions back to one tag + prob per source word,
    # taking the first sub-word of each word (word_ids() gives us the mapping).
    word_ids = encoding.word_ids(batch_index=0)
    tags, token_probs, seen = [], [], set()
    for position, word_id in enumerate(word_ids):
        if word_id is None or word_id in seen:
            continue
        seen.add(word_id)
        tags.append(ID2LABEL[int(pred_ids[position])])
        token_probs.append(float(probs[position, pred_ids[position]]))

    confidence = code_span_confidence(tags, token_probs)
    return to_fields(words, tags, confidence=confidence)


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract receipt fields with LayoutLMv3")
    parser.add_argument("--image", required=True)
    parser.add_argument("--model", default="models/layoutlmv3-receipt-ner")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()

    model, processor = _load(args.model)
    fields = extract_fields(args.image, model, processor)

    if args.json:
        print(json.dumps(fields))
    else:
        for key, value in fields.items():
            print(f"{key:>12}: {value}")

    sys.exit(0 if fields.get("survey_code") else 2)


if __name__ == "__main__":
    main()
