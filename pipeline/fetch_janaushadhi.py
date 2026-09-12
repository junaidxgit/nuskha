"""Build the Jan Aushadhi generic-price layer.

Jan Aushadhi (PMBJP) sells generics at government-set prices, typically a
fraction of branded equivalents. This is the "cheap compliant floor" half of the
price answer: NPPA gives the legal maximum, Jan Aushadhi gives the bottom.

Why this is a PDF and not an API: janaushadhi.gov.in is a client-rendered React
SPA. Its product API exists at https://janaushadhi.gov.in:8443/ and the guest
token endpoint works, but /api/v1/website/getAllProductForWeb returns HTTP 500
for every payload shape tried (pageSize/pageIndex and ~80 other combinations).
No predictable PDF path on the official host resolves either - every guess
returns the SPA fallback HTML. So the published "Product Portfolio List" PDF is
used, sourced from a mirror.

Table shape:

    Sr.No  Drug Code  Generic Name                          Unit Size  MRP(in Rs.)
    1      1          Aceclofenac 100mg and Paracetamol ...  10's       10.00

The Generic Name carries the composition and strength, which is what makes
composition-first matching possible.

PROVENANCE: mirror. Recorded per row, and the file is hashed.

Run:
    python pipeline/fetch_janaushadhi.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pdfplumber

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw" / "janaushadhi"
OUT = ROOT / "data" / "processed" / "janaushadhi_prices.jsonl"
MANIFEST = ROOT / "data" / "raw" / "janaushadhi_manifest.json"

SOURCES = [
    "https://www.gpvdspharma.com/wp-content/uploads/2025/04/"
    "Jan-Aushadhi-Drug-Code-List-2025.pdf",
]

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

# "10's" | "15 g" | "3 ml" | "1's" | "60 ml" | "5 gm"
UNIT = r"(?:\d+\s*'?s|\d+(?:\.\d+)?\s*(?:g|gm|ml|mg|l|kg|%|w/w|w/v))"
LINE = re.compile(
    rf"^\s*(?P<sr>\d+)\s+(?P<code>\d+)\s+(?P<name>.+?)\s+"
    rf"(?P<unit>{UNIT})\s+(?P<mrp>\d+(?:\.\d+)?)\s*$",
    re.I,
)


def get(url: str, timeout: int = 60) -> bytes | None:
    url = urllib.parse.quote(url, safe="/:?=&%#[]@!$'()*+,;~")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as r:
            return r.read() if r.status == 200 else None
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        return None


def download() -> Path | None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for url in SOURCES:
        blob = get(url)
        if blob and blob[:5] == b"%PDF-":
            out = RAW_DIR / "jan_aushadhi_product_portfolio.pdf"
            out.write_bytes(blob)
            MANIFEST.write_text(json.dumps([{
                "source_url": url,
                "local_path": str(out.relative_to(ROOT)).replace("\\", "/"),
                "bytes": len(blob),
                "sha256": hashlib.sha256(blob).hexdigest(),
                "provenance": "mirror",
            }], indent=2), encoding="utf-8")
            print(f"downloaded {len(blob):,} B from {url}")
            return out
        print(f"  ..  not a PDF: {url}")
    return None


def parse_lines(text: str) -> list[dict]:
    rows = []
    for line in text.splitlines():
        m = LINE.match(line)
        if not m:
            continue
        name = re.sub(r"\s+", " ", m.group("name")).strip(" .,-")
        if len(name) < 4 or not re.search(r"[A-Za-z]{3}", name):
            continue
        rows.append({
            "sr_no": int(m.group("sr")),
            "drug_code": int(m.group("code")),
            "generic_name": name,
            "unit_size": re.sub(r"\s+", " ", m.group("unit")).strip(),
            "mrp_inr": float(m.group("mrp")),
        })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reuse", action="store_true",
                    help="use the already-downloaded PDF")
    args = ap.parse_args()

    existing = RAW_DIR / "jan_aushadhi_product_portfolio.pdf"
    path = existing if (args.reuse and existing.exists()) else download()
    if not path:
        print("could not obtain the Jan Aushadhi product list")
        return 1

    rows: list[dict] = []
    with pdfplumber.open(path) as pdf:
        print(f"pages: {len(pdf.pages)}")
        for page in pdf.pages:
            rows.extend(parse_lines(page.extract_text() or ""))

    # the document restarts numbering per section; dedupe on drug code
    seen, uniq = set(), []
    for r in rows:
        if r["drug_code"] in seen:
            continue
        seen.add(r["drug_code"])
        uniq.append(r)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps({**r, "provenance": "mirror"}, ensure_ascii=False) + "\n")

    print(f"\n{len(rows):,} rows, {len(uniq):,} distinct drug codes")
    if rows:
        print(f"MRP range: Rs {min(r['mrp_inr'] for r in rows)}"
              f" - {max(r['mrp_inr'] for r in rows)}")
    print(f"-> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
