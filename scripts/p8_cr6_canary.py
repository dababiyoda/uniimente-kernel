"""Canary for P8 cycle 6's kept proposal on the constraint-release target: a measurement, never an adoption.

Cycle 6 (2026-10-21) RETAINed a search configuration of ``develop_constraint_release`` 1.2.0 (``p_restart`` 0.807) as
PROPOSED_NOT_APPLIED. Its proposal names a canary before any adoption. This script measures, once, on fresh seeds
no freeze, cycle, admission run or pilot has generated (``evolution.CR_CANARY_SEEDS["cycle-6"]``, 8300-8539):

* the incumbent ``CR_DEFAULT_CONFIG`` (unchanged; nothing here edits it);
* the proposed configuration, read from the cycle-6 record;
* random restart, the target's baseline and admission competitor.

Every loss is the cycle's loss (``SealedEvaluator.losses`` over ``constraint_release_score``) on the output of
``constraint_release_solve_with`` (the sandbox's method) or ``constraint_release_random_restart``, run in this process.
Stress items come from the cycle's ``_cr_stress``, and every stress answer is checked by the target's verifier. The
decision rules are declared in ``PREREGISTRATION.md`` beside the output and in ``decide`` below, before any canary
instance is generated. The run refuses a dirty tree, an existing output and any seed outside the frozen range
(development seeds 0-9 are accepted for tests only, and are never written as evidence).

    PYTHONPATH=. taskset -c 1 python scripts/p8_cr6_canary.py \\
        --out docs/evidence/greg-protected-evolution/2026-10-16-cr-6/canary/canary.json
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import p8_cr_pilot as P                                         # noqa: E402
from greg.cognition import evolution as E                      # noqa: E402
from greg.cognition.genomes import developmental as D          # noqa: E402

RECORD = ROOT / "docs/evidence/greg-protected-evolution/2026-10-16-cr-6/cycle-cr-6.json"
SEEDS = E.CR_CANARY_SEEDS["cycle-6"]
SCHEMA = "greg-p8-canary/1"


class CanaryError(ValueError):
    pass


def guard(seeds) -> tuple:
    """The frozen canary seeds, or development seeds 0-9 (tests); anything else is refused."""
    seeds = tuple(seeds)
    if seeds != SEEDS and not (seeds and all(type(s) is int and s in P.DEV_SEEDS for s in seeds)):
        raise CanaryError(f"the canary measures exactly seeds {SEEDS[0]}-{SEEDS[-1]} (development 0-9 in tests)")
    return seeds


def items(seeds) -> dict:
    out = {}
    for s in guard(seeds):
        data, truth = D.constraint_release_instance(s)
        out[f"c{s}"] = {"data": data, "truth": truth, "category": D.constraint_release_subregion(data)}
    return out


def proposal() -> dict:
    record = json.loads(RECORD.read_text())
    if record["decision"] != "RETAIN" or record["proposal"]["state"] != "PROPOSED_NOT_APPLIED":
        raise CanaryError("the cycle-6 record carries no pending proposal")
    if record["proposal"]["change"]["from"] != D.CR_DEFAULT_CONFIG:
        raise CanaryError("the incumbent changed since cycle 6: the proposal no longer applies to it")
    return record["proposal"]["change"]["to"]


def _paired_mean(a: dict, b: dict) -> dict:
    out = P.paired(a, b)
    return {**out, "mean_a": P.mean(a.values()), "mean_b": P.mean(b.values())}


def decide(vs_incumbent: dict, vs_restart: dict, stress_ok: bool) -> dict:
    """Declared before any canary instance was generated (PREREGISTRATION.md)."""
    replicates = (vs_incumbent["sign_test_p_one_sided"] < E.ALPHA and vs_incumbent["mean_a"] < vs_incumbent["mean_b"]
                  and stress_ok)
    restart_better = (vs_restart["losses"] > vs_restart["wins"]
                      and E.sign_test(vs_restart["losses"], vs_restart["wins"]) < E.ALPHA
                      and vs_restart["mean_b"] < vs_restart["mean_a"])
    if not replicates:
        verdict = "CANARY_FAILS"
    elif restart_better:
        verdict = "CANARY_PASSES_BUT_RANDOM_RESTART_IS_BETTER"
    else:
        verdict = "CANARY_PASSES"
    return {"verdict": verdict, "replicates_against_incumbent": replicates, "stress_ok": stress_ok,
            "random_restart_significantly_better": restart_better, "applied": False}


def measure(seeds) -> dict:
    pilot = P.Pilot()
    target = pilot.target
    proposed = target.validate(proposal())
    incumbent = target.validate(dict(D.CR_DEFAULT_CONFIG))
    its = items(seeds)
    loss = {"incumbent": pilot.losses(incumbent, its), "proposed": pilot.losses(proposed, its),
            "random_restart": pilot.losses("random_restart", its)}
    stress_items = E._cr_stress(its)
    stress, verified = {}, True
    for name, config in (("incumbent", incumbent), ("proposed", proposed)):
        outputs = {k: pilot._output(config, v["data"]) for k, v in stress_items.items()}
        verified &= all(all(D.constraint_release_verify(stress_items[k]["data"], o["output"],
                                                        o["certificate"]).values())
                        for k, o in outputs.items() if o.get("output") is not None)
        losses = E.SealedEvaluator(stress_items, D.constraint_release_score).losses(outputs)
        stress[name] = {kind: P.mean(v for k, v in losses.items() if k.startswith(kind + ":"))
                        for kind in ("lean", "fewval")}
    stress_ok = verified and not any(E.worsened(stress["incumbent"][k], stress["proposed"][k])
                                     for k in ("lean", "fewval"))
    vs_incumbent = _paired_mean(loss["proposed"], loss["incumbent"])
    vs_restart = _paired_mean(loss["proposed"], loss["random_restart"])
    by_category: dict = {}
    for k, item in its.items():
        by_category.setdefault(item["category"], []).append(k)
    return {"n": len(its), "incumbent": {"id": E.config_id(incumbent), "config": incumbent},
            "proposed": {"id": E.config_id(proposed), "config": proposed},
            "mean_loss": {k: P.mean(v.values()) for k, v in loss.items()},
            "proposed_vs_incumbent": vs_incumbent, "proposed_vs_random_restart": vs_restart,
            "random_restart_vs_incumbent": _paired_mean(loss["random_restart"], loss["incumbent"]),
            "stress": {**stress, "all_outputs_verified": verified},
            "by_category": {c: {"n": len(ks), **{a: P.mean(loss[a][k] for k in ks) for a in loss}}
                            for c, ks in sorted(by_category.items())},
            "decision": decide(vs_incumbent, vs_restart, stress_ok)}


def _git(*args) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    if args.out.exists():
        raise SystemExit(f"{args.out} exists: the canary runs once")
    dirty = _git("status", "--porcelain")
    if dirty:
        raise SystemExit(f"DIRTY_TREE: commit before the canary runs:\n{dirty}")
    started = time.time()
    result = {"schema": SCHEMA, "started_at": datetime.now(timezone.utc).isoformat(), "source_commit": _git(
        "rev-parse", "HEAD"), "seeds": [SEEDS[0], SEEDS[-1]], "python": platform.python_version(),
        **measure(SEEDS), "seconds": None, "authority_created": False}
    result["seconds"] = round(time.time() - started, 1)
    args.out.write_text(json.dumps(result, indent=1) + "\n")
    print(json.dumps({"out": str(args.out), "verdict": result["decision"]["verdict"], "seconds": result["seconds"]}))


if __name__ == "__main__":
    main()
