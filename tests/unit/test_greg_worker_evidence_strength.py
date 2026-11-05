"""A worker cannot certify its own change: sealed oracle, discrimination and mutation adversary.

Baseline at c64ae19, the head before this change: a wrong ``sub()`` (it adds) shipped with
``assert True``, or with ``assert sub(0, 0) == 0``, was ACCEPTED by ``worker.appraise``. The mission
closed, and the founder's review handoff was written. These tests drive the same real Body path
with the scripted test double from ``test_greg_workers``. They cover corrupted output, a sealed
oracle the worker rewrote, an ablation that removes the new mechanism, and a restart.
"""
from __future__ import annotations

import importlib.util
import json
import py_compile
from pathlib import Path

import pytest

from greg import evidence_strength, templates, workers
from greg.body import Body, Layout
from greg.capabilities import BUILTINS, InvocationContext, SecretBroker
from tests.greg_fixtures import Clock, drop, make_body, signed
import tests.unit.test_greg_workers as tw
from tests.unit.test_greg_workers import GOOD, ScriptedWorker, git, make_repo, run_mission
# The worker tests' autouse envelope applies here too: real confinement where the host provides it, else the
# labelled scripted envelope, so these appraisal tests run on a host without usable bubblewrap (CI runners).
from tests.unit.test_greg_workers import acceptance_envelope  # noqa: F401  (autouse fixture)

WRONG = "def add(a, b):\n    return a + b\n\n\ndef sub(a, b):\n    return a + b\n"          # corrupted: sub adds
VACUOUS = {"pkg/calc.py": WRONG, "tests/test_calc.py": "def test_ok():\n    assert True\n"}
WEAK = {"pkg/calc.py": WRONG, "tests/test_calc.py":
        "from pkg.calc import sub\n\n\ndef test_sub():\n    assert sub(0, 0) == 0\n"}
ORACLE = "from pkg.calc import sub\n\n\ndef test_sub_oracle():\n    assert sub(5, 2) == 3\n"


def verdicts(observed):
    return [o for o in observed if o["check_id"] == "work_accepted"]


def appraise_again(home, tmp_path, order="add-sub", mission="m_work-add-sub"):
    root = Layout(home).workspace / mission / "work-orders" / order
    config = json.loads(Layout(home).config.read_text())
    ctx = InvocationContext(workspace=root.parents[1], read_roots=tuple(Path(r) for r in config["read_roots"]),
                            secrets=SecretBroker(tmp_path / "s.json"), manifest=BUILTINS["worker.appraise"][0])
    return workers.appraise({"order": order}, ctx)


def test_a_vacuous_test_no_longer_certifies_a_corrupted_change(tmp_path, monkeypatch):
    home, _, _, events, observed = run_mission(tmp_path, monkeypatch, VACUOUS)
    assert "greg.mission.achieved" not in events
    assert verdicts(observed) and not any(o["passed"] for o in verdicts(observed))
    assert not (Layout(home).workspace / "m_work-add-sub" / "handoff-add-sub.md").exists()   # parent never continues
    result = appraise_again(home, tmp_path)
    assert result["verdict"] == "REJECTED"
    assert any("also pass on the base" in f for f in result["findings"])
    assert result["evidence_strength"]["discrimination"]["established"] is False


def test_a_test_that_cannot_tell_add_from_sub_is_refused_by_the_mutation_adversary(tmp_path, monkeypatch):
    home, _, _, events, _ = run_mission(tmp_path, monkeypatch, WEAK)
    assert "greg.mission.achieved" not in events
    result = appraise_again(home, tmp_path)
    strength = result["evidence_strength"]
    assert result["verdict"] == "REJECTED"
    assert strength["discrimination"]["established"] is True                  # it does fail on the base...
    assert strength["mutation"]["measured"] and strength["mutation"]["killed"] == 0   # ...but cannot see + vs -
    assert any("swap +/-" in s for s in strength["mutation"]["survivors"])
    assert any("mutants of its own change" in f for f in result["findings"])


