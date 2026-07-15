import asyncio
import os
import re
from io import BytesIO
from typing import Any

import pytesseract
import torch
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, UnidentifiedImageError
from transformers import AutoModelForTokenClassification, AutoProcessor

MODEL_NAME = os.getenv("LAYOUTLM_MODEL_NAME", "microsoft/layoutlmv3-base-finetuned-funsd")
MAX_IMAGE_BYTES = int(os.getenv("RECEIPT_MAX_IMAGE_BYTES", 8 * 1024 * 1024))
MAX_IMAGE_DIMENSION = int(os.getenv("RECEIPT_MAX_IMAGE_DIMENSION", 4096))
PARSE_TIMEOUT_SECONDS = int(os.getenv("RECEIPT_PARSE_TIMEOUT_SECONDS", 45))

DATE_PATTERNS = [
    r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
    r"\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b",
    r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+\d{1,2},?\s+\d{2,4}\b",
]
MONEY_PATTERN = re.compile(r"(?<!\d)(?:\$)?\d{1,4}(?:,\d{3})*(?:\.\d{2})(?!\d)")
LINE_ITEM_PATTERN = re.compile(r"^(?P<name>.+?)\s{1,}(?P<amount>\$?\d+(?:\.\d{2}))\s*$")
SURVEY_CODE_PATTERN = re.compile(r"\b\d{5}(?:-\d{5}){4}-\d\b")
TOTAL_KEYWORDS = ("total", "amount due", "balance due")
SUBTOTAL_KEYWORDS = ("subtotal", "sub total")
TAX_KEYWORDS = ("tax", "vat", "gst")

processor: AutoProcessor | None = None
model: AutoModelForTokenClassification | None = None
model_load_error: str | None = None

app = FastAPI(title="Receipt Parser API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("RECEIPT_ALLOWED_ORIGIN", "*")],
    allow_credentials=False,
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)


def _normalize_box(left: int, top: int, width: int, height: int, image_width: int, image_height: int) -> list[int]:
    x0 = max(0, min(1000, int(1000 * left / image_width)))
    y0 = max(0, min(1000, int(1000 * top / image_height)))
    x1 = max(0, min(1000, int(1000 * (left + width) / image_width)))
    y1 = max(0, min(1000, int(1000 * (top + height) / image_height)))
    return [x0, y0, x1, y1]


def _safe_money_value(raw_value: str | None) -> float | None:
    if not raw_value:
        return None
    try:
        return float(raw_value.replace("$", "").replace(",", ""))
    except ValueError:
        return None


def _extract_money_by_keywords(lines: list[str], keywords: tuple[str, ...]) -> str | None:
    for line in reversed(lines):
        lowered = line.lower()
        if any(keyword in lowered for keyword in keywords):
            amounts = MONEY_PATTERN.findall(line)
            if amounts:
                return amounts[-1]
    return None


def _extract_line_items(lines: list[str]) -> list[dict[str, Any]]:
    ignored_terms = TOTAL_KEYWORDS + SUBTOTAL_KEYWORDS + TAX_KEYWORDS
    items: list[dict[str, Any]] = []
    for line in lines:
        if any(term in line.lower() for term in ignored_terms):
            continue
        match = LINE_ITEM_PATTERN.match(line.strip())
        if not match:
            continue
        amount_raw = match.group("amount")
        amount = _safe_money_value(amount_raw)
        if amount is None:
            continue
        name = match.group("name").strip(" .:-")
        if not name or len(name) < 2:
            continue
        items.append({"description": name, "amount": amount})
    return items


def _extract_fields(full_text: str) -> dict[str, Any]:
    lines = [line.strip() for line in full_text.splitlines() if line.strip()]
    merchant = next((line for line in lines if any(ch.isalpha() for ch in line)), None)
    date_match = None
    for pattern in DATE_PATTERNS:
        date_match = re.search(pattern, full_text, flags=re.IGNORECASE)
        if date_match:
            break

    subtotal_text = _extract_money_by_keywords(lines, SUBTOTAL_KEYWORDS)
    tax_text = _extract_money_by_keywords(lines, TAX_KEYWORDS)
    total_text = _extract_money_by_keywords(lines, TOTAL_KEYWORDS)
    survey_code = SURVEY_CODE_PATTERN.search(full_text)

    return {
        "merchant": {"value": merchant, "confidence": 0.6 if merchant else 0.0},
        "date": {"value": date_match.group(0) if date_match else None, "confidence": 0.7 if date_match else 0.0},
        "subtotal": {"value": _safe_money_value(subtotal_text), "raw": subtotal_text, "confidence": 0.75 if subtotal_text else 0.0},
        "tax": {"value": _safe_money_value(tax_text), "raw": tax_text, "confidence": 0.7 if tax_text else 0.0},
        "total": {"value": _safe_money_value(total_text), "raw": total_text, "confidence": 0.8 if total_text else 0.0},
        "survey_code": {"value": survey_code.group(0) if survey_code else None, "confidence": 0.95 if survey_code else 0.0},
        "line_items": _extract_line_items(lines),
    }


