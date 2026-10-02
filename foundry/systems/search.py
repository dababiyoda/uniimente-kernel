"""#17 Precedent search: retrieve declared cases by relevance and outcome label.

BM25 over case text finds cases that resemble the present decision. Outcomes then
split them instead of burying them: ``precedents`` returns the closest case that
*worked* and the closest case that *failed* side by side, because a similar
failure is the most valuable warning. Cases with no measured outcome are
down-weighted and labelled ``unmeasured``, never treated as successes. Context
filters keep a freight case from answering a clinic question. Every hit explains
its score. Supplied labels and references do not establish measurement, causal
effect or factual truth. Canonical GREG records own verified observations.
"""
from __future__ import annotations

import math
import re
from collections import Counter

K1, B = 1.2, 0.75
_TOKEN = re.compile(r"[a-z0-9]+")
_STOP = {"the", "a", "an", "of", "to", "and", "or", "in", "on", "for", "is", "was", "with", "by", "at", "it"}


def tokens(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOP]


UNMEASURED_WEIGHT = 0.6


def outcome_class(quality) -> str:
    if quality is None:
        return "unmeasured"
    if type(quality) not in (int, float) or not math.isfinite(quality) or not 0 <= quality <= 1:
        raise ValueError("outcome quality must be a finite probability or unknown")
    q = float(quality)
    return "worked" if q >= 0.6 else "failed" if q <= 0.4 else "mixed"


def search(cases: list[dict], query: str, *, context: dict | None = None, limit: int = 5) -> list[dict]:
    if type(limit) is not int or not 0 <= limit <= 512:
        raise ValueError("search limit must be a bounded nonnegative integer")
    pool = [c for c in cases if not context or all(c.get("context", {}).get(k) == v for k, v in context.items())]
    docs = [Counter(tokens(c["text"])) for c in pool]
    if not docs:
        return []
    avg = sum(sum(d.values()) for d in docs) / len(docs)
    df = Counter(t for d in docs for t in d)
    q = tokens(query)
    hits = []
    for case, doc in zip(pool, docs):
        length = sum(doc.values())
        relevance = sum(math.log(1 + (len(docs) - df[t] + 0.5) / (df[t] + 0.5)) * doc[t] * (K1 + 1)
                        / (doc[t] + K1 * (1 - B + B * length / avg)) for t in q if doc[t])
        if relevance <= 0:
            continue
        outcome = outcome_class(case.get("outcome_quality"))
        weight = UNMEASURED_WEIGHT if outcome == "unmeasured" else 1.0
        hits.append({"id": case["id"], "score": round(relevance * weight, 4), "relevance": round(relevance, 4),
                     "outcome": outcome, "outcome_quality": case.get("outcome_quality"),
                     "matched": sorted(t for t in set(q) if doc[t])})
    return sorted(hits, key=lambda h: (-h["score"], h["id"]))[:limit]


def precedents(cases: list[dict], query: str, *, context: dict | None = None) -> dict:
    """The closest precedent that worked and the closest that failed, for one decision."""
    hits = search(cases, query, context=context, limit=len(cases))
    first = lambda kind: next((h for h in hits if h["outcome"] == kind), None)
    return {"closest_worked": first("worked"), "closest_failed": first("failed"),
            "unmeasured": [h["id"] for h in hits if h["outcome"] == "unmeasured"], "all": hits}


QUERY_OPS = {"search": lambda a, r: {"hits": search(a["cases"], a["query"], context=a.get("context"),
                                                    limit=int(a.get("limit", 5)))},
             "precedents": lambda a, r: precedents(a["cases"], a["query"], context=a.get("context"))}
APPLY_OPS: dict = {}


def exercise(root) -> dict:
    cases = [
        {"id": "freight-pilot-failed", "text": "proof of delivery verifier pilot for freight brokers invoices paid late",
         "outcome_quality": 0.1, "context": {"market": "freight"}},
        {"id": "freight-pilot-worked", "text": "delivery proof verifier with broker finance sign off invoices paid faster",
         "outcome_quality": 0.9, "context": {"market": "freight"}},
        {"id": "clinic-intake", "text": "clinic intake proof verifier for insurance claims",
         "outcome_quality": 0.8, "context": {"market": "clinics"}},
        {"id": "freight-unmeasured", "text": "proof of delivery verifier idea for freight brokers", "context": {"market": "freight"}},
    ]
    found = precedents(cases, "proof of delivery verifier for freight brokers", context={"market": "freight"})
    return {"closest_worked": found["closest_worked"]["id"], "closest_failed": found["closest_failed"]["id"],
            "unmeasured": found["unmeasured"], "context_filtered": all(h["id"].startswith("freight") for h in found["all"]),
            "clinic_case_excluded": "clinic-intake" not in [h["id"] for h in found["all"]]}
