"""The whole-machine acceptance harness reports only what tests establish (directive 2026-10-13, sections 33, 35).

These tests hold the harness to its own rule, "do not infer a higher status from a lower one": a declared tier
is attained only by passing every cited node; failures, skips and empty collections leave a requirement
unverified; a requirement whose coverage is 'gap' attains nothing, yet its failing tests are recorded, printed
and fail the run; a requirement covers its whole obligation only when it attained its tier and is declared
covered, and the report separates requirements that cover their whole obligation from those that cover only
part; BODY_VERIFIED needs a cited test in which an argv for a real Body process reaches a process-spawning
call; no test can establish FOUNDER_ACCEPTED or above; missions and contract functions are only as verified as
their least-verified evidence, Mission L's trace links included; each Mission L trace link's tier is computed
from its own proofs and a short link fails the run; and the manifest, the contract and the Mission L trace
must name real files, symbols and test nodes of this tree.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

import acceptance as a

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def manifest():
    return a.load(a.MANIFEST)


@pytest.fixture(scope="module")
def contract():
    return a.load(a.CONTRACT)


def test_the_manifest_and_contract_are_sound_against_this_tree(manifest, contract):
    assert a.problems(manifest, contract) == []
    assert [m["id"] for m in manifest["missions"]] == list("ABCDEFGHIJKL")


def test_every_trace_link_names_owner_code_proof_and_tier(manifest):
    trace = manifest["missions"][11]["trace"]
    assert [link["link"] for link in trace] == list(a.TRACE_LINKS)
    for link in trace:
        assert link["owner"] and link["code"] and link["proof"] and link["tier"] in a.TEST_TIERS
    broken = copy.deepcopy(manifest)
    broken["missions"][11]["trace"][1]["code"] = ["cortex/routing.py::no_such_function"]
    broken["missions"][11]["trace"][2]["proof"] = ["tests/unit/test_greg_ventures.py::test_not_there"]
    found = a.problems(broken)
    assert any("no_such_function is not defined" in p for p in found)
    assert any("test_not_there is not defined" in p for p in found)
    reordered = copy.deepcopy(manifest)
    reordered["missions"][11]["trace"].reverse()
    assert any("must name the links" in p for p in a.problems(reordered))


REQ = {"id": "R1", "obligation": "x", "coverage": "covered", "tier": "BODY_VERIFIED", "implementation": "INTEGRATED",
       "tests": ["tests/unit/test_x.py::test_a", "tests/unit/test_y.py"]}


def outcomes(**kw):
    base = {"tests/unit/test_x.py::test_a[1]": "passed", "tests/unit/test_x.py::test_a[2]": "passed",
            "tests/unit/test_y.py::test_b": "passed", "tests/unit/test_y.py::Test::test_c": "passed"}
    base.update(kw)
    return {k: {"outcome": v, "reason": "why" if v != "passed" else ""} for k, v in base.items() if v}


def test_a_requirement_attains_its_tier_only_when_every_cited_node_passed():
    assert a.requirement_status(REQ, outcomes()) == {"status": "BODY_VERIFIED", "declared_tier": "BODY_VERIFIED",
                                                      "attained": True, "coverage": "covered",
                                                      "whole_obligation": True, "failing": [], "observed": []}
    for bad in ({"tests/unit/test_x.py::test_a[2]": "failed"}, {"tests/unit/test_y.py::Test::test_c": "error"},
                {"tests/unit/test_y.py::test_b": "skipped"}):
        got = a.requirement_status(REQ, outcomes(**bad))
        assert got["status"] == "INTEGRATED" and not got["attained"] and len(got["observed"]) == 1
    empty = a.requirement_status(REQ, outcomes(**{"tests/unit/test_x.py::test_a[1]": None,
                                                  "tests/unit/test_x.py::test_a[2]": None}))
    assert not empty["attained"] and "collected nothing" in empty["observed"][0]
    # A same-prefix function is not a parametrization of the cited one.
    lookalike = {"tests/unit/test_x.py::test_ab": {"outcome": "passed", "reason": ""},
                 "tests/unit/test_y.py::test_b": {"outcome": "passed", "reason": ""}}
    assert not a.requirement_status(REQ, lookalike)["attained"]


def test_without_a_run_nothing_is_verified(manifest, contract):
    rep = a.report(manifest, contract, None, {"head": None})
    assert rep["ran"] is False and rep["summary"]["attained_declared_tier"] == 0
    statuses = [r["status"] for m in rep["missions"].values() for r in m["requirements"].values()]
    assert set(statuses) <= set(a.UNVERIFIED) | {a.BLOCKED}
    assert all(f["evidence_tier"] in set(a.UNVERIFIED) | {a.BLOCKED} for f in rep["contract"])
    trace = rep["missions"]["L"]["trace"]
    assert len(trace) == 9 and all(x["status"] == a.LINK_FLOOR and not x["attained"] for x in trace)


def test_coverage_gap_never_attains_and_cannot_claim_a_tier(manifest):
    gap = {**REQ, "coverage": "gap", "implementation": "IMPLEMENTED"}
    got = a.requirement_status(gap, outcomes())                   # every cited node passed
    assert not got["attained"] and got["status"] == "IMPLEMENTED" and got["declared_tier"] is None
    assert "coverage is 'gap'" in got["observed"][0]
    assert not a.requirement_status({k: v for k, v in REQ.items() if k != "coverage"}, outcomes())["attained"]
    claimed = copy.deepcopy(manifest)
    claimed["missions"][0]["requirements"][0]["coverage"] = "gap"
    assert any("coverage 'gap' cannot claim a tier" in p for p in a.problems(claimed))
    # the gap a mission carries makes the mission no more verified than the gap's implementation status
    mission = {"id": "Z", "title": "t", "gaps": [], "requirements": [{**REQ, "id": "R1"}, {**gap, "id": "R2"}]}
    assert a.mission_status(mission, outcomes())["status"] == "IMPLEMENTED"


def test_the_report_says_how_much_of_each_obligation_the_attained_tiers_cover(capsys):
    reqs = [{**REQ, "id": "R1"}, {**REQ, "id": "R2", "coverage": "partial", "tier": "UNIT_VERIFIED"},
            {**REQ, "id": "R3", "coverage": "gap", "implementation": "IMPLEMENTED"}]
    reqs[2].pop("tier")
    manifest = {"missions": [{"id": "Z", "title": "t", "gaps": [], "requirements": reqs[:2]},
                             {"id": "Y", "title": "u", "gaps": [], "requirements": [reqs[0]]},
                             {"id": "X", "title": "v", "gaps": [], "requirements": [reqs[2]]}]}
    contract = {"functions": [{"id": "F1", "implementation": "IMPLEMENTED", "evidence": ["Y.R1"]},
                              {"id": "F2", "implementation": "IMPLEMENTED", "evidence": ["Z.R1", "Z.R2"]},
                              {"id": "F3", "implementation": "IMPLEMENTED", "evidence": ["Y.R1", "X.R3"]}]}
    rep = a.report(manifest, contract, outcomes(), {"head": "h"})
    s = rep["summary"]
    assert (s["attained_declared_tier"], s["attained_whole_obligation"], s["attained_part_obligation"]) == (3, 2, 1)
    assert s["declared_coverage"] == {"covered": 2, "partial": 1, "gap": 1}
    assert s["missions"] == {"Z": {"status": "UNIT_VERIFIED", "coverage": "partial"},
                             "Y": {"status": "BODY_VERIFIED", "coverage": "covered"},
                             "X": {"status": "IMPLEMENTED", "coverage": "partial"}}
    assert [(f["evidence_tier"], f["coverage"]) for f in rep["contract"]] == [
        ("BODY_VERIFIED", "covered"), ("UNIT_VERIFIED", "partial"), ("IMPLEMENTED", "partial")]
    assert s["contract_functions_whole_obligation"] == 1
    from acceptance.__main__ import _print
    _print(rep)
    out = capsys.readouterr().out
    assert "3/4 requirements reach their declared tier; 2 of them cover the whole obligation, 1 only part." in out
    assert "Mission Z: UNIT_VERIFIED        part of obligation" in out


def test_a_requirement_covers_its_whole_obligation_only_when_it_attained_its_tier(capsys):
    reqs = [{**REQ, "id": "K1"}, {**REQ, "id": "K2"}]               # both declared covered at BODY_VERIFIED
    manifest = {"missions": [{"id": "K", "title": "Founder shutdown", "gaps": [], "requirements": reqs}]}
    contract = {"functions": [{"id": "BODY-SHUTDOWN", "implementation": "IMPLEMENTED", "evidence": ["K.K1", "K.K2"]}]}
    every_node_fails = outcomes(**{k: "failed" for k in outcomes()})
    rep = a.report(manifest, contract, every_node_fails, {"head": "h"})
    k = rep["missions"]["K"]
    assert [(r["coverage"], r["attained"], r["whole_obligation"]) for r in k["requirements"].values()] == [
        ("covered", False, False)] * 2
    assert k["coverage"] == "partial" and rep["contract"][0]["coverage"] == "partial"
    assert rep["summary"]["contract_functions_whole_obligation"] == 0
    assert rep["summary"]["missions"]["K"] == {"status": "INTEGRATED", "coverage": "partial"}
    from acceptance.__main__ import _print
    _print(rep)
    assert "Mission K: INTEGRATED           part of obligation" in capsys.readouterr().out
    assert a.report(manifest, contract, None, {})["missions"]["K"]["coverage"] == "partial"   # nothing ran
    passing = a.report(manifest, contract, outcomes(), {"head": "h"})
    assert passing["missions"]["K"]["coverage"] == "covered" and passing["contract"][0]["coverage"] == "covered"
    assert passing["summary"]["contract_functions_whole_obligation"] == 1


def test_a_failing_test_cited_only_by_a_gap_requirement_is_recorded_printed_and_fails_the_run(manifest, tmp_path,
                                                                                                   capsys):
    j1b = next(r for r in manifest["missions"][9]["requirements"] if r["id"] == "J1b")
    assert j1b["coverage"] == "gap" and "tier" not in j1b
    others = [n for m in manifest["missions"] for r in m["requirements"] if r is not j1b for n in r.get("tests", [])]
    others += [n for link in manifest["missions"][11]["trace"] for n in link["proof"]]
    only_gap = [n for n in j1b["tests"] if not any(a.covers(o, n) for o in others)]
    assert only_gap == ["tests/integration/test_greg_artifact_process.py::"
                        "test_real_process_replacement_recovers_receipt_bound_bytes",
                        "tests/unit/test_goal_gravity.py::test_compounding_makes_next_comparable_mission_cheaper"]
    passed = {n: {"outcome": "passed", "reason": ""} for n in set(others) | set(j1b["tests"])}
    record, out = tmp_path / "outcomes.json", tmp_path / "report.json"
    from acceptance.__main__ import main
    for node in only_gap:
        record.write_text(json.dumps({**passed, node: {"outcome": "failed", "reason": "AssertionError: dearer"}}))
        assert main(["report", "--outcomes", str(record), "--out", str(out)]) == 1, node
        printed = capsys.readouterr().out
        got = json.loads(out.read_text())["missions"]["J"]["requirements"]["J1b"]
        assert got["failing"] == [node] and got["declared_tier"] is None and not got["attained"]
        assert f"{node}: failed: AssertionError: dearer" in got["observed"]
        assert f"J1b: {node}: failed: AssertionError: dearer" in printed
        assert "[cited tests failing, no tier declared: J1b]" in printed
        assert "1 requirements cite a test that failed, errored or collected nothing" in printed
    # an error and an empty collection count too; a skip is recorded and printed but fails nothing
    record.write_text(json.dumps({**passed, node: {"outcome": "error", "reason": "fixture"}}))
    assert main(["report", "--outcomes", str(record)]) == 1
    record.write_text(json.dumps({k: v for k, v in passed.items() if k != node}))
    assert main(["report", "--outcomes", str(record)]) == 1
    capsys.readouterr()
    record.write_text(json.dumps({**passed, node: {"outcome": "skipped", "reason": "no toolchain"}}))
    assert main(["report", "--outcomes", str(record)]) == 0
    assert f"J1b: {node}: skipped: no toolchain" in capsys.readouterr().out


def test_body_verified_needs_a_cited_node_that_drives_a_real_body_process(manifest):
    # Mission G's owned-company loop runs an in-process Body with a test clock: SANDBOX at most.
    claimed = copy.deepcopy(manifest)
    req = next(r for r in claimed["missions"][6]["requirements"] if r["id"] == "R5")
    req["tier"] = "BODY_VERIFIED"
    assert any(p.startswith("G.R5: BODY_VERIFIED needs a cited node that drives a real Body process")
               for p in a.problems(claimed))
    # A link at BODY tier is held to the same rule.
    link = copy.deepcopy(manifest)
    link["missions"][11]["trace"][0]["tier"] = "BODY_VERIFIED"
    assert any(p.startswith("L.trace Goal: BODY_VERIFIED needs") for p in a.problems(link))
    # Unregistering the only real-process file a requirement cites leaves it in-process.
    unregistered = copy.deepcopy(manifest)
    unregistered["body_process_tests"] = [e for e in unregistered["body_process_tests"]
                                          if e["file"] != "tests/integration/test_greg_goal_gravity_process.py"]
    assert any(p.startswith("F.R1: BODY_VERIFIED needs") for p in a.problems(unregistered))
    # A registered file must really start what it claims to start.
    false = copy.deepcopy(manifest)
    false["body_process_tests"].append({"file": "tests/unit/test_greg_platform.py", "starts": "supervisord"})
    assert any("test_greg_platform.py: no test in it statically starts a supervisord Body process" in p
               for p in a.problems(false))
    schema = json.loads((ROOT / "acceptance" / "missions.schema.json").read_text())
    assert schema["$defs"]["body_process_test"]["properties"]["starts"]["enum"] == list(a.PROCESS_KINDS)


@pytest.mark.parametrize("node, kinds", [
    ("tests/integration/test_greg_body_supervised.py::test_body_survives_hard_kill_waits_for_founder_and_stops_on_command",
     {"supervisord"}),
    ("tests/integration/test_greg_cognition_process.py::test_cli_composition_survives_sigkill_without_duplicate_computation[mission.action]",
     {"greg run"}),                                                        # through the cli(home, 'run', ...) helper
    ("tests/integration/test_greg_body_midflight_kill.py", {"Body.run driver"}),
    ("tests/integration/test_greg_genesis_kill_process.py", {"Body.run driver"}),   # Body(home, builder=...).run(
    ("tests/unit/test_greg_presence.py::test_a_real_sigkilled_body_process_leaves_an_absence_bounded_by_its_last_heartbeat",
     {"greg run"}),
    # in-process main loops, supervisor configs written but never launched, and `greg sop run` are not processes
    ("tests/unit/test_greg_presence.py::test_the_running_loop_records_host_sleep_from_clock_divergence", set()),
    ("tests/unit/test_greg_platform.py::test_supervisor_configs_restart_crashes_but_respect_stop", set()),
    ("tests/unit/test_greg_sop_compounding.py::test_the_cli_shows_ratifies_and_runs_a_procedure", set()),
    ("tests/unit/test_greg_owned_company.py", set()),
])
def test_real_body_processes_are_recognised_statically(node, kinds):
    assert a.node_process_kinds(node) == kinds


PROBE = """
import asyncio
import shutil
import subprocess
import sys
from unittest import mock