def _load_model() -> None:
    global processor, model, model_load_error
    if processor is not None and model is not None:
        return
    if model_load_error:
        raise RuntimeError(model_load_error)
    try:
        processor = AutoProcessor.from_pretrained(MODEL_NAME, apply_ocr=False)
        model = AutoModelForTokenClassification.from_pretrained(MODEL_NAME)
    except Exception as exc:
        model_load_error = f"Unable to load model '{MODEL_NAME}': {exc}"
        raise RuntimeError(model_load_error) from exc


def _run_layoutlm_inference(image: Image.Image, words: list[str], boxes: list[list[int]]) -> dict[str, Any]:
    if not words:
        return {"entities": [], "model_name": MODEL_NAME}

    _load_model()
    assert processor is not None
    assert model is not None

    encoding = processor(
        images=image,
        text=words,
        boxes=boxes,
        truncation=True,
        padding="max_length",
        max_length=512,
        return_tensors="pt",
    )
    with torch.no_grad():
        outputs = model(**encoding)

    probabilities = torch.softmax(outputs.logits, dim=-1)[0]
    pred_ids = probabilities.argmax(dim=-1).tolist()
    word_ids = encoding.word_ids(batch_index=0)

    seen_word_ids: set[int] = set()
    entities: list[dict[str, Any]] = []
    id2label = model.config.id2label

    for token_index, word_index in enumerate(word_ids):
        if word_index is None or word_index in seen_word_ids:
            continue
        seen_word_ids.add(word_index)
        label_id = pred_ids[token_index]
        label = id2label.get(label_id, "O")
        confidence = float(probabilities[token_index][label_id].item())
        if label == "O":
            continue
        entities.append(
            {
                "text": words[word_index],
                "label": label,
                "confidence": round(confidence, 4),
                "box": boxes[word_index],
            }
        )

    return {"entities": entities, "model_name": MODEL_NAME}


def _ocr_words_and_boxes(image: Image.Image) -> tuple[list[str], list[list[int]], list[float], str]:
    data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
    full_text = pytesseract.image_to_string(image)
    words: list[str] = []
    boxes: list[list[int]] = []
    confidences: list[float] = []

    image_width, image_height = image.size
    total = len(data["text"])
    for i in range(total):
        text = (data["text"][i] or "").strip()
        conf_raw = (data["conf"][i] or "").strip()
        if not text:
            continue
        try:
            conf = max(0.0, min(100.0, float(conf_raw)))
        except ValueError:
            conf = 0.0
        left = int(data["left"][i])
        top = int(data["top"][i])
        width = int(data["width"][i])
        height = int(data["height"][i])
        words.append(text)
        boxes.append(_normalize_box(left, top, width, height, image_width, image_height))
        confidences.append(conf / 100.0)

    return words, boxes, confidences, full_text


def _compute_overall_confidence(
    fields: dict[str, Any], ocr_confidences: list[float], layoutlm_entities: list[dict[str, Any]]
) -> float:
    field_scores = [
        field_data.get("confidence", 0.0)
        for key, field_data in fields.items()
        if key != "line_items" and isinstance(field_data, dict)
    ]
    model_scores = [entity.get("confidence", 0.0) for entity in layoutlm_entities]
    aggregate = field_scores + ocr_confidences + model_scores
    if not aggregate:
        return 0.0
    return round(float(sum(aggregate) / len(aggregate)), 4)


async def _parse_receipt_image(raw_bytes: bytes) -> dict[str, Any]:
    try:
        image = Image.open(BytesIO(raw_bytes)).convert("RGB")
    except UnidentifiedImageError as exc:
        raise HTTPException(status_code=400, detail="Unable to decode uploaded image.") from exc

    width, height = image.size
    if max(width, height) > MAX_IMAGE_DIMENSION:
        ratio = MAX_IMAGE_DIMENSION / max(width, height)
        image = image.resize((int(width * ratio), int(height * ratio)))

    words, boxes, ocr_confidences, full_text = _ocr_words_and_boxes(image)
    if not words:
        raise HTTPException(status_code=422, detail="OCR could not detect readable text on the image.")

    fields = _extract_fields(full_text)
    layoutlm = _run_layoutlm_inference(image, words, boxes)
    overall_confidence = _compute_overall_confidence(fields, ocr_confidences, layoutlm["entities"])

    return {
        "fields": fields,
        "confidence": overall_confidence,
        "raw_text": full_text.strip(),
        "layoutlm": layoutlm,
        "meta": {
            "ocr_word_count": len(words),
            "image_size": {"width": image.size[0], "height": image.size[1]},
        },
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/parse-receipt")
async def parse_receipt(image: UploadFile = File(...)) -> dict[str, Any]:
    if image.content_type is None or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image uploads are supported.")

    raw_bytes = await image.read()
    if not raw_bytes:
        raise HTTPException(status_code=400, detail="Empty upload.")
    if len(raw_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Image too large. Max size is {MAX_IMAGE_BYTES // (1024 * 1024)}MB.",
        )

    try:
        return await asyncio.wait_for(_parse_receipt_image(raw_bytes), timeout=PARSE_TIMEOUT_SECONDS)
    except asyncio.TimeoutError as exc:
        raise HTTPException(status_code=504, detail="Receipt parsing timed out.") from exc
    except HTTPException:
        raise
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unexpected parser error: {exc}") from exc
