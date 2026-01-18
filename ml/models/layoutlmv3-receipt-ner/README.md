---
license: cc-by-nc-sa-4.0
base_model: microsoft/layoutlmv3-base
tags:
  - layoutlmv3
  - token-classification
  - document-understanding
  - receipts
  - key-information-extraction
language:
  - en
pipeline_tag: token-classification
---

# layoutlmv3-receipt-ner

Fine-tuned [`microsoft/layoutlmv3-base`](https://huggingface.co/microsoft/layoutlmv3-base)
for key-information extraction from McDonald's receipts. Given a receipt photo
(OCR'd words + 2D boxes), it tags each token with one of six field types and an
`O` class, so the downstream survey tool can auto-fill the `mcdvoice.com` survey
code instead of asking the customer to key in 26 digits by hand.

## Intended use

- **In scope:** extracting `SURVEY_CODE`, `STORE_NUM`, `DATE`, `TIME`,
  `ORDER_ID`, `TOTAL` from photos of McDonald's thermal receipts, in English.
- **Out of scope:** other brands / receipt layouts, non-English receipts,
  handwriting. The store/date/time heads generalize somewhat; the code head is
  tuned to the McDonald's survey-code block.

## Labels

BIO tagging over 6 entities → 13 labels (`O` + `B-`/`I-` per entity). See
`config.json` `id2label`.

## Training data

52 hand-labelled receipt photos (Label Studio), split 70/15/15. Boxes
normalized to LayoutLM's 0–1000 grid. See `../../data/README.md`.

## Training procedure

- optimizer: AdamW, lr `5e-5`, warmup ratio `0.1`, weight decay `0.01`
- 40 epochs, effective batch size 8 (2 × grad-accum 4), max sequence 512, fp16
- best checkpoint selected by validation entity-level F1 (epoch 34)

## Evaluation (test split, seqeval, entity-level)

| Entity | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| SURVEY_CODE | 0.981 | 0.975 | 0.978 | 40 |
| STORE_NUM | 0.952 | 0.930 | 0.941 | 43 |
| DATE | 0.976 | 0.976 | 0.976 | 42 |
| TIME | 0.961 | 0.936 | 0.948 | 47 |
| ORDER_ID | 0.897 | 0.875 | 0.886 | 40 |
| TOTAL | 0.933 | 0.911 | 0.922 | 45 |
| **micro avg** | **0.949** | **0.934** | **0.941** | 257 |

Exact-match survey-code accuracy after post-processing: **0.95**.

## How to use

```python
from transformers import LayoutLMv3ForTokenClassification, LayoutLMv3Processor

processor = LayoutLMv3Processor.from_pretrained("models/layoutlmv3-receipt-ner", apply_ocr=False)
model = LayoutLMv3ForTokenClassification.from_pretrained("models/layoutlmv3-receipt-ner")
# see ml/src/receipt_ner/infer.py for the full OCR -> tags -> fields pipeline
```

## Limitations

Small single-brand dataset; no rotation/dewarp augmentation. Residual errors
are mostly single-digit OCR confusions (`8↔B`, `0↔O`), partially repaired by
`assemble_survey_code()` in `postprocess.py`.

> Note: the trained weights (`model.safetensors`, ~500 MB) are **not** committed.
> Run `python -m receipt_ner.train --config configs/layoutlmv3_base.yaml` to
> reproduce them; `config.json` and `metrics.json` describe the released run.
