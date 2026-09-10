"""Parse CDSCO NSQ alert PDFs into structured records.

The PDFs are bordered tables, so we use pdfplumber's table detection rather
than bucketing words by x-position. An earlier word-bucketing attempt failed
because the header labels are centred while the data is left-aligned, which
shifted every column by one. Border-based extraction avoids that entirely.

Each record is one table row. Rows whose S.No cell is not a number are section
headings ("A. CDSCO/Central Laboratories") and are skipped.

Run:
    python pipeline/parse_nsq.py
    python pipeline/parse_nsq.py --verbose
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pdfplumber

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw" / "nsq"
OUT = ROOT / "data" / "processed" / "nsq_records.jsonl"

FIELDS = [
    "sno", "product_name", "batch_no", "mfg_date", "expiry_date",
    "manufacturer", "nsq_reason", "reported_by",
]

S_NO = re.compile(r"^\d{1,4}\.?$")
MMYYYY = re.compile(r"\b(\d{1,2})/(\d{4})\b")
MONYY = re.compile(r"\b([A-Za-z]{3})[-\s]?(\d{2}|\d{4})\b")

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def norm(value: str | None) -> str:
    """Collapse a PDF cell into a single line.

    Some source PDFs are letter-spaced, so a single word arrives as a run of
    one-character tokens ("T e l a n g a n a ."). Runs of consecutive
    single-character tokens are joined back together; normal words are left
    alone. Without this, manufacturer names come out unsearchable.
    """
    if not value:
        return ""
    tokens = value.replace("\n", " ").split()
    if not tokens:
        return ""

    out: list[str] = []
    run: list[str] = []
    for t in tokens:
        if len(t) == 1 and not t.isdigit():
            run.append(t)
        else:
            if run:
                out.append("".join(run))
                run = []
            out.append(t)
    if run:
        out.append("".join(run))

    return re.sub(r"\s+", " ", " ".join(out)).strip()


def match_column(label: str) -> str | None:
    """Map a header cell to a canonical field name.

    Header spellings vary: "S.No", "S. N.", "Product/Drug Name",
    "Manufacturing Date" vs "Manufactured By", "Reported by CDSCO Laboratory".
    Whitespace is stripped before matching because PDF column headers wrap
    mid-word ("Manufa cturing Date"), which otherwise defeats substring tests.
    """
    l = re.sub(r"\s+", "", label.lower())
    if re.match(r"^s\.?n", l):        # S.No / S. N. / sno
        return "sno"
    if "product" in l:
        return "product_name"
    if "batch" in l:
        return "batch_no"
    if "expir" in l:
        return "expiry_date"
    if "manufactured" in l:          # must precede the "manufactur" check
        return "manufacturer"
    if "manufactur" in l:
        return "mfg_date"
    if "nsq" in l:
        return "nsq_reason"
    if "reported" in l:
        return "reported_by"
    return None


def to_ym(raw: str) -> str | None:
    """Normalise a date cell to YYYY-MM. Handles '10/2023' and 'Feb-24'."""
    if not raw:
        return None
    m = MMYYYY.search(raw)
    if m:
        return f"{m.group(2)}-{int(m.group(1)):02d}"
    m = MONYY.search(raw)
    if m:
        mon = MONTHS.get(m.group(1).lower())
        if mon:
            yr = int(m.group(2))
            yr = yr + 2000 if yr < 100 else yr
            return f"{yr}-{mon:02d}"
    return None


def table_to_records(
    table, fallback_colmap: dict[str, int] | None = None
) -> tuple[list[dict], dict[str, int] | None]:
    """Extract records from one detected table.

    Only the first page of a document carries a header row; continuation pages
    are headerless, so the column mapping is carried across pages.
    """
    try:
        rows = table.extract()
    except Exception:
        return [], fallback_colmap
    if not rows:
        return [], fallback_colmap

    header_idx, colmap = None, None
    for i, row in enumerate(rows):
        mapping: dict[str, int] = {}
        for j, c in enumerate(norm(x) for x in row):
            name = match_column(c)
            if name and name not in mapping:
                mapping[name] = j
        if len(mapping) >= 5 and "product_name" in mapping:
            header_idx, colmap = i, mapping
            break

    if colmap is None:
        # headerless continuation page: reuse the document's mapping, or fall
        # back to the fixed column order used by every CDSCO NSQ table.
        if fallback_colmap:
            colmap, header_idx = fallback_colmap, -1
        elif rows and len(rows[0]) == len(FIELDS):
            colmap, header_idx = {f: i for i, f in enumerate(FIELDS)}, -1
        else:
            return [], fallback_colmap

    out = []
    for row in rows[header_idx + 1:]:
        cells = [norm(c) for c in row]

        def cell(name: str) -> str:
            j = colmap.get(name)
            return cells[j] if j is not None and j < len(cells) else ""

        if not S_NO.match(cell("sno")):
            continue  # section heading or stray row
        rec = {f: cell(f) for f in FIELDS}
        rec["sno"] = cell("sno").rstrip(".")
        rec["mfg_ym"] = to_ym(rec["mfg_date"])
        rec["expiry_ym"] = to_ym(rec["expiry_date"])
        if rec["product_name"] or rec["manufacturer"]:
            out.append(rec)
    return out, colmap


def parse_pdf(path: Path) -> tuple[list[dict], int]:
    parts = path.stem.split("_")
    alert_type, series = parts[0], parts[1]
    year, month = (int(parts[2]), int(parts[3])) if len(parts) > 3 else (None, None)

    records: list[dict] = []
    colmap: dict[str, int] | None = None
    with pdfplumber.open(path) as pdf:
        n_pages = len(pdf.pages)
        for pageno, page in enumerate(pdf.pages, start=1):
            for table in page.find_tables():
                recs, colmap = table_to_records(table, colmap)
                for rec in recs:
                    records.append({
                        "source_file": path.name,
                        "alert_type": alert_type,
                        "series": series,
                        "alert_year": year,
                        "alert_month": month,
                        "page": pageno,
                        **rec,
                    })
    return records, n_pages


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    pdfs = sorted(RAW_DIR.glob("*.pdf"))
    if args.limit:
        pdfs = pdfs[:args.limit]
    if not pdfs:
        print(f"no PDFs in {RAW_DIR} - run fetch_nsq.py first")
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    total, pages_total, empty = 0, 0, []

    with OUT.open("w", encoding="utf-8") as fh:
        for p in pdfs:
            try:
                recs, pages = parse_pdf(p)
            except Exception as exc:
                print(f"  !!  {p.name}: {type(exc).__name__}: {exc}")
                empty.append(p.name)
                continue
            pages_total += pages
            total += len(recs)
            if not recs:
                empty.append(p.name)
            for r in recs:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
            if args.verbose or not recs:
                print(f"      {p.name:<52} {pages:>3}p  {len(recs):>4} records")

    print(f"\n{total:,} records from {len(pdfs)} PDFs ({pages_total} pages)")
    if empty:
        print(f"{len(empty)} file(s) yielded nothing: {', '.join(empty[:5])}")
    print(f"-> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
