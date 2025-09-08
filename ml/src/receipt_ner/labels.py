"""Label schema for receipt field extraction.

Single source of truth for the token-classification tag set. Everything
downstream (dataset builder, model head, seqeval metrics, post-processing)
imports from here so the label space can never drift between components.

We use BIO tagging over six entity types. The only field that is strictly
required by the downstream survey automation is ``SURVEY_CODE``; the rest are
extracted because they are cheap to label once the receipt is in front of the
annotator and useful for analytics / dedup.
"""

# Order matters: this is the canonical entity ordering used in the README
# results table and the model card.
ENTITIES = [
    "SURVEY_CODE",  # 26-digit mcdvoice code, format #####-#####-#####-#####-#####-#
    "STORE_NUM",    # restaurant / store number, e.g. #04582
    "DATE",         # visit date
    "TIME",         # visit time
    "ORDER_ID",     # KS / order number
    "TOTAL",        # order total
]


def build_labels():
    """Expand the entity list into a flat BIO label list.

    Returns ``["O", "B-SURVEY_CODE", "I-SURVEY_CODE", ...]`` — 1 + 2 * N labels.
    """
    labels = ["O"]
    for entity in ENTITIES:
        labels.append(f"B-{entity}")
        labels.append(f"I-{entity}")
    return labels


LABELS = build_labels()
NUM_LABELS = len(LABELS)

LABEL2ID = {label: idx for idx, label in enumerate(LABELS)}
ID2LABEL = {idx: label for label, idx in LABEL2ID.items()}


def entity_of(label):
    """Strip the BIO prefix from a label. ``"B-DATE" -> "DATE"``, ``"O" -> None``."""
    if label == "O":
        return None
    return label.split("-", 1)[1]
