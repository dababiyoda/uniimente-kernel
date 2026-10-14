"""Frozen P8 evaluator: replay a routing-policy genome against recorded, independently scored engine runs.

Run only as a separate process by ``greg.cognition.evolution.ProtectedEvaluator``; its SHA-256 is pinned
in ``freeze-v1.json`` and re-checked around every call. Input: one validated genome on stdin. Argument:
``dev`` or ``heldout``. Output: counts only (no data, paths or labels are returned to the search).

Replay semantics. For each item the genome's conditional memory (thresholds, feature list and fallback
order from the genome) chooses the lead engine from the policy order; the item's outcome is the recorded,
ground-truth-scored outcome of that engine leading under the item's budget:

* dev: the founder-pinned runs of P4 v2's training (both engines, every development item); the memory
  for an item is trained on every *other* development item (leave-one-out), so dev fitness never sees
  the item it scores;
* heldout: P4 v3's fresh held-out items, scored by their recorded fixed-order runs (z3_first, cpsat_first);
  the memory is trained on all development items.

Limit: replay ignores the second engine's fallback (rarely reachable: the lead consumes the budget).
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

from greg.cognition.conditional_competence import ConditionalCompetence, conditions  # noqa: E402

Z3, CPSAT = "cortex.formal.z3@0.2.0", "cortex.optimization.cpsat@0.2.0"
DEV_LOG = ROOT / "docs/evidence/greg-learned-routing/2026-10-07/results-v2.json"
HELDOUT = ROOT / "docs/evidence/greg-learned-routing/2026-10-07/results-v3.json"
SUITE_V3 = ROOT / "cortex/evaluation/learned_routing/suite-v3.json"


class Ordered(ConditionalCompetence):
    """The genome's own fallback order; the frozen module's vocabulary and estimator are unchanged."""

    def __init__(self, records, genome):
        super().__init__(records, min_evidence=genome["min_evidence"], margin=genome["margin"],
                         shrink=genome["shrink"])
        self.order = genome["features"]

    def bind(self, feats):
        other = Ordered([], {"min_evidence": self.min_evidence, "margin": self.margin, "shrink": self.shrink,
                             "features": self.order})
        other.records = self.records
        other.bound = {k: feats[k] for k in self.order if k in feats}
        return other

    def levels(self, method, version, geometry, feats):
        rows = super().levels(method, version, geometry, {})       # global and class
        est = rows[-1]["estimate"]
        present = [k for k in self.order if k in feats]
        for depth in range(1, len(present) + 1):
            fixed = {k: feats[k] for k in present[:depth]}
            s, f = self._counts(method, version, geometry, fixed)
            est = (s + self.shrink * est) / (s + f + self.shrink)
            rows.append({"level": "+".join(present[:depth]), "estimate": est, "n": s + f})
        return rows


def _record(entry):
    feats = dict(c.split("=", 1) for c in entry["conditions"])
    method, _, version = entry["lead"].partition("@")
    return SimpleNamespace(method=method, method_version=version, conditions=tuple(entry["conditions"]),
                           geometry="optimization" if feats.get("kind") == "optimize" else "constraint_feasibility",
                           outcome_status="verified_success" if entry["result"] == "correct" else "observed_failure",
                           competence_update={"weight": 0.6})


def _choose(memory, feats):
    policy = [CPSAT, Z3] if feats.get("kind") == "optimize" else [Z3, CPSAT]
    geometry = SimpleNamespace(epistemic_class="optimization" if feats.get("kind") == "optimize"
                               else "constraint_feasibility")
    return memory.bind(feats).reorder(policy, geometry)[0]


def score(genome: dict, partition: str) -> dict:
    log = [e for e in json.loads(DEV_LOG.read_text())["training"]["runs"] if e.get("result")]
    counts = {"partition": partition, "correct": 0, "wrong": 0, "no_decision": 0, "n": 0, "per_item": []}
    if partition == "dev":
        items = sorted({e["item_id"] for e in log})
        outcomes = {(e["item_id"], e["lead"]): e["result"] for e in log}
        feats_of = {e["item_id"]: dict(c.split("=", 1) for c in e["conditions"]) for e in log}
        for item in items:
            memory = Ordered([_record(e) for e in log if e["item_id"] != item], genome)
            lead = _choose(memory, feats_of[item])
            result = outcomes.get((item, lead), "no_decision")
            counts[result if result in counts else "no_decision"] += 1
            counts["n"] += 1
            counts["per_item"].append(result)
    else:
        from greg.cognition.conditional_competence import features
        suite = {i["item_id"]: i for i in json.loads(SUITE_V3.read_text())["items"]}
        memory = Ordered([_record(e) for e in log], genome)
        for row in json.loads(HELDOUT.read_text())["heldout"]:
            feats = features(suite[row["item_id"]]["problem"]["payload"])
            arm = "z3_first" if _choose(memory, feats) == Z3 else "cpsat_first"
            result = row["arms"][arm]["result"]
            counts[result if result in counts else "no_decision"] += 1
            counts["n"] += 1
            counts["per_item"].append(result)
    return counts


if __name__ == "__main__":
    genome = json.loads(sys.stdin.read())
    print(json.dumps(score(genome, sys.argv[1])))
