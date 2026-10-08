"""Goal Gravity (directive 2026-10-07, section 19): one read-only turn over GREG's existing paths."""
from types import SimpleNamespace

import pytest

from greg import asks, gravity
from greg.cognition.cortex import registry_view
from tests.greg_fixtures import mission, note_check, write_strategy
from tests.unit.test_lawful_leverage import favourable, problem


def situation(p=None, **goal):
    return {"situation_id": "s-1", "goal": {"statement": "settle verified repair claims faster", **goal},
            "source": "test:sensor", "observed_at": "2026-10-08T11:00:00Z", "leverage_problem": p or problem()}


class FakeJournal:
    """Just enough of the canonical journal for read-only projections (no writes are possible)."""

    def __init__(self, events):
        self.events = [SimpleNamespace(type=t, payload=pl) for t, pl in events]

    def replay(self, prefix=""):
        return [e for e in self.events if e.type.startswith("greg." + prefix) or not prefix]


def test_one_turn_reaches_a_founder_decision_with_a_screened_ask_and_gate_proposals():
    report = gravity.step(situation())
    assert report["disposition"] == "FOUNDER_DECISION"
    ask = report["founder_ask"]
    asks.validate({k: v for k, v in ask.items() if k not in ("state", "record_with")})
    assert asks.screen(ask) == [] and ask["state"] == "PREPARED_NOT_RECORDED"
    assert report["gate"]["state"] == "PROPOSED_FOR_GATE" and report["gate"]["proposals"]
    assert all(p["execution_authority"] == "none" for p in report["gate"]["proposals"])
    assert report["authority_created"] is False and report["ledger_writes"] == 0 and report["executes"] is False


def test_backcast_and_metrics_stay_on_the_one_path():
    report = gravity.step(situation())
    assert report["backcast"]["active_node"] == "N1" and report["backcast"]["sbm"]["name"] == "VEPMC"
    assert set(report["metrics_kept_distinct"]) == {"mind", "body"}


def test_the_mind_prices_the_test_through_the_one_cognition_path():
    p = favourable()
    p["mechanism_overrides"] = {"proof.verifiable_receipts": {"cost_usd": 0, "effort_hours": 0}}
    unattached = gravity.step(situation(p))
    assert unattached["leverage"]["selected"] == "proof.verifiable_receipts"
    voi = unattached["mind"]["value_of_information"]
    assert voi["state"] == "CAPABILITY_DEFICIT" and "founder's decision" in voi["meaning"]
    registry = registry_view()
    registry.set_state("cognition.information", "ATTACHED")    # evaluation-only view; the body is unchanged
    attached = gravity.step(situation(p), registry=registry)
    voi = attached["mind"]["value_of_information"]
    assert voi["state"] == "ANSWERED" and voi["method"] == "cognition.information"
    assert voi["agrees_with_foundry"] is True


def test_dormant_goals_wake_only_as_a_founder_proposal(tmp_path):
    spec = mission("m:claims", checks=[note_check("c", tmp_path / "c.txt", "ok")],
                   strategies=[write_strategy("w", "c.txt", "ok", ["c"])], capabilities=["fs.read", "fs.write"])
    journal = FakeJournal([("greg.mission.registered", {"mission_id": "m:claims", "spec": spec,
                                                        "command_digest": "sha256:" + "c" * 64}),
                           ("greg.mission.lifecycle", {"mission_id": "m:claims", "state": "PAUSED"})])
    goals = gravity._goals(journal, "m:claims")
    assert [g["mission_id"] for g in goals["dormant"]] == ["m:claims"] and not goals["active"]
    assert goals["wake"]["automatic_resume"] is False and goals["wake"]["was"] == "dormant"
    assert gravity._goals(journal, "m:unknown")["named_mission_state"] == "UNKNOWN_TO_THIS_LEDGER"
    assert gravity._goals(None, "m:claims")["wake"] is None


def test_the_ask_carries_the_named_mission():
    report = gravity.step(situation(mission_id="m:claims"))
    assert report["founder_ask"]["mission_id"] == "m:claims"


@pytest.mark.parametrize("change,needle", [
    (lambda s: s.__setitem__("extra", 1), "takes only"),
    (lambda s: s.__setitem__("observed_at", "2026-10-09T00:00:00Z"), "after the decision time"),
    (lambda s: s["goal"].__setitem__("statement", " "), "statement"),
    (lambda s: s.__setitem__("observed_at", "2026-10-08T11:00:00"), "timezone"),
])
def test_malformed_situations_are_refused(change, needle):
    s = situation()
    change(s)
    with pytest.raises(gravity.GravityError, match=needle):
        gravity.step(s)


def test_cli_turn_is_read_only_and_creates_no_body(tmp_path, capsys):
    import json
    from greg import cli
    path = tmp_path / "situation.json"
    path.write_text(json.dumps(situation()))
    home = tmp_path / "no-body"
    assert cli.main(["--home", str(home), "gravity", "--situation", str(path)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["disposition"] == "FOUNDER_DECISION" and out["ledger_writes"] == 0
    assert not home.exists()
