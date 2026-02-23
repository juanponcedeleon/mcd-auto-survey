"""Turn per-token BIO predictions into a clean fields dict.

This module is the bridge between the model and the rest of the product: the
JS app only needs the ``survey_code`` string in the canonical format
``#####-#####-#####-#####-#####-#``. Everything here is plain Python (no torch)
so it is trivially unit-testable and importable without the heavy deps.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

from .labels import entity_of

# 5-5-5-5-5-1 groups of digits separated by hyphens.
SURVEY_CODE_RE = re.compile(r"\d{5}-\d{5}-\d{5}-\d{5}-\d{5}-\d")
# The digit layout without the separators (26 digits total).
_GROUP_SIZES = [5, 5, 5, 5, 5, 1]


def group_entities(words: List[str], tags: List[str]) -> Dict[str, List[str]]:
    """Group a BIO tag sequence into ``{entity: [span_text, ...]}``.

    Standard BIO decoding: ``B-X`` opens a span, ``I-X`` extends the currently
    open span of the same type, anything else closes it. A stray ``I-X`` with
    no open span is treated as a ``B-X`` (models occasionally emit these).
    """
    grouped: Dict[str, List[str]] = {}
    current_entity: Optional[str] = None
    current_tokens: List[str] = []

    def flush():
        nonlocal current_entity, current_tokens
        if current_entity and current_tokens:
            grouped.setdefault(current_entity, []).append(" ".join(current_tokens))
        current_entity, current_tokens = None, []

    for word, tag in zip(words, tags):
        if tag == "O":
            flush()
            continue
        prefix, entity = tag.split("-", 1)
        if prefix == "B" or entity != current_entity:
            flush()
            current_entity = entity
            current_tokens = [word]
        else:  # I- continuation of the same entity
            current_tokens.append(word)
    flush()
    return grouped


def assemble_survey_code(spans: List[str]) -> Optional[str]:
    """Normalize a ``SURVEY_CODE`` span into the canonical hyphenated form.

    OCR is inconsistent about the code: it may arrive as one token, split
    across several, with spaces, or with some/all hyphens dropped. We take the
    longest span (the fullest read), keep only digits and hyphens, and:

    * if it already matches the canonical pattern, return it;
    * otherwise, if we have exactly 26 digits, re-insert the 5-5-5-5-5-1
      hyphens ourselves.
    """
    if not spans:
        return None

    candidate = max(spans, key=len)
    cleaned = re.sub(r"[^0-9-]", "", candidate)

    match = SURVEY_CODE_RE.search(cleaned)
    if match:
        return match.group(0)

    digits = re.sub(r"\D", "", cleaned)
    if len(digits) == sum(_GROUP_SIZES):
        parts, offset = [], 0
        for size in _GROUP_SIZES:
            parts.append(digits[offset:offset + size])
            offset += size
        rebuilt = "-".join(parts)
        if SURVEY_CODE_RE.fullmatch(rebuilt):
            return rebuilt

    return None


def _first(spans: Optional[List[str]]) -> Optional[str]:
    return spans[0] if spans else None


def to_fields(words: List[str], tags: List[str],
              confidence: Optional[float] = None) -> Dict[str, Optional[object]]:
    """Build the final fields dict consumed by the app / API.

    ``confidence`` (mean soft-max prob over the survey-code tokens) is surfaced
    so the caller can decide whether to auto-submit or ask the user to confirm.
    """
    grouped = group_entities(words, tags)

    fields = {
        "survey_code": assemble_survey_code(grouped.get("SURVEY_CODE", [])),
        "store_num": _first(grouped.get("STORE_NUM")),
        "date": _first(grouped.get("DATE")),
        "time": _first(grouped.get("TIME")),
        "order_id": _first(grouped.get("ORDER_ID")),
        "total": _first(grouped.get("TOTAL")),
    }
    if confidence is not None:
        fields["confidence"] = round(float(confidence), 4)
    return fields


def code_span_confidence(tags: List[str], token_probs: List[float]) -> Optional[float]:
    """Mean probability over the tokens tagged as part of the survey code."""
    vals = [p for tag, p in zip(tags, token_probs) if entity_of(tag) == "SURVEY_CODE"]
    if not vals:
        return None
    return sum(vals) / len(vals)
