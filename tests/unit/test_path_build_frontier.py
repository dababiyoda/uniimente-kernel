"""The build frontier beside the acceptance frontier (founder correction of 2026-10-30).

"Continue building and doing the prompt verbatim. No real Chromebook run is needed. That is done when we
completely build the prompt" (INTENT-20261030-BUILD-BEFORE-DEVICE-RUN). The device run moved to the end of the
build; it was not redefined. So the build is read on its own axis, from the predicates' ``structurally_met``,
and a test key, a fixture or a rehearsal moves only that axis: ``achieved``, the one operationally primary node
and VEPMC still move only at the founder tier.
"""
from __future__ import annotations

import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path

import pytest

from greg import cli, metrics
from greg import path as devpath
from greg.body import Body
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, signed, workspace

ROOT = Path(__file__).resolve().parents[2]
PLACEMENTS = ROOT / "docs/collaboration/DEVELOPMENTAL-INHERITANCE-2026-09-30.json"
PLACEMENT = "n1.vepmc_is_final_acceptance_not_build_gate"
CORRECTION = "INTENT-20261030-BUILD-BEFORE-DEVICE-RUN"
PREDICATE_NODES = {"N1", "N2", "N3", "N4", "N6", "N7"}


def greg(*argv) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = cli.main([str(a) for a in argv])
        except SystemExit as exc:                      # argparse refusals exit; the CLI returns otherwise
            code = exc.code
    return code, out.getvalue(), err.getvalue()


def note(home, mid: str) -> dict:
    target = workspace(home, mid) / "n.txt"
    return mission(mid, checks=[note_check("n", target, "x")], strategies=[], capabilities=["fs.read"],
                   ceiling="read_only")


def rows(status: dict) -> dict:
    return {r["id"]: r for r in status["nodes"]}


def one_primary(status: dict, where: dict) -> str:
    """Exactly one node is operationally primary, and it is position()'s active node."""
    primary = [r["id"] for r in status["nodes"] if r["operationally_primary"]]
    assert primary == [where["active"]["id"]] == [status["acceptance_frontier"]["id"]], primary
    assert status["acceptance_frontier"]["operationally_primary"] is True
    assert status["achieved"] == where["achieved"]
    assert status["built"][:len(status["achieved"])] == status["achieved"]   # acceptance never runs ahead of the build
    return primary[0]


def test_a_fresh_body_has_both_frontiers_at_n1_and_the_cli_prints_them(tmp_path):
    home, *_ = make_body(tmp_path)
    with Body(home) as body:
        status, where = devpath.build_status(body.journal), devpath.position(body.journal)
    assert status["build_frontier"]["id"] == status["acceptance_frontier"]["id"] == "N1"
    assert one_primary(status, where) == "N1" and status["achieved"] == status["built"] == ["N0"]
    # N1 is not built here, so its acceptance is not one founder step away (review WU01-F2).
    assert status["acceptance_frontier"]["build"] == devpath.BUILD_OPEN
    assert status["acceptance_frontier"]["status"] == devpath.ACCEPTANCE_AFTER_BUILD
    by_id = rows(status)
    assert by_id["N0"]["build"] == devpath.STRUCTURALLY_BUILT and by_id["N1"]["build"] == devpath.BUILD_OPEN
    assert {i for i, r in by_id.items() if r["build"] == devpath.NO_PREDICATE} == {"N5", "N8", "N9", "N10"}
    assert status["structural_depth"] == 0 and status["built_ahead"] == []
    assert CORRECTION in status["sequencing"] and CORRECTION in devpath.load()["intent"]

    code, out, _ = greg("--home", home, "path", "--build")
    printed = json.loads(out)
    assert code == 0 and printed["build_frontier"]["id"] == printed["acceptance_frontier"]["id"] == "N1"
    assert printed["acceptance_frontier"]["status"] == "build open; acceptance follows the build"
    assert "only by a run of the gate" in printed["mutation_guard"]          # listed, never claimed caught
    assert [r["build"] for r in printed["nodes"]] == [r["build"] for r in status["nodes"]]
    code, out, _ = greg("--home", home, "path")                       # the plain view is unchanged
    assert code == 0 and "build_frontier" not in json.loads(out) and json.loads(out)["active"]["id"] == "N1"
    code, _, err = greg("--home", home, "path", "--build", "--node", "N3")
    assert code == 2 and "not allowed with" in err


