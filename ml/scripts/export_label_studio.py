"""Convert a Label Studio JSON-MIN export into repo annotation files.

Label Studio exports rectangle-label results with per-region coordinates as
percentages of the image plus the transcription of each region. We map each
labelled region back onto the OCR token whose box it best overlaps, then emit
one ``data/annotations/<id>.json`` per task in the format ``dataset.py`` reads.

Usage::

    python scripts/export_label_studio.py export.json --images data/images
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from receipt_ner.labels import LABEL2ID  # noqa: E402
from receipt_ner.preprocessing import load_image, normalize_box, run_ocr  # noqa: E402


def _iou(a, b):
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    inter = max(0, ix1 - ix0) * max(0, iy1 - iy0)
    if inter == 0:
        return 0.0
    area_a = (ax1 - ax0) * (ay1 - ay0)
    area_b = (bx1 - bx0) * (by1 - by0)
    return inter / (area_a + area_b - inter)


def _regions(task):
    """Yield ``(entity, box_0_1000)`` for each rectangle-label region."""
    for ann in task.get("annotations", []):
        for result in ann.get("result", []):
            value = result.get("value", {})
            labels = value.get("labels") or value.get("rectanglelabels")
            if not labels:
                continue
            # Label Studio stores x/y/width/height as percentages (0-100).
            x0 = value["x"] * 10
            y0 = value["y"] * 10
            x1 = (value["x"] + value["width"]) * 10
            y1 = (value["y"] + value["height"]) * 10
            yield labels[0], [int(x0), int(y0), int(x1), int(y1)]


def convert(task, images_dir, out_dir):
    filename = os.path.basename(task["data"]["ocr"])
    image_path = os.path.join(images_dir, filename)

    words, pixel_boxes, _ = run_ocr(image_path)
    width, height = load_image(image_path).size
    boxes = [normalize_box(b, width, height) for b in pixel_boxes]
    tags = [0] * len(words)

    for entity, region_box in _regions(task):
        # Assign BIO tags to every token overlapping this region, in reading order.
        hits = [i for i, box in enumerate(boxes) if _iou(box, region_box) > 0.3]
        for order, i in enumerate(sorted(hits)):
            prefix = "B" if order == 0 else "I"
            tags[i] = LABEL2ID[f"{prefix}-{entity}"]

    basename = os.path.splitext(filename)[0]
    record = {
        "id": basename,
        "image_path": os.path.join("data/images", filename),
        "image_size": [width, height],
        "words": words,
        "boxes": boxes,
        "ner_tags": tags,
    }
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{basename}.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=2)
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Label Studio export -> annotations")
    parser.add_argument("export")
    parser.add_argument("--images", default="data/images")
    parser.add_argument("--out-dir", default="data/annotations")
    args = parser.parse_args()

    with open(args.export, "r", encoding="utf-8") as fh:
        tasks = json.load(fh)

    for task in tasks:
        print("Wrote", convert(task, args.images, args.out_dir))


if __name__ == "__main__":
    main()
