"""#178's independent verifier asks GREG's appraiser the same question the body asks.

The appraiser re-observes a worker's acceptance and an organ's answer in the postures the original ran in. The body
passes them (worker confinement, confined egress); #178's verifier built its own request without them, so on a host
without the OS envelope (CI) it re-ran a supervised body's acceptance under the fail-closed default, was refused, and
reported NOT_REDERIVED for a mission the body had VERIFIED. The two requests must stay equal.
"""
from __future__ import annotations

import importlib.util
import json

import pytest

from greg.body import Body, Layout
from tests.greg_fixtures import make_body

ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("verify_one_machine", ROOT / "scripts" / "verify_one_machine.py")
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


@pytest.mark.parametrize("confinement", ["required", "supervised"])
@pytest.mark.parametrize("confined_egress", [False, True])
def test_the_verifier_and_the_body_ask_the_appraiser_the_same_question(tmp_path, confinement, confined_egress):
    home, _, _, _ = make_body(tmp_path, worker_confinement=confinement)
    if confined_egress:                                   # as the founder's installer records it
        config = json.loads(Layout(home).config.read_text())
        config["confined_egress"] = True
        Layout(home).config.write_text(json.dumps(config))
    mission = "m:one-machine-staff-om"
    with Body(home) as body:
        expected = body.appraisal_request(mission)
    config = json.loads(Layout(home).config.read_text())
    asked = verifier.appraisal_request(config, Layout(home), home.resolve(), mission, expected["head"])
    assert asked == expected
    assert asked["worker_confinement"] == confinement and asked["confined_egress"] is confined_egress
