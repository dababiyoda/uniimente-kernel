"""P6 v6: does the admitted single genome flow_expansion_mcf match the routed composition on F7's real items?

A declared RE-USE of P6 v4's held-out items (``suite-v4.json``), not a new family. In v4, the routed composition
``graph_then_allocate`` (compile -> CP-SAT -> max-flow cross-check) was optimal on 200 of 200 held-out items, and
parametric min-cost flow (PMCF, the truth algorithm, in process) tied it. The Track B audit (``49b2d58``/``8bbd3b8``
on ``claude/greg-mind-lineage-convergence``) rebuilt those 200 items independently and re-scored v4's recorded
plans; it did not run the genome. Afterwards the single genome ``flow_expansion_mcf``
(``solver.graph.capacity_expansion_mcf`` 1.0.0: successive shortest paths with a duality or cut certificate) was
admitted DEFAULT_FOR_GEOMETRY in admission v3 against the graph_then_allocate twin, on 30 SYNTHETIC instances
(seeds 1200-1229). The Competency Compiler now treats it as canonical for this geometry while that verdict is current
(``greg.cognition.compiler._matched_by_single_genome``). It was never run on F7's real items. The
pre-registration is ``prereg-v6.json``.

QUESTION. On F7's held-out items, does flow_expansion_mcf, served through GREG's canonical path
(``greg.cognition.cortex.reason``: an isolated solver worker and an independent verifier), decide every item, give
no wrong answer, not be significantly worse than the routed composition, and stay within 1.25x its median latency?
The rule is ``RULE`` (conditions ``CONDITIONS``, deviations from admission v3 ``DEVIATIONS``), decided by
``decide(rows)``.

Arms (every GREG arm through ``cortex.reason``, one evaluation-only registry view: run_v4's four attached families
plus ``cognition.flow_expansion_mcf``, attached in memory only):

* ``flow_expansion_mcf``         primary: ``{operation: expand_capacity_mcf, data: <network>}``, the same 20 s
                                 single-operation geometry run_v4 gives its constituents. A receipt the independent
                                 verifier REFUTED is scored wrong whatever its plan (as admission v3 scores it).
* ``routed_composition``         comparator: run_v4's chain without a pinned recipe, re-run on this machine so
                                 that latencies are comparable (v4's own latencies are not re-used).
* ``compiled``                   secondary: run_v4's ``{compile: {geometry, data: {capacity_network}}}`` request,
                                 with the genome attached and the current evidence index; its selected method is
                                 recorded.
* ``parametric_min_cost_flow``   secondary: the truth algorithm and practitioner, in process (latency not
                                 comparable with the GREG arms).

Scoring. Primary: ``run_v4.f7_score`` (imported) against v4's suite truth. Secondary and independent: every arm's
plan and every item's truth are re-scored by code that calls nothing in ``greg/cognition/genomes/flow.py`` or
``run_v4``: SciPy's ``maximum_flow`` on capacity plus leased units, the budget and per-arc limit checked from the item
data, and the optimum re-solved as a mixed-integer program by HiGHS (``scipy.optimize.milp``, gap 0). This mirrors
the Track B audit's method (``cortex/evaluation/pr155_f7_audit/audit.py`` at ``49b2d58``, not on this branch). A
disagreement on a rule arm or a truth makes the outcome INCONCLUSIVE, except a disagreement on the plan of a genome
receipt the verifier REFUTED: the refutation scores that row wrong whatever its plan scores. A disagreement on a
secondary arm (compiled, PMCF) is reported and makes the run informative; it does not change the outcome.

Secondary decision ``F7_LIFT_WITH_GENOME`` (``f7_lift_with_genome``): v4's frozen F7 rule (``run_v4.VERDICT_RULE``)
re-evaluated with flow_expansion_mcf as a third constituent beside v4's two, whose optimal and wrong counts are read
from v4's frozen evidence. It does not change v4's verdict; its rule is ``F7_RULE``.

An exception that escapes an arm on an item is recorded on that arm (``ARM_EXCEPTION``, scored no_decision) and the
run goes on; the report is always written. An exception on the warm-up item stops the run before the look.

Held-out runs need a committed freeze (``--freeze`` writes ``freeze-v6-attempt2.json``), and ``heldout_gate`` refuses when
any frozen input differs (code, data, rule, thresholds, Python version, distribution versions), the working tree is
not the committed one, the checkout holds bytecode or ignored files, the process was not started as
``python -I .../run_v6.py`` (whose first statements install a source-only loader: no bytecode is read and every
repository source compiled is hashed), any repository source it compiled is outside or unlike the freeze, or a
precondition fails (the genome's version and its current DEFAULT verdict). Only the gate issues the one-use token
that ``run_items`` requires for held-out items. Before the look one development item runs through every arm
(unscored); the run refuses when that executed code or loaded a distribution the freeze does not cover. After the
look the same checks, a fresh bytecode scan, the frozen inputs and the genome receipts' identity are checked again,
and any failure marks the run INVALID_RUN. ``--development`` runs development items only and writes no evidence;
``--check-gate`` runs the gate and stops before any held-out item is read. It checks this process only as it is at
gate time (the modules the gate and ``preconditions`` import); the modules the arms import are checked first at the
warm-up of the real run, so a ``--check-gate`` PASS is not the whole pre-look check: the warm-up completes it.
"""
from __future__ import annotations

import hashlib
import importlib.machinery
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def _source_only_loader(root: Path):
    """``SourceFileLoader.get_data`` that never reads bytecode and records the digest of every repository source it
    reads for compilation. A mirror of ``greg/cognition/evolution_room.py``'s hook (P8's clean room), not an import of
    it: importing that module would load the ``greg`` packages before the hook is in place."""
    read = importlib.machinery.SourceFileLoader.get_data

    def get_data(loader, path):
        resolved = Path(path).resolve()
        if resolved.suffix == ".pyc":
            raise OSError("source only: bytecode is never read; the import system compiles the source")
        data = read(loader, path)
        if root in resolved.parents and resolved.suffix == ".py":
            get_data.executed[resolved.relative_to(root).as_posix()] = "sha256:" + hashlib.sha256(data).hexdigest()
        return data

    get_data.executed = {}
    get_data.source_only_v6 = True
    return get_data


