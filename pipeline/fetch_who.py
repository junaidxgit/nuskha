"""Download WHO Medical Product Alerts and extract their text.

WHO publishes alerts for substandard and falsified medical products. These are
Tier 2 sources in our policy (docs/source-policy.md): institutional and citable,
but shown separately from Tier 1 regulatory records.

They matter because they cover a data class CDSCO's NSQ list does not: recalls,
production halts and licence suspensions. The Chhindwara cough syrup deaths
(Alert N5/2025) were an enforcement action, not a laboratory failure - an
NSQ-only product would have shown the user nothing.

How the site works (reverse-engineered 2026-09-10):

  1. Index  : /teams/regulation-prequalification/incidents-and-SF/
              full-list-of-who-medical-product-alerts
              server-rendered; each alert is an <a class="link-container"
              aria-label="Medical Product Alert N°5/2025: ..."> pointing at a
              /news/item/... page.
  2. News   : that page embeds the real PDF on cdn.who.int. Pages can link
              several alerts' PDFs, so pick the one whose filename matches the
              alert number parsed from the label.

Run:
    python pipeline/fetch_who.py --since 2024
    python pipeline/fetch_who.py --india-only
"""

from __future__ import annotations

import argparse
import hashlib
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
RAW_DIR = ROOT / "data" / "raw" / "who"
OUT = ROOT / "data" / "processed" / "who_alerts.jsonl"

INDEX_URL = (
    "https://www.who.int/teams/regulation-prequalification/incidents-and-SF/"
    "full-list-of-who-medical-product-alerts"
)
ORIGIN = "https://www.who.int"

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

ANCHOR = re.compile(
    r"<a\s+href=\"(?P<href>[^\"]+)\"[^>]*class=\"link-container\""
    r"[^>]*aria-label=\"(?P<label>[^\"]*)\"",
    re.I | re.S,
)
PDF_ON_PAGE = re.compile(r"https://cdn\.who\.int[^\"' <>\\]+\.pdf[^\"' <>\\]*")
# "Medical Product Alert N°5/2025" / "N 5/2025"
ALERT_ID = re.compile(r"N[°ºo]?\s*(\d+)\s*/\s*(\d{4})", re.I)


def get(url: str, timeout: int = 45) -> bytes | None:
    url = urllib.parse.quote(url, safe="/:?=&%#[]@!$'()*+,;~")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as r:
            return r.read() if r.status == 200 else None
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        return None


def slugify(text: str, limit: int = 48) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:limit].strip("-")


def parse_index(src: str) -> list[dict]:
    entries, seen = [], set()
    for m in ANCHOR.finditer(src):
        href = html.unescape(m.group("href")).strip()
        label = re.sub(r"\s+", " ", html.unescape(m.group("label"))).strip()
        url = href if href.startswith("http") else ORIGIN + href
        # the index lists some entries twice (relative + absolute href)
        if url in seen or not label:
            continue
        seen.add(url)

        am = ALERT_ID.search(label)
        number = int(am.group(1)) if am else None
        year = int(am.group(2)) if am else None
        entries.append({
            "label": label,
            "news_url": url,
            "number": number,
            "year": year,
        })
    return entries


def pick_pdf(body: str, number: int | None, year: int | None) -> str | None:
    """Prefer the PDF whose filename matches this alert's number and year."""
    cands = []
    for p in PDF_ON_PAGE.findall(body):
        p = p.rstrip("\\")
        if p not in cands:
            cands.append(p)
    if not cands:
        return None
    if number is not None and year is not None:
        want = re.compile(rf"n\s*{number}[_\-\s]*{year}", re.I)
        for p in cands:
            if want.search(p.rsplit("/", 1)[-1]):
                return p
    return cands[0]


def pdf_text(blob: bytes) -> str:
    try:
        import io

        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(blob))
        return "\n".join((pg.extract_text() or "") for pg in reader.pages)
    except Exception:
        return ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", type=int, default=None,
                    help="only alerts from this year onward")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--india-only", action="store_true",
                    help="keep only alerts whose text mentions India")
    ap.add_argument("--sleep", type=float, default=0.5)
    args = ap.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)

    index_html = get(INDEX_URL)
    if not index_html:
        print("could not fetch the WHO alert index")
        return 1
    entries = parse_index(index_html.decode("utf-8", "ignore"))
    print(f"index lists {len(entries)} alerts")

    if args.since:
        entries = [e for e in entries if e["year"] and e["year"] >= args.since]
        print(f"{len(entries)} from {args.since} onward")
    if args.limit:
        entries = entries[:args.limit]

    manifest, out_rows, ok, fail, skipped = [], [], 0, 0, 0

    for e in entries:
        page = get(e["news_url"])
        time.sleep(args.sleep)
        if not page:
            fail += 1
            print(f"  XX  {e['label'][:66]} (news page failed)")
            manifest.append({**e, "status": "news_failed"})
            continue

        pdf_url = pick_pdf(page.decode("utf-8", "ignore"), e["number"], e["year"])
        blob = get(pdf_url) if pdf_url else None
        time.sleep(args.sleep)

        if not blob or blob[:5] != b"%PDF-":
            fail += 1
            print(f"  XX  {e['label'][:66]} (pdf failed)")
            manifest.append({**e, "status": "pdf_failed", "pdf_url": pdf_url})
            continue

        text = pdf_text(blob)
        mentions_india = bool(re.search(r"\bIndia\b", text, re.I))

        if args.india_only and not mentions_india:
            skipped += 1
            manifest.append({**e, "status": "skipped_not_india", "pdf_url": pdf_url})
            continue

        tag = f"N{e['number']}" if e["number"] else "Nx"
        name = f"who_{e['year'] or 'x'}_{tag}_{slugify(e['label'])}.pdf"
        path = RAW_DIR / name
        path.write_bytes(blob)
        ok += 1

        out_rows.append({
            "alert_label": e["label"],
            "alert_number": e["number"],
            "alert_year": e["year"],
            "news_url": e["news_url"],
            "pdf_url": pdf_url,
            "local_path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "sha256": hashlib.sha256(blob).hexdigest(),
            "bytes": len(blob),
            "mentions_india": mentions_india,
            "text": text,
        })
        manifest.append({**e, "status": "ok", "pdf_url": pdf_url,
                         "local_path": out_rows[-1]["local_path"],
                         "mentions_india": mentions_india})
        print(f"  OK  {e['year']} {tag:<5} india={'Y' if mentions_india else 'n'} "
              f"{len(blob):>8,} B  {e['label'][:56]}")

    (RAW_DIR / "_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")
    with OUT.open("w", encoding="utf-8") as fh:
        for r in out_rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"\n{ok} downloaded, {fail} failed, {skipped} skipped (not India)")
    print(f"-> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
