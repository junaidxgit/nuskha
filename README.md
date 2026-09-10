# MedLens — what is on your prescription, and what it should cost

*Working title. Built for the AWS **Agents for Humans** hackathon (Everyday Agents track).*

A user types the salt on their prescription. The agent finds every same-composition
option, shows what the law says it may cost, and flags whether any of the
manufacturers involved have a recorded quality failure.

**Status: data layer only.** No agent, no UI, no Strands code yet.

---

## Why composition, not brand

Indian prescriptions already name the salt — a doctor writes *Tab Paracetamol 650*,
not *Dolo 650*. Starting from the salt removes the single hardest problem in this
domain: mapping brand names to compositions for Indian medicines requires a dataset
that does not exist publicly. Composition-first is not a compromise, it is how
prescriptions actually read.

## Why the alert is the product

Price comparison across Indian pharmacies is already commoditised (mymedisaathi,
medcompare.in, medikwise, medibachat, rxjinn). What nobody does is surface the
regulator's own quality record next to the price. That is the whole idea.

In Sept–Oct 2025, children died in Chhindwara, Madhya Pradesh after consuming
cough syrup contaminated with diethylene glycol. Reporting put the toll between
14 and 24. WHO identified the fatality cluster on **30 Sept 2025**, CDSCO reported
the DEG finding on **8 Oct**, and WHO published a public alert on **13 Oct** —
two weeks from signal to public warning. During those two weeks prescriptions were
still being filled.

The batches were in the regulatory record. Nobody holding a prescription could see it.

---

## Two data classes, deliberately never merged

An early version of this project assumed CDSCO's NSQ list was enough. It is not.
NSQ is a monthly list of batches that **failed laboratory testing**. Chhindwara was
a **recall plus production halt plus licence suspension** — a different document type
entirely. `--check coldrif` proves the point: zero NSQ hits, one WHO hit.

| class | what it is | source | status |
|---|---|---|---|
| NSQ batch alerts | batches that failed lab testing | CDSCO monthly PDFs | **built** — 1,598 records |
| Recalls / suspensions / contamination | enforcement action, product recalls | WHO Medical Product Alerts | **built** — 15 alerts |
| Bans / prohibitions | products prohibited from sale | CDSCO banned-drugs list | not built |

## What is built

```
pipeline/fetch_nsq.py          download CDSCO NSQ PDFs, 2024-01..2025-06   (Tier 1)
pipeline/parse_nsq.py          bordered-table layout -> 1,598 records       (Tier 1)
pipeline/fetch_nsq_recent.py   download CDSCO NSQ PDFs, 2025-07..2026-07   (Tier 1)
pipeline/parse_nsq_v2.py       cell-rect layout -> 1,993 records            (Tier 1)
pipeline/fetch_who.py          download WHO Medical Product Alerts          (Tier 2)
pipeline/parse_who.py          WHO text -> products / manufacturers / dates (Tier 2)
pipeline/build_db.py           combined SQLite index + tiered lookup
```

**Tier 1 — CDSCO NSQ, 2024-01 → 2026-07:** 70 PDFs, **3,591 records**, 2024: 699 ·
2025: 1,831 · 2026: 1,061.

| field | 2024–2025 set | 2025–2026 set |
|---|---|---|
| product_name | 99.9% | **100.0%** |
| batch_no | 99.4% | **100.0%** |
| manufacturer | 100.0% | 98.6% |
| nsq_reason | 99.7% | 98.6% |
| reported_by | 99.6% | 98.6% |
| expiry_date | 97.2% | 98.3% |
| mfg_date | 96.9% | **98.4%** |

**Independently validated.** The parser's monthly totals were checked against
trade-press counts published independently of this work — **7 of 8 months match
exactly** (2025-07: 143, 2025-08: 94, 2025-10: 211, 2025-11: 205, 2025-12: 167,
2026-06: 159, 2026-07: 239). The one difference, 2026-05 at 159 vs 157, is the two
spurious-drug records in that file, which are not NSQ samples.