def test_without_a_body_ledger_nothing_is_built_and_the_frontiers_say_why():
    status = devpath.build_status(None)
    n1 = rows(status)["N1"]
    assert n1["build"] == devpath.BUILD_OPEN and n1["why"] == "no body ledger here: measure on the body"
    assert status["build_frontier"]["id"] == status["acceptance_frontier"]["id"] == "N1"


def test_test_key_closures_move_only_the_build_frontier(tmp_path, monkeypatch):
    """The setup of test_structural_closures_cannot_advance_the_external_primary_gate: missions signed by a test
    key, with VEPMC's rows stubbed so N1 is structurally met. N1 and N2 are structurally met, so the build reaches
    N3, and the founder's path does not move. The founder tier is read here from the real ledger; VEPMC's own
    founder_tier_count on a real one-body ledger is asserted by tests/integration/test_greg_chromebook_rehearsal.py
    (review F2: here VEPMC has no rows, so asserting it would test nothing)."""
    home, key, body_id, _ = make_body(tmp_path)
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        for mid in ("m:brief", "m:genesis"):
            drop(home, signed(key, body_id, "MISSION", note(home, mid), now=clock.now))
        body.tick()
        journal = body.journal
        counted = {"VEPMC": 1, "external_confirmation_required": "x",
                   "missions": [{"mission_id": "m:brief", "counts": True, "missing": []}]}
        monkeypatch.setattr(metrics, "vepmc", lambda j: counted)
        status = devpath.build_status(journal)
        assert status["build_frontier"]["id"] == "N2" and one_primary(status, devpath.position(journal)) == "N1"

        counted["missions"].append({"mission_id": "m:genesis", "counts": True, "missing": []})
        journal.record("deficit.opened", {"deficit_id": "d3", "mission_id": "m:genesis", "function": "h"}, key="d3")
        journal.record("deficit.resolved", {"deficit_id": "d3", "capability_id": "built:abc", "mission_id": "m:genesis"},
                       key=["d3", "resolved"])
        journal.record("mission.achieved", {"mission_id": "m:genesis"}, key=["m:genesis", "achieved"])
        status, where = devpath.build_status(journal), devpath.position(journal)
        tiers = metrics.founder_tier(journal)
    assert status["build_frontier"]["id"] == "N3" and status["built"] == ["N0", "N1", "N2"]
    assert one_primary(status, where) == "N1" and where["active"]["id"] == "N1"
    assert status["achieved"] == where["achieved"] == ["N0"]                       # achieved is unchanged
    by_id = rows(status)
    for node in ("N1", "N2"):
        assert by_id[node]["build"] == devpath.STRUCTURALLY_BUILT and by_id[node]["counted"]
        assert by_id[node]["evidence_level"] == metrics.STRUCTURAL_CANDIDATE
    assert where["active"]["measurement"]["not_founder_tier"] == {m: metrics.NOT_FOUNDER_TIER
                                                                   for m in ("m:brief", "m:genesis")}
    assert {tiers[m]["tier"] for m in ("m:brief", "m:genesis")} == {metrics.STRUCTURAL_CANDIDATE}
    assert status["acceptance_frontier"]["status"] == devpath.ACCEPTANCE_PENDING   # N1 built: only acceptance left
    assert status["structural_depth"] == 2                                        # N1 and N2, both guarded


def _structural_only(monkeypatch, names):
    """Every named predicate structurally met with a test key: real structure, never the founder tier."""
    for name in names:
        monkeypatch.setitem(devpath.PREDICATES, name, lambda journal: devpath._tiered(
            {"value": 0, "structural_value": 1}, structural=True, passed=[],
            refused={"m:test-key": metrics.NOT_FOUNDER_TIER}))


