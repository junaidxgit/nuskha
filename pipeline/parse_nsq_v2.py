"""Parse the 2025-07+ CDSCO NSQ alert format.

The post-June-2025 PDFs changed layout. Their borders fragment each cell into
its own tiny table, so `find_tables()` returns ~19 tables per page and
column-index mapping breaks (page 1's header table has 18 columns, page 2's
data table has 16, and neither aligns).

What survives the fragmentation is the important part: **every cell keeps a
correct bounding box**. So instead of mapping columns by index, we:

  1. Collect every cell from every table on the page as (x0, x1, top, bottom, text)
  2. Cluster cells into visual lines by vertical overlap
  3. Derive column boundaries from the header row's cell positions
  4. Assign each cell to a column by its x-centre
  5. Start a new record wherever a cell lands in the S.No column

Run:
    python pipeline/parse_nsq_v2.py --verbose
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pdfplumber

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw" / "nsq_recent"
# Separate output on purpose: this parser handles the post-June-2025 layout and
# its quality is not yet good enough to merge into the main dataset.
OUT = ROOT / "data" / "processed" / "nsq_records_recent.jsonl"

S_NO = re.compile(r"^\d{1,4}\.?$")
MMYYYY = re.compile(r"\b(\d{1,2})/(\d{4})\b")
MONYY = re.compile(r"\b([A-Za-z]{3,9})[-\s]?(\d{2}|\d{4})\b")

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

FIELDS = ["sno", "product_name", "batch_no", "mfg_date", "expiry_date",
          "manufacturer", "nsq_reason", "reported_by"]

# Canonical column order, matched against header text (whitespace stripped)
HEADER_MATCHERS = [
    ("sno",          r"^s\.?n"),
    ("product_name", r"nameofproduct|^product"),
    ("batch_no",     r"batch"),
    ("mfg_date",     r"manufacturingdate|^manufactur"),
    ("expiry_date",  r"expiry"),
    ("manufacturer", r"manufacturedby"),
    ("nsq_reason",   r"nsqresult"),
    ("reported_by",  r"reporting|reported"),
]


def norm(value: str | None) -> str:
    if not value:
        return ""
    tokens = value.replace("\n", " ").split()
    out, run = [], []
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


def to_ym(raw: str) -> str | None:
    if not raw:
        return None
    m = MMYYYY.search(raw)
    if m:
        return f"{m.group(2)}-{int(m.group(1)):02d}"
    m = MONYY.search(raw)
    if m:
        mon = MONTHS.get(m.group(1)[:3].lower())
        if mon:
            yr = int(m.group(2))
            yr = yr + 2000 if yr < 100 else yr
            return f"{yr}-{mon:02d}"
    return None


def collect_cells(page) -> list[dict]:
    """Every non-empty cell on the page, with its bbox.

    pdfplumber cell tuples are (x0, top, x1, bottom) and carry NO text, so each
    cell has to be cropped and read. Dedup on bbox because the fragmented
    tables overlap each other heavily.
    """
    cells, seen = [], set()
    for table in page.find_tables():
        try:
            rows = table.rows
        except Exception:
            continue
        for row in rows:
            for c in row.cells:
                if not c or len(c) < 4:
                    continue
                x0, top, x1, bottom = c[0], c[1], c[2], c[3]
                if x1 - x0 < 2 or bottom - top < 2:
                    continue
                key = (round(x0, 1), round(top, 1), round(x1, 1), round(bottom, 1))
                if key in seen:
                    continue
                seen.add(key)
                try:
                    txt = norm(page.crop((x0, top, x1, bottom)).extract_text())
                except Exception:
                    continue
                if not txt:
                    continue
                cells.append({"x0": x0, "x1": x1, "top": top,
                              "bottom": bottom, "text": txt})
    return cells


def cluster_lines(cells: list[dict]) -> list[list[dict]]:
    """Group cells into visual lines by vertical overlap."""
    if not cells:
        return []
    cells = sorted(cells, key=lambda c: (c["top"], c["x0"]))
    lines: list[list[dict]] = []
    for c in cells:
        placed = False
        for line in lines:
            ref = line[0]
            overlap = min(ref["bottom"], c["bottom"]) - max(ref["top"], c["top"])
            height = min(ref["bottom"] - ref["top"], c["bottom"] - c["top"])
            if height > 0 and overlap / height > 0.5:
                line.append(c)
                placed = True
                break
        if not placed:
            lines.append([c])
    for line in lines:
        line.sort(key=lambda c: c["x0"])
    return lines


def header_columns(lines: list[list[dict]]) -> list[tuple[str, float, float]] | None:
    """Find the header line and return [(field, x0, x1)] for each column."""
    for line in lines[:12]:
        found: dict[str, tuple[float, float]] = {}
        for c in line:
            key = re.sub(r"\s+", "", c["text"].lower())
            for field, pattern in HEADER_MATCHERS:
                if field not in found and re.search(pattern, key):
                    found[field] = (c["x0"], c["x1"])
        if len(found) >= 5 and "product_name" in found:
            return [(f, *found[f]) for f, _ in HEADER_MATCHERS if f in found]
    return None


def build_bounds(columns: list[tuple[str, float, float]]) -> list[tuple[str, float, float]]:
    """Turn column start positions into half-open x ranges."""
    out = []
    for i, (field, x0, x1) in enumerate(columns):
        lo = 0.0 if i == 0 else (columns[i - 1][1] + x0) / 2
        hi = 10_000.0 if i == len(columns) - 1 else (x0 + columns[i + 1][1]) / 2
        out.append((field, lo, hi))
    return out


def field_for(x0: float, x1: float, bounds) -> str | None:
    centre = (x0 + x1) / 2
    for field, lo, hi in bounds:
        if lo <= centre < hi:
            return field
    return None


def parse_page(page, bounds) -> tuple[list[dict], list | None]:
    cells = collect_cells(page)
    if not cells:
        return [], None
    lines = cluster_lines(cells)

    if bounds is None:
        hdr = header_columns(lines)
        if hdr:
            bounds = build_bounds(hdr)

    if bounds is None:
        return [], None

    records, current = [], None
    for line in lines:
        first = line[0]
        field = field_for(first["x0"], first["x1"], bounds)
        is_new = field == "sno" and S_NO.match(first["text"])
        if is_new:
            if current:
                records.append(current)
            current = {f: [] for f in FIELDS}
            current["sno"] = [first["text"]]
            line = line[1:]
        if current is None:
            continue
        for c in line:
            f = field_for(c["x0"], c["x1"], bounds)
            if f:
                current[f].append(c["text"])

    if current:
        records.append(current)

    out = []
    for r in records:
        rec = {f: re.sub(r"\s+", " ", " ".join(r[f])).strip() for f in FIELDS}
        if not rec["product_name"] and not rec["manufacturer"]:
            continue
        rec["sno"] = rec["sno"].rstrip(".")
        rec["mfg_ym"] = to_ym(rec["mfg_date"])
        rec["expiry_ym"] = to_ym(rec["expiry_date"])
        out.append(rec)
    return out, bounds


def parse_pdf(path: Path) -> list[dict]:
    stem = path.stem
    parts = stem.split("_")
    alert_type = parts[0] if parts[0] in ("nsq", "spurious", "other") else "nsq"
    series = parts[1] if len(parts) > 1 else "central"
    year = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else None
    month = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else None

    records, bounds = [], None
    with pdfplumber.open(path) as pdf:
        for pageno, page in enumerate(pdf.pages, start=1):
            recs, bounds = parse_page(page, bounds)
            for r in recs:
                records.append({
                    "source_file": path.name,
                    "alert_type": alert_type,
                    "series": series,
                    "alert_year": year,
                    "alert_month": month,
                    "page": pageno,
                    "provenance": "mirror",
                    **r,
                })
    return records


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    pdfs = sorted(RAW_DIR.glob("*.pdf"))
    if not pdfs:
        print(f"no PDFs in {RAW_DIR}")
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    total, empty = 0, []
    with OUT.open("w", encoding="utf-8") as fh:
        for p in pdfs:
            try:
                recs = parse_pdf(p)
            except Exception as exc:
                print(f"  !!  {p.name}: {type(exc).__name__}: {exc}")
                empty.append(p.name)
                continue
            total += len(recs)
            if not recs:
                empty.append(p.name)
            for r in recs:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
            if args.verbose or not recs:
                print(f"      {p.name:<46} {len(recs):>4} records")

    print(f"\n{total:,} records from {len(pdfs)} PDFs")
    if empty:
        print(f"{len(empty)} file(s) yielded nothing")
    print(f"-> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
