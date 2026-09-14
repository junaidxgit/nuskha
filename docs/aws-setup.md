# Running the agent against Amazon Bedrock

Strands ships Bedrock as its default provider, so this is the only setup needed to run the
**real** agent with a real model. Everything else in the project works without it.

Check current state with:

```bash
python tools/bedrock_probe.py --region ap-south-1   # thorough: which route is
                                                    # live, and can it actually infer?
python -m nuskha.cli check-bedrock                  # quick: are credentials present?
```

`tools/bedrock_probe.py` is the one to trust. It separates the failures that look alike
but need different fixes: credentials absent, credentials malformed, the login session
expired, the account still being verified, and model access not granted. It makes one tiny
inference call and never prints the secret.

`check-bedrock` only looks for the *presence* of credentials, and only understands a
`[default]` section — it does not see `aws login` profiles. Use the probe.

Two things have to be true. The probe checks them in order, because each failure has a
different fix.

---

## 1. Credentials — pick one of three routes

### Route A — an `aws login` session (what this machine uses)

The **new AWS experience** authenticates with a browser flow rather than access keys. This
is set up and working here under the profile **`junxaws`**:

```bash
aws login --region ap-south-1 --profile junxaws
aws sts get-caller-identity --profile junxaws
```

Two things bite here, both learned the hard way:

- **`botocore[crt]` is required.** A login session is read through a DPoP-based provider.
  Without the CRT extra, boto3 (and therefore Strands) fails with
  `MissingDependencyException: Using the login credential provider requires an additional
  dependency`. It is in `requirements.txt`; if it is missing: `pip install "botocore[crt]"`.
- **A token file on disk does not mean the session is valid.** `~/.aws/login/cache/*.json`
  persists after the console session ends, and the refresh is then rejected with
  `CreateOAuth2Token: The provided authorization grant is invalid, expired, revoked, or
  malformed`. Credentials last 12 hours and refresh for 90 days — but only while the
  underlying console session lives. Re-run `aws login` when this appears.

`aws login` writes `login_session = arn:...` into `~/.aws/config` and leaves
`~/.aws/credentials` **empty**. Anything that only reads the credentials file will
incorrectly report "not configured".

### Route B — a Bedrock API key

Bedrock also issues its own keys, used as a bearer token instead of AWS SigV4
credentials. No IAM user to create.

Bedrock console → left nav **API keys** → either tab:

- **Short-term** — `Generate short-term API keys`. Expires with your console session
  (max 12 hours). This is the recommended type.
- **Long-term** — `Generate long-term API keys`, choose an expiry. AWS labels these
  *for exploration only*, which is exactly this use.

Then set it in the shell:

```bash
export AWS_BEARER_TOKEN_BEDROCK="<key>"      # macOS/Linux/bash
setx AWS_BEARER_TOKEN_BEDROCK "<key>"        # Windows; needs a NEW shell
```

`botocore` reads that variable automatically for the `bedrock-runtime` client, so
**Strands picks it up with no code change**. Verified on this machine.

The variable takes precedence over the other routes, so unset it if you want to use
`junxaws` instead. Watch the expiry: a long-term key still dies on its date, and a
short-term one dies when your console session ends.

### Route C — IAM access keys

Create `C:\Users\offic\.aws\credentials`:

```ini
[default]
aws_access_key_id = YOUR_KEY_ID
aws_secret_access_key = YOUR_SECRET
```

and `C:\Users\offic\.aws\config`:

```ini
[default]
region = us-west-2
```

Keys come from the AWS console: **IAM → Users → your user → Security credentials →
Create access key**. Use a dedicated user rather than the root account.

Environment-variable form (per-shell, disappears when the terminal closes):

```bash
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_DEFAULT_REGION=us-west-2
```

Never commit any of these. `~/.aws/` is outside the repo, and `.gitignore` already
excludes `.env`.

## 2. Model access — the actual blocker on this account

**The Bedrock "Model access" page has been retired.** Serverless foundation models are now
enabled automatically, per region, on first invocation. So the old instruction
("Model access → Modify → tick Claude → submit") **no longer applies** — that page is gone.

The console page now states:

> Note that for Anthropic models, first-time users may need to submit use case details
> before they can access the model. For models served from AWS Marketplace, a user with
> AWS Marketplace permissions must invoke the model once to enable it account-wide for all
> users.

**That is this account's blocker.** The API reports it as:

```
ValidationException: Operation not allowed
```

and, if you try to accept the model agreement programmatically:

