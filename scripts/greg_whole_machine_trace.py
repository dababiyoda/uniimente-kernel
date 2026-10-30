#!/usr/bin/env python3
"""Reproducible whole-machine trace: one consequence-inert GREG mission end to end on the canonical path.

Directive 2026-10-21 section 8 ("Integrate the Mind with persistent Goal Gravity and the organs"), sections 7 and
10, and INTENT-20261001-FULL-MACHINE-COMPLETION. Nothing here is a second engine: every step runs through the
existing body (greg/body.py), founder-signed inbox (greg/founder.py), mission engine (greg/missions.py), Kernel
Consequence Gate, Competency Compiler (greg/cognition/compiler.py via ``cognition.solve`` -> ``cortex.reason``),
Capability Genesis (greg/genesis.py), separate-process appraiser (greg/appraisal.py), cognition settlement
(greg/cognition/settlement.py), and the registered organ contracts and adapters (contracts/, adapters/, linker/).

The mission is GREG's own operating need, on natural data read from this checkout:

  * sub-problem A, critical path: the module import graph of ``greg/cognition`` (top-level imports, read with
    ``ast``) as an integer schedule; the minimum makespan is the longest dependency chain, i.e. how many
    sequential review/test stages a change touching every module needs. Durations are a PROXY (ceil(lines/100)).
  * sub-problem B, CI shard assignment: assign test-file groups of this repository to distinct jobs of
    ``.github/workflows/*.yml`` minimising the summed share of each job's ``timeout-minutes`` budget, never placing
    a group on a job that does not install the solver requirements its tests import. Group sizes, job timeouts and
    installed requirements are natural; the minutes-per-line constant is SYNTHETIC (no CI timing data offline).

Everything runs in a temporary state directory with a per-run test founder key (real Ed25519, not Alfonso's
key). The body's clock is accelerated (each tick advances 31 s) so waiting cadences pass in seconds; that is the
only departure from the CLI ``greg run`` loop and it is labelled in the trace. No network, no external effect, no
spend, no activation outside the temporary directory. VEPMC stays 0.

    python scripts/greg_whole_machine_trace.py --out docs/evidence/greg-whole-machine-trace/2026-10-21
"""
from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
import glob
import hashlib
import importlib.metadata
import itertools
import json
import math
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TICK_ADVANCE_SECONDS = 31
SCHEMA = "greg-whole-machine-trace/1.0"
SCIPY_ASSIGNMENT = "acquired.cognition.mechanism:linear_assignment.scipy"
LINES_PER_STAGE = 100            # PROXY: one review/test stage per 100 source lines
TEST_LINES_PER_CI_MINUTE = 400   # SYNTHETIC calibration constant: no CI timing data was available offline
MISSING_REQUIREMENT_PENALTY = 1000


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def sha(value) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode()).hexdigest()


# ------------------------------------------------------------------ natural data from this checkout
def module_graph(package_dir: str, package: str) -> dict:
    """Top-level intra-package imports (module -> module it imports). Function-local imports are excluded."""
    mods = {p.stem: p for p in sorted((ROOT / package_dir).glob("*.py")) if p.stem != "__init__"}
    edges = set()
    for name, path in mods.items():
        for node in ast.parse(path.read_text()).body:
            if not isinstance(node, ast.ImportFrom):
                continue
            if node.level == 1 and not node.module:
                targets = [a.name for a in node.names]
            elif node.level == 1:
                targets = [node.module.split(".")[0]]
            elif node.level == 0 and node.module and node.module.startswith(package + "."):
                targets = [node.module[len(package) + 1:].split(".")[0]]
            else:
                continue
            edges.update((name, t) for t in targets if t in mods and t != name)
    lines = {m: len(p.read_text().splitlines()) for m, p in mods.items()}
    return {"package": package, "modules": sorted(mods), "edges": sorted(edges), "lines": lines,
            "duration": {m: max(1, math.ceil(n / LINES_PER_STAGE)) for m, n in lines.items()},
            "source_digest": sha({m: hashlib.sha256(p.read_bytes()).hexdigest() for m, p in mods.items()})}


def critical_path_data(graph: dict) -> dict:
    """Integer schedule: a module starts after every module it imports has finished; minimise the makespan."""
    dur, horizon = graph["duration"], sum(graph["duration"].values())
    variables = {f"s_{m}": [0, horizon] for m in graph["modules"]}
    variables["makespan"] = [0, horizon]
    constraints = [{"coefficients": {f"s_{m}": 1, f"s_{d}": -1}, "op": ">=", "rhs": dur[d]}
                   for m, d in graph["edges"]]
    constraints += [{"coefficients": {"makespan": 1, f"s_{m}": -1}, "op": ">=", "rhs": dur[m]}
                    for m in graph["modules"]]
    return {"variables": variables, "constraints": constraints,
            "objective": {"coefficients": {"makespan": 1}, "sense": "min"}}


def independent_longest_chain(graph: dict) -> dict:
    """Independent check with NetworkX topological DP (shares no code with CP-SAT, Z3 or the compiler)."""
    import networkx as nx
    g = nx.DiGraph()
    g.add_nodes_from(graph["modules"])
    g.add_edges_from((d, m) for m, d in graph["edges"])        # prerequisite -> dependent
    if not nx.is_directed_acyclic_graph(g):
        return {"acyclic": False}
    finish, parent = {}, {}
    for n in nx.topological_sort(g):
        preds = list(g.predecessors(n))
        best = max(preds, key=lambda p: finish[p], default=None)
        finish[n] = graph["duration"][n] + (finish[best] if best else 0)
        parent[n] = best
    end = max(finish, key=finish.get)
    chain = [end]
    while parent[chain[-1]]:
        chain.append(parent[chain[-1]])
    return {"acyclic": True, "makespan": finish[end], "chain": chain[::-1], "engine": f"networkx {nx.__version__}"}


