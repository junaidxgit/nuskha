"""The offline agent path is load-bearing for the demo, so it gets a test.

Run:  python -m tests.test_agent_offline      (or)  python tests/test_agent_offline.py

Why these assertions and not others: the demo video depends on four things being
true at once, and each one failed at least once while building this.

  1. the real Strands loop runs with no AWS credentials (it raised
     NoCredentialsError before mock_model was wired into the CLI)
  2. both tools are actually dispatched, by name (the loop could silently
     skip a tool and still print a plausible answer)
  3. the answer is printed exactly once (Strands' default callback handler
     streams to stdout, so the CLI printing the return value duplicated it)
  4. --trace emits the tool names (the visible evidence judges look for)

No network, no credentials, no model. Deterministic.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable

FAILURES: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    mark = "PASS" if ok else "FAIL"
    print(f"  {mark}  {label}" + (f"   [{detail}]" if detail and not ok else ""))
    if not ok:
        FAILURES.append(label)


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [PY, "-m", "nuskha.cli", *args],
        cwd=ROOT, capture_output=True, text=True, timeout=300,
    )


def main() -> int:
    question = "what should atorvastatin 10mg cost, and is it any good?"

    print("offline agent loop")
    plain = run_cli("ask", question, "--offline")

    check("exits 0 with no AWS credentials", plain.returncode == 0,
          f"rc={plain.returncode} stderr={plain.stderr.strip()[:160]}")
    check("no credential error in stderr",
          "NoCredentialsError" not in plain.stderr, plain.stderr.strip()[:160])

    out = plain.stdout
    check("price ceiling present", "4.94" in out, out[:200])
    check("generic floor present", "0.88" in out, out[:200])
    check("ratio present", "5.6x" in out, out[:200])
    check("batch record present", "AV26072" in out, out[:300])
    check("provenance caveat preserved",
          "batch-specific" in out and "prescriber" in out, out[-300:])

    # The duplicate bug: the answer body must appear once, not twice.
    check("answer printed exactly once",
          out.count("legal maximum") == 1,
          f"count={out.count('legal maximum')}")

    print("trace")
    traced = run_cli("ask", question, "--offline", "--trace")
    check("traced run exits 0", traced.returncode == 0,
          f"rc={traced.returncode}")
    check("trace names get_price", "get_price" in traced.stderr, traced.stderr[:200])
    check("trace names check_quality_record",
          "check_quality_record" in traced.stderr, traced.stderr[:200])
    check("trace shows parsed args", "atorvastatin" in traced.stderr,
          traced.stderr[:200])
    check("stdout stays clean under --trace",
          "tool ->" not in traced.stdout, traced.stdout[:200])

    print("second demo case")
    cold = run_cli("ask", "is coldrif safe?", "--offline", "--trace")
    check("coldrif exits 0", cold.returncode == 0, f"rc={cold.returncode}")
    check("coldrif gets the CDSCO batch", "SR-13" in cold.stdout, cold.stdout[:300])
    check("coldrif gets the WHO alert", "5/2025" in cold.stdout, cold.stdout[:400])

    print("deterministic commands still work")
    price = run_cli("price", "atorvastatin", "10mg")
    check("price exits 0", price.returncode == 0, f"rc={price.returncode}")
    check("price shows the ceiling", "4.94" in price.stdout, price.stdout[:200])

    print("bad input does not crash")
    bad = run_cli("ask", "zzzznotadrug", "--offline")
    check("unknown salt exits 0", bad.returncode == 0, f"rc={bad.returncode}")

    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILED:")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("all passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
