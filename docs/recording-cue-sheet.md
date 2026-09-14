# Recording cue sheet — do this now

**Deadline 05:30 IST.** Target 4:00, hard limit 5:00. Slides + screen recording + voiceover are
all explicitly allowed by the rules. No camera needed.

Everything below has been verified: every number, every command, every claim. Nothing on screen
will contradict the voiceover.

---

## Step 0 — open these, in this order (2 min)

1. **`docs/demo-slides.html`** in Chrome/Edge, full screen. Press **F** to enter fullscreen.
   Arrow keys move between the 8 slides.
2. A **terminal** at the project root, font size up two notches:
   ```
   cd "C:\Users\offic\WorkBuddy AI\2026-09-10-22-06-33"
   ```
3. **`ui/index.html`** in a browser tab, full screen.
4. **`docs/architecture.svg`** in another tab.
5. Silence notifications. Close mail, Slack, everything.

Warm the shell so nothing is slow on camera:

```bash
PY="C:/Users/offic/.workbuddy-ai/binaries/python/envs/default/Scripts/python.exe"
$PY -m nuskha.cli price atorvastatin 10mg
$PY -m nuskha.cli check coldrif
```

---

## Step 1 — record the screen (Win+G, 5 min)

Record the **screen only, no microphone**. You'll add narration separately — live narration over
a terminal always sounds like reading.

Work through these shots. Rough timings assume the narration in Step 2.

| Shot | On screen | How long |
|---|---|---|
| A | Slide 1 (title) | 12s |
| B | Slide 2 — "Two weeks." | 25s |
| C | Slide 3 — who it's for | 20s |
| D | Slide 4 → **switch to terminal** | 5s |
| E | Terminal: run `price atorvastatin 10mg`, let it finish | 35s |
| F | Switch to `ui/index.html`, type `atorvastatin` then `10mg`, let the card render | 25s |
| G | Back to terminal: run `check coldrif`, let it finish | 40s |
| H | Slide 6 — how it works (or `docs/architecture.svg`) | 30s |
| I | Slide 7 — why you can trust it | 25s |
| J | Slide 8 — the two figures. Hold. Stop recording. | 20s |

**Slide 5 is a cue card, not a slide to show** — it tells you to switch to the terminal. Skip
past it on camera.

If you fumble a shot, pause three seconds and redo just that shot. Don't restart the take.

---

## Step 2 — record the narration (5 min)

Read this over the footage. Pauses matter; they're marked.

### Over slides 1–3 (0:00–1:00)

> On 30 September 2025, the World Health Organization identified a cluster of child fatalities
> in India. On 8 October, India's drug regulator confirmed diethylene glycol — industrial
> solvent — in three cough syrups. The public alert went out on 13 October.
>
> *(pause)*
>
> Two weeks. During those two weeks, prescriptions were still being filled.
>
> Reporting put the death toll between fourteen and twenty-four children. All of them under
> five. In Chhindwara district, Madhya Pradesh.
>
> *(pause)*
>
> This is for anyone holding an Indian prescription. A parent, a patient, a caregiver.
>
> Two things are true about that piece of paper. The brand prescribed is often several times
> the price of an identical composition, because hospitals and pharmacies have commercial
> arrangements. And the batches that failed testing are already on a public government list —
> a list no patient has ever seen.

### Over shot E — the price (1:00–1:35)

> Nuskha. You type the salt written on the prescription — not a brand, because Indian
> prescriptions already name the salt.
>
> The legal maximum for atorvastatin 10mg is four rupees ninety-four a tablet. That is the
> NPPA ceiling price — under the Drugs and Prices Control Order, charging more is illegal.
>
> The government's own generic is eighty-eight paise a tablet.
>
> That is a **5.6 times** difference, and both numbers are official.

### Over shot F — the browser (1:35–2:00)

> The same thing in a browser. One input, the salt. Same figures.
>
> Legal maximum on the left. Government generic on the right. Below it, the regulatory record.

### Over shot G — Coldrif (2:00–2:40)

> Now the part that matters. Coldrif — one of the three syrups.
>
> *(let the output render fully before speaking)*
>
> Two separate records, from two separate authorities.
>
> Tier one, from India's drug regulator: the batch. Batch SR-13. The reason, in the regulator's
> own word: adulterated. October 2025. With a link to the original document.
>
> Tier two, from the World Health Organization: the international alert, naming all three
> products and all three manufacturers.
>
> **A tool built only on the laboratory-failure list would have shown this parent nothing.**
> That is why there are two tiers.

### Over slide 6 — how it works (2:40–3:10)

> Four official sources. India's drug regulator for batch failures. The WHO for recalls and
> contamination. NPPA for the legally binding price ceiling. Jan Aushadhi for the government's
> generic price.
>
> Three thousand five hundred and ninety-one batch records, from April 2024 through July
> 2026. Fifteen WHO alerts. Three hundred and forty-nine ceiling prices. One thousand nine
> hundred and four generic prices.
>
> On top of that, a Strands Agents agent with three tools. Find alternatives. Get the price.
> Check the quality record.

### Over slide 7 — trust (3:10–3:40)

> One design decision runs through everything, and it is the reason this is safe to ship.
>
> Every claim carries its source and its authority level, and the levels never blend. A
> regulator's record is labelled a regulator's record. A WHO publication is labelled a WHO
> publication.
>
> An NSQ finding is batch-specific. It means one batch failed testing on one date for the
> stated reason. It is not a statement about the company, and Nuskha never says it is.
> Absence of a record is not evidence of quality either, because only sampled batches are
> tested.
>
> And it never tells you to switch medication. It shows you options. Your prescriber decides.

### Over slide 8 — close (3:40–4:00)

> Two weeks, between the first signal and a public warning. The information was always public.
> Nobody holding a prescription could reach it.
>
> Four rupees ninety-four, against eighty-eight paise. Same medicine. Both official.
>
> That is Nuskha.

---

## Step 3 — assemble and upload (10 min)

- Trim dead air at the start and end. **The first three seconds decide whether a judge keeps
  watching.**
- Keep it under 5:00. Aim for ~4:00.
- Upload to YouTube. Set it **public** — the rules only require the *repo* to be public, but
  judges must be able to watch, so public removes all risk.
- Check the link in an incognito window.

---

## Things that will bite you

- **Do not say "a few months ago"** about Chhindwara. It was Sep–Oct 2025.
- **Do not quote a single death toll as fact.** It was reported between 14 and 24.
- **Do not call any manufacturer unsafe.** Say "the regulator recorded this batch".
- **Do not round 5.6× up to 6×.** It's checkable.
- **Keep the provenance caveat on screen.** The price data comes from mirrors, not the issuing
  bodies. It's printed in the output — don't cut around it.
- **Do not claim the agent is running on Bedrock.** It isn't — this AWS account isn't
  authorised for Bedrock model invocation. If asked, say the agent is built on Strands with
  `BedrockModel` and the code path is wired up, but the account can't invoke yet, so the demo
  uses the same loop with a scripted model. Say it plainly; claiming otherwise would be
  dishonest and checkable.