```
AccessDeniedException: You have not filled out the request form.
Fill out the form before getting access.
```

The "request form" is the **Anthropic first-time use case details form**.

### The fix — console, one time

1. Bedrock console → **Model catalog**
2. Select **Anthropic Claude Sonnet 4.x**
3. **Open in playground**
4. Submit the **use case details** when prompted
5. Re-run `python tools/bedrock_probe.py --region <region> --profile junxaws`

Anthropic models are Marketplace-served, so the principal doing this needs Marketplace
permissions — root/admin has them; a restricted IAM user would not.

### Three look-alike errors, three different fixes

| Error | Meaning | Fix |
|---|---|---|
| `... your account is currently being verified` | New account, transient | Wait (AWS says <2h) |
| `Operation not allowed` | Model not granted yet | Submit the Anthropic use-case form |
| `AccessDeniedException` (plain) | Often the same gate, older wording | Same as above |

**Ruled out by testing on this account** — do not re-investigate these:

- **Region:** 5 tried (ap-south-1, ap-south-2, us-east-1, us-west-2, eu-central-1).
  Identical failure. Note `ap-south-1` lists **75 models (19 Claude)** and `ap-south-2`
  lists 21 (12 Claude) — so Claude *is* offered in both Indian regions.
- **Model id:** 7 tried, including `amazon.nova-micro-v1:0` and `amazon.nova-lite-v1:0`.
  **Nova needs no use-case form and fails identically**, which is why this looked like
  account gating rather than an Anthropic-specific form.
- **API surface:** `Converse`, `ConverseStream` and `InvokeModel` all fail.
- **Credentials:** STS resolves; control plane works.
- **SCPs:** the new-AWS-experience SCPs explicitly allow `bedrock:*` and exempt
  `bedrock:InvokeModel` from region denies.

Control-plane calls work, which is the tell that this is a grant problem rather than a
credentials or region problem:

```bash
python -c "import boto3;print(len(boto3.Session(profile_name='junxaws',region_name='ap-south-1').client('bedrock').list_foundation_models()['modelSummaries']))"
# -> 75
```

**Which region is the project's?** `account.list_regions()` is the scriptable way to find
out: `ap-south-2` shows `ENABLED` (explicitly opted in) while everything else is
`ENABLED_BY_DEFAULT` or `DISABLED`. Worth checking, because a new-AWS-experience project
is pinned to its own region and Strands defaults to us-west-2.

## 3. Region

`us-west-2` is Strands' default, which is usually **wrong** for a new-AWS-experience
project. The live path takes an explicit region:

```bash
python -m nuskha.cli ask "what should atorvastatin 10mg cost?" --profile junxaws --region us-east-1
```

or via env: `AWS_PROFILE`, `AWS_REGION`, `BEDROCK_MODEL_ID`.

Note the region SCPs: only your **project region**, `us-east-1` and `us-west-2` are usable.
Outside the project region only a specific list of Bedrock actions is exempted, and
`InvokeModel` is on that list while `Converse`/`ConverseStream` is not — so a live agent
run (Strands calls `ConverseStream`) belongs in the project region.

## 4. The model

`global.anthropic.claude-sonnet-4-6` — Strands' current default, a global cross-region
inference profile. You can override it in `nuskha/agent.py` via `build_agent(model=...)`.

Note `BedrockModel(boto_session=..., region_name=...)` raises
`ValueError: Cannot specify both` — set the region **on the session**, not the model.

## 5. Run it

```bash
$PY -m nuskha.cli ask "what should atorvastatin 10mg cost, and is there any quality record?"
```

If it fails, the error surfaces rather than being swallowed, and the CLI prints a reminder
that the deterministic commands still work.

---

## Cost

The $100 in credits is far more than this needs. Each question makes two tool calls and one
short generation — fractions of a cent on Sonnet-class pricing. A full rehearsal of the demo
script would cost pennies.

## A note on the offline path

`nuskha/mock_model.py` drives the genuine Strands event loop with a scripted policy instead
of an LLM. It exists because a demo video cannot depend on live credentials and network
access. **Keep it.** If Bedrock misbehaves during recording, the demo still runs, and the
agent loop it exercises is the real one — only the model is substituted.

## Not the same as an AWS Builder ID

The hackathon requires an **AWS Builder ID** for submission. That is a builder.aws.com
identity, which is separate from an AWS account even though the same email can be used for
both. Sign up at `builder.aws.com` — it takes a minute and it is a hard requirement.