def test_a_node_without_a_predicate_stops_the_build(monkeypatch):
    _structural_only(monkeypatch, list(devpath.PREDICATES))
    journal = object()                                   # the predicates are replaced; no ledger is read
    status = devpath.build_status(journal)
    by_id = rows(status)
    assert status["build_frontier"]["id"] == "N5" and by_id["N5"]["build"] == devpath.NO_PREDICATE
    assert by_id["N5"]["evidence_level"] == "NONE" and "met" not in status["build_frontier"]["measurement"]
    assert status["built"] == ["N0", "N1", "N2", "N3", "N4"]
    for node in ("N6", "N7"):                           # measured past the frontier: reported, never counted
        assert not by_id[node]["counted"] and node not in status["built"]
    assert [r["id"] for r in status["built_ahead"]] == ["N6", "N7"]
    assert status["structural_depth"] == 4
    # The founder's path: still N1, nothing achieved, nothing met ahead.
    assert status["achieved"] == ["N0"] and status["acceptance_frontier"]["id"] == "N1"
    assert sum(r["operationally_primary"] for r in status["nodes"]) == 1 and by_id["N1"]["operationally_primary"]


def test_a_founder_tier_closure_moves_the_acceptance_frontier_and_never_past_the_build(monkeypatch):
    _structural_only(monkeypatch, list(devpath.PREDICATES))
    monkeypatch.setitem(devpath.PREDICATES, "vepmc_at_least_one", lambda journal: devpath._tiered(
        {"value": 1, "structural_value": 1}, structural=True, passed=["m:founder"], refused={}))
    status = devpath.build_status(object())
    assert status["achieved"] == ["N0", "N1"] and status["acceptance_frontier"]["id"] == "N2"
    assert status["build_frontier"]["id"] == "N5" and rows(status)["N1"]["evidence_level"] == metrics.FOUNDER_TIER
    assert [r["id"] for r in status["nodes"] if r["operationally_primary"]] == ["N2"]


def test_the_build_depth_counts_only_mutation_guarded_nodes(monkeypatch):
    _structural_only(monkeypatch, list(devpath.PREDICATES))
    monkeypatch.setattr(devpath, "mutation_guarded", lambda gate=None: {"N1", "N2", "N4"})
    status = devpath.build_status(object())
    assert status["built"][-1] == "N4" and status["structural_depth"] == 2          # N3 unguarded stops the count
    assert [r["mutation_guarded"] for r in status["nodes"][:5]] == [False, True, True, False, True]


def test_n1_counts_only_a_closure_that_meets_all_nine_conditions(tmp_path, monkeypatch):
    home, *_ = make_body(tmp_path)
    monkeypatch.setattr(metrics, "vepmc", lambda j: {"VEPMC": 0, "external_confirmation_required": "x", "missions": [
        {"mission_id": "m:half", "counts": False, "missing": ["interruption_survived", "founder_accepted"]}]})
    with Body(home) as body:
        n1 = devpath.vepmc_at_least_one(body.journal)
        status = devpath.build_status(body.journal)
    assert n1["structurally_met"] is False and n1["closest_closure"]["mission_id"] == "m:half"
    assert rows(status)["N1"]["build"] == devpath.BUILD_OPEN and status["build_frontier"]["id"] == "N1"


def test_n7_needs_a_transplant_that_was_faster_or_cheaper(monkeypatch):
    from greg import venture_books
    slower = {"procedure_id": "sop-x", "from_venture": "leases", "to_venture": "audits", "faster_or_cheaper": False,
              "why_not": ["no measure fell"]}
    monkeypatch.setattr(venture_books, "transfers", lambda journal: [slower])
    monkeypatch.setattr(venture_books, "books", lambda journal: [
        {"venture": "audits", "currency": "USD", "surplus_for_reinvestment": "400.00", "cases": ["c1"]}])
    result = devpath.venture_compounding(None)
    assert result["structurally_met"] is False and result["missing"][0].startswith("no transplant was faster")


