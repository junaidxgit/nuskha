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
- [x] `parse_nsq.py` — 1,598 records (2024–2025 layout)
- [x] `fetch_nsq_recent.py` — 25 PDFs, 2025-07 → 2026-07, hashed, provenance recorded
- [x] **`parse_nsq_v2.py` — 1,993 records (2025–2026 layout). DONE.** The unlock: each  
  record is one row of ten non-overlapping cell rectangles, so group `page.rects` by  
  identical vertical extent and crop each cell. Clean text, no duplication.
- [x] **Tier 1 total: 3,591 records, 2024-01 → 2026-07** (2024: 699 · 2025: 1,831 · 2026: 1,061)
- [x] **Independently validated: 7 of 8 months match trade-press totals exactly**  
  (2025-07: 143, 2025-08: 94, 2025-10: 211, 2025-11: 205, 2025-12: 167, 2026-06: 159,  
  2026-07: 239). The 2026-05 difference is the 2 spurious-drug records in that file.
- [x] New-set field quality: product 100%, batch 100%, mfg 98.4%, expiry 98.3%,  
  manufacturer 98.6%, reason 98.6% — **better than the 2024 set**
- [x] `fetch_who.py` — 15 WHO alerts, 2024 → 2026, full text
- [x] `parse_who.py` — structured products / manufacturers / dates / batches
- [x] `fetch_nppa.py` — **349 NPPA ceiling prices**, 23 notifications, 206 formulations
- [x] `fetch_janaushadhi.py` — **1,904 Jan Aushadhi products** with composition + MRP
- [x] `build_db.py` — combined SQLite index: NSQ + WHO + NPPA + Jan Aushadhi
- [x] `--check` demo works both directions:  
  `coldrif` → 0 Tier 1 / 1 Tier 2 · `atorvastatin` → 2 Tier 1 (2026 records) / 0 Tier 2
- [x] `--price` works: **atorvastatin floor Rs 0.88 vs ceiling Rs 4.94 per tablet** —
  a 5.6x gap, both figures official
- [x] Fixed a real correctness bug: NPPA quotes "per 1 Capsule", Jan Aushadhi "per 10's".
  Comparing raw figures put the floor ABOVE the ceiling. `parse_unit()` normalises both
  and only compares matching unit kinds, with a printed sanity verdict.

### The agent — built
- [x] `nuskha/queries.py` — the three query functions, DB-backed
- [x] **Strength matching** (`strengths_of`) — stops "metformin 250 mg" matching a 500 mg
  product. This was the flagged highest-priority fix.
- [x] **Combination-product detection** (`is_combination`) — strength matching alone still
  returned "Aspirin & Atorvastatin Capsules" as the ceiling for plain atorvastatin. Single
  ingredient now ranks first, and a WARNING is attached when only a combination matches.
- [x] `nuskha/tools.py` — Strands `@tool` wrappers; schema verified
  (`tool.tool_spec["inputSchema"]["json"]`, 3 tools registered)
- [x] `nuskha/agent.py` — `build_agent()` + a system prompt enforcing the framing rules
- [x] `nuskha/cli.py` — deterministic CLI (`price` / `check` / `report` / `json`) + `ask`
- [x] `nuskha/mock_model.py` — scripted model; **the real Strands loop runs offline**
  with no AWS credentials. Verified trace: `user → assistant(toolUse ×2) →
  user(toolResult ×2) → assistant(text)`.
- [x] `docs/agent.md` — how to run, and the API gotchas for wiring a real model
- [x] `check coldrif` now returns **both tiers** — the CDSCO batch record (batch SR-13,
  reason "Adulterated", state alert 2025-10) *and* WHO N°5/2025. The recency gap closing
  is what put the batch itself on screen.

### Submission scaffolding

- [x] `LICENSE` (MIT) — required in the repo About section
- [x] `.gitignore` — raw PDFs and DBs excluded, JSONL tracked
- [x] `git init` + **3 commits** (`82f389d` head), 17 files, clean tree
- [x] `README.md` — setup, gotchas, guardrails, gaps
- [x] `PLAN.md` — day-by-day schedule + video script
- [x] `docs/data-sources.md`, `docs/source-policy.md`

---

## Next — in priority order

### 1. ~~Finish the 2025-07+ NSQ parser~~ — DONE

Tier 1 now covers 2024-01 → 2026-07 with 3,591 records, validated against independently
reported monthly totals (7 of 8 exact). This is no longer the critical path.

### 2. ~~Price layer~~ — BUILT, with two correctness gaps

- [ ] **Strength matching.** `--price "metformin"` compares the cheapest Jan Aushadhi entry
  (250 mg) against the cheapest NPPA ceiling (a glimepiride combination). Both real, not
  the same product. Must match on strength before showing a range. **Highest priority.**
- [ ] **NPPA coverage.** 206 formulations captured vs 907–935 in the full DPCO schedule.
  Posts sometimes carry truncated preview tables. Needs the S.O. PDFs from nppa.gov.in.

### 3. Admin — do these today, they're blockers if forgotten

- [ ] **AWS Builder ID** at builder.aws.com
- [ ] **$50 AWS credits form** — closes Sep 12 00:30 IST
- [ ] **Create the public GitHub repo, push, add description + topics**
- [ ] Confirm GitHub shows the MIT license in the About section
- [ ] Add surname to the copyright line in `LICENSE`
- [ ] Publish `ui/index.html` to a static host for the live demo link

### 4. The agent itself

- [ ] Strands Agents SDK setup (AWS account, SDK install)
- [ ] Tools: `find_alternatives(salt, strength, form)`, `get_price(brand)`,  
  `check_quality_record(name)` — the last wraps `nuskha.db`
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

| gap                         | impact                                                                             |
| --------------------------- | ---------------------------------------------------------------------------------- |
| 2025-07+ NSQ not parsed     | Tier 1 blind to the last 13 months — the window Chhindwara-style events fall in    |
| Recent PDFs are **mirrors** | provenance recorded + hashed; resolve the CDSCO primary or re-host before shipping |
| WHO extraction incomplete   | 11/15 yield products, 4/15 manufacturers; N°5/2025 misses ReLife                   |
| Bans / prohibitions class   | third regulatory class, unbuilt                                                    |
| 16 pre-2025 NSQ files       | "spurious"/older formats, different table shape, yield nothing                     |
| Manufacturer normalisation  | lossy by design — retrieval only, never display                                    |

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
9. The July-2025 layout needs the **cell rects**, not `find_tables()`. Each record is one
   row of ten non-overlapping cell rectangles — group `page.rects` by identical vertical
   extent, sort by x, crop each cell. Cropping cells from the *fragmented tables* instead
   duplicates text, because those bboxes overlap.
10. A source column called "Alert Month" collides with the numeric `alert_month` metadata
    field and silently overwrites it. Renamed `alert_period`.
