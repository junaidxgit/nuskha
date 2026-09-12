"""Build the NPPA ceiling-price layer.

NPPA (National Pharmaceutical Pricing Authority) fixes the maximum retail price
of scheduled formulations under the Drugs (Prices Control) Order, 2013. For a
scheduled drug this ceiling is legally binding - charging more is illegal. It is
the "what should this cost" half of the product.

Where the data comes from: NPPA publishes each fixation as an "S.O. <n> (E)"
notification PDF. Those are awkward to parse, but the trade press republishes
the full notification table as HTML inside their posts, and their WordPress REST
API exposes the post bodies. The table carries exactly the columns needed:

    Sl. No. | Name of the Formulation / Brand Name | Strength | Unit |
    Manufacturer & Marketing Company | Retail Price (Rs.)

The "Strength" column holds the composition ("Each Film Coated Tablet Contains:
Atorvastatin Calcium IP eq. to Atorvastatin 10 mg ..."), which is what makes
composition-first matching possible.

Prices are exclusive of GST - say so wherever they are displayed.

Run:
    python pipeline/fetch_nppa.py
    python pipeline/fetch_nppa.py --pages 3
"""

from __future__ import annotations

import argparse
import html
import json
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "processed" / "nppa_ceiling_prices.jsonl"
MANIFEST = ROOT / "data" / "raw" / "nppa_manifest.json"

API = ("https://thehealthmaster.com/wp-json/wp/v2/posts"
       "?search={q}&per_page=100&page={page}&_fields=date,link,title,content")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
CELL = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S | re.I)
TAG = re.compile(r"<[^>]+>")

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}

# A price cell looks like "18.46" or "1,234.56"
PRICE = re.compile(r"^\d[\d,]*\.?\d*$")


def get(url: str, timeout: int = 60) -> bytes | None:
    url = urllib.parse.quote(url, safe="/:?=&%#[]@!$'()*+,;~")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as r:
            return r.read() if r.status == 200 else None
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        return None


def text_of(fragment: str) -> str:
    s = html.unescape(TAG.sub(" ", fragment))
    return re.sub(r"\s+", " ", s).strip()


def parse_price(value: str) -> float | None:
    v = value.replace(",", "").replace("Rs.", "").strip()
    m = re.search(r"\d+(?:\.\d+)?", v)
    return float(m.group(0)) if m else None


def post_month(title: str) -> tuple[int | None, int | None]:
    m = re.search(r"\b(" + "|".join(MONTHS) + r")\s+(20\d\d)\b", title, re.I)
    if m:
        return int(m.group(2)), MONTHS[m.group(1).lower()]
    return None, None


def header_map(cells: list[str]) -> dict[str, int]:
    """Map field -> column index from the header row.

    NPPA notifications do not use one fixed schema. Observed headers:
      "Sl. No. | Name of the Formulation / Brand Name | Strength | Unit | ..."
      "Sl. No. | Medicines | Dosage form and strength | Unit | ..."
      "Sl. No. | Medicine | Strength | Unit | ..."
    so columns are resolved by label rather than by position.
    """
    m: dict[str, int] = {}
    for i, c in enumerate(cells):
        l = c.lower()
        if re.search(r"\bsl\.?\s*no", l):
            m.setdefault("sl_no", i)
        elif "formulation" in l or "medicine" in l:
            m.setdefault("formulation", i)
        elif "strength" in l or "dosage" in l or "composition" in l:
            m.setdefault("composition", i)
        elif "unit" in l:
            m.setdefault("unit", i)
        elif "manufactur" in l or "marketing" in l or "company" in l:
            m.setdefault("manufacturer", i)
        elif "price" in l:
            m.setdefault("price", i)
    return m


def extract_rows(content: str) -> list[dict]:
    """Pull price rows out of a notification table in a post body."""
    out = []
    for table_html in re.findall(r"<table.*?</table>", content, re.S | re.I):
        rows = ROW.findall(table_html)
        if len(rows) < 2:
            continue
        hdr = [text_of(c) for c in CELL.findall(rows[0])]
        cols = header_map(hdr)
        if "formulation" not in cols:
            continue
        if "price" not in cols and "composition" not in cols:
            continue

        for r in rows[1:]:
            cells = [text_of(c) for c in CELL.findall(r)]
            if len(cells) < 3:
                continue
            if cells[0].startswith("("):
                continue        # the "(1) (2) (3)" column-number row

            def cell(name: str, default: str = "") -> str:
                i = cols.get(name)
                return cells[i] if i is not None and i < len(cells) else default

            price = parse_price(cell("price"))
            if price is None:
                for c in reversed(cells):
                    if PRICE.match(c.replace("Rs.", "").strip()):
                        price = parse_price(c)
                        break
            if price is None:
                continue

            formulation = cell("formulation")
            if not formulation or not re.search(r"[A-Za-z]{3}", formulation):
                continue
            out.append({
                "sl_no": cell("sl_no"),
                "formulation": formulation,
                "composition": cell("composition"),
                "unit": cell("unit"),
                "manufacturer": cell("manufacturer"),
                "retail_price_inr": price,
            })
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=3,
                    help="WP API pages to walk (100 posts each)")
    ap.add_argument("--sleep", type=float, default=0.6)
    args = ap.parse_args()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    seen_links: set[str] = set()
    all_rows: list[dict] = []
    manifest: list[dict] = []

    for page in range(1, args.pages + 1):
        blob = get(API.format(q="NPPA", page=page))
        time.sleep(args.sleep)
        if not blob:
            print(f"  page {page}: fetch failed")
            break
        try:
            posts = json.loads(blob)
        except Exception:
            break
        if not isinstance(posts, list) or not posts:
            break

        added = 0
        for p in posts:
            link = p.get("link", "")
            if link in seen_links:
                continue
            seen_links.add(link)
            title = text_of(p.get("title", {}).get("rendered", ""))
            content = p.get("content", {}).get("rendered", "")
            rows = extract_rows(content)
            if not rows:
                continue
            year, month = post_month(title)
            notice = ""
            nm = re.search(r"S\.?O\.?\s*[\d\s()Ee.-]{4,40}", text_of(content))
            if nm:
                notice = re.sub(r"\s+", " ", nm.group(0)).strip()
            for r in rows:
                all_rows.append({
                    "source_post": link,
                    "source_title": title,
                    "post_date": p.get("date", "")[:10],
                    "notice_year": year,
                    "notice_month": month,
                    "notice_ref": notice,
                    "provenance": "mirror",
                    **r,
                })
                added += 1
            manifest.append({"link": link, "title": title, "rows": len(rows),
                             "year": year, "month": month})
        print(f"  page {page}: {len(posts)} posts, {added} price rows")
        if len(posts) < 100:
            break

    with OUT.open("w", encoding="utf-8") as fh:
        for r in all_rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    notices = {(r["notice_year"], r["notice_month"]) for r in all_rows}
    print(f"\n{len(all_rows):,} ceiling-price rows from {len(manifest)} notifications")
    print(f"{len(notices)} distinct notice months")
    print(f"-> {OUT.relative_to(ROOT)}")
    print("NOTE: prices are exclusive of GST. Provenance is 'mirror'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
