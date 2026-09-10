"""Download CDSCO NSQ alerts published after June 2025.

The CDSCO index page (/Notifications/nsq-drugs/) stops at June 2025 - the
monthly lists moved to a "new dedicated link" announced in an Aug-2025 notice.
That notice is a scanned image with no extractable text, and the new CDSCO
endpoint has not been located.

The documents are mirrored by the trade press, whose WordPress REST API is a
clean discovery channel:

    /wp-json/wp/v2/posts?search=NSQ&per_page=100&_fields=date,link,title,content

Each monthly post links the CDSCO PDFs:

    Drug-Alert-<Month>-<Year>-CDSCO.pdf
    Drug-Alert-<Month>-<Year>-States.pdf
    Drug-Alert-<Month>-<Year>-Spurious-Drugs.pdf

PROVENANCE WARNING: these are CDSCO documents hosted on a third-party mirror.
Every manifest entry records `provenance: "mirror"` and the source URL. Before
this ships as a product, either resolve the CDSCO primary or re-host the files
and say so. A tool that makes safety claims must be able to prove its documents
are unaltered - which is why each file is hashed.

Run:
    python pipeline/fetch_nsq_recent.py --since 2025-07
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw" / "nsq_recent"
MANIFEST = ROOT / "data" / "raw" / "nsq_recent_manifest.json"

API = ("https://thehealthmaster.com/wp-json/wp/v2/posts"
       "?search={q}&per_page=100&_fields=date,link,title,content")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

PDF_LINK = re.compile(
    r'href="(https?://[^"]*/wp-content/uploads/[^"]*\.pdf)"', re.I)
MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}
# filename fragment -> our internal kind
KINDS = [("nsq", r"CDSCO"), ("state", r"States"), ("spurious", r"Spurious")]


def get(url: str, timeout: int = 60) -> bytes | None:
    url = urllib.parse.quote(url, safe="/:?=&%#[]@!$'()*+,;~")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as r:
            return r.read() if r.status == 200 else None
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        return None


def month_from_title(title: str) -> tuple[int, int] | None:
    m = re.search(r"\b(" + "|".join(MONTHS) + r")\s+(20\d\d)\b", title, re.I)
    return (int(m.group(2)), MONTHS[m.group(1).lower()]) if m else None


def classify(filename: str) -> str | None:
    for kind, pat in KINDS:
        if re.search(pat, filename, re.I):
            return kind
    return None


def discover(queries: list[str], sleep: float) -> dict[tuple[int, int, str], dict]:
    """Find every monthly alert PDF. Keyed by (year, month, kind)."""
    found: dict[tuple[int, int, str], dict] = {}
    for q in queries:
        blob = get(API.format(q=urllib.parse.quote(q)))
        time.sleep(sleep)
        if not blob:
            print(f"  !!  query {q!r} failed")
            continue
        try:
            posts = json.loads(blob)
        except Exception:
            continue
        if not isinstance(posts, list):
            continue
        print(f"  {len(posts):>3} posts for {q!r}")
        for p in posts:
            title = re.sub(r"<[^>]+>", "", p.get("title", {}).get("rendered", ""))
            ym = month_from_title(title)
            if not ym:
                continue
            content = p.get("content", {}).get("rendered", "")
            for url in PDF_LINK.findall(content):
                name = url.rsplit("/", 1)[-1]
                kind = classify(name)
                if not kind:
                    continue
                found.setdefault((ym[0], ym[1], kind), {
                    "year": ym[0], "month": ym[1], "kind": kind,
                    "source_url": url, "post_url": p.get("link", ""),
                    "post_title": title,
                })
    return found


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2025-07")
    ap.add_argument("--sleep", type=float, default=0.5)
    args = ap.parse_args()

    sy, sm = (int(x) for x in args.since.split("-"))
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    print("discovering monthly alerts via the WordPress REST API")
    found = discover(["NSQ", "Drug alert", "Spurious"], args.sleep)

    items = [v for k, v in found.items() if (v["year"], v["month"]) >= (sy, sm)]
    items.sort(key=lambda v: (v["year"], v["month"], v["kind"]))
    print(f"\n{len(items)} alert PDFs at or after {args.since}")

    manifest, ok, fail = [], 0, 0
    for it in items:
        name = it["source_url"].rsplit("/", 1)[-1]
        out = RAW_DIR / f"{it['kind']}_{it['year']}_{it['month']:02d}_{name}"
        blob = get(it["source_url"])
        time.sleep(args.sleep)
        if not blob or blob[:5] != b"%PDF-":
            fail += 1
            print(f"  XX  {it['year']}-{it['month']:02d} {it['kind']:8s} failed")
            manifest.append({**it, "status": "failed"})
            continue
        out.write_bytes(blob)
        ok += 1
        print(f"  OK  {it['year']}-{it['month']:02d} {it['kind']:8s} "
              f"{len(blob):>9,} B  {name}")
        manifest.append({
            **it, "status": "ok", "provenance": "mirror",
            "local_path": str(out.relative_to(ROOT)).replace("\\", "/"),
            "bytes": len(blob), "sha256": hashlib.sha256(blob).hexdigest(),
        })

    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\n{ok} downloaded, {fail} failed -> {RAW_DIR}")
    print("NOTE: provenance is 'mirror'. Resolve the CDSCO primary before shipping.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