def ci_jobs(selection: list[tuple[str, str]]) -> list[dict]:
    import yaml
    out = []
    for workflow, job_id in selection:
        path = ROOT / ".github" / "workflows" / workflow
        job = yaml.safe_load(path.read_text())["jobs"][job_id]
        runs = " ".join(str(step.get("run", "")) for step in job.get("steps", []))
        installs = sorted(r for r in ("requirements-dev", "requirements-cognition", "requirements-cortex")
                          if r in runs)
        out.append({"job": f"{workflow}:{job_id}", "timeout_minutes": job.get("timeout-minutes"),
                    "installs": installs, "workflow_sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    return out


def test_groups(spec: list[tuple[str, list[str], list[str]]]) -> list[dict]:
    out = []
    for name, patterns, needs in spec:
        files = sorted({f for p in patterns for f in glob.glob(str(ROOT / p))})
        lines = sum(len(Path(f).read_text().splitlines()) for f in files)
        out.append({"group": name, "patterns": patterns, "files": len(files), "test_lines": lines,
                    "needs": needs, "proxy_minutes": max(1, math.ceil(lines / TEST_LINES_PER_CI_MINUTE))})
    return out


def assignment_costs(groups: list[dict], jobs: list[dict]) -> list[list[int]]:
    costs = []
    for g in groups:
        row = []
        for j in jobs:
            share = math.ceil(100 * g["proxy_minutes"] / (j["timeout_minutes"] or 360))   # GitHub default 360
            lacks = [n for n in g["needs"] if n not in j["installs"]]
            row.append(share + (MISSING_REQUIREMENT_PENALTY if lacks else 0))
        costs.append(row)
    return costs


def independent_assignment(costs: list[list[int]]) -> dict:
    """Exhaustive enumeration of every injective row->column map (independent of SciPy and GREG's certificate)."""
    rows, cols = len(costs), len(costs[0])
    best = min(itertools.permutations(range(cols), rows), key=lambda p: (sum(costs[i][j] for i, j in enumerate(p)), p))
    return {"total": sum(costs[i][j] for i, j in enumerate(best)), "pairs": [[i, j] for i, j in enumerate(best)],
            "maps_enumerated": math.perm(cols, rows), "engine": "itertools.permutations (exhaustive)"}


MISSION_CLASSES = {
    "m:ci-plan-cognition": {
        "package": ("greg/cognition", "greg.cognition"),
        "groups": [("greg-cognition-unit", ["tests/unit/test_greg_cognition*.py",
                                            "tests/unit/test_greg_competency_compiler.py"],
                    ["requirements-cognition"]),
                   ("cortex-unit", ["tests/unit/test_cortex_*.py"], ["requirements-cognition", "requirements-cortex"]),
                   ("greg-integration", ["tests/integration/test_greg_*.py"], ["requirements-cognition"]),
                   ("contracts-adapters", ["tests/unit/test_required_schema_formats.py",
                                           "tests/integration/test_phase_zero_connection.py",
                                           "tests/unit/test_shared_durable_boundary.py"], ["requirements-dev"])],
        "jobs": [("canonical-ci.yml", "tests"), ("canonical-ci.yml", "contracts"), ("canonical-ci.yml", "sealed"),
                 ("canonical-ci.yml", "cortex_seed"), ("canonical-ci.yml", "research_line")],
    },
    # Mission 2 was the body package ``greg`` (47 modules on #179's tree). On the joined tree (#196) it has 69, past
    # cognition.optimization's declared model ceiling of 64 variables (greg/cognition/solvers.py ``_model``), where
    # the compiler abstains (MODEL_INVALID) instead of answering: that case is kept as an executable control
    # (tests/integration/test_greg_whole_machine_trace.py). The standing runtime ``egregore`` is the natural package
    # within the ceiling.
    "m:ci-plan-runtime": {
        "package": ("egregore", "egregore"),
        "groups": [("greg-unit-body", ["tests/unit/test_greg_[!c]*.py"], ["requirements-dev"]),
                   ("kernel-unit", ["tests/unit/test_[!cg]*.py"], ["requirements-dev"]),
                   ("integration-other", ["tests/integration/test_[!g]*.py"], ["requirements-dev"])],
        "jobs": [("canonical-ci.yml", "tests"), ("canonical-ci.yml", "sealed"),
                 ("canonical-ci.yml", "cortex_seed"), ("ade1-standing-cognition.yml", "verify")],
    },
}


def mission_inputs(mission_id: str) -> dict:
    cls = MISSION_CLASSES[mission_id]
    graph = module_graph(*cls["package"])
    groups, jobs = test_groups(cls["groups"]), ci_jobs(cls["jobs"])
    return {"graph": graph, "critical_path": critical_path_data(graph), "groups": groups, "jobs": jobs,
            "costs": assignment_costs(groups, jobs)}


def compile_params(problem_id: str, geometry: dict, data: dict, assumptions: list[str]) -> dict:
    return {"problem_id": problem_id, "compile": {"geometry": geometry, "data": data, "assumptions": assumptions}}


def horizon(days: float = 2) -> str:
    from datetime import timedelta
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat().replace("+00:00", "Z")


def ci_plan_mission(mission_id: str, inputs: dict) -> dict:
    """One founder-signable mission body (contracts/greg-mission.schema.json); read-only; no spend."""
    tag = mission_id.split(":", 1)[1]
    cp = compile_params(f"{tag}:critical-path", {"geometry": "optimization", "subgeometry": "critical_path",
                                                 "consequence_class": "read_only", "reversibility": "reversible"},
                        inputs["critical_path"],
                        [f"durations are a proxy: ceil(source lines / {LINES_PER_STAGE}) stages per module",
                         "only top-level intra-package imports are dependencies"])
    asg = compile_params(f"{tag}:shard-assignment", {"geometry": "optimization", "subgeometry": "assignment",
                                                     "consequence_class": "read_only", "reversibility": "reversible"},
                         {"costs": inputs["costs"]},
                         [f"SYNTHETIC: {TEST_LINES_PER_CI_MINUTE} test lines per CI minute",
                          f"+{MISSING_REQUIREMENT_PENALTY} when a job lacks a requirement the group imports"])
    checks, strategies = [], []
    for check_id, target, params, what in (("critical-path", "cognition:critical-path", cp,
                                             "a certified minimum makespan of the module dependency schedule"),
                                            ("shard-assignment", "cognition:shard-assignment", asg,
                                             "a certified optimal one-to-one test-group to CI-job assignment")):
        step = {"capability": "cognition.solve", "target": target, "params": params}
        checks.append({"check_id": check_id, "description": what, "sensor": step,
                       "predicate": {"op": "equals", "field": "state", "value": "ANSWERED"}})
        strategies.append({"action_id": f"compile-{check_id}", **step, "advances": [check_id],
                           "rationale": f"compile and solve: {what}"})
    return {"mission_id": mission_id,
            "founder_expression": ("TEST FOUNDER KEY, not Alfonso: plan CI for this repository: the critical path "
                                   "of the module dependency graph and which CI job should run which test group"),
            "intended_effect": "a verified, consequence-inert CI plan (two certified answers); nothing is changed",
            "priority": 50, "closure": {"kind": "bounded"}, "success_checks": checks, "strategies": strategies,
            "light_cone": {"capabilities": ["cognition.solve"], "targets": ["cognition:*"],
                           "max_consequence_class": "read_only", "budget_usd": 0.0, "horizon": horizon()}}


def policy_question_mission(mission_id: str) -> dict:
    params = compile_params(f"{mission_id.split(':', 1)[1]}:drop-slow-group",
                            {"geometry": "normative", "consequence_class": "read_only"},
                            {"question": "Should the slowest CI test group be dropped to stay inside the 45-minute "
                                         "budget of canonical-ci.yml job 'tests'?",
                             "evidence": "trace mission m:ci-plan-cognition shard assignment"}, [])
    params["compile"]["human"] = {"competence_domain": "CI coverage policy for this repository",
                                  "roles": ["founder", "operator"]}
    step = {"capability": "cognition.solve", "target": "cognition:policy", "params": params}
    return {"mission_id": mission_id, "founder_expression": "TEST FOUNDER KEY: decide whether to drop a test group",
            "intended_effect": "a decision on CI coverage policy", "priority": 40, "closure": {"kind": "bounded"},
            "success_checks": [{"check_id": "decided", "description": "the policy question is answered",
                                "sensor": step, "predicate": {"op": "equals", "field": "state", "value": "ANSWERED"}}],
            "strategies": [{"action_id": "ask-compiler", **step, "advances": ["decided"],
                            "rationale": "route the question through the compiler"}],
            "light_cone": {"capabilities": ["cognition.solve"], "targets": ["cognition:*"],
                           "max_consequence_class": "read_only", "budget_usd": 0.0, "horizon": horizon()}}


# ------------------------------------------------------------------ the body as a separate OS process
def worker(home: str, clock_file: str, max_ticks: int, tick_sleep: float) -> int:
    """The canonical body loop (``Body.boot`` then ``Body.tick``) with an accelerated, persisted clock."""
    from greg.body import Body
    from tests.greg_fixtures import Clock
    path = Path(clock_file)
    start = datetime.fromisoformat(path.read_text().strip()) if path.exists() else datetime.now(timezone.utc)
    clock = Clock(max(start, datetime.now(timezone.utc)))
    with Body(home, clock=clock) as body:
        body.boot()
        for _ in range(max_ticks):
            body.tick()
            clock.advance(TICK_ADVANCE_SECONDS)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(clock.now.isoformat())
            tmp.replace(path)
            time.sleep(tick_sleep)
    return 0


def spawn(home: Path, clock_file: Path, max_ticks: int, tick_sleep: float, log: Path) -> subprocess.Popen:
    return subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--worker", str(home),
                             "--clock-file", str(clock_file), "--max-ticks", str(max_ticks),
                             "--tick-sleep", str(tick_sleep)], cwd=ROOT,
                            env={**os.environ, "PYTHONPATH": str(ROOT)}, stdout=open(log, "ab"),
                            stderr=subprocess.STDOUT)


