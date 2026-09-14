"""The Nuskha Strands agent.

Provider-agnostic on purpose. Strands ships Amazon Bedrock by default; pass any
other model via build_agent(model=...). See docs/agent.md for how to run it
against Bedrock, and nuskha/cli.py for a deterministic mode that needs no
model credentials at all.

The system prompt is where the safety framing is enforced. The data layer will
happily return a combination product as "the ceiling" or an NSQ hit as though it
condemned a company; it is this prompt, plus the flags the tools return, that
stops that reaching a user.
"""

from __future__ import annotations

from strands import Agent

from nuskha.tools import check_quality_record, find_alternatives, get_price

SYSTEM_PROMPT = """You are Nuskha. A user tells you the salt written on their
prescription and you tell them two things: what it should cost, and whether
anything in the regulatory record concerns it.

You are not a doctor and you never give medical advice.

## How to answer

1. Call get_price for the salt and strength. Call check_quality_record for the
   salt and for any manufacturer named in the results.
2. Lead with the two numbers: the NPPA ceiling (the legal maximum) and the Jan
   Aushadhi price (the government generic). If the comparison object is present,
   state the ratio.
3. Then report quality records, if any, in their tiers.

## Non-negotiable rules

- **Composition-first only.** If the user gives a brand name you cannot resolve
  it. Say so and ask for the salt, which is printed on the prescription.
- **Never instruct a substitution.** Show options. Composition match is not
  proven therapeutic equivalence - CDSCO does not require bioequivalence studies
  for domestically marketed generics. Tell them to ask their prescriber.
- **An NSQ finding is batch-specific.** It means one batch failed testing on one
  date for the stated reason. It is NOT a statement about the company. Never
  call a manufacturer unsafe, adulterated, or untrustworthy. Quote the batch
  number, the alert month and the stated reason, and link the source.
- **Absence of a record is not evidence of quality.** Only sampled batches are
  tested. Say this whenever you report zero findings.
- **Never merge the tiers.** A Tier 1 CDSCO record is "recorded by the
  regulator". A Tier 2 WHO alert is "published by WHO". Keep them separate and
  label which is which.
- **Never editorialise.** No scores, no rankings, no red flags of your own
  invention. Mirror the government record verbatim.
- **If a match is a combination product** (is_combination is true, or a caveat
  warns about it), say so plainly. An aspirin-atorvastatin combination is not
  the price of atorvastatin.
- **If you cannot find something, say so.** Never estimate a price.

## Tone

Direct and plain. The user may be a patient or a family member, not a
pharmacologist. Short sentences. No hedging, no filler, no emoji.
"""


def build_ollama_model(model_id: str | None = None, host: str | None = None,
                       force_cpu: bool = True):
    """Build a model backed by a local Ollama server.

    This is the credential-free *live* LLM path: a real model, a real token
    stream, real tool calls - no AWS account, no API key, no network.

    `force_cpu` matters on this machine: the GTX 1650 (compute 7.5) cannot run
    the bundled llama.cpp kernels, and the GPU path dies with
    "CUDA error: a PTX JIT compilation failed". Running on CPU avoids it, at the
    cost of roughly a minute or two per question for a 2B model.

    Also note the bundled models are reasoning models - they emit a `thinking`
    field before `content`. A small `num_predict` can be consumed entirely by
    the reasoning and return an empty answer, so the token budget is generous.
    """
    import os

    from strands.models.ollama import OllamaModel

    model_id = model_id or os.environ.get("OLLAMA_MODEL") or "qwen3.5:2b"
    host = host or os.environ.get("OLLAMA_HOST") or "http://127.0.0.1:11434"

    options: dict = {"num_predict": 512}
    if force_cpu:
        options["num_gpu"] = 0
    return OllamaModel(host=host, model_id=model_id, options=options)


def build_bedrock_model(profile: str | None = None, region: str | None = None,
                        model_id: str | None = None):
    """Build a Bedrock model, honouring env vars so no code edit is needed.

    Strands' default is us-west-2, but a new-AWS-experience project is pinned to
    its own region (and the SCPs only exempt a handful of Bedrock actions
    elsewhere), so the region has to be settable without touching this file.

    Resolution order, each falling back to the next:
      profile  -> arg, then AWS_PROFILE
      region   -> arg, then AWS_REGION / AWS_DEFAULT_REGION, then Strands' default
      model_id -> arg, then BEDROCK_MODEL_ID, then Strands' default

    Note: BedrockModel rejects `region_name` and `boto_session` together, so the
    region is always carried on the session.
    """
    import os

    import boto3
    from strands.models import BedrockModel

    profile = profile or os.environ.get("AWS_PROFILE") or None
    region = (region or os.environ.get("AWS_REGION")
              or os.environ.get("AWS_DEFAULT_REGION") or None)

    session = boto3.Session(profile_name=profile, region_name=region)

    kwargs: dict = {"boto_session": session}
    if model_id or os.environ.get("BEDROCK_MODEL_ID"):
        kwargs["model_id"] = model_id or os.environ["BEDROCK_MODEL_ID"]
    return BedrockModel(**kwargs)


def build_agent(model=None, callback_handler=None) -> Agent:
    """Create the agent.

    Args:
        model: any Strands model. Defaults to Strands' own default (Amazon
            Bedrock), which requires AWS credentials.
        callback_handler: pass None to silence streaming output.
    """
    kwargs = {
        "tools": [find_alternatives, get_price, check_quality_record],
        "system_prompt": SYSTEM_PROMPT,
        "name": "nuskha",
        "description": "Medicine composition, price ceiling and quality records",
    }
    if model is not None:
        kwargs["model"] = model
    if callback_handler is not None:
        kwargs["callback_handler"] = callback_handler
    return Agent(**kwargs)


def ask(question: str, model=None, callback_handler=None) -> str:
    """One-shot convenience wrapper."""
    agent = build_agent(model=model, callback_handler=callback_handler)
    return str(agent(question))
