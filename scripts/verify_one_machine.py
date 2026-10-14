"""Independent re-derivation of a one-machine mission from retained evidence.

Run as its own process after the body has stopped (it never takes the writer lock):

    python scripts/verify_one_machine.py --home HOME --mission MISSION_ID \\
        [--wealthmachine-root DIR --wealthmachine-python PY] --out REPORT.json

What it re-derives, and from what (the producer's claims are inputs to check, never accepted):

1. GREG's own separate-process appraisal (``python -m greg.appraisal``) over the head-pinned ledger:
   signature, receipts, re-observation, exactly-once, approval and precondition boundaries.
2. The Mind's answer, by exhaustive search written here with no GREG import: the certified
   ``staffed`` value must equal the true optimum of the problem the founder signed, and the
   certified assignment must be feasible.
3. The worker's change: a fresh clone of the sandbox repository at the recorded base, the retained
   patch re-applied (its digest must match the receipt), and the patch's own test re-run.
4. The organs' answer: the DALEOBANKS packet retained in the ledger is re-evaluated by
   WealthMachine's own code in its own interpreter (no signature involved) and compared with the
   retained WealthMachine answer; both organs' messages must be transport-verified on one trace,
   bound to a DONE exchange receipt, and judged REPRODUCED. Without a WealthMachine checkout the
   verdict is NOT_REDERIVED: a skipped re-derivation is never a pass.
5. Exactly one receipted DONE commission and one worker commit, despite the interruption, which the
   founder reconciled (either answer) instead of a blind retry. A commission reconciled as executed has
   no receipt, so its work is reported as not re-derivable, never counted as the commission.
6. VEPMC stays 0: this is sandbox integration proof, not a founder-accepted closure.

Limits: it runs on the same host as the body and reads the same files; it is a separate process
with separate code for the re-derivations, not a separate machine or organization.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from greg import metrics, organ_bridge, routing  # noqa: E402
from greg.body import Layout, observe  # noqa: E402

SUMMARY = ("go_no_go", "opportunity_score", "market_alignment", "risk_level", "legal_readiness",
           "requires_human_approval", "validation_plan", "reasons")

REEVALUATE = r'''
import json, sys
from src.services.opportunity_intake import OpportunityIntakeService
print(json.dumps(OpportunityIntakeService().evaluate_packet(json.loads(sys.stdin.read())), sort_keys=True))
'''


def optimum(problem: dict) -> int:
    """The largest number of staffed units any feasible assignment achieves (exhaustive)."""
    workers = {w["id"]: w for w in problem["workers"]}
    orders = {o["id"]: o for o in problem["orders"]}
    pairs = [(w, o) for w in workers for o in orders if orders[o]["skill"] in workers[w]["skills"]]
    best = 0
    for units in itertools.product(*[range(min(workers[w]["capacity"], orders[o]["demand"]) + 1) for w, o in pairs]):
        used, served = {}, {}
        for (w, o), u in zip(pairs, units):
            used[w] = used.get(w, 0) + u
            served[o] = served.get(o, 0) + u
        if all(used[w] <= workers[w]["capacity"] for w in used) and \
                all(served[o] <= orders[o]["demand"] for o in served):
            best = max(best, sum(units))
    return best


def feasible(problem: dict, assignment: list) -> bool:
    workers = {w["id"]: w for w in problem["workers"]}
    orders = {o["id"]: o for o in problem["orders"]}
    used, served = {}, {}
    for worker, order, units in assignment:
        if worker not in workers or order not in orders or units <= 0 \
                or orders[order]["skill"] not in workers[worker]["skills"]:
            return False
        used[worker] = used.get(worker, 0) + units
        served[order] = served.get(order, 0) + units
    return all(used[w] <= workers[w]["capacity"] for w in used) and \
        all(served[o] <= orders[o]["demand"] for o in served)


def commission_outcomes(actions: list[dict], ledger) -> dict:
    """The commission's records, judged by retained evidence: a DONE counts only with its receipt on the
    ledger; a founder reconciliation of either answer shows the interruption was not retried blind."""
    ours = [x for x in actions if x["action_id"] == "commission"]

    def receipted(x) -> bool:
        record = ledger.find(x["receipt"]) if x.get("receipt") else None
        return record is not None and record.record_type == "receipt"
    executed = [x for x in ours if x["status"] == "DONE" and routing.founder_reconciled(x)]
    return {"done": [x for x in ours if x["status"] == "DONE" and receipted(x)],
            "reconciled": [x for x in ours if x["status"] == "RECONCILED_NOT_EXECUTED"] + executed,
            "reconciled_executed": executed}


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=300, **kw)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--home", required=True)
    ap.add_argument("--mission", required=True)
    ap.add_argument("--wealthmachine-root")
    ap.add_argument("--wealthmachine-python")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    home = Path(a.home).resolve()
    layout = Layout(home)
    config = json.loads(layout.config.read_text())
    report, findings = {"mission_id": a.mission, "checks": {}}, []
    checks = report["checks"]

    with observe(home, actor="spiffe://uniimente.internal/greg/one-machine-verifier") as journal:
        ledger = journal.ledger
        head = ledger.head
        [registered] = [e.payload for e in journal.replay("mission.registered") if e.payload["mission_id"] == a.mission]
        spec = registered["spec"]
        strategies = {s["action_id"]: s for s in spec["strategies"]}
        observed = [e.payload for e in journal.replay("mission.observed") if e.payload["mission_id"] == a.mission]
        actions = [e.payload for e in journal.replay("mission.action") if e.payload["mission_id"] == a.mission]

        def passing_output(check_id):
            rows = [o for o in observed if o["check_id"] == check_id and o.get("passed") and o.get("receipt")]
            record = ledger.find(rows[-1]["receipt"]) if rows else None
            return record.payload["result"].get("output") if record is not None else None

        # 2. the Mind's certified answer against an exhaustive optimum of the signed problem
        problem = strategies["compile"]["params"]["compile"]["data"]
        answer = passing_output("answered") or {}
        result = answer.get("result") or {}
        truth = optimum(problem)
        checks["mind_answer_is_optimal"] = result.get("staffed") == truth
        checks["mind_assignment_feasible"] = feasible(problem, result.get("assignment", []))
        checks["mind_used_no_model"] = (answer.get("cost") or {}).get("model_calls") == 0
        if not checks["mind_answer_is_optimal"]:
            findings.append(f"certified staffed={result.get('staffed')} but the exhaustive optimum is {truth}")

        # 5. exactly one receipted DONE commission despite the interruption
        commissions = commission_outcomes(actions, ledger)
        done = commissions["done"]
        checks["one_commission_done"] = len(done) == 1
        checks["interruption_reconciled_not_retried_blind"] = len(commissions["reconciled"]) >= 1
        for x in commissions["reconciled_executed"]:
            findings.append(f"commission attempt {x.get('attempt')} was reconciled by the founder as executed "
                            "without a receipt; its work cannot be re-derived from retained evidence")
        receipt = ledger.find(done[0]["receipt"]).payload["result"]["output"] if done else {}
        work = strategies["commission"]["params"]

        # 4. organs: both organs, transport-verified on one trace, bound to a DONE exchange receipt, judged
        #    REPRODUCED; and WealthMachine re-evaluates the retained packet here
        bound = organ_bridge.bound_facts(journal, a.mission)
        organs = bound["observed"]
        checks["organ_messages_transport_verified"] = ({o["organ"] for o in organs} >= {"daleobanks", "wealthmachine"}
                                                      and all(o["transport_verified"] for o in organs))
        checks["organ_messages_one_trace"] = len({o["trace_id"] for o in organs}) == 1
        checks["organ_appraisal_reproduced"] = bool(bound["appraisals"]) and \
            bound["appraisals"][-1]["verdict"] == "REPRODUCED"
        retained = {e.payload["content_sha256"]: e.payload["content"] for e in journal.replay("external.ingested")}
        by_organ = {o["organ"]: retained.get(o["content_sha256"]) for o in organs}
        if a.wealthmachine_root and a.wealthmachine_python and by_organ.get("daleobanks") and by_organ.get("wealthmachine"):
            proc = run([a.wealthmachine_python, "-s", "-c", REEVALUATE], input=by_organ["daleobanks"],
                       cwd=a.wealthmachine_root, env={"PATH": "/usr/bin:/bin", "HOME": tempfile.gettempdir()})
            if proc.returncode:
                checks["organ_answer_rederived"] = False
                findings.append("WealthMachine re-evaluation failed: " + proc.stderr[-300:])
            else:
                again, original = json.loads(proc.stdout), json.loads(by_organ["wealthmachine"])
                diff = [k for k in SUMMARY if again.get(k) != original.get(k)]
                checks["organ_answer_rederived"] = not diff
                if diff:
                    findings.append(f"WealthMachine re-evaluation differs on {diff}")
        else:   # skipping a re-derivation is never a pass
            checks["organ_answer_rederived"] = False
            findings.append("organ re-derivation not run (no WealthMachine checkout given or bodies not retained)")

        # 1. GREG's own appraiser, as a separate process over the same head
        request = {"ledger": str(layout.ledger), "constitution": config["constitution_hash"], "head": head,
                   "mission_id": a.mission, "read_roots": config.get("read_roots", []),
                   "deliver_root": str(config.get("deliver_root") or home / "deliveries"),
                   "artifact_root": str(layout.artifacts),
                   "workspace": str(layout.workspace / a.mission.replace(":", "_"))}
        sandbox = metrics.sandbox_whole_machine(journal)
        report["vepmc"] = metrics.vepmc(journal)["VEPMC"]
        report["sandbox_whole_machine"] = [r for r in sandbox["missions"] if r["mission_id"] == a.mission]
        report["ledger_head"] = head
        checks["ledger_chain_intact"] = ledger.verify_chain()[0]

    appraiser = run([sys.executable, "-m", "greg.appraisal"], input=json.dumps(request), cwd=ROOT,
                    env={"PATH": "/usr/bin:/bin", "PYTHONPATH": os.pathsep.join([str(ROOT)] + [p for p in sys.path
                                                                                             if "-packages" in p])})
    appraisal = json.loads(appraiser.stdout) if appraiser.returncode == 0 else {"verdict": "APPRAISAL_FAILED",
                                                                                "findings": [appraiser.stderr[-400:]]}
    report["greg_appraisal"] = appraisal
    checks["greg_appraisal_verified"] = appraisal.get("verdict") == "VERIFIED"

    # 3. the worker's change: fresh clone, retained patch re-applied, its own test re-run
    order_dir = layout.workspace / a.mission.replace(":", "_") / "work-orders" / work["order"]
    patch = order_dir / "change.patch"
    if patch.exists() and receipt:
        digest = hashlib.sha256(patch.read_bytes()).hexdigest()
        checks["patch_matches_receipt"] = receipt.get("patch_sha256") in (digest, "sha256:" + digest)
        with tempfile.TemporaryDirectory() as tmp:
            clone = Path(tmp) / "c"
            env = {"PATH": "/usr/bin:/bin", "HOME": tmp, "GIT_CONFIG_NOSYSTEM": "1"}
            ok = run(["git", "clone", "-q", "--no-hardlinks", work["repo"], str(clone)], env=env).returncode == 0
            evidence = json.loads((order_dir / "evidence.json").read_text()) if (order_dir / "evidence.json").exists() else {}
            base = evidence.get("base_commit") or evidence.get("base") or "HEAD"
            ok = ok and run(["git", "-C", str(clone), "checkout", "-q", "--detach", base], env=env).returncode == 0
            ok = ok and run(["git", "-C", str(clone), "apply", str(patch)], env=env).returncode == 0
            tests = run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests/test_plan.py"],
                        cwd=clone, env={"PATH": "/usr/bin:/bin", "HOME": tmp, "PYTHONDONTWRITEBYTECODE": "1"}) \
                if ok else None
            checks["patch_reapplies_and_its_test_passes"] = bool(ok and tests and tests.returncode == 0)
            if not checks["patch_reapplies_and_its_test_passes"]:
                findings.append("worker patch did not re-apply or its test failed: "
                                + ((tests.stdout + tests.stderr)[-400:] if tests else "clone/apply failed"))
            branches = run(["git", "-C", str(clone), "branch", "-a"], env=env).stdout
        checks["no_duplicate_worker_branch_in_source"] = "greg/" not in branches   # GREG commits only in its clone
    else:
        checks["patch_matches_receipt"] = checks["patch_reapplies_and_its_test_passes"] = False
        findings.append("no retained patch or commission receipt")

    checks["vepmc_not_inflated"] = report["vepmc"] == 0
    required = [k for k, v in checks.items() if v is not None]
    report["verdict"] = "REDERIVED" if all(checks[k] for k in required) else "NOT_REDERIVED"
    report["findings"] = findings
    report["tier"] = "sandbox integration proof on a synthetic-authority test body; not VEPMC, not founder acceptance"
    Path(a.out).write_text(json.dumps(report, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({"verdict": report["verdict"], "failed": [k for k in required if not checks[k]],
                      "findings": findings}, indent=1))
    return 0 if report["verdict"] == "REDERIVED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
