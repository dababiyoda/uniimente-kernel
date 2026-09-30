"""Model-backed proposer parts over any OpenAI-compatible chat endpoint.

Local open-weight servers (Ollama, llama.cpp, vLLM, LM Studio) and hosted
tiers (Groq, OpenRouter, Together, Gemini's compatibility endpoint) share the
chat-completions wire format, so one stdlib client covers all of them and a
newer model is a new ``PartSpec``, not new code.

The model drafts content only: objective, expected outcome, payload,
self-reported confidence and which of the tick's signals it relied on.
Authority-bearing fields -- action class, requested capability, target and
consequence class -- are fixed by the code that builds the part, never by
the model. Model confidence is capped because model output is not evidence
by itself; the raw value is kept in the payload.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from .contracts import CandidateProposal, ContractError, SignalEnvelope, require_text
from .parts import PartSpec

Transport = Callable[[str, Mapping[str, str], Mapping[str, Any], float], Mapping[str, Any]]

_SYSTEM = (
    "You are one proposer inside a governed decision system. You draft candidate "
    "next steps from the signals given. You have no authority: humans and a policy "
    "gate decide what happens. Only cite signal ids you were given. Reply with JSON "
    'only: {"candidates": [{"objective": str, "expected_outcome": str, '
    '"payload": object, "confidence": number 0..1, "source_signal_ids": [str], '
    '"evidence_refs": [str]}]}. Return {"candidates": []} when nothing is warranted.'
)


def urllib_transport(url: str, headers: Mapping[str, str], body: Mapping[str, Any],
                     timeout: float) -> Mapping[str, Any]:
    request = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers}, method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - operator-set URL
        return json.loads(response.read().decode("utf-8"))


def extract_json(text: str) -> Any:
    """Parse a JSON object from model text, tolerating fences and think blocks."""
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S).strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.S)
    if fenced:
        text = fenced.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ContractError("model reply contained no JSON object")
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError as exc:
        raise ContractError(f"model reply was not valid JSON: {exc}") from exc


@dataclass(frozen=True)
class Envelope:
    """Authority-bearing candidate fields, fixed by code for this part."""

    action_class: str
    requested_capability: str
    target: str
    consequence_class: str
    estimated_cost_usd: float = 0.0


def openai_compatible_proposer(
    *,
    role: str,
    base_url: str,
    model: str,
    envelope: Envelope,
    api_key_env: str | None = None,
    provenance: str | None = None,
    open_weights: bool | None = None,
    confidence_cap: float = 0.5,
    max_candidates: int = 3,
    temperature: float = 0.2,
    timeout: float = 60.0,
    transport: Transport = urllib_transport,
) -> tuple[PartSpec, Callable[[tuple[SignalEnvelope, ...], dict[str, Any]], list[CandidateProposal]]]:
    """Build a (spec, proposer) pair ready for ``PartsBoard.register``."""
    role = require_text("role", role)
    base_url = require_text("base_url", base_url).rstrip("/")
    model = require_text("model", model)
    if not 0.0 <= confidence_cap <= 1.0:
        raise ContractError("confidence_cap must be between 0 and 1")
    if max_candidates < 1:
        raise ContractError("max_candidates must be positive")
    for name in ("action_class", "requested_capability", "target", "consequence_class"):
        require_text(name, getattr(envelope, name))

    spec = PartSpec(
        slot=f"proposer:{role}",
        implementation=f"openai-compatible:{model}",
        version=f"{base_url}|{envelope.consequence_class}|cap={confidence_cap}",
        provenance=provenance or base_url,
        open_weights=open_weights,
        notes="model drafts content; code fixes action/capability/target/consequence",
    )

    def propose(signals: tuple[SignalEnvelope, ...], context: dict[str, Any]) -> list[CandidateProposal]:
        if not signals:
            return []
        headers = {}
        if api_key_env:
            key = os.environ.get(api_key_env, "")
            if not key:
                raise ContractError(f"{api_key_env} is not set")
            headers["Authorization"] = f"Bearer {key}"
        user = json.dumps({
            "context": context,
            "signals": [{"signal_id": s.signal_id, "source": s.source, "observed_at": s.observed_at,
                         "trust_level": s.trust_level, "payload": s.payload} for s in signals],
            "max_candidates": max_candidates,
        }, sort_keys=True)
        reply = transport(f"{base_url}/chat/completions", headers, {
            "model": model,
            "temperature": temperature,
            "messages": [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": user}],
        }, timeout)
        try:
            text = reply["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ContractError("endpoint reply is not a chat completion") from exc
        drafts = extract_json(text).get("candidates", [])
        if not isinstance(drafts, list):
            raise ContractError("model 'candidates' must be a list")

        known = {s.signal_id for s in signals}
        results = []
        for draft in drafts[:max_candidates]:
            if not isinstance(draft, Mapping):
                raise ContractError("each model candidate must be an object")
            cited = [sid for sid in draft.get("source_signal_ids", []) if sid in known]
            if not cited:
                continue  # uncited or invented signal ids are dropped, not repaired
            raw_confidence = float(draft.get("confidence", 0.0))
            if not 0.0 <= raw_confidence <= 1.0:
                raise ContractError("model confidence must be between 0 and 1")
            payload = draft.get("payload", {})
            if not isinstance(payload, Mapping):
                raise ContractError("model payload must be an object")
            results.append(CandidateProposal.build(
                proposed_by=role,
                objective=str(draft.get("objective", "")),
                action_class=envelope.action_class,
                requested_capability=envelope.requested_capability,
                target=envelope.target,
                consequence_class=envelope.consequence_class,
                payload={**payload, "model": model, "model_confidence": raw_confidence},
                evidence_refs=[str(ref) for ref in draft.get("evidence_refs", [])],
                confidence=min(raw_confidence, confidence_cap),
                estimated_cost_usd=envelope.estimated_cost_usd,
                expected_outcome=str(draft.get("expected_outcome", "")),
                source_signal_ids=cited,
            ))
        return results

    return spec, propose
