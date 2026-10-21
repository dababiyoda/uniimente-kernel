"""Re-admission of PR #155's control, game, information and probabilistic verdicts on the merged solvers.

#155's admission (``run.py`` here, frozen in ``freeze-v1.json``, seeds 1001-1040) measured these four operation
families on solvers that PR #184 has since replaced with #159's native-qualified ones (greg/cognition/solvers.py and
contracts.py). The evidence index binds each positive verdict to the solver closure it measured, so all four route as
UNEVALUATED until the merged code is measured (greg.cognition.compiler.operation_status). #155's runner cannot measure
it: its freeze pins the old solvers.py, and its geometry (compute_limit 200000) exceeds the merged native ceiling of
100000, so every solver call raises CognitionError.

This runner composes what exists and adds only the adapter between the parts:

* the canonical genome-admission harness (greg/cognition/genomes/admission.py): ``evaluate`` and ``decide`` under its
  ``RULE``, verbatim (that rule routes), its seed refusals and its freeze-then-run discipline;
* #155's four benchmark generators and arms, verbatim, split into an instance and three timed arms. The one declared
  change is ``GEOMETRY``: compute_limit 100000, the merged native ceiling;
* every solver answer behind a candidate output passes greg.cognition.verification.verify; a refuted output is scored
  wrong (the harness scores it below abstaining, so it can never win);
* #155's own ``status()`` on the same held-out rows is recorded as ``rule_155_status`` for comparability. It never
  routes.

The arms are #155's (P-only, pure maximin, always acquire, Jeffreys). They are weaker than the genome library's
strongest competitors for these geometries (pid_simopt, game_lp_dual, bayes_interval), so a verdict here answers
#155's question on the merged code; it is not a strongest-competitor admission.

    --dev FAMILY                       development seeds 0-9 (builders)
    --freeze RUN_ID --heldout-start N  freeze code and protocol before any held-out instance exists
    --run RUN_ID                       run the frozen held-out re-admission once; results are never overwritten
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import platform
import random
import subprocess
import sys
from types import SimpleNamespace
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REPO = ROOT                             # the git repository whose HEAD pre-registers a run (a test may point it elsewhere)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cortex.evaluation.genome_admission import run as run155  # noqa: E402
from greg.cognition.catalog import FAMILIES as CATALOG  # noqa: E402
from greg.cognition.genomes import admission  # noqa: E402
from greg.cognition.solvers import SOLVERS  # noqa: E402
from greg.cognition.verification import verify as verify_answer  # noqa: E402

RUNNER = "cortex/evaluation/genome_admission/run_operations.py"
EVIDENCE = admission.EVIDENCE           # the genome harness's directory: spent_seeds() counts these freezes too
SCHEMA = "greg-operation-admission/1"
FAMILIES = ("control", "game", "information", "probabilistic")
OPERATION = {"control": "pid", "game": "minimax", "information": "value_of_information",
             "probabilistic": "beta_update"}
# #155's GEOMETRY with its one declared change: the merged solvers refuse a compute_limit above 100000 (solvers._work)
GEOMETRY = {**run155.GEOMETRY, "compute_limit": 100000}
HELDOUT_N = 30
# Seeds #155's own runs drew: operations (run.py), repertoire (run_v2.py) and crowd-sparse (pr155_crowd_sparse)
PR155_SEEDS = (*run155.SEEDS, *range(2001, 2041), *range(3001, 3041))
TOLERANCE = 1e-9                         # #155's status() tie margin
ABSTAIN_QUALITY = -1e6                   # below any answer's quality on these four metrics
# #155's status rule, verbatim from run.py's docstring: recorded beside each verdict, it never routes
RULE_155 = ("REJECTED the baseline is better on more items than the candidate, one-sided sign test p < 0.05; "
            "SUPERSEDED the candidate beats the baseline (p < 0.05) but the competitor beats the candidate "
            "(p < 0.05): acquire the competitor (Capability Genesis); DEFAULT_FOR_GEOMETRY the candidate beats the "
            "baseline (p < 0.05) and no competitor beats it (p < 0.05); EXPERIMENTAL otherwise (no demonstrated "
            "difference). Recorded as rule_155_status; it does not route.")


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _call(family, request, calls):
    answer = SOLVERS[family](request, GEOMETRY)
    calls.append((request, answer))
    return answer


# ------------------------------------------------------------------ #155's generators and arms, verbatim, split
def _probabilistic_instance(seed):
    r = random.Random(seed)
    p = r.betavariate(2, 2)
    n = r.randint(1, 8)
    s = sum(r.random() < p for _ in range(n))
    return {"alpha": 1, "beta": 1, "successes": s, "failures": n - s}, {"p": p}


def _probabilistic_metric(data, truth, out):
    """Expected log loss of the predicted next outcome under the true p."""
    p, q = truth["p"], min(max(out["mean"], 1e-6), 1 - 1e-6)
    return -(p * math.log(q) + (1 - p) * math.log(1 - q))


def _probabilistic_candidate(data):
    calls = []
    return _call("probabilistic", data, calls)["output"], calls


def _control_instance(seed):
    r = random.Random(seed)
    a, b, target, umax, dt = r.uniform(.2, 1.0), r.uniform(.5, 2.0), r.uniform(1, 5), 10.0, .1
    noise = [r.gauss(0, .05) for _ in range(120)]
    return {"a": a, "b": b, "target": target, "umax": umax, "dt": dt, "noise": noise}, None


def _control_loop(data, policy):
    """Hold the first-order plant at its set point for 120 steps; integrated absolute error."""
    x, state, iae = 0.0, {}, 0.0
    for t in range(120):
        u, state = policy(x, state)
        x += data["dt"] * (-data["a"] * x + data["b"] * u) + data["noise"][t]
        iae += abs(data["target"] - x) * data["dt"]
    return iae


def _pid_request(data, x, state):
    return {"observed": x, "target": data["target"], "dt": data["dt"], "kp": 2.0, "ki": 1.0, "kd": 0.0,
            "correction_limit": data["umax"], "state": state}


def _control_candidate(data):
    calls = []

    def pid(x, state):
        out = _call("control", _pid_request(data, x, state), calls)["output"]
        return out["correction"], out["state"]
    return {"iae": _control_loop(data, pid)}, calls


def _control_bang_bang(data):
    umax, target = data["umax"], data["target"]
    return {"iae": _control_loop(data, lambda x, state: ((umax if x < target else -umax), state))}


def _control_p_only(data):
    umax, target = data["umax"], data["target"]
    return {"iae": _control_loop(data, lambda x, state: (max(-umax, min(umax, 2.0 * (target - x))), state))}


def _information_instance(seed):
    r = random.Random(seed)
    k = r.randint(2, 4)
    w = [r.random() for _ in range(k)]
    probs = [x / sum(w) for x in w]
    probs[-1] = 1 - sum(probs[:-1])
    best = [round(r.uniform(0, 100), 2) for _ in range(k)]
    prior = round(max(sum(p * b for p, b in zip(probs, best)) - r.uniform(0, 30), 0), 2)
    cost = round(r.uniform(0, 25), 2)
    return {"posterior_scenarios": [{"probability": p, "best_value": b} for p, b in zip(probs, best)],
            "prior_best_value": prior, "cost": cost}, None


def _information_metric(data, truth, out):
    """Negative expected net value of the decision."""
    informed = sum(s["probability"] * s["best_value"] for s in data["posterior_scenarios"]) - data["cost"]
    return -(informed if out["acquire"] else data["prior_best_value"])


def _information_candidate(data):
    calls = []
    return _call("information", data, calls)["output"], calls


def _game_instance(seed):
    r = random.Random(seed)
    m, n = r.randint(2, 6), r.randint(2, 6)
    return {"payoffs": [[round(r.uniform(-5, 5), 2) for _ in range(n)] for _ in range(m)]}, None


def _game_metric(data, truth, out):
    """Negative guaranteed value of the row strategy."""
    a, x = data["payoffs"], out["mixed_strategy"]
    return -min(sum(x[i] * a[i][j] for i in range(len(a))) for j in range(len(a[0])))


def _game_candidate(data):
    calls = []
    return _call("game", data, calls)["output"], calls


def _game_pure_maximin(data):
    a = data["payoffs"]
    pure = max(range(len(a)), key=lambda i: min(a[i]))
    return {"mixed_strategy": [1.0 if i == pure else 0.0 for i in range(len(a))]}


# ------------------------------------------------------------------ the adapter the genome harness reads
@dataclass(frozen=True)
class Operation:
    """One operation family in the shape ``admission.evaluate`` and ``admission.decide`` read."""
    family: str
    instance: Callable[[int], tuple]
    candidate: Callable[[dict], tuple]      # (output, [(solver request, solver answer), ...])
    baseline: Callable[[dict], Any]
    competitor: Callable[[dict], Any]
    metric: Callable[[dict, Any, Any], float]   # #155's metric: lower is better
    names: tuple                            # #155's (candidate, baseline, competitor) names
    request: Callable[[dict], dict] = lambda data: data   # an instance's first solver request (canonical-path smoke)
    subregion = None
    tolerance = TOLERANCE

    @property
    def genome(self):
        return SimpleNamespace(intelligence_id=f"operation.{self.family}", standalone_decision=True,
                               operation=OPERATION[self.family])

    def solve(self, data, _budget):
        """The merged solver at ``GEOMETRY``; the solver calls behind the output are its certificate."""
        output, calls = self.candidate(data)
        unanswered = [answer for _, answer in calls if answer["status"] != "ANSWER"]
        if unanswered:
            return {"output": None, "certificate": calls, "status": "UNKNOWN",
                    "missing": unanswered[0]["missing_information"]}
        return {"output": output, "certificate": calls, "status": "ANSWER", "missing": []}

    def verify(self, data, output, certificate):
        """greg.cognition.verification.verify on every solver call behind the output; one refutation refutes it."""
        verdicts = [verify_answer(self.family, request, answer, CATALOG[self.family][3])["verdict"]
                    for request, answer in certificate]
        passed = sum(v == "STRUCTURALLY_VERIFIED" for v in verdicts)
        return {"structurally_verified": bool(verdicts) and passed == len(verdicts),
                "detail": f"{passed} of {len(verdicts)} solver calls STRUCTURALLY_VERIFIED"}

    def score(self, data, truth, output):
        if output is None:
            return {"quality": ABSTAIN_QUALITY, "category": "abstain"}
        # an answered arm is scored by #155's metric; "wrong" is reserved for a refuted candidate output
        return {"quality": -self.metric(data, truth, output), "category": "correct"}


ITEMS = {
    "control": Operation("control", _control_instance, _control_candidate, _control_bang_bang, _control_p_only,
                         lambda data, truth, out: out["iae"], ("PID kp=2 ki=1", "bang-bang", "P-only kp=2"),
                         request=lambda data: _pid_request(data, 0.0, {})),
    "game": Operation("game", _game_instance, _game_candidate,
                      lambda data: {"mixed_strategy": [1 / len(data["payoffs"])] * len(data["payoffs"])},
                      _game_pure_maximin, _game_metric, ("minimax LP", "uniform mix", "pure maximin")),
    "information": Operation("information", _information_instance, _information_candidate,
                             lambda data: {"acquire": False}, lambda data: {"acquire": True}, _information_metric,
                             ("value-of-information rule", "never acquire", "always acquire")),
    "probabilistic": Operation(
        "probabilistic", _probabilistic_instance, _probabilistic_candidate,
        lambda data: {"mean": min(max(data["successes"] / (data["successes"] + data["failures"]), 0.02), 0.98)},
        lambda data: {"mean": (data["successes"] + 0.5) / (data["successes"] + data["failures"] + 1)},
        _probabilistic_metric, ("Beta(1,1) posterior mean", "clipped MLE", "Jeffreys posterior mean")),
}


def rule_155(rows) -> dict:
    """#155's ``status()`` on the same rows. Its metric is the negated quality, so its wins and ties are the
    canonical comparison's (an abstention or a refuted output keeps its penalty)."""
    return run155.status([{arm: -r["arms"][arm]["quality"] for arm in ("candidate", "baseline", "competitor")}
                          for r in rows])


