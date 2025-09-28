"""Bootstrap an annotation file from a raw receipt image.

Runs OCR, normalizes boxes to the LayoutLM 0-1000 grid, and writes a JSON
skeleton with every token pre-labelled ``O`` (tag id 0). The output is then
loaded into Label Studio for a human to correct the few non-``O`` spans — far
faster than boxing from scratch.

Usage::

    python scripts/ocr_to_annotation.py data/images/receipt_0007.jpg
"""

from __future__ import annotations

import argparse
import json
import os
import sys

# Allow running as a plain script (`python scripts/...`) without installing.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from receipt_ner.preprocessing import load_image, normalize_box, run_ocr  # noqa: E402


def build_skeleton(image_path: str, out_dir: str) -> str:
    words, pixel_boxes, _ = run_ocr(image_path)
    image = load_image(image_path)
    width, height = image.size
    boxes = [normalize_box(box, width, height) for box in pixel_boxes]

    basename = os.path.splitext(os.path.basename(image_path))[0]
    record = {
        "id": basename,
        "image_path": os.path.relpath(image_path, os.path.join(out_dir, "..", "..")),
        "image_size": [width, height],
        "words": words,
        "boxes": boxes,
        "ner_tags": [0] * len(words),  # all O; label the spans in Label Studio
    }

    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{basename}.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=2)
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="OCR -> annotation skeleton")
    parser.add_argument("image")
    parser.add_argument("--out-dir", default="data/annotations")
    args = parser.parse_args()

    out_path = build_skeleton(args.image, args.out_dir)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