def test_mutation_guarded_reads_the_gate_and_covers_every_node_predicate(tmp_path):
    assert devpath.mutation_guarded() == PREDICATE_NODES
    assert {n["id"] for n in devpath.load()["nodes"] if n.get("predicate")} == PREDICATE_NODES
    assert devpath.mutation_guarded(tmp_path / "absent.py") == set()               # no gate in this install
    weird = _mini_repo(tmp_path)
    weird.write_text("MUTANTS = [(name, 'N1') for name in 'ab']\n")             # not plain literals: never read
    assert devpath.mutation_guarded(weird) == set()
    weird.write_text(f"MUTANTS = [{LIVE!r}, ('b', None, 'src.py', 'x = 1\\n', 'x = 3\\n', 'tests/test_x.py::test_x')]\n")
    assert devpath.mutation_guarded(weird) == {"N1"} and devpath.mutant_problems(weird) == []


# A greg/path.py with five predicates (N1 "one" on lines 1-2, N2 "two" calling the helper _shared, N3, N4, N6), an
# uncalled function, and a path whose N9 has no predicate.
MINI_PREDICATES = ('def one(journal):\n    return "one"\n\n\ndef _shared():\n    return "shared"\n\n\n'
                   'def two(journal):\n    _shared()\n    return "two"\n\n\n'
                   'def three(journal):\n    return "three"\n\n\ndef four(journal):\n    return "four"\n\n\n'
                   'def six(journal):\n    return "six"\n\n\ndef unused():\n    return "unused"\n\n\n'
                   'PREDICATES = {"one": one, "two": two, "three": three, "four": four, "six": six}\n')
MINI_NODES = [{"id": "N1", "predicate": "one"}, {"id": "N2", "predicate": "two"}, {"id": "N3", "predicate": "three"},
              {"id": "N4", "predicate": "four"}, {"id": "N6", "predicate": "six"}, {"id": "N9"}]


def mutant(name, node, word, test="tests/test_x.py::test_x", file="greg/path.py") -> tuple:
    """A mutant that edits the line `    return "<word>"`."""
    return (name, node, file, f'    return "{word}"\n', f'    return "{word}!"\n', test)


LIVE = mutant("a", "N1", "one")


def _mini_repo(root: Path) -> Path:
    """A repository holding the predicates above, one source line, one test and the gate's place
    (<root>/scripts/ci/gate.py)."""
    (root / "scripts" / "ci").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "greg").mkdir()
    (root / "greg" / "path.py").write_text(MINI_PREDICATES)
    (root / "greg" / "path.json").write_text(json.dumps({"nodes": MINI_NODES}))
    (root / "src.py").write_text("x = 1\n")
    (root / "tests" / "test_x.py").write_text("def test_x():\n    assert True\n")
    return root / "scripts" / "ci" / "gate.py"


def _real_repo(root: Path) -> tuple[Path, str]:
    """The real gate's text, and its place beside the real source and tests (symlinked)."""
    gate = root / "scripts" / "ci" / "check_path_predicate_mutants.py"
    gate.parent.mkdir(parents=True)
    for name in ("greg", "tests"):
        (root / name).symlink_to(ROOT / name)
    return gate, (ROOT / "scripts/ci/check_path_predicate_mutants.py").read_text()