def inputs(heldout) -> dict:
    """Everything the run executes or reads (the import closure of this runner, the genome harness and the isolated
    worker, all of ``greg/cognition``, the requirement files, the dependency versions) and the protocol: both rules,
    the seeds, families, geometry, arms and scoring constants."""
    from cortex.evaluation.closure import code_closure, dependency_versions
    files = code_closure((RUNNER, "greg/cognition/genomes/admission.py", "greg/cognition/worker.py"),
                         packages=("greg/cognition",), extra=("requirements-cortex.txt", "requirements-cognition.txt"),
                         root=ROOT)
    return {"rule": admission.RULE, "rule_155": RULE_155, "dev_seeds": list(admission.DEV_SEEDS),
            "heldout_seeds": list(heldout), "families": list(FAMILIES), "operations": dict(OPERATION),
            "geometry": dict(GEOMETRY), "arms": {f: list(ITEMS[f].names) for f in FAMILIES},
            "tolerance": TOLERANCE, "abstain_quality": ABSTAIN_QUALITY,
            "code": {p: _sha(ROOT / p) for p in files}, "dependencies": dependency_versions()}


def smoke(family: str, seed: int) -> dict:
    """An instance's first solver request through GREG's canonical cognition path, with the family attached in an
    evaluation-only registry view (as the genome harness's smoke does); nothing is attached on any body."""
    from greg.cognition.cortex import reason, registry_view
    item = ITEMS[family]
    data, _ = item.instance(seed)
    registry = registry_view()
    cid = f"cognition.{family}"
    if cid not in registry.manifests:
        return {"state": "NOT_REGISTERED", "capability": cid}
    registry.set_state(cid, "ATTACHED")
    receipt = reason({"problem_id": f"readmission:{family}", "operation": OPERATION[family],
                      "data": item.request(data), "geometry": {"latency_limit": 30}}, registry=registry)
    return {"capability": cid, "abstention_state": receipt["abstention_state"], "method": receipt["method"],
            "verifier": receipt["evaluator_result"].get("verdict"), "proof_type": receipt["proof_type"],
            "latency_s": round(receipt["latency"], 4), "authority_created": receipt["authority_created"],
            "receipt_id": receipt["receipt_id"]}