def events(home: Path, kind: str) -> list[dict]:
    from greg.body import observe
    with observe(home, actor="spiffe://uniimente.internal/greg/trace-observer") as journal:
        return [{"event_id": e.event_id, **e.payload} for e in journal.replay(kind)]


def counts(home: Path, mission_id: str) -> dict:
    from greg.body import observe
    with observe(home, actor="spiffe://uniimente.internal/greg/trace-observer") as journal:
        def n(kind, **match):
            return sum(1 for e in journal.replay(kind) if all(e.payload.get(k) == v for k, v in match.items()))
        receipts = sum(1 for r in journal.ledger.records if r.record_type == "receipt")
        return {"body.booted": n("body.booted"), "body.recovered": n("body.recovered"),
                "deficit.opened": n("deficit.opened", mission_id=mission_id),
                "genesis.verified": n("genesis.verified"),
                "decision.requested": n("decision.requested", mission_id=mission_id),
                "mission.action.DONE": n("mission.action", mission_id=mission_id, status="DONE"),
                "mission.achieved": n("mission.achieved", mission_id=mission_id),
                "mission.appraised": n("mission.appraised", mission_id=mission_id),
                "cognition.settled": n("cognition.settled", mission_id=mission_id),
                "gate_receipts": receipts}


def wait_until(predicate, *, proc=None, timeout=120.0, poll=0.02, what="condition"):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            value = predicate()
        except (FileNotFoundError, json.JSONDecodeError, ValueError):
            value = None
        if value:
            return value
        if proc is not None and proc.poll() is not None:
            raise RuntimeError(f"worker exited ({proc.returncode}) before {what}")
        time.sleep(poll)
    raise TimeoutError(f"timed out waiting for {what}")


def drop_atomic(home: Path, envelope: dict, name: str) -> Path:
    """Write a signed envelope into the inbox atomically: a running body never reads a half-written file."""
    target = Path(home) / "inbox" / name
    tmp = target.with_suffix(".partial")
    tmp.write_text(json.dumps(envelope))
    tmp.replace(target)
    return target


def sigkill(proc: subprocess.Popen) -> None:
    os.kill(proc.pid, signal.SIGKILL)        # actual SIGKILL: no orderly close, no flush, no tick completion
    proc.wait(timeout=10)


# ------------------------------------------------------------------ ledger references
def ledger_index(home: Path) -> dict:
    from greg.body import observe
    with observe(home, actor="spiffe://uniimente.internal/greg/trace-observer") as journal:
        ledger = journal.ledger
        index = {}
        for r in ledger.records:
            if r.record_type == "event":
                index[r.payload.get("event_id")] = {"seq": r.seq, "hash": r.hash, "type": r.payload.get("type")}
        ok, why = ledger.verify_chain()
        return {"events": index, "head": ledger.head, "records": len(ledger.records), "chain_verified": ok,
                "chain_detail": why}


def ref(index: dict, event_id: str) -> dict:
    return {"event_id": event_id, **index["events"].get(event_id, {"seq": None, "hash": None})}


def compilations(home: Path, problem_id: str | None = None) -> list[dict]:
    """Competency-compilation receipts retained by the Gate (``receipt`` records), in ledger order."""
    from greg.body import observe
    out = []
    with observe(home, actor="spiffe://uniimente.internal/greg/trace-observer") as journal:
        for r in journal.ledger.records:
            if r.record_type != "receipt":
                continue
            output = (r.payload.get("result") or {}).get("output")
            if isinstance(output, dict) and str(output.get("schema", "")).startswith("greg-competency-compilation"):
                if problem_id is None or output.get("problem_id") == problem_id:
                    out.append({"seq": r.seq, "hash": r.hash, "action_id": r.payload.get("action_id"),
                                "witness_id": r.payload.get("witness_id"), "receipt": output})
    return out


def selection(c: dict) -> dict:
    r = c["receipt"]
    return {"ledger_seq": c["seq"], "ledger_hash": c["hash"], "state": r["state"],
            "method_selected": r["method_or_composition_selected"], "selection_level": r["selection_level"],
            "methods_considered": r["methods_considered"], "methods_rejected": r["methods_rejected"],
            "methods_demoted": r["methods_demoted"], "conditional_competence_basis": r["conditional_competence_basis"],
            "derived_geometry": r.get("derived_geometry"), "capability_deficit": r.get("capability_deficit"),
            "verification_method": r["verification_method"], "confidence_type": r["confidence_type"],
            "uncertainty": r["uncertainty"], "dissent": [d for d in r["dissent"] if d],
            "abstentions": r["abstentions"], "authority_state": r["authority_state"],
            "authority_created": r["authority_created"], "result": r["result"], "receipt_id": r["receipt_id"]}