**Tier 2 — WHO alerts:** 15 alerts (2024 → 2026), full text extracted, 5 mentioning
India. 11 have product names extracted, 4 have manufacturer names. Covers N°5/2025,
which names COLDRIF (Sresan Pharmaceutical), Respifresh TR (Rednex Pharmaceuticals)
and ReLife (Shape Pharma).

## Run it

```bash
PY="C:/Users/offic/.workbuddy-ai/binaries/python/envs/default/Scripts/python.exe"

$PY pipeline/fetch_nsq.py --since 2024-01        # ~4 min, 45 PDFs
$PY pipeline/parse_nsq.py                        # ~3 min
$PY pipeline/fetch_nsq_recent.py --since 2025-07 # ~1 min, 25 PDFs
$PY pipeline/parse_nsq_v2.py                     # ~5 min
$PY pipeline/fetch_who.py --since 2024           # ~1 min, 15 alerts
$PY pipeline/parse_who.py                        # structured fields
$PY pipeline/build_db.py --check "coldrif"       # tiered lookup
$PY pipeline/build_db.py --check "atorvastatin"
```

Outputs: `data/raw/nsq/*.pdf`, `data/raw/nsq_recent/*.pdf`, `data/raw/who/*.pdf`,
manifests with sha256 per file, and `data/processed/` JSONL + `medlens.db`.

Sample output — the query only Tier 2 catches:

```
$ python pipeline/build_db.py --check "coldrif"

[TIER 1] CDSCO NSQ batch alerts - recorded by the regulator
         0 matching record(s)

[TIER 2] WHO Medical Product Alerts - published by WHO
         1 matching alert(s)
  Medical Product Alert N°5/2025: Substandard (contaminated) oral liquid medicines
    date    13 October 2025   india=yes
    products COLDRIF; Respifresh TR
    makers   Sresan Pharmaceutical; Rednex Pharmaceuticals; Shape Pharma
```

And a query that reaches into 2026:

```
$ python pipeline/build_db.py --check "atorvastatin"

[TIER 1] CDSCO NSQ batch alerts - recorded by the regulator
  Atorvastatin Tablets IP 10mg
    batch AV26072   mfg Apr-2026  exp Sep-2027
    maker  Eurokem Laboratories Pvt Ltd, C-25, SIDCO Pharmaceutical Complex, Alathur
    reason Dissolution
    source state / state alert 2026-07; lab: State Lab
```

---

## How the CDSCO site actually works

Reverse-engineered 2026-09-10, because nothing about it is guessable:

1. **Index** — `/opencms/opencms/en/Notifications/nsq-drugs/` lists every alert as
   `<a href='...download_file_division.jsp?num_id=<base64>'>` with a title and date.
2. **Wrapper** — that `num_id` URL returns a tiny HTML page containing an `<iframe>`.
3. **Real PDF** — the iframe `src` points at `/opencms/resources/.../UploadAlertsFiles/<code>.pdf`.

The published filenames are cryptic codes (`stnsqapr25.pdf`), so filename guessing
fails. Go through the index. The title text is inconsistent — "NSQ ALERT FOR THE
MONTH OF Feb-2025", "Not Of Standard of Quality (NSQ) ALERT FOR THE MONTH OF
April-2025", "List of Drugs ... declared as Not of Standard Quality" — so the parser
matches `<month> <year>` anywhere and falls back to the publish date, recording which
source it used (`month_source`) so a publish date is never presented as an alert month.

**Parsing gotchas already handled:**

- Tables are bordered; `pdfplumber.find_tables()` gives clean 8-column cells.
  Bucketing words by x-position fails — headers are centred, data is left-aligned,
  so every column shifts by one.
- Only page 1 carries a header; continuation pages are headerless, so the column
  mapping is carried across pages.
- Headers wrap mid-word ("Manufa cturing Date"), so whitespace is stripped before
  matching labels.
- Some PDFs are letter-spaced ("T e l a n g a n a"), so runs of single-character
  tokens are rejoined.

## The July-2025 format change

