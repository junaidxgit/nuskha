"""Nuskha CLI.

Two modes:

  deterministic  - calls the query layer directly and formats the answer. No
                   model, no credentials, no network. This is what the demo
                   video should use, because it cannot fail on stage.
  agent          - runs the real Strands agent. Needs model credentials.

Usage:
    python -m nuskha.cli price atorvastatin 10mg
    python -m nuskha.cli check coldrif
    python -m nuskha.cli report atorvastatin 10mg
    python -m nuskha.cli ask "what should atorvastatin 10mg cost?"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from nuskha.queries import check_quality_record, find_alternatives, get_price

RULE = "-" * 76


def _silent(**kwargs) -> None:
    """A Strands callback handler that prints nothing.

    Strands installs a printing handler by default, which streams the answer to
    stdout. The CLI prints the returned string itself, so without this the answer
    appears twice.
    """
    return None


def _traced() -> object:
    """A callback handler that prints each tool dispatch as the loop runs.

    The tool trace is the visible evidence that Strands is really driving a loop
    rather than printing a canned string, so the demo wants it on screen. It
    emits to stderr so the answer on stdout stays clean and pipeable.

    Strands calls the handler with kwargs; the tool name arrives under
    `current_tool_use` on `tool_use_stream` events (verified against this
    Strands version, not guessed).
    """

    def handler(**kwargs) -> None:
        if kwargs.get("type") != "tool_use_stream":
            return
        current = kwargs.get("current_tool_use") or {}
        name = current.get("name")
        if not name:
            return
        # `input` is still a raw JSON string while the block is streaming; it only
        # becomes a dict afterwards. Accept both, and never raise from a callback -
        # an exception here aborts the whole agent run.
        raw = current.get("input")
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except (ValueError, TypeError):
                raw = {}
        if not isinstance(raw, dict):
            raw = {}
        args = ", ".join(f"{k}={v}" for k, v in raw.items() if v)
        print(f"  tool -> {name}({args})", file=sys.stderr)
    return handler


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
        if c.get("is_combination") or f.get("is_combination"):
            print("\n  No ratio: one of the matches is a combination product, so the")
            print("  two figures are not the same medicine.")
        else:
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
        if rec.get("source_url"):
            print(f"    doc    {rec['source_url']}")
        else:
            print(f"    file   {rec['source_file']}")

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


def check_bedrock(region: str = "") -> int:
    """Diagnose whether the real agent can run against Amazon Bedrock.

    Checks credentials, region, and model access in that order, because each
    failure has a different fix and a generic "access denied" tells you nothing.
    Never prints credential values - only whether they resolve.
    """
    import os

    print("\nBedrock readiness")
    print(RULE)
    ok = True

    try:
        import boto3
        from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError
    except ImportError:
        print("  boto3 is missing. Install it: pip install boto3")
        return 1

    # 1. credentials
    env_keys = [k for k in ("AWS_ACCESS_KEY_ID", "AWS_PROFILE",
                            "AWS_SHARED_CREDENTIALS_FILE") if os.environ.get(k)]
    cred_file = Path.home() / ".aws" / "credentials"
    # fall back to the region Strands itself defaults to, so the diagnostic can
    # reach the model-access check instead of dying on NoRegionError
    sess = boto3.Session(region_name=region or os.environ.get("AWS_REGION")
                         or os.environ.get("AWS_DEFAULT_REGION") or "us-west-2")
    try:
        creds = sess.get_credentials()
        frozen = creds.get_frozen_credentials() if creds else None
    except Exception as exc:
        frozen = None
        print(f"  credentials  ERROR: {exc}")
        ok = False

    if frozen and frozen.access_key:
        src = sess.get_credentials().method if hasattr(sess.get_credentials(), "method") else "?"
        print(f"  credentials  found (source: {src})")
        if env_keys:
            print(f"               env vars set: {', '.join(env_keys)}")
    else:
        print("  credentials  NOT FOUND")
        print(f"               looked in env vars and {cred_file}")
        print("               fix: run `aws configure`, or set AWS_ACCESS_KEY_ID /")
        print("                    AWS_SECRET_ACCESS_KEY, or write ~/.aws/credentials")
        ok = False

    # 2. region
    resolved = sess.region_name or "us-west-2 (Strands default)"
    print(f"  region       {resolved}")

    # 3. model access
    model_id = "global.anthropic.claude-sonnet-4-6"
    try:
        client = sess.client("bedrock")
        resp = client.list_foundation_models(byOutputModality="TEXT")
        ids = [m["modelId"] for m in resp.get("modelSummaries", [])]
        anthropic = [i for i in ids if "anthropic" in i]
        print(f"  model access {len(ids)} text models visible, "
              f"{len(anthropic)} Anthropic")
        if anthropic:
            print(f"               e.g. {anthropic[0]}")
        print(f"  target       {model_id}")
        if not anthropic:
            print("               no Anthropic models visible - request access in the")
            print("               Bedrock console: Model access -> Claude models")
            ok = False
    except NoCredentialsError:
        print("  model access skipped (no credentials)")
        ok = False
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "?")
        print(f"  model access DENIED ({code})")
        print("               fix: Bedrock console -> Model access -> request Claude access")
        ok = False
    except BotoCoreError as exc:
        print(f"  model access ERROR: {type(exc).__name__}: {exc}")
        ok = False

    print()
    if ok:
        print("  Ready. Run the real agent:")
        print('    python -m nuskha.cli ask "what should atorvastatin 10mg cost?"')
    else:
        print("  Not ready. The deterministic commands still work and need no AWS:")
        print("    python -m nuskha.cli price atorvastatin 10mg")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="nuskha")
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
    p4.add_argument(
        "--offline", action="store_true",
        help="run the real agent loop with a scripted model instead of Bedrock, "
             "so it works with no AWS credentials. For demos and CI.",
    )
    p4.add_argument(
        "--trace", action="store_true",
        help="print each tool the agent dispatches (to stderr) as the loop runs.",
    )

    p5 = sub.add_parser("json", help="raw query output, for piping")
    p5.add_argument("salt")
    p5.add_argument("strength", nargs="?", default="")

    p6 = sub.add_parser("check-bedrock", help="diagnose AWS/Bedrock readiness")
    p6.add_argument("--region", default="")

    args = ap.parse_args(argv)

    if args.cmd == "price":
        show_price(args.salt, args.strength)
    elif args.cmd == "check":
        show_quality(args.name)
    elif args.cmd == "report":
        show_report(args.salt, args.strength)
    elif args.cmd == "json":
        print(json.dumps(get_price(args.salt, args.strength), indent=2))
    elif args.cmd == "check-bedrock":
        return check_bedrock(args.region)
    elif args.cmd == "ask":
        model = None
        if args.offline:
            # The genuine Strands event loop, driven by a scripted policy rather
            # than an LLM. Real tool dispatch, real results fed back. Lets the
            # demo and CI reproduce the agent without AWS credentials.
            # verbose=False: the CLI prints the returned answer itself, and the
            # callback handler would otherwise print the same text twice.
            from nuskha.mock_model import ScriptedModel
            model = ScriptedModel(verbose=False)
        try:
            from nuskha.agent import ask
        except Exception as exc:
            print(f"could not load the agent: {exc}", file=sys.stderr)
            return 2
        # Pass no model for the real (Bedrock) path and no handler at all, so the
        # answer comes back through the return value only. Strands' *default*
        # callback handler streams to stdout, which would print the answer a
        # second time when the CLI also prints the return value. An explicit
        # no-op handler keeps stdout owned by this function.
        try:
            answer = ask(args.question, model=model,
                         callback_handler=_traced() if args.trace else _silent)
        except Exception as exc:
            print(f"\nagent run failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            print("Bedrock needs AWS credentials. Re-run with --offline to drive the "
                  "same agent loop with a scripted model, or use the deterministic "
                  "commands (price/check/report), which need no model.",
                  file=sys.stderr)
            return 1
        print(answer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
