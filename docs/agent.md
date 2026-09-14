# The agent

A Strands Agents agent with three tools over `nuskha.db`.

```
nuskha/
  queries.py     the three query functions (pure, DB-backed)
  tools.py       @tool wrappers - Strands derives the spec from the signature
  agent.py       build_agent() + the system prompt that enforces the framing
  mock_model.py  a scripted model, so the real loop runs with no credentials
  cli.py         deterministic CLI + agent mode
```

## Run it

```bash
PY=python    # or your interpreter; `python -m nuskha.cli ...` works as-is

# deterministic - no model, no credentials, no network. Use this for the demo.
$PY -m nuskha.cli price atorvastatin 10mg
$PY -m nuskha.cli check coldrif
$PY -m nuskha.cli report atorvastatin 10mg
$PY -m nuskha.cli json atorvastatin 10mg

# the real agent loop, driven by a scripted model instead of an LLM.
# --trace prints each tool dispatch, which is the demo's evidence that the
# loop is genuinely running. Exit code 0, no credentials, no network.
$PY -m nuskha.cli ask "what should atorvastatin 10mg cost?" --offline --trace

# the real agent with a real model (needs AWS credentials)
$PY -m nuskha.cli ask "what should atorvastatin 10mg cost?"
```

## Why there is a scripted model

Strands ships **Amazon Bedrock** as its default provider, and Bedrock needs AWS
credentials. A demo video cannot depend on live credentials, and neither can CI.

`mock_model.py` implements the Strands `Model` interface and drives the genuine
event loop — real tool dispatch, real tool results fed back, real two-turn
agent cycle. Only the policy is scripted: turn one emits `get_price` and
`check_quality_record`, turn two renders the results.

It is **not** a production substitute. It exists so the wiring is provably
correct and the demo is reproducible.

Verified loop trace:

```
user       ['text']
assistant  ['toolUse', 'toolUse']
user       ['toolResult', 'toolResult']
assistant  ['text']
```

### Notes for wiring a real model

- `Model.stream` is called as `stream(messages, tool_specs, system_prompt, **kwargs)`
  — accept extra positional args or it fails with a `TypeError`.
- A tool spec lives at `tool.tool_spec["inputSchema"]["json"]`, not at
  `inputSchema` directly.
- The stream chunks are `messageStart`, `contentBlockStart`, `contentBlockDelta`,
  `contentBlockStop`, `messageStop`. Tool calls arrive as
  `{"contentBlockStart": {"start": {"toolUse": {"toolUseId", "name"}}}}`
  followed by `{"contentBlockDelta": {"delta": {"toolUse": {"input": "<json>"}}}}`.
- Only Bedrock ships by default. Ollama and LiteLLM need their own packages
  (`pip install strands-agents[ollama]`, or `litellm`).

## The tools

| tool | answers | source |
|---|---|---|
| `find_alternatives(salt, strength)` | what else has this composition | Jan Aushadhi + NPPA |
| `get_price(salt, strength)` | what should it cost | NPPA ceiling + Jan Aushadhi floor |
| `check_quality_record(name)` | any recorded quality failure | CDSCO NSQ + WHO alerts |

All three are **composition-first**. Brand names are not accepted, because no
public dataset maps Indian brand names to compositions.

## Where the safety framing lives

The data layer is deliberately dumb — it will return a combination product as
"the ceiling" and an NSQ hit as though it condemned a company. Two things stop
that reaching a user:

1. **Flags in the returned data.** `is_combination`, the `sanity` verdict on
   price comparisons, and the `caveats` list.
2. **The system prompt** in `agent.py`, which states the rules explicitly:
   never instruct a substitution, NSQ findings are batch-specific, absence of a
   record is not evidence of quality, never merge the tiers, never editorialise,
   never estimate a price.

Both layers matter. The prompt can be argued with; the flags cannot.
