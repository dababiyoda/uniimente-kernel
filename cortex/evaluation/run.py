"""Reproducible seed-experiment runner (build prompt items 9 and 11).

    python -m cortex.evaluation.run --freeze                       # write the freeze manifest
    python -m cortex.evaluation.run --partition smoke --out s.json # development runs, no freeze needed
    python -m cortex.evaluation.run --partition heldout --out results.json

The held-out partition is refused unless every frozen input still hashes to the
manifest: cases, scoring rules, arm configuration, generators, route policy,
organ code, budgets, partitions and exit thresholds.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from ..contracts import CORTEX_VERSION, Problem, ResourceLimits, digest
from ..memory import CompetenceLedger
from ..routing import POLICY_VERSION, Cortex
from . import arms as A
from . import scoring as S
from .generators import expand

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SUITES = {"smoke": HERE / "suites" / "smoke-v0.1.json", "dev": HERE / "suites" / "dev-v0.1.json",
          "heldout": HERE / "suites" / "heldout-v0.1.json"}
# One manifest per cortex version; earlier manifests and their results are kept.
MANIFEST = HERE / f"freeze-v{CORTEX_VERSION}.json"
FROZEN_CODE = ["cortex/evaluation/scoring.py", "cortex/evaluation/arms.py", "cortex/evaluation/generators.py",
               "cortex/evaluation/run.py", "cortex/routing.py", "cortex/gates.py", "cortex/genome.py",
               "cortex/contracts.py", "cortex/memory.py", "cortex/organs/formal.py",
               "cortex/organs/estimation.py", "cortex/organs/evidence_causal.py", "cortex/organs/semantic.py",
               "cortex/organs/adversarial.py", "cortex/organs/deterrence.py", "cortex/organs/cpsat.py",
               "cortex/organs/formal_eval.py", "cortex/outcomes.py"]


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def freeze_inputs() -> dict:
    return {
        "suites": {k: {"path": str(v.relative_to(ROOT)), "sha256": _sha(v)} for k, v in SUITES.items()},
        "code": {p: _sha(ROOT / p) for p in FROZEN_CODE},
        "scoring_version": S.SCORING_VERSION, "thresholds": S.THRESHOLDS,
        "overcautious_credit": S.OVERCAUTIOUS_CREDIT, "bootstrap": [S.BOOTSTRAP_B, S.BOOTSTRAP_SEED],
        "route_policy": POLICY_VERSION, "cortex_version": CORTEX_VERSION,
        "default_budget": ResourceLimits().to_dict(),
        "partitions": {"development": ["smoke", "dev"], "reported": ["heldout"]},
        "arms": {"declared_baselines": S.THRESHOLDS["declared_baselines"], "routed": "routed_seed",
                 "references": ["always_abstain"], "committee_roles": list(A.COMMITTEE_ROLES),
                 "baseline_system_prompt_sha256": digest(A.BASELINE_SYSTEM)},
    }


def load_items(partition: str) -> list[dict]:
    data = json.loads(SUITES[partition].read_text(encoding="utf-8"))
    items = []
    for item in data["items"]:
        item = copy.deepcopy(item)
        if item["partition"] != partition:
            raise SystemExit(f"{item['item_id']} is labelled {item['partition']}, not {partition}")
        item["problem"]["payload"] = expand(item["problem"].get("payload", {}))
        items.append(item)
    ids = [i["item_id"] for i in items]
    if len(ids) != len(set(ids)):
        raise SystemExit("duplicate item ids")
    return items


def learning_checks() -> dict:
    """Deterministic checks of item 10 on real receipts: delayed and absent outcomes,
    predictions offered as outcomes, bounded updates, default changes, rollback."""
    cortex = Cortex(clock=lambda: "2026-09-30T00:00:00Z")
    receipt = cortex.run({"problem_id": "learn-1", "question": "Is the pair schedulable?", "payload": {
        "formal_model": {"requirement": "x + y <= 4", "variables": [{"name": "x", "sort": "int", "lo": 0, "hi": 4},
                                                                   {"name": "y", "sort": "int", "lo": 0, "hi": 4}],
                         "obligations": [{"id": "R1", "text": "x + y at most 4"}],
                         "constraints": [{"id": "C1", "covers": ["R1"], "expr": ["<=", ["+", "x", "y"], 4]}]},
        "declared": {"consequence_class": "internal_write", "reversibility": "reversible"}}})
    ledger = CompetenceLedger()
    method, version = "cortex.formal.z3", "0.2.0"
    geometry = receipt["geometry"]["epistemic_class"]
    out = {"receipt_id": receipt["receipt_id"]}
    ledger.settle(receipt=receipt, method=method, method_version=version, outcome_status="absent_feedback",
                  provenance={"kind": "internal_observation"}, attribution=[])
    ledger.settle(receipt=receipt, method=method, method_version=version, outcome_status="unresolved",
                  provenance={"kind": "internal_observation"}, attribution=[])
    out["after_delayed_or_absent"] = ledger.estimate(method, version, geometry)
    try:
        ledger.settle(receipt=receipt, method=method, method_version=version, outcome_status="verified_success",
                      provenance={"kind": "prediction", "validation_status": "externally_verified"},
                      attribution=[{"method": method, "role": "final_answer", "uncertainty": "low"}])
        out["prediction_as_outcome"] = "ACCEPTED (defect)"
    except ValueError as exc:
        out["prediction_as_outcome"] = f"refused: {exc}"
    checkpoint = ledger.head
    for _ in range(6):
        ledger.settle(receipt=receipt, method=method, method_version=version, outcome_status="verified_success",
                      provenance={"kind": "external_observation", "validation_status": "externally_verified"},
                      attribution=[{"method": method, "role": "final_answer", "uncertainty": "low"},
                                   {"method": "cortex.verifier.adversarial", "role": "flaw_detection",
                                    "uncertainty": "medium"}])
    out["after_six_verified"] = ledger.estimate(method, version, geometry)
    out["max_single_update"] = max(abs(r.competence_update["delta"]) for r in ledger.records())
    out["rollback_to_checkpoint"] = ledger.rollback(checkpoint).estimate(method, version, geometry)
    out["registry_unchanged"] = sorted(cortex.registry.keys()) == sorted(Cortex().registry.keys())
    return out


def run(partition: str, arm_names: list[str], *, client_factory=None) -> dict:
    items = load_items(partition)
    manifest = None
    if partition == "heldout":
        if not MANIFEST.exists():
            raise SystemExit("held-out evaluation refused: no freeze manifest")
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        current = freeze_inputs()
        if manifest["inputs"] != current:
            changed = sorted(k for k in current if manifest["inputs"].get(k) != current[k])
            raise SystemExit(f"held-out evaluation refused: frozen inputs changed: {changed}")
    cortex = Cortex(clock=lambda: "2026-09-30T00:00:00Z")
    client, reason = (None, None)
    if any(a in arm_names for a in ("always_llm", "llm_committee")):
        client, reason = A.model_client_or_reason(client_factory)
    results = {"schema": "cortex-seed-results/0.1", "partition": partition, "cortex_version": CORTEX_VERSION,
               "run_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
               "freeze_manifest_sha256": _sha(MANIFEST) if manifest else None,
               "frozen_at": manifest.get("frozen_at") if manifest else None,
               "item_count": len(items), "resource_disclosure": A.RESOURCE_DISCLOSURE, "arms": {}}
    decisions_by_arm: dict[str, list[dict]] = {}
    for name in arm_names:
        if name in ("always_llm", "llm_committee") and client is None:
            results["arms"][name] = {"status": "NOT_RUN", "reason": f"configured local model unavailable: {reason}"}
            continue
        decisions = []
        for item in items:
            try:
                if name == "routed_seed":
                    d = A.routed_seed(item, cortex)
                elif name == "always_llm":
                    d = A.always_llm(item, client)
                elif name == "llm_committee":
                    d = A.llm_committee(item, client)
                elif name == "always_abstain":
                    d = A.always_abstain(item)
                else:
                    raise SystemExit(f"unknown arm {name}")
            except (ValueError, OSError, KeyError, TypeError) as exc:
                d = {"disposition": "error", "answer": None, "error": f"{type(exc).__name__}: {exc}",
                     "latency_s": 0.0, "cost_usd": 0.0, "model_calls": 0, "solver_calls": 0}
            decisions.append(d)
        scored = [S.score_item(i, d) for i, d in zip(items, decisions)]
        decisions_by_arm[name] = scored
        results["arms"][name] = {
            "status": "RUN", "summary": S.summarize(items, scored, decisions),
            "items": [{**s, "state": d.get("state"), "receipt_id": d.get("receipt_id"),
                       "latency_s": round(d.get("latency_s", 0.0), 6), "answer": d.get("answer")}
                      for s, d in zip(scored, decisions)],
        }
        if name == "routed_seed":
            results["representative_receipts"] = {d["receipt"]["problem"]["problem_id"]: d["receipt"]
                                                  for d in decisions[:4] if "receipt" in d}
    routed = decisions_by_arm.get("routed_seed")
    for name, scored in decisions_by_arm.items():
        if name != "routed_seed" and routed is not None:
            results["arms"][name]["paired_gain_vs_routed"] = S.paired_gain(routed, scored)
    results["exit"] = S.exit_verdict(results["arms"])
    results["learning_checks"] = learning_checks()
    return results


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--freeze", action="store_true")
    ap.add_argument("--partition", choices=sorted(SUITES), default="smoke")
    ap.add_argument("--arms", default="routed_seed,always_llm,llm_committee,always_abstain")
    ap.add_argument("--out")
    args = ap.parse_args(argv)
    if args.freeze:
        for p in ("smoke", "dev", "heldout"):
            load_items(p)
        manifest = {"schema": "cortex-freeze/0.1",
                    "frozen_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "inputs": freeze_inputs()}
        MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"frozen: {MANIFEST.relative_to(ROOT)} {_sha(MANIFEST)}")
        return 0
    results = run(args.partition, [a for a in args.arms.split(",") if a])
    text = json.dumps(results, indent=2, sort_keys=True, default=str) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    brief = {k: (v.get("status"), v.get("summary", {}).get("mean_quality"),
                 v.get("summary", {}).get("critical_errors"), v.get("reason"))
             for k, v in results["arms"].items()}
    print(json.dumps({"partition": args.partition, "arms": brief, "exit": results["exit"]}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
