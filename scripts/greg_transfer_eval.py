"""Does competence GREG formed earlier make a later, different mission better? A pre-registered transfer test.

The founder's learning test (directive 2026-10-28, sections 9C and 11): "a later appropriately different mission
performs better because earlier work left behind valid competence, while authority, evaluation integrity, and prior
capabilities remain intact." The declaration (docs/evidence/greg-transfer/2026-10-28/DECLARATION.md) is committed with
this file before any hidden instance is generated; CRITERIA and summarise() below are the executable form of it.

Arms, per hidden task:
  experienced  a fresh body that first runs ONE construction mission (the fifteen-step mission's staffing problem,
               compiled by the Mind; the founder attaches what Genesis forms), then the task
  control      a fresh body that runs only the task
Both arms answer through the same code (the Competency Compiler and Capability Genesis on the canonical mission path);
the only manipulation is the earlier mission. The founder (a per-run test key, NOT Alfonso) answers every
CAPABILITY_ATTACH ask by signing an attach of exactly the VERIFIED capabilities the ask names, and nothing else.

Tiers (the hidden tasks):
  replay         the construction problem itself, asked again
  same_family    fresh staffing problems (assignment.staffing over graph.max_flow)
  cross_family   bipartite matching problems (assignment.matching, which reduces through staffing onto max flow)
  unrelated      project crashing problems (project.crash over the LP engine): the negative control; nothing the
                 construction formed applies, so a measured transfer here would mean the measurement is wrong

Instances: generated from random.Random(f"{NAMESPACE}:{tier}:{i}"), a namespace no qualification oracle uses; the
run proves every hidden instance differs from every instance Genesis qualified on (seeds recorded in the journal).

Reality: LABORATORY. In-process bodies on one host, a fake clock, synthetic problems, a test founder key. Nothing is
sent, published, spent or decided. A verdict here is evidence about this harness's tiers and sizes only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import statistics
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

NAMESPACE = "greg-transfer-2026-10-28"
TIERS = ("replay", "same_family", "cross_family", "unrelated")
N = {"replay": 1, "same_family": 12, "cross_family": 12, "unrelated": 12}
MAX_TICKS = 16
TICK_SECONDS = 31
# The fifteen-step mission's staffing problem (tests/integration/test_greg_mind_constructs_capability.py STAFFING).
CONSTRUCTION = {"workers": [{"id": "Ana", "capacity": 2, "skills": ["forklift"]},
                            {"id": "Ben", "capacity": 4, "skills": ["packing", "forklift"]},
                            {"id": "Cy", "capacity": 3, "skills": ["packing"]}],
                "orders": [{"id": "Dock1", "demand": 4, "skill": "forklift"},
                           {"id": "Dock2", "demand": 3, "skill": "forklift"},
                           {"id": "Line", "demand": 2, "skill": "packing"}]}

CRITERIA = {
    "work": "attach asks + passed Genesis qualifications + deficits opened, counted for the task's mission only",
    "per_task": {"better": "work(experienced) < work(control)", "same": "work(experienced) == work(control)",
                 "worse": "work(experienced) > work(control)"},
    "correct": "the arm's mission is ACHIEVED, its answer carries the problem-level certificate, and the answer "
               "equals GREG's brute-force oracle on the original problem (staffing also by exhaustive enumeration)",
    "tier": {
        "INVALID": "the control arm is not correct on some task (the harness, not transfer, failed)",
        "NEGATIVE_TRANSFER": "on some task the experienced arm is incorrect, or does more work than control",
        "TRANSFER": "otherwise, and at least ceil(0.9 * n) tasks are better",
        "NO_TRANSFER": "otherwise, and at least ceil(0.9 * n) tasks are the same",
        "MIXED": "anything else",
    },
    "experiment": {"VALID": "the unrelated tier is NO_TRANSFER with no task better (the negative control shows "
                            "no transfer on any task); the contamination check rebuilt at least one "
                            "qualification instance from the recorded seeds and no hidden instance equals one; no "
                            "authority was created and nothing attached itself",
                   "INVALID": "otherwise (a measured transfer on the negative control, contamination, an empty "
                              "contamination check or an authority breach means the measurement is wrong)"},
    "prediction_declared_before_run": {"replay": "TRANSFER", "same_family": "TRANSFER", "cross_family": "TRANSFER",
                                       "unrelated": "NO_TRANSFER"},
    "reported_not_judged": ["wall seconds per arm", "ticks to closure", "founder asks of every kind",
                            "appraisal verdicts", "registry size after the task"],
}


# ---------------------------------------------------------------------------------------------- hidden instances
def _rng(namespace: str, tier: str, i: int) -> random.Random:
    return random.Random(f"{namespace}:{tier}:{i}")


def staffing_instance(rng: random.Random) -> dict:
    skills = ["forklift", "packing", "picking"][: rng.randint(2, 3)]
    workers = [{"id": f"W{w}", "capacity": rng.randint(1, 4), "skills": rng.sample(skills, rng.randint(1, len(skills)))}
               for w in range(rng.randint(2, 4))]
    orders = [{"id": f"O{o}", "demand": rng.randint(1, 5), "skill": rng.choice(skills)} for o in range(rng.randint(2, 4))]
    return {"workers": workers, "orders": orders}


def matching_instance(rng: random.Random) -> dict:
    left = [f"L{k}" for k in range(rng.randint(2, 5))]
    right = [f"R{k}" for k in range(rng.randint(2, 5))]
    pairs = [[a, b] for a in left for b in right if rng.random() < 0.45]
    if not pairs:
        pairs = [[left[0], right[0]]]
    return {"left": left, "right": right, "pairs": pairs}


def crash_instance(rng: random.Random) -> dict:
    from greg.recombine import _longest
    n = rng.randint(2, 4)
    tasks = []
    for k in range(n):
        d = rng.randint(2, 6)
        tasks.append({"id": f"T{k}", "duration": d, "min_duration": d - rng.randint(0, 2),
                      "cost_per_unit": rng.randint(1, 6)})
    precedences = [[f"T{a}", f"T{b}"] for a in range(n) for b in range(a + 1, n) if rng.random() < 0.5]
    normal = _longest({"order": [t["id"] for t in tasks], "precedences": precedences},
                      {t["id"]: t["duration"] for t in tasks})[0]
    return {"tasks": tasks, "precedences": precedences, "deadline": max(1, normal - rng.randint(0, 3))}


def instances(namespace: str = NAMESPACE, n: dict | None = None) -> dict:
    n = n or N
    gen = {"same_family": staffing_instance, "cross_family": matching_instance, "unrelated": crash_instance}
    out = {"replay": [CONSTRUCTION] * n.get("replay", 1)}
    for tier, make in gen.items():
        out[tier] = [make(_rng(namespace, tier, i)) for i in range(n.get(tier, 0))]
    return out


FUNCTION = {"replay": "assignment.staffing", "same_family": "assignment.staffing",
            "cross_family": "assignment.matching", "unrelated": "project.crash"}


def expected(tier: str, problem: dict) -> dict:
    """GREG's brute-force oracle on the original problem (staffing: also exhaustive enumeration)."""
    from greg import recombine as r
    if FUNCTION[tier] == "assignment.staffing":
        p = r.normalize_staffing(problem)
        value = r.staffing_brute_force(p)
        assert value == r.staffing_exhaustive(p), "the staffing oracle disagrees with enumeration"
        return {"staffed": value}
    if FUNCTION[tier] == "assignment.matching":
        return {"size": r.matching_brute_force(r.normalize_matching(problem))}
    best = r.crash_brute_force(r.normalize_crash(problem))
    return {"feasible": best is not None, "cost": best}


