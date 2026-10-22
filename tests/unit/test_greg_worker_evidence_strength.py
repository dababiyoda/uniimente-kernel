"""A worker cannot certify its own change: sealed oracle, discrimination and mutation adversary.

Baseline at c64ae19, the head before this change: a wrong ``sub()`` (it adds) shipped with
``assert True``, or with ``assert sub(0, 0) == 0``, was ACCEPTED by ``worker.appraise``. The mission
closed, and the founder's review handoff was written. These tests drive the same real Body path
with the scripted test double from ``test_greg_workers``. They cover corrupted output, a sealed
oracle the worker rewrote, an ablation that removes the new mechanism, and a restart.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from greg import evidence_strength, templates, workers
from greg.body import Body, Layout
from greg.capabilities import BUILTINS, InvocationContext, SecretBroker
from tests.greg_fixtures import Clock, drop, make_body, signed
from tests.unit.test_greg_workers import GOOD, ScriptedWorker, git, make_repo, run_mission

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
