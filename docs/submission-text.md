# Devpost submission — text description

Copy the block below into the "Text description" field. The rules ask for what the project
does, who it's for, and how it works. Every figure here is verified against the repo.

---

## Nuskha — what is on your prescription, and what it should cost

**What it does.** Nuskha takes the medicine *composition* printed on an Indian prescription —
the salt, not the brand — and answers two questions with official data: what the medicine is
legally allowed to cost, and whether the specific batch is on a regulator's failure list.

It joins four Indian government sources that have never been joined:

- **NPPA ceiling prices** — the legally binding maximum under the Drugs and Prices Control
  Order. Charging above it is illegal.
- **Jan Aushadhi (PMBJP) generic prices** — what the government's own generic costs.
- **CDSCO NSQ alerts** — batches that failed laboratory testing, 3,591 records from April
  2024 to July 2026.
- **WHO Medical Product Alerts** — recalls, suspensions and contamination, 15 alerts.

For atorvastatin 10mg the result is stark: a legal ceiling of **₹4.94 per tablet** against a
government generic at **₹0.88 per tablet** — a **5.6× gap**, both figures official.

**Who it's for.** Anyone holding an Indian prescription: a parent, a patient, a caregiver.
Two things are true about that piece of paper. The brand prescribed is often several times the
price of an identical composition, because hospitals and pharmacies have commercial
arrangements. And the batches that failed testing are already on a public government list — a
list no patient has ever seen. Nuskha reaches both facts in one query.

**How it works.** A Strands Agents agent with three tools — `find_alternatives`, `get_price`,
`check_quality_record` — over a local SQLite database built from the parsed source documents.
The agent is deliberately composition-first: a brand name cannot be resolved, because the
comparison is only meaningful between identical compositions.

**Why the design matters.** Every claim carries its source and its authority level, and the
levels never blend. A regulator's record is labelled a regulator's record; a WHO publication is
labelled a WHO publication. An NSQ finding is **batch-specific** — one batch, one date, one
stated reason — and is never a statement about the manufacturer. Absence of a record is
explicitly *not* evidence of quality, because only sampled batches are tested. And the tool
**never** recommends substituting a medicine: composition match is not proven therapeutic
equivalence, since CDSCO does not require bioequivalence studies for domestically marketed
generics. It shows options; the prescriber decides.

**Stack.** Python, the Strands Agents SDK, Amazon Bedrock as the model provider, and a
deterministic query layer that runs with no model and no credentials at all.

**Links.** Code: https://github.com/junaidxgit/nuskha — Live demo:
https://junaidxgit.github.io/nuskha/

---

## Shorter version (if the field is tight)

Nuskha takes the composition written on an Indian prescription and answers two questions with
official data: what the medicine is legally allowed to cost, and whether that batch is on a
regulator's failure list.

It joins four government sources that have never been joined — NPPA ceiling prices, Jan
Aushadhi generic prices, CDSCO batch-failure alerts (3,591 records) and WHO product alerts (15).
For atorvastatin 10mg: a legal ceiling of ₹4.94 per tablet against a government generic at
₹0.88 — a 5.6× gap, both official.

It's for anyone holding a prescription: a parent, a patient, a caregiver. The brand prescribed
is often several times the price of an identical composition, and the batches that failed
testing are already on a public list no patient has ever seen.

Built as a Strands Agents agent with three tools over a local database. Every claim carries its
source and its authority level, and the levels never blend. Batch findings are never a
statement about a manufacturer, absence of a record is not evidence of quality, and the tool
never recommends substituting a medicine — it shows options and tells you to ask your
prescriber.

Code: https://github.com/junaidxgit/nuskha · Live demo: https://junaidxgit.github.io/nuskha/

---

## Other fields

| Field | Value |
|---|---|
| Public repo URL | `https://github.com/junaidxgit/nuskha` |
| Architecture diagram | `docs/architecture.svg` in the repo (also embedded at the top of the README) |
| Live demo link (optional) | `https://junaidxgit.github.io/nuskha/` |
| AWS Builder ID | `mohamedjunaidm6@gmail.com` (alias `@junxaws`) |
| Demo video | **needs a URL** — see `docs/recording-cue-sheet.md` |

**Do not claim the agent runs on Bedrock in the submission.** It is built on Strands with
`BedrockModel` and the code path is wired up and reaches the API, but this AWS account is not
authorised for Bedrock model invocation, so the demo runs the same loop with a scripted model.
Say that plainly if asked; claiming otherwise is checkable and false.
