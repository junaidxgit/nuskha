# Code review — 2026-09-12

Two-axis review (Standards / Spec) run with the `code-review` skill, fixed point
`4b825dc` (empty tree) → `HEAD` `9985af0`. The two axes ran as parallel sub-agents and are
reported **separately and unmerged** — a change can pass one axis and fail the other, and
merging them would let one mask the other.

No issue tracker and no coding-standards doc exist, so the Standards axis ran on the Fowler
smell baseline alone, and the Spec axis ran against `PLAN.md`, `STATUS.md`, `README.md` and
`docs/source-policy.md`.

---

## Standards

**(a) Documented standards:** none exist — no `CODING_STANDARDS.md`, `CONTRIBUTING.md`, or
convention section in README/STATUS. So no hard violations. Everything below is baseline
judgement.

**(b) Baseline smells**

**Duplicated Code** (dominant):
- `norm_key` + the `NOISE` regex copy-pasted verbatim — `pipeline/build_db.py:37-56` and
  `nuskha/queries.py:27-64`. Same for the LIKE builder: `like_where` (`build_db.py:223-231`)
  vs `_like` (`queries.py:93-99`).
- `norm()` (letter-spacing rejoin) duplicated — `parse_nsq.py:44-71` vs `parse_nsq_v2.py:76-93`.
- `to_ym` + `MMYYYY`/`MONYY`/`MONTHS` duplicated — `parse_nsq.py:102-116` vs
  `parse_nsq_v2.py:96-109`.
- `get()` + `SSL_CTX` + `UA` repeated in all five fetchers. Extract one `http.py`.

**Shotgun Surgery / Divergent Change** — the "compare prices across sources" rule is
implemented twice, independently: `build_db.price` (`build_db.py:350-392`) and
`queries.get_price` (`queries.py:230-245`). The unit-mismatch fix had to land in *both*, and
they can drift. Likewise two unconnected unit classifiers: `KIND_PATTERNS`/`unit_kind`
(`build_db.py:289-311`) and `STRENGTH`/`strengths_of` (`queries.py:36-80`).

**Primitive Obsession + Data Clumps:** price is a bare `float` and unit a bare `str`, so
`(qty, kind)` is re-derived at every call site. `queries.py:232` reaches into the ETL script
(`from pipeline.build_db import parse_unit`) — a layering inversion that makes the drift
worse. A shared `units.py` would gather what changes together.

*Not a smell:* `nuskha/tools.py` looks like Middle Man, but thin delegation is the required
`@tool` contract.

**Correctness spotted in passing (outside this axis, same class as bugs already fixed):**
- `fetch_janaushadhi.py:134-145` computes `uniq` ("dedupe on drug code") then writes `rows`,
  not `uniq` — **the dedupe is dead**, duplicate drug codes reach the DB.
- `strengths_of` (`queries.py:78`) maps `gm`→`g` but never `mg`↔`g`, so `1000 mg` ≠ `1 g`.
- `KIND_PATTERNS` (`build_db.py:289-296`) is first-match-wins and order-sensitive.

---

## Spec

### (a) Missing or partial

- **`form` is absent from the tools.** PLAN.md Day 2 specifies
  `find_alternatives(salt, strength, form)`; `tools.py:25,48` expose only `(salt, strength)`.
  A syrup query can therefore match tablet prices — contradicting `data-sources.md` §6.
- **No web UI** (PLAN.md Day 2). README.md:9 admits this.
- **No architecture diagram** — a required submission item (PLAN.md Day 3).
- **Banned-drugs list not built** — `source-policy.md` lists it under Tier 1; the class table
  marks it "not built".
- **Guardrail 1 not honoured:** *"Show the batch number, alert month, exact stated reason, and
  a link to the source PDF."* `cli.py:85-91` prints batch and reason but **no PDF link** — only
  `source_file`, a local filename.

### (b) Scope creep

Minor: `mock_model.py` and the `report`/`json`/`ask` subcommands exceed the spec, but are
documented scaffolding. Nothing harmful.

### (c) Implemented but wrong

- **Guardrail 5 / source-policy breach.** *"Government data only… authorised use of all
  third-party data."* `fetch_nppa.py:44` scrapes **thehealthmaster.com** (trade press = Tier 3)
  and `fetch_janaushadhi.py:48` downloads from **gpvdspharma.com**. All 349 NPPA and 1,904
  Jan Aushadhi rows carry `provenance="mirror"`, yet render as Tier 1 *"LEGAL MAXIMUM"* and
  *"GOVT GENERIC"*. This breaks the policy's own rule: *"A news report never renders as a
  regulatory finding."*
- **`notice_month` derived from a blog post title** (`fetch_nppa.py:205`) and then displayed as
  the S.O. date — a Tier 3 post date asserted as a Tier 1 notice date.
- **Guardrail 4 (persistent disclaimer) not honoured in the offline path.**
  `mock_model.py:150-184` drops the `note` field entirely, and the batch-specific caveat fires
  only when counts are zero (`:181`). `docs/agent.md` presents this as the offline agent run.
- **Guardrail 2 (never rank/editorialise) partially violated:** `price metformin 500mg` prints
  a **combination** product as *"LEGAL MAXIMUM"* with a *"13.8x"* ratio. STATUS.md's claim that
  "single ingredient now ranks first" holds only when a single-ingredient ceiling exists.
- **Authority mislabel:** `cli.py:81` prints `[TIER 1] CDSCO NSQ alerts` for the coldrif record
  whose source is a **state** lab PDF (`...States.pdf`, reason "Adulterated").

---

## Summary

**Standards: 5 findings** (4 duplication clusters, 1 layering/shotgun-surgery cluster);
worst = the cross-source price comparison implemented twice and already drifting.

**Spec: 9 findings**; worst = the price data is a Tier 3 mirror rendering as a Tier 1
regulatory claim, which contradicts the project's own binding source policy.

Not merged, not ranked across axes — by design.

## Recommended fix order

1. Surface `provenance` in the price output, and label the price source honestly (Spec c-1).
   This is the one that would embarrass the project under questioning.
2. Add the source link to `cli.py` output (Spec a-5).
3. Fix the `uniq` dead dedupe (Standards correctness).
4. Fix the state-lab authority mislabel (Spec c-5).
5. Add the disclaimer to `mock_model` output (Spec c-3).
6. Add the `form` parameter to the tools (Spec a-1).
7. Extract shared helpers — `http.py`, `units.py` (Standards).