import pytest

from greg import service
from greg.body import Body

DRIVER = '''
import sys
from greg.body import Body
sys.exit(Body(sys.argv[1]).run(tick_seconds=0.1))
'''
NESTED_DRIVER = '''
import sys
from greg.body import Body


class Agent:
    max_budget_usd = 0.4


sys.exit(Body(sys.argv[1], builder=Agent(), clock=None).run(tick_seconds=float(sys.argv[2])))
'''
MENTION_ONLY = '''
# Body(home).run(tick_seconds=0.1) is what greg run runs; this script only prints that, and runs something else.
class Runner:
    def run(self, **kwargs):
        return 0


print("Body(home).run(tick_seconds=0.1)", Runner().run(tick_seconds=0.1))
'''
SUPERVISORD = shutil.which("supervisord")


def greg_argv(home, *args):
    return [sys.executable, "-m", "greg", "--home", str(home), *args]


def start(home):
    return subprocess.Popen(greg_argv(home, "run", "--tick-seconds", "0.1"))


def never_called(home):
    subprocess.Popen(greg_argv(home, "run"))


@pytest.fixture
def body(tmp_path):
    child = subprocess.Popen([sys.executable, "-m", "greg", "--home", str(tmp_path), "run"])
    yield child
    child.kill()


@pytest.fixture
def argv(tmp_path):
    return [sys.executable, "-m", "greg", "--home", str(tmp_path), "run"]


