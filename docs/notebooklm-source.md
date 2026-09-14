# NotebookLM source — Nuskha

Paste everything below the line into NotebookLM as a source, then generate the video overview.
**After it generates, check every figure against the "Numbers that must not change" table at
the end.** NotebookLM invented prices, a batch number and lab results on a previous attempt.

---

# Nuskha — what is on your prescription, and what it should cost

## The problem

On 30 September 2025, the World Health Organization identified a cluster of child fatalities
in India. On 8 October 2025, India's drug regulator confirmed diethylene glycol — an industrial
solvent — in three cough syrups. The public alert went out on 13 October 2025.

Two weeks passed between the first signal and the public warning. During those two weeks,
prescriptions were still being filled. Reporting put the death toll between fourteen and
twenty-four children, all of them under five, in Chhindwara district, Madhya Pradesh.

The information was public the whole time. Nobody holding a prescription could reach it.

## Who it is for

Anyone holding an Indian prescription: a parent, a patient, a caregiver.

Two things are true about that piece of paper. The brand prescribed is often several times the
price of an identical composition, because hospitals and pharmacies have commercial
arrangements. And the batches that failed laboratory testing are already on a public government
list — a list no patient has ever seen.

## What Nuskha does

Nuskha takes the medicine composition printed on the prescription — the salt, not the brand —
and answers two questions using official Indian government data:

1. What is this medicine legally allowed to cost?
2. Is this batch on a regulator's failure list?

It joins four official sources that have never been joined before:

- **NPPA ceiling prices** — the legally binding maximum under the Drugs and Prices Control
  Order. Charging above the ceiling for a scheduled formulation is illegal.
- **Jan Aushadhi (PMBJP) generic prices** — what the government's own generic version costs.
- **CDSCO NSQ alerts** — batches that failed laboratory testing. 3,591 records covering April
  2024 to July 2026.
- **WHO Medical Product Alerts** — recalls, suspensions and contamination. 15 alerts.

## The central finding

For atorvastatin 10mg, the NPPA legal ceiling is **4.94 rupees per tablet**, under notification
S.O. 5498 (E) of December 2024.

The government's own generic, sold through Jan Aushadhi stores, is **8.80 rupees for a pack of
ten tablets — 0.88 rupees per tablet**.

That is a **5.6 times** difference between the legal maximum and the government's own generic.
Both numbers are official. Same medicine.

## The case that motivated the project

For the cough syrup Coldrif, Nuskha returns two separate records from two separate authorities:

- **Tier 1 — India's drug regulator:** batch **SR-13**, reason recorded as **Adulterated**,
  October 2025, with a link to the original government document. This is a state laboratory
  finding.
- **Tier 2 — the World Health Organization:** Medical Product Alert No. 5/2025, dated
  **13 October 2025**, naming the products COLDRIF and Respifresh TR and three manufacturers.

A tool built only on the laboratory-failure list would have shown this parent nothing. That is
why there are two tiers.

## How it works

A Strands Agents agent with three tools — find alternatives, get the price, check the quality
record — over a local database built from the parsed government documents. The agent is
composition-first: a brand name cannot be resolved, because the comparison is only meaningful
between identical compositions.

## Why the design matters

Every claim carries its source and its authority level, and the levels never blend. A
regulator's record is labelled a regulator's record. A WHO publication is labelled a WHO
publication.

A batch finding is **batch-specific**. It means one batch failed testing on one date for the
stated reason. It is never a statement about the manufacturer, and Nuskha never says it is.

Absence of a record is **not** evidence of quality, because only sampled batches are tested.

And Nuskha **never** recommends substituting a medicine. Composition match is not proven
therapeutic equivalence — CDSCO does not require bioequivalence studies for domestically
marketed generics. It shows options. The prescriber decides.

---

# Numbers that must not change

If the generated video says anything different from this table, **do not use it.**

| Item | Correct value |
|---|---|
| NPPA legal ceiling, atorvastatin 10mg | **₹4.94 per tablet** |
| Notification | **S.O. 5498 (E), December 2024** |
| Jan Aushadhi generic price | **₹8.80 per 10 tablets = ₹0.88 per tablet** |
| Ratio between them | **5.6×** |
| NSQ batch records | **3,591** |
| NSQ record period | **April 2024 – July 2026** |
| WHO alerts | **15** |
| NPPA ceiling prices in the dataset | **349** |
| Jan Aushadhi prices in the dataset | **1,904** |
| Coldrif batch number | **SR-13** |
| Coldrif stated reason | **Adulterated** |
| Coldrif alert month | **October 2025** |
| WHO alert number and date | **No. 5/2025, 13 October 2025** |

## Things the video must NOT contain

The previous generated video invented all of these. None of them are true:

- ❌ A "₹120 per strip" ceiling price — the ceiling is ₹4.94 per tablet
- ❌ A "₹10 per strip" generic price — it is ₹0.88 per tablet
- ❌ A batch number "AT-9876" — that batch does not exist
- ❌ Any "Purity: PASS" or "Dissolution: PASS" result — Nuskha holds **no** purity data and
  reports **failures**, not passes
- ❌ The phrase "Verified Alternative" — Nuskha never recommends an alternative
- ❌ The phrase "Clean Lab Record" — absence of a record is not evidence of quality
- ❌ Any claim that Nuskha diagnoses, treats, or advises on medication

## Also do not claim

The agent is built on the Strands Agents SDK with Amazon Bedrock as the model provider, and the
code path is wired up. It should **not** be claimed that the video shows it running on Bedrock,
because that cannot be verified in the demo. Say the agent is built on Strands and leave it
there.