# ------------------------------------------------------------------ governance (read-only audit of the Gate trail)
def gate_audit(home: Path) -> dict:
    from greg.body import observe
    with observe(home, actor="spiffe://uniimente.internal/greg/trace-observer") as journal:
        recs = journal.ledger.records
        granted = {r.payload.get("action_id") for r in recs
                   if r.record_type == "event" and r.payload.get("type") == "action.granted"}
        witnesses = {r.payload["witness_id"]: r.payload for r in recs if r.record_type == "witness"}
        receipts = [r.payload for r in recs if r.record_type == "receipt"]
        ungated = [p["action_id"] for p in receipts
                   if p["action_id"] not in granted or p.get("witness_id") not in witnesses]
        classes = sorted({w.get("consequence_class") or w.get("action_class") for w in witnesses.values()})
        targets = sorted({w.get("target") for w in witnesses.values()})
        policies = sorted({w.get("policy_version") for w in witnesses.values()})
        cones = sorted({canonical(r.payload.get("cone", {}).get("max_consequence_class")) for r in recs
                        if r.record_type == "event" and r.payload.get("type") == "greg.authority.grant_issued"})
        return {"gate_receipts": len(receipts), "receipts_without_grant_and_witness": ungated,
                "witnessed_action_classes": classes, "witnessed_targets": targets,
                "policy_versions": policies, "grant_ceilings": [json.loads(c) for c in cones],
                "external_targets": [t for t in targets if t and not t.startswith(("cognition:", "workspace:"))]}


# ------------------------------------------------------------------ organs through canonical contracts
def organ_coordination() -> dict:
    """DALEOBANKS -> WealthMachine Bridge A edge, on the registered contracts and Kernel adapters only.

    The organ code is not in this repository: no organ process runs. The wire packet and assessment are labelled
    SYNTHETIC fixtures. The HMAC key is a per-run test key held in this process only."""
    from adapters import bridge_transport as bt
    from adapters import daleobanks_opportunity as pkt
    from adapters import wealthmachine_assessment as asm
    from adapters.contract_validation import validate_contract
    from linker.linker import InstitutionalLinker
    from linker.manifest import load_all
    daleobanks = "spiffe://uniimente.internal/organ/daleobanks"
    wmi = "spiffe://uniimente.internal/organ/wealthmachine"
    kernel = "spiffe://uniimente.internal/organ/constitutional-controller"
    report = InstitutionalLinker(load_all()).link()
    edges = sorted({(e.producer, e.contract, e.consumer) for e in report.edges})
    wire = {"id": "00000000-0000-4000-8000-0000000c1001", "schema_version": "1.1",
            "created_at": "2026-10-21T00:00:00Z", "source": "daleobanks:fixture",
            "observed_pain": "SYNTHETIC FIXTURE: maintainers report CI runs exceeding their job time budgets",
            "audience": "SYNTHETIC: repository maintainers", "buyer_type": "",
            "smallest_validation_action": "SYNTHETIC: measure job durations for one week",
            "evidence": [], "risk_flags": ["fixture: no real audience signal"]}
    validate_contract(wire, "wire-opportunity-packet")
    secret_before = os.environ.get(bt.SIGNING_KEY_ENV)
    os.environ[bt.SIGNING_KEY_ENV] = "trace-test-bridge-key-" + hashlib.sha256(os.urandom(16)).hexdigest()[:16]
    try:
        body = json.dumps(wire, sort_keys=True).encode()
        headers = bt.build_headers(body, identity="daleobanks", schema_version="1.1", idempotency_key=wire["id"])
        cache = bt.NonceCache()
        meta = bt.verify_headers(headers, body, nonce_cache=cache)
        refusals = {}
        for name, mutate in (("replayed_nonce", lambda h, b: (h, b)),
                             ("tampered_body", lambda h, b: (bt.build_headers(b, identity="daleobanks",
                                                                              schema_version="1.1"), b + b" ")),
                             ("forged_identity", lambda h, b: ({**bt.build_headers(b, identity="daleobanks",
                                                                                   schema_version="1.1"),
                                                                bt.H_IDENTITY: "attacker"}, b))):
            h, b = mutate(headers, body)
            try:
                bt.verify_headers(h, b, nonce_cache=cache if name == "replayed_nonce" else bt.NonceCache())
                refusals[name] = "ACCEPTED (defect)"
            except bt.BridgeSecurityError as exc:
                refusals[name] = f"refused: {exc}"
    finally:
        if secret_before is None:
            os.environ.pop(bt.SIGNING_KEY_ENV, None)
        else:
            os.environ[bt.SIGNING_KEY_ENV] = secret_before
    adapted = pkt.adapt(wire, transport_identity=meta["identity"])
    try:
        pkt.resolve(adapted, {f: "an anonymous guess" for f in adapted.unresolved}, resolved_by="anonymous")
        anonymous = "ACCEPTED (defect)"
    except pkt.AdapterError as exc:
        anonymous = f"refused: {exc}"
    wire_assessment = {"id": "00000000-0000-4000-8000-0000000c1002", "schema_version": "1.1",
                       "created_at": "2026-10-21T00:00:01Z", "opportunity_packet_id": wire["id"],
                       "go_no_go": "needs_more_evidence", "requires_human_approval": True,
                       "reasons": ["SYNTHETIC FIXTURE: no buyer evidenced"],
                       "cases": [{"case": "bull", "stance": "for", "severity": "low",
                                  "argument": "SYNTHETIC: measuring durations is cheap."},
                                 {"case": "bear", "stance": "against", "severity": "medium",
                                  "argument": "SYNTHETIC: no buyer or budget owner is evidenced."},
                                 {"case": "do_nothing", "stance": "against", "severity": "low",
                                  "argument": "SYNTHETIC: keep the current CI layout."}]}
    validate_contract(wire_assessment, "wire-venture-assessment")
    assessed = asm.adapt(wire_assessment, transport_identity="wealthmachine")
    validate_contract(assessed, "venture-assessment")
    return {
        "reality": "CONTRACT+ADAPTER ONLY: DALEOBANKS and WealthMachine code is not in this repository; no organ "
                   "process ran; wire payloads are SYNTHETIC fixtures; transport key is a per-run test key",
        "linker_edges": [list(e) for e in edges if daleobanks in e or wmi in e],
        "bridge_a_edge_present": (daleobanks, "wire-opportunity-packet", wmi) in edges,
        "wire_packet": {"schema": "contracts/wire-opportunity-packet.schema.json", "validated": True,
                        "digest": sha(wire)},
        "transport": {"verified_identity": meta["identity"], "signed": meta.get("signed"),
                      "protocol": bt.PROTOCOL_VERSION, "hostile_controls": refusals},
        "packet_adapter": {"module": "adapters/daleobanks_opportunity.py", "created_by": adapted.partial["created_by"],
                           "unresolved": adapted.unresolved, "resolved": adapted.resolved,
                           "information_lost": list(adapted.information_lost),
                           "information_added": list(adapted.information_added),
                           "assumptions": list(adapted.assumptions), "anonymous_resolution": anonymous},
        "assessment_adapter": {"module": "adapters/wealthmachine_assessment.py",
                               "canonical_schema": "contracts/venture-assessment.schema.json", "validated": True,
                               "information_lost": list(asm.INFORMATION_LOST),
                               "field_mapping": dict(asm.FIELD_MAPPING),
                               "information_added": (list(asm.INFORMATION_ADDED) if hasattr(asm, "INFORMATION_ADDED")
                                                     else "NOT DECLARED: the module has no INFORMATION_ADDED tuple; "
                                                          "its additions (assessed_by from transport, constant "
                                                          "requires_human_approval/execution_authority) appear only "
                                                          "in FIELD_MAPPING (gap)"),
                               "requires_human_approval": assessed.get("requires_human_approval"),
                               "execution_authority": assessed.get("execution_authority"),
                               "digest": sha(assessed)},
        "kernel_consumer_edge_present": (daleobanks, "wire-opportunity-packet", kernel) in edges,
    }


