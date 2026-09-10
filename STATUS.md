# Status — done / next

**Verified 2026-09-11 00:45 IST.** Deadline **Sep 15, 05:30 IST** → 4 days 4 hours left.
Nearest hard deadline: **AWS credits form, Sep 12 00:30 IST (~23 hours).**

---

## Done

### Foundations
- [x] Identity + working prefs pinned down
- [x] Idea validated against the hackathon theme (Everyday Agents)
- [x] Competitor scan — price comparison is commoditised (5 live sites); the quality-record
      layer is the differentiator
- [x] Legal framing settled: NSQ findings are batch-specific, so the product mirrors the
      government record rather than editorialising

### Data sources — all verified by actually fetching, not by reading about them
- [x] CDSCO NSQ alerts: reverse-engineered (index → iframe → PDF, cryptic filenames)
- [x] WHO Medical Product Alerts: reverse-engineered (index → news page → cdn PDF)
- [x] NPPA ceiling prices: reachable, 907 scheduled formulations
- [x] Jan Aushadhi: API located at `:8443`, guest token works, product endpoint unsolved
- [x] Trade-press WordPress REST API: clean discovery channel for recent NSQ + NPPA posts
- [x] Source policy written — 4 tiers, Instagram/X excluded (`docs/source-policy.md`)

### Pipeline — working
- [x] `fetch_nsq.py` — 45 CDSCO PDFs, 2024-01 → 2025-06
- [x] `parse_nsq.py` — **1,598 clean records**, 1,197 manufacturers, 342 pages
- [x] Field completeness: manufacturer 100%, product 99.9%, reason 99.7%, lab 99.6%,
      batch 99.4%, expiry 97.2%, mfg 96.9%
- [x] `fetch_who.py` — 15 WHO alerts, 2024 → 2026, full text
- [x] `parse_who.py` — structured products / manufacturers / dates / batches
- [x] `fetch_nsq_recent.py` — **25 PDFs, 2025-07 → 2026-07**, hashed, provenance recorded
- [x] `build_db.py` — combined SQLite index with tiered lookup
- [x] `--check` demo works both directions:
      `coldrif` → 0 Tier 1 / 1 Tier 2 · `atorvastatin` → 2 Tier 1 / 0 Tier 2

### Submission scaffolding
- [x] `LICENSE` (MIT) — required in the repo About section
- [x] `.gitignore` — raw PDFs and DBs excluded, JSONL tracked
- [x] `git init` + **3 commits** (`82f389d` head), 17 files, clean tree
- [x] `README.md` — setup, gotchas, guardrails, gaps
- [x] `PLAN.md` — day-by-day schedule + video script
- [x] `docs/data-sources.md`, `docs/source-policy.md`

---

## Next — in priority order

### 1. Finish the 2025-07+ NSQ parser — highest value
The documents are downloaded and hashed; only the parser is missing. This is the one gap
that makes the Tier 1 layer blind to the last 13 months.
- [ ] Fix text duplication: crops overlap, so the same cell text is read from neighbouring
      bboxes. Dedup by bbox containment, or restrict each crop to words whose centre falls
      inside the cell.
- [ ] Handle the two column counts (page 1 = 18, page 2 = 16) — map by x-position from the
      header, not by index.
- [ ] Target: `--check "paracetamol"` returns 2026 records with the same field quality as
      the 2024 set (≥96%).
- [ ] Merge into `nsq_records.jsonl` **only after** quality clears that bar. Keep the
      separate file until then.

### 2. Price layer — nothing built yet
- [ ] NPPA ceiling prices via the trade-press API (posts like "NPPA fixed retail price of 39
      formulations: July 2026"). 907 scheduled formulations. Gives the legal maximum.
- [ ] Jan Aushadhi MRP — either crack the `:8443` product endpoint (~1 hr) or fall back to
      their official MRP PDF. Gives the cheap compliant floor.
- [ ] Answer shape: *"legal ceiling ₹X, Jan Aushadhi equivalent ₹Y"*

### 3. Admin — do these today, they're blockers if forgotten
- [ ] **AWS Builder ID** at builder.aws.com
- [ ] **$50 AWS credits form** — closes Sep 12 00:30 IST
- [ ] **Create the public GitHub repo, push, add description + topics**
- [ ] Confirm GitHub shows the MIT license in the About section
- [ ] Add surname to the copyright line in `LICENSE`

### 4. The agent itself
- [ ] Strands Agents SDK setup (AWS account, SDK install)
- [ ] Tools: `find_alternatives(salt, strength, form)`, `get_price(brand)`,
      `check_quality_record(name)` — the last wraps `medlens.db`
- [ ] Composition-first input (the salt on the prescription), never brand-first
- [ ] Disclaimers enforced in code, not just copy: batch-specificity, "absence ≠ safe",
      "not medical advice", no substitution instructions

### 5. Product surface
- [ ] Web UI — one input, one result card, tiers as visually separate blocks
- [ ] Architecture diagram (required submission item)
- [ ] Deploy: AgentCore (lifts Technical Implementation) + live demo link

### 6. Submission
- [ ] Demo video, ≤5 min, public on YouTube/Vimeo
- [ ] Text description
- [ ] Submit **Sep 14 evening**, not the last hour
- [ ] Optional: builder.aws.com post, "Agents for Humans" in the title (0.2 pts, max 0.6,
      only counts if you reach Stage Two)

---

## Known gaps (carried, not hidden)

| gap | impact |
|---|---|
| 2025-07+ NSQ not parsed | Tier 1 blind to the last 13 months — the window Chhindwara-style events fall in |
| Recent PDFs are **mirrors** | provenance recorded + hashed; resolve the CDSCO primary or re-host before shipping |
| WHO extraction incomplete | 11/15 yield products, 4/15 manufacturers; N°5/2025 misses ReLife |
| Bans / prohibitions class | third regulatory class, unbuilt |
| 16 pre-2025 NSQ files | "spurious"/older formats, different table shape, yield nothing |
| Manufacturer normalisation | lossy by design — retrieval only, never display |

## Traps already hit (don't re-hit)

1. Word-position column bucketing shifts every column by one — headers are centred, data is
   left-aligned. Use `find_tables()` on the borders.
2. Only page 1 has a header; continuation pages need the column map carried forward.
3. Headers wrap mid-word ("Manufa cturing Date") — strip all whitespace before matching.
   Took mfg_date from 47.9% → 96.9%.
4. Some PDFs are letter-spaced ("T e l a n g a n a") — rejoin single-char runs.
5. `pdfplumber` cell tuples are `(x0, top, x1, bottom)` with **no text** — crop to read.
6. Derived-data scripts must never share an output path. `parse_nsq_v2.py` overwrote the
   1,598-record dataset once. Separate files.
7. `curl -k` is required (TLS verification fails through the local proxy).
8. `/tmp` does not exist in this Git Bash — write scratch files inside the workspace.