The layout changed at July 2025 and the 2024-era parser returns **zero** records against
it. Three things defeat the obvious approaches:

1. `find_tables()` returns ~19 tables per page, because every cell carries its own border
   and the table fragments into cell-sized pieces. Page 1 reports 18 columns, page 2
   reports 16, and the indices do not align.
2. pdfplumber cell tuples are `(x0, top, x1, bottom)` and carry **no text**, so cells must
   be cropped to be read. Cropping cells taken from the *fragmented tables* duplicates
   text, because those bboxes overlap.
3. Banding records from the S.No anchor's own `top` cuts records in half — the S.No is
   vertically centred in a 178pt-tall row.

**The unlock:** every record is a single row of ten tall, *non-overlapping* cell
rectangles. For record 1 of the May-2026 alert they all span `top=74.2 → bottom=252.1`
with x-ranges `72.4-114.2, 114.9-234.8, 235.2-288.8, 289.6-365.9, 366.7-415.6,
416.3-508.5, 509.3-588.5, 589.2-649.0, 649.7-709.5, 710.2-770.0`.

So the row grouping is given directly by the drawing rather than inferred: filter
`page.rects` to cell-sized rectangles, group by identical vertical extent, sort by x, and
crop each cell. Because the cells tile the row exactly, nothing overlaps and the text
comes out clean. `parse_nsq_v2.py` implements this.

One collision to know about: the source's own "Alert Month" column is also called
`alert_month`, which clobbers the numeric metadata field of the same name. It is renamed
`alert_period` in the parsed record.

## Known gaps

- **Provenance is a mirror.** The 2025-07+ PDFs come from trade-press mirrors of the
  CDSCO documents, because the CDSCO endpoint moved and the Aug-2025 notice announcing
  it is a scanned image with no extractable text. Every manifest entry records
  `provenance: "mirror"` and the source URL, and each file is hashed. Before shipping,
  resolve the CDSCO primary or re-host and say so. A tool making safety claims must be
  able to prove its documents are unaltered.
- **The price layer is not built.** NPPA ceiling prices and Jan Aushadhi MRP are still
  missing, so the agent cannot yet answer "what should this cost". Discovery lead: the
  same WordPress REST API that exposed the NSQ mirrors also carries NPPA posts
  ("NPPA fixed retail price of 39 formulations: July 2026"), which is a clean way in.
- `alert_type` labelling is inconsistent between the two fetchers: the 2024 set tags
  state alerts as `nsq`, the 2025+ set tags them `state`. `series` is correct in both.
  Cosmetic, but worth normalising before the UI consumes it.
- WHO extraction is pattern-based and incomplete: 11 of 15 alerts yield product names,
  4 yield manufacturers, and N°5/2025 returns COLDRIF and Respifresh TR but misses
  ReLife. Conservative by design — it returns nothing rather than inventing a name.
- 16 pre-2025 NSQ files yield no records: the "spurious drugs" and older "other" alerts
  use a different table shape.
- Manufacturer normalisation is deliberately lossy (strips "Pvt/Ltd/Pharma/...").
  Retrieval only, never display.
- Occasional source typos and hyphenation survive ("Pharmaceuti cals", "MISBRANDE D",
  "Mec obalamin", "Lhore" for Lahore). These are defects in the source PDFs.

## Guardrails (non-negotiable)

An NSQ finding is **batch-specific**. A firm with one flagged batch is not an
"adulterated manufacturer", and saying so is defamation. Therefore:

1. Show the batch number, alert month, exact stated reason, and a link to the source PDF.
2. Never score, rank, or editorialise. Mirror the government record.
3. State that absence from the list is **not** evidence of quality — only sampled
   batches are tested.
4. Never instruct a substitution. Composition match is not proven therapeutic
   equivalence; CDSCO does not require bioequivalence studies for domestically
   marketed generics. Persistent "not medical advice" disclaimer.
5. Government data only. Do not scrape commercial pharmacies — their terms forbid it,
   and the hackathon requires authorised use of all third-party data.

Full detail: `docs/data-sources.md`.