# ------------------------------------------------------------------ the run
def run(out_dir: Path | None = None, state_dir: Path | None = None, *, keep_state: bool = False) -> dict:
    from greg.body import Body
    from greg.founder import generate_founder_key, load_founder_key
    from greg.missions import MISSION_SCHEMA
    from jsonschema import Draft202012Validator
    from tests.greg_fixtures import Clock, drop, make_body, signed

    started = time.monotonic()
    tmp = Path(state_dir or tempfile.mkdtemp(prefix="greg-whole-machine-trace-"))
    tmp.mkdir(parents=True, exist_ok=True)
    log = tmp / "worker.log"
    clock_file = tmp / "clock.txt"
    notes = {"state_dir": "temporary (deleted unless --keep-state)", "clock": f"accelerated: +{TICK_ADVANCE_SECONDS}s "
             "per tick, persisted across worker processes; otherwise the canonical Body.boot/Body.tick loop"}
    home, key, body_id, _ = make_body(tmp)               # canonical fixture: real Ed25519 test key, enrolled
    M1, M2, MQ = "m:ci-plan-cognition", "m:ci-plan-runtime", "m:ci-policy-question"
    in1 = mission_inputs(M1)
    spec1 = ci_plan_mission(M1, in1)
    schema_errors = [e.message for e in Draft202012Validator(MISSION_SCHEMA).iter_errors(spec1)]
    drop(home, signed(key, body_id, "MISSION", spec1))

    # -- worker 1: boots, takes the mission, solves A, opens the deficit for B, runs Genesis, asks; SIGKILL #1 while
    #    the mission is blocked on the founder's attach
    clock_file.write_text(datetime.now(timezone.utc).isoformat())
    w1 = spawn(home, clock_file, 200, 0.05, log)
    try:
        wait_until(lambda: any(r["kind"] == "CAPABILITY_ATTACH" for r in events(home, "decision.requested"))
                   and events(home, "mission.blocked"), proc=w1, what="the founder attach ask")
        sigkill(w1)
    finally:
        if w1.poll() is None:
            w1.kill()
    at_kill1 = counts(home, M1)
    blocked = events(home, "mission.blocked")[-1]

    # -- worker 2: restart from retained history; a forged attach is refused; the founder's signed attach resumes the
    #    ORIGINAL mission; SIGKILL #2 in the window between closure and its separate-process appraisal
    w2 = spawn(home, clock_file, 400, 0.05, log)
    kill2 = {"attempted": True}
    try:
        wait_until(lambda: len(events(home, "body.booted")) >= 2, proc=w2, what="restart")
        boots_seen = len(events(home, "body.booted"))
        tick_mark = clock_file.read_text()
        wait_until(lambda: clock_file.read_text() != tick_mark, proc=w2, what="a tick after restart")
        tick_mark = clock_file.read_text()
        wait_until(lambda: clock_file.read_text() != tick_mark, proc=w2, what="a second tick after restart")
        after_restart = counts(home, M1)
        intruder = tmp / "intruder.pem"
        generate_founder_key(intruder, None)
        forged = signed(load_founder_key(intruder, None), body_id, "CAPABILITY_ATTACH",
                        {"capability_id": SCIPY_ASSIGNMENT})
        drop_atomic(home, forged, "0-forged-attach.json")
        wait_until(lambda: events(home, "command.rejected"), proc=w2, what="the forged attach refusal")
        attach = signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": SCIPY_ASSIGNMENT})
        drop_atomic(home, attach, "1-founder-attach.json")
        wait_until(lambda: events(home, "mission.achieved"), proc=w2, poll=0.005, what="closure")
        if not [e for e in events(home, "mission.appraised") if e["mission_id"] == M1]:
            sigkill(w2)
            kill2.update(point="after mission.achieved, before mission.appraised and cognition.settled",
                         hit=True, at_kill=counts(home, M1))
        else:
            kill2.update(point="window missed: appraisal already recorded when closure was observed", hit=False,
                         at_kill=counts(home, M1))
            sigkill(w2)
    finally:
        if w2.poll() is None:
            w2.kill()

    # -- worker 3: restart again and let the body finish (appraise, settle) from retained history
    w3 = spawn(home, clock_file, 400, 0.05, log)
    try:
        wait_until(lambda: len([e for e in events(home, "cognition.settled") if e["mission_id"] == M1]) >= 2
                   and [e for e in events(home, "mission.appraised") if e["mission_id"] == M1], proc=w3,
                   what="appraisal and settlement after the second restart")
        tick_mark = clock_file.read_text()
        for _ in range(3):                                 # extra ticks: nothing may settle or act twice
            wait_until(lambda: clock_file.read_text() != tick_mark, proc=w3, what="extra ticks")
            tick_mark = clock_file.read_text()
        sigkill(w3)
    finally:
        if w3.poll() is None:
            w3.kill()
    final1 = counts(home, M1)

    # -- independent verification of both answers (no shared code with the engines or GREG's certificates)
    tag1 = M1.split(":", 1)[1]
    cp_rows = compilations(home, f"{tag1}:critical-path")
    as_rows = compilations(home, f"{tag1}:shard-assignment")
    cp_answer = next(c for c in reversed(cp_rows) if c["receipt"]["state"] == "ANSWERED")
    as_first = as_rows[0]
    as_answer = next(c for c in reversed(as_rows) if c["receipt"]["state"] == "ANSWERED")
    indep_cp = independent_longest_chain(in1["graph"])
    indep_as = independent_assignment(in1["costs"])
    cp_value = cp_answer["receipt"]["result"]["objective_value"]
    as_value = as_answer["receipt"]["result"]["total"]

    # -- mission 2, same class, new natural data, on the same body (retained evidence) and on a fresh control body
    in2 = mission_inputs(M2)
    spec2 = ci_plan_mission(M2, in2)
    drop(home, signed(key, body_id, "MISSION", spec2))
    start = datetime.fromisoformat(clock_file.read_text().strip())
    clock = Clock(max(start, datetime.now(timezone.utc)))
    with Body(home, clock=clock) as body:
        body.boot()
        states2 = []
        for _ in range(4):
            states2.append(body.tick()["missions"])
            clock.advance(TICK_ADVANCE_SECONDS)
    control_dir = tmp / "control"
    control_dir.mkdir(exist_ok=True)
    c_home, c_key, c_body, _ = make_body(control_dir)
    drop(c_home, signed(c_key, c_body, "MISSION", spec2))
    c_clock = Clock()
    with Body(c_home, clock=c_clock) as body:
        body.boot()
        for _ in range(3):
            body.tick()
            c_clock.advance(TICK_ADVANCE_SECONDS)
    tag2 = M2.split(":", 1)[1]
    m2_as = compilations(home, f"{tag2}:shard-assignment")
    m2_cp = compilations(home, f"{tag2}:critical-path")
    control_as = compilations(c_home, f"{tag2}:shard-assignment")
    final2 = counts(home, M2)
    control_counts = counts(c_home, M2)
    indep2_cp = independent_longest_chain(in2["graph"])
    indep2_as = independent_assignment(in2["costs"])

    # -- abstention: a normative question is never answered by cognition; the mission stays open
    drop(home, signed(key, body_id, "MISSION", policy_question_mission(MQ)))
    with Body(home, clock=clock) as body:
        body.boot()
        q_states = []
        for _ in range(3):
            q_states.append([m for m in body.tick()["missions"] if m.get("mission_id") == MQ])
            clock.advance(TICK_ADVANCE_SECONDS)
    q_rows = compilations(home, f"{MQ.split(':', 1)[1]}:drop-slow-group")
    q_counts = counts(home, MQ)
    judgment_asks = [e for e in events(home, "decision.requested") if e.get("kind") not in ("CAPABILITY_ATTACH",)]

    organs = organ_coordination()
    gate = gate_audit(home)
    index = ledger_index(home)

    # -- assemble the trace ---------------------------------------------------------------------------------------
    deficits = [e for e in events(home, "deficit.opened") if e["mission_id"] == M1]
    genesis_routes = [e for e in events(home, "genesis.route")]
    verified = events(home, "genesis.verified")
    attach_states = [e for e in events(home, "capability.state") if e["capability_id"] == SCIPY_ASSIGNMENT]
    asks = [e for e in events(home, "decision.requested") if e["kind"] == "CAPABILITY_ATTACH"]
    rejected = events(home, "command.rejected")
    unblocked = [e for e in events(home, "mission.unblocked") if e["mission_id"] == M1]
    settled1 = [e for e in events(home, "cognition.settled") if e["mission_id"] == M1]
    settled2 = [e for e in events(home, "cognition.settled") if e["mission_id"] == M2]
    appraised1 = [e for e in events(home, "mission.appraised") if e["mission_id"] == M1]
    appraised2 = [e for e in events(home, "mission.appraised") if e["mission_id"] == M2]
    registered = [e for e in events(home, "mission.registered") if e.get("mission_id") == M1]
    achieved1 = [e for e in events(home, "mission.achieved") if e["mission_id"] == M1]
    boots = events(home, "body.booted")
    recovered = events(home, "body.recovered")
    from greg import routing
    from greg.cognition.settlement import competence
    from greg.body import observe
    with observe(home, actor="spiffe://uniimente.internal/greg/trace-observer") as journal:
        knowledge = routing.routing_knowledge(journal)
        comp = {f"{m}@{v}": {k: rec[k] for k in ("count", "correct") if k in rec}
                for (m, v, _g), rec in competence(journal).items()}

    def ok(cond) -> str:
        return "DEMONSTRATED" if cond else "NOT DEMONSTRATED"

    steps = []
    steps.append({"demonstration": 1, "name": "goal persistence",
                  "claim": "a durable mission created from a founder-signed MISSION command in a temp state dir "
                           "survives two SIGKILLs and closes in a third process",
                  "status": ok(registered and achieved1 and len(boots) >= 3 and not schema_errors),
                  "tier": "INTEGRATED (local process; test founder key)",
                  "evidence": {"mission_registered": [ref(index, e["event_id"]) for e in registered],
                               "schema": "contracts/greg-mission.schema.json", "schema_errors": schema_errors,
                               "boots": [{"boot_number": b["boot_number"], "pid": b["pid"], **ref(index, b["event_id"])}
                                         for b in boots],
                               "recovered": [ref(index, e["event_id"]) for e in recovered],
                               "achieved": [ref(index, e["event_id"]) for e in achieved1]}})
    cp_sel = selection(cp_answer)
    frozen = json.loads((ROOT / "docs" / "evidence" / "greg-mind-evidence-index.json").read_text())
    frozen_rows = {}
    for row in cp_sel["methods_rejected"]:
        name = row["method"].removeprefix("cognition.")
        entry = frozen.get("genomes", {}).get(name)
        if entry:
            frozen_rows[row["method"]] = {k: entry.get(k) for k in ("status", "version", "evidence", "competitor",
                                                                    "median_seconds")}
    steps.append({"demonstration": 2, "name": "method selection by frozen evidence",
                  "claim": "the Competency Compiler characterised the critical-path sub-problem (real import graph "
                           f"of {in1['graph']['package']}: {len(in1['graph']['modules'])} modules, "
                           f"{len(in1['graph']['edges'])} edges) and selected a method, recording rejected "
                           "alternatives and why",
                  "status": ok(cp_sel["state"] == "ANSWERED" and cp_sel["methods_rejected"]),
                  "tier": "INTEGRATED",
                  "evidence": {"compile_receipt": cp_sel,
                               "frozen_evidence_index": "docs/evidence/greg-mind-evidence-index.json",
                               "frozen_entries_of_rejected_methods": frozen_rows,
                               "independent_check": indep_cp}})
    first_sel = selection(as_first)
    as_sel = selection(as_answer)
    ev_seq = lambda e: index["events"].get(e["event_id"], {}).get("seq")
    order = {"deficit_opened": ev_seq(deficits[0]) if deficits else None,
             "genesis_verified": ev_seq(verified[0]) if verified else None,
             "founder_ask": min((ev_seq(e) for e in asks if e["mission_id"] == M1), default=None),
             "founder_attach": ev_seq(attach_states[0]) if attach_states else None,
             "mission_resumed": ev_seq(unblocked[0]) if unblocked else None,
             "answered_compile_receipt": as_answer["seq"],
             "mission_achieved": ev_seq(achieved1[0]) if achieved1 else None}
    ordered = None not in order.values() and list(order.values()) == sorted(order.values())
    steps.append({"demonstration": 3, "name": "missing-capability resolution",
                  "claim": "the assignment sub-problem had no method; a verified CapabilityDeficit opened the one "
                           "Genesis loop; an installed open-source engine (SciPy) was qualified on GREG's frozen "
                           "oracle with no network; the founder attach came through the signed inbox; the ORIGINAL "
                           "mission resumed and its answer was certified and independently re-checked",
                  "status": ok(first_sel["state"] == "CAPABILITY_DEFICIT" and len(deficits) == 1 and verified
                               and attach_states and unblocked and as_value == indep_as["total"] and ordered),
                  "tier": "INTEGRATED (installed package; nothing downloaded or installed)",
                  "evidence": {"first_compile": {k: first_sel[k] for k in ("ledger_seq", "state", "capability_deficit")},
                               "deficit_opened": [ref(index, e["event_id"]) for e in deficits],
                               "genesis_routes": [{"route": e["route"], "result": e["result"],
                                                   "capability_id": e.get("capability_id"),
                                                   **ref(index, e["event_id"])} for e in genesis_routes],
                               "genesis_verified": [{"capability_id": e["capability_id"], "passed": e["passed"],
                                                     "cases": e["report"]["cases"],
                                                     "failures": e["report"]["failures"],
                                                     "isolation": e["report"]["isolation"],
                                                     "mechanism": {k: e["mechanism"].get(k) for k in
                                                                   ("distribution", "version", "license", "mode",
                                                                    "package_digest", "acquisition")},
                                                     **ref(index, e["event_id"])} for e in verified],
                               "founder_attach_ask": [ref(index, e["event_id"]) for e in asks if e["mission_id"] == M1],
                               "blocked": {"blocker": blocked["blocker"], **ref(index, blocked["event_id"])},
                               "attach": [{"state": e["state"], "by": e["by"], **ref(index, e["event_id"])}
                                          for e in attach_states],
                               "resumed": [ref(index, e["event_id"]) for e in unblocked],
                               "answer": as_sel, "independent_check": indep_as,
                               "ledger_order": order, "ledger_order_strictly_increasing": ordered,
                               "building_the_tool_did_not_close_the_mission":
                                   "genesis.verified < founder ask < founder attach < resume < answered compile of "
                                   "the ORIGINAL check < mission.achieved, by ledger sequence"}})
    steps.append({"demonstration": 4, "name": "governed execution",
                  "claim": "every invocation crossed the Kernel Consequence Gate (proposal, identity evaluation, "
                           "grant, witness with policy version, dispatch, receipt); ceilings stayed read_only; no "
                           "target outside cognition:*; a forged founder command was refused",
                  "status": ok(not gate["receipts_without_grant_and_witness"] and not gate["external_targets"]
                               and rejected),
                  "tier": "INTEGRATED (no external effect exists to govern; sandbox/local only)",
                  "evidence": {**gate, "forged_attach_refused": [{"reason": e["reason"], **ref(index, e["event_id"])}
                                                                 for e in rejected]}})
    steps.append({"demonstration": 5, "name": "interruption recovery",
                  "claim": "SIGKILL #1 while the mission waited on the founder; SIGKILL #2 "
                           + ("between closure and appraisal" if kill2.get("hit") else "(window missed; see kill_2)")
                           + "; after restarts exactly one qualification, one ask, one settlement per check, no "
                             "duplicate action",
                  "status": ok(final1["genesis.verified"] == 1 and final1["decision.requested"] == 1
                               and final1["cognition.settled"] == 2 and final1["mission.appraised"] == 1
                               and final1["mission.action.DONE"] == at_kill1["mission.action.DONE"]
                               and after_restart["genesis.verified"] == at_kill1["genesis.verified"]),
                  "tier": "INTEGRATED (real SIGKILL of the body process on Linux; not the founder's device)",
                  "evidence": {"kill_1": {"point": "mission blocked on the founder attach ask", "at_kill": at_kill1,
                                          "after_restart_before_attach": after_restart},
                               "kill_2": kill2, "final": final1, "worker_processes": 3,
                               "settled": [ref(index, e["event_id"]) for e in settled1]}})
    steps.append({"demonstration": 6, "name": "appraisal and settlement",
                  "claim": "a separate-process appraiser re-derived the checks from receipt bytes and re-observed "
                           "the world (VERIFIED); each answer settled once against its method and version; "
                           "competence and routing knowledge are projected from the journal",
                  "status": ok(appraised1 and appraised1[-1]["verdict"] == "VERIFIED" and len(settled1) == 2),
                  "tier": "INTEGRATED (appraiser shares reviewed Kernel code; not an independent implementation)",
                  "evidence": {"appraisal": {"verdict": appraised1[-1]["verdict"], "checks": appraised1[-1]["checks"],
                                             "limits": appraised1[-1].get("limits"),
                                             **ref(index, appraised1[-1]["event_id"])},
                               "settlements": [{"check_id": e["check_id"], "method": e["method"],
                                                "method_version": e["method_version"], "correct": e["correct"],
                                                **ref(index, e["event_id"])} for e in settled1],
                               "competence_after": comp,
                               "routing_knowledge": [r for r in knowledge if r["capability"] == "cognition.solve"]}})
    m2_first = selection(m2_as[0]) if m2_as else None
    control_first = selection(control_as[0]) if control_as else None
    changed = bool(m2_first and control_first and m2_first["state"] == "ANSWERED"
                   and control_first["state"] == "CAPABILITY_DEFICIT"
                   and final2["deficit.opened"] == 0 and final2["decision.requested"] == 0)
    steps.append({"demonstration": 7, "name": "a later decision changed by retained evidence",
                  "claim": "a second CI-plan mission (new natural data) was routed straight to the formed SciPy "
                           "mechanism with no deficit, Genesis search or founder ask; the identical mission on a "
                           "fresh control body opened a deficit. Cause: mission 1's retained qualification and the "
                           "founder's attach. Mission 1's settled outcomes enter mission 2's compiler competence "
                           "basis (critical-path receipt) but did not themselves change a choice",
                  "status": ok(changed),
                  "tier": "INTEGRATED",
                  "evidence": {"before_mission_1_first_compile": {k: first_sel[k] for k in
                                                                  ("ledger_seq", "state", "method_selected",
                                                                   "capability_deficit")},
                               "after_mission_2_first_compile": m2_first,
                               "control_fresh_body_first_compile": ({k: control_first[k] for k in
                                                                     ("state", "method_selected",
                                                                      "capability_deficit")}
                                                                    if control_first else None),
                               "control_counts": control_counts, "mission_2_counts": final2,
                               "mission_2_critical_path": selection(m2_cp[-1]) if m2_cp else None,
                               "mission_2_independent": {"critical_path": indep2_cp, "assignment": indep2_as},
                               "mission_2_appraisal": [{"verdict": e["verdict"], **ref(index, e["event_id"])}
                                                       for e in appraised2],
                               "mission_2_settlements": [{"method": e["method"], "correct": e["correct"]}
                                                         for e in settled2],
                               "causes": {"genesis_verified": [ref(index, e["event_id"]) for e in verified],
                                          "founder_attach": [ref(index, e["event_id"]) for e in attach_states],
                                          "mission_1_settlement": [ref(index, e["event_id"]) for e in settled1
                                                                   if e["method"] == SCIPY_ASSIGNMENT]},
                               "competence_basis_in_mission_2": (selection(m2_cp[-1])["conditional_competence_basis"]
                                                                 if m2_cp else None),
                               "limit": "settled outcomes alone did not change the choice here: only one method fits "
                                        "each geometry, settled competence only orders fits within one admission "
                                        "status, and the compiler demotes on settled outcomes only after >= 10 "
                                        "(greg/cognition/compiler.py SETTLED_MIN_N); the formed-mechanism route's "
                                        "receipt reports no conditional_competence_basis"}})
    steps.append({"demonstration": 8, "name": "organ coordination through canonical contracts",
                  "claim": "a DALEOBANKS wire OpportunityPacket was validated, HMAC-verified on the canonical "
                           "transport, adapted with declared information lost/added and unresolved fields; a "
                           "WealthMachine wire assessment was adapted to the canonical VentureAssessment",
                  "status": ok(organs["bridge_a_edge_present"] and organs["packet_adapter"]["unresolved"]
                               and all(v.startswith("refused") for v in organs["transport"]["hostile_controls"].values())
                               and organs["packet_adapter"]["anonymous_resolution"].startswith("refused")),
                  "tier": "IMPLEMENTED (contract + adapter only; SYNTHETIC fixtures; no organ process)",
                  "evidence": organs})
    dissent = {"critical_path_compiler_dissent": cp_sel["dissent"], "assignment_compiler_dissent": as_sel["dissent"],
               "uncertainty": {"critical_path": cp_sel["uncertainty"], "assignment": as_sel["uncertainty"]},
               "appraiser_limits": appraised1[-1].get("limits") if appraised1 else None,
               "abstention": {"mission_id": MQ, "compile": selection(q_rows[-1]) if q_rows else None,
                              "counts": q_counts, "judgment_asks": [ref(index, e["event_id"]) for e in judgment_asks]},
               "independent_rescoring": {"critical_path_agrees": cp_value == indep_cp.get("makespan"),
                                         "assignment_agrees": as_value == indep_as["total"]}}
    steps.append({"demonstration": 9, "name": "dissent and uncertainty preserved",
                  "claim": "the compiler's strongest counterargument, the conditional (WORLD-unverified) "
                           "uncertainty, the appraiser's stated limits and a HUMAN_JUDGMENT_REQUIRED abstention on a "
                           "normative question are kept in the trace; the abstaining mission never closed",
                  "status": ok(cp_sel["dissent"] and q_rows and q_rows[-1]["receipt"]["state"] ==
                               "HUMAN_JUDGMENT_REQUIRED" and q_counts["mission.achieved"] == 0),
                  "tier": "INTEGRATED",
                  "evidence": dissent})

    prev = None
    for n, s in enumerate(steps):
        s["prev_step_hash"] = prev
        s["step_hash"] = prev = sha({k: v for k, v in s.items() if k != "step_hash"})
    facts = {"mission_1": {"critical_path": cp_value, "assignment_total": as_value,
                           "assignment_pairs": as_answer["receipt"]["result"]["pairs"],
                           "methods": [cp_sel["method_selected"], as_sel["method_selected"]]},
             "mission_2": {"critical_path": (m2_cp[-1]["receipt"]["result"] or {}).get("objective_value") if m2_cp
                           else None, "assignment_first_state": m2_first and m2_first["state"],
                           "control_first_state": control_first and control_first["state"]},
             "statuses": [s["status"] for s in steps], "inputs": {"m1": sha(in1), "m2": sha(in2)}}
    try:
        commit = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True,
                                timeout=10).stdout.strip() or None
        dirty = bool(subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain"], capture_output=True,
                                    text=True, timeout=10).stdout.strip())
    except OSError:
        commit, dirty = None, None
    versions = {}
    for dist in ("scipy", "networkx", "ortools", "z3-solver", "jsonschema", "cryptography"):
        try:
            versions[dist] = importlib.metadata.version(dist)
        except importlib.metadata.PackageNotFoundError:
            versions[dist] = None
    trace = {"schema": SCHEMA, "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
             "source_commit": commit, "source_dirty": dirty,
             "environment": {"python": platform.python_version(), "platform": platform.platform(), **versions},
             "labels": {"founder_key": "per-run test Ed25519 key, NOT Alfonso; no founder use is claimed",
                        "effects": "none external; temporary state directory only; read-only consequence ceiling",
                        "VEPMC": 0, "revenue": None, "external_validation": None, **notes},
             "natural_data": {"m1": {"package": in1["graph"]["package"], "modules": len(in1["graph"]["modules"]),
                                     "edges": len(in1["graph"]["edges"]),
                                     "source_digest": in1["graph"]["source_digest"],
                                     "groups": in1["groups"], "jobs": in1["jobs"], "costs": in1["costs"]},
                              "m2": {"package": in2["graph"]["package"], "modules": len(in2["graph"]["modules"]),
                                     "edges": len(in2["graph"]["edges"]),
                                     "source_digest": in2["graph"]["source_digest"],
                                     "groups": in2["groups"], "jobs": in2["jobs"], "costs": in2["costs"]},
                              "synthetic": [f"duration proxy ceil(lines/{LINES_PER_STAGE})",
                                            f"{TEST_LINES_PER_CI_MINUTE} test lines per CI minute",
                                            f"+{MISSING_REQUIREMENT_PENALTY} missing-requirement penalty",
                                            "organ wire fixtures"]},
             "answers": {"m1_critical_path": {"makespan": cp_value, "independent": indep_cp},
                         "m1_assignment": {"total": as_value, "pairs": as_answer["receipt"]["result"]["pairs"],
                                           "rows": [g["group"] for g in in1["groups"]],
                                           "columns": [j["job"] for j in in1["jobs"]], "independent": indep_as}},
             "ledger": {"head": index["head"], "records": index["records"], "chain_verified": index["chain_verified"]},
             "steps": steps, "trace_head": prev, "reproducible_facts": facts,
             "reproducible_digest": sha(facts), "seconds": round(time.monotonic() - started, 2)}
    if out_dir is not None:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "trace.json").write_text(json.dumps(trace, indent=1, sort_keys=False) + "\n")
    if not keep_state and state_dir is None:
        shutil.rmtree(tmp, ignore_errors=True)
    return trace


