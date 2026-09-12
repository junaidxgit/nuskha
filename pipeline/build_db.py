"""Build the combined index and run lookups.

Two tables, deliberately kept separate so the UI can render them at different
authority levels (see docs/source-policy.md):

  nsq_records  Tier 1 - CDSCO NSQ batch alerts (batches that failed lab testing)
  who_alerts   Tier 2 - WHO Medical Product Alerts (recalls, suspensions,
                        contamination events, falsified products)

They are never merged into a single verdict. A Tier 2 hit is rendered as
"published by WHO", a Tier 1 hit as "recorded by CDSCO".

Run:
    python pipeline/build_db.py
    python pipeline/build_db.py --check "paracetamol"
    python pipeline/build_db.py --check "coldrif"
    python pipeline/build_db.py --check "sresan"
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NSQ_JSONL = ROOT / "data" / "processed" / "nsq_records.jsonl"
NSQ_RECENT_JSONL = ROOT / "data" / "processed" / "nsq_records_recent.jsonl"
WHO_JSONL = ROOT / "data" / "processed" / "who_alerts.jsonl"
WHO_STRUCT = ROOT / "data" / "processed" / "who_alerts_structured.jsonl"
NPPA_JSONL = ROOT / "data" / "processed" / "nppa_ceiling_prices.jsonl"
JA_JSONL = ROOT / "data" / "processed" / "janaushadhi_prices.jsonl"
DB = ROOT / "data" / "processed" / "medlens.db"

NOISE = re.compile(
    r"\b(m/s|ms|m/s\.|pvt|private|ltd|limited|llp|inc|co|company|"
    r"pharmaceuticals|pharmaceutical|pharma|pharmacia|laboratories|"
    r"laboratory|labs|lab|industries|healthcare|biotech|sciences|"
    r"unit|plot|no|phase)\b",
    re.I,
)


def norm_key(value: str) -> str:
    """Aggressive normalisation so 'M/s. Rhombus Pharma Pvt. Ltd.' matches
    'M/s.Rhombus Pharma Private Limited.,'. Deliberately lossy: for candidate
    retrieval only, never for display."""
    if not value:
        return ""
    s = value.lower()
    s = re.sub(r"[,.;:\-()/&'\"]", " ", s)
    s = NOISE.sub(" ", s)
    s = re.sub(r"\b\d{4,}\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def load_nsq(con: sqlite3.Connection) -> int:
    """Load both NSQ datasets.

    nsq_records.jsonl        2024-01..2025-06, bordered-table layout
    nsq_records_recent.jsonl 2025-07..2026-07, cell-rect layout

    They are separate files because the layouts differ, but they belong in one
    table: to a user asking about a medicine there is no seam between them.
    """
    rows = []
    for path in (NSQ_JSONL, NSQ_RECENT_JSONL):
        if path.exists():
            rows.extend(json.loads(l) for l in path.open(encoding="utf-8"))
    if not rows:
        return 0

    def g(r, key, default=None):
        v = r.get(key, default)
        return v if v is not None else default

    con.executemany(
        "INSERT INTO nsq_records (source_file, alert_type, series, alert_year,"
        " alert_month, page, sno, product_name, product_key, batch_no, mfg_date,"
        " expiry_date, mfg_ym, expiry_ym, manufacturer, maker_key, nsq_reason,"
        " reported_by) VALUES (" + ",".join("?" * 18) + ")",
        [(
            g(r, "source_file"), g(r, "alert_type"), g(r, "series"),
            g(r, "alert_year"), g(r, "alert_month"), g(r, "page"),
            g(r, "sno"), g(r, "product_name", ""), norm_key(g(r, "product_name", "")),
            g(r, "batch_no"), g(r, "mfg_date"), g(r, "expiry_date"),
            g(r, "mfg_ym"), g(r, "expiry_ym"),
            g(r, "manufacturer", ""), norm_key(g(r, "manufacturer", "")),
            g(r, "nsq_reason"), g(r, "reported_by"),
        ) for r in rows])
    return len(rows)


def load_who(con: sqlite3.Connection) -> int:
    """Load WHO alerts, preferring the structured file when it exists so the
    lookup can name which product matched rather than returning a whole doc."""
    if WHO_STRUCT.exists():
        rows = [json.loads(l) for l in WHO_STRUCT.open(encoding="utf-8")]
    elif WHO_JSONL.exists():
        rows = [json.loads(l) for l in WHO_JSONL.open(encoding="utf-8")]
    else:
        return 0

    payload = []
    for r in rows:
        products = r.get("products") or []
        makers = r.get("manufacturers") or []
        payload.append((
            r.get("alert_label"), r.get("alert_number"), r.get("alert_year"),
            r.get("news_url"), r.get("pdf_url"), r.get("local_path"),
            int(bool(r.get("mentions_india"))), r.get("text", ""),
            norm_key(r.get("text", "")),
            "; ".join(products),
            "; ".join(makers),
            r.get("alert_date"),
            norm_key(" ".join(products)),
            norm_key(" ".join(makers)),
        ))

    con.executemany(
        "INSERT INTO who_alerts (alert_label, alert_number, alert_year, news_url,"
        " pdf_url, local_path, mentions_india, text, text_key, products,"
        " manufacturers, alert_date, product_key, maker_key)"
        " VALUES (" + ",".join("?" * 14) + ")", payload)
    return len(rows)


def load_nppa(con: sqlite3.Connection) -> int:
    """NPPA ceiling prices - the legally binding maximum retail price."""
    if not NPPA_JSONL.exists():
        return 0
    rows = [json.loads(l) for l in NPPA_JSONL.open(encoding="utf-8")]
    con.executemany(
        "INSERT INTO nppa_prices (formulation, formulation_key, composition,"
        " unit, manufacturer, retail_price_inr, notice_ref, notice_year,"
        " notice_month, source_post, provenance) VALUES (" + ",".join("?" * 11) + ")",
        [(
            r.get("formulation"), norm_key(r.get("formulation", "")),
            r.get("composition"), r.get("unit"), r.get("manufacturer"),
            r.get("retail_price_inr"), r.get("notice_ref"), r.get("notice_year"),
            r.get("notice_month"), r.get("source_post"), r.get("provenance"),
        ) for r in rows])
    return len(rows)


def load_janaushadhi(con: sqlite3.Connection) -> int:
    """Jan Aushadhi generic prices - the cheap compliant floor."""
    if not JA_JSONL.exists():
        return 0
    rows = [json.loads(l) for l in JA_JSONL.open(encoding="utf-8")]
    con.executemany(
        "INSERT INTO janaushadhi_prices (drug_code, generic_name, generic_key,"
        " unit_size, mrp_inr, provenance) VALUES (" + ",".join("?" * 6) + ")",
        [(
            r.get("drug_code"), r.get("generic_name"),
            norm_key(r.get("generic_name", "")), r.get("unit_size"),
            r.get("mrp_inr"), r.get("provenance"),
        ) for r in rows])
    return len(rows)


def build() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    if DB.exists():
        DB.unlink()

    con = sqlite3.connect(DB)
    con.execute("""
        CREATE TABLE nsq_records (
            id INTEGER PRIMARY KEY, source_file TEXT, alert_type TEXT, series TEXT,
            alert_year INTEGER, alert_month INTEGER, page INTEGER, sno TEXT,
            product_name TEXT, product_key TEXT, batch_no TEXT, mfg_date TEXT,
            expiry_date TEXT, mfg_ym TEXT, expiry_ym TEXT, manufacturer TEXT,
            maker_key TEXT, nsq_reason TEXT, reported_by TEXT)
    """)
    con.execute("""
        CREATE TABLE who_alerts (
            id INTEGER PRIMARY KEY, alert_label TEXT, alert_number INTEGER,
            alert_year INTEGER, news_url TEXT, pdf_url TEXT, local_path TEXT,
            mentions_india INTEGER, text TEXT, text_key TEXT, products TEXT,
            manufacturers TEXT, alert_date TEXT, product_key TEXT, maker_key TEXT)
    """)

    con.execute("""
        CREATE TABLE nppa_prices (
            id INTEGER PRIMARY KEY, formulation TEXT, formulation_key TEXT,
            composition TEXT, unit TEXT, manufacturer TEXT,
            retail_price_inr REAL, notice_ref TEXT, notice_year INTEGER,
            notice_month INTEGER, source_post TEXT, provenance TEXT)
    """)
    con.execute("""
        CREATE TABLE janaushadhi_prices (
            id INTEGER PRIMARY KEY, drug_code INTEGER, generic_name TEXT,
            generic_key TEXT, unit_size TEXT, mrp_inr REAL, provenance TEXT)
    """)

    n_nsq = load_nsq(con)
    n_who = load_who(con)
    n_nppa = load_nppa(con)
    n_ja = load_janaushadhi(con)

    for stmt in (
        "CREATE INDEX idx_maker ON nsq_records(maker_key)",
        "CREATE INDEX idx_product ON nsq_records(product_key)",
        "CREATE INDEX idx_ym ON nsq_records(alert_year, alert_month)",
        "CREATE INDEX idx_who_year ON who_alerts(alert_year)",
        "CREATE INDEX idx_nppa_key ON nppa_prices(formulation_key)",
        "CREATE INDEX idx_ja_key ON janaushadhi_prices(generic_key)",
    ):
        con.execute(stmt)
    con.commit()
    print(f"medlens.db built:")
    print(f"  {n_nsq:,} NSQ records (Tier 1)")
    print(f"  {n_who:,} WHO alerts (Tier 2)")
    print(f"  {n_nppa:,} NPPA ceiling prices")
    print(f"  {n_ja:,} Jan Aushadhi prices")
    print(f"-> {DB.relative_to(ROOT)}")
    return con


def like_where(column: str, term: str) -> tuple[str, list[str]]:
    """Require every query token to appear, so 'pulse pharma' does not match
    every record containing 'pharma'."""
    key = norm_key(term)
    tokens = [t for t in key.split() if len(t) > 2]
    if not tokens:
        return f"{column} LIKE ?", [f"%{key}%"]
    return " AND ".join(f"{column} LIKE ?" for _ in tokens), \
        [f"%{t}%" for t in tokens]


def check(con: sqlite3.Connection, term: str, limit: int) -> None:
    print(f"\n{'=' * 78}")
    print(f"Checking: {term!r}")
    print("=" * 78)

    where, params = like_where("maker_key", term)
    prod_where, prod_params = like_where("product_key", term)

    nsq = con.execute(
        f"SELECT manufacturer, product_name, batch_no, mfg_date, expiry_date,"
        f" nsq_reason, reported_by, alert_type, series, alert_year, alert_month,"
        f" source_file FROM nsq_records WHERE ({where}) OR ({prod_where})"
        f" ORDER BY alert_year DESC, alert_month DESC LIMIT ?",
        (*params, *prod_params, limit)).fetchall()

    print(f"\n[TIER 1] CDSCO NSQ batch alerts - recorded by the regulator")
    print(f"         {len(nsq)} matching record(s)")
    if not nsq:
        print("         none on record")
    for (maker, product, batch, mfg, exp, reason, lab,
         atype, series, yr, mo, src) in nsq:
        print(f"\n  {product[:72]}")
        print(f"    batch {batch or '-':<16} mfg {mfg or '-':<9} exp {exp or '-'}")
        print(f"    maker  {maker[:86]}")
        print(f"    reason {reason[:86]}")
        print(f"    source {atype} / {series} alert {yr}-{mo:02d}; lab: {lab or '-'}")
        print(f"           file {src}")

    wwhere, wparams = like_where("text_key", term)
    who = con.execute(
        f"SELECT alert_label, alert_year, alert_number, news_url, mentions_india,"
        f" products, manufacturers, alert_date FROM who_alerts WHERE {wwhere}"
        f" ORDER BY alert_year DESC LIMIT ?",
        (*wparams, limit)).fetchall()

    print(f"\n[TIER 2] WHO Medical Product Alerts - published by WHO")
    print(f"         {len(who)} matching alert(s)")
    if not who:
        print("         none on record")
    for (label, yr, num, url, india, products, makers, adate) in who:
        print(f"\n  {label[:92]}")
        print(f"    date    {adate or yr}   india={'yes' if india else 'no'}")
        if products:
            print(f"    products {products[:86]}")
        if makers:
            print(f"    makers   {makers[:86]}")
        print(f"    {url}")

    print(f"\n{'-' * 78}")
    print("  An NSQ finding is batch-specific. A hit means one batch failed")
    print("  testing on one date for the stated reason - not that the company")
    print("  is unsafe. Absence of a hit is NOT evidence of quality: only")
    print("  sampled batches are tested. Not medical advice.")


KIND_PATTERNS = [
    ("tablet",  r"\btablet"),
    ("capsule", r"\bcapsule"),
    ("ml",      r"\bml\b|\binjection\b|\bsyrup\b|\bsuspension\b|\bsolution\b|\bdrop"),
    ("g",       r"\bgm?\b|\bgram|\bgel\b|\bcream\b|\bointment\b|\bpowder\b"),
    ("sachet",  r"\bsachet\b"),
    ("patch",   r"\bpatch\b"),
]

# NPPA unit strings look like "1 Capsule", "1 ml", "1 Tablet".
# Jan Aushadhi unit strings look like "10's", "15 g", "3 ml", "1's".
NPPA_UNIT = re.compile(
    r"(?P<qty>\d+(?:\.\d+)?)\s*(?P<kind>[A-Za-z%][A-Za-z/ ]*)")
JA_UNIT = re.compile(r"(?P<qty>\d+(?:\.\d+)?)\s*(?:'?s\b)?\s*(?P<kind>[A-Za-z]*)?")


def unit_kind(text: str, fallback: str = "") -> str:
    """Classify a unit or product name into tablet / capsule / ml / g / ..."""
    t = f"{text} {fallback}".lower()
    for kind, pattern in KIND_PATTERNS:
        if re.search(pattern, t):
            return kind
    return "unit"


def parse_unit(raw: str, name: str = "") -> tuple[float, str]:
    """Return (quantity, kind) so prices can be compared per unit.

    Without this, 'Rs 3.65 per 1 Capsule' and 'Rs 8.80 per 10's' look comparable
    and produce a nonsense range where the floor sits above the ceiling.
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


