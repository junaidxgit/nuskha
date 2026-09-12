# Running the agent against Amazon Bedrock

Strands ships Bedrock as its default provider, so this is the only setup needed to run the
**real** agent with a real model. Everything else in the project works without it.

Check current state with:

```bash
PY="C:/Users/offic/.workbuddy-ai/binaries/python/envs/default/Scripts/python.exe"
$PY -m medlens.cli check-bedrock
```

Two things have to be true. The command checks them in order, because each failure has a
different fix.

---

## 1. Credentials

Not currently configured on this machine — `~/.aws/` exists but is empty, and no
`AWS_ACCESS_KEY_ID` is set.

**Option A — credentials file** (survives reboots; recommended). Create
`C:\Users\offic\.aws\credentials`:

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

**Option B — environment variables** (per-shell, disappears when the terminal closes):

```bash
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_DEFAULT_REGION=us-west-2
```

Never commit either of these. `~/.aws/` is outside the repo, and `.gitignore` already
excludes `.env`.

## 2. Model access

Bedrock does not grant model access by default — it has to be requested per model, per
account. Without it every call fails with `AccessDeniedException`, which reads like a
credentials problem and wastes an hour.

AWS console → **Bedrock** → **Model access** → **Modify model access** → tick the
**Anthropic Claude** models → submit. Approval is usually immediate.

## 3. Region

`us-west-2` is Strands' default and where this project is configured. Bedrock model
availability differs by region — `ap-south-1` (Mumbai) is closer to Bengaluru but carries a
different model list. If you switch, pass it explicitly:

```bash
$PY -m medlens.cli check-bedrock --region ap-south-1
```

## 4. The model

`global.anthropic.claude-sonnet-4-6` — Strands' current default, a global cross-region
inference profile. You can override it in `medlens/agent.py` via `build_agent(model=...)`.

## 5. Run it

```bash
$PY -m medlens.cli ask "what should atorvastatin 10mg cost, and is there any quality record?"
```

If it fails, the error surfaces rather than being swallowed, and the CLI prints a reminder
that the deterministic commands still work.

---

## Cost

The $100 in credits is far more than this needs. Each question makes two tool calls and one
short generation — fractions of a cent on Sonnet-class pricing. A full rehearsal of the demo
script would cost pennies.

## A note on the offline path

`medlens/mock_model.py` drives the genuine Strands event loop with a scripted policy instead
of an LLM. It exists because a demo video cannot depend on live credentials and network
access. **Keep it.** If Bedrock misbehaves during recording, the demo still runs, and the
agent loop it exercises is the real one — only the model is substituted.

## Not the same as an AWS Builder ID

The hackathon requires an **AWS Builder ID** for submission. That is a builder.aws.com
identity, which is separate from an AWS account even though the same email can be used for
both. Sign up at `builder.aws.com` — it takes a minute and it is a hard requirement.
