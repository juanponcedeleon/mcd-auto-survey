# Receipt Field Extraction — LayoutLMv3

Fine-tuning [LayoutLMv3](https://arxiv.org/abs/2204.08387) to pull the fields we
need off a McDonald's receipt photo — mainly the 26-digit `mcdvoice.com` survey
code — so the survey automation can start from a picture instead of a
hand-typed code.

The first cut (`../helper/vision.js`) was Tesseract + a regex; it fell apart on
real phone photos of crumpled thermal receipts. A layout-aware model should do
much better because *where* the code sits on the page is a strong signal.

> Status: early scaffolding. Project layout + label schema are in;
> preprocessing, dataset, training and inference to follow.

## Labels

BIO tagging over six entities — `SURVEY_CODE`, `STORE_NUM`, `DATE`, `TIME`,
`ORDER_ID`, `TOTAL` → `O` + `B-`/`I-` per entity (see `src/receipt_ner/labels.py`).
