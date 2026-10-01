"""Contract examples produced by real runs (build prompt item 11).

    python -m cortex.examples --out docs/cortex/examples

Every example is emitted by the code it documents, never written by hand, and
``tests/unit/test_cortex_traceability.py`` validates each file against its
contract. Receipts carry measured expenditure, so their ids change between
runs; the dispositions and states do not.
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

from .evaluation.run import load_items
from .memory import CompetenceLedger
from .routing import Cortex
from .schemas import validate
from .genome import seed_registry

# (file stem, held-out item or None, what the example shows)
RECEIPTS = (
    ("receipt-formal-recommend", "H-F01", "Z3 feasibility with witnesses; reversible internal write"),
    ("receipt-estimate-dependent-inputs", "H-E02", "copula-preserved dependency between uncertain inputs"),
    ("receipt-causal-identified", "H-C01", "declared identification, adjustment, refutations"),
    ("receipt-causal-unmeasured-confounding", "H-C04", "named unmeasured confounder -> not identified"),
    ("receipt-gates-incomparable", "H-G03", "hard gates before ranking; Pareto tradeoff kept"),
    ("receipt-semantic-model-unavailable", "H-S01", "no local model -> explicit DEPENDENCY_UNAVAILABLE"),
)
LEGAL = {"problem_id": "example-legal", "question": "Is this clause enforceable?",
         "payload": {"declared": {"epistemic_class": "legal", "consequence_class": "internal_write"}}}
STAFFING = {"problem_id": "example-optimize", "question": "Cheapest staffing that covers 7 shift units?", "payload": {
    "formal_model": {
        "requirement": "Cover at least 7 shift units with juniors (1 unit, 30 USD) and seniors (2 units, 45 USD); "
                       "at most 6 juniors and 5 seniors; minimize cost.",
        "variables": [{"name": "a", "sort": "int", "lo": 0, "hi": 6}, {"name": "b", "sort": "int", "lo": 0, "hi": 5}],
        "obligations": [{"id": "R_cover", "text": "at least 7 units covered"}],
        "constraints": [{"id": "C_cover", "covers": ["R_cover"], "expr": [">=", ["+", "a", ["*", 2, "b"]], 7]}],
        "query": {"kind": "optimize", "sense": "minimize", "objective": ["+", ["*", 30, "a"], ["*", 45, "b"]]},
        "witnesses": {"satisfying": [{"a": 1, "b": 3}], "violating": [{"a": 0, "b": 0}]}},
    "declared": {"consequence_class": "internal_write", "reversibility": "reversible"}}}
PROTECTION = {"relevant": True, "required_actions": ["immediate_protection", "evidence_preservation", "escalation"],
              "evidence_access": "need_to_know", "disclosure_controls": ["no disclosure without the person's consent"]}


def _find(items, item_id):
    return copy.deepcopy(next(i["problem"] for i in items if i["item_id"] == item_id))


def build() -> dict[str, tuple[str, dict]]:
    """Return {file stem: (contract name, payload)}; every payload is validated."""
    cortex = Cortex(clock=lambda: "2026-09-30T00:00:00Z")
    items = load_items("heldout")
    out: dict[str, tuple[str, dict]] = {}
    receipts = {}
    for stem, item_id, _ in RECEIPTS:
        receipts[stem] = cortex.run(_find(items, item_id))
    receipts["receipt-legal-handoff"] = cortex.run(copy.deepcopy(LEGAL))
    receipts["receipt-formal-optimize-certified"] = cortex.run(copy.deepcopy(STAFFING))
    protected = _find(items, "H-F01")
    protected["problem_id"] = "example-victim-protection"
    protected["payload"]["victim_protection"] = copy.deepcopy(PROTECTION)
    receipts["receipt-victim-protection-handoff"] = cortex.run(protected)
    for stem, r in receipts.items():
        out[stem] = ("cortex-receipt", r)
    out["problem-geometry-formal"] = ("cortex-problem-geometry", receipts["receipt-formal-recommend"]["geometry"])
    seen = set()
    for r in receipts.values():
        for proof in r["proof_artifacts"]:
            pc = proof["proof_class"]
            if pc not in seen:
                seen.add(pc)
                out[f"proof-{pc}"] = ("cortex-proof-artifact", proof)
    registry = seed_registry()
    out["genome-formal-z3"] = ("cortex-intelligence-genome", registry.get("cortex.formal.z3@0.2.0").to_dict())
    reserved = next(k for k in registry.keys() if not registry.get(k).profile.enabled
                    and registry.get(k).profile.biological_concept)
    out["genome-reserved-disabled"] = ("cortex-intelligence-genome", registry.get(reserved).to_dict())
    ledger = CompetenceLedger()
    record = ledger.settle(receipt=receipts["receipt-formal-recommend"], method="cortex.formal.z3",
                           method_version="0.2.0", outcome_status="verified_success",
                           provenance={"kind": "external_observation", "validation_status": "externally_verified",
                                       "ref": "example: schedule executed as proved"},
                           attribution=[{"method": "cortex.formal.z3", "role": "final_answer", "uncertainty": "low"},
                                        {"method": "cortex.verifier.adversarial", "role": "flaw_detection",
                                         "uncertainty": "medium"}])
    out["routing-memory-verified-success"] = ("cortex-routing-memory", record.to_dict())
    for stem, (name, payload) in out.items():
        validate(payload, name)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="docs/cortex/examples")
    args = ap.parse_args(argv)
    target = Path(args.out)
    target.mkdir(parents=True, exist_ok=True)
    index = {}
    for stem, (name, payload) in build().items():
        (target / f"{stem}.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        index[f"{stem}.json"] = name
    (target / "INDEX.json").write_text(json.dumps({"schema": "cortex-examples/0.1", "contracts": index},
                                                  indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(index, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
