# Source policy — what the agent may cite, and how

Probed 2026-09-10. The rule is simple: **every claim on screen carries a source and an
authority level, and levels never blend.** A news report never renders as a regulatory
finding. A social post never renders at all.

---

## The tier system

### Tier 1 — Regulatory record. Citable as fact.
CDSCO NSQ batch alerts, CDSCO public notices, state FDA orders, licence suspensions,
recalls, the banned-drugs list.

Rendered as: "Recorded by CDSCO, <month year> — batch <no>, reason: <stated reason>"
with a link to the source PDF.

### Tier 2 — Institutional / peer-reviewed. Citable as "published by".
WHO Medical Product Alerts, peer-reviewed literature (BMJ, Lancet Respiratory Medicine,
IJME), WHO rapid alerts.

Rendered as: "WHO Medical Product Alert N°5/2025 (13 Oct 2025)" with the alert PDF linked.
Never merged into a Tier 1 statement — shown as a separate, labelled block.

### Tier 3 — News reporting. Labelled, linked, never asserted.
Reputable outlets only. Rendered as: "Reported by <outlet>, <date>" + link out.

**Why this is not paranoia.** Under Indian law, republication of a defamatory statement is
itself defamation. Restating a news claim as your own fact makes it yours. Attributing it
and linking out does not. The difference is one line of UI copy and a lawyer's afternoon.

### Tier 4 — Social media. Excluded as a source.
See below.

---

## Instagram — do not use. Not a data source.

- There is no legitimate API for reading arbitrary public posts. The Instagram Graph API
  only serves accounts you own or manage.
- Scraping breaches Meta's terms. The hackathon rules separately require **authorised** use
  of all third-party data, so this is a disqualification risk as well as a legal one.
- Worse than the legal problem is the epistemic one: social platforms are where health
  misinformation concentrates. A viral reel claiming a medicine is contaminated is not
  evidence. Building an alert on one means your agent could defame a company on the strength
  of a stranger's post — and it would be commercially motivated often enough to matter.

## X / Twitter — not a source, but occasionally a pointer.

- The API is paid and its terms restrict content display. The free tier is effectively
  write-only.
- Regulators *do* post there. If CDSCO or a state FDA posts an enforcement action, treat the
  post as a **discovery signal only** and then fetch the underlying official notice. Cite the
  notice, never the tweet.

## News — yes, but only as Tier 3.

**Legitimate access:** RSS. Google News RSS works today and needs no key
(`news.google.com/rss/search?q=...&hl=en-IN&gl=IN&ceid=IN:en`), as do most outlets' own feeds.
This is permitted, stable, and the right way to do discovery.

**Verified working 2026-09-10:**

| Source | Endpoint | Status |
|---|---|---|
| Google News RSS | `news.google.com/rss/search?q=...` | 200, 191 KB, returns items |
| PubMed E-utilities | `eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi` | 200, JSON, 6 hits for cough-syrup+DEG+India |
| WHO alert PDFs | `cdn.who.int/media/docs/default-source/substandard-and-falsified/...` | 200, valid PDF |

News is for *discovery and narrative*, never for the alert verdict. Its job is to tell you a
story exists; Tier 1 and 2 tell you whether it is true.

---

## What this changes about the product

**NSQ alerts alone would not have caught Coldrif.** That is the most important finding here.

NSQ is a monthly list of batches that failed laboratory testing. The Chhindwara event was a
*recall plus production halt plus licence suspension*, triggered by a cluster of child deaths.
Different data class. Different document type. A product built only on NSQ would have shown
the user nothing.

The alert layer needs three regulatory classes:

| Class | What it is | Source | Status |
|---|---|---|---|
| NSQ batch alerts | batches that failed lab testing | CDSCO monthly PDFs | **built** — 1,598 records |
| Recalls / suspensions / halts | enforcement action against a product or site | CDSCO notices, state FDA, WHO alerts | not built |
| Bans / prohibitions | product prohibited from sale | CDSCO banned-drugs list | not built |

## The WHO finding — the strongest single source found so far

**WHO Medical Product Alert N°5/2025**, 13 October 2025, 2 pages, downloadable as a clean PDF
from `cdn.who.int`. It states that CDSCO reported diethylene glycol in at least three oral
liquid medicines, following WHO's own identification of child fatalities in India, and names:

- **COLDRIF** — Sresan Pharmaceutical
- **Respifresh TR** — Rednex Pharmaceuticals
- **ReLife** — Shape Pharma

It records that state authorities halted production at the implicated sites, suspended
product authorisations, and initiated a recall.

This is citable, authoritative, international, and names manufacturers directly. It is
better raw material for the alert feature than any news article, and it is exactly the kind
of document a judge will recognise as credible.

Note the causal chain it documents: WHO saw the fatality cluster on 30 Sept 2025, CDSCO
reported DEG on 8 Oct, WHO published the alert on 13 Oct. **Two weeks.** That gap is the
product argument — in a working system the parent is warned in hours, not weeks.
