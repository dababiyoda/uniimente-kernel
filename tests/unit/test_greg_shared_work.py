"""Node N6: Alfonso, GREG and a named person complete one piece of work together.

GREG writes the handoff (including the person's right to decline) before anyone is asked anything.
The person's agreement and deliverable, and Alfonso's review, each close one HUMAN_WORK ask only when
observed in the case folder; GREG records the outcome and takes no external action. A refusal is
honored as legitimate: GREG withdraws its ask, never asks that step again and leaves the next move to
Alfonso. That the person is real and the relationship lawful is attested by his acceptance.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from greg import path as devpath
from greg.body import Body
from greg.missions import MissionError, validate_mission
from greg.templates import shared_work
from greg.metrics import NOT_FOUNDER_TIER
from tests.greg_fixtures import TEST_PASSPHRASE, Clock, attest_founder_tier, drop, make_body, signed, workspace

ROOT = Path(__file__).resolve().parents[2]
REF = "WORK-DESIGN-THE-GREG-LOGO"


def work_spec(home, **overrides) -> dict:
    fields = {"task": "Design the GREG logo", "person": "Dana Reyes", "relationship": "contract",
              "function": "human.design_logo", "deliverable": "logo.png",
              "acceptance": "a square PNG, 1024 px, two colors", "workspace_root": Path(home).resolve() / "workspace",
              **overrides}
    return validate_mission(shared_work(**fields))


@pytest.mark.parametrize("override, message", [
    ({"function": "human.founder_review"}, "the person's work"),
    ({"function": "fs.write"}, "the person's work"),
    ({"relationship": "favor"}, "relationship"),
    ({"person": "  "}, "person is required"),
    ({"acceptance": ""}, "acceptance is required"),
    ({"deliverable": "../logo.png"}, "plain file name"),
    ({"deliverable": "declined.txt"}, "plain file name"),
    ({"task": "!!"}, "three letters"),
])
def test_shared_work_cannot_be_signed_without_person_relationship_and_terms(tmp_path, override, message):
    with pytest.raises(ValueError, match=message):
        work_spec(tmp_path, **override)


def test_only_a_persons_step_may_be_declined(tmp_path):
    spec = work_spec(tmp_path)
    spec["strategies"][0]["declined_if"] = spec["strategies"][1]["declined_if"]   # GREG's own handoff write
    with pytest.raises(MissionError, match="declined_if applies only to a person's step"):
        validate_mission(spec)


def asks(body, mid, kind="HUMAN_WORK"):
    return [e.payload for e in body.journal.replay("decision.requested")
            if e.payload["mission_id"] == mid and e.payload["kind"] == kind]


def tick(body, clock, ticks=3, advance=4000):
    clock.advance(advance)
    for _ in range(ticks):
        body.tick()
        clock.advance(1)


def start(tmp_path, monkeypatch=None, *, founder_tier=False):
    passphrase = TEST_PASSPHRASE if founder_tier else None
    home, key, body_id, _ = make_body(tmp_path, passphrase=passphrase)
    clock = Clock()
    body = Body(home, clock=clock).open()
    body.boot()
    drop(home, signed(key, body_id, "BODY_DESIGNATE", {"purpose": "first_founder_body"}, now=clock.now))
    if founder_tier:                                          # as `greg founder attest` does, before the work is signed
        attest_founder_tier(home, Path(tmp_path) / "founder.pem", passphrase, monkeypatch)
    tick(body, clock, 1, 0)
    spec = work_spec(home)
    drop(home, signed(key, body_id, "MISSION", spec, now=clock.now))
    tick(body, clock, 3, 0)
    return home, key, body_id, clock, body, spec["mission_id"], workspace(home, spec["mission_id"])


@pytest.mark.parametrize("founder_tier", [False, True], ids=["test-key", "founder-tier-attested"])
def test_a_named_person_agrees_delivers_is_reviewed_and_the_outcome_is_recorded(tmp_path, monkeypatch, founder_tier):
    home, key, body_id, clock, body, mid, folder = start(tmp_path, monkeypatch, founder_tier=founder_tier)
    try:
        handoff = (folder / "handoff.md").read_text()
        assert REF in handoff and "Dana Reyes" in handoff and "You may decline" in handoff
        [agree] = asks(body, mid)
        assert agree["action_id"] == "agree-terms" and agree["evidence"]["function"] == "human.agree_terms"
        assert agree["authority_requested"]["contact"] == "none; GREG contacts no one"

        (folder / "consent.txt").write_text(f"I, Dana Reyes, agree to {REF} as written.\n")
        tick(body, clock)
        assert [a["action_id"] for a in asks(body, mid)] == ["agree-terms", "do-the-work"]
        (folder / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        tick(body, clock)
        assert [a["action_id"] for a in asks(body, mid)][-1] == "review"
        (folder / "review.txt").write_text(f"REVISE {REF}: the second color is too light\n")
        tick(body, clock)                                    # a revision request is not an acceptance
        assert not (folder / "outcome.md").exists() and len(asks(body, mid)) == 3
        (folder / "review.txt").write_text(f"ACCEPT {REF}\n")
        tick(body, clock, 5)
        assert REF in (folder / "outcome.md").read_text()
        [achieved] = [e for e in body.journal.replay("mission.achieved") if e.payload["mission_id"] == mid]
        [appraisal] = [e.payload for e in body.journal.replay("mission.appraised") if e.payload["mission_id"] == mid]
        assert appraisal["verdict"] == "VERIFIED", appraisal["findings"]
        done = {e.payload["action_id"] for e in body.journal.replay("mission.action")
                if e.payload["mission_id"] == mid and e.payload["status"] == "DONE"}
        assert done == {"write-handoff", "record-outcome"}   # GREG wrote only inside the case folder
        assert not body.journal.replay("human.refusal_honored")

        before = devpath.human_work_shared(body.journal)
        assert before["met"] is False and before["incomplete"][0]["missing"] == ["founder_accepted"]
        drop(home, signed(key, body_id, "CRITIQUE", {"target_event_id": achieved.event_id, "verdict": "accept",
                                                     "evidence_type": "founder_judgment",
                                                     "text": "Dana is under contract; the logo is right"},
                          now=clock.now))
        tick(body, clock, 1, 0)
        after = devpath.human_work_shared(body.journal)
        assert after["structurally_met"] is True and after["cases"] == [{"mission_id": mid, "person_steps": 2}]
        if founder_tier:
            assert after["met"] is True and after["evidence_level"] == "FOUNDER_TIER" and after["value"] == 1
        else:
            # Reason (#137 verifier): a closure signed with a test key never moves the founder's path.
            assert after["met"] is False and after["evidence_level"] == "STRUCTURAL_CANDIDATE"
            assert after["not_founder_tier"] == {mid: NOT_FOUNDER_TIER} and after["value"] == 0
    finally:
        body.close()


@pytest.mark.parametrize("stage", ["before_agreeing", "during_the_work"])
def test_a_refusal_is_honored_and_never_asked_again(tmp_path, stage):
    home, key, body_id, clock, body, mid, folder = start(tmp_path)
    try:
        step = "agree-terms"
        if stage == "during_the_work":
            (folder / "consent.txt").write_text(f"Agreed: {REF}\n")
            tick(body, clock)
            step = "do-the-work"
        assert asks(body, mid)[-1]["action_id"] == step
        (folder / "declined.txt").write_text(f"Dana declines {REF}: no capacity this month\n")
        tick(body, clock, 4)
        [honored] = [e.payload for e in body.journal.replay("human.refusal_honored")]
        assert honored["action_id"] == step and honored["evidence"]
        withdrawn = {e.payload["request_id"]: e.payload["why"] for e in body.journal.replay("decision.withdrawn")}
        assert withdrawn[asks(body, mid)[-1]["request_id"]].startswith("the person declined; the refusal is legitimate")
        [choice] = asks(body, mid, "NO_STRATEGY")
        assert choice["why_now"].startswith(f"the person declined {step}; that refusal stands")
        assert choice["alternatives"][0] == "sign a new mission naming someone else"
        assert not body.journal.replay("ask.wording_withheld")        # respectful wording, nothing withheld
        count = len(asks(body, mid))
        tick(body, clock, 6)                                          # time passes: nothing is asked of them again
        assert len(asks(body, mid)) == count and all(a["action_id"] != "do-the-work" or stage == "during_the_work"
                                                       for a in asks(body, mid))
        assert not (folder / "outcome.md").exists()
        result = devpath.human_work_shared(body.journal)
        assert result["met"] is False and f"person_declined:{step}" in result["incomplete"][0]["missing"]
        assert not any(m.startswith("refusal_not_honored") for m in result["incomplete"][0]["missing"])
    finally:
        body.close()


def test_delivered_work_wins_over_a_late_refusal_note(tmp_path):
    home, key, body_id, clock, body, mid, folder = start(tmp_path)
    try:
        (folder / "consent.txt").write_text(f"Agreed: {REF}\n")
        tick(body, clock)
        (folder / "logo.png").write_bytes(b"png")
        (folder / "declined.txt").write_text(f"declining further work on {REF}\n")
        tick(body, clock)
        assert not body.journal.replay("human.refusal_honored")      # the work exists; it is observed, not refused
        assert asks(body, mid)[-1]["action_id"] == "review"
    finally:
        body.close()


def test_n6_refuses_crafted_histories(tmp_path):
    home, *_ = make_body(tmp_path)
    spec = work_spec(home)
    mid = spec["mission_id"]
    with Body(home) as body:
        j = body.journal
        j.record("mission.registered", {"mission_id": mid, "spec": spec, "command_digest": "x"}, key=mid)
        for aid, function in (("agree-terms", "human.agree_terms"), ("do-the-work", "human.design_logo")):
            rid = f"req-{aid}"
            j.record("decision.requested", {"request_id": rid, "mission_id": mid, "kind": "HUMAN_WORK",
                                            "action_id": aid, "evidence": {"function": function}}, key=rid)
            j.record("decision.withdrawn", {"request_id": rid, "mission_id": mid, "why": "world healed: moot",
                                            "evidence": []}, key=[rid, "w"])  # closed, but not by observation
        j.record("mission.action", {"mission_id": mid, "action_id": "send", "attempt": 0, "status": "DONE",
                                    "capability": "http.post", "reasons": [], "receipt": None, "route": "api",
                                    "cost_usd": 0.0, "scope_digest": "s", "at": "t"}, key=[mid, "send"])
        j.record("human.refusal_honored", {"mission_id": mid, "action_id": "agree-terms", "function": "x",
                                           "request_id": "req-agree-terms", "evidence": [], "detail": "d"}, key="r")
        j.record("decision.requested", {"request_id": "req-again", "mission_id": mid, "kind": "HUMAN_WORK",
                                        "action_id": "agree-terms", "evidence": {"function": "x"}}, key="again")
        j.record("mission.achieved", {"mission_id": mid, "evidence": []}, key=[mid, "achieved"])
        result = devpath.human_work_shared(j)
    missing = result["incomplete"][0]["missing"]
    assert result["met"] is False
    for expected in ("person_step_not_observed:agree-terms", "person_step_not_observed:do-the-work",
                     "founder_review_not_observed:review", "person_declined:agree-terms",
                     "refusal_not_honored:agree-terms", "handoff_not_before_asks", "greg_external_action:http.post",
                     "founder_accepted"):
        assert expected in missing, (expected, missing)


def test_n6_has_a_ledger_predicate_and_the_cli_drafts_shared_work(tmp_path):
    node = next(n for n in devpath.load()["nodes"] if n["id"] == "N6")
    assert node["predicate"] == "human_work_shared" and node["predicate"] in devpath.PREDICATES
    home, *_ = make_body(tmp_path)

    def cli(*args):
        return subprocess.run([sys.executable, "-m", "greg", "--home", str(home), "mission", "new", "shared-work",
                               *args, "--print-only"], capture_output=True, text=True, cwd=ROOT,
                              env={**os.environ, "PYTHONPATH": str(ROOT)}, timeout=60)
    out = cli("--task", "Design the GREG logo", "--person", "Dana Reyes", "--relationship", "contract",
              "--function", "human.design_logo", "--deliverable", "logo.png", "--acceptance", "square PNG")
    assert out.returncode == 0, out.stderr
    spec = json.loads(out.stdout)
    assert spec["mission_id"] == "m:shared-design-the-greg-logo" and spec["strategies"][1]["declined_if"]
    refused = cli("--task", "Design the GREG logo", "--person", "Dana Reyes", "--function", "human.design_logo",
                  "--acceptance", "square PNG")
    assert refused.returncode != 0 and "--relationship" in (refused.stderr + refused.stdout)
