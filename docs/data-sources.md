# Indian pharma open-data sources — verified reconnaissance

Reconnaissance done 2026-09-10 for the "medicine alternative + quality record" agent.
Everything below was tested from this machine, not assumed.

---

## 1. CDSCO NSQ drug alerts — VERIFIED WORKING

**What it is:** monthly PDF listing drug batches sampled by regulators and declared
*Not of Standard Quality*. This is the only official, citable source for "this
manufacturer's batch failed testing".

**URL pattern (predictable, so scrapeable in a loop):**

```
https://cdsco.mohfw.gov.in/opencms/resources/UploadCDSCOWeb/2018/UploadAlertsFiles/NSQ%20ALERT%20FOR%20THE%20MONTH%20OF%20<Mon>-<YYYY>.pdf
https://cdsco.mohfw.gov.in/opencms/resources/UploadCDSCOWeb/2018/UploadAlertsFiles/STATE%20NSQ%20ALERT%20FOR%20THE%20MONTH%20OF%20<Mon>-<YYYY>.pdf
```

Two series: central-lab alerts (`NSQ ALERT...`) and state-lab alerts (`STATE NSQ ALERT...`).
Month token format observed: `Feb-2025`, `JANUARY-2025` — **case is inconsistent, probe both.**
Fetch with `curl -k` (TLS cert check fails on this host; the sandbox proxy presents a wrong cert).

**Verified sample:** `Feb-2025` → HTTP 200, 158,846 bytes, 6 pages.
Saved at `data/raw/nsq_feb2025.pdf`.

**Schema (extracts cleanly with `pypdf` — no OCR needed):**

| Field | Example |
|---|---|
| S.No | 1 |
| Product/Drug Name | Compound Sodium Lactate Injection IP (Ringer Lactate Solution for Injection) |
| Batch No. | DCSL3021 |
| Manufacturing Date | 11/2023 |
| Expiry Date | 10/2026 |
| Manufactured By | M/s. Eurolife Healthcare Pvt. Ltd., K.No-520, Bhagwanpur, Roorkee-247667, Uttarakhand |
| NSQ Result | Particulate Contamination, Bacterial endotoxin test, Sterility and Description |
| Reported by | CDL, Kolkata |

Document has sections: **A. CDSCO/Central Laboratories**, then a state section.
~100–240 records per month (239 in July 2026, 157 in May 2026, 94 in Sep 2025).

**Extraction:** `pypdf` works. The text comes out as a run of lines with no reliable
column delimiters, so parse by regex anchors (`S.No` counter, `Batch No` token,
date pairs `MM/YYYY`, trailing lab name) rather than by whitespace splitting.

---

## 2. Jan Aushadhi (PMBJP) product prices — PARTIAL

The website `janaushadhi.gov.in` is a client-rendered React SPA — the product table
is not in the HTML. The real API was recovered from the JS bundle
(`/static/js/main.f33b8dc2.js`).

**Base URL (hardcoded in bundle module 71306):**

```
https://janaushadhi.gov.in:8443/          # note the non-standard port
```

**Auth — WORKS:** guest token, no credentials needed.

```
GET https://janaushadhi.gov.in:8443/auth/generateGuestToken
→ {"responseBody":"eyJhbGciOiJIUzI1NiJ9...","message":"Token generated successfully","responseCode":200}
```

Send as header: `Authorization: Bearer <token>`. Tokens are short-lived; the SPA
re-mints them when the JWT `exp` is within 60s.

**Product endpoint — EXISTS BUT NOT YET CRACKED:**

```
POST https://janaushadhi.gov.in:8443/api/v1/website/getAllProductForWeb
```

- `GET` → `405 Method Not Allowed` (so: POST only)
- POST `{}` → `{"message":"pageSize and page index cant be null","responseCode":400}`
- POST `{"pageNumber":0,"pageSize":5}` → passes the null check, then `server error`
- POST `{"pageIndex":0,"pageSize":10}` → `server error`

So the pagination fields are recognised by name somewhere in the chain but the
payload shape is still wrong. **Next step:** grep the bundle for the call site of
`getAllProductForWeb` to read the exact request body the SPA sends.

**Fallback if that stalls:** PMBJP publishes the product/MRP portfolio as a PDF
(third-party mirrors exist, e.g. the "Jan Aushadhi Drug Code List" PDFs). Lower
fidelity but zero reverse-engineering.

---

## 3. NPPA ceiling prices — REACHABLE

`https://nppa.gov.in/` and `https://nppa.gov.in/2026e` both respond. Covers the
**907–935 scheduled formulations** under DPCO, revised annually (latest revision
effective 1 April 2026, +0.64956% WPI). Published as HTML/PDF, not an API.

This is the legally binding **maximum retail price** for scheduled drugs. Useful as
the "legal ceiling" in the answer, and it is genuinely under-used by consumers.

---

## 4. Legal guardrails — read before writing any code that names a company

These are not optional; they are the difference between a useful product and a
lawsuit.

1. **NSQ is batch-specific, never company-wide.** A firm with one flagged batch is
   not an "adulterated manufacturer". Stating that is both factually wrong and
   defamatory. Always show batch no. + alert month + the exact stated reason.
2. **Mirror, never editorialise.** Quote the government record, link the source PDF.
   No scores, no "bad manufacturer" ranking, no red flags of our own invention.
3. **Absence from NSQ ≠ safe.** Only sampled batches are tested. Say so explicitly,
   or the app implies unlisted = trustworthy, which is false and harmful.
4. **Not medical advice.** Never instruct a substitution. Show same-composition
   alternatives and let the user's doctor decide. Persistent disclaimer.
5. **Do not scrape commercial pharmacies** (1mg / PharmEasy / Netmeds / Truemeds).
   Their ToS forbid it, and the hackathon rules require authorised use of all
   third-party data. Government sources only.
6. **A cheaper generic is not automatically equivalent.** CDSCO does not mandate
   bioequivalence studies for domestically marketed generics. The agent should show
   same salt + strength + dosage form, and be honest that this is composition
   matching, not proven therapeutic equivalence.

---

## 5. Environment notes

- `curl -k` is required — CDSCO's host fails TLS verification through the local proxy.
- `/tmp` does not exist in this Git Bash. Write scratch files inside the workspace.
- `pypdf 6.18.0` installed in venv `C:\Users\offic\.workbuddy-ai\binaries\python\envs\default`.
