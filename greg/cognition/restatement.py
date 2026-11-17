"""A document that restates its sources, checked by the Mind sentence by sentence (directive section 16).

One contract, two consumers. DALEOBANKS's ``daleobanks.verify`` reads the Mind's receipts from the canonical
ledger when a signed mission declared every claim in advance (the media case). The Task Fabric's independent
evaluator, ``worker.appraise``, cannot: a temporary worker writes the document after the mission is signed, so it
asks the Mind itself, here, over the bindings the worker declares and GREG's own copies of the inputs. Either way,
every sentence of the document must be a claim GREG's evidence family answered as written: bound to supporting
spans and showing none of the six detected kinds of change. A worker's binding is a claim to be checked, never
acceptance; finding no change is not entailment.
"""
from __future__ import annotations

import json

from .contracts import digest

MAX_CLAIMS = 32
MAX_CLAIM_CHARS = 2000
LIMITS = ("each claim is span-bound and shows none of the six detected kinds of change; that is not entailment, "
          "factual accuracy or acceptance")


def coverage(text: str, receipts: dict) -> tuple[dict, list[str]]:
    """The document against the Mind's restatement receipts: each sentence a claim answered as written."""
    findings, rest, distortions = [], text, []
    for name, receipt in receipts.items():
        claim = (receipt.get("output") or {}).get("claim") or ""
        why = "; ".join(receipt.get("missing_information") or []) or receipt.get("abstention_state")
        if receipt.get("method") != "cognition.evidence":
            findings.append(f"claim {name}: receipt is from {receipt.get('method')}, not the evidence family")
            continue
        if not claim and receipt.get("abstention_state") != "NONE":
            # the Mind took the request and answered nothing (a quote the source lacks): its reason, not ours
            findings.append(f"claim {name} is not supported as written; the Mind answered nothing: {why}"[:400])
            continue
        if not claim or claim not in rest:
            findings.append(f"claim {name}: not a sentence of this draft")
            continue
        rest = rest.replace(claim, " ", 1)
        changed = (receipt.get("output") or {}).get("distortions") or []
        distortions += [{"claim": name, **c} for c in changed]
        if receipt.get("abstention_state") != "NONE":
            findings.append(f"claim {name} is not supported as written: {why}"[:400])
    uncovered = " ".join(rest.split())
    if any(ch.isalnum() for ch in uncovered):
        findings.append(f"draft text no receipt covers: {uncovered[:200]!r}")
    return {"checked": True, "claims": len(receipts), "distortions": distortions,
            "receipts": {k: r.get("receipt_id") for k, r in receipts.items()}, "limits": LIMITS}, findings


def read_claims(raw: str, inputs: list[str]) -> tuple[list[dict], list[str]]:
    """The worker's declared bindings: ``[{"text": sentence, "quotes": [{"input": name, "quote": span}]}]``.

    A bare string quote names the only input. Malformed bindings are findings, never repaired or guessed."""
    try:
        claims = json.loads(raw)
    except json.JSONDecodeError as exc:
        return [], [f"claims file is not JSON: {exc.msg}"]
    if not isinstance(claims, list) or not 1 <= len(claims) <= MAX_CLAIMS:
        return [], [f"claims file must list 1..{MAX_CLAIMS} claims"]
    out, findings = [], []
    for i, claim in enumerate(claims, 1):
        text = claim.get("text") if isinstance(claim, dict) else None
        quotes = claim.get("quotes") if isinstance(claim, dict) else None
        if not isinstance(text, str) or not text.strip() or len(text) > MAX_CLAIM_CHARS:
            findings.append(f"claim {i}: text must be a sentence of the deliverable")
            continue
        if not isinstance(quotes, list) or not quotes:
            findings.append(f"claim {i}: no supporting span; every sentence must cite an input")
            continue
        bindings = []
        for q in quotes:
            if isinstance(q, str) and len(inputs) == 1:
                q = {"input": inputs[0], "quote": q}
            if not isinstance(q, dict) or q.get("input") not in inputs or not isinstance(q.get("quote"), str):
                findings.append(f"claim {i}: each quote names one of the inputs {inputs} and copies a span from it")
                bindings = []
                break
            bindings.append({"source_id": q["input"], "quote": q["quote"], "relationship": "supports"})
        if bindings:
            out.append({"name": f"c{i}", "text": text, "bindings": bindings})
    return out, findings


def answer(claims: list[dict], sources: list[dict], *, problem_prefix: str, registry=None) -> dict:
    """GREG's evidence family on each claim, through the canonical cognition entry; receipts, never verdicts."""
    from .cortex import reason, registry_view
    registry = registry or registry_view(None)
    return {c["name"]: reason({"problem_id": f"{problem_prefix}-{c['name']}", "operation": "bind_evidence",
                               "data": {"claim": c["text"], "sources": sources, "bindings": c["bindings"]}},
                              registry=registry)
            for c in claims}


def source(name: str, text: str, *, quality: str, expires_at: str, provenance: str) -> dict:
    return {"id": name, "text": text, "digest": digest(text), "quality": quality, "expires_at": expires_at,
            "provenance": provenance}