def test_a_stale_no_op_or_untested_mutant_guards_nothing(tmp_path):
    """Review WU01-F1: a node stayed mutation_guarded, and kept counting toward the build depth, when its mutant
    was stale (its text gone from the source) or a no-op. A listed mutant now guards only while it can run as
    written; whether its test catches it is still shown only by running the gate, and the output says so."""
    gate = _mini_repo(tmp_path)
    mutants = [mutant("stale", "N1", "won"),
               ("no-op", "N2", "greg/path.py", '    return "two"\n', '    return "two"\n', "tests/test_x.py::test_x"),
               mutant("untested", "N3", "three", test="tests/test_x.py::test_gone"),
               mutant("no file", "N4", "four", file="gone.py"),
               mutant("live", "N6", "six")]
    gate.write_text(f"MUTANTS = {mutants!r}\n")
    assert devpath.mutation_guarded(gate) == {"N6"}
    problems = dict(devpath.mutant_problems(gate))
    assert problems["stale"].startswith("stale") and problems["no-op"].startswith("no-op")
    assert problems["untested"].startswith("no test") and problems["no file"].startswith("no file")
    assert "live" not in problems

    # The reviewer's reproduction on the real gate: N3's mutant made stale and N4's a no-op.
    gate, real = _real_repo(tmp_path / "real")
    n3 = "'        if not (observed and observed[-1][\"passed\"]):\\n            missing.append(\"payment_reconciled\")\\n',"
    n4 = "'        missing = [f\"sop_run_not_{c}\" for c in off_body]\\n',"
    assert real.count(n3) == 1 and real.count(n4) == 1
    gate.write_text(real.replace(n3, "'        if not (TEXT THAT IS NOT IN THE SOURCE):\\n',").replace(
        n4, "'        missing = list(p.get(\"why_not\", [])) + [f\"sop_run_not_{c}\" for c in off_body]\\n',"))
    assert devpath.mutation_guarded(gate) == PREDICATE_NODES - {"N3", "N4"}
    # Every mutant in the real gate is live, the build-frontier ones too.
    assert devpath.mutant_problems() == []


def test_a_malformed_gate_guards_nothing_and_never_crashes_the_cli(tmp_path, monkeypatch):
    """Review WU01-F3: a MUTANTS literal that is not a list (None, a number, a set, a dict with unhashable keys)
    raised TypeError out of `greg path --build`. It now reads as a gate that guards nothing."""
    gate = _mini_repo(tmp_path / "repo")
    for text in ("MUTANTS = None", "MUTANTS = 5", "MUTANTS = {[1]: 2}", f"MUTANTS = {{{LIVE!r}}}",
                 "MUTANTS = [(['a'], 'N1', 'src.py', 'x = 1\\n', 'x = 2\\n', 'tests/test_x.py::test_x')]"):
        gate.write_text(text + "\n")
        assert devpath.mutation_guarded(gate) == set(), text
        devpath.mutant_problems(gate)                                              # reads, never raises
    gate.write_text("MUTANTS = None\n")
    monkeypatch.setattr(devpath, "MUTANT_GATE", gate)
    home, *_ = make_body(tmp_path)
    code, out, err = greg("--home", home, "path", "--build")
    assert code == 0, err
    printed = json.loads(out)
    assert not any(r["mutation_guarded"] for r in printed["nodes"]) and printed["structural_depth"] == 0


def test_the_acceptance_status_follows_the_acceptance_nodes_build(monkeypatch):
    """Review WU01-F2: the acceptance frontier always said "founder acceptance pending (final step)", even on a
    node that is not built or has no predicate at all, telling the reader only acceptance remained."""
    assert set(devpath.ACCEPTANCE_STATUS) == {devpath.STRUCTURALLY_BUILT, devpath.BUILD_OPEN, devpath.NO_PREDICATE}
    accept = devpath.build_status(None)["acceptance_frontier"]                       # N1 open: no ledger
    assert (accept["id"], accept["build"], accept["status"]) == ("N1", devpath.BUILD_OPEN,
                                                                 devpath.ACCEPTANCE_AFTER_BUILD)
    _structural_only(monkeypatch, list(devpath.PREDICATES))
    accept = devpath.build_status(object())["acceptance_frontier"]                   # N1 built with a test key
    assert (accept["id"], accept["status"]) == ("N1", devpath.ACCEPTANCE_PENDING)
    for name in devpath.PREDICATES:                                                # every predicate founder-tier
        monkeypatch.setitem(devpath.PREDICATES, name, lambda journal: devpath._tiered(
            {"value": 1, "structural_value": 1}, structural=True, passed=["m:founder"], refused={}))
    status = devpath.build_status(object())
    accept = status["acceptance_frontier"]
    assert (accept["id"], accept["build"], accept["status"]) == ("N5", devpath.NO_PREDICATE,
                                                                 devpath.ACCEPTANCE_UNMEASURABLE)
    assert status["achieved"] == ["N0", "N1", "N2", "N3", "N4"] and status["build_frontier"]["id"] == "N5"