def test_a_discriminating_test_still_lets_honest_work_through(tmp_path, monkeypatch):
    home, _, _, events, observed = run_mission(tmp_path, monkeypatch, GOOD)
    assert "greg.mission.achieved" in events                                   # non-regression floor
    result = appraise_again(home, tmp_path)
    strength = result["evidence_strength"]
    assert result["verdict"] == "ACCEPTED"
    assert strength["discrimination"]["established"] and strength["mutation"]["kill_ratio"] == 1.0
    again = appraise_again(home, tmp_path)                                      # replay gives the same judgment
    assert again["verdict"] == "ACCEPTED" and again["evidence_strength"]["mutation"] == strength["mutation"]
    assert again["evidence_strength"]["discrimination"]["returncode_on_base"] == 2   # sub() absent at the base


def run_with_oracle(tmp_path, monkeypatch, edits):
    data = tmp_path / "data"
    data.mkdir()
    repo = make_repo(data)
    (repo / "tests" / "test_oracle.py").write_text(ORACLE)                     # the founder's judge, at the base
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "add", "-A")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "founder oracle")
    home, key, body_id, _ = make_body(tmp_path, read_roots=[data])
    monkeypatch.setitem(workers.PROVIDERS, "scripted", ScriptedWorker(edits))
    spec = templates.code_change(repo=str(repo), objective="add sub()", order="add-sub", provider="scripted",
                                 allowed_paths=["pkg/*", "tests/*"], budget_usd=1.0,
                                 tests=[["python", "-m", "pytest", "-q", "tests/test_oracle.py"]],
                                 workspace_root=Layout(home).workspace)
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        for _ in range(6):
            body.tick()
            clock.advance(60)
        events = {e.type for e in body.journal.replay("mission.")}
    return home, events


def test_a_worker_that_rewrites_its_sealed_oracle_is_judged_by_the_founders_version(tmp_path, monkeypatch):
    home, events = run_with_oracle(tmp_path, monkeypatch, {**VACUOUS, "tests/test_oracle.py": "def test_x():\n    pass\n"})
    assert "greg.mission.achieved" not in events
    result = appraise_again(home, tmp_path)
    assert result["verdict"] == "REJECTED"
    assert any("sealed acceptance oracle ['tests/test_oracle.py']" in f for f in result["findings"])
    oracle_run = [t for t in result["independent_tests"] if "tests/test_oracle.py" in t["argv"]]
    assert oracle_run and oracle_run[0]["passed"] is False                     # the founder's sub(5, 2) == 3 ran


def test_an_untouched_oracle_and_honest_work_pass_together(tmp_path, monkeypatch):
    home, events = run_with_oracle(tmp_path, monkeypatch, GOOD)
    assert "greg.mission.achieved" in events
    assert appraise_again(home, tmp_path)["verdict"] == "ACCEPTED"


def test_ablation_without_the_new_interaction_the_corrupted_change_is_accepted_again(tmp_path, monkeypatch):
    monkeypatch.setattr(evidence_strength, "judge", lambda **kw: {"findings": []})
    monkeypatch.setattr(evidence_strength, "sealed_paths", lambda acceptance, base_files: set())
    _, _, _, events, _ = run_mission(tmp_path, monkeypatch, VACUOUS)
    assert "greg.mission.achieved" in events                                   # the c64ae19 behavior returns


def test_a_restart_does_not_turn_a_refusal_into_acceptance(tmp_path, monkeypatch):
    home, _, worker, events, _ = run_mission(tmp_path, monkeypatch, WEAK)
    assert "greg.mission.achieved" not in events
    clock = Clock()
    with Body(home, clock=clock) as body:                                      # a fresh process over the same ledger
        for _ in range(4):
            body.tick()
            clock.advance(3600)
        after = {e.type for e in body.journal.replay("mission.")}
        observed = [e.payload for e in body.journal.replay("mission.observed") if e.payload["check_id"] == "work_accepted"]
    assert "greg.mission.achieved" not in after
    assert observed and not any(o["passed"] for o in observed)
    assert worker.calls == 1                                                   # no blind re-commission


SHOWN = "def add(a, b):\n    return a + b\n\n\nsub = add\n"                       # what the founder reviews: wrong
COMPILED_FROM = GOOD["pkg/calc.py"]                                               # what a planted .pyc runs


class BytesWorker(ScriptedWorker):
    """Scripted double that also writes binary files, as any real worker in the clone can."""

    def __init__(self, edits, blobs):
        super().__init__(edits)
        self.blobs = blobs

    def run(self, order, cwd):
        report = super().run(order, cwd)
        for rel, data in self.blobs.items():
            (cwd / rel).parent.mkdir(parents=True, exist_ok=True)
            (cwd / rel).write_bytes(data)
        return report