def supervisor_conf(tmp_path, home):
    conf = tmp_path / "supervisord.conf"
    conf.write_text("[supervisord]\\nnodaemon=true\\n" + service.supervisord_program(home))
    return conf


def test_popen_argv(tmp_path):
    subprocess.Popen([sys.executable, "-m", "greg", "--home", str(tmp_path), "run", "--tick-seconds", "0.1"])


def test_argv_variable_then_run(tmp_path):
    cmd = [sys.executable, "-m", "greg", "--home", str(tmp_path), "run"]
    subprocess.run(cmd + ["--max-ticks", "1"], check=True)


def test_helper(tmp_path):
    start(tmp_path).wait()


def test_fixture(body):
    assert body.poll() is None


def test_fixture_argv_spawned(argv):
    subprocess.check_call(argv)


def test_nested_helper_called(tmp_path):
    def launch():
        return subprocess.Popen(greg_argv(tmp_path, "run"))
    launch()


async def test_asyncio_exec(tmp_path):
    proc = await asyncio.create_subprocess_exec(sys.executable, "-m", "greg", "--home", str(tmp_path), "run")
    await proc.wait()


def test_driver_file_spawned(tmp_path):
    driver = tmp_path / "driver.py"
    driver.write_text(DRIVER)
    subprocess.Popen([sys.executable, str(driver), str(tmp_path)])


