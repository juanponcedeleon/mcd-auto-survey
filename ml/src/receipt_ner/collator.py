"""Encode word/box/label triples into LayoutLMv3 model inputs.

This is where sub-word label alignment happens — the part that most often bites
people fine-tuning token classifiers on top of BPE tokenizers.

``LayoutLMv3Processor`` bundles the image processor (resizes to 224x224 and
produces ``pixel_values``) and the RoBERTa-style BPE tokenizer. When we pass
``word_labels`` it takes care of the alignment for us:

* the label is attached to the **first** sub-word of each word,
* every following sub-word of that word is set to ``-100``,
* special tokens (``<s>``, ``</s>``, ``<pad>``) are ``-100``,

and ``-100`` is the ignore index that ``CrossEntropyLoss`` skips, so those
positions never contribute to the loss.

We keep a manual ``align_labels_with_tokens`` reference below — it's the first
thing we wrote before discovering the processor does it — because it documents
the contract and is handy for unit tests.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Dict, List

from PIL import Image
from transformers import LayoutLMv3Processor

MODEL_NAME = "microsoft/layoutlmv3-base"
MAX_LENGTH = 512


@lru_cache(maxsize=1)
def get_processor(model_name: str = MODEL_NAME) -> LayoutLMv3Processor:
    # apply_ocr=False: we feed our own words + boxes (see preprocessing.py).
    return LayoutLMv3Processor.from_pretrained(model_name, apply_ocr=False)


def encode_example(example: Dict, processor: LayoutLMv3Processor | None = None,
                   max_length: int = MAX_LENGTH) -> Dict:
    """Encode a single dataset row into tensors ready for the model."""
    processor = processor or get_processor()
    image = Image.open(example["image_path"]).convert("RGB")

    encoding = processor(
        image,
        example["words"],
        boxes=example["boxes"],
        word_labels=example["ner_tags"],
        truncation=True,
        padding="max_length",
        max_length=max_length,
        return_tensors="pt",
    )
    # Drop the batch dim the processor adds for a single example.
    return {key: value.squeeze(0) for key, value in encoding.items()}


def build_encoder(processor: LayoutLMv3Processor | None = None,
                  max_length: int = MAX_LENGTH):
    """Return a ``datasets.map`` compatible batched encode function."""
    processor = processor or get_processor()

    def _encode_batch(batch: Dict[str, List]) -> Dict:
        images = [Image.open(p).convert("RGB") for p in batch["image_path"]]
        encoding = processor(
            images,
            batch["words"],
            boxes=batch["boxes"],
            word_labels=batch["ner_tags"],
            truncation=True,
            padding="max_length",
            max_length=max_length,
            return_tensors="pt",
        )
        return encoding

    return _encode_batch


def align_labels_with_tokens(word_ids: List[int | None],
                             word_labels: List[int]) -> List[int]:
    """Reference implementation of first-subword label alignment.

    Kept for documentation / tests. ``word_ids`` comes from a fast tokenizer's
    ``.word_ids()`` — ``None`` for special tokens, otherwise the index of the
    source word. We label the first sub-word of each word and mask the rest
    (and all special tokens) with ``-100``.
    """
    aligned: List[int] = []
    previous_word_id = None
    for word_id in word_ids:
        if word_id is None:
            aligned.append(-100)
        elif word_id != previous_word_id:
            aligned.append(word_labels[word_id])
        else:
            aligned.append(-100)
        previous_word_id = word_id
    return aligned
