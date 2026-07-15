## mcd-auto-survey

This app now supports a full browser-camera receipt capture flow with backend LayoutLM-family parsing.

## What is included

- Frontend modal to:
  - open camera
  - capture receipt image
  - preview before submit
  - fallback upload via file picker when camera is unavailable/denied
- Backend FastAPI service (`backend/`) with `/parse-receipt` endpoint
- OCR + layout parsing pipeline:
  - OCR via Tesseract (`pytesseract`)
  - LayoutLMv3 token classification inference (`microsoft/layoutlmv3-base-finetuned-funsd` by default)
  - best-effort post-processing for receipt fields:
    - merchant
    - date
    - subtotal
    - tax
    - total
    - survey code (if present)
    - line items (if detectable)

## Frontend setup

```bash
npm ci
npm run dev
```

Optional environment variable:

```bash
# defaults to http://127.0.0.1:8000
VITE_RECEIPT_BACKEND_URL=http://127.0.0.1:8000
```

## Backend setup (LayoutLM parser)

Python 3.10+ is recommended.

```bash
npm run backend:install
npm run backend:dev
```

The backend starts on `http://127.0.0.1:8000` by default.

### Backend environment variables

- `LAYOUTLM_MODEL_NAME` (default: `microsoft/layoutlmv3-base-finetuned-funsd`)
- `RECEIPT_MAX_IMAGE_BYTES` (default: `8388608`)
- `RECEIPT_MAX_IMAGE_DIMENSION` (default: `4096`)
- `RECEIPT_PARSE_TIMEOUT_SECONDS` (default: `45`)
- `RECEIPT_ALLOWED_ORIGIN` (default: `*`)

## Notes and limitations

- The default LayoutLM model is not receipt-specific; extraction is best-effort and combines model predictions with regex heuristics.
- First run downloads model weights from Hugging Face, so startup/inference can be slower initially.
- OCR quality strongly depends on image sharpness, lighting, and framing.
- `pytesseract` requires a local Tesseract OCR binary to be installed and available in your PATH.
