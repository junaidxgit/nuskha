"""Strands tools for MedLens.

Thin wrappers over medlens.queries. Each is decorated with @tool so Strands
derives the tool spec from the signature, type hints and docstring - which is
why the docstrings are written as instructions to the model rather than as
documentation for a human.

The tools return structured dicts, not prose. Formatting decisions (how to
present a Tier 1 record versus a Tier 2 record) belong to the agent's system
prompt, not to the data layer.
"""

from __future__ import annotations

from strands import tool

from medlens.queries import (
    check_quality_record as _check,
    find_alternatives as _find,
    get_price as _price,
)


@tool
def find_alternatives(salt: str, strength: str = "") -> dict:
    """Find medicines with the same composition and strength from official price lists.

    Use this when the user names a salt (the active ingredient written on their
    prescription) and wants to know what else contains it. Input is
    composition-first: pass "paracetamol", not "Dolo 650". Brand names cannot be
    resolved, because no public dataset maps Indian brand names to compositions.

    Args:
        salt: The active ingredient, e.g. "atorvastatin" or "metformin".
        strength: Optional dose to match exactly, e.g. "10mg" or "500 mg".
            Strongly recommended - without it the results mix doses and the
            cheapest row will be the lowest strength, which is misleading.

    Returns:
        Dict with generic_options (Jan Aushadhi) and scheduled_options (NPPA),
        each carrying an is_combination flag. Prefer rows where is_combination
        is false; those are the single-ingredient products.
    """
    return _find(salt, strength)


@tool
def get_price(salt: str, strength: str = "") -> dict:
    """Get the legal maximum price and the government generic price for a composition.

    Two figures: the NPPA ceiling (legally binding maximum retail price for a
    scheduled formulation - charging above it is illegal) and the Jan Aushadhi
    price (the government's own generic). Both are strength-matched.

    Args:
        salt: The active ingredient, e.g. "atorvastatin".
        strength: Optional dose, e.g. "10mg". Pass it whenever known.

    Returns:
        Dict with ceiling, floor and comparison. comparison is null when the two
        sources disagree on unit kind, or when either side has no same-strength
        match. Check the caveats list: it flags when a match is a combination
        product rather than the single ingredient.
    """
    return _price(salt, strength)


@tool
def check_quality_record(name: str) -> dict:
    """Check regulatory quality records for a product or manufacturer.

    Returns two tiers that MUST be presented separately and never blended:

      tier1_nsq_batch_alerts - CDSCO's list of batches that failed laboratory
          testing. Batch-specific.
      tier2_who_alerts - WHO Medical Product Alerts: recalls, production halts,
          contamination events, falsified products.

    Args:
        name: A manufacturer or product name, e.g. "Sresan Pharmaceutical",
            "Coldrif", or "atorvastatin".

    Returns:
        Dict with both tiers and a framing_rules list. Follow those rules
        exactly when describing the result.
    """
    return _check(name)
