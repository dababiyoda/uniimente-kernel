"""Claim/span binding, declared quality, freshness and contradictions in a bounded corpus."""
from datetime import datetime, timezone
from .contracts import CognitionError, digest


def assess(data, geometry):
    from .solvers import result
    claim, sources, bindings = data["claim"], data["sources"], data["bindings"]
    if not isinstance(claim, str) or not claim or not 1 <= len(sources) <= 32 or not 1 <= len(bindings) <= 64:
        raise CognitionError("claim and bounded sources/bindings required")
    now = datetime.now(timezone.utc)
    index, limitations = {}, ["span binding is not entailment, factual accuracy, causality or institutional acceptance"]
    for s in sources:
        if not isinstance(s, dict) or not isinstance(s.get("id"), str) or s["id"] in index or not isinstance(s.get("text"), str):
            raise CognitionError("unique source IDs and text required")
        if s.get("digest") != digest(s["text"]):
            raise CognitionError("forged source digest")
        if not s.get("provenance") or s.get("quality") not in ("primary", "secondary", "unverified"):
            raise CognitionError("source provenance and declared quality required")
        expires = datetime.fromisoformat(s["expires_at"].replace("Z", "+00:00"))
        if expires.tzinfo is None or expires <= now:
            raise CognitionError("stale or undated evidence")
        index[s["id"]] = s
    contradictions = []
    for b in bindings:
        if b.get("source_id") not in index or not isinstance(b.get("quote"), str) or not b["quote"] or b["quote"] not in index[b["source_id"]]["text"]:
            raise CognitionError("evidence mismatch")
        if b.get("relationship") not in ("supports", "contradicts", "context"):
            raise CognitionError("unsupported evidence relationship")
        if b["relationship"] == "contradicts":
            contradictions.append(b)
    return result({"claim": claim, "bound": True, "contested": bool(contradictions)},
                  {"claim": claim, "sources": [{k:v for k,v in s.items() if k != "text"} for s in sources], "bindings": bindings, "contradictions": contradictions,
                   "limitations": limitations, "source_quality": "declared, not independently authenticated"},
                  status="ABSTAIN" if contradictions else "ANSWER",
                  missing=("CONTRADICTION: retain dissent; request the next decisive observation",) if contradictions else ())
