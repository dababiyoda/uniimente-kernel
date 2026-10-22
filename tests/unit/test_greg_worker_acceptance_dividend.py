"""R1-A: worker-independent acceptance (#190). A worker cannot pass its own acceptance by gaming its evaluator.

Three refusals on top of #173's frozen evaluator, each read from GREG's own copies: the worker's changed tests must
fail on the recorded base (``discrimination_findings``); a delivered artifact the order binds must equal the bound
value (``bound_artifact_findings``); a named reviewed verifier re-derives the artifact (``rederivation_findings``).
The workers here are SCRIPTED TEST DOUBLES. The hostile classes on the full canonical path, in both confinement
regimes, are ``tests/integration/test_greg_acceptance_dividend.py``.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest

from greg import artifact_verifiers, templates, workers
from greg.body import Body, Layout
from tests.greg_fixtures import Clock, drop, make_body, signed
from tests.integration.test_greg_mind_constructs_capability import STAFFING
from tests.unit.test_greg_workers import ScriptedWorker, acceptance_envelope, make_repo  # noqa: F401 (autouse fixture)

CERTIFIED = {"assignment": [["Ana", "Dock2", 2], ["Ben", "Dock1", 4], ["Cy", "Line", 2]], "staffed": 8,
             "certificate": {"kind": "deficiency set"}}
CONTEXT = "CERTIFIED_PLAN_JSON:\n" + json.dumps(CERTIFIED)
BOUND = {"bound_artifacts": [{"path": "plan/plan.json", "label": "CERTIFIED_PLAN_JSON",
                              "keys": ["assignment", "staffed"]}]}
VERIFIED = {"verifiers": [{"name": "assignment.staffing", "artifact": "plan/plan.json", "problem": "problem.json"}]}
LIE = {"assignment": [["Ana", "Dock2", 2], ["Ben", "Dock1", 4], ["Cy", "Line", 3]], "staffed": 9}


def delivered(artifact=None, problem=STAFFING) -> dict:
    return {"tests": [], "test_side": {},
            "artifacts": {"plan/plan.json": None if artifact is None else json.dumps(artifact).encode()},
            "problems": {"problem.json": None if problem is None else json.dumps(problem).encode()}}


# -- bound artifact -------------------------------------------------------------------------------

def test_a_delivered_artifact_must_equal_the_value_the_mission_bound_on_its_keys():
    honest = {"assignment": CERTIFIED["assignment"], "staffed": 8, "source": "worker prose is not bound"}
    assert workers.bound_artifact_findings(BOUND, CONTEXT, delivered(honest)) == []
    [assignment, staffed] = workers.bound_artifact_findings(BOUND, CONTEXT, delivered(LIE))   # in the order's key order
    assert "CERTIFIED_PLAN_JSON" in staffed and "'staffed'" in staffed and "delivered 9, bound 8" in staffed
    assert "'assignment'" in assignment
    # canonical JSON: key order and whitespace never matter, values do
    reordered = {"staffed": 8, "assignment": [list(x) for x in CERTIFIED["assignment"]]}
    assert workers.bound_artifact_findings(BOUND, CONTEXT, delivered(reordered)) == []
    whole = {"bound_artifacts": [{"path": "plan/plan.json", "label": "CERTIFIED_PLAN_JSON"}]}
    assert workers.bound_artifact_findings(whole, CONTEXT, delivered(CERTIFIED)) == []
    assert workers.bound_artifact_findings(whole, CONTEXT, delivered(honest))


@pytest.mark.parametrize("context, says", [("", "carries no CERTIFIED_PLAN_JSON value"),
                                          (CONTEXT + "\n" + CONTEXT, "more than one"),
                                          ("CERTIFIED_PLAN_JSON:\nnot json", "is not JSON")])
def test_the_bound_value_must_be_one_json_value_in_the_frozen_context(context, says):
    [finding] = workers.bound_artifact_findings(BOUND, context, delivered(CERTIFIED))
    assert says in finding


def test_a_missing_or_non_json_artifact_is_refused_not_skipped():
    [finding] = workers.bound_artifact_findings(BOUND, CONTEXT, delivered(None))
    assert "missing, a symbolic link or not JSON" in finding


# -- re-derivation ----------------------------------------------------------------------------------

def test_the_staffing_verifier_checks_feasibility_its_own_total_and_the_exhaustive_optimum():
    assert artifact_verifiers.staffing_plan(CERTIFIED, STAFFING) == []
    short = {"assignment": [["Ana", "Dock2", 2], ["Ben", "Dock1", 3], ["Cy", "Line", 2]], "staffed": 7}
    assert artifact_verifiers.staffing_plan(short, STAFFING) == [
        "staffed 7 but the exhaustive optimum of the problem is 8"]
    over = artifact_verifiers.staffing_plan(LIE, STAFFING)
    assert "Line is filled 3, above demand 2" in over and any("optimum of the problem is 8" in f for f in over)
    padded = {"assignment": CERTIFIED["assignment"], "staffed": 9}
    assert any("not the assignment's own total 8" in f for f in artifact_verifiers.staffing_plan(padded, STAFFING))
    assert artifact_verifiers.staffing_plan({"assignment": [["Cy", "Dock1", 1]], "staffed": 1}, STAFFING) == [
        "Cy is not eligible for Dock1, or the pair repeats"]
    overload = {"assignment": [["Ben", "Dock1", 4], ["Ben", "Dock2", 1]], "staffed": 5}
    assert "Ben is assigned 5, above capacity 4" in artifact_verifiers.staffing_plan(overload, STAFFING)


def test_the_staffing_verifier_never_assumes_optimality_it_cannot_re_derive():
    big = {"workers": [{"id": "W", "capacity": 1, "skills": ["s"]}],
           "orders": [{"id": f"O{i}", "demand": 1, "skill": "s"} for i in range(17)]}
    [finding] = artifact_verifiers.staffing_plan({"assignment": [["W", "O0", 1]], "staffed": 1}, big)
    assert "17 orders exceed the exhaustive verifier's 16" in finding


def test_re_derivation_runs_on_gregs_copies_and_names_the_verifier():
    assert workers.rederivation_findings(VERIFIED, delivered(CERTIFIED)) == []
    lie = workers.rederivation_findings(VERIFIED, delivered(LIE))
    assert lie and all(f.startswith("verifier assignment.staffing on plan/plan.json: ") for f in lie)
    [absent] = workers.rederivation_findings(VERIFIED, delivered(CERTIFIED, problem=None))
    assert "problem.json is missing, a symbolic link or not JSON in the recorded base" in absent


@pytest.mark.parametrize("acceptance, mode, message", [
    ({"verifiers": [{"name": "nope", "artifact": "plan/p.json", "problem": "p.json"}]}, "repository", "unknown"),
    ({"bound_artifacts": [{"path": "src/p.json", "label": "X"}]}, "repository", "writable surface"),
    ({"bound_artifacts": [{"path": "/plan/p.json", "label": "X"}]}, "repository", "relative path"),
    ({"bound_artifacts": [{"path": "plan/../p.json", "label": "X"}]}, "repository", "relative path"),
    ({"bound_artifacts": [{"path": "plan/p.json", "label": "lower"}]}, "repository", "upper-case"),
    ({"bound_artifacts": [{"path": "plan/p.json", "label": "X", "keys": []}]}, "repository", "non-empty"),
    ({"bound_artifacts": [{"path": "plan/p.json", "label": "X", "extra": 1}]}, "repository", "at most"),
    ({"verifiers": [{"name": "assignment.staffing", "artifact": "plan/p.json", "problem": "../p.json"}]},
     "repository", "relative path"),
    ({"bound_artifacts": [{"path": "plan/p.json", "label": "X"}]}, "document", "repository work orders")])
def test_malformed_acceptance_bindings_are_refused_at_commission(acceptance, mode, message):
    with pytest.raises(workers.WorkerError, match=message):
        workers.acceptance_bindings(acceptance, mode, ("plan/*", "tests/*"))


# -- discrimination ---------------------------------------------------------------------------------

def staged_patch(tmp_path, files: dict, links: dict | None = None) -> tuple[Path, str, str]:
    repo = make_repo(tmp_path)
    base = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True,
                          check=True).stdout.strip()
    for rel, text in files.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text)
    for rel, target in (links or {}).items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).symlink_to(target)
    workers._git(repo, "add", "-A")
    return repo, base, workers._git(repo, "diff", "--cached", "--name-status", "--no-renames", base).stdout


def discriminate(tmp_path, repo, base, name_status, acceptance=None):
    inputs = workers.delivered_inputs(repo, base, acceptance or {}, name_status)
    tree = None
    if inputs["tests"] and None not in inputs["test_side"].values():
        tree = tmp_path / "base-tree"
        workers.base_tree(repo, base, tree, inputs["test_side"])
    return workers.discrimination_findings(tree, inputs, timeout=60)


def test_a_test_that_passes_on_the_base_proves_nothing_and_is_refused(tmp_path):
    repo, base, status = staged_patch(tmp_path, {"tests/test_vacuous.py": "def test_ok():\n    assert True\n"})
    [finding], run = discriminate(tmp_path, repo, base, status)
    assert "pass on the recorded base without its change" in finding and run["returncode"] == 0


def test_a_test_that_depends_on_the_change_fails_on_the_base_and_passes_this_check(tmp_path):
    repo, base, status = staged_patch(tmp_path, {
        "pkg/sub.py": "def sub(a, b):\n    return a - b\n",
        "tests/test_sub.py": "from pkg.sub import sub\n\n\ndef test_sub():\n    assert sub(3, 1) == 2\n"})
    findings, run = discriminate(tmp_path, repo, base, status)
    assert findings == [] and run["returncode"] in (1, 2)
    assert not (tmp_path / "base-tree" / "pkg" / "sub.py").exists(), "the change itself never reaches the base run"


def test_test_side_helpers_travel_to_the_base_run(tmp_path):
    """A vacuous test hidden behind a helper in its own test directory still passes on the base: refused."""
    repo, base, status = staged_patch(tmp_path, {
        "tests/__init__.py": "", "tests/helper.py": "def check():\n    return True\n",
        "tests/test_helped.py": "from tests.helper import check\n\n\ndef test_ok():\n    assert check()\n"})
    [finding], _ = discriminate(tmp_path, repo, base, status)
    assert "prove nothing" in finding


def test_a_symbolic_link_is_never_followed_as_a_test_or_an_artifact(tmp_path):
    repo, base, status = staged_patch(tmp_path, {"tests/vacuous.py": "def test_ok():\n    assert True\n",
                                                 "plan/real.json": json.dumps(CERTIFIED)},
                                      links={"tests/test_linked.py": "vacuous.py", "plan/plan.json": "real.json"})
    inputs = workers.delivered_inputs(repo, base, BOUND, status)
    assert inputs["test_side"]["tests/test_linked.py"] is None and inputs["artifacts"]["plan/plan.json"] is None
    [finding], run = discriminate(tmp_path, repo, base, status)
    assert "symbolic links or unreadable" in finding and run is None
    assert "symbolic link" in workers.bound_artifact_findings(BOUND, CONTEXT, inputs)[0]


# -- on the canonical path: commission, the in-body appraisal and the separate appraiser ----------------

def code_mission(tmp_path, monkeypatch, edits: dict, *, acceptance: dict | None = None, ticks: int = 6):
    data = tmp_path / "data"
    data.mkdir()
    repo = make_repo(data)
    (repo / "problem.json").write_text(json.dumps(STAFFING))
    workers._git(repo, "add", "-A")
    workers._git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "problem")
    home, key, body_id, _ = make_body(tmp_path, read_roots=[data])
    spec = templates.code_change(repo=str(repo), objective="record the plan", order="r1a", provider="scripted",
                                 allowed_paths=["pkg/*", "plan/*", "tests/*"], budget_usd=1.0,
                                 workspace_root=Layout(home).workspace)
    spec["strategies"][0]["params"]["acceptance"].update(acceptance or {})
    clock = Clock()
    monkeypatch.setitem(workers.PROVIDERS, "scripted", ScriptedWorker(edits))
    drop(home, signed(key, body_id, "MISSION", spec))
    with Body(home, clock=clock) as body:
        states = []
        for _ in range(ticks):
            states.append(body.tick()["missions"][0]["state"])
            clock.advance(60)
        verdicts = [r.payload["result"]["output"] for r in body.ledger.by_type("receipt")
                    if isinstance(r.payload["result"].get("output"), dict)
                    and r.payload["result"]["output"].get("order") == "r1a"
                    and "verdict" in r.payload["result"]["output"]]
        appraisal = body.appraise(spec["mission_id"]) if "ACHIEVED" in states else None
    return states, verdicts[-1], appraisal


def test_a_vacuous_test_no_longer_closes_a_code_change_mission(tmp_path, monkeypatch):
    states, verdict, _ = code_mission(tmp_path, monkeypatch, {"pkg/calc.py": "def add(a, b):\n    return a + b\n# touched\n",
                                                 "tests/test_calc.py": "def test_ok():\n    assert True\n"})
    assert verdict["verdict"] == "REJECTED" and "ACHIEVED" not in states
    assert any("pass on the recorded base" in f for f in verdict["findings"]), verdict["findings"]
    assert verdict["base_run"]["returncode"] == 0


def test_an_honest_change_closes_with_its_tests_failing_on_the_base(tmp_path, monkeypatch):
    states, verdict, appraisal = code_mission(tmp_path, monkeypatch, {
        "pkg/calc.py": "def add(a, b):\n    return a + b\n\n\ndef sub(a, b):\n    return a - b\n",
        "tests/test_calc.py": "from pkg.calc import sub\n\n\ndef test_sub():\n    assert sub(3, 1) == 2\n"})
    assert verdict["verdict"] == "ACCEPTED" and "ACHIEVED" in states, verdict["findings"]
    assert verdict["base_run"]["returncode"] in (1, 2) and len(verdict["independent_tests"]) == 1
    assert appraisal["verdict"] == "VERIFIED", appraisal["findings"]


def test_a_coherent_lie_is_refused_by_the_named_verifier_on_the_canonical_path(tmp_path, monkeypatch):
    own_test = ('import json\nfrom pathlib import Path\n\n\ndef test_plan():\n    plan = json.loads((Path(__file__)'
                '.resolve().parents[1] / "plan" / "plan.json").read_text())\n    assert plan["staffed"] == 9\n')
    states, verdict, _ = code_mission(tmp_path, monkeypatch, {"plan/plan.json": json.dumps(LIE), "tests/test_plan.py": own_test},
                                      acceptance=VERIFIED)
    assert verdict["verdict"] == "REJECTED" and "ACHIEVED" not in states
    assert verdict["independent_tests"][0]["passed"], "its own test passes: only the verifier refuses it"
    assert any(f.startswith("verifier assignment.staffing on plan/plan.json") for f in verdict["findings"])


def test_the_one_machine_order_binds_the_certified_plan_and_names_its_verifier():
    spec = templates.one_machine(problem_id="p", data=STAFFING, sandbox_repo="/tmp",
                                 organs={k: "/x" for k in ("daleobanks_root", "daleobanks_python",
                                                           "wealthmachine_root", "wealthmachine_python")}, seed="s")
    commission = next(s for s in spec["strategies"] if s["action_id"] == "commission")
    acceptance = commission["params"]["acceptance"]
    assert acceptance["bound_artifacts"] == BOUND["bound_artifacts"]
    assert acceptance["verifiers"] == VERIFIED["verifiers"]
    assert commission["bind"][0]["template"].startswith("CERTIFIED_PLAN_JSON:\n")
    workers.acceptance_bindings(acceptance, "repository", tuple(commission["params"]["allowed_paths"]))


def test_a_work_order_with_malformed_bindings_is_refused_before_any_worker_runs(tmp_path):
    from greg.capabilities import BUILTINS, InvocationContext
    repo = make_repo(tmp_path)
    ctx = InvocationContext(workspace=tmp_path, read_roots=(tmp_path,), secrets=None,
                            manifest=BUILTINS["worker.commission"][0])
    params = {"order": "x", "objective": "o", "max_budget_usd": 1, "repo": str(repo), "allowed_paths": ["plan/*"],
              "acceptance": {"run_changed_tests": True, "verifiers": [{"name": "assignment.staffing",
                                                                        "artifact": "src/p.json", "problem": "p.json"}]}}
    with pytest.raises(workers.WorkerError, match="writable surface"):
        workers.WorkOrder.from_params(params, ctx)


def test_the_artifact_verifiers_are_a_protected_surface():
    assert workers.protected("greg/artifact_verifiers.py")