if __name__ == "__main__":         # a run of this file: the loader goes in before any repository module is imported
    sys.dont_write_bytecode = True
    _HOOK = _source_only_loader(ROOT)
    _HOOK.executed[Path(__file__).resolve().relative_to(ROOT).as_posix()] = (
        "sha256:" + hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    importlib.machinery.SourceFileLoader.get_data = _HOOK

import argparse  # noqa: E402
from collections import Counter  # noqa: E402
from datetime import datetime, timezone  # noqa: E402
from functools import lru_cache  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import os  # noqa: E402
import platform  # noqa: E402
import re  # noqa: E402
import statistics  # noqa: E402
import subprocess  # noqa: E402
import time  # noqa: E402

sys.path.insert(0, str(ROOT))

from cortex.evaluation.composition_lift import run as V1  # noqa: E402
from cortex.evaluation.composition_lift import run_v4 as V4  # noqa: E402

SUITE = V4.SUITE                                   # suite-v4.json, read only (frozen v4 evidence)
# attempt 1 froze freeze-v6.json (4430138) and hung before any held-out item finished; that file is kept as it was
MANIFEST = HERE / "freeze-v6-attempt2.json"
PREREG = HERE / "prereg-v6.json"
GENOME = "flow_expansion_mcf"
GENOME_CAPABILITY = f"cognition.{GENOME}"
GENOME_INTELLIGENCE = "solver.graph.capacity_expansion_mcf"
GENOME_OPERATION = "expand_capacity_mcf"
GENOME_VERSION = "1.0.0"                           # the version admission v3 admitted DEFAULT_FOR_GEOMETRY
RECIPE = "graph_then_allocate"
OPERATION_LATENCY_S = 20.0                         # run_v4.op's single-operation geometry budget
ALPHA = 0.05                                       # admission.ALPHA
LATENCY_RATIO = 1.25                               # admission.COST_RATIO
ROUTED, COMPILED, PMCF = "routed_composition", "compiled", "parametric_min_cost_flow"
ARMS = (GENOME, ROUTED, COMPILED, PMCF)
RULE_ARMS = (GENOME, ROUTED)
OUTCOMES = ("optimal", "suboptimal", "wrong", "no_decision")
EVAL_ATTACH = (*V4.EVAL_ATTACH, GENOME_CAPABILITY)
ARM_EXCEPTION = "ARM_EXCEPTION"                   # the state of an arm record whose runner raised on the item
ENTRY_POINTS = ("cortex/evaluation/composition_lift/run_v6.py", "greg/cognition/worker.py")
# v4's frozen F7 evidence: the constituents' per-item results on the same items (read, never re-run)
V4_EVIDENCE = {"heldout": "docs/evidence/greg-composition-lift/2026-10-14-v4/results-v4.json",
               "dev": "docs/evidence/greg-composition-lift/2026-10-14-v4/development-v4.json"}
FROZEN_EXTRA = ("cortex/evaluation/data/sndlib_networks.json.gz", "cortex/evaluation/data/build_sndlib_networks.py",
                "cortex/evaluation/composition_lift/prereg-v6.json", "docs/evidence/greg-mind-evidence-index.json",
                "tools/offline_test.py", "requirements-cortex.txt", "requirements-cognition.txt",
                *V4_EVIDENCE.values())
# Every third-party distribution a one-development-item run under ``python -I`` opened a module file of (strace -f
# over the parent and every worker it launched), plus the six numerical pins earlier freezes bound (sympy and
# z3-solver were not opened). Their versions are frozen; the parent and its pool also check what they loaded.
DISTRIBUTIONS = ("attrs", "charset-normalizer", "idna", "jsonschema", "jsonschema-specifications", "networkx", "numpy",
                 "ortools", "pandas", "python-dateutil", "referencing", "rfc3339-validator", "rpds-py", "scipy",
                 "setuptools", "six", "sympy", "typing-extensions", "z3-solver")
CONDITIONS = ("NO_WRONG_ANSWER", "GENOME_DECIDES_EVERY_ITEM", "NOT_SIGNIFICANTLY_WORSE", "LATENCY_WITHIN_RATIO")
RULE = ("flow_expansion_mcf MATCHES the routed composition on F7's held-out items when all four conditions hold and "
        "the comparator replicates v4. (1) NO_WRONG_ANSWER: no held-out item is scored wrong for flow_expansion_mcf; "
        "wrong is run_v4.f7_score's 'wrong' (over budget, out of bounds or a flow claim the recomputation "
        "contradicts) or a receipt the independent verifier REFUTED, which is scored wrong whatever its plan, as "
        "admission v3 scores a refuted answer. (2) GENOME_DECIDES_EVERY_ITEM: no held-out item is scored no_decision "
        "for the genome (an abstention of any kind, or an output f7_score cannot read as a plan). "
        "(3) NOT_SIGNIFICANTLY_WORSE: the one-sided exact sign test over discordant items gives p >= 0.05 for 'the "
        "genome is worse'. A loss is an item where routed is optimal and the genome is not, or where the genome is "
        "scored no_decision and routed is not (routed returned a plan, even a wrong one); a win is an "
        "item where the genome is optimal and routed is not; every other item is a tie, so the count is asymmetric "
        "against the genome. (4) LATENCY_WITHIN_RATIO: the genome's median latency over the held-out items is at most "
        "1.25x the routed composition's, both end to end through greg.cognition.cortex.reason on this machine. "
        "Outcome: INCONCLUSIVE when the independent rescoring disagrees with the primary scoring on any genome or "
        "routed plan or on any item's truth, except on the plan of a genome receipt the verifier REFUTED (the "
        "refutation scores that row wrong whatever its plan scores, so it decides NO_WRONG_ANSWER); a disagreement "
        "on a secondary arm (compiled, PMCF) is reported, makes the run informative and does not change the "
        "outcome; otherwise NO_MATCH, naming every failed condition, when a condition "
        "fails, except that a failure of LATENCY_WITHIN_RATIO alone is INCONCLUSIVE when the comparator did not "
        "replicate; otherwise INCONCLUSIVE when the comparator did not replicate v4 (routed optimal on every "
        "held-out item); otherwise MATCH. INVALID_RUN replaces the outcome when an integrity check fails; the "
        "measured outcome is kept beside it. The thresholds are admission v3's DEFAULT rule's (alpha 0.05, 1.25x); "
        "the rule deviates from that rule in the ways DEVIATIONS lists.")
DEVIATIONS = (
    ("ZERO_WRONG", "zero wrong answers are required; admission's DEFAULT requires no more wrong answers than the "
                   "competitor. Both score a refuted answer wrong, so this condition is stricter."),
    ("DECIDES_EVERY_ITEM", "the genome must return a plan on every item; admission has no such condition (there an "
                           "abstention is a lower native quality and weighs only through the sign test)."),
    ("OPTIMAL_VS_NOT_DISCORDANCE", "discordance is optimal-versus-not, as in v4, plus a genome abstention against a "
                                   "routed plan as a loss; admission compares native quality with the genome's "
                                   "tolerance. Here two non-optimal plans tie whatever their throughputs, and a "
                                   "genome plan against a routed abstention is not a win unless it is optimal."),
    ("NO_SIGNIFICANCE_ESCAPE", "the latency condition is always required; admission's DEFAULT also passes a "
                               "candidate that is significantly better than the competitor at any latency."),
    ("NO_BASELINE_CLAUSE", "there is no simple baseline: admission's DEFAULT requires beating one (significantly "
                           "better, or equal quality at >= 1.25x lower latency) and its REJECTED and EXPERIMENTAL "
                           "outcomes precede it; here the genome is compared with the routed composition only."),
    ("LATENCY_END_TO_END", "latency is measured end to end through cortex.reason for both arms (isolated worker "
                           "launches included); admission v3 measured both arms in process."),
    ("INCONCLUSIVE_OUTCOME", "admission has no INCONCLUSIVE outcome; here MATCH is withheld unless the comparator "
                             "replicates v4 and the independent rescoring agrees, and the outcome is an answer to "
                             "this question, not an admission status (no SUPERSEDED or NICHE_CAPABILITY)."),
)
# The secondary decision: v4's F7 rule with the genome as a constituent (it does not change v4's frozen verdict)
F7_CONDITIONS = ("ROUTED_MORE_OPTIMAL", "ROUTED_NO_MORE_WRONG", "SIGN_TEST_P_BELOW_ALPHA",
                 "ROUTED_MEDIAN_WITHIN_CHAIN_BUDGET", "ROUTED_MEDIAN_WITHIN_MULTIPLIER")
F7_RULE = ("F7_LIFT_WITH_GENOME (secondary; it does not change v4's frozen verdict, LIFT): v4's F7 rule, verbatim '"
           + V4.VERDICT_RULE + "', re-evaluated with the constituent set v4's two constituents (graph_alone_greedy, "
           "optimize_flow_blind: their optimal and wrong counts on the same items, as v4's frozen evidence records "
           "them, which do not depend on the machine) plus flow_expansion_mcf from this run, with routed being this "
           "run's routed_composition. The best constituent is chosen as v4 chooses it (most optimal, then fewest "
           "wrong; a full tie keeps v4's order, so a v4 constituent precedes the genome). When the genome is the best "
           "constituent, five conditions are read from this run's genome and routed rows (one machine): "
           "(1) ROUTED_MORE_OPTIMAL: routed optimal > the genome's optimal; (2) ROUTED_NO_MORE_WRONG: routed wrong <= "
           "the genome's wrong; (3) SIGN_TEST_P_BELOW_ALPHA: over the discordant items (routed optimal and the genome "
           "not is a routed win, the reverse a routed loss) the one-sided exact sign test for 'routed is better' "
           "gives p < 0.05; (4) ROUTED_MEDIAN_WITHIN_CHAIN_BUDGET: routed median latency <= 60 s; "
           "(5) ROUTED_MEDIAN_WITHIN_MULTIPLIER: routed median latency <= 10x the genome's median (medians of the "
           "recorded seconds rounded to 4 decimals, as run_v4 rounds them). LIFT when all five hold, otherwise "
           "NO_LIFT naming every failed condition. INCONCLUSIVE instead when the rows are not exactly the items v4's "
           "counts cover; when the independent rescoring disagrees with the primary scoring on a genome or routed "
           "plan or a truth (with the primary rule's exception for a refuted genome receipt); or when a v4 "
           "constituent is the best constituent: its paired rows and latencies are v4's, from another run on "
           "another machine, so the sign test and the latency conditions cannot be computed from this run's rows, "
           "and v4's verdict against it stands. A REFUTED genome receipt counts as wrong here, as in the primary "
           "rule; v4 scored its constituents through run_v4.op(), which counted a receipt in any state but NONE as no "
           "decision, so a refutation weighs against the genome in ROUTED_NO_MORE_WRONG and in the wrong-count "
           "tie-break where v4's scoring would not (v4's held-out constituent counts hold no such receipt). "
           "INVALID_RUN replaces the outcome when an integrity check fails.")


# ------------------------------------------------------------------ registry and arms
def registry():
    """run_v4's evaluation-only view (its four families attached, in memory) plus the genome. One object: run_v4's
    ``chain``, ``compiled`` and ``reason`` read the same view, so every GREG arm sees the same attachments."""
    view = V4.registry()
    view.set_state(GENOME_CAPABILITY, "ATTACHED")          # evaluation-only founder pin, in memory, never the body
    return view


def genome_arm(item):
    registry()
    net = item["payload"]["capacity_network"]
    started = time.perf_counter()
    r = V4.reason({"problem_id": f"{item['item_id']}/{GENOME}"[:128], "operation": GENOME_OPERATION, "data": net,
                   "geometry": {"latency_limit": OPERATION_LATENCY_S}})
    seconds = time.perf_counter() - started
    state = r["abstention_state"]
    plan = r.get("output") if isinstance(r.get("output"), dict) else None
    if state == "REFUTED":
        # a refuted answer is a false answer (admission v3): wrong whatever the plan scores; the plan is still scored
        plan_score, throughput = V4.f7_score(item, plan)
        outcome = "wrong"
    else:
        plan_score, throughput = V4.f7_score(item, plan if state == "NONE" else None)
        outcome = plan_score
    proof = r.get("proof_artifact") if isinstance(r.get("proof_artifact"), dict) else {}
    return {"result": outcome, "plan_score": plan_score, "throughput": throughput, "seconds": round(seconds, 4),
            "stages": 1, "state": state, "method": r["method"], "method_version": r["method_version"],
            "proof_intelligence_id": proof.get("intelligence_id"), "proof_version": proof.get("version"),
            "verifier": (r.get("evaluator_result") or {}).get("verdict"), "missing": r.get("missing_information"),
            "answer": plan if state in ("NONE", "REFUTED") else None}


def routed_arm(item):
    registry()
    answer, seconds, r = V4.chain(item)
    outcome, throughput = V4.f7_score(item, answer)
    return {"result": outcome, "throughput": throughput, "seconds": round(seconds, 4),
            "stages": len(r.get("stages", [])), "state": r["state"], "recipe": r.get("recipe"),
            "routed_by": r.get("routed_by"), "answer": answer}


def compiled_arm(item):
    registry()
    answer, seconds, r = V4.compiled(item)
    outcome, throughput = V4.f7_score(item, answer)
    return {"result": outcome, "throughput": throughput, "seconds": round(seconds, 4),
            "stages": (r.get("resource_use") or {}).get("stages"), "state": r["state"],
            "selected": r.get("method_or_composition_selected"), "answer": answer}


def pmcf_arm(item):
    started = time.perf_counter()
    answer = V4.parametric_min_cost_flow(item["payload"]["capacity_network"])
    seconds = time.perf_counter() - started
    outcome, throughput = V4.f7_score(item, answer)
    return {"result": outcome, "throughput": throughput, "seconds": round(seconds, 4), "stages": None,
            "state": "practitioner_in_process", "answer": answer}


RUNNERS = {GENOME: genome_arm, ROUTED: routed_arm, COMPILED: compiled_arm, PMCF: pmcf_arm}


# ------------------------------------------------------------------ independent rescoring (no flow.py, no run_v4)
def independent_instance(net: dict) -> dict:
    """The declared problem read straight from the item data: arcs, free capacity, lease price, per-arc limit,
    budget. Nothing here calls greg/cognition/genomes/flow.py or run_v4."""
    arcs = [(u, v) for u, v, _ in net["edges"]]
    if len(set(arcs)) != len(arcs) or net["source"] == net["sink"]:
        raise ValueError("the independent scorer needs distinct arcs and a source unlike the sink")
    return {"arcs": arcs, "capacity": {(u, v): int(c) for u, v, c in net["edges"]},
            "price": {(u, v): int(net["unit_cost"][f"{u}->{v}"]) for u, v in arcs},
            "limit": int(net["max_increment"]), "budget": int(net["budget"]), "source": net["source"],
            "sink": net["sink"]}


def independent_max_flow(inst: dict, units: dict) -> int:
    """SciPy's max flow on free capacity plus leased units (a C implementation; no code shared with flow.py)."""
    import numpy as np
    from scipy.sparse import csr_matrix
    from scipy.sparse.csgraph import maximum_flow
    nodes = sorted({n for a in inst["arcs"] for n in a} | {inst["source"], inst["sink"]})
    at = {n: i for i, n in enumerate(nodes)}
    caps = np.array([inst["capacity"][a] + units.get(a, 0) for a in inst["arcs"]], dtype=np.int32)
    graph = csr_matrix((caps, ([at[u] for u, _ in inst["arcs"]], [at[v] for _, v in inst["arcs"]])),
                       shape=(len(nodes), len(nodes)))
    return int(maximum_flow(graph, at[inst["source"]], at[inst["sink"]]).flow_value)


def independent_optimum(inst: dict) -> dict:
    """max F subject to arc flow <= free capacity + leased units, integer leased units in [0, limit], flow
    conservation and total lease price <= budget, solved by HiGHS (scipy.optimize.milp, relative gap 0). The MILP's
    own plan is re-checked by the independent max flow and budget. Status OPTIMAL only when all of that holds."""
    import numpy as np
    from scipy.optimize import Bounds, LinearConstraint, milp
    arcs, m = inst["arcs"], len(inst["arcs"])
    nodes = sorted({n for a in arcs for n in a} | {inst["source"], inst["sink"]})
    n = 2 * m + 1                                   # f (m), x (m), F
    c = np.zeros(n)
    c[-1] = -1.0
    rows, lo, hi = [], [], []
    for i, a in enumerate(arcs):                    # f_a - x_a <= capacity_a
        row = np.zeros(n)
        row[i], row[m + i] = 1.0, -1.0
        rows.append(row), lo.append(-np.inf), hi.append(inst["capacity"][a])
    for node in nodes:                              # out - in - F at the source, + F at the sink, = 0
        row = np.zeros(n)
        for i, (u, v) in enumerate(arcs):
            row[i] += (u == node) - (v == node)
        row[-1] = -1.0 if node == inst["source"] else 1.0 if node == inst["sink"] else 0.0
        rows.append(row), lo.append(0.0), hi.append(0.0)
    row = np.zeros(n)                               # total lease price within the budget
    row[m:2 * m] = [inst["price"][a] for a in arcs]
    rows.append(row), lo.append(-np.inf), hi.append(inst["budget"])
    upper = [inst["capacity"][a] + inst["limit"] for a in arcs] + [inst["limit"]] * m + [np.inf]
    result = milp(c, constraints=LinearConstraint(np.array(rows), lo, hi), bounds=Bounds([0.0] * n, upper),
                  integrality=np.array([0] * m + [1] * m + [0]), options={"mip_rel_gap": 0.0, "disp": False})
    if result.status != 0 or result.x is None:
        return {"status": f"NOT_SOLVED: {result.message}", "value": None}
    value = -float(result.fun)
    units = {a: int(round(result.x[m + i])) for i, a in enumerate(arcs)}
    plan_value = independent_max_flow(inst, units)
    plan_spent = sum(inst["price"][a] * x for a, x in units.items())
    if abs(value - round(value)) > 1e-6:
        return {"status": f"NOT_INTEGRAL: {value}", "value": None}
    if plan_value != round(value) or plan_spent > inst["budget"]:
        return {"status": f"PLAN_RECHECK_FAILED: plan carries {plan_value} at {plan_spent}", "value": None}
    return {"status": "OPTIMAL", "value": int(round(value))}


def independent_score(inst: dict, answer, optimum) -> dict:
    """The plan re-scored from the item data with the categories of run_v4.f7_score: no_decision (no plan), wrong
    (a key that names no arc, a non-integral or out-of-bounds unit count, over budget, or a flow claim unlike the
    recomputed flow), optimal or suboptimal against the independent optimum. A plan's 'spent' claim is checked and
    reported but, as in f7_score, does not set the category."""
    if not isinstance(answer, dict) or not isinstance(answer.get("increments"), dict):
        return {"result": "no_decision", "throughput": None, "spent_claim_true": None}
    names = {f"{u}->{v}": (u, v) for u, v in inst["arcs"]}
    units = {}
    for key, value in answer["increments"].items():
        integral = (isinstance(value, int) and not isinstance(value, bool)) or (
            isinstance(value, float) and math.isfinite(value) and value.is_integer())
        if key not in names or not integral:
            return {"result": "wrong", "throughput": None, "spent_claim_true": None}
        units[names[key]] = int(value)
    spent = sum(inst["price"][a] * x for a, x in units.items())
    if spent > inst["budget"] or any(not 0 <= x <= inst["limit"] for x in units.values()):
        return {"result": "wrong", "throughput": None, "spent_claim_true": None}
    flow = independent_max_flow(inst, units)
    spent_true = None if answer.get("spent") is None else answer["spent"] == spent
    if answer.get("flow_value") is not None and answer["flow_value"] != flow:
        return {"result": "wrong", "throughput": flow, "spent_claim_true": spent_true}
    if optimum is None:
        return {"result": "unscored", "throughput": flow, "spent_claim_true": spent_true}
    return {"result": "optimal" if flow == optimum else "suboptimal", "throughput": flow,
            "spent_claim_true": spent_true}


def independent_rescoring(item, arms: dict) -> dict:
    """Every arm's plan and the item's truth, re-scored independently. An arm agrees when the independent category
    and throughput equal the primary score of its plan (for the genome, the plan's score before a refutation). A
    rescoring that cannot run is recorded as a disagreement on every count, never as agreement."""
    try:
        inst = independent_instance(item["payload"]["capacity_network"])
        best = independent_optimum(inst)
        out = {"optimum": best["value"], "status": best["status"],
               "truth_agrees": best["status"] == "OPTIMAL" and best["value"] == item["truth"]["optimum"], "arms": {}}
        for arm, record in arms.items():
            score = independent_score(inst, record.get("answer"), best["value"])
            primary = (record.get("plan_score", record["result"]), record["throughput"])
            out["arms"][arm] = {**score, "agrees": (score["result"], score["throughput"]) == primary}
        return out
    except Exception as exc:          # the run goes on; the rule reads this item as INCONCLUSIVE
        return {"optimum": None, "status": f"ERROR: {type(exc).__name__}: {str(exc)[:200]}", "truth_agrees": False,
                "arms": {arm: {"result": None, "throughput": None, "spent_claim_true": None, "agrees": False}
                         for arm in arms}}


# ------------------------------------------------------------------ the rule (primary) and the report (secondary)
def _loss(g, k) -> bool:
    return (k["result"] == "optimal" and g["result"] != "optimal") or (
        g["result"] == "no_decision" and k["result"] != "no_decision")


def _win(g, k) -> bool:
    return g["result"] == "optimal" and k["result"] != "optimal"


def _row_disagreements(r, arms) -> list[dict]:
    """Where the independent rescoring disagrees with the primary scoring on one row (truth, or an arm's plan)."""
    ind = r.get("independent")
    if not ind:
        return [{"item_id": r.get("item_id"), "what": "independent rescoring missing"}]
    out = []
    if not ind.get("truth_agrees"):
        out.append({"item_id": r.get("item_id"), "what": "truth", "suite": (r.get("truth") or {}).get("optimum"),
                    "independent": ind.get("optimum"), "status": ind.get("status")})
    for arm in arms:
        a = (ind.get("arms") or {}).get(arm)
        if a is None or not a.get("agrees"):
            record = r["arms"].get(arm, {})
            out.append({"item_id": r.get("item_id"), "what": arm,
                        "primary": [record.get("plan_score", record.get("result")), record.get("throughput")],
                        "independent": None if a is None else [a.get("result"), a.get("throughput")]})
    return out


def rescoring_disagreements(rows, arms=ARMS) -> list[dict]:
    """Every item where the independent rescoring disagrees with the primary scoring (truth, or an arm's plan)."""
    return [d for r in rows for d in _row_disagreements(r, arms)]


def _refuted(r) -> bool:
    return r["arms"][GENOME].get("state") == "REFUTED"


def rule_disagreements(rows) -> list[dict]:
    """The disagreements the rule reads: on the genome's and the routed composition's plans and on every truth. A
    disagreement on the plan of a genome receipt the verifier REFUTED is left out: the refutation scores that row
    wrong whatever its plan scores, so it decides NO_WRONG_ANSWER whichever scorer is right about the plan."""
    return [d for r in rows for d in _row_disagreements(r, RULE_ARMS) if not (d["what"] == GENOME and _refuted(r))]


def refuted_plan_disagreements(rows) -> list[dict]:
    """Disagreements on refuted genome plans (reported; the refutation decides those rows)."""
    return [d for r in rows if _refuted(r) for d in _row_disagreements(r, (GENOME,)) if d["what"] == GENOME]


def secondary_disagreements(rows) -> list[dict]:
    """Disagreements on the secondary arms (compiled, PMCF) a row records. Reported; they make the run informative and
    never change the rule's outcome. A row without a rescoring is already a rule disagreement."""
    out = []
    for r in rows:
        if not r.get("independent"):
            continue
        recorded = set(r["arms"]) | set(r["independent"].get("arms") or {})
        arms = [a for a in (COMPILED, PMCF) if a in recorded]
        out += [d for d in _row_disagreements(r, arms) if d["what"] in arms]
    return out


def _counts(records) -> dict:
    return {k: sum(x["result"] == k for x in records) for k in OUTCOMES}


def decide(rows) -> dict:
    """The pre-registered rule on result rows (each ``{"arms": {arm: {"result", "seconds", "state"}},
    "independent": ...}``)."""
    if not rows:
        raise ValueError("the rule needs at least one item")
    genome = [r["arms"][GENOME] for r in rows]
    routed = [r["arms"][ROUTED] for r in rows]
    wins = sum(_win(g, k) for g, k in zip(genome, routed))
    losses = sum(_loss(g, k) for g, k in zip(genome, routed))
    p_worse, p_better = V1.sign_test(losses, wins), V1.sign_test(wins, losses)
    count_g, count_k = _counts(genome), _counts(routed)
    median_genome = statistics.median(g["seconds"] for g in genome)
    median_routed = statistics.median(k["seconds"] for k in routed)
    ratio = median_genome / median_routed if median_routed > 0 else math.inf
    conditions = {"NO_WRONG_ANSWER": count_g["wrong"] == 0,
                  "GENOME_DECIDES_EVERY_ITEM": count_g["no_decision"] == 0,
                  "NOT_SIGNIFICANTLY_WORSE": p_worse >= ALPHA,
                  "LATENCY_WITHIN_RATIO": median_genome <= LATENCY_RATIO * median_routed}
    failed = [name for name in CONDITIONS if not conditions[name]]
    replicated = count_k["optimal"] == len(rows)
    disagreements = rule_disagreements(rows)
    refuted_plan = refuted_plan_disagreements(rows)
    secondary = secondary_disagreements(rows)
    secondary_by_arm = dict(sorted(Counter(d["what"] for d in secondary).items()))
    states_g = Counter(str(g.get("state")) for g in genome)
    states_k = Counter(str(k.get("state")) for k in routed)
    why = []
    if disagreements:
        why.append(f"INDEPENDENT_RESCORING_DISAGREES on {len({d['item_id'] for d in disagreements})} item(s)")
    if not replicated:
        why.append(f"COMPARATOR_NOT_REPLICATED: routed optimal on {count_k['optimal']} of {len(rows)}")
    if disagreements:
        outcome = "INCONCLUSIVE"
    elif failed and (set(failed) - {"LATENCY_WITHIN_RATIO"} or replicated):
        outcome, why = "NO_MATCH", []
    elif failed or not replicated:
        outcome = "INCONCLUSIVE"
    else:
        outcome, why = "MATCH", []
    irregular = (set(states_g) - {"NONE"}) | (set(states_k) - {"ANSWERED"})
    informative = bool(failed or wins or losses or disagreements or secondary or not replicated or irregular
                       or count_g["optimal"] < len(rows))
    if informative:
        reading = (f"{outcome}, informative: genome {count_g}, routed {count_k}; genome states {dict(states_g)}, "
                   f"routed states {dict(states_k)}; wins {wins}, losses {losses} (p_worse {round(p_worse, 6)}); "
                   f"latency ratio {round(ratio, 4) if math.isfinite(ratio) else None}; failed {failed or 'none'}"
                   + (f"; {'; '.join(why)}" if why else "")
                   + (f"; the rescoring of a refuted genome plan disagrees on {len(refuted_plan)} item(s) (the "
                      f"refutation decides those rows)" if refuted_plan else "")
                   + (f"; SECONDARY_RESCORING_DISAGREES {secondary_by_arm} (reported; the outcome does not depend "
                      f"on it)" if secondary else ""))
    else:
        reading = ("MATCH, uninformative beyond replication: both arms optimal on every item, no abstention, "
                   "refutation or wrong answer; the independent rescoring agrees with the primary scoring on the "
                   "genome's and the routed composition's plans and on every item's truth, and no secondary arm's "
                   "rescoring disagrees; the expected tie, which replicates admission v3's DEFAULT verdict on real "
                   "items and is not a new capability")
    return {"outcome": outcome, "failed": failed, "conditions": conditions, "why": why, "n": len(rows),
            "counts": {GENOME: count_g, ROUTED: count_k},
            "states": {GENOME: dict(sorted(states_g.items())), ROUTED: dict(sorted(states_k.items()))},
            "genome_wrong": count_g["wrong"], "genome_no_decision": count_g["no_decision"],
            "genome_refuted": states_g.get("REFUTED", 0), "wins": wins, "losses": losses,
            "p_worse_one_sided": round(p_worse, 6), "p_better_one_sided": round(p_better, 6),
            "median_seconds": {GENOME: round(median_genome, 4), ROUTED: round(median_routed, 4)},
            "latency_ratio": round(ratio, 4) if math.isfinite(ratio) else None,
            "alpha": ALPHA, "latency_ratio_limit": LATENCY_RATIO, "comparator_replicated": replicated,
            "rescoring_disagreements_on_rule_arms": len(disagreements),
            "refuted_plan_rescoring_disagreements": len(refuted_plan),
            "rescoring_disagreements_on_secondary_arms": secondary_by_arm, "informative": informative,
            "reading": reading, "rule": RULE}


# ------------------------------------------------------------------ the secondary decision: v4's F7 rule + the genome
def v4_constituents(partition: str) -> dict:
    """v4's two F7 constituents' optimal and wrong counts on ``partition`` ('heldout' or 'dev'), counted from v4's
    frozen per-item results and checked against v4's own summary and rule. These counts do not depend on the machine;
    v4's constituent latencies are never used."""
    path = V4_EVIDENCE[partition]
    report = json.loads((ROOT / path).read_text())
    rows = [r for r in (report["heldout"] if partition == "heldout" else report["rows"]) if r["family"] == "F7"]
    counts = {name: {k: sum(r["arms"][name]["result"] == k for r in rows) for k in ("optimal", "wrong")}
              for name in V4.CONSTITUENTS["F7"]}
    summary = report["summary"]
    if summary["VPL_v4"]["rule"] != V4.VERDICT_RULE:
        raise ValueError(f"{path}: its rule is not run_v4.VERDICT_RULE")
    if any(counts[n][k] != summary["F7"]["outcomes"][n][k] for n in counts for k in ("optimal", "wrong")):
        raise ValueError(f"{path}: its per-item results do not reproduce its summary")
    return {"source": path, "partition": partition, "item_ids": [r["item_id"] for r in rows], "counts": counts}


def f7_lift_with_genome(rows, v4: dict) -> dict:
    """``F7_RULE`` on result rows (genome and routed arms of this run) and ``v4`` (``v4_constituents``' shape). A pure
    function of its arguments."""
    out = {"outcome": "INCONCLUSIVE", "failed": None, "conditions": None, "why": [], "secondary": True,
           "v4_verdict": "LIFT (frozen; unchanged by this reading)", "counts_source": v4.get("source"),
           "expected": "NO_LIFT (the expectation given admission v3, not a result)", "rule": F7_RULE}
    if sorted(str(r.get("item_id")) for r in rows) != sorted(str(i) for i in v4["item_ids"]):
        out["why"] = [f"ITEMS_DIFFER: v4's constituent counts cover {len(v4['item_ids'])} items of "
                      f"{v4.get('partition')}; these rows are {len(rows)} items that are not exactly those"]
        return out
    genome, routed = _counts([r["arms"][GENOME] for r in rows]), _counts([r["arms"][ROUTED] for r in rows])
    constituents = {**{n: {"optimal": c["optimal"], "wrong": c["wrong"], "from": "v4"} for n, c in v4["counts"].items()},
                    GENOME: {"optimal": genome["optimal"], "wrong": genome["wrong"], "from": "this run"}}
    best = max(constituents, key=lambda a: (constituents[a]["optimal"], -constituents[a]["wrong"]))
    out.update(constituents=constituents, best_constituent=best,
               routed={"optimal": routed["optimal"], "wrong": routed["wrong"]})
    disagreements = rule_disagreements(rows)
    if disagreements:
        out["why"].append(f"INDEPENDENT_RESCORING_DISAGREES on {len({d['item_id'] for d in disagreements})} item(s)")
    if best != GENOME:
        out["why"].append(f"BEST_CONSTITUENT_IS_V4s: {best} ({constituents[best]['optimal']} optimal, "
                          f"{constituents[best]['wrong']} wrong) outranks the genome ({genome['optimal']}, "
                          f"{genome['wrong']}); its paired rows and latencies are v4's (another run, another "
                          f"machine), so the sign test and the latency conditions cannot be computed from this run; "
                          f"v4's verdict against it stands")
    if out["why"]:
        return out
    wins, losses, p = V4._discordant(rows, ROUTED, GENOME)
    median = {a: round(statistics.median(r["arms"][a]["seconds"] for r in rows), 4) for a in (GENOME, ROUTED)}
    conditions = {"ROUTED_MORE_OPTIMAL": routed["optimal"] > genome["optimal"],
                  "ROUTED_NO_MORE_WRONG": routed["wrong"] <= genome["wrong"],
                  "SIGN_TEST_P_BELOW_ALPHA": p < ALPHA,
                  "ROUTED_MEDIAN_WITHIN_CHAIN_BUDGET": median[ROUTED] <= V4.CHAIN_BUDGET_S,
                  "ROUTED_MEDIAN_WITHIN_MULTIPLIER": median[ROUTED] <= V4.LATENCY_MULTIPLIER * median[GENOME]}
    failed = [c for c in F7_CONDITIONS if not conditions[c]]
    out.update(outcome="NO_LIFT" if failed else "LIFT", failed=failed, conditions=conditions, routed_wins=wins,
               routed_losses=losses, sign_test_p_one_sided=round(p, 6), median_seconds=median,
               latency_ratio_routed_over_best=round(median[ROUTED] / median[GENOME], 3) if median[GENOME] else None)
    return out


def _versus(rows, a, b):
    """Optimal-versus-not (v4's discordance), reported for every pair; it is not the rule's loss definition."""
    wins = sum(r["arms"][a]["result"] == "optimal" and r["arms"][b]["result"] != "optimal" for r in rows)
    losses = sum(r["arms"][b]["result"] == "optimal" and r["arms"][a]["result"] != "optimal" for r in rows)
    return {"wins": wins, "losses": losses, "p_one_sided_better": round(V1.sign_test(wins, losses), 6),
            "p_one_sided_worse": round(V1.sign_test(losses, wins), 6)}


def _ratio(a, b):
    return round(a / b, 4) if b else None


def summarize(rows, v4: dict | None = None) -> dict:
    """The report's summary: the rule, the secondary decision F7_LIFT_WITH_GENOME (when ``v4`` is given) and every
    secondary comparison."""
    count = {a: _counts([r["arms"][a] for r in rows]) for a in ARMS}
    median = {a: round(statistics.median(r["arms"][a]["seconds"] for r in rows), 4) for a in ARMS}
    selected = Counter(str(r["arms"][COMPILED].get("selected")) for r in rows)
    same = sum(r["arms"][COMPILED]["result"] == r["arms"][GENOME]["result"]
               and r["arms"][COMPILED]["throughput"] == r["arms"][GENOME]["throughput"] for r in rows)
    identical = sum(isinstance(r["arms"][COMPILED].get("answer"), dict)
                    and isinstance(r["arms"][GENOME].get("answer"), dict)
                    and r["arms"][COMPILED]["answer"].get("increments") == r["arms"][GENOME]["answer"].get("increments")
                    for r in rows)
    per_network = {}
    for network in sorted({r["network"] for r in rows}):
        nr = [r for r in rows if r["network"] == network]
        per_network[network] = {"n": len(nr), **{a: {"optimal": sum(r["arms"][a]["result"] == "optimal" for r in nr),
                                                     "median_s": round(statistics.median(r["arms"][a]["seconds"]
                                                                                         for r in nr), 4)}
                                                 for a in ARMS}}
    genome = [r["arms"][GENOME] for r in rows]
    by_state = {}
    for g in genome:
        by_state.setdefault(str(g.get("state")), Counter())[g["result"]] += 1
    disagreements = rescoring_disagreements(rows)
    disagreeing_arms = {d["what"] for d in disagreements}
    exceptions = [{"item_id": r.get("item_id"), "arm": a, "exception": r["arms"][a].get("exception")}
                  for r in rows for a in ARMS if r["arms"][a].get("state") == ARM_EXCEPTION]
    return {
        "n": len(rows), "networks": len({r["network"] for r in rows}), "rule": decide(rows),
        "f7_lift_with_genome": f7_lift_with_genome(rows, v4) if v4 is not None else {"outcome": "NOT_EVALUATED"},
        "arm_exceptions": {"count": dict(sorted(Counter(e["arm"] for e in exceptions).items())),
                           "items": exceptions[:50]},
        "outcomes": count, "median_seconds": median,
        "latency_ratios": {"genome_over_routed": _ratio(median[GENOME], median[ROUTED]),
                           "compiled_over_routed": _ratio(median[COMPILED], median[ROUTED]),
                           "compiled_over_genome": _ratio(median[COMPILED], median[GENOME]),
                           "genome_over_pmcf_in_process_not_comparable": _ratio(median[GENOME], median[PMCF])},
        "versus_optimal_vs_not": {f"{a}_vs_{b}": _versus(rows, a, b)
                                  for a, b in ((GENOME, ROUTED), (GENOME, PMCF), (ROUTED, PMCF), (COMPILED, GENOME))},
        "compiler": {"selected": dict(sorted(selected.items())),
                     "selected_genome_on_every_item": selected.get(GENOME_CAPABILITY, 0) == len(rows),
                     "same_outcome_and_throughput_as_genome": same, "identical_increments_to_genome": identical},
        "genome_receipts": {"method": dict(Counter(str(g.get("method")) for g in genome)),
                            "method_version_capability_manifest": dict(Counter(str(g.get("method_version"))
                                                                               for g in genome)),
                            "proof_intelligence_id": dict(Counter(str(g.get("proof_intelligence_id"))
                                                                  for g in genome)),
                            "proof_version": dict(Counter(str(g.get("proof_version")) for g in genome)),
                            "verifier": dict(Counter(str(g.get("verifier")) for g in genome)),
                            "state": dict(Counter(str(g.get("state")) for g in genome)),
                            "result_by_state": {s: dict(sorted(c.items())) for s, c in sorted(by_state.items())}},
        "routed_receipts": {"recipe": dict(Counter(str(r["arms"][ROUTED].get("recipe")) for r in rows)),
                            "state": dict(Counter(str(r["arms"][ROUTED].get("state")) for r in rows))},
        "independent_rescoring": {
            "n": len(rows),
            "truth_agreement": sum(bool((r.get("independent") or {}).get("truth_agrees")) for r in rows),
            "milp_status": dict(Counter(str((r.get("independent") or {}).get("status")) for r in rows)),
            "agreement": {a: sum(bool(((r.get("independent") or {}).get("arms", {}).get(a) or {}).get("agrees"))
                                 for r in rows) for a in ARMS},
            "spent_claim_false": {a: sum(((r.get("independent") or {}).get("arms", {}).get(a) or {})
                                         .get("spent_claim_true") is False for r in rows) for a in ARMS},
            "disagreements": disagreements[:50], "disagreement_count": len(disagreements),
            "secondary_inconclusive": sorted(disagreeing_arms & {COMPILED, PMCF})},
        "pmcf_equals_suite_truth": sum(r["arms"][PMCF]["throughput"] == r["truth"]["optimum"] for r in rows),
        "throughput_shortfall_vs_optimum": {a: sum(r["truth"]["optimum"] - (r["arms"][a]["throughput"] or 0)
                                                   for r in rows) for a in ARMS},
        "per_network": per_network, "model_calls": 0, "money_usd": 0.0}


def receipt_problems(rows) -> list[str]:
    """Genome receipts that do not name the frozen genome: every receipt must name the method
    cognition.flow_expansion_mcf, and every receipt that carries an output must carry a proof artifact of
    solver.graph.capacity_expansion_mcf at 1.0.0. (By the receipt contract an abstention carries no artifact; it is a
    GENOME_DECIDES_EVERY_ITEM failure, not an identity failure. An arm that raised returned no receipt: it is scored
    no_decision and reported under arm_exceptions.)"""
    out = []
    for r in rows:
        g = r["arms"][GENOME]
        if g.get("state") == ARM_EXCEPTION:
            continue
        if g.get("method") != GENOME_CAPABILITY:
            out.append(f"{r.get('item_id')}: method {g.get('method')}")
        if g.get("answer") is not None and (g.get("proof_intelligence_id"), g.get("proof_version")) != (
                GENOME_INTELLIGENCE, GENOME_VERSION):
            out.append(f"{r.get('item_id')}: proof artifact {g.get('proof_intelligence_id')} "
                       f"{g.get('proof_version')}")
    return out


# ------------------------------------------------------------------ preconditions, closure, tree, freeze
def preconditions(index: dict | None = None) -> list[str]:
    """Why the question would not be the pre-registered one (empty when it is): the genome's version, its current
    DEFAULT verdict in the evidence index, and the compiler's single-genome match for the recipe."""
    from greg.cognition import compiler
    from greg.cognition.genomes import library
    index = compiler.evidence_index() if index is None else index
    problems = []
    item = library.executables().get(GENOME)
    if item is None:
        return [f"{GENOME} is not in the genome library"]
    if item.genome.version != GENOME_VERSION:
        problems.append(f"{GENOME} is at version {item.genome.version}, not {GENOME_VERSION}")
    record = index.get("genomes", {}).get(GENOME, {})
    if (record.get("status"), record.get("version")) != ("DEFAULT_FOR_GEOMETRY", GENOME_VERSION):
        problems.append(f"the evidence index records {record.get('status')} at {record.get('version')} for {GENOME}, "
                        f"not DEFAULT_FOR_GEOMETRY at {GENOME_VERSION}")
    if GENOME_CAPABILITY not in [m["method"] for m in compiler._matched_by_single_genome(RECIPE, index)]:
        problems.append(f"the compiler does not match {GENOME_CAPABILITY} against {RECIPE}")
    return problems


def code_closure() -> list[str]:
    """Every repository file the run can execute or read, hashed by the freeze (the v3 closure rule)."""
    from cortex.evaluation.closure import code_closure as closure
    return closure(ENTRY_POINTS, packages=("greg/cognition",), extra=FROZEN_EXTRA, root=ROOT)


def _rel(path: Path) -> str:
    """Repository-relative when inside the repository; otherwise absolute (which the tree check cannot vouch for)."""
    resolved = Path(path).resolve()
    return resolved.relative_to(ROOT).as_posix() if ROOT in resolved.parents else str(resolved)


def inputs() -> dict:
    """JSON-normalised so the comparison with the stored freeze is exact (tuples become lists)."""
    from cortex.evaluation.closure import dependency_versions
    return json.loads(json.dumps({
        "suite": V1._sha(SUITE), "prereg": V1._sha(PREREG),
        "code": {p: V1._sha(ROOT / p) for p in code_closure()}, "rule": RULE, "conditions": CONDITIONS,
        "deviations": DEVIATIONS, "alpha": ALPHA, "latency_ratio": LATENCY_RATIO,
        "operation_latency_s": OPERATION_LATENCY_S, "chain_budget_s": V4.CHAIN_BUDGET_S, "arms": ARMS,
        "evaluation_attach": EVAL_ATTACH,
        "f7_secondary": {"rule": F7_RULE, "conditions": F7_CONDITIONS, "v4_rule": V4.VERDICT_RULE,
                         "latency_multiplier": V4.LATENCY_MULTIPLIER, "v4_constituents": v4_constituents("heldout")},
        "genome": {"family": GENOME, "capability": GENOME_CAPABILITY, "intelligence_id": GENOME_INTELLIGENCE,
                   "operation": GENOME_OPERATION, "version": GENOME_VERSION, "recipe": RECIPE},
        "partition": V4.partition(), "python": {"version": platform.python_version(),
                                                "implementation": sys.implementation.name},
        "dependencies": dependency_versions(DISTRIBUTIONS)}))


def differences(frozen: dict, current: dict) -> list[str]:
    """Each frozen input that differs: a top-level key, or a code path added, removed or changed."""
    out = []
    for key in sorted(set(frozen) | set(current)):
        if key == "code":
            a, b = frozen.get("code", {}), current.get("code", {})
            out += [f"code:{p}" for p in sorted(set(a) | set(b)) if a.get(p) != b.get(p)]
        elif frozen.get(key) != current.get(key):
            out.append(key)
    return out


def _blob(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def tree_dirty(paths, root: Path = ROOT) -> list[str]:
    """Why the working tree is not the committed one (empty when it is): each named path whose bytes are not its
    blob at HEAD (compared by content, so an index flag cannot hide an edit), then every ``git status`` line
    (a tracked change or an untracked file anywhere). Ignored files are ``ignored_files``'s. When git cannot tell, it
    says so."""
    paths = sorted(set(paths))
    try:
        tree = subprocess.run(["git", "ls-tree", "-r", "-z", "HEAD", "--", *paths], cwd=root, capture_output=True,
                              check=True).stdout
        status = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=root,
                                capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        return [f"git cannot tell: {exc}"]
    committed = {}
    for entry in filter(None, tree.split(b"\0")):
        meta, _, name = entry.partition(b"\t")
        committed[name.decode()] = meta.split()[2].decode()
    out = [f"not committed as is: {p}" for p in paths
           if p not in committed or not (root / p).is_file() or _blob(root / p) != committed[p]]
    return out + [f"git status: {line}" for line in status.splitlines() if line.strip()]


def bytecode_files(root: Path = ROOT) -> list[str]:
    """Every ``__pycache__`` directory and ``.pyc`` file under the repository (``.git`` aside). The isolated
    workers (``python -I worker.py``) read repository bytecode whenever its timestamp and size match the source, so a
    held-out run needs none: then every process compiles the frozen source."""
    found = []
    for directory, subdirs, files in os.walk(root):
        subdirs[:] = [d for d in subdirs if d != ".git"]
        here = Path(directory)
        found += [(here / d).relative_to(root).as_posix() + "/" for d in subdirs if d == "__pycache__"]
        found += [(here / f).relative_to(root).as_posix() for f in files if f.endswith(".pyc")]
    return sorted(found)


def ignored_files(root: Path = ROOT) -> list[str]:
    """Every file git ignores in the checkout (a fresh checkout has none), or why git cannot tell."""
    try:
        status = subprocess.run(["git", "status", "--porcelain", "--ignored", "--untracked-files=all"], cwd=root,
                                capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        return [f"git cannot tell: {exc}"]
    return [line[3:] for line in status.splitlines() if line.startswith("!! ")]


def _loaded_repository_files() -> set[str]:
    out = set()
    for module in list(sys.modules.values()):
        path = getattr(module, "__file__", None)
        if path:
            resolved = Path(path).resolve()
            if ROOT in resolved.parents and not ({"site-packages", "dist-packages"} & set(resolved.parts)):
                out.add(resolved.relative_to(ROOT).as_posix())
    return out


def _canonical(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


@lru_cache(maxsize=1)
def _owners() -> dict:
    import importlib.metadata as md
    return md.packages_distributions()


def _loaded_distributions() -> dict[str, str | None]:
    """Third-party distributions this process has loaded a module from, with versions: each module file under a
    site-packages or dist-packages directory is attributed by the first path component below it (a package directory
    or a single-file module), as ``importlib.metadata.packages_distributions`` maps it. A component no distribution
    claims is reported as ``<unowned:name>``."""
    import importlib.metadata as md
    owners = _owners()
    out = {}
    for module in list(sys.modules.values()):
        path = getattr(module, "__file__", None)
        parts = Path(path).parts if path else ()
        sites = [i for i, part in enumerate(parts) if part in ("site-packages", "dist-packages")]
        if not sites or sites[-1] + 1 >= len(parts):
            continue
        top = parts[sites[-1] + 1].split(".")[0]
        for dist in owners.get(top, [f"<unowned:{top}>"]):
            if dist not in out:
                try:
                    out[dist] = md.version(dist)
                except md.PackageNotFoundError:
                    out[dist] = None
    return {_canonical(k) if not k.startswith("<") else k: v for k, v in sorted(out.items())}


def _isolated() -> bool:
    return bool(sys.flags.isolated)


def _hook():
    hook = importlib.machinery.SourceFileLoader.get_data
    return hook if getattr(hook, "source_only_v6", False) else None


def _process_record() -> dict:
    hook = _hook()
    return {"loaded": sorted(_loaded_repository_files()), "executed": None if hook is None else dict(hook.executed),
            "distributions": _loaded_distributions()}


def _executed_problems(executed, loaded, code: dict) -> list[str]:
    if executed is None:
        return ["no source-only record of the code executed (the loader was not installed)"]
    out = []
    unhashed = sorted(set(loaded) - set(executed))
    if unhashed:
        out.append(f"repository modules loaded without the source-only loader: {unhashed[:10]}")
    outside = sorted(set(executed) - set(code))
    if outside:
        out.append(f"executed repository files outside the freeze: {outside[:10]}")
    unlike = sorted(p for p, sha in executed.items() if p in code and code[p] != sha)
    if unlike:
        out.append(f"executed repository source unlike the freeze: {unlike[:10]}")
    return out


def _distribution_problems(distributions: dict) -> list[str]:
    allowed = {_canonical(d) for d in DISTRIBUTIONS}
    outside = sorted(d for d in distributions if d not in allowed)
    return [f"loaded distributions the freeze does not bind: {outside}"] if outside else []


def integrity(code: dict, ran: dict) -> list[str]:
    """What a run's own record says against the freeze: repository code executed (parent and forked pool) outside or
    unlike the frozen digests, modules loaded around the source-only loader, distributions the freeze does not bind."""
    return (_executed_problems(ran.get("executed"), ran.get("loaded", ()), code)
            + _distribution_problems(ran.get("distributions", {})))


def clean_room_violations(code: dict, root: Path = ROOT) -> list[str]:
    """Why this process and checkout cannot vouch that the frozen source is what runs (empty when they can)."""
    found = []
    held = bytecode_files(root)
    if held:
        found.append(f"bytecode in the checkout (an isolated worker would run it instead of the source): {held[:5]}")
    ignored = ignored_files(root)
    if ignored:
        found.append(f"ignored files in the checkout (not a fresh checkout): {ignored[:5]}")
    if not _isolated():
        found.append("not started with python -I: user site-packages and PYTHON* variables can change what runs")
    if not sys.dont_write_bytecode:
        found.append("bytecode writing is on")
    if _hook() is None:
        found.append("the source-only loader is not installed: start this file as a script "
                     "(python -I cortex/evaluation/composition_lift/run_v6.py), not by import")
    else:
        found += integrity(code, _process_record())
    return found


def freeze(manifest: Path | None = None) -> dict:
    """Write the freeze: refuses an existing one, an interpreter not started with -I (the distribution versions must
    be read as the run reads them: without -I, user site-packages can shadow them), a dirty tree (the frozen bytes
    must be HEAD's) or a failed precondition."""
    manifest = manifest or MANIFEST
    if manifest.exists():
        raise SystemExit("refusing to overwrite an existing freeze; create a new version")
    if not _isolated():
        raise SystemExit("NOT_ISOLATED: write the freeze with python -I, as the held-out run starts")
    frozen = inputs()
    dirty = tree_dirty([*frozen["code"], _rel(SUITE), _rel(PREREG)])
    if dirty:
        raise SystemExit(f"DIRTY_TREE: a freeze binds committed bytes only: {dirty[:10]}")
    problems = preconditions()
    if problems:
        raise SystemExit(f"PRECONDITION: {problems}")
    record = {"frozen_at": datetime.now(timezone.utc).isoformat(), "inputs": frozen}
    manifest.write_text(json.dumps(record, indent=2) + "\n")
    return record


class _HeldoutToken:
    """The one-use permission ``heldout_gate`` issues to ``run_items`` for held-out items (an accident guard inside
    one process, not a security boundary)."""
    __slots__ = ()


_ISSUED: set = set()


def heldout_gate(manifest: Path | None = None) -> dict:
    """Everything a held-out run must pass before any held-out item is read for running: the freeze exists, every
    frozen input is unchanged, the tree (freeze included) is the committed one, the checkout and this process form a
    clean room, and the preconditions hold. Returns the frozen inputs and the one-use held-out token."""
    manifest = manifest or MANIFEST
    if not manifest.is_file():
        raise SystemExit(f"NO_FREEZE: a held-out run needs a committed freeze at {manifest}; run --freeze, commit it")
    frozen = json.loads(manifest.read_text())["inputs"]
    changed = differences(frozen, inputs())
    if changed:
        raise SystemExit(f"FROZEN_INPUT_CHANGED: results cannot be reported: {changed[:20]}")
    dirty = tree_dirty([*frozen["code"], _rel(SUITE), _rel(PREREG), _rel(manifest)])
    if dirty:
        raise SystemExit(f"DIRTY_TREE: the held-out run needs a clean checkout at the freeze's commit: {dirty[:10]}")
    room = clean_room_violations(frozen["code"])
    if room:
        raise SystemExit(f"CLEAN_ROOM_REQUIRED: {room}")
    problems = preconditions()
    if problems:
        raise SystemExit(f"PRECONDITION: {problems}")
    token = _HeldoutToken()
    _ISSUED.add(token)
    return {"inputs": frozen, "token": token}


# ------------------------------------------------------------------ running
def suite_items(partition: str) -> list[dict]:
    return [i for i in json.loads(SUITE.read_text())["items"] if i["partition"] == partition]


def arm_exception(arm: str, exc: BaseException, seconds: float) -> dict:
    """The record of an arm whose runner raised on an item: no plan, scored no_decision (for the genome a
    GENOME_DECIDES_EVERY_ITEM failure; for the routed composition a failure to replicate), the exception kept."""
    record = {"result": "no_decision", "throughput": None, "seconds": round(seconds, 4), "stages": None,
              "state": ARM_EXCEPTION, "exception": f"{type(exc).__name__}: {str(exc)[:500]}", "answer": None}
    return {**record, "plan_score": "no_decision"} if arm == GENOME else record


def _run_item(index, item):
    order = ARMS[index % len(ARMS):] + ARMS[:index % len(ARMS)]
    row = {"item_id": item["item_id"], "family": item["family"], "network": item["network"], "pair": item["pair"],
           "partition": item["partition"], "truth": item["truth"], "arm_order": list(order), "arms": {}}
    for arm in order:
        started = time.perf_counter()
        try:
            row["arms"][arm] = RUNNERS[arm](item)
        except Exception as exc:          # recorded and scored; the look goes on (prereg execution.arm_exceptions)
            row["arms"][arm] = arm_exception(arm, exc, time.perf_counter() - started)
    row["arms"] = {a: row["arms"][a] for a in ARMS}
    row["independent"] = independent_rescoring(item, row["arms"])          # after every arm: no latency effect
    print(json.dumps({"i": index, "item": item["item_id"], "optimum": item["truth"]["optimum"],
                      "result": {a: row["arms"][a]["result"] for a in ARMS},
                      "seconds": {a: row["arms"][a]["seconds"] for a in ARMS},
                      "compiler_selected": row["arms"][COMPILED].get("selected"),
                      "independent_agrees": row["independent"]["truth_agrees"] and all(
                          a["agrees"] for a in row["independent"]["arms"].values())}), flush=True)
    return row


def _job(job):
    return _run_item(*job), _process_record()


def _merge(records) -> dict:
    loaded, executed, distributions = set(), {}, {}
    for record in records:
        loaded |= set(record["loaded"])
        distributions.update(record["distributions"])
        if record["executed"] is None:
            executed = None
        elif executed is not None:
            for path, sha in record["executed"].items():
                executed[path] = sha if executed.get(path, sha) == sha else f"conflict:{executed[path]},{sha}"
    return {"loaded": sorted(loaded), "executed": executed, "distributions": dict(sorted(distributions.items()))}


def worker_pool(workers, cores=None):
    """The pinned fork pool, or None for one process. Fork it while this process is still single-threaded: the
    solver libraries start native threads (8 after one item), and a pool forked after them deadlocked the first
    held-out attempt of 2026-10-16 before any held-out item finished."""
    if workers <= 1:
        return None
    import multiprocessing
    cores = sorted(cores or os.sched_getaffinity(0))
    if len(cores) < workers:
        raise SystemExit(f"{workers} workers need {workers} cores; {len(cores)} available")
    context = multiprocessing.get_context("fork")
    counter = context.Value("i", 0)
    return context.Pool(workers, initializer=V4._pin, initargs=(cores[:workers], counter), maxtasksperchild=None)


def run_items(items, partition, workers=1, cores=None, token=None, pool=None):
    """Each item runs whole on one process (arms rotated by index, as in v4); with ``workers`` > 1 the items are
    spread over that many processes, each pinned to its own core (or over ``pool``, forked earlier by
    ``worker_pool``). Held-out items need the token ``heldout_gate`` issued (used once). Returns the rows in suite
    order and what every process loaded and executed."""
    if any(i["partition"] != partition for i in items):
        raise SystemExit(f"refusing to run an item outside the {partition} partition")
    if partition == "heldout":
        if token not in _ISSUED:
            raise SystemExit("HELDOUT_TOKEN: held-out items run only with the token heldout_gate issues, once")
        _ISSUED.discard(token)
    jobs = [(index, item) for index, item in enumerate(items)]
    if pool is not None:
        done = list(pool.imap(_job, jobs, chunksize=1))
    elif workers <= 1:
        done = [_job(j) for j in jobs]
    else:
        with worker_pool(workers, cores) as own:
            done = list(own.imap(_job, jobs, chunksize=1))
    return {"rows": [row for row, _ in done], **_merge([_process_record(), *(record for _, record in done)])}


def _other_python_processes(proc: Path = Path("/proc"), me: int | None = None) -> int | None:
    """Python processes on the machine other than this one and its children (from /proc), or None without /proc."""
    me = os.getpid() if me is None else me
    if not proc.is_dir():
        return None
    count = 0
    for entry in proc.iterdir():
        if not entry.name.isdigit() or int(entry.name) == me:
            continue
        try:
            argv0 = (entry / "cmdline").read_bytes().split(b"\0")[0].decode(errors="replace")
            ppid = int((entry / "stat").read_text().rsplit(")", 1)[1].split()[1])
        except (OSError, ValueError, IndexError):
            continue
        if ppid != me and os.path.basename(argv0).startswith("python"):
            count += 1
    return count


def machine_load() -> dict:
    return {"at": datetime.now(timezone.utc).isoformat(), "loadavg_1_5_15_min": [round(x, 2) for x in os.getloadavg()],
            "cpu_count": os.cpu_count(), "affinity": sorted(os.sched_getaffinity(0)),
            "other_python_processes": _other_python_processes()}


def _header(workers, cores) -> dict:
    return {"started_at": datetime.now(timezone.utc).isoformat(),
            "source_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                                            text=True).stdout.strip() or None,
            "platform": platform.platform(), "python": sys.version.split()[0], "workers": workers, "cores": cores,
            "isolated": _isolated(), "dont_write_bytecode": sys.dont_write_bytecode,
            "source_only_loader": _hook() is not None, "machine_load_start": machine_load()}


LIMITS = ["a declared re-use of P6 v4's held-out items, looked at twice before this run (v4's run, and the Track B "
          "audit, which rebuilt them and re-scored v4's recorded plans without running the genome); it cannot change "
          "v4's verdict and is not a new natural family for VPL",
          "real topologies, link lengths, demand pairs and ECMP loads; the planning layer (modules, utilisation, "
          "admissible paths, prices, arc limit, budget) is v4's declared layer, not SNDlib's capacities or costs",
          "the truth is the exact optimum of v4's declared problem (suite-v4.json), not a realised outcome",
          "items within one network share its topology; the item sign test treats them as independent; a "
          "per-network breakdown is reported",
          "latency is end to end through greg.cognition.cortex.reason (isolated solver and verifier workers per "
          "operation, compiling the repository source they import), on this machine; PMCF runs in process and its "
          "latency is not comparable",
          "F7_LIFT_WITH_GENOME is a secondary reading of v4's rule: v4's constituents' optimal and wrong counts are "
          "v4's frozen ones (machine-independent), their latencies are never compared, and it cannot change v4's "
          "verdict",
          "SNDlib redistribution terms are unresolved (release blocker, founder decision)"]


def _after_the_look(rows, ran, frozen, v4):
    """The summary and every post-run integrity problem (empty when the run is valid)."""
    summary = summarize(rows, v4)
    appeared, changed = bytecode_files(), differences(frozen, inputs())
    invalid = (integrity(frozen["code"], ran) + receipt_problems(rows)
               + ([f"bytecode appeared in the checkout during the run: {appeared[:5]}"] if appeared else [])
               + ([f"frozen inputs changed during the run: {changed[:10]}"] if changed else []))
    return summary, invalid


def _look(args, gate, pool):
    """The warm-up (one development item in this process, never scored), then the one held-out run."""
    warmup = run_items(suite_items("dev")[:1], "dev")                  # imports before the look, never scored
    problems = integrity(gate["inputs"]["code"], warmup) + receipt_problems(warmup["rows"])
    if problems:
        raise SystemExit(f"UNFROZEN_CODE: the warm-up executed code the freeze does not cover: {problems}")
    raised = [f"{arm}: {record['exception']}" for row in warmup["rows"] for arm, record in row["arms"].items()
              if record.get("state") == ARM_EXCEPTION]
    if raised:
        raise SystemExit(f"WARMUP_ARM_EXCEPTION: an arm raised on the warm-up item, so the look would not measure "
                         f"it: {raised}")
    return run_items(suite_items("heldout"), "heldout", args.workers, token=gate["token"], pool=pool), warmup


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--freeze", action="store_true", help="write freeze-v6-attempt2.json (a clean tree is required)")
    ap.add_argument("--development", action="store_true",
                    help="builders only: run the development items, never the held-out items")
    ap.add_argument("--check-gate", action="store_true",
                    help="run the held-out gate and stop before any held-out item is read (this process as it is at "
                         "gate time only; the warm-up of the real run completes the pre-look check)")
    ap.add_argument("--limit", type=int, help="with --development only: the first N development items")
    ap.add_argument("--out", type=Path, help="where to write the results (required for a held-out run)")
    ap.add_argument("--workers", type=int, default=1, help="processes, one pinned core each (latency stays per core)")
    ap.add_argument("--cores", type=str, help="comma-separated cores for the workers (default: all available)")
    args = ap.parse_args(argv)
    cores = [int(c) for c in args.cores.split(",")] if args.cores else None
    if args.freeze:
        freeze()
        return
    if args.limit is not None and not args.development:
        raise SystemExit("--limit applies to development runs only; a held-out run evaluates every held-out item")
    if args.check_gate:
        gate = heldout_gate()
        _ISSUED.discard(gate["token"])
        print(f"GATE PASS: {len(gate['inputs']['code'])} frozen files; no held-out item was read")
        return
    if args.development:
        items = suite_items("dev")
        items = items[:args.limit] if args.limit is not None else items
        header = _header(args.workers, cores)
        problems, v4 = preconditions(), v4_constituents("dev")
        ran = run_items(items, "dev", args.workers, cores)
        rows, frozen = ran["rows"], set(code_closure())
        report = {"schema": "greg-f7-single-genome-development/6", "partition": "dev",
                  "role": "builder's development run: not evidence, never a verdict", **header,
                  "finished_at": datetime.now(timezone.utc).isoformat(), "machine_load_end": machine_load(),
                  "preconditions": problems, "unfrozen_repository_files_loaded": sorted(set(ran["loaded"]) - frozen),
                  "integrity_against_current_closure": (
                      integrity({p: V1._sha(ROOT / p) for p in frozen}, ran) if ran["executed"] is not None
                      else ["not run: the source-only loader is not installed (imported, not started as a script)"]),
                  "receipt_problems": receipt_problems(rows), "distributions_loaded_by_parent_and_pool":
                      ran["distributions"], "rows": rows, "summary": summarize(rows, v4)}
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(json.dumps(report, indent=1) + "\n")
        print(json.dumps({k: report[k] for k in ("preconditions", "unfrozen_repository_files_loaded",
                                                 "integrity_against_current_closure", "receipt_problems")}, indent=1))
        print(json.dumps(report["summary"], indent=1))
        return
    if not args.out:
        raise SystemExit("--out required")
    if args.out.exists():
        raise SystemExit(f"refusing to overwrite {args.out}")
    gate = heldout_gate()
    frozen = gate["inputs"]
    v4 = v4_constituents("heldout")                                    # v4's frozen counts, read before the look
    header = _header(args.workers, cores)
    pool = worker_pool(args.workers, cores)          # forked before the warm-up starts any solver thread
    try:
        ran, warmup = _look(args, gate, pool)
    finally:
        if pool is not None:
            pool.terminate()
    rows = ran["rows"]
    try:
        summary, invalid = _after_the_look(rows, ran, frozen, v4)
    except Exception as exc:             # the report is written whatever a post-run step does
        summary, invalid = {"n": len(rows)}, [f"POST_RUN_EXCEPTION: {type(exc).__name__}: {str(exc)[:500]}"]
    if invalid:
        for key in ("rule", "f7_lift_with_genome"):
            summary[key] = {"outcome": "INVALID_RUN", "why": invalid, "as_measured": summary.get(key)}
    report = {"schema": "greg-f7-single-genome-results/6", "manifest_sha256": V1._sha(MANIFEST), **header,
              "finished_at": datetime.now(timezone.utc).isoformat(), "machine_load_end": machine_load(),
              "integrity": invalid, "executed_repository_files": ran["executed"],
              "distributions_loaded_by_parent_and_pool": ran["distributions"], "warmup": warmup["rows"],
              "out_of_scope": json.loads(SUITE.read_text())["out_of_scope"],
              "heldout": rows, "summary": summary, "limits": LIMITS}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
