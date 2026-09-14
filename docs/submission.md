# Submission checklist

**Deadline: Sep 15, 05:30 IST** (Sep 14, 17:00 PT). Submit **Sep 14 evening**, not the last
hour.

**Repo is live: https://github.com/junaidxgit/nuskha** — public, pushed from here with the
portable `gh` in `.tools/` (the keyring credential became readable on the second attempt).

---

## 1. Push the repo — DONE

- [x] Pushed. `main` tracks `origin/main`, in sync.
- [x] **Description** set: "What is on your prescription, and what it should cost: NPPA price
      ceiling + Janaushadhi generic floor + CDSCO batch quality record, joined."
- [x] **Topics** set: agent, aws, cdsco, india, janaushadhi, medicine, nppa, open-data,
      public-health, price-transparency, strands-agents, healthcare
- [x] **MIT license** confirmed detected by GitHub (`license.spdx_id: MIT` via API).
- [x] Architecture diagram embedded in the README top; verified GitHub-safe.
- [x] **Copyright line** reads "Copyright (c) 2026 Junaid"; GitHub still reports MIT.

## 2. AWS Builder ID — DONE

Required for submission, and **separate from an AWS account**.

- [x] Builder Center alias: **@junxaws**
- [x] Builder ID / signup email: **mohamedjunaidm6@gmail.com**

Paste the **email** into Devpost's "AWS Builder ID" field -- that is the actual identifier.
`@junxaws` is the public Builder Center alias, which is a different thing.

## 3. Bedrock — BLOCKED at the account level, not fixable from here

**Status: not achievable on this AWS account.** Ruled out by testing, in order:
credentials (STS resolves, root user), region (5 tried), model id (7 tried,
**including Amazon Nova**, which needs no Anthropic approval and fails identically),
account plan (**PAID**, ACTIVE, $120 credits), Bedrock quotas (non-zero), spend limits
(none configured), and the new-AWS-experience SCPs (which explicitly allow `bedrock:*`).

Control-plane calls succeed (`list_foundation_models` returns 75 models) while **every**
inference call returns `ValidationException: Operation not allowed`. Submitting the
Anthropic first-time use-case form returns *"Your account is not authorized to perform this
action. Please create a support case."*

That is an account-authorisation hold. See `docs/aws-setup.md` for the full diagnosis and
`tools/bedrock_probe.py` to re-check.

- [ ] ~~`check-bedrock` reports Ready~~ — blocked on AWS, see above
- [x] A **support case** is the only remaining path; turnaround is unpredictable
- [x] **The agent is Bedrock-ready regardless**: `ask` without `--offline` builds a real
      `BedrockModel` and reaches the API. It fails on authorisation, not on code.
- [x] **A live model is available anyway** via `ask --ollama` (local Ollama, real tool
      calls, no AWS at all)

**This does not block submission.** The scoring criterion is a working, non-trivial Strands
implementation, and that is demonstrable on three paths: `--offline` (scripted model),
`--ollama` (live local model), and the Bedrock code path itself.

## 4. Live demo link — DONE

**https://junaidxgit.github.io/nuskha/** — GitHub Pages, served from `/docs` on `main`.
`ui/build_ui.py` regenerates both `ui/index.html` and `docs/index.html` together.

- [x] GitHub Pages enabled via API, source `main` / `/docs`
- [x] Both HTML copies are tracked in git (the blanket `*.html` gitignore rule had been
      silently excluding them — fixed with explicit `!` exceptions)
- [x] **Verified serving**: HTTP 200, 1,602,947 bytes, correct title, and the embedded
      data (atorvastatin / coldrif / SR-13) all present in the fetched HTML
- [ ] Paste the URL into the submission

## 5. Demo video — required, max 5 minutes

Must be public on YouTube or Vimeo, and must cover (1) the problem, (2) who it's for,
(3) why it matters. Slides, screen recording and voiceover are fine; no camera needed.

- [ ] Recorded, under 5 minutes
- [ ] Uploaded, set **public** (not unlisted — the rules say public)
- [ ] Link works in an incognito window

## 6. Submit

- [ ] Text description written
- [ ] Public repo URL
- [ ] Architecture diagram: `docs/architecture.svg`
- [ ] Video URL
- [x] AWS Builder ID: **mohamedjunaidm6@gmail.com** (alias `@junxaws`)
- [ ] Optional live demo link
- [ ] Submitted **Sep 14 evening**

## 7. Optional bonus

- [ ] Post the build story on `builder.aws.com` with **"Agents for Humans"** in the title.
      0.2 points each, max 0.6 — but **only counts if you reach Stage Two**.

---

## What is verified working

```
3,591 NSQ records      2024-01 → 2026-07, validated against independently reported monthly totals
15 WHO alerts          2024 → 2026, structured
349 NPPA ceilings      23 notifications
1,904 Jan Aushadhi     generic prices
```

- `--check coldrif` returns **both tiers**: the CDSCO batch record (batch SR-13, reason
  "Adulterated", Oct 2025) and WHO N°5/2025
- `--price atorvastatin 10mg` → ceiling ₹4.94, floor ₹0.88, **5.6×**
- The Strands agent loop runs end to end, verified trace
  `user → assistant(toolUse ×2) → user(toolResult ×2) → assistant(text)`
- The UI reproduces the CLI's answers exactly (verified by running the page's own JS in Node)

## Do not

- Do not scrape commercial pharmacies — breaches their terms and the hackathon's
  authorised-data rule. Government sources only.
- Do not claim a manufacturer is unsafe. An NSQ finding is batch-specific.
- Do not tell a user to switch medication. Show options, defer to their prescriber.
- Do not remove the provenance caveat. The price data is a mirror, not the issuing body.
