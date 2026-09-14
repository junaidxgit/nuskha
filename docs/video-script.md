# Demo video — shooting script

**Target 4:00. Hard limit 5:00.** Must be public on YouTube or Vimeo. No camera needed —
screen recording plus voiceover. The rules require the pitch to cover (1) the problem,
(2) who it's for, (3) why it matters, so those are marked below.

Numbers in this script are real and verified. Say them as written; do not round them up.

---

## Before you record

Open these, in this order, so nothing is hunting mid-take:

1. Terminal, font size up two notches, at the project root
2. `ui/index.html` in a browser, full screen
3. `docs/architecture.svg` in a browser tab
4. Silence notifications. Close Slack, mail, everything.

Run these once so they are in shell history and the output is warm:

```bash
PY=python    # or your interpreter; `python -m nuskha.cli ...` works as-is
$PY -m nuskha.cli price atorvastatin 10mg
$PY -m nuskha.cli check coldrif
```

**Fallback if Bedrock misbehaves:** the deterministic commands need no AWS at all. The demo
below is built on them on purpose, so it cannot fail on stage.

---

## 0:00 – 0:35 · The problem

**On screen:** the terminal, empty. Or a plain title card: *"Two weeks."*

**Narration:**

> On 30 September 2025, the World Health Organization identified a cluster of child
> fatalities in India. On 8 October, India's drug regulator confirmed diethylene glycol —
> industrial solvent — in three cough syrups. The public alert went out on 13 October.
>
> Two weeks. During those two weeks, prescriptions were still being filled.
>
> Reporting put the death toll between fourteen and twenty-four children. All of them
> under five. In Chhindwara district, Madhya Pradesh.

*(Pause. Let it land.)*

---

## 0:35 – 0:55 · Who it's for, and why it matters

**On screen:** still the terminal.

**Narration:**

> This is for anyone holding an Indian prescription. A parent, a patient, a caregiver.
>
> Two things are true about that piece of paper. The brand prescribed is often several
> times the price of an identical composition, because hospitals and pharmacies have
> commercial arrangements. And the batches that failed testing are already on a public
> government list — a list no patient has ever seen.

---

## 0:55 – 2:20 · The demo

**On screen:** terminal. Type the first command live.

**Narration:**

> Nuskha. You type the salt written on the prescription — not a brand, because Indian
> prescriptions already name the salt.

```
$ python -m nuskha.cli price atorvastatin 10mg
```

**Narration, reading the output as it appears:**

> The legal maximum for atorvastatin 10mg is four rupees ninety-four a tablet. That is the
> NPPA ceiling price — under the Drugs and Prices Control Order, charging more is illegal.
>
> The government's own generic is eighty-eight paise a tablet.
>
> That is a **5.6 times** difference, and both numbers are official.

**On screen:** switch to the browser, `ui/index.html`.

**Narration:**

> The same thing in a browser. One input, the salt. Same figures.

*(Type `atorvastatin`, then `10mg`. Let the result card render.)*

**Narration:**

> Legal maximum on the left. Government generic on the right. Below it, the regulatory
> record.

**On screen:** back to terminal. This is the important one.

```
$ python -m nuskha.cli check coldrif
```

**Narration:**

> Now the part that matters. Coldrif — one of the three syrups.

*(Let the output render fully before speaking.)*

> Two separate records, from two separate authorities.
>
> Tier one, from India's drug regulator: the batch. Batch SR-13. The reason, in the
> regulator's own word: adulterated. October 2025. With a link to the original document.
>
> Tier two, from the World Health Organization: the international alert, naming all three
> products and all three manufacturers.
>
> **A tool built only on the laboratory-failure list would have shown this parent nothing.**
> That is why there are two tiers.

---

## 2:20 – 3:10 · How it works

**On screen:** `docs/architecture.svg`.

**Narration:**

> Four official sources. India's drug regulator for batch failures. The WHO for recalls and
> contamination. NPPA for the legally binding price ceiling. Jan Aushadhi for the
> government's generic price.
>
> Three thousand five hundred and ninety-one batch records, from January 2024 through July
> 2026. Fifteen WHO alerts. Three hundred and forty-nine ceiling prices. Nineteen hundred
> generic prices.
>
> On top of that, a Strands Agents agent with three tools. Find alternatives. Get the price.
> Check the quality record.

**On screen:** back to the terminal.

