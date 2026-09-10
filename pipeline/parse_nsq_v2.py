"""Parse the post-June-2025 CDSCO NSQ alert format.

The layout changed at July 2025 and the original parser returns zero records.

The insight that unlocks it: every record is a single row of ten tall,
NON-OVERLAPPING cell rectangles. For record 1 of the May-2026 alert the cells
all span top=74.2 to bottom=252.1, with x-ranges:

    72.4-114.2   114.9-234.8   235.2-288.8   289.6-365.9   366.7-415.6
    416.3-508.5  509.3-588.5   589.2-649.0   649.7-709.5   710.2-770.0

So the row grouping is given directly by the drawing, not inferred.

Why the obvious approaches fail:

  * `find_tables()` returns ~19 tables per page because each cell carries its own
    border, fragmenting the table into cell-sized tables. Page 1 reports 18
    columns and page 2 reports 16, and the indices do not align.
  * pdfplumber cell tuples are (x0, top, x1, bottom) and carry NO text, so cells
    must be cropped to be read. Cropping cells taken from the *fragmented tables*
    duplicates text, because those bboxes overlap. Cropping the raw cell rects
    does not, because they tile the row exactly.
  * Banding records from the S.No anchor's own `top` cuts records in half - the
    S.No is vertically centred in a 178pt-tall row.

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
# Separate output on purpose: different layout, tracked independently of the
# clean 2024-2025 dataset.
OUT = ROOT / "data" / "processed" / "nsq_records_recent.jsonl"

MMYYYY = re.compile(r"\b(\d{1,2})/(\d{4})\b")
MONYY = re.compile(r"\b([A-Za-z]{3,9})[-\s]?(\d{2}|\d{4})\b")

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

MIN_CELL_W = 20.0
MIN_CELL_H = 15.0
ROW_TOL = 3.0

# Column order used when the header row cannot be read.
DEFAULT_FIELDS = ["sno", "product_name", "batch_no", "mfg_date", "expiry_date",
                  "manufacturer", "nsq_reason", "reported_by", "lab",
                  "alert_period"]

HEADER_LABELS = [
    ("sno",          r"^s\.?n"),
    ("product_name", r"nameofproduct|^product"),
    ("batch_no",     r"batch"),
    ("mfg_date",     r"manufacturingdate"),
    ("expiry_date",  r"expiry"),
    ("manufacturer", r"manufacturedby"),
    ("nsq_reason",   r"nsqresult"),
    ("reported_by",  r"reportingsource|reportedby"),
    ("lab",          r"laboratory|^lab"),
    ("alert_period", r"alertmonth|monthofalert|month"),
]


def norm(value: str | None) -> str:
    """Collapse whitespace, rejoining letter-spaced runs ("T e l a n g a n a")."""
    if not value:
        return ""
    tokens = value.replace("\n", " ").split()
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


def cell_rects(page) -> list[dict]:
    """The drawn cell rectangles, excluding the thin border strokes."""
    out = []
    for r in page.rects:
        w, h = r["x1"] - r["x0"], r["bottom"] - r["top"]
        if w >= MIN_CELL_W and h >= MIN_CELL_H:
            out.append({"x0": r["x0"], "x1": r["x1"],
                        "top": r["top"], "bottom": r["bottom"]})
    return out


def group_rows(cells: list[dict]) -> list[list[dict]]:
    """Cells sharing the same vertical extent form one record row."""
    buckets: dict[tuple[int, int], list[dict]] = {}
    for c in cells:
        key = (round(c["top"] / ROW_TOL), round(c["bottom"] / ROW_TOL))
        buckets.setdefault(key, []).append(c)
    rows = [sorted(v, key=lambda c: c["x0"]) for _, v in sorted(buckets.items())]
    # drop fragments: a real record row has most of the ten columns
    return [r for r in rows if len(r) >= 5]


def row_text(page, row: list[dict]) -> list[str]:
    """Crop each cell in the row. Cells tile the row, so nothing overlaps."""
    texts = []
    for c in row:
        try:
            t = page.crop((c["x0"], c["top"], c["x1"], c["bottom"])).extract_text()
        except Exception:
            t = ""
        texts.append(norm(t))
    return texts


def header_fields(page, rows: list[list[dict]]) -> list[str] | None:
    """Read the page-1 header row and return the field order."""
    for row in rows[:4]:
        texts = row_text(page, row)
        mapping: dict[int, str] = {}
        for i, t in enumerate(texts):
            key = re.sub(r"\s+", "", t.lower())
            if not key:
                continue
            for field, pattern in HEADER_LABELS:
                if field not in mapping.values() and re.search(pattern, key):
                    mapping[i] = field
                    break
        if len(mapping) >= 5 and "product_name" in mapping.values():
            order = []
            for i in range(len(texts)):
                order.append(mapping.get(i, DEFAULT_FIELDS[i] if i < len(DEFAULT_FIELDS)
                                         else f"col{i}"))
            seen, out = set(), []
            for f in order:
                if f in seen:
                    f = f"{f}_dup"
                seen.add(f)
                out.append(f)
            return out
    return None


def parse_filename(path: Path) -> tuple[str, str, int | None, int | None]:
    """Two filename conventions are in play.

    fetch_nsq.py (2024-2025)  -> nsq_central_2024_04_title_xxx.pdf
    fetch_nsq_recent.py       -> nsq_2026_05_Drug-Alert-May-2026-CDSCO.pdf

    In the recent convention parts[1] is the year, not the series.
    """
    parts = path.stem.split("_")
    alert_type = parts[0] if parts[0] in ("nsq", "state", "spurious", "other") else "nsq"

    if len(parts) > 2 and re.fullmatch(r"20\d\d", parts[1]):
        # fetch_nsq_recent.py convention: the series is in the alert_type
        # prefix (state_2026_07_...), not a separate path segment.
        series = "state" if alert_type == "state" else "central"
        year, month = int(parts[1]), int(parts[2])
    else:
        series = parts[1] if len(parts) > 1 else "central"
        year = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else None
        month = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else None
    return alert_type, series, year, month


def parse_pdf(path: Path) -> list[dict]:
    alert_type, series, year, month = parse_filename(path)

    records, fields = [], None
    with pdfplumber.open(path) as pdf:
        for pageno, page in enumerate(pdf.pages, start=1):
            rows = group_rows(cell_rects(page))
            if not rows:
                continue
            if fields is None:
                fields = header_fields(page, rows)
            order = fields or DEFAULT_FIELDS

            for row in rows:
                texts = row_text(page, row)
                if len(texts) < 5:
                    continue
                rec = {}
                for i, t in enumerate(texts):
                    f = order[i] if i < len(order) else f"col{i}"
                    rec[f] = t
                sno = rec.get("sno", "").strip().rstrip(".")
                if not sno.isdigit():
                    continue          # header row or a stray fragment
                if not (rec.get("product_name") or rec.get("manufacturer")):
                    continue
                rec["mfg_ym"] = to_ym(rec.get("mfg_date", ""))
                rec["expiry_ym"] = to_ym(rec.get("expiry_date", ""))
                records.append({
                    "source_file": path.name,
                    "alert_type": alert_type,
                    "series": series,
                    "alert_year": year,
                    "alert_month": month,
                    "page": pageno,
                    "provenance": "mirror",
                    **rec,
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
                print(f"      {p.name[:52]:<52} {len(recs):>4} records")

    print(f"\n{total:,} records from {len(pdfs)} PDFs")
    if empty:
        print(f"{len(empty)} file(s) yielded nothing: {', '.join(empty[:4])}")
    print(f"-> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
