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
pipeline/fetch_nsq.py   download CDSCO NSQ alert PDFs      (Tier 1)
pipeline/parse_nsq.py   PDF tables -> structured records   (Tier 1)
pipeline/fetch_who.py   download WHO Medical Product Alerts (Tier 2)
pipeline/build_db.py    combined SQLite index + tiered lookup
```

**Tier 1 — CDSCO NSQ:** 45 PDFs, 342 pages, **1,598 records**, 1,197 distinct
manufacturers, 2024-01 → 2025-06.

| field | filled |
|---|---|
| manufacturer | 100.0% |
| product_name | 99.9% |
| nsq_reason | 99.7% |
| reported_by | 99.6% |
| batch_no | 99.4% |
| expiry_date | 97.2% |
| mfg_date | 96.9% |

**Tier 2 — WHO alerts:** **15 alerts** (2024 → 2026), full text extracted, 5 mentioning
India. Covers N°5/2025, which names COLDRIF (Sresan Pharmaceutical), Respifresh TR
(Rednex Pharmaceuticals) and ReLife (Shape Pharma).

## Run it

```bash
PY="C:/Users/offic/.workbuddy-ai/binaries/python/envs/default/Scripts/python.exe"

$PY pipeline/fetch_nsq.py --since 2024-01    # ~4 min, 45 PDFs
$PY pipeline/parse_nsq.py                    # ~3 min
$PY pipeline/fetch_who.py --since 2024       # ~1 min, 15 alerts
$PY pipeline/build_db.py --check "coldrif"   # tiered lookup
$PY pipeline/build_db.py --check "atorvastatin"
```

Outputs: `data/raw/nsq/*.pdf`, `data/raw/who/*.pdf`, `data/raw/nsq_manifest.json`
(sha256 per file), `data/processed/nsq_records.jsonl`, `data/processed/who_alerts.jsonl`,
`data/processed/medlens.db`.

Sample output for a query that only Tier 2 catches:

```
$ python pipeline/build_db.py --check "coldrif"

[TIER 1] CDSCO NSQ batch alerts - recorded by the regulator
         0 matching record(s)

[TIER 2] WHO Medical Product Alerts - published by WHO
         1 matching alert(s)
  Medical Product Alert N°5/2025: Substandard (contaminated) oral liquid medicines
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

## Known gaps

- **The CDSCO index stops at mid-2025.** `/Notifications/nsq-drugs/` lists 225 alerts
  spanning 2013–2025, but the newest NSQ alert on it is 2025-06. Yet monthly NSQ alerts are
  known to exist for 2026 (239 samples in July 2026, 157 in May 2026 per trade press), and
  CDSCO published a notice in Aug 2025 about a *new dedicated link* for NSQ alerts. **The
  current endpoint has not been located.** Tier 2 (WHO) does cover 2026, so recent events
  are partially visible — but Tier 1 has a blind spot exactly where recent failures live.
  This is the highest-priority gap.
- 16 NSQ files yield no records: the "spurious drugs" and older "other" alerts use a
  different table shape. ~5 spurious records parsed; the rest need their own mapper.
- Manufacturer normalisation is deliberately lossy (strips "Pvt/Ltd/Pharma/...").
  Good for candidate retrieval, **not** for display or exact matching. "Pulse Pharma"
  and "Pulse Pharmaceuticals" collapse together, which is usually right and
  occasionally wrong.
- WHO alerts are stored as full text and searched with LIKE, not extracted into
  product/manufacturer fields. `--check` finds them, but the agent cannot yet say
  *which* product in an alert matched.
- Occasional source typos survive ("Mec obalamin", "Lhore" for Lahore).
- `mfg_date` for one NSQ record shows "NM".

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
