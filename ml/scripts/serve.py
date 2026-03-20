"""Minimal FastAPI inference server for the receipt NER model.

Loads the fine-tuned checkpoint once at startup and exposes a single endpoint
the web app's `/api/scan-receipt` proxy calls::

    POST /extract   (multipart: file=<image>)  ->  { survey_code, store_num, ... }

Run it with::

    uvicorn scripts.serve:app --host 0.0.0.0 --port 8000

This is optional — `infer.py` covers the CLI path with no server required.
"""

from __future__ import annotations

import io
import os
import sys

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from receipt_ner.infer import _load, extract_fields  # noqa: E402
from receipt_ner.preprocessing import normalize_box, run_ocr  # noqa: E402

MODEL_DIR = os.environ.get("MODEL_DIR", "models/layoutlmv3-receipt-ner")

app = FastAPI(title="Receipt NER", version="0.3.0")
_model, _processor = None, None


@app.on_event("startup")
def _startup() -> None:
    global _model, _processor
    _model, _processor = _load(MODEL_DIR)


def _extract_from_image(image: Image.Image) -> dict:
    """Same pipeline as infer.extract_fields but from an in-memory image."""
    import torch
    from receipt_ner.labels import ID2LABEL
    from receipt_ner.postprocess import code_span_confidence, to_fields

    # Persist to a temp buffer so we can reuse the file-based OCR helper.
    tmp = io.BytesIO()
    image.convert("RGB").save(tmp, format="PNG")
    tmp.seek(0)
    tmp_path = "/tmp/receipt_ner_upload.png"
    with open(tmp_path, "wb") as fh:
        fh.write(tmp.read())

    return extract_fields(tmp_path, _model, _processor)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "model": MODEL_DIR, "loaded": _model is not None}


@app.post("/extract")
async def extract(file: UploadFile = File(...)) -> JSONResponse:
    try:
        image = Image.open(io.BytesIO(await file.read())).convert("RGB")
        fields = _extract_from_image(image)
        return JSONResponse(fields)
    except Exception as exc:  # noqa: BLE001 - surface a clean error to the caller
        return JSONResponse({"error": str(exc), "survey_code": None}, status_code=500)
