"""MedLens CLI.

Two modes:

  deterministic  - calls the query layer directly and formats the answer. No
                   model, no credentials, no network. This is what the demo
                   video should use, because it cannot fail on stage.
  agent          - runs the real Strands agent. Needs model credentials.

Usage:
    python -m medlens.cli price atorvastatin 10mg
    python -m medlens.cli check coldrif
    python -m medlens.cli report atorvastatin 10mg
    python -m medlens.cli ask "what should atorvastatin 10mg cost?"
"""

from __future__ import annotations

import argparse
import json
import sys

from medlens.queries import check_quality_record, find_alternatives, get_price

RULE = "-" * 76


def _money(v) -> str:
    return f"Rs {v:,.2f}" if isinstance(v, (int, float)) else "Rs -"


def show_price(salt: str, strength: str = "") -> None:
    r = get_price(salt, strength)
    q = r["query"]
    head = f"{q['salt']}" + (f" {q['strength']}" if q["strength"] else "")

    print(f"\n{head}")
    print(RULE)

    c = r["ceiling"]
    if c:
        print(f"  LEGAL MAXIMUM  {_money(c['price_inr'])} per {c['unit']}")
        print(f"                 {c['formulation']}")
        if c.get("notice"):
            print(f"                 {c['notice']}"
                  + (f" ({c['notice_period']})" if c.get("notice_period") else ""))
    else:
        print("  LEGAL MAXIMUM  no same-strength NPPA ceiling on record")

    f = r["floor"]
    if f:
        print(f"\n  GOVT GENERIC   {_money(f['price_inr'])} per {f['pack']}")
        print(f"                 {f['product']}")
    else:
        print("\n  GOVT GENERIC   no same-strength Jan Aushadhi product on record")

    cmp_ = r["comparison"]
    if cmp_:
        print(f"\n  PER {cmp_['unit_kind'].upper():<10} ceiling {_money(cmp_['ceiling_per_unit_inr'])}"
              f"   floor {_money(cmp_['floor_per_unit_inr'])}"
              f"   ratio {cmp_['ratio']}x")
        print(f"  SANITY         {cmp_['sanity']}")
    elif c and f:
        print("\n  No per-unit comparison: the two sources quote different units.")

    for cav in r["caveats"]:
        if cav.startswith(("WARNING", "PROVENANCE")):
            print(f"\n  ! {cav}")

    print(f"\n  NPPA prices exclude GST. Charging above the ceiling for a scheduled")
    print(f"  formulation is illegal. Not medical advice - composition match is not")
    print(f"  proven therapeutic equivalence. Ask your prescriber before changing anything.")


def show_quality(name: str) -> None:
    r = check_quality_record(name)
    print(f"\nQuality records for: {r['query']}")
    print(RULE)

    t1 = r["tier1_nsq_batch_alerts"]
    print(f"\n[TIER 1] {t1['source']}")
    # a state-lab alert is a state finding, not a central CDSCO one
    state_recs = [x for x in t1["records"] if x.get("series") == "state"]
    if state_recs:
        print("         (some records below are STATE laboratory findings, "
              "not central CDSCO)")
    print(f"         {t1['count']} matching record(s)")
    if not t1["count"]:
        print("         none on record")
    for rec in t1["records"]:
        print(f"\n  {rec['product_name'][:70]}")
        print(f"    batch  {rec['batch_no'] or '-'}")
        print(f"    maker  {rec['manufacturer'][:66]}")
        print(f"    reason {rec['nsq_reason'][:66]}")
        who_lab = "state" if rec["series"] == "state" else "central"
        print(f"    source {who_lab} lab alert {rec['alert_year']}-{rec['alert_month']:02d}")
        print(f"    file   {rec['source_file']}  (source URL in the manifest)")

    t2 = r["tier2_who_alerts"]
    print(f"\n[TIER 2] {t2['source']}")
    print(f"         {t2['count']} matching alert(s)")
    if not t2["count"]:
        print("         none on record")
    for rec in t2["records"]:
        print(f"\n  {rec['alert_label'][:74]}")
        print(f"    date {rec['alert_date'] or rec['alert_year']}")
        if rec["products"]:
            print(f"    products {rec['products'][:64]}")
        if rec["manufacturers"]:
            print(f"    makers   {rec['manufacturers'][:64]}")
        print(f"    {rec['news_url']}")

    print(f"\n  An NSQ finding is batch-specific: one batch failed testing on one")
    print(f"  date for the stated reason. It is not a statement about the company.")
    print(f"  Absence of a record is NOT evidence of quality - only sampled batches")
    print(f"  are tested.")


def show_report(salt: str, strength: str = "") -> None:
    show_price(salt, strength)
    show_quality(salt)
    for row in find_alternatives(salt, strength)["scheduled_options"][:1]:
        maker = (row.get("manufacturer") or "").split("/")[0].strip()
        if maker and len(maker) > 4:
            show_quality(maker)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="medlens")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("price", help="ceiling and floor for a composition")
    p1.add_argument("salt")
    p1.add_argument("strength", nargs="?", default="")

    p2 = sub.add_parser("check", help="regulatory quality records")
    p2.add_argument("name")

    p3 = sub.add_parser("report", help="price + quality + manufacturer records")
    p3.add_argument("salt")
    p3.add_argument("strength", nargs="?", default="")

    p4 = sub.add_parser("ask", help="run the Strands agent (needs model credentials)")
    p4.add_argument("question")

    p5 = sub.add_parser("json", help="raw query output, for piping")
    p5.add_argument("salt")
    p5.add_argument("strength", nargs="?", default="")

    args = ap.parse_args(argv)

    if args.cmd == "price":
        show_price(args.salt, args.strength)
    elif args.cmd == "check":
        show_quality(args.name)
    elif args.cmd == "report":
        show_report(args.salt, args.strength)
    elif args.cmd == "json":
        print(json.dumps(get_price(args.salt, args.strength), indent=2))
    elif args.cmd == "ask":
        try:
            from medlens.agent import ask
        except Exception as exc:
            print(f"could not load the agent: {exc}", file=sys.stderr)
            return 2
        try:
            print(ask(args.question))
        except Exception as exc:
            print(f"\nagent run failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            print("Bedrock needs AWS credentials. Use the deterministic commands "
                  "(price/check/report) instead - they need no model.",
                  file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