def refusals(heldout, exclude: Path | None = None) -> list[str]:
    """Why these held-out seeds may not be used: development, P8-reserved, spent by another admission freeze
    (``exclude`` is this run's own directory) or drawn by a #155 run. A negative seed is refused outright, because
    ``random.Random(-s)`` is seeded exactly as ``random.Random(s)`` and would redraw a refused instance."""
    seeds = set(heldout)
    out = [f"negative seeds ({min(seeds)}): random.Random(-s) draws the same instances as s"] if min(seeds) < 0 else []
    refused = {"development": set(admission.DEV_SEEDS), "P8-reserved": set(admission.P8_RESERVED),
               "spent by an earlier admission freeze": admission.spent_seeds(exclude),
               "drawn by a #155 run": set(PR155_SEEDS)}
    return out + [f"{why} ({min(used & seeds)}-{max(used & seeds)})" for why, used in refused.items() if used & seeds]


def preregistration(target: Path) -> dict:
    """Bind a run to its pre-registration. A run directory inside the repository is the only kind the evidence index
    can cite, so there the freeze must be committed at HEAD unchanged and the tree clean outside the run directory, or
    the run is refused: the results' source_commit is then the commit that pre-registered them. A directory outside
    the repository (a test's) is recorded as not pre-registered."""
    try:
        rel = target.resolve().relative_to(REPO.resolve()).as_posix()
    except ValueError:
        return {"pre_registered": False, "reason": "the run directory is outside the repository"}

    def git(*args):
        return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True)

    manifest = f"{rel}/freeze.json"
    if git("cat-file", "-e", f"HEAD:{manifest}").returncode:
        raise SystemExit("NOT_PRE_REGISTERED: commit freeze.json before the run")
    if git("diff", "--quiet", "HEAD", "--", manifest).returncode:
        raise SystemExit("NOT_PRE_REGISTERED: freeze.json differs from the committed pre-registration")
    dirty = [line for line in git("status", "--porcelain", "--untracked-files=all").stdout.splitlines()
             if not line[3:].strip('"').startswith(f"{rel}/")]
    if dirty:
        raise SystemExit(f"NOT_PRE_REGISTERED: uncommitted changes outside the run directory ({dirty[0][3:]})")
    added = git("log", "--diff-filter=A", "-1", "--format=%H", "--", manifest).stdout.strip()
    return {"pre_registered": True, "freeze_commit": added}


