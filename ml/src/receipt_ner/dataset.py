"""Build a HuggingFace ``DatasetDict`` from the annotation JSON files.

Annotation format (one JSON per receipt, see ``data/annotations/*.json``)::

    {
      "id": "receipt_0001",
      "image_path": "data/images/receipt_0001.jpg",
      "image_size": [width, height],
      "words":    ["McDonald's", "#04582", ...],
      "boxes":    [[x0, y0, x1, y1], ...],   # already normalized to 0-1000
      "ner_tags": [0, 3, ...]                # ints parallel to `words`
    }

Boxes are stored pre-normalized so this loader is deterministic and does not
depend on the image being present just to read the labels. Splits are defined
by basename lists under ``data/splits/{train,val,test}.txt``.
"""

from __future__ import annotations

import json
import os
from typing import Dict, List

from datasets import Dataset, DatasetDict, Features, Sequence, Value, Array2D

from .labels import LABELS

# Feature schema keeps `boxes` as a 2D int array so `datasets` doesn't try to
# infer (and occasionally mangle) the nested list type.
FEATURES = Features(
    {
        "id": Value("string"),
        "image_path": Value("string"),
        "words": Sequence(Value("string")),
        "boxes": Array2D(shape=(None, 4), dtype="int64"),
        "ner_tags": Sequence(Value("int64")),
    }
)


def _read_split(splits_dir: str, name: str) -> List[str]:
    path = os.path.join(splits_dir, f"{name}.txt")
    with open(path, "r", encoding="utf-8") as fh:
        return [line.strip() for line in fh if line.strip()]


def _load_annotation(ann_dir: str, basename: str, root: str) -> Dict:
    with open(os.path.join(ann_dir, f"{basename}.json"), "r", encoding="utf-8") as fh:
        record = json.load(fh)

    # Resolve the image path relative to the project root so the loader works
    # regardless of the current working directory.
    record["image_path"] = os.path.join(root, record["image_path"])

    n = len(record["words"])
    assert len(record["boxes"]) == n, f"{basename}: boxes/words length mismatch"
    assert len(record["ner_tags"]) == n, f"{basename}: tags/words length mismatch"
    for tag in record["ner_tags"]:
        assert 0 <= tag < len(LABELS), f"{basename}: tag {tag} out of range"

    return {
        "id": record["id"],
        "image_path": record["image_path"],
        "words": record["words"],
        "boxes": record["boxes"],
        "ner_tags": record["ner_tags"],
    }


def _build_split(ann_dir: str, basenames: List[str], root: str) -> Dataset:
    rows = [_load_annotation(ann_dir, b, root) for b in basenames]
    return Dataset.from_list(rows, features=FEATURES)


def load_splits(data_dir: str, project_root: str | None = None) -> DatasetDict:
    """Load train/val/test splits from ``data_dir``.

    ``data_dir`` is expected to contain ``annotations/`` and ``splits/``.
    ``project_root`` is prepended to the (repo-relative) image paths; defaults
    to the parent of ``data_dir``.
    """
    ann_dir = os.path.join(data_dir, "annotations")
    splits_dir = os.path.join(data_dir, "splits")
    root = project_root or os.path.dirname(os.path.abspath(data_dir))

    return DatasetDict(
        {
            split: _build_split(ann_dir, _read_split(splits_dir, split), root)
            for split in ("train", "val", "test")
        }
    )
