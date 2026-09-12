"""Query layer for MedLens.

Three questions, one database:

    find_alternatives(salt, strength)  - what else has this exact composition
    get_price(salt, strength)          - what should it cost
    check_quality_record(name)         - is there a recorded quality failure

Kept separate from the Strands tools (agent/tools.py) and from the CLI so the
same functions back the agent, the demo and any future UI.

Every function returns a plain dict. Nothing here decides what to say - the
framing rules live in docs/source-policy.md and are enforced by the callers.

The database is built by pipeline/build_db.py.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "data" / "processed" / "medlens.db"

# Corporate noise stripped for matching only, never for display
NOISE = re.compile(
    r"\b(m/s|ms|m/s\.|pvt|private|ltd|limited|llp|inc|co|company|"
    r"pharmaceuticals|pharmaceutical|pharma|pharmacia|laboratories|"
    r"laboratory|labs|lab|industries|healthcare|biotech|sciences|"
    r"unit|plot|no|phase)\b",
    re.I,
)

STRENGTH = re.compile(
    r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>mg|mcg|µg|g|gm|ml|iu|%|w/w|w/v)\b",
    re.I,
)

# "Aspirin & Atorvastatin Capsules", "Glimepiride and Metformin", "A, B and C"
COMBINATION = re.compile(r"\s(?:&|and)\s|,", re.I)


def is_combination(text: str) -> bool:
    """True when a formulation contains more than one active ingredient.

    Matters because a strength-only match happily returns
    "Aspirin Gastro-resistant & Atorvastatin Capsules" as the ceiling for plain
    atorvastatin. That is a different medicine, and presenting it as the price
    of atorvastatin would be wrong.
    """
    return bool(COMBINATION.search(text or ""))


def norm_key(value: str) -> str:
    """Lossy normalisation for candidate retrieval. Never used for display."""
    if not value:
        return ""
    s = value.lower()
    s = re.sub(r"[,.;:\-()/&'\"]", " ", s)
    s = NOISE.sub(" ", s)
    s = re.sub(r"\b\d{4,}\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def strengths_of(text: str) -> set[str]:
    """Normalised strength signature, e.g. {'10mg'} or {'500mg','125mg'}.

    This is what stops 'metformin 250 mg' being compared against a 500 mg
    product, or an atorvastatin 10 mg query against an atorvastatin 20 mg
    ceiling. Without it the cheapest match wins regardless of dose, which is
    both useless and unsafe.
    """
    out = set()
    for m in STRENGTH.finditer(text or ""):
        unit = m.group("unit").lower()
        unit = {"gm": "g", "mcg": "mcg", "µg": "mcg"}.get(unit, unit)
        out.add(f"{float(m.group('value')):g}{unit}")
    return out


def _connect(db: Path | None = None) -> sqlite3.Connection:
    path = Path(db) if db else DEFAULT_DB
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found - run: python pipeline/build_db.py")
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    return con


def _like(column: str, term: str) -> tuple[str, list[str]]:
    key = norm_key(term)
    tokens = [t for t in key.split() if len(t) > 2]
    if not tokens:
        return f"{column} LIKE ?", [f"%{key}%"]
    return " AND ".join(f"{column} LIKE ?" for _ in tokens), \
        [f"%{t}%" for t in tokens]


def _disclaimer() -> str:
    return (
        "Not medical advice. Composition match is not proven therapeutic "
        "equivalence - CDSCO does not require bioequivalence studies for "
        "domestically marketed generics. Never change a prescribed medicine "
        "without asking the prescriber."
    )


def find_alternatives(salt: str, strength: str = "", limit: int = 10,
                      db: Path | None = None) -> dict:
    """Same-composition options from the government price lists.

    Composition-first: `salt` is the salt on the prescription ("paracetamol",
    "atorvastatin"), optionally with `strength` ("10mg"). Brand names are not
    accepted as input, because mapping Indian brand names to compositions
    requires a dataset that does not exist publicly.
    """
    query = f"{salt} {strength}".strip()
    want = strengths_of(query)

    con = _connect(db)
    try:
        where, params = _like("generic_key", salt)
        ja = [dict(r) for r in con.execute(
            f"SELECT generic_name, unit_size, mrp_inr, drug_code, provenance"
            f" FROM janaushadhi_prices WHERE ({where}) AND mrp_inr > 0",
            params).fetchall()]

        where2, params2 = _like("formulation_key", salt)
        nppa = [dict(r) for r in con.execute(
            f"SELECT formulation, composition, unit, manufacturer,"
            f" retail_price_inr, notice_ref, notice_year, notice_month, provenance"
            f" FROM nppa_prices WHERE {where2}", params2).fetchall()]
    finally:
        con.close()

    # strength filter
    ja_matched = [r for r in ja
                  if not want or want <= strengths_of(r["generic_name"])]
    nppa_matched = [r for r in nppa
                    if not want or want <= strengths_of(r["composition"])]

    strength_filtered = (len(ja) - len(ja_matched)) + (len(nppa) - len(nppa_matched))

    # Annotate single-ingredient vs combination, and rank single first. A
    # combination product is a legitimate alternative to mention, but it is not
    # the price of the single-ingredient product.
    for r in ja_matched:
        r["is_combination"] = is_combination(r["generic_name"])
    for r in nppa_matched:
        r["is_combination"] = is_combination(r["formulation"])

    ja_matched.sort(key=lambda r: (r["is_combination"], r["mrp_inr"]))
    nppa_matched.sort(key=lambda r: (r["is_combination"], r["retail_price_inr"]))

    single_generic = [r for r in ja_matched if not r["is_combination"]]
    single_scheduled = [r for r in nppa_matched if not r["is_combination"]]

    return {
        "query": {"salt": salt, "strength": strength or None,
                  "strength_signature": sorted(want) or None},
        "generic_options": ja_matched[:limit],
        "scheduled_options": nppa_matched[:limit],
        "counts": {
            "generic": len(ja_matched),
            "scheduled": len(nppa_matched),
            "single_ingredient_generic": len(single_generic),
            "single_ingredient_scheduled": len(single_scheduled),
            "dropped_for_strength_mismatch": strength_filtered,
        },
        "note": _disclaimer(),
    }


def get_price(salt: str, strength: str = "", limit: int = 6,
              db: Path | None = None) -> dict:
    """The legal ceiling (NPPA) and the government generic floor (Jan Aushadhi).

    Both figures are strength-matched. The comparison is only made when the two
    sources agree on the unit kind, because NPPA quotes "per 1 Capsule" and
    Jan Aushadhi quotes "per 10's" - comparing those raw puts the floor above
    the ceiling.
    """
    alt = find_alternatives(salt, strength, limit=limit, db=db)

    ceiling = None
    for row in alt["scheduled_options"]:
        ceiling = {
            "formulation": row["formulation"],
            "composition": row["composition"],
            "unit": row["unit"],
            "price_inr": row["retail_price_inr"],
            "notice": row["notice_ref"],
            "notice_period": (f"{row['notice_year']}-{row['notice_month']:02d}"
                              if row["notice_year"] else None),
            "is_combination": row["is_combination"],
            "provenance": row.get("provenance"),
        }
        break

    floor = None
    for row in alt["generic_options"]:
        floor = {
            "product": row["generic_name"],
            "pack": row["unit_size"],
            "price_inr": row["mrp_inr"],
            "drug_code": row["drug_code"],
            "is_combination": row["is_combination"],
            "provenance": row.get("provenance"),
        }
        break

    caveats = [
        "NPPA prices exclude GST.",
        "Charging above the NPPA ceiling for a scheduled formulation is illegal.",
        "Both figures are strength-matched; if either is null, no same-strength "
        "price was found and no comparison is offered.",
    ]
    # Honesty about where the figures came from. The price tables were obtained
    # from a trade-press mirror of the NPPA notifications and a third-party host
    # of the Jan Aushadhi list, not from the issuing bodies directly. The source
    # policy says authority levels must never blend, so a mirrored figure must
    # not be presented as though it were pulled from the regulator.
    mirrored = [n for n, p in (("NPPA ceiling", ceiling and ceiling.get("provenance")),
                               ("Jan Aushadhi floor", floor and floor.get("provenance")))
                if p == "mirror"]
    if mirrored:
        caveats.append(
            "PROVENANCE: " + " and ".join(mirrored) + " come from a third-party "
            "mirror of the official document, not from the issuing body. Verify "
            "against the primary source before relying on it."
        )
    if ceiling and ceiling["is_combination"]:
        caveats.append(
            "WARNING: the ceiling shown is a COMBINATION product that contains "
            "this ingredient. It is not the price of the single ingredient."
        )
    if floor and floor["is_combination"]:
        caveats.append(
            "WARNING: the generic shown is a COMBINATION product that contains "
            "this ingredient."
        )

    comparison = None
    if ceiling and floor:
        from pipeline.build_db import parse_unit
        c_qty, c_kind = parse_unit(ceiling["unit"], ceiling["formulation"])
        f_qty, f_kind = parse_unit(floor["pack"], floor["product"])
        if c_kind == f_kind and c_qty and f_qty:
            per_ceiling = ceiling["price_inr"] / c_qty
            per_floor = floor["price_inr"] / f_qty
            comparison = {
                "unit_kind": c_kind,
                "ceiling_per_unit_inr": round(per_ceiling, 2),
                "floor_per_unit_inr": round(per_floor, 2),
                "ratio": round(per_ceiling / per_floor, 1) if per_floor else None,
                "sanity": ("floor below ceiling" if per_floor <= per_ceiling
                           else "CHECK - floor above ceiling"),
            }

    return {
        "query": alt["query"],
        "ceiling": ceiling,
        "floor": floor,
        "comparison": comparison,
        "caveats": caveats,
        "note": _disclaimer(),
    }


def check_quality_record(name: str, limit: int = 6,
                         db: Path | None = None) -> dict:
    """Regulatory records for a product or manufacturer.

    Two tiers, returned separately and never merged:

      tier1_nsq_batch_alerts  CDSCO - batches that failed laboratory testing
      tier2_who_alerts        WHO   - recalls, suspensions, contamination events

    An NSQ hit is BATCH-SPECIFIC. A firm with one flagged batch is not an
    "adulterated manufacturer", and absence of a hit is not evidence of quality
    because only sampled batches are tested.
    """
    con = _connect(db)
    try:
        w1, p1 = _like("maker_key", name)
        w2, p2 = _like("product_key", name)
        nsq = [dict(r) for r in con.execute(
            f"SELECT manufacturer, product_name, batch_no, mfg_date, expiry_date,"
            f" nsq_reason, reported_by, alert_type, series, alert_year,"
            f" alert_month, source_file FROM nsq_records"
            f" WHERE ({w1}) OR ({w2})"
            f" ORDER BY alert_year DESC, alert_month DESC LIMIT ?",
            (*p1, *p2, limit)).fetchall()]

        w3, p3 = _like("text_key", name)
        who = [dict(r) for r in con.execute(
            f"SELECT alert_label, alert_number, alert_year, alert_date,"
            f" products, manufacturers, news_url, mentions_india"
            f" FROM who_alerts WHERE {w3} ORDER BY alert_year DESC LIMIT ?",
            (*p3, limit)).fetchall()]
    finally:
        con.close()

    return {
        "query": name,
        "tier1_nsq_batch_alerts": {
            "source": "CDSCO NSQ alerts (batches that failed laboratory testing)",
            "count": len(nsq),
            "records": nsq,
        },
        "tier2_who_alerts": {
            "source": "WHO Medical Product Alerts (recalls, suspensions, contamination)",
            "count": len(who),
            "records": who,
        },
        "framing_rules": [
            "An NSQ finding is batch-specific. It is not a statement about the company.",
            "Absence of a record is NOT evidence of quality: only sampled batches are tested.",
            "Mirror the government record verbatim, with batch number and date. "
            "Never score, rank or editorialise.",
        ],
        "note": _disclaimer(),
    }