def planted_bytecode(tmp_path):
    src = tmp_path / "calc.py"
    src.write_text(COMPILED_FROM)
    pyc = Path(importlib.util.cache_from_source(str(src)))
    py_compile.compile(str(src), cfile=str(pyc), invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH)
    return {"pkg/__pycache__/" + pyc.name: pyc.read_bytes()}


def test_a_planted_bytecode_file_cannot_stand_in_for_the_source_under_review(tmp_path, monkeypatch):
    """Probed on 196 (d35d92a5): ACCEPTED, mission achieved, with a delivered ``sub`` that adds."""
    worker = BytesWorker({"pkg/calc.py": SHOWN, "tests/test_calc.py": WEAK["tests/test_calc.py"].replace(
        "sub(0, 0) == 0", "sub(5, 2) == 3")}, planted_bytecode(tmp_path))
    monkeypatch.setattr(tw, "ScriptedWorker", lambda edits, cost=0.01: worker)
    home, _, _, events, _ = run_mission(tmp_path, monkeypatch, {})
    assert worker.calls == 1
    assert "greg.mission.achieved" not in events
    result = appraise_again(home, tmp_path)
    assert result["verdict"] == "REJECTED"
    assert any("compiled modules" in f and "__pycache__" in f for f in result["findings"])
    ran = [t for t in result["independent_tests"] if "tests/test_calc.py" in t["argv"]]
    assert ran and not any(t["passed"] for t in ran)                 # the source, sub = add, is what ran


def test_compiled_modules_name_bytecode_caches_and_native_extensions_only():
    names = ["pkg/__pycache__/calc.cpython-311.pyc", "pkg/calc.pyc", "pkg/_calc.cpython-311-x86_64-linux-gnu.so",
             "pkg/calc.pyd", "pkg/calc.py", "docs/pyc-notes.md", "tests/test_calc.py"]
    assert evidence_strength.compiled_modules(names) == [
        "pkg/__pycache__/calc.cpython-311.pyc", "pkg/_calc.cpython-311-x86_64-linux-gnu.so", "pkg/calc.pyc",
        "pkg/calc.pyd"]


ADD = "def add(a, b):\n    return a + b\n"
ALIAS = {"pkg/calc.py": ADD + "\n\nsub = add\n",                                 # corrupted: an alias, no operator
         "tests/test_calc.py": "from pkg.calc import sub\n\n\ndef test_sub():\n    assert True\n"}
LABEL = {"pkg/calc.py": ADD + '\n\nLABEL = "Approving records your answer; attaching is its own command"\n',
         "tests/test_calc.py": "from pkg.calc import LABEL\n\n\ndef test_label():\n    assert 'its own command' in LABEL\n"}
IMPORTED = {"pkg/calc.py": "from operator import sub\n\n\n" + ADD,                  # correct, but no site at all
            "tests/test_calc.py": "from pkg.calc import sub\n\n\ndef test_sub():\n    assert sub(5, 2) == 3\n"}


def test_an_alias_certified_only_by_importing_it_is_refused_by_the_fallback_tier(tmp_path, monkeypatch):
    """Probed on 196 (d35d92a5): ``sub = add`` gave no primary site, mutation went unmeasured, ACCEPTED."""
    home, _, _, events, _ = run_mission(tmp_path, monkeypatch, ALIAS)
    assert "greg.mission.achieved" not in events
    mutation = appraise_again(home, tmp_path)["evidence_strength"]["mutation"]
    assert mutation["tier"] == "fallback" and mutation["killed"] == 0
    assert mutation["survivors"] == ["line 5: assign value -> None"]


def test_a_string_change_pinned_by_its_test_is_measured_and_accepted(tmp_path, monkeypatch):
    home, _, _, events, _ = run_mission(tmp_path, monkeypatch, LABEL)
    assert "greg.mission.achieved" in events
    result = appraise_again(home, tmp_path)
    mutation = result["evidence_strength"]["mutation"]
    assert result["verdict"] == "ACCEPTED" and mutation["tier"] == "fallback" and mutation["kill_ratio"] == 1.0