```
$ python -m nuskha.cli ask "what should atorvastatin 10mg cost?"
```

**Narration:**

> And the agent itself, running on Strands with Amazon Bedrock.

*(If Bedrock is not working, skip this shot and say instead: "the agent runs the same three
tools — here it is driven by a scripted model, which is how I test it without burning
credits." Then run the scripted-model one-liner.)*

---

## 3:10 – 3:50 · Why you can trust it

**On screen:** the terminal, showing the coldrif output again. Or the UI.

**Narration:**

> One design decision runs through everything, and it is the reason this is safe to ship.
>
> Every claim carries its source and its authority level, and the levels never blend. A
> regulator's record is labelled a regulator's record. A WHO publication is labelled a WHO
> publication.
>
> An NSQ finding is **batch-specific**. It means one batch failed testing on one date for
> the stated reason. It is not a statement about the company, and Nuskha never says it is.
> Absence of a record is not evidence of quality either, because only sampled batches are
> tested.
>
> And it never tells you to switch medication. It shows you options. Your prescriber
> decides.

---

## 3:50 – 4:05 · Close

**On screen:** the two figures, side by side.

**Narration:**

> Two weeks, between the first signal and a public warning. The information was always
> public. Nobody holding a prescription could reach it.
>
> Four rupees ninety-four, against eighty-eight paise. Same medicine. Both official.
>
> That is Nuskha.

---

## Things that will bite you

- **Do not say "a few months ago"** about Chhindwara. It was September–October 2025, about a
  year before the deadline. A judge who knows the case will notice.
- **Do not quote a single death toll as fact.** It was reported between 14 and 24. Say
  "reported between", or pick one and attribute it.
- **Do not call any manufacturer unsafe.** Say "the regulator recorded this batch". That
  distinction is the product.
- **Do not round 5.6× up to 6×.** The number is checkable.
- **Say "composition match is not proven therapeutic equivalence"** at least once. It is the
  honest caveat and it strengthens rather than weakens the pitch.
- **Keep the provenance caveat on screen.** The price data comes from mirrors, not the
  issuing bodies. It is printed in the output — don't cut around it.

---

## If a judge pushes back

**"Isn't this just Pharma Sahi Daam?"**
NPPA's own app gives you a ceiling price. So do firstscanit and sahidawa.in. That half is
commoditised and you should concede it immediately — then draw the line: those tools give you
a *number*. Nuskha gives you the number **and** whether that batch is on the regulator's
failure list. No existing tool joins the price record to the quality record, and that join is
the product.

**"Where does the quality data come from?"**
Two tiers, kept separate. Tier 1 is CDSCO's NSQ alerts — batches that failed laboratory
testing. Tier 2 is WHO Medical Product Alerts — recalls, suspensions, contamination. They are
never merged, because they carry different authority.

**"How do you know the parsing is right?"**
The monthly record counts were cross-checked against totals published independently of this
work. **Seven of eight months match exactly** — 2025-07: 143, 2025-08: 94, 2025-10: 211,
2025-11: 205, 2025-12: 167, 2026-06: 159, 2026-07: 239. The one difference, May 2026 at 159
against 157, is the two spurious-drug records in that file, which are not NSQ samples.

**"Isn't this defamatory to the manufacturers?"**
This is the question to be ready for, and the answer is the design. An NSQ finding is
batch-specific — one batch, one date, one stated reason. The product never says a company is
unsafe; it mirrors the regulator's record with the batch number, the alert month, the stated
reason, and a link to the source PDF. It also states plainly that absence from the list is not
evidence of quality, because only sampled batches are tested.

**"What if the price data is wrong?"**
It is a mirror, not the issuing body, and the output says so on every answer. That is a
deliberate tradeoff, and the fix is to resolve the primary source — which is on the list.

**"Does it work without AWS?"**
Yes. The deterministic commands need no credentials at all, which is why the demo uses them.
The agent adds natural-language routing over the same three tools; it is not load-bearing for
correctness.

## Recording

- Screen recording only. OBS, or Windows Game Bar (Win+G). 1080p is plenty.
- Record narration **separately** and lay it over. Live narration over a terminal always
  sounds like you're reading.
- Two takes minimum. One slow, one normal. Use the slow one.
- If you fumble a line, pause three seconds and redo the sentence — don't restart the take.
- Trim the dead air at the start and end. The first three seconds decide whether a judge
  keeps watching.