def test_driver_string_spawned(tmp_path):
    subprocess.run([sys.executable, "-c", DRIVER, str(tmp_path)], check=True)


def test_nested_driver_file_spawned(tmp_path):
    driver = tmp_path / "driver.py"
    driver.write_text(NESTED_DRIVER)
    subprocess.Popen([sys.executable, str(driver), str(tmp_path), "0.1"])


def test_nested_driver_string_spawned(tmp_path):
    subprocess.run([sys.executable, "-c", NESTED_DRIVER, str(tmp_path), "0.1"], check=True)


def test_supervisord_launched(tmp_path):
    conf = supervisor_conf(tmp_path, tmp_path / "body")
    subprocess.Popen([SUPERVISORD, "-c", str(conf)])


def test_argv_built_never_spawned(tmp_path):
    cmd = [sys.executable, "-m", "greg", "--home", str(tmp_path), "run"]
    print(cmd)
    subprocess.run(["git", "status"])


def test_in_process_body_run(tmp_path):
    driver = tmp_path / "driver.py"
    driver.write_text(DRIVER)
    assert Body(tmp_path).run(tick_seconds=0.01, max_ticks=2) == 0
    subprocess.run(["git", "status"])


def test_an_argv_handed_to_a_run_that_spawns_nothing(tmp_path):
    Body(tmp_path).run([sys.executable, "-m", "greg", "--home", str(tmp_path), "run"])