def test_a_change_with_nothing_to_corrupt_needs_the_founders_acceptance_test(tmp_path, monkeypatch):
    home, _, _, events, _ = run_mission(tmp_path, monkeypatch, IMPORTED)
    assert "greg.mission.achieved" not in events
    result = appraise_again(home, tmp_path)
    assert result["evidence_strength"]["mutation"]["measured"] is False
    assert any("nothing to corrupt" in f and "name an acceptance test" in f for f in result["findings"])


def test_the_founders_acceptance_test_certifies_a_change_with_nothing_to_corrupt(tmp_path, monkeypatch):
    home, events = run_with_oracle(tmp_path, monkeypatch, IMPORTED)
    assert "greg.mission.achieved" in events
    result = appraise_again(home, tmp_path)
    assert result["verdict"] == "ACCEPTED" and result["evidence_strength"]["mutation"]["measured"] is False


DATA = {"plan/plan.json": '{"staffed": 3}\n',
        "tests/test_plan.py": "import json\n\n\ndef test_plan():\n    assert json.load(open('plan/plan.json'))['staffed'] == 3\n"}


def test_a_data_deliverable_is_outside_the_adversary_and_keeps_its_earlier_acceptance(tmp_path, monkeypatch):
    """CI on 5502651a (job 8): the fifteen-step mission's worker delivers plan/plan.json, no Python source;
    failing closed there refused the founder's own flagship mission. Mutation is not applicable to data."""
    home, _, _, events, _ = run_mission(tmp_path, monkeypatch, DATA, allowed=("plan/*", "tests/*"))
    assert "greg.mission.achieved" in events
    result = appraise_again(home, tmp_path)
    mutation = result["evidence_strength"]["mutation"]
    assert result["verdict"] == "ACCEPTED" and mutation["applicable"] is False and mutation["measured"] is False


# -- the parts on their own ---------------------------------------------------------------

def test_sealed_paths_cover_files_directories_and_node_ids():
    base = {"tests/a/test_x.py", "tests/a/helpers.py", "tests/test_y.py", "pkg/m.py"}
    acceptance = {"tests": [["python", "-m", "pytest", "-q", "tests/a"], ["pytest", "tests/test_y.py::test_one"],
                            ["python", "-c", "print(1)"]]}
    assert evidence_strength.sealed_paths(acceptance, base) == {"tests/a/test_x.py", "tests/a/helpers.py",
                                                                "tests/test_y.py"}


def test_added_lines_reads_unified_zero_context_hunks():
    diff = "diff --git a/x b/x\n@@ -1,0 +2,3 @@\n+a\n+b\n+c\n@@ -9 +12 @@\n-x\n+y\n@@ -20,2 +22,0 @@\n-p\n-q\n"
    assert evidence_strength.added_lines(diff) == {2, 3, 4, 12}


def test_mutants_touch_only_the_changed_lines_and_are_deterministic():
    source = "def f(a, b):\n    return a + b\n\n\ndef g(x):\n    return x > 1 and not x == 3\n"
    first = evidence_strength.mutants(source, {6})
    assert first == evidence_strength.mutants(source, {6})
    labels = [label for label, _ in first]
    assert labels and all(label.startswith("line 6") for label in labels)
    assert {"swap and/or", "drop 'not'", "negate comparison", "flip comparison"} <= {l.split(": ", 1)[1] for l in labels}
    assert all("a + b" in text for _, text in first)                            # line 2 untouched
    assert len(evidence_strength.mutants("x = [" + ", ".join(["1"] * 40) + "]\n", {1}, limit=5)) == 5


def test_the_fallback_tier_runs_only_where_the_primary_operators_find_nothing():
    source = '"""Module docstring."""\nfrom operator import sub\nLABEL = "text"\nalias = sub\n\n\ndef f(x):\n    return g(x) + 1\n'
    changed = set(range(1, 9))
    assert [label for label, _ in evidence_strength.mutants(source, changed)] == [
        "line 8: 1 -> 2", "line 8: 1 -> 0", "line 8: drop '+ 1'", "line 8: swap +/-"]
    assert [label for label, _ in evidence_strength.mutants(source, changed, tier="fallback")] == [
        "line 3: string emptied", "line 3: assign value -> None", "line 4: assign value -> None",
        "line 8: return value -> None"]                                  # never the docstring, never the import