def freeze(run_id: str, start: int) -> Path:
    target = EVIDENCE / run_id
    manifest = target / "freeze.json"
    if manifest.exists():
        raise SystemExit("refusing to overwrite an existing re-admission freeze; use a new run id")
    heldout = tuple(range(start, start + HELDOUT_N))
    clash = refusals(heldout)
    if clash:
        raise SystemExit(f"held-out seeds refused, {'; '.join(clash)}: choose fresh ones")
    target.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps({"frozen_at": datetime.now(timezone.utc).isoformat(), "inputs": inputs(heldout)},
                                   indent=2) + "\n")
    return manifest


def run(run_id: str) -> dict:
    target = EVIDENCE / run_id
    frozen = json.loads((target / "freeze.json").read_text())
    heldout = tuple(frozen["inputs"]["heldout_seeds"])
    if frozen["inputs"] != inputs(heldout):
        raise SystemExit("FROZEN_INPUT_CHANGED: re-admission results cannot be reported")
    if (target / "results.json").exists():
        raise SystemExit("refusing to overwrite re-admission results")
    binding = preregistration(target)
    clash = refusals(heldout, exclude=target)
    if clash and binding["pre_registered"]:
        raise SystemExit(f"held-out seeds refused, {'; '.join(clash)}")
    # "families", never "genomes": the evidence index reads this file through OPERATION_RUNS, not as a genome run
    report = {"schema": SCHEMA, "freeze_sha256": _sha(target / "freeze.json"),
              "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
              **binding, "seed_refusals": clash,
              "platform": platform.platform(), "python": sys.version.split()[0], "rule": admission.RULE,
              "rule_155": RULE_155, "geometry": GEOMETRY, "families": {}}
    for family in frozen["inputs"]["families"]:
        item = ITEMS[family]
        rows = admission.evaluate(item, heldout)
        status, detail = admission.decide(item, rows)
        try:
            canonical = smoke(family, heldout[0])
        except Exception as exc:       # recorded, never hidden; a failing smoke blocks DEFAULT below
            canonical = {"state": "SMOKE_FAILED", "error": f"{type(exc).__name__}: {str(exc)[:300]}"}
        if canonical.get("verifier") != "STRUCTURALLY_VERIFIED":
            status = {"DEFAULT_FOR_GEOMETRY": "NICHE_CAPABILITY"}.get(status, status)
        lineage = rule_155(rows)
        report["families"][family] = {"operation": OPERATION[family], "candidate": item.names[0],
                                      "baseline": item.names[1], "competitor": item.names[2], "n": len(rows),
                                      "status": status, **detail, "rule_155_status": lineage["status"],
                                      "rule_155": lineage, "canonical_path": canonical, "heldout": rows}
        print(json.dumps({"family": family, "status": status, "rule_155_status": lineage["status"],
                          "vs_baseline": detail["vs_baseline"], "vs_competitor": detail["vs_competitor"]}), flush=True)
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    (target / "results.json").write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps({f: g["status"] for f, g in report["families"].items()}, indent=1))
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--dev", metavar="FAMILY", choices=FAMILIES, help="run development seeds for one family")
    ap.add_argument("--freeze", metavar="RUN_ID", help="freeze code and protocol under the admission evidence tree")
    ap.add_argument("--heldout-start", type=int, help=f"first of {HELDOUT_N} fresh held-out seeds (with --freeze)")
    ap.add_argument("--run", metavar="RUN_ID", help="run the frozen held-out re-admission")
    args = ap.parse_args(argv)
    if args.dev:
        item = ITEMS[args.dev]
        rows = admission.evaluate(item, admission.DEV_SEEDS)
        status, detail = admission.decide(item, rows)
        print(json.dumps({"family": args.dev, "partition": "dev", "status_if_heldout_matched": status,
                          "rule_155_status": rule_155(rows)["status"], **detail}, indent=1))
        return
    if args.freeze:
        if args.heldout_start is None:
            raise SystemExit("--freeze needs --heldout-start: held-out seeds are pre-registered, never defaulted")
        print(freeze(args.freeze, args.heldout_start))
        return
    if not args.run:
        raise SystemExit("--dev, --freeze or --run required")
    run(args.run)


if __name__ == "__main__":
    main()