def test_a_repository_node_not_attested_achieved_stops_the_build(monkeypatch):
    """Review WU01-F4: no test pinned the repository-node rule; making every repository node built survived."""
    data = copy.deepcopy(devpath.load())
    [n0] = [n for n in data["nodes"] if n["evidence_source"] == "repository"]
    n0["attested"] = "NOT_YET_ON_MAIN"
    _structural_only(monkeypatch, list(devpath.PREDICATES))
    status = devpath.build_status(object(), data)
    where = devpath.position(None, data)                         # the founder walk needs no ledger here
    assert rows(status)["N0"]["build"] == devpath.BUILD_OPEN and status["built"] == []
    assert status["build_frontier"]["id"] == "N0" == where["active"]["id"] and status["achieved"] == []
    assert status["acceptance_frontier"]["status"] == devpath.ACCEPTANCE_AFTER_BUILD
    assert status["structural_depth"] == 0 and [r["id"] for r in status["built_ahead"]][:2] == ["N1", "N2"]


def test_a_gate_that_could_run_another_list_guards_nothing(tmp_path):
    """Review WU01-ATK-2 (a): the read took the first `MUTANTS = [...]`, so a gate that later reassigned, cleared or
    filtered its list was read as guarding nodes it never ran. A list now counts only when the gate binds it once
    and names it nowhere else, and the gate runs that same read (test_the_gate_runs_only_what_the_build_frontier_
    counts)."""
    gate = _mini_repo(tmp_path)
    listed = f"MUTANTS = [{LIVE!r}]\n"
    gate.write_text(listed)
    assert devpath.mutation_guarded(gate) == {"N1"}
    for later in ("MUTANTS = []", "MUTANTS.clear()", "MUTANTS += []", "del MUTANTS[0]", "MUTANTS[:] = []",
                  "mutants = MUTANTS", "for m in MUTANTS:\n    pass", "print(len(MUTANTS))",
                  "def f():\n    global MUTANTS", "globals()['MUTANTS'] = []", "from os import sep as MUTANTS",
                  "def MUTANTS():\n    pass", "MUTANTS: list = []", "import sys\nsys.modules[__name__].MUTANTS = []"):
        gate.write_text(listed + later + "\n")
        assert devpath.mutation_guarded(gate) == set(), later


def test_a_mutant_off_its_nodes_predicate_guards_nothing(tmp_path):
    """Review WU01-ATK-2 (b): a mutant tagged with a node counted for it wherever its text was, a README line
    included. It now guards its node only from inside that node's predicate in greg/path.py, or a function the
    predicate calls."""
    gate = _mini_repo(tmp_path)
    (tmp_path / "README.md").write_text("one\n")
    test = "tests/test_x.py::test_x"
    mutants = [("readme", "N1", "README.md", "one\n", "won\n", test),
               # Line 2 of tests/test_x.py: inside N1's line numbers, but not in greg/path.py.
               ("same line, another file", "N1", "tests/test_x.py", "    assert True\n", "    assert False\n", test),
               mutant("another node's predicate", "N3", "one"),
               mutant("a function no predicate calls", "N4", "unused"),
               mutant("a helper another predicate calls", "N1", "shared"),
               mutant("a helper its predicate calls", "N2", "shared"),
               mutant("its own predicate", "N6", "six")]
    gate.write_text(f"MUTANTS = {mutants!r}\n")
    assert devpath.mutation_guarded(gate) == {"N2", "N6"}
    problems = dict(devpath.mutant_problems(gate))
    assert set(problems) == {"readme", "same line, another file", "another node's predicate",
                             "a function no predicate calls", "a helper another predicate calls"}
    assert all(why.startswith("off target") for why in problems.values()), problems

    # The reviewer's case on the real gate: N3's mutant, its text unchanged, aimed at a README holding that text.
    gate, real = _real_repo(tmp_path / "real")
    tag = '"N3", "greg/path.py",'
    assert real.count(tag) == 1
    gate.write_text(real.replace(tag, '"N3", "README.md",'))
    (gate.parents[2] / "README.md").write_text(
        '        if not (observed and observed[-1]["passed"]):\n            missing.append("payment_reconciled")\n')
    assert devpath.mutation_guarded(gate) == PREDICATE_NODES - {"N3"}