def verify_trace(trace: dict) -> tuple[bool, str]:
    """Recompute the step hash chain and the reproducible digest of a written trace."""
    prev = None
    for s in trace["steps"]:
        if s["prev_step_hash"] != prev:
            return False, f"step {s['demonstration']}: broken link"
        if sha({k: v for k, v in s.items() if k != "step_hash"}) != s["step_hash"]:
            return False, f"step {s['demonstration']}: content does not match its hash"
        prev = s["step_hash"]
    if prev != trace["trace_head"]:
        return False, "trace head does not match the last step"
    if sha(trace["reproducible_facts"]) != trace["reproducible_digest"]:
        return False, "reproducible digest does not match its facts"
    return True, "chain intact"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, help="directory for trace.json")
    parser.add_argument("--state-dir", type=Path, help="temporary state directory (default: a new temp dir)")
    parser.add_argument("--keep-state", action="store_true")
    parser.add_argument("--verify", type=Path, help="verify an existing trace.json and exit")
    parser.add_argument("--worker", help=argparse.SUPPRESS)
    parser.add_argument("--clock-file", help=argparse.SUPPRESS)
    parser.add_argument("--max-ticks", type=int, default=100, help=argparse.SUPPRESS)
    parser.add_argument("--tick-sleep", type=float, default=0.05, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.verify:
        ok, why = verify_trace(json.loads(args.verify.read_text()))
        print(why)
        return 0 if ok else 1
    if args.worker:
        return worker(args.worker, args.clock_file, args.max_ticks, args.tick_sleep)
    trace = run(args.out, args.state_dir, keep_state=args.keep_state)
    for s in trace["steps"]:
        print(f"{s['demonstration']}. {s['name']}: {s['status']} [{s['tier']}]")
    print("trace head", trace["trace_head"], "ledger chain verified", trace["ledger"]["chain_verified"])
    return 0 if all(s["status"] == "DEMONSTRATED" for s in trace["steps"]) else 1


if __name__ == "__main__":
    sys.exit(main())
