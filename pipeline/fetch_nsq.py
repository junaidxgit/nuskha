"""Download CDSCO NSQ (Not of Standard Quality) drug alerts.

How the CDSCO site actually works (reverse-engineered 2026-09-10):

  1. Index page   : /opencms/opencms/en/Notifications/nsq-drugs/
                    lists every alert as <a href='...download_file_division.jsp?num_id=<b64>'>
                    with a human title and publish date inside the anchor.
  2. Wrapper      : the num_id URL returns a tiny HTML page holding an <iframe>
  3. Real PDF     : the iframe src points at /opencms/resources/.../UploadAlertsFiles/<code>.pdf

The published filename is a cryptic code (e.g. stnsqapr25.pdf), NOT a readable
month name, so filename guessing does not work. Always go through the index.

Run:
    python pipeline/fetch_nsq.py                 # everything on the index page
    python pipeline/fetch_nsq.py --since 2024-01 # only from a given month
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
RAW_DIR = ROOT / "data" / "raw" / "nsq"
MANIFEST = ROOT / "data" / "raw" / "nsq_manifest.json"

ORIGIN = "https://cdsco.gov.in"
INDEX_URL = f"{ORIGIN}/opencms/opencms/en/Notifications/nsq-drugs/"

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

# TLS verification fails against this host from this machine (the local proxy
# presents a certificate for the wrong principal). The content is public
# regulatory data and every file is hashed into the manifest.
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12, "feburary": 2,  # typo that appears in CDSCO documents
}

ANCHOR = re.compile(
    r"<a[^>]+href=['\"](?P<href>[^'\"]*num_id=[^'\"]+)['\"][^>]*>(?P<body>.*?)</a>",
    re.S | re.I,
)
IFRAME = re.compile(r"<iframe[^>]+src=['\"](?P<src>[^'\"]+)['\"]", re.I)

# CDSCO titles are inconsistent. Observed forms include:
#   "NSQ ALERT FOR THE MONTH OF Feb-2025"
#   "Not Of Standard of Quality (NSQ) ALERT FOR THE MONTH OF April-2025"
#   "State NSQ Alert For The Month April-2025"
#   "List of Drugs, Medical Devices ... declared as Not of Standard Quality ..."
# so match "<month> <year>" anywhere rather than anchoring on a fixed phrase.
MONTH_NAME = (
    r"jan(?:uary)?|feb(?:ruary|rurary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|"
    r"dec(?:ember)?"
)
MONTH_YEAR = re.compile(
    rf"(?P<month>{MONTH_NAME})[\s\-.,]{{0,3}}(?P<year>20\d{{2}})", re.I
)
DATE = re.compile(r"(?P<y>\d{4})-(?P<m>[A-Za-z]{3})-(?P<d>\d{1,2})")


def get(url: str, timeout: int = 45) -> bytes | None:
    # some iframe srcs contain literal spaces
    url = urllib.parse.quote(url, safe="/:?=&%#[]@!$'()*+,;~")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as r:
            return r.read() if r.status == 200 else None
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        return None


def strip_tags(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def parse_index(src: str) -> list[dict]:
    """Pull every alert entry out of the index page."""
    entries = []
    for m in ANCHOR.finditer(src):
        href = html.unescape(m.group("href"))
        text = strip_tags(m.group("body"))
        if not text:
            continue

        series = "state" if re.search(r"state\s+nsq", text, re.I) else "central"

        if re.search(r"spurious", text, re.I):
            alert_type = "spurious"
        elif re.search(r"not\s+of\s+standard|nsq", text, re.I):
            alert_type = "nsq"
        else:
            alert_type = "other"

        month = year = None
        tm = MONTH_YEAR.search(text)
        if tm:
            month = MONTHS.get(tm.group("month").lower())
            year = int(tm.group("year"))

        # Some entries ("List of Drugs ... declared as Not of Standard Quality")
        # carry no month in the visible title; the publish date is the only
        # anchor we get, so record the alert as undated rather than guessing.
        published = None
        dm = DATE.search(text)
        if dm:
            mon = MONTHS.get(dm.group("m").lower())
            if mon:
                published = f"{dm.group('y')}-{mon:02d}-{int(dm.group('d')):02d}"

        url = href if href.startswith("http") else ORIGIN + href
        entries.append({
            "title": text,
            "series": series,
            "alert_type": alert_type,
            "year": year,
            "month": month,
            "published": published,
            "wrapper_url": url,
        })

    # de-duplicate on the wrapper url, keep first (index lists newest first)
    seen, out = set(), []
    for e in entries:
        if e["wrapper_url"] in seen:
            continue
        seen.add(e["wrapper_url"])
        out.append(e)
    return out


def resolve_pdf_url(wrapper_url: str) -> str | None:
    """Hop 1 -> 2: the num_id page embeds the real PDF in an iframe."""
    blob = get(wrapper_url)
    if not blob:
        return None
    body = blob.decode("utf-8", "ignore")
    if body[:5] == "%PDF-":
        return wrapper_url  # sometimes it serves the file directly
    m = IFRAME.search(body)
    if not m:
        return None
    src = html.unescape(m.group("src"))
    return src if src.startswith("http") else ORIGIN + src


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default=None,
                    help="skip alerts older than YYYY-MM (inclusive)")
    ap.add_argument("--sleep", type=float, default=0.5)
    ap.add_argument("--limit", type=int, default=0, help="0 = no limit")
    args = ap.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    index_html = get(INDEX_URL)
    if not index_html:
        print("could not fetch the CDSCO index page")
        return 1
    entries = parse_index(index_html.decode("utf-8", "ignore"))
    print(f"index lists {len(entries)} alerts")

    # Resolve the month before filtering. Entries whose title carries no month
    # ("List of Drugs ... declared as Not of Standard Quality") fall back to the
    # publish month, flagged so downstream code never presents a publish date as
    # an alert month.
    for e in entries:
        if e["year"] and e["month"]:
            e["month_source"] = "title"
        elif e["published"]:
            e["year"], e["month"] = (int(x) for x in e["published"].split("-")[:2])
            e["month_source"] = "published"
        else:
            e["month_source"] = None

    if args.since:
        sy, sm = (int(x) for x in args.since.split("-"))
        entries = [e for e in entries
                   if e["year"] and e["month"]
                   and (e["year"], e["month"]) >= (sy, sm)]
        print(f"{len(entries)} at or after {args.since}")
    if args.limit:
        entries = entries[:args.limit]

    manifest, ok, fail = [], 0, 0

    for e in entries:
        month_source = e.get("month_source") or "published"
        if not e["year"] or not e["month"]:
            print(f"  ??  no date at all: {e['title'][:70]}")
            manifest.append({**e, "status": "undated"})
            continue

        pdf_url = resolve_pdf_url(e["wrapper_url"])
        time.sleep(args.sleep)
        blob = get(pdf_url) if pdf_url else None
        time.sleep(args.sleep)

        if not blob or blob[:5] != b"%PDF-":
            fail += 1
            print(f"  XX  {e['alert_type']:8s} {e['series']:7s} "
                  f"{e['year']}-{e['month']:02d}  download failed")
            manifest.append({**e, "status": "failed", "pdf_url": pdf_url})
            continue

        # alert_type is part of the name because CDSCO publishes both an NSQ
        # alert and a spurious-drugs list for the same month. The num_id tail
        # disambiguates multiple entries sharing one month.
        uid = e["wrapper_url"].rstrip("=").rsplit("=", 1)[-1][-6:]
        out = RAW_DIR / (
            f"{e['alert_type']}_{e['series']}_{e['year']}_{e['month']:02d}"
            f"_{month_source}_{uid}.pdf"
        )
        out.write_bytes(blob)
        ok += 1
        print(f"  OK  {e['alert_type']:8s} {e['series']:7s} "
              f"{e['year']}-{e['month']:02d} [{month_source:9s}] "
              f"{len(blob):>9,} B  pub={e['published']}")
        manifest.append({
            **e,
            "status": "ok",
            "month_source": month_source,
            "pdf_url": pdf_url,
            "local_path": str(out.relative_to(ROOT)).replace("\\", "/"),
            "bytes": len(blob),
            "sha256": hashlib.sha256(blob).hexdigest(),
        })

    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\n{ok} downloaded, {fail} failed -> {RAW_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