def test_only_a_test_pytest_would_collect_makes_a_mutant_live(tmp_path):
    """Review WU01-ATK-2 (c): the test lookup was a regex over the file's text, so `def test_gone():` inside a
    docstring kept a removed test defined. A test is now found in the parsed module, where pytest collects it."""
    gate = _mini_repo(tmp_path)
    (tmp_path / "tests" / "test_y.py").write_text(
        '"""Notes.\n\ndef test_in_docstring():\n"""\nNOTE = "def test_in_string():"\n\n\n'
        'def helper():\n    def test_nested():\n        pass\n\n\n'
        'class TestKind:\n    def test_method(self):\n        pass\n\n\n'
        'def test_real():\n    pass\n')
    defined = {"test_in_docstring": False, "test_in_string": False, "test_nested": False, "helper": False,
               "test_method": False, "TestKind::test_real": False, "TestKind::test_method": True,
               "test_real": True, "test_real[1]": True}
    for name, expected in defined.items():
        listed = mutant("a", "N1", "one", test=f"tests/test_y.py::{name}")
        gate.write_text(f"MUTANTS = [{listed!r}]\n")
        assert (devpath.mutation_guarded(gate) == {"N1"}) is expected, name


def _run_gate(root: Path, files: dict, mutants: list, monkeypatch, capsys) -> tuple[int, list]:
    """Run this tree's gate on a small repository holding ``files`` and a gate file that lists ``mutants``."""
    for relative, text in {**files, "scripts/ci/check_path_predicate_mutants.py": f"MUTANTS = {mutants!r}\n"}.items():
        (root / relative).parent.mkdir(parents=True, exist_ok=True)
        (root / relative).write_text(text)
    spec = importlib.util.spec_from_file_location("path_predicate_gate",
                                                  ROOT / "scripts/ci/check_path_predicate_mutants.py")
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    monkeypatch.setattr(gate, "ROOT", root)
    monkeypatch.setattr(gate, "MUTANTS", mutants)          # what a gate that ran its own list would run
    code = gate.main()
    return code, capsys.readouterr().out.splitlines()


LAZY = {"greg/path.json": '{"nodes": []}', "pkg/__init__.py": "", "pkg/lazy.py": "VALUE = 1\n",
        "pkg/user.py": "from pkg.lazy import VALUE\n", "pkg/core.py": "def double(x):\n    return 2 * x\n",
        "tests/test_pkg.py": "def test_double():\n"
                             "    from pkg import core, user                 # imported here, after collection\n"
                             "    assert core.double(user.VALUE) == 2\n"}


def test_the_gate_never_counts_a_mutant_that_breaks_an_import_as_caught(tmp_path, monkeypatch, capsys):
    """Review WU01-ATK-1: a mutant that broke a module its test imports lazily made the test FAIL rather than ERROR
    at collection, and the gate printed CAUGHT. A mutated module that does not import, or a test that fails on a
    syntax or import error, is now INVALID; only a failure on behaviour is a catch."""
    test = "tests/test_pkg.py::test_double"
    mutants = [("a syntax error in a lazily imported module", None, "pkg/lazy.py", "VALUE = 1\n",
                "VALUE = 1\ndef broken(:\n", test),
               ("a module that raises while it is imported", None, "pkg/lazy.py", "VALUE = 1\n",
                'VALUE = 1\nraise RuntimeError("broken at import")\n', test),
               ("a name another module imports is removed", None, "pkg/lazy.py", "VALUE = 1\n",
                "VALUE_RENAMED = 1\n", test),
               ("double adds", None, "pkg/core.py", "    return 2 * x\n", "    return 2 + x\n", test)]
    code, lines = _run_gate(tmp_path, LAZY, mutants, monkeypatch, capsys)
    assert code == 1 and lines[-1] == "1/4 caught", lines
    assert [line for line in lines if line.startswith("CAUGHT")] == ["CAUGHT double adds"]
    invalid = [line for line in lines if line.startswith("INVALID")]
    assert len(invalid) == 3, lines
    assert "does not import" in invalid[0] and "SyntaxError" in invalid[0]
    assert "does not import" in invalid[1] and "RuntimeError" in invalid[1]
    assert "failed on ImportError" in invalid[2]