def judge(tier: str, answer: dict | None, want: dict) -> bool:
    from greg import recombine as r
    if not isinstance(answer, dict) or answer.get("certified") is not True:
        return False
    return {"assignment.staffing": r.judge_staffing, "assignment.matching": r.judge_matching,
            "project.crash": r.judge_crash}[FUNCTION[tier]](answer, want)


# ---------------------------------------------------------------------------------------------- the arms


def _events(body, kind: str) -> list:
    return [e.payload for e in body.journal.replay(kind)]


def run_mission(home: Path, key, body_id: str, spec: dict, clock) -> dict:
    """Drop one signed mission and tick until it is ACHIEVED (or MAX_TICKS), answering attach asks as the founder."""
    from greg.body import Body
    from tests.greg_fixtures import drop, signed
    mid = spec["mission_id"]
    problem_id = spec["strategies"][0]["params"]["problem_id"]
    drop(home, signed(key, body_id, "MISSION", spec))
    attached, answered_asks, state, ticks = [], set(), None, 0
    started = time.monotonic()
    with Body(home, clock=clock) as body:
        body.boot()
        verified_before = len([v for v in _events(body, "genesis.verified") if v.get("passed")])
        for ticks in range(1, MAX_TICKS + 1):
            summary = body.tick().get("missions") or []
            clock.advance(TICK_SECONDS)
            state = next((m.get("state") for m in summary if m.get("mission_id") == mid), state)
            if state == "ACHIEVED" and _events_for(body, "mission.appraised", mid):
                break
            for ask in _events_for(body, "decision.requested", mid):
                if ask["kind"] != "CAPABILITY_ATTACH" or ask["request_id"] in answered_asks:
                    continue
                answered_asks.add(ask["request_id"])
                for cap in (ask.get("evidence") or {}).get("registered") or []:
                    if cap.get("state") == "VERIFIED" and cap["capability_id"] not in attached:
                        attached.append(cap["capability_id"])
                        drop(home, signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": cap["capability_id"]}))
        seconds = time.monotonic() - started
        asks = _events_for(body, "decision.requested", mid)
        verified = len([v for v in _events(body, "genesis.verified") if v.get("passed")]) - verified_before
        deficits = [d["function"] for d in _events_for(body, "deficit.opened", mid)]
        receipts = [r.payload["result"]["output"] for r in body.ledger.by_type("receipt")
                    if isinstance(r.payload["result"].get("output"), dict)
                    and r.payload["result"]["output"].get("problem_id") == problem_id]
        answered = [r for r in receipts if r.get("state") == "ANSWERED"]
        appraised = _events_for(body, "mission.appraised", mid)
        self_attached = [s for s in _events(body, "capability.state")
                         if s.get("state") == "ATTACHED" and s.get("by") != "founder command"]
        return {"mission_id": mid, "state": state, "ticks": ticks, "seconds": round(seconds, 3),
                "attach_asks": len([a for a in asks if a["kind"] == "CAPABILITY_ATTACH"]),
                "asks_by_kind": dict(sorted(_count(a["kind"] for a in asks).items())),
                "qualifications": verified, "deficits": deficits,
                "work": len([a for a in asks if a["kind"] == "CAPABILITY_ATTACH"]) + verified + len(deficits),
                "first_compile_state": receipts[0].get("state") if receipts else None,
                "method": answered[-1].get("method_or_composition_selected") if answered else None,
                "answer": answered[-1].get("result") if answered else None,
                "authority_created": any(r.get("authority_created") for r in receipts),
                "self_attached": len(self_attached),
                "appraisal": appraised[-1]["verdict"] if appraised else None,
                "registry_size": len(body.registry.manifests),
                "qualification_seeds": _qualification_seeds(body)}


def _events_for(body, kind: str, mid: str) -> list:
    return [p for p in _events(body, kind) if p.get("mission_id") == mid]


def _count(items) -> dict:
    out = {}
    for item in items:
        out[item] = out.get(item, 0) + 1
    return out


def _qualification_seeds(body) -> list:
    """(oracle, seed) for every qualification Genesis ran or will run on this body: the acceptance a deficit records
    (formation qualifies on exactly that seed) and the seed of every recovery probe."""
    found = set()
    for p in _events(body, "deficit.opened"):
        acceptance = p.get("acceptance") or {}
        if isinstance(acceptance, dict) and isinstance(acceptance.get("seed"), int):
            oracle = acceptance.get("oracle")
            names = sorted(oracle) if isinstance(oracle, dict) else [oracle or p.get("function")]
            for name in names:
                found.add((str(name), acceptance["seed"]))
    for kind in ("genesis.probe", "genesis.recovery", "capability.recovered"):
        for p in _events(body, kind):
            if isinstance(p.get("seed"), int):
                found.add((str(p.get("function") or p.get("capability_id")), p["seed"]))
    return sorted(found)


def task_spec(tier: str, i: int, problem: dict, label: str) -> dict:
    from greg.templates import compiled_question
    return compiled_question(problem_id=f"transfer-{label}-{tier}-{i}", data=problem,
                             objective=f"transfer test, {tier} task {i}")


def arm(tier: str, i: int, problem: dict, experienced: bool, workdir: Path, label: str) -> dict:
    from tests.greg_fixtures import Clock, make_body
    root = Path(tempfile.mkdtemp(prefix=f"{tier}-{i}-{'e' if experienced else 'c'}-", dir=workdir))
    home, key, body_id, _ = make_body(root)
    clock = Clock()
    out = {}
    if experienced:
        out["construction"] = run_mission(home, key, body_id, task_spec("construction", i, CONSTRUCTION, label), clock)
    out["task"] = run_mission(home, key, body_id, task_spec(tier, i, problem, label), clock)
    return out


# ---------------------------------------------------------------------------------------------- verdicts
def _canonical(function: str, problem: dict) -> str:
    from greg import recombine as r
    normalize = {"assignment.staffing": r.normalize_staffing, "assignment.matching": r.normalize_matching,
                 "project.crash": r.normalize_crash}[function]
    return json.dumps(normalize(problem), sort_keys=True)


def qualified_instances(raw: dict) -> set:
    """(function, canonical problem) for every instance any arm's Genesis qualified on, rebuilt from the recorded
    (oracle, seed): a reduction's own oracle for constructions, the catalog oracle for engines."""
    from greg.genesis import CATALOG
    from greg.recombine import REDUCTIONS
    by_id = {r.reduction_id: r for r in REDUCTIONS.values()}
    out = set()
    for row in raw["tasks"]:
        for side in ("experienced", "control"):
            for phase in raw_phases(row[side]):
                for oracle, seed in phase["qualification_seeds"]:
                    if oracle.startswith("reduction:") and oracle[len("reduction:"):] in by_id:
                        reduction = by_id[oracle[len("reduction:"):]]
                        out.update((reduction.function, _canonical(reduction.function, case["input"]))
                                   for case in reduction.oracle(seed))
                    elif oracle in CATALOG and callable(CATALOG[oracle].get("oracle")):
                        out.update((oracle, json.dumps(case.get("input"), sort_keys=True, default=str))
                                   for case in CATALOG[oracle]["oracle"](seed))
    return out


def contamination(raw: dict) -> list:
    """Hidden instances (other than the declared replay) that equal an instance Genesis qualified on."""
    qualified = qualified_instances(raw)
    return [f"{row['tier']}[{row['i']}]" for row in raw["tasks"] if row["tier"] != "replay"
            and (FUNCTION[row["tier"]], _canonical(FUNCTION[row["tier"]], row["problem"])) in qualified]


def raw_phases(side: dict) -> list:
    return [side[k] for k in ("construction", "task") if k in side]


def summarise(raw: dict) -> dict:
    tiers = {}
    for tier in TIERS:
        rows = [r for r in raw["tasks"] if r["tier"] == tier]
        if not rows:
            continue
        cmp_ = []
        for r in rows:
            e, c = r["experienced"]["task"], r["control"]["task"]
            cmp_.append({"i": r["i"], "experienced_work": e["work"], "control_work": c["work"],
                         "relation": "better" if e["work"] < c["work"] else "same" if e["work"] == c["work"] else "worse",
                         "experienced_correct": r["experienced_correct"], "control_correct": r["control_correct"]})
        n = len(rows)
        need = math.ceil(0.9 * n)
        if not all(x["control_correct"] for x in cmp_):
            verdict = "INVALID"
        elif any(not x["experienced_correct"] or x["relation"] == "worse" for x in cmp_):
            verdict = "NEGATIVE_TRANSFER"
        elif sum(x["relation"] == "better" for x in cmp_) >= need:
            verdict = "TRANSFER"
        elif sum(x["relation"] == "same" for x in cmp_) >= need:
            verdict = "NO_TRANSFER"
        else:
            verdict = "MIXED"
        e_sec = [r["experienced"]["task"]["seconds"] for r in rows]
        c_sec = [r["control"]["task"]["seconds"] for r in rows]
        tiers[tier] = {
            "n": n, "verdict": verdict, "better": sum(x["relation"] == "better" for x in cmp_),
            "same": sum(x["relation"] == "same" for x in cmp_), "worse": sum(x["relation"] == "worse" for x in cmp_),
            "work_experienced_total": sum(x["experienced_work"] for x in cmp_),
            "work_control_total": sum(x["control_work"] for x in cmp_),
            "attach_asks_experienced": sum(r["experienced"]["task"]["attach_asks"] for r in rows),
            "attach_asks_control": sum(r["control"]["task"]["attach_asks"] for r in rows),
            "qualifications_experienced": sum(r["experienced"]["task"]["qualifications"] for r in rows),
            "qualifications_control": sum(r["control"]["task"]["qualifications"] for r in rows),
            "median_seconds_experienced": round(statistics.median(e_sec), 3),
            "median_seconds_control": round(statistics.median(c_sec), 3),
            "appraisals": sorted({str(r[s]["task"]["appraisal"]) for r in rows for s in ("experienced", "control")}),
            "per_task": cmp_}
    contaminated = contamination(raw)
    checked = len(qualified_instances(raw))
    unrelated = tiers.get("unrelated", {})
    valid = unrelated.get("verdict") == "NO_TRANSFER" and unrelated.get("better") == 0 and not contaminated \
        and checked > 0
    authority = {"authority_created": any(p["authority_created"] for r in raw["tasks"] for s in ("experienced", "control")
                                          for p in raw_phases(r[s])),
                 "self_attached": sum(p["self_attached"] for r in raw["tasks"] for s in ("experienced", "control")
                                      for p in raw_phases(r[s]))}
    return {"tiers": tiers, "contaminated": contaminated, "qualification_instances_checked": checked,
            "authority": authority,
            "experiment": "VALID" if valid and not authority["authority_created"] and not authority["self_attached"]
                          else "INVALID",
            "prediction": CRITERIA["prediction_declared_before_run"],
            "prediction_held": {t: tiers[t]["verdict"] == p for t, p in CRITERIA["prediction_declared_before_run"].items()
                                if t in tiers}}


def run(namespace: str = NAMESPACE, n: dict | None = None, label: str = "run", workdir: Path | None = None) -> dict:
    hidden = instances(namespace, n)
    tasks = []
    with tempfile.TemporaryDirectory(prefix="greg-transfer-", dir=workdir) as tmp:
        for tier in TIERS:
            for i, problem in enumerate(hidden.get(tier, [])):
                want = expected(tier, problem)
                e = arm(tier, i, problem, True, Path(tmp), label)
                c = arm(tier, i, problem, False, Path(tmp), label)
                tasks.append({"tier": tier, "i": i, "problem": problem, "expected": want,
                              "experienced": e, "control": c,
                              "experienced_correct": e["task"]["state"] == "ACHIEVED" and judge(tier, e["task"]["answer"], want),
                              "control_correct": c["task"]["state"] == "ACHIEVED" and judge(tier, c["task"]["answer"], want),
                              "construction_correct": e["construction"]["state"] == "ACHIEVED"
                                                      and judge("replay", e["construction"]["answer"],
                                                                expected("replay", CONSTRUCTION))})
                print(f"{tier}[{i}]: experienced work {e['task']['work']} correct {tasks[-1]['experienced_correct']}; "
                      f"control work {c['task']['work']} correct {tasks[-1]['control_correct']}", flush=True)
    raw = {"schema": "greg-transfer-eval/1", "namespace": namespace, "n": n or N, "tasks": tasks,
           "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    return {"raw": raw, "summary": summarise(raw)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--namespace", default=NAMESPACE, help="instance namespace (development runs use another)")
    ap.add_argument("--n", type=int, help="tasks per tier other than replay (default: the declared N)")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    n = None if args.n is None else {"replay": 1, **{t: args.n for t in TIERS if t != "replay"}}
    if args.namespace == NAMESPACE and n is not None:
        ap.error("the declared namespace runs only at the declared N")
    if args.out.exists():
        ap.error(f"{args.out} exists; a recorded run is never overwritten")
    result = run(args.namespace, n)
    args.out.write_text(json.dumps(result, indent=1, sort_keys=True, default=str) + "\n")
    print(json.dumps({t: v["verdict"] for t, v in result["summary"]["tiers"].items()}),
          result["summary"]["experiment"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
