"""COMBINED MACHINE: one constructed answer, read by WealthMachine, then settled by its world outcome.

Two children of #196 meet here: #210 (a construction's pending world outcome is offered once per signed claim and a
signed scalar REALIZATION settles it once) and #212 (WealthMachine reads the staffing figures the Mind sends it). One
founder-signed mission asks the fifteen-step staffing question. The Competency Compiler finds a deficit, Capability
Genesis constructs ``assignment.staffing`` over an acquired max-flow engine, and the organs assess the certified answer
(8 of 9 staffed) over the signed bridge. Asserted, on one body's ledger:

1. the answer's world outcome is pending exactly once, as the claim settlement will count;
2. one founder-signed ``greg realize RECEIPT --objective-value 7`` (one unit short of the promise, beyond the declared
   tolerance) settles it once: the construction's competence on this geometry goes from (1, 1) to (1, 0), the certificate
   verdict is kept beside the world verdict, and nothing is left pending;
3. WealthMachine's reading of the same answer is unchanged by the outcome: the realization re-runs no organ, and the
   assessment the Kernel retained keeps its staffing reading and first validation step byte for byte.

Gated as the fifteen-step mission: the four UNIIMENTE_* variables name the organ checkouts (skipped with the reason,
failed under UNIIMENTE_REQUIRE_ORGANS=1, which CI job 8 sets). The realized value is synthetic, not a founder-reported
or external outcome; a per-test Ed25519 key stands in for the founder; nothing counts toward VEPMC.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("networkx")
pytest.importorskip("scipy")

from tests.integration.test_one_mission_fifteen_steps import SEED_TEMPLATE, best_staffing  # noqa: E402

PROBLEM_ID = "combined-staff"


def mission(organs: dict) -> dict:
    """The compiled staffing question, plus the fifteen-step mission's organ assessment of its certified answer."""
    from greg.organs import TARGET
    from greg.templates import compiled_question
    from tests.integration.test_greg_mind_constructs_capability import STAFFING
    spec = compiled_question(problem_id=PROBLEM_ID, data=STAFFING, allow_construction=True,
                             objective="staff the docks and the line")
    keys = ("daleobanks_root", "daleobanks_python", "wealthmachine_root", "wealthmachine_python")
    spec["success_checks"].append(
        {"check_id": "organs-assessed", "description": "both organ messages on the answer verified and reproduced",
         "sensor": {"capability": "organ.status", "target": TARGET, "params": {}},
         "predicate": {"op": "equals", "field": "verdict", "value": "REPRODUCED"}})
    spec["strategies"].append(
        {"action_id": "organs", "capability": "organ.exchange", "target": TARGET,
         "params": {k: str(organs[k]) for k in keys},
         "bind": [{"param": "seed", "from": {"check_id": "answered", "field": "result"}, "type": "object",
                   "render": "json", "template": SEED_TEMPLATE, "max_bytes": 2000}],
         "requires": ["answered"], "advances": ["organs-assessed"],
         "rationale": "the organs assess the Mind's certified answer through their own code over the signed bridge"})
    cone = spec["light_cone"]
    cone["capabilities"] += ["organ.exchange", "organ.status"]
    cone["targets"] += [TARGET]
    cone["max_consequence_class"] = "internal_write"
    return spec


def wealthmachine_assessments(journal) -> list[dict]:
    """WealthMachine's assessments as the Kernel verified and retained them (untrusted content)."""
    seen = {e.payload["content_sha256"] for e in journal.replay("organ.observed")
            if e.payload["organ"] == "wealthmachine"}
    return [e.payload for e in journal.replay("external.ingested")
            if e.payload.get("source") == "organ:wealthmachine" and e.payload["content_sha256"] in seen]


def test_one_constructed_answer_is_read_by_wealthmachine_and_settled_once_by_its_world_outcome(tmp_path, capsys):
    from greg import cli
    from greg.body import Body
    from greg.cognition import settlement
    from tests.greg_fixtures import Clock, drop, make_body, signed
    from tests.integration.test_greg_mind_constructs_capability import STAFFING
    from tests.unit.test_greg_organs import live_organs, organ_roots

    organs = live_organs()
    home, key, body_id, _ = make_body(tmp_path, read_roots=list(organ_roots(organs)))
    clock = Clock()
    spec = mission(organs)
    mid = spec["mission_id"]
    with Body(home, clock=clock) as body:
        body.boot()
        drop(home, signed(key, body_id, "MISSION", spec))
        for _ in range(12):
            body.tick()
            clock.advance(31)
            if body.engine.book.missions[mid].status == "ACHIEVED":
                break
        assert body.engine.book.missions[mid].status == "ACHIEVED", body.engine.book.missions[mid].status
        journal = body.journal

        # The organs read the constructed answer: 8 of 9 staffed, the shortage leads WealthMachine's plan.
        constructed = settlement._constructed_versions(journal)
        [method] = constructed
        assert method.startswith("composed.assignment.staffing")
        [before] = wealthmachine_assessments(journal)
        assessment = json.loads(before["content"])
        [reading] = [r for r in assessment["reasons"] if r.startswith("staffing evidence[")]
        assert best_staffing(STAFFING) == 8 and "staffed=8, total_demand=9, shortage=1" in reading
        assert assessment["validation_plan"][0].startswith("Validate the reported staffing shortage of 1 units")
        assert assessment["go_no_go"] != "go" and assessment["requires_human_approval"] is True
        organ_runs = len(list(journal.replay("organ.observed")))

        # 1. The answer's world outcome is pending exactly once, however often the mission observed it.
        rows = [r for r in settlement.awaiting_realization(journal) if r.get("kind") == "objective"]
        assert len(rows) == 1, rows
        [row] = rows
        assert (row["method"], row["objective"], row["promised"]) == (method, "staffed", 8)
        [(count, correct)] = [(r["count"], r["correct"]) for (m, _, _), r in settlement.competence(journal).items()
                              if m == method]
        assert (count, correct) == (1, 1), "before the outcome, only the certificate has settled the answer"

        # 2. One founder-signed scalar report settles it once.
        capsys.readouterr()
        assert cli.main(["--home", str(home), "realize", row["receipt"], "--objective-value", "7",
                         "--key", str(tmp_path / "founder.pem"), "--no-passphrase"]) == 0
        capsys.readouterr()
        for _ in range(3):
            body.tick()
            clock.advance(31)
        [fact] = list(journal.replay("cognition.realization"))
        assert fact.payload["kind"] == "objective" and fact.payload["realized"] == 7.0
        assert fact.payload["met"] is False and fact.payload["authority_created"] is False
        assert fact.payload["command_digest"], "the realization did not arrive as a founder-signed command"
        assert [r for r in settlement.awaiting_realization(journal) if r.get("kind") == "objective"] == []
        [outcome] = [o for o in settlement.measured_outcomes(journal) if o["method"] == method]
        assert outcome["correct"] is False and outcome["certificate_correct"] is True
        assert outcome["world"]["promised"] == 8 and outcome["world"]["realized"] == 7.0
        [(count, correct)] = [(r["count"], r["correct"]) for (m, _, _), r in settlement.competence(journal).items()
                              if m == method]
        assert (count, correct) == (1, 0), "one claim settles once, as wrong in the world"

        # 3. WealthMachine's reading of the same answer is unchanged by the outcome.
        assert len(list(journal.replay("organ.observed"))) == organ_runs, "the realization re-ran an organ"
        [after] = wealthmachine_assessments(journal)
        assert after["content_sha256"] == before["content_sha256"] and after["content"] == before["content"]
