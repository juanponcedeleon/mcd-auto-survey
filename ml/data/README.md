# Dataset

52 photographed McDonald's receipts, OCR'd with Tesseract and hand-labelled in
Label Studio into six entity types (see `../README.md` for the schema).

## What's in the repo

Only two receipts (`receipt_0001`, `receipt_0002`) are committed as **format
samples** — one with the survey code read as a single OCR token, one where the
code is split across two tokens (the `B-`/`I-` continuation case). The full
image set is not committed (photos of real receipts + it would bloat the repo);
the pipeline treats the dataset as an external artifact, which is why the
`splits/*.txt` files reference receipts whose images/annotations live outside
version control.

```
data/
├── images/            # <id>.jpg  (2 samples committed; full set gitignored)
├── annotations/       # <id>.json (words, boxes[0-1000], ner_tags) — 2 samples committed
├── splits/            # train/val/test basename lists (70/15/15)
└── label_studio_config.xml
```

## Regenerating annotations

```bash
# 1. OCR a new image into an all-"O" skeleton
python scripts/ocr_to_annotation.py data/images/receipt_0007.jpg

# 2. label the spans in Label Studio using label_studio_config.xml, export JSON-MIN

# 3. convert the export back to token-level BIO tags
python scripts/export_label_studio.py export.json --images data/images
```
