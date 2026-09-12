# Submission checklist

**Deadline: Sep 15, 05:30 IST** (Sep 14, 17:00 PT). Submit **Sep 14 evening**, not the last
hour.

Repo is ready to push: branch `main`, working tree clean, 10 commits dated Sep 10–12, author
set to `junaidxgit <officiallyunofficial007@gmail.com>`.

---

## 1. Push the repo

`gh` is not installed on this machine, so create the repo in the browser:

1. github.com → **New repository**
2. Name: `nuskha` (or your preference). **Public.** No README, no .gitignore, no licence —
   the repo already has all three.
3. Copy the URL, then:

```bash
cd "C:/Users/offic/WorkBuddy AI/2026-09-10-22-06-33"
git remote add origin https://github.com/<your-username>/nuskha.git
git push -u origin main
```

Git will prompt for credentials. Use a **personal access token** as the password
(GitHub → Settings → Developer settings → Personal access tokens), not your account password.

**Then, on the repo page:**
- [ ] Add a **description**: *"Composition-first medicine pricing and regulatory quality
      records for India. Built on Strands Agents."*
- [ ] Add **topics**: `strands-agents`, `aws`, `healthcare`, `india`, `agent`
- [ ] Confirm the **About** panel shows **MIT license**. If it doesn't, GitHub has not
      detected `LICENSE` — check the filename has no extension.
- [ ] Add your surname to the copyright line in `LICENSE` first.

## 2. AWS Builder ID

Required for submission, and **separate from an AWS account**. Sign up at `builder.aws.com`.

- [ ] Builder ID created, email verified

## 3. Bedrock (optional but lifts the score)

See `docs/aws-setup.md`. Two steps: credentials, then model access.

- [ ] `python -m nuskha.cli check-bedrock` reports **Ready**
- [ ] `python -m nuskha.cli ask "what should atorvastatin 10mg cost?"` returns a real answer

## 4. Live demo link (optional, scores higher)

`ui/index.html` is self-contained — no server, no build. Any static host works:

- [ ] GitHub Pages: Settings → Pages → deploy from `main`, `/docs` folder — move
      `ui/index.html` to `docs/index.html`, or point Pages at the root and rename
- [ ] Or drag the file onto netlify.com/drop
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
- [ ] AWS Builder ID
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
