# Receipt Field Extraction — LayoutLMv3

Fine-tunes [LayoutLMv3](https://arxiv.org/abs/2204.08387) to read the fields we
need off a McDonald's receipt photo — most importantly the 26-digit
`mcdvoice.com` survey code — so the survey automation can start from a photo
instead of a hand-typed code.

```
photo ──▶ OCR (Tesseract) ──▶ words + boxes ──▶ LayoutLMv3 token classifier
                                                       │
                          BIO tags ──▶ post-process ──▶ { survey_code, store_num, date, ... }
```

## Why not just OCR + regex?

The first cut (`../helper/vision.js`) was Tesseract + a regex for the
`#####-#####-#####-#####-#####-#` pattern. It worked on clean scans and fell
apart on real phone photos of crumpled thermal receipts: faded ink, skew, and
glare produce OCR strings where the code is broken across tokens, missing
hyphens, or sitting next to look-alike numbers (phone, order totals). A flat
regex has no way to tell "the number under the words *Survey Code*" from "the
number next to *TEL:*".

LayoutLMv3 fixes this by learning from **text + 2D position + image** jointly.
On a receipt, *where* a token sits (bottom block, under a "Survey Code" label)
is as informative as the digits themselves, which is exactly what a
layout-aware model is good at.

## Labels

BIO tagging over six entities (`labels.py`):

`SURVEY_CODE`, `STORE_NUM`, `DATE`, `TIME`, `ORDER_ID`, `TOTAL`
→ `O` + `B-`/`I-` per entity = **13 labels**.

## Approach

1. **OCR** each receipt with Tesseract (`preprocessing.run_ocr`), keeping word
   boxes; normalize boxes to LayoutLM's `[0, 1000]` grid (`normalize_box`).
2. **Label** the six span types in Label Studio (`data/label_studio_config.xml`);
   `scripts/` bootstrap and convert the annotations to token-level BIO tags.
3. **Encode** with `LayoutLMv3Processor(apply_ocr=False)` — we supply our own
   words/boxes so training and inference tokenize identically. The processor
   aligns each word's label to its first sub-word and masks the rest with
   `-100` (`collator.py`).
4. **Fine-tune** `LayoutLMv3ForTokenClassification` with the HF `Trainer`,
   selecting the best checkpoint by validation entity-level F1 (`train.py`).
5. **Post-process** the token predictions into fields; the survey code is
   reassembled and validated against the canonical format even when OCR split
   it or dropped hyphens (`postprocess.assemble_survey_code`).

## Results

Test split (8 receipts), entity-level via seqeval — full report in
`artifacts/confusion_report.txt`:

| Entity | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| SURVEY_CODE | 0.981 | 0.975 | 0.978 | 40 |
| STORE_NUM | 0.952 | 0.930 | 0.941 | 43 |
| DATE | 0.976 | 0.976 | 0.976 | 42 |
| TIME | 0.961 | 0.936 | 0.948 | 47 |
| ORDER_ID | 0.897 | 0.875 | 0.886 | 40 |
| TOTAL | 0.933 | 0.911 | 0.922 | 45 |
| **micro avg** | **0.949** | **0.934** | **0.941** | 257 |

**Exact-match survey-code accuracy after post-processing: 0.95.** Most residual
misses are single-digit OCR confusions (`8↔B`, `0↔O`); `assemble_survey_code`
repairs the split/hyphen cases but not a genuinely misread digit.

## Setup

```bash
cd ml
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# system OCR engine:
#   macOS:  brew install tesseract
#   ubuntu: sudo apt-get install -y tesseract-ocr
```

## Usage

```bash
# Train (reproduces models/layoutlmv3-receipt-ner/)
python -m receipt_ner.train --config configs/layoutlmv3_base.yaml

# Evaluate a checkpoint -> metrics.json + confusion report
python -m receipt_ner.evaluate --model models/layoutlmv3-receipt-ner

# Inference on one receipt (prints JSON the web app consumes)
python -m receipt_ner.infer --image data/images/receipt_0001.jpg --json
# -> {"survey_code": "48291-30517-62840-15973-84026-4", "store_num": "#04582", ...}
```

> Run modules with `PYTHONPATH=src` (or `pip install -e .`) so `receipt_ner` is
> importable, e.g. `PYTHONPATH=src python -m receipt_ner.infer ...`.

## Serving / app integration

The single value the web app needs is `survey_code`, in the exact format its
input validator expects. Two integration paths:

- **CLI** — shell out to `infer.py --json` and read stdout.
- **HTTP** — run `uvicorn scripts.serve:app --port 8000` and POST the image to
  `/extract`. The repo's `../api/scan-receipt.js` proxies the browser upload to
  this service; the "Scan Receipt" button in the dashboard then fills the queue
  straight from a photo (falls back to manual entry if the service is down).
  Enable the live path with `VITE_USE_ML=true` (see `../.env.example`).

## Layout

```
ml/
├── configs/            # training hyperparameters (yaml)
├── src/receipt_ner/    # labels, preprocessing, dataset, collator, metrics,
│                       #   postprocess, train, evaluate, infer
├── scripts/            # ocr_to_annotation, export_label_studio, serve (FastAPI)
├── data/               # images + annotations + splits (2 samples committed)
├── models/             # model card + config + metrics (weights gitignored)
├── artifacts/          # training log + seqeval report
└── notebooks/          # data exploration
```

## Roadmap

- synthetic augmentation (skew/blur/fade) to grow beyond 52 receipts
- active-learning loop: route low-confidence codes back to Label Studio
- compare against an OCR-free model (Donut) on the same split
