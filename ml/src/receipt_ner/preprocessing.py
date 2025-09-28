"""OCR + geometry helpers shared by dataset building and inference.

LayoutLMv3 expects, per word, a bounding box normalized to the range
``[0, 1000]`` relative to the image size. We run OCR ourselves (Tesseract via
``pytesseract``) rather than letting the processor do it (``apply_ocr=True``)
for two reasons:

1. Training and inference must tokenize identically. If the processor re-ran
   its own OCR at inference time we could not guarantee the word order / boxes
   match what the labels were aligned against.
2. Thermal receipts are noisy. We pin a Tesseract page-segmentation mode and a
   character set tuned for the numeric-heavy McDonald's layout — the same idea
   the original ``helper/vision.js`` prototype used, just kept in one place.
"""

from __future__ import annotations

from typing import List, Tuple

from PIL import Image

try:  # pytesseract is only needed for OCR paths, not for pure label/postprocess tests
    import pytesseract
    from pytesseract import Output
except ImportError:  # pragma: no cover
    pytesseract = None
    Output = None


Box = List[int]

# Page segmentation mode 6 = "assume a single uniform block of text", which is
# a good default for the boxy receipt layout. We keep letters so labels like
# "TOTAL" / "Survey Code" survive to give the model textual context.
_TESSERACT_CONFIG = "--oem 1 --psm 6"

# Tokens below this confidence are almost always noise from the paper texture.
_MIN_CONFIDENCE = 30.0


def load_image(path: str) -> Image.Image:
    """Open an image and force RGB (LayoutLMv3's image processor expects 3 channels)."""
    return Image.open(path).convert("RGB")


def normalize_box(box: Box, width: int, height: int) -> Box:
    """Scale a pixel box ``[x0, y0, x1, y1]`` to the LayoutLM ``[0, 1000]`` grid.

    Values are clamped: skewed thermal scans occasionally yield a box edge a
    pixel or two outside the image, and LayoutLMv3's position embedding table
    raises on any coordinate > 1000.
    """
    x0, y0, x1, y1 = box
    scaled = [
        int(1000 * x0 / width),
        int(1000 * y0 / height),
        int(1000 * x1 / width),
        int(1000 * y1 / height),
    ]
    return [min(1000, max(0, v)) for v in scaled]


def run_ocr(image_path: str) -> Tuple[List[str], List[Box], List[float]]:
    """Run Tesseract and return ``(words, pixel_boxes, confidences)``.

    ``pixel_boxes`` are ``[x0, y0, x1, y1]`` in image pixels (NOT yet
    normalized) so callers can normalize against the exact image they loaded.
    """
    if pytesseract is None:
        raise RuntimeError(
            "pytesseract is not installed. Install it and the `tesseract-ocr` "
            "system binary to run OCR (see ml/README.md)."
        )

    image = load_image(image_path)
    data = pytesseract.image_to_data(
        image, config=_TESSERACT_CONFIG, output_type=Output.DICT
    )

    words: List[str] = []
    boxes: List[Box] = []
    confidences: List[float] = []

    for i in range(len(data["text"])):
        word = data["text"][i].strip()
        if not word:
            continue
        try:
            conf = float(data["conf"][i])
        except (TypeError, ValueError):
            conf = -1.0
        if conf < _MIN_CONFIDENCE:
            continue

        x, y, w, h = (
            data["left"][i],
            data["top"][i],
            data["width"][i],
            data["height"][i],
        )
        words.append(word)
        boxes.append([x, y, x + w, y + h])
        confidences.append(conf)

    return words, boxes, confidences