def price(con: sqlite3.Connection, term: str, limit: int) -> None:
    """The price half of the answer: legal ceiling and generic floor."""
    print(f"\n{'=' * 78}")
    print(f"Prices for: {term!r}")
    print("=" * 78)

    where, params = like_where("formulation_key", term)
    nppa = con.execute(
        f"SELECT formulation, composition, unit, manufacturer, retail_price_inr,"
        f" notice_ref, notice_year, notice_month FROM nppa_prices"
        f" WHERE {where} ORDER BY retail_price_inr ASC LIMIT ?",
        (*params, limit)).fetchall()

    print(f"\n[CEILING] NPPA scheduled formulation - legally binding maximum")
    print(f"          {len(nppa)} matching entry/entries")
    if not nppa:
        print("          none on record (not a scheduled formulation, or not yet captured)")

    ceiling_per_unit: dict[str, float] = {}
    for (form, comp, unit, maker, rupees, ref, yr, mo) in nppa:
        qty, kind = parse_unit(unit, form)
        per = rupees / qty if qty else rupees
        ceiling_per_unit.setdefault(kind, per)
        ceiling_per_unit[kind] = min(ceiling_per_unit[kind], per)
        print(f"\n  {form[:78]}")
        print(f"    composition {str(comp)[:76]}")
        print(f"    ceiling     Rs {rupees} per {unit}"
              + (f"  (= Rs {per:.2f} per {kind})" if qty != 1 else ""))
        print(f"    maker       {str(maker)[:74]}")
        if yr:
            print(f"    notice      {ref or '-'} ({yr}-{mo:02d})")

    where2, params2 = like_where("generic_key", term)
    ja = con.execute(
        f"SELECT generic_name, unit_size, mrp_inr, drug_code FROM janaushadhi_prices"
        f" WHERE {where2} AND mrp_inr > 0 ORDER BY mrp_inr ASC LIMIT ?",
        (*params2, limit)).fetchall()

    print(f"\n[FLOOR] Jan Aushadhi generic - government-set price")
    print(f"        {len(ja)} matching entry/entries")
    if not ja:
        print("        none on record")

    floor_per_unit: dict[str, float] = {}
    for (name, unit, mrp, code) in ja:
        qty, kind = parse_unit(unit, name)
        per = mrp / qty if qty else mrp
        floor_per_unit.setdefault(kind, per)
        floor_per_unit[kind] = min(floor_per_unit[kind], per)
        print(f"  Rs {mrp:>9} per {unit:<8} {name[:56]}"
              + (f"  (= Rs {per:.2f} per {kind})" if qty != 1 else ""))

    # Only compare like with like. A cross-unit range is meaningless and would
    # put the floor above the ceiling.
    shared = sorted(set(ceiling_per_unit) & set(floor_per_unit))
    if shared:
        print(f"\n  Comparable per-unit ({', '.join(shared)}):")
        for kind in shared:
            lo, hi = floor_per_unit[kind], ceiling_per_unit[kind]
            verdict = "floor below ceiling" if lo <= hi else "CHECK - floor above ceiling"
            print(f"    {kind:<9} floor Rs {lo:.2f}   ceiling Rs {hi:.2f}   ({verdict})")
    elif nppa and ja:
        print("\n  Units differ between the two sources, so no per-unit comparison is")
        print("  shown. Compare within each block above.")

    print(f"\n{'-' * 78}")
    print("  NPPA prices are exclusive of GST. Charging above the ceiling for a")
    print("  scheduled formulation is illegal. This is not medical advice and not")
    print("  a recommendation to substitute - composition match is not proven")
    print("  therapeutic equivalence. Ask your doctor or pharmacist.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", help="run a tiered quality lookup for a term")
    ap.add_argument("--price", help="show NPPA ceiling + Jan Aushadhi price")
    ap.add_argument("--manufacturer", help="NSQ lookup by manufacturer only")
    ap.add_argument("--product", help="NSQ lookup by product only")
    ap.add_argument("--limit", type=int, default=6)
    args = ap.parse_args()

    con = build()

    if args.check:
        check(con, args.check, args.limit)
    if args.price:
        price(con, args.price, args.limit)
    if args.manufacturer:
        check(con, args.manufacturer, args.limit)
    if args.product:
        check(con, args.product, args.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
