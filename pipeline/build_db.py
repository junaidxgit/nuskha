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
WHO_JSONL = ROOT / "data" / "processed" / "who_alerts.jsonl"
WHO_STRUCT = ROOT / "data" / "processed" / "who_alerts_structured.jsonl"
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
    if not NSQ_JSONL.exists():
        return 0
    rows = [json.loads(l) for l in NSQ_JSONL.open(encoding="utf-8")]
    con.executemany(
        "INSERT INTO nsq_records (source_file, alert_type, series, alert_year,"
        " alert_month, page, sno, product_name, product_key, batch_no, mfg_date,"
        " expiry_date, mfg_ym, expiry_ym, manufacturer, maker_key, nsq_reason,"
        " reported_by) VALUES (" + ",".join("?" * 18) + ")",
        [(
            r.get("source_file"), r.get("alert_type"), r.get("series"),
            r.get("alert_year"), r.get("alert_month"), r.get("page"),
            r.get("sno"), r.get("product_name"), norm_key(r.get("product_name", "")),
            r.get("batch_no"), r.get("mfg_date"), r.get("expiry_date"),
            r.get("mfg_ym"), r.get("expiry_ym"),
            r.get("manufacturer"), norm_key(r.get("manufacturer", "")),
            r.get("nsq_reason"), r.get("reported_by"),
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

    n_nsq = load_nsq(con)
    n_who = load_who(con)

    for stmt in (
        "CREATE INDEX idx_maker ON nsq_records(maker_key)",
        "CREATE INDEX idx_product ON nsq_records(product_key)",
        "CREATE INDEX idx_ym ON nsq_records(alert_year, alert_month)",
        "CREATE INDEX idx_who_year ON who_alerts(alert_year)",
    ):
        con.execute(stmt)
    con.commit()
    print(f"medlens.db built: {n_nsq:,} NSQ records (Tier 1), "
          f"{n_who:,} WHO alerts (Tier 2)")
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", help="run a tiered lookup for a term")
    ap.add_argument("--manufacturer", help="NSQ lookup by manufacturer only")
    ap.add_argument("--product", help="NSQ lookup by product only")
    ap.add_argument("--limit", type=int, default=6)
    args = ap.parse_args()

    con = build()

    if args.check:
        check(con, args.check, args.limit)
    if args.manufacturer:
        check(con, args.manufacturer, args.limit)
    if args.product:
        check(con, args.product, args.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