def test_supervisord_config_written_not_launched(tmp_path):
    conf = supervisor_conf(tmp_path, tmp_path / "body")
    launch = [SUPERVISORD, "-c", str(conf)]
    subprocess.run(["supervisorctl", "-c", str(conf), "status"])


def test_supervisord_launched_without_the_program(tmp_path):
    service.supervisord_program(tmp_path)
    conf = tmp_path / "supervisord.conf"
    conf.write_text("[supervisord]\\nnodaemon=true\\n")
    subprocess.Popen(["supervisord", "-c", str(conf)])


def test_driver_string_never_spawned(tmp_path):
    driver = tmp_path / "driver.py"
    driver.write_text(DRIVER)
    subprocess.run([sys.executable, "-m", "greg", "--home", str(tmp_path), "status"])


def test_in_process_nested_body_run(tmp_path):
    class Agent:
        max_budget_usd = 0.4
    assert Body(tmp_path, builder=Agent(), clock=None).run(tick_seconds=float("0.01"), max_ticks=2) == 0
    subprocess.run(["git", "status"])


def test_nested_driver_file_read_not_run(tmp_path):
    driver = tmp_path / "driver.py"
    driver.write_text(NESTED_DRIVER)
    subprocess.run(["cat", str(driver)])


def test_a_script_that_only_mentions_body_run(tmp_path):
    script = tmp_path / "mention.py"
    script.write_text(MENTION_ONLY)
    subprocess.Popen([sys.executable, str(script), str(tmp_path)])
    subprocess.run([sys.executable, "-c", MENTION_ONLY])


def test_driver_file_read_not_run(tmp_path):
    driver = tmp_path / "driver.py"
    driver.write_text(DRIVER)
    subprocess.run(["cat", str(driver)])


def test_another_subcommand(tmp_path):
    subprocess.run(greg_argv(tmp_path, "sop", "run", "weekly"))


def test_launchers_defined_never_called(tmp_path):
    def launch():
        subprocess.Popen(greg_argv(tmp_path, "run"))
    later = lambda: start(tmp_path)


def test_a_constant_false_branch(tmp_path):
    if False:
        start(tmp_path)


def test_subprocess_patched(tmp_path, monkeypatch):
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: None)
    start(tmp_path)


@mock.patch("subprocess.Popen")
def test_subprocess_patched_by_decorator(popen, tmp_path):
    start(tmp_path)


def test_an_unknown_starred_argv(tmp_path, extra):
    subprocess.run([sys.executable, "-m", "greg", "--home", str(tmp_path), *extra, "run"])
