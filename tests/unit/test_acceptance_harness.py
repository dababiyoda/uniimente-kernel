"""The whole-machine acceptance harness reports only what tests establish (directive 2026-10-13, sections 33, 35).

These tests hold the harness to its own rule, "do not infer a higher status from a lower one": a declared tier
is attained only by passing every cited node; failures, skips and empty collections leave a requirement
unverified; a requirement whose coverage is 'gap' attains nothing, and the report separates requirements that
cover their whole obligation from those that cover only part; BODY_VERIFIED needs a cited test that drives a
real Body process; no test can establish FOUNDER_ACCEPTED or above; missions and contract functions are only as
verified as their least-verified evidence; each Mission L trace link's tier is computed from its own proofs and
a short link fails the run; and the manifest, the contract and the Mission L trace must name real files,
symbols and test nodes of this tree.
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
                                                      "whole_obligation": True, "observed": []}
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
    assert s["coverage"] == {"covered": 2, "partial": 1, "gap": 1}
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
