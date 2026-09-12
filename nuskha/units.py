"""Unit and strength handling.

Shared by the ETL (`pipeline/build_db.py`) and the query layer
(`nuskha/queries.py`). It lives here rather than in either one because the
code review found the same logic duplicated in both, and the unit-mismatch bug
had to be fixed twice as a result.

Two distinct jobs:

  * `parse_unit` / `unit_kind` - split a quantity from its unit kind so prices
    can be compared per unit. NPPA says "per 1 Capsule", Jan Aushadhi says
    "per 10's"; comparing those raw puts the floor above the ceiling.
  * `strengths_of` - extract a normalised strength signature so "metformin
    250 mg" cannot match a 500 mg product.
"""

from __future__ import annotations

import re

# Order matters: first match wins, so more specific kinds come first.
KIND_PATTERNS = [
    ("tablet",  r"\btablet"),
    ("capsule", r"\bcapsule"),
    ("ml",      r"\bml\b|\binjection\b|\bsyrup\b|\bsuspension\b|\bsolution\b|\bdrop"),
    ("g",       r"\bg\b|\bgm\b|\bgram|\bgel\b|\bcream\b|\bointment\b|\bpowder\b"),
    ("sachet",  r"\bsachet\b"),
    ("patch",   r"\bpatch\b"),
]

# Dosage forms the UI and tools can filter on. Deliberately the same vocabulary
# as KIND_PATTERNS so a form filter and a unit comparison agree.
FORMS = ("tablet", "capsule", "ml", "g", "sachet", "patch")

# What a user actually types, mapped onto that vocabulary. Without this,
# form="syrup" silently matches nothing and the filter is a no-op.
FORM_SYNONYMS = {
    "tablet": "tablet", "tablets": "tablet", "tab": "tablet", "tabs": "tablet",
    "capsule": "capsule", "capsules": "capsule", "cap": "capsule",
    "syrup": "ml", "suspension": "ml", "solution": "ml", "injection": "ml",
    "injectable": "ml", "liquid": "ml", "drops": "ml", "drop": "ml",
    "oral liquid": "ml", "ml": "ml",
    "gel": "g", "cream": "g", "ointment": "g", "powder": "g", "g": "g",
    "gram": "g", "sachet": "g", "sachets": "g",
    "patch": "patch", "patches": "patch",
}


def normalize_form(form: str) -> str | None:
    """Map a user-supplied dosage form onto a KIND_PATTERNS kind, or None."""
    f = (form or "").strip().lower()
    if not f:
        return None
    if f in FORM_SYNONYMS:
        return FORM_SYNONYMS[f]
    if f in FORMS:
        return f
    return None

STRENGTH = re.compile(
    r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>mg|mcg|µg|g|gm|ml|iu|%|w/w|w/v)\b",
    re.I,
)

# mass units normalise to a common base so 1000mg == 1g
_MASS_TO_MG = {"mg": 1.0, "mcg": 0.001, "µg": 0.001, "g": 1000.0, "gm": 1000.0}


def strengths_of(text: str) -> set[str]:
    """Normalised strength signature, e.g. {'10mg'} or {'500mg','125mg'}.

    Mass units are converted to a common base, so "1000 mg" and "1 g" produce
    the same signature. Volume and IU are left in their own units because they
    are not inter-convertible with mass.
    """
    out: set[str] = set()
    for m in STRENGTH.finditer(text or ""):
        unit = m.group("unit").lower()
        value = float(m.group("value"))
        if unit in _MASS_TO_MG:
            out.add(f"{value * _MASS_TO_MG[unit]:g}mg")
        else:
            out.add(f"{value:g}{unit}")
    return out


def unit_kind(text: str, fallback: str = "") -> str:
    """Classify a unit or product name into tablet / capsule / ml / g / ..."""
    t = f"{text} {fallback}".lower()
    for kind, pattern in KIND_PATTERNS:
        if re.search(pattern, t):
            return kind
    return "unit"


def parse_unit(raw: str, name: str = "") -> tuple[float, str]:
    """Return (quantity, kind) so prices can be compared per unit.

    "10's" -> (10, kind-inferred-from-name); "1 Capsule" -> (1, 'capsule').
    """
    s = (raw or "").strip()
    m = re.match(r"^(\d+(?:\.\d+)?)\s*'?s?\s*(.*)$", s)
    if not m:
        return 1.0, unit_kind(s, name)
    qty = float(m.group(1)) or 1.0
    tail = m.group(2).strip()
    kind = unit_kind(tail, name) if tail else unit_kind(name)
    if kind == "unit":
        kind = unit_kind(name)
    return qty, kind