"""


@pytest.fixture(scope="module")
def probe(tmp_path_factory):
    root = tmp_path_factory.mktemp("probe")
    (root / "tests").mkdir()
    (root / "tests" / "test_probe.py").write_text(PROBE)
    return root


@pytest.mark.parametrize("test, kinds", [
    # recognised: an argv that starts a real Body process reaches a process-spawning call
    ("test_popen_argv", {"greg run"}),
    ("test_argv_variable_then_run", {"greg run"}),
    ("test_helper", {"greg run"}),                          # a same-module helper, called with 'run'
    ("test_fixture", {"greg run"}),                         # a same-module fixture the test requests
    ("test_fixture_argv_spawned", {"greg run"}),            # a fixture's argv, spawned by the test
    ("test_nested_helper_called", {"greg run"}),
    ("test_asyncio_exec", {"greg run"}),
    ("test_driver_file_spawned", {"Body.run driver"}),      # the driver string, written to a file python runs
    ("test_driver_string_spawned", {"Body.run driver"}),    # the driver string, passed to python -c
    ("test_nested_driver_file_spawned", {"Body.run driver"}),   # Body(..., builder=Agent()).run(...): nested calls
    ("test_nested_driver_string_spawned", {"Body.run driver"}),
    ("test_supervisord_launched", {"supervisord"}),         # its -c file holds service.supervisord_program
    # not recognised
    ("test_argv_built_never_spawned", set()),
    ("test_in_process_body_run", set()),
    ("test_an_argv_handed_to_a_run_that_spawns_nothing", set()),
    ("test_supervisord_config_written_not_launched", set()),
    ("test_supervisord_launched_without_the_program", set()),
    ("test_driver_string_never_spawned", set()),
    ("test_driver_file_read_not_run", set()),
    ("test_in_process_nested_body_run", set()),              # an in-process Body.run never counts, nested or not
    ("test_nested_driver_file_read_not_run", set()),
    ("test_a_script_that_only_mentions_body_run", set()),    # in a comment or a string, Body.run is not called
    ("test_another_subcommand", set()),
    ("test_launchers_defined_never_called", set()),
    ("test_a_constant_false_branch", set()),
    ("test_subprocess_patched", set()),
    ("test_subprocess_patched_by_decorator", set()),
    ("test_an_unknown_starred_argv", set()),
])
def test_only_an_argv_that_reaches_a_spawning_call_counts_as_a_real_process(probe, test, kinds):
    assert a.node_process_kinds(f"tests/test_probe.py::{test}", probe) == kinds


def test_a_cited_node_counts_only_when_its_own_test_spawns_the_process(probe):
    registry = {"tests/test_probe.py": "greg run"}
    nodes = ["tests/test_probe.py::test_helper", "tests/test_probe.py::test_in_process_body_run",
             "tests/test_probe.py::test_argv_built_never_spawned"]
    assert a.real_process_nodes(nodes, registry, probe) == ["tests/test_probe.py::test_helper"]
    assert a.node_process_kinds("tests/test_probe.py", probe) == {"greg run", "Body.run driver", "supervisord"}


def test_trace_link_tiers_are_computed_from_their_proofs_and_a_short_link_fails_the_run(manifest, tmp_path, capsys):
    nodes = {n for m in manifest["missions"] for r in m["requirements"] for n in r.get("tests", [])}
    nodes |= {n for link in manifest["missions"][11]["trace"] for n in link["proof"]}
    passed = {n: {"outcome": "passed", "reason": ""} for n in nodes}
    record = tmp_path / "outcomes.json"
    record.write_text(json.dumps(passed))
    from acceptance.__main__ import main
    assert main(["report", "--outcomes", str(record)]) == 0
    capsys.readouterr()
    # A proof cited only by the trace fails: its link falls to the floor, is printed short, and the run fails.
    failed = {**passed, "tests/unit/test_provenance.py::test_append_and_verify_chain":
              {"outcome": "failed", "reason": "AssertionError"}}
    record.write_text(json.dumps(failed))
    out = tmp_path / "report.json"
    assert main(["report", "--outcomes", str(record), "--out", str(out)]) == 1
    printed = capsys.readouterr().out
    rep = json.loads(out.read_text())
    evidence = next(x for x in rep["missions"]["L"]["trace"] if x["link"] == "Evidence")
    assert evidence["status"] == a.LINK_FLOOR and not evidence["attained"]
    assert "test_append_and_verify_chain: failed" in evidence["observed"][0]
    assert rep["summary"]["trace_links_attained"] == 8 and rep["summary"]["attained_declared_tier"] == sum(
        1 for m in manifest["missions"] for r in m["requirements"] if r.get("tier") and r["coverage"] != "gap")
    assert "short of declared tier: Evidence" in printed and "8/9 trace links" in printed


def test_a_short_trace_link_lowers_mission_l_and_every_contract_function_citing_it(manifest, contract):
    nodes = {n for m in manifest["missions"] for r in m["requirements"] for n in r.get("tests", [])}
    nodes |= {n for link in manifest["missions"][11]["trace"] for n in link["proof"]}
    passed = {n: {"outcome": "passed", "reason": ""} for n in nodes}
    rep = a.report(manifest, contract, passed, {})
    L = rep["missions"]["L"]
    assert L["status"] == a.lowest([r["status"] for r in L["requirements"].values()]
                                   + [x["status"] for x in L["trace"]])
    # A proof only the trace cites fails: Mission L, LOOP-COMPREHENSION and BODY-INTERFACE (which cites L1) fall
    # to the link floor and cover only part of their obligation, though every requirement still attains.
    failed = {**passed, "tests/unit/test_provenance.py::test_append_and_verify_chain":
              {"outcome": "failed", "reason": "AssertionError"}}
    rep = a.report(manifest, contract, failed, {})
    L = rep["missions"]["L"]
    assert all(r["attained"] for r in L["requirements"].values())
    assert (L["status"], L["coverage"]) == (a.LINK_FLOOR, "partial")
    assert rep["summary"]["missions"]["L"] == {"status": a.LINK_FLOOR, "coverage": "partial"}
    functions = {f["id"]: f for f in rep["contract"]}
    for fid in ("LOOP-COMPREHENSION", "BODY-INTERFACE"):
        assert (functions[fid]["evidence_tier"], functions[fid]["coverage"]) == (a.LINK_FLOOR, "partial"), fid
    assert functions["BODY-SHUTDOWN"]["evidence_tier"] != a.LINK_FLOOR     # it cites no Mission L requirement
    # The rule on a small mission whose one requirement is covered at BODY_VERIFIED: its link, not R1, sets the
    # mission's tier, and a short link leaves the mission and the function citing it partial.
    link = {"link": "Goal", "owner": "o", "tier": "UNIT_VERIFIED", "code": [],
            "proof": ["tests/unit/test_z.py::test_c"]}
    mission = {"id": "Z", "title": "t", "gaps": [], "requirements": [{**REQ, "id": "R1"}], "trace": [link]}
    fn = {"id": "F", "implementation": "IMPLEMENTED", "evidence": ["Z.R1"]}
    for proof, tier, coverage in (("passed", "UNIT_VERIFIED", "covered"), ("failed", a.LINK_FLOOR, "partial")):
        got = a.mission_status(mission, outcomes(**{"tests/unit/test_z.py::test_c": proof}))
        assert got["requirements"]["R1"]["whole_obligation"] and (got["status"], got["coverage"]) == (tier, coverage)
        function = a.contract_status(fn, {"Z": got})
        assert (function["evidence_tier"], function["coverage"]) == (tier, coverage), proof


def test_no_status_beyond_tests_can_be_declared_or_claimed_without_tests(manifest):
    for tier in a.BEYOND_TESTS:
        claimed = copy.deepcopy(manifest)
        claimed["missions"][0]["requirements"][0]["tier"] = tier
        assert any("declares a tier tests can establish" in p for p in a.problems(claimed)), tier
    untested = copy.deepcopy(manifest)
    req = untested["missions"][0]["requirements"][0]
    req.pop("tests"), req.pop("tier"), req.pop("implementation")
    req["status"] = "SANDBOX_VERIFIED"
    assert any("an untested requirement cannot claim SANDBOX_VERIFIED" in p for p in a.problems(untested))
    req["status"] = a.BLOCKED
    assert any("needs its reason" in p for p in a.problems(untested))


def test_a_mission_or_function_is_only_as_verified_as_its_least_verified_evidence():
    mission = {"id": "Z", "title": "t", "gaps": [], "requirements": [
        {**REQ, "id": "R1"}, {**REQ, "id": "R2", "tier": "UNIT_VERIFIED"}]}
    assert a.mission_status(mission, outcomes())["status"] == "UNIT_VERIFIED"
    blocked = {**mission, "requirements": mission["requirements"] + [
        {"id": "R3", "obligation": "x", "coverage": "gap", "status": a.BLOCKED, "blocked_reason": "founder"}]}
    assert a.mission_status(blocked, outcomes())["status"] == a.BLOCKED
    missions = {"Z": a.mission_status(mission, outcomes())}
    fn = {"id": "F", "implementation": "IMPLEMENTED", "evidence": ["Z.R1", "Z.R2"]}
    assert a.contract_status(fn, missions)["evidence_tier"] == "UNIT_VERIFIED"
    assert a.contract_status({**fn, "evidence": ["Z.R1"]}, missions)["evidence_tier"] == "BODY_VERIFIED"
    assert a.contract_status({**fn, "implementation": "DESIGNED"}, missions)["evidence_tier"] == "DESIGNED"


def test_cited_nodes_resolve_statically_and_bogus_ones_do_not():
    assert a.node_problem("tests/unit/test_acceptance_harness.py::test_cited_nodes_resolve_statically_and_bogus_ones_do_not") is None
    assert a.node_problem("tests/unit/test_acceptance_harness.py") is None
    assert a.node_problem("tests/unit/test_acceptance_harness.py::nope")
    assert a.node_problem("tests/unit/no_such_file.py::test_x")
    assert a.node_problem("greg/missions.py")                       # not a test file
    assert a.minimal_nodes(["tests/a.py", "tests/a.py::t", "tests/b.py::t[1]", "tests/b.py::t"]) == \
        ["tests/a.py", "tests/b.py::t"]


def test_the_plugin_records_passes_failures_errors_and_skips_truthfully(tmp_path):
    (tmp_path / "test_probe.py").write_text(
        "import pytest\n"
        "def test_ok(): pass\n"
        "def test_bad(): assert 1 == 2\n"
        "def test_skip(): pytest.skip('no toolchain')\n"
        "@pytest.fixture\n"
        "def broken(): raise RuntimeError('setup')\n"
        "def test_setup_error(broken): pass\n"
        "@pytest.fixture\n"
        "def leaky():\n    yield\n    raise RuntimeError('teardown')\n"
        "def test_teardown_error(leaky): pass\n"
        "@pytest.mark.parametrize('x', [1, 2])\n"
        "def test_param(x): assert x == 1\n")
    target = tmp_path / "outcomes.json"
    env = {**os.environ, "ACCEPTANCE_OUTCOMES": str(target), "PYTHONPATH": str(ROOT)}
    subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "acceptance._plugin", "-p", "no:cacheprovider",
                    "test_probe.py"], cwd=tmp_path, env=env, capture_output=True, timeout=120)
    got = {k: v["outcome"] for k, v in json.loads(target.read_text()).items()}
    assert got == {"test_probe.py::test_ok": "passed", "test_probe.py::test_bad": "failed",
                   "test_probe.py::test_skip": "skipped", "test_probe.py::test_setup_error": "error",
                   "test_probe.py::test_teardown_error": "error", "test_probe.py::test_param[1]": "passed",
                   "test_probe.py::test_param[2]": "failed"}
    reasons = json.loads(target.read_text())
    assert "no toolchain" in reasons["test_probe.py::test_skip"]["reason"]


def test_the_cli_check_is_static_and_sound():
    proc = subprocess.run([sys.executable, "-m", "acceptance", "check"], cwd=ROOT, capture_output=True, text=True,
                          timeout=120)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "sound: 12 missions" in proc.stdout


def test_the_contract_declares_the_machine_incomplete_and_claims_nothing_beyond_tests(contract):
    assert "NOT declared complete" in contract["boundary"]
    unmet = [c for c in contract["current_machine_conditions"] if c["met"] != "yes"]
    assert unmet, "the developmental machine may be declared complete only when every condition is met"
    for fn in contract["functions"]:
        assert fn["implementation"] not in a.BEYOND_TESTS


AUDITED_PARTIAL = ("A.R1", "A.R7", "B.B3", "B.B4", "C.R1", "C.R3", "C.R8", "F.R5", "G.R3", "G.R5", "G.R6", "H.H.5",
                   "I.I1", "I.I2", "I.I6", "I.I7", "I.I8", "K.K1", "K.K2", "K.K3", "K.K4", "K.K6")


def test_requirements_whose_own_notes_show_a_clause_below_their_tier_are_partial_and_name_it(manifest):
    reqs = {f"{m['id']}.{r['id']}": r for m in manifest["missions"] for r in m["requirements"]}
    for ref in AUDITED_PARTIAL:
        assert reqs[ref]["coverage"] == "partial", ref
        assert reqs[ref]["notes"].startswith("Partial (coverage audit 2026-10-15): "), ref
    for ref, r in reqs.items():                    # a covered requirement's notes name no unshown clause
        assert not (r["coverage"] == "covered" and "Partial (coverage audit" in r.get("notes", "")), ref