def test_the_gate_runs_only_what_the_build_frontier_counts(tmp_path, monkeypatch, capsys):
    """Review WU01-ATK-2: the gate ran its own MUTANTS, so a mutant tagged N3 that edited other code ran, was caught,
    and guarded N3. The gate now runs the list greg.path reads, and refuses, unrun, every mutant that read would
    not count."""
    files = {"greg/__init__.py": "", "greg/path.py": MINI_PREDICATES, "greg/path.json": json.dumps({"nodes": [
                 {"id": "N3", "predicate": "three"}]}),
             "pkg/__init__.py": "", "pkg/core.py": "def double(x):\n    return 2 * x\n",
             "tests/test_mini.py": "from greg.path import three\nfrom pkg.core import double\n\n\n"
                                   "def test_three():\n    assert three(None) == 'three'\n\n\n"
                                   "def test_double():\n    assert double(1) == 2\n"}
    mutants = [mutant("three weakened", "N3", "three", test="tests/test_mini.py::test_three"),
               ("off its node's predicate", "N3", "pkg/core.py", "    return 2 * x\n", "    return 2 + x\n",
                "tests/test_mini.py::test_double")]
    code, lines = _run_gate(tmp_path, files, mutants, monkeypatch, capsys)
    assert code == 1 and lines[-1] == "1/2 caught", lines
    assert lines[0].startswith("NOT_LIVE off its node's predicate: off target"), lines
    assert [line for line in lines if line.startswith(("CAUGHT", "SURVIVED", "INVALID"))] == ["CAUGHT three weakened"]


def _missing_rehearsals(data: dict) -> list:
    """Rehearsal references that name no test pytest would collect (the gate's own reading of a test id)."""
    return [ref for node in data["nodes"] for ref in node.get("rehearsal", [])
            if not devpath._test_defined(ROOT, ref)]


def test_every_rehearsal_reference_names_a_test_that_exists():
    """Checked here, not in validate(): `greg path` loads the path on installs that ship without tests/."""
    data = devpath.load()
    assert {n["id"] for n in data["nodes"] if n.get("rehearsal")} == PREDICATE_NODES
    assert _missing_rehearsals(data) == []
    bad = copy.deepcopy(data)
    bad["nodes"][1]["rehearsal"] = ["tests/unit/test_no_such_file.py::test_nothing"]
    devpath.validate(bad)                                                          # the load does not look
    assert _missing_rehearsals(bad) == ["tests/unit/test_no_such_file.py::test_nothing"]
    for shape in ("tests/unit/x.py::t", [], ["tests/unit/x.py"]):
        bad["nodes"][1]["rehearsal"] = shape
        with pytest.raises(devpath.PathError, match="rehearsal"):
            devpath.validate(bad)


def test_the_correction_is_placed_on_n1_and_cannot_change_the_destination():
    record = json.loads(PLACEMENTS.read_text())
    devpath.validate_placements(record, devpath.load())
    [placement] = [p for p in record["placements"] if p["id"] == PLACEMENT]
    assert placement["node"] == "N1" and placement["intended_effect_status"] == "active"
    assert placement["classification"] == "SUPERSEDED_IMPLEMENTATION_ASSUMPTION"
    assert set(placement["changed_axes"]) <= {"sequence", "timing", "immediate_priority"}
    assert placement["lineage"][0].startswith(CORRECTION)
    for change, message in ((lambda p: p["changed_axes"].append("final_intended_effect"), "changes the destination"),
                            (lambda p: p.update(classification="GENUINELY_OBSOLETE"), "genuine obsolescence"),
                            (lambda p: p.update(intended_effect_status="superseded"), "explicit founder decision")):
        variant = copy.deepcopy(record)
        change(next(p for p in variant["placements"] if p["id"] == PLACEMENT))
        with pytest.raises(devpath.PathError, match=message):
            devpath.validate_placements(variant)
