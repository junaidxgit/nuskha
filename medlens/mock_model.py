"""A scripted model for running the real Strands agent loop offline.

Why this exists: Strands ships Amazon Bedrock as its default provider, and
Bedrock needs AWS credentials. A demo video cannot depend on live credentials,
and neither can CI. This model drives the genuine agent event loop - real tool
dispatch, real tool results fed back - with a deterministic policy instead of an
LLM.

It is NOT a substitute for the LLM in production. It proves the wiring works and
it makes the demo reproducible. Run the real thing with Bedrock via
medlens.agent.build_agent().

Policy:
  turn 1 - no tool results yet  -> emit tool calls for get_price and
                                   check_quality_record, arguments parsed from
                                   the user's question
  turn 2 - tool results present -> emit a short written summary
"""

from __future__ import annotations

import json
import re
from typing import Any, AsyncIterator

from strands.models import Model

SALT = re.compile(
    r"\b(atorvastatin|metformin|paracetamol|amoxicillin|omeprazole|"
    r"amlodipine|azithromycin|montelukast|pantoprazole|cefixime|"
    r"coldrif|sresan)\b", re.I)
STRENGTH = re.compile(r"\b(\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml))\b", re.I)


class ScriptedModel(Model):
    """Deterministic stand-in for an LLM, for offline runs of the agent loop."""

    def __init__(self, verbose: bool = False) -> None:
        self._verbose = verbose
        self._config: dict[str, Any] = {"model_id": "scripted"}

    # --- Model interface -------------------------------------------------
    def update_config(self, **model_config: Any) -> None:
        self._config.update(model_config)

    def get_config(self) -> Any:
        return self._config

    async def structured_output(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError("the scripted model has no structured output")

    # --- the loop --------------------------------------------------------
    async def stream(self, messages: list[dict], *args: Any,
                     **kwargs: Any) -> AsyncIterator[dict]:
        # Strands calls stream(messages, tool_specs, system_prompt, **kwargs),
        # so the extra positional arguments must be accepted.
        question = self._user_question(messages)
        already_ran = self._has_tool_result(messages)

        yield {"messageStart": {"role": "assistant"}}

        if not already_ran:
            salt = (SALT.search(question) or [None])
            salt = salt.group(1) if hasattr(salt, "group") else None
            strength = (STRENGTH.search(question) or [None])
            strength = strength.group(1).replace(" ", "") if hasattr(strength, "group") else ""
            name = salt or question.strip()[:40] or "unknown"

            calls = [
                ("get_price", {"salt": salt or name, "strength": strength}),
                ("check_quality_record", {"name": name}),
            ]
            for i, (tool_name, payload) in enumerate(calls, start=1):
                yield {"contentBlockStart": {"start": {"toolUse": {
                    "toolUseId": f"scripted-{i}", "name": tool_name}}}}
                yield {"contentBlockDelta": {"delta": {"toolUse": {
                    "input": json.dumps(payload)}}}}
                yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "tool_use"}}
            return

        text = self._summarise(messages)
        yield {"contentBlockStart": {"start": {}}}
        yield {"contentBlockDelta": {"delta": {"text": text}}}
        yield {"contentBlockStop": {}}
        yield {"messageStop": {"stopReason": "end_turn"}}

    # --- helpers ---------------------------------------------------------
    @staticmethod
    def _user_question(messages: list[dict]) -> str:
        for m in reversed(messages):
            if m.get("role") != "user":
                continue
            content = m.get("content")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts = [c.get("text", "") for c in content if isinstance(c, dict)]
                joined = " ".join(p for p in parts if p)
                if joined:
                    return joined
        return ""

    @staticmethod
    def _has_tool_result(messages: list[dict]) -> bool:
        for m in messages:
            content = m.get("content")
            if not isinstance(content, list):
                continue
            for c in content:
                if isinstance(c, dict) and ("toolResult" in c or "tool_result" in c):
                    return True
        return False

    def _summarise(self, messages: list[dict]) -> str:
        """Render the tool results the loop handed back."""
        blocks: list[dict] = []
        for m in messages:
            content = m.get("content")
            if not isinstance(content, list):
                continue
            for c in content:
                if not isinstance(c, dict):
                    continue
                tr = c.get("toolResult") or c.get("tool_result")
                if tr:
                    blocks.append(tr)

        lines: list[str] = []
        for tr in blocks:
            payload = tr.get("content")
            text = ""
            if isinstance(payload, list):
                text = " ".join(p.get("text", "") for p in payload
                                if isinstance(p, dict))
            elif isinstance(payload, str):
                text = payload
            try:
                data = json.loads(text)
            except Exception:
                continue
            if "ceiling" in data or "floor" in data:
                lines.append(self._fmt_price(data))
            elif "tier1_nsq_batch_alerts" in data:
                lines.append(self._fmt_quality(data))

        body = "\n\n".join(x for x in lines if x)
        return body or "No matching records found."

    @staticmethod
    def _fmt_price(d: dict) -> str:
        c, f, cmp_ = d.get("ceiling"), d.get("floor"), d.get("comparison")
        out = ["Price:"]
        out.append(f"  legal maximum  Rs {c['price_inr']} per {c['unit']} "
                   f"({c['formulation']})" if c else
                   "  legal maximum  no same-strength NPPA ceiling on record")
        out.append(f"  govt generic   Rs {f['price_inr']} per {f['pack']} "
                   f"({f['product']})" if f else
                   "  govt generic   no same-strength Jan Aushadhi product on record")
        if cmp_:
            out.append(f"  per {cmp_['unit_kind']}: floor Rs {cmp_['floor_per_unit_inr']}"
                       f" vs ceiling Rs {cmp_['ceiling_per_unit_inr']}"
                       f"  ({cmp_['ratio']}x)")
        for cav in d.get("caveats", []):
            if cav.startswith("WARNING"):
                out.append(f"  ! {cav}")
        return "\n".join(out)

    @staticmethod
    def _fmt_quality(d: dict) -> str:
        t1 = d["tier1_nsq_batch_alerts"]
        t2 = d["tier2_who_alerts"]
        out = [f"Quality records for {d['query']}:"]
        out.append(f"  Tier 1 CDSCO NSQ batch alerts: {t1['count']}")
        for r in t1["records"][:3]:
            out.append(f"    {r['product_name'][:60]} | batch {r['batch_no']}"
                       f" | {r['nsq_reason'][:40]} | {r['alert_year']}-{r['alert_month']:02d}")
        out.append(f"  Tier 2 WHO alerts: {t2['count']}")
        for r in t2["records"][:3]:
            out.append(f"    {r['alert_label'][:66]}")
        if not t1["count"] and not t2["count"]:
            out.append("  Absence of a record is not evidence of quality - "
                       "only sampled batches are tested.")
        return "\n".join(out)
