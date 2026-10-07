"""A schedule typed in plain controlled words reaches the cortex from GREG's own surfaces.

Directive section 16: connect the seed to the real GREG path and the founder's devices. The
console (phone or Chromebook browser) and `greg cognition mission` both turn the founder's words
into one signed, read-only cognition.solve mission. No model is needed: the controlled language is
read deterministically, and a sentence it cannot read stops the plan instead of being dropped.
"""
import json
from pathlib import Path
import subprocess
import sys

import pytest

pytest.importorskip("z3")
pytest.importorskip("ortools")

from greg import planner  # noqa: E402
from greg.body import Body  # noqa: E402
from greg.capabilities import CapabilityRegistry  # noqa: E402
from tests.greg_fixtures import drop, make_body, signed  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
WORDS = ("Shift: 10 hours. Job J takes 3 hours. Job K takes 2 hours. Job L takes 4 hours. J before L. "
         "One machine; one job at a time. Minimize total completion time. The machine is free all shift.")


def ctx():
    return planner.PlannerContext(read_roots=(), capabilities=CapabilityRegistry().inventory(), repositories={})


def test_console_words_become_one_read_only_cognition_mission():
    proposal = planner.template_route(WORDS, ctx())
    assert proposal["status"] == "PROPOSED" and proposal["origin"] == "template:schedule-in-words"
    spec = proposal["spec"]
    cone = spec["light_cone"]
    assert cone["capabilities"] == ["cognition.solve"] and cone["max_consequence_class"] == "read_only"
    request = spec["strategies"][0]["params"]["problem"]["payload"]["schedule_request"]
    assert "free all shift" not in request["text"] and "founder statement" in request["availability_evidence"]
    assert spec["founder_expression"] == WORDS


def test_without_an_availability_statement_the_plan_says_it_stays_conditional():
    proposal = planner.template_route(WORDS.replace(" The machine is free all shift.", ""), ctx())
    payload = proposal["spec"]["strategies"][0]["params"]["problem"]["payload"]
    assert "availability_evidence" not in payload["schedule_request"]
    assert any("conditional" in n for n in proposal["notes"])


def test_signed_words_close_on_reobserved_evidence(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    spec = planner.template_route(WORDS, ctx())["spec"]
    drop(home, signed(key, body_id, "MISSION", spec))
    with Body(home) as body:
        body.boot()
        assert body.tick()["missions"][0]["state"] == "ACHIEVED"
        receipts = [r.payload["result"]["output"] for r in body.ledger.by_type("receipt")
                    if isinstance(r.payload["result"].get("output"), dict)
                    and r.payload["result"]["output"].get("proof_type") == "cortex_receipt"]
        final = receipts[-1]
        assert final["outcome"]["outcome"] == "ANSWERED_WITHIN_SCOPE" and final["authority_created"] is False
        assert final["output"]["answer"][1]["objective"] == 16       # K, J, L: 2 + 5 + 9 (brute force)
        assert body.journal.replay("mission.appraised")[-1].payload["verdict"] == "VERIFIED"


def test_an_impossible_schedule_never_closes(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    words = "Shift: 5 hours. Job J takes 3 hours. Job K takes 4 hours. Any feasible schedule. " \
            "The machine is free all shift."
    drop(home, signed(key, body_id, "MISSION", planner.template_route(words, ctx())["spec"]))
    with Body(home) as body:
        body.boot()
        assert body.tick()["missions"][0]["state"] != "ACHIEVED"
        assert not body.journal.replay("mission.achieved")


def test_cognition_mission_command_accepts_the_cortex_contract(tmp_path):
    request = {"problem_id": "cli-words", "problem": {"question": "Best schedule", "payload": {
        "schedule_request": {"text": WORDS.replace(" The machine is free all shift.", "")},
        "declared": {"consequence_class": "read_only", "reversibility": "reversible"}}}}
    path = tmp_path / "request.json"
    path.write_text(json.dumps(request))
    out = subprocess.run([sys.executable, "-m", "greg", "--home", str(tmp_path / "body"), "cognition", "mission",
                          "--request", str(path), "--id", "m:cli-words", "--field", "output.answer.1.objective",
                          "--equals", "16", "--print-only"], cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr[-1500:]
    spec = json.loads(out.stdout)
    assert spec["strategies"][0]["capability"] == "cognition.solve"
    assert spec["success_checks"][0]["predicate"] == {"op": "equals", "field": "output.answer.1.objective",
                                                      "value": 16}
    bad = dict(request, problem={"question": "q", "payload": "not a payload"})
    path.write_text(json.dumps(bad))
    out = subprocess.run([sys.executable, "-m", "greg", "--home", str(tmp_path / "body"), "cognition", "mission",
                          "--request", str(path), "--id", "m:bad", "--print-only"], cwd=ROOT, capture_output=True,
                         text=True, timeout=60)
    assert out.returncode != 0
