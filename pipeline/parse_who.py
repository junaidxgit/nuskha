"""Extract structured fields from WHO Medical Product Alert text.

Without this the agent can only say "this document mentions your drug" - it
cannot say WHICH product matched, or name the manufacturer. That distinction is
the difference between a citation and a lookup.

WHO alerts follow a stable shape:

    <date>
    ...
    Medical Product Alert N°5/2025
    Substandard (contaminated) oral liquid medicines identified in the WHO ...
    Alert Summary
    ... manufactured by Sresan Pharmaceutical, Rednex Pharmaceuticals, and ...

Extraction is pattern-based and deliberately conservative: we would rather
return nothing than invent a manufacturer name. Every extracted value also keeps
its surrounding sentence so the UI can show the claim in context.

Run:
    python pipeline/parse_who.py --verbose
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "processed" / "who_alerts.jsonl"
OUT = ROOT / "data" / "processed" / "who_alerts_structured.jsonl"

MONTHS = ("January February March April May June July August September "
          "October November December")

DATE_LINE = re.compile(rf"\b(\d{{1,2}}\s+(?:{MONTHS.replace(' ', '|')})\s+20\d\d)\b")
ALERT_ID = re.compile(r"Medical Product Alert\s*N[°ºo]?\s*(\d+)\s*/\s*(20\d\d)", re.I)

# Words that appear in caps in titles but are not product names
STOP_CAPS = {
    "WHO", "ALERT", "MEDICAL", "PRODUCT", "PRODUCTS", "SUBSTANDARD", "FALSIFIED",
    "AND", "THE", "IN", "ALL", "REGIONS", "REGION", "SUMMARY", "UPDATE", "NOTICE",
    "INFORMATION", "GLOBAL", "SURVEILLANCE", "MONITORING", "SYSTEM", "REF",
    "FOR", "OF", "TO", "WITH", "IVD", "USERS", "ORAL", "LIQUID", "MEDICINES",
    "SOLUTIONS", "INJECTION", "IDENTIFIED", "BATCHES", "SPECIFIC", "ARE", "NOT",
    "THIS", "REFERS", "MULTIPLE", "BATCH", "CONTAMINATED", "DEG", "EG",
}

# "manufactured by X", "manufacturer: X", "manufactured by X and Y"
MANUFACTURER_PATTERNS = [
    re.compile(r"manufactur\w*\s+by\s+([^.;\n]{3,180})", re.I),
    re.compile(r"manufacturer[s]?\s*[:\-]\s*([^.;\n]{3,180})", re.I),
    re.compile(r"produced\s+by\s+([^.;\n]{3,180})", re.I),
]
SPLIT_NAMES = re.compile(r"\s*(?:,|;|\band\b|\b&\b)\s*", re.I)

PRODUCT_PATTERNS = [
    re.compile(r"brand\s+names?\s+([^.;\n]{3,200})", re.I),
    re.compile(r"identified\s+to\s+be\s+(?:specific\s+batches\s+of\s+)?([^.;\n]{3,200})", re.I),
    re.compile(r"marketed\s+as\s+([^.;\n]{3,200})", re.I),
    re.compile(r"affected\s+products?\s+(?:are|were)\s+([^.;\n]{3,200})", re.I),
]

BATCH_PATTERNS = [
    re.compile(r"batch\s+(?:number|no\.?|nos\.?)\s*[:\-]?\s*([A-Za-z0-9][A-Za-z0-9/\- ]{1,40})", re.I),
    re.compile(r"\bB\.?\s*No\.?\s*[:\-]?\s*([A-Za-z0-9][A-Za-z0-9/\- ]{1,40})"),
]


def clean_name(value: str) -> str:
    v = re.sub(r"\s+", " ", value).strip(" .,;:")
    v = re.sub(r"^(?:the|a|an)\s+", "", v, flags=re.I)
    # drop clause tails that ride along after a comma
    v = re.split(r"\s+(?:manufactured|marketed|produced|supplied|distributed|"
                 r"reported|identified|have|has|were|was|which|that)\b",
                 v, flags=re.I)[0]
    v = re.sub(r"\s+(?:and|or|of|for|in|to)$", "", v, flags=re.I)
    return v.strip(" .,;:")


def plausible(name: str) -> bool:
    """Reject fragments that are clearly not a name."""
    if not (3 <= len(name) <= 90):
        return False
    if not re.search(r"[A-Za-z]{3}", name):
        return False
    # must look like a proper noun somewhere
    if not re.search(r"\b[A-Z]", name):
        return False
    low = name.lower()
    if low.startswith(("specific", "these", "those", "which", "that", "it ",
                       "manufactur", "market", "produc", "batch", "batch ")):
        return False
    return True


def split_names(blob: str) -> list[str]:
    out = []
    for part in SPLIT_NAMES.split(blob):
        n = clean_name(part)
        # drop trailing clause fragments
        n = re.split(r"\s+(?:have|has|were|was|which|that|and\s+the)\s+", n, flags=re.I)[0]
        n = clean_name(n)
        if plausible(n):
            out.append(n)
    return out


def extract_caps_products(title: str) -> list[str]:
    """WHO titles capitalise brand names: 'Substandard ACCUPAQUE (Iohexol)...'"""
    found = []
    for m in re.finditer(r"\b[A-Z][A-Z0-9\-]{3,}\b", title):
        tok = m.group(0)
        if tok in STOP_CAPS or tok in {"ALERT"}:
            continue
        found.append(tok)
    return found


def extract(text: str) -> dict:
    body = re.sub(r"[ \t]+", " ", text)
    # the naming sentence often sits well past the summary, so search widely
    head = body[:4000]

    date_m = DATE_LINE.search(body)
    id_m = ALERT_ID.search(body)

    # title = the line(s) after the alert-number line, before "Alert Summary"
    title = ""
    if id_m:
        tail = body[id_m.end():id_m.end() + 400]
        title = re.split(r"Alert\s+Summary|Summary", tail, flags=re.I)[0]
        title = re.sub(r"\s+", " ", title).strip(" -\n")

    products: list[str] = []
    for pat in PRODUCT_PATTERNS:
        for m in pat.finditer(head):
            products.extend(split_names(m.group(1)))
    products.extend(extract_caps_products(title))
    products = list(dict.fromkeys(p for p in products if plausible(p)))

    manufacturers: list[str] = []
    for pat in MANUFACTURER_PATTERNS:
        for m in pat.finditer(body):
            manufacturers.extend(split_names(m.group(1)))
    manufacturers = list(dict.fromkeys(
        m for m in manufacturers if plausible(m) and len(m) > 3))

    batches: list[str] = []
    for pat in BATCH_PATTERNS:
        for m in pat.finditer(body):
            b = clean_name(m.group(1))
            if 2 <= len(b) <= 40:
                batches.append(b)
    batches = list(dict.fromkeys(batches))

    return {
        "alert_date": date_m.group(1) if date_m else None,
        "title": title,
        "products": products,
        "manufacturers": manufacturers,
        "batch_numbers": batches,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    rows = [json.loads(l) for l in SRC.open(encoding="utf-8")]
    OUT.parent.mkdir(parents=True, exist_ok=True)

    n_prod = n_man = 0
    with OUT.open("w", encoding="utf-8") as fh:
        for r in rows:
            ex = extract(r.get("text", ""))
            rec = {
                "alert_label": r["alert_label"],
                "alert_number": r["alert_number"],
                "alert_year": r["alert_year"],
                "news_url": r["news_url"],
                "pdf_url": r.get("pdf_url"),
                "local_path": r["local_path"],
                "mentions_india": r["mentions_india"],
                # keep the full text so the index can still be searched on
                # anything the pattern extraction missed
                "text": r.get("text", ""),
                **ex,
            }
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            if ex["products"]:
                n_prod += 1
            if ex["manufacturers"]:
                n_man += 1
            if args.verbose:
                print(f"  {r['alert_label'][:60]}")
                print(f"     date    : {ex['alert_date']}")
                print(f"     products: {', '.join(ex['products'][:5]) or '-'}")
                print(f"     makers  : {', '.join(ex['manufacturers'][:3]) or '-'}")

    print(f"\n{len(rows)} alerts processed")
    print(f"  {n_prod} with product names extracted")
    print(f"  {n_man} with manufacturer names extracted")
    print(f"-> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
