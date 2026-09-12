# Plan — Agents for Humans submission

**Deadline: Sep 15, 05:30 IST** (Sep 14, 17:00 PT). Submit **Sep 14 evening**, not the
last hour. Today is Sep 11.

---

## Do tonight (20 minutes, then sleep)

These are the items that disqualify you if forgotten, and they cost almost nothing now.

- [ ] **AWS Builder ID** — sign up at `builder.aws.com`. Required for submission.
- [ ] **Request the $50 AWS credits.** Form is on the hackathon Resources tab.
      **Hard deadline Sep 12, 00:30 IST** — roughly 24 hours from now. Credits expire Oct 31.
- [ ] **`git init` and commit tonight's pipeline.** Hackathon rules require the project be
      built *during* the submission window (Aug 10 – Sep 14). Dated commits are your
      evidence. Commit early, commit often.
- [ ] **Create the public GitHub repo** and push. MIT license is already in the tree —
      it must be *detectable in the repo's About section*, which means GitHub has to
      recognise the LICENSE file. Add a description and topics while you're there.

## Day 1 — Sep 11

- [ ] **Close the CDSCO recency gap.** Highest-value hour available. The current endpoint's
      newest NSQ alert is June 2025; alerts exist through 2026. Start with the Aug-2025 CDSCO
      public notice about a "new dedicated link" for NSQ alerts.
- [ ] **Price layer.** NPPA ceiling prices (907 scheduled formulations) + Jan Aushadhi MRP.
      Jan Aushadhi needs ~1 hour of API reverse-engineering; the fallback is their official
      MRP PDF.
- [ ] **WHO structured extraction.** Parse each alert into product names, manufacturer names,
      batches, and dates, so the agent can say *which* product matched rather than just
      "this document mentions your drug".

## Day 2 — Sep 12

- [ ] **Strands agent.** Tools: `find_alternatives(salt, strength, form)`,
      `get_price(brand)`, `check_quality_record(name)`. The last one wraps `nuskha.db`.
- [ ] **Web UI.** One input, one result card. Tiers rendered as visibly separate blocks —
      Tier 1 "recorded by CDSCO", Tier 2 "published by WHO". This is the design decision
      judges will notice.
- [ ] **Deploy.** Amazon Bedrock AgentCore strengthens Technical Implementation. A live demo
      link also scores higher.

## Day 3 — Sep 13

- [ ] **Architecture diagram** (required submission item).
- [ ] **README final pass** — setup instructions a stranger can follow.
- [ ] **Record the demo video**, max 5 minutes, public on YouTube or Vimeo. Must cover
      (1) the problem, (2) who it's for, (3) why it matters. Slides + screen recording +
      voiceover are fine; no camera needed.
- [ ] **Write the text description.**

## Day 4 — Sep 14

- [ ] **Submit in the morning.** Leave the evening as buffer, not as the deadline.
- [ ] Optional bonus: post the build story on builder.aws.com with "Agents for Humans" in the
      title. 0.2 points each, max 0.6 — but **only counts if you reach Stage Two**.

---

## The video script, roughly

Open on the number, not the product.

> "On 30 September 2025, the WHO identified a cluster of child fatalities in India.
> On 8 October, CDSCO confirmed diethylene glycol in three cough syrups. The public
> alert went out on 13 October. Two weeks. During those two weeks, prescriptions were
> still being filled."

Then the demo: type a salt, show the alternatives and the price ceiling, then show the
alert. Use `coldrif` — it returns **zero NSQ records and one WHO alert**, which is the
whole argument in a single screen: the lab-failure list alone would have shown a parent
nothing.

Close on the tiering. Every claim on screen carries its source and its authority level,
and the two are never blended. That's the part that makes this trustworthy rather than
just useful.

## What to say if a judge asks about the risk

Be direct: an NSQ finding is batch-specific, so calling a company "adulterated" would be
defamation. The product never editorialises — it mirrors the government record with batch
number, date, stated reason, and a link to the source PDF. It also states plainly that
absence from the list is not evidence of quality, and that composition match is not proven
therapeutic equivalence. Those constraints are why the thing is defensible.

---

## Non-negotiables

- **New project only.** Built inside Aug 10 – Sep 14. Disclose any pre-existing code.
- **Public repo** with MIT or Apache visible in About, plus a README.
- **Architecture diagram** and a **≤5 min public video**. Both are required, not optional.
- **Government data only.** No scraping commercial pharmacies — their terms forbid it and
  the hackathon requires authorised use of third-party data.
- **Never tell a user to switch medication.** Show options, defer to their doctor.
