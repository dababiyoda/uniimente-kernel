"""Founder correction -> bounded hypothesis -> later mission behaviour -> evidence -> retain/regress.

Strategies here all use ``fs.write``, so the empirical per-capability reliability in
``routing.py`` cannot tell them apart; only the typed ``params.content`` fact can.
That is exactly the gap a founder correction must close without becoming dogma.
"""
from pathlib import Path

import pytest

from greg import corrections
from greg.body import Body, Layout
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, signed, workspace, write_strategy

PLACEHOLDER = "status: TODO"
REAL = "status: all repositories clean"


def _note_mission(home, mission_id, *, placeholder=PLACEHOLDER, real=REAL, closure=None, capabilities=("fs.read", "fs.write")):
    path = workspace(home, mission_id) / "status.txt"
    return mission(mission_id, checks=[note_check("status", path, "status")],
                   strategies=[write_strategy("quick-note", "status.txt", placeholder, ["status"]),
                               write_strategy("full-note", "status.txt", real, ["status"])],
                   capabilities=list(capabilities), closure=closure)


def _run(body, clock, mission_id, ticks=6):
    for _ in range(ticks):
        body.tick()
        clock.advance(61)
        if any(e.payload["mission_id"] == mission_id for e in body.journal.replay("mission.achieved")):
            break


def _action(body, mission_id, action_id):
    return next(e for e in body.journal.replay("mission.action")
                if e.payload["mission_id"] == mission_id and e.payload["action_id"] == action_id)


def _choice(body, mission_id):
    return next(e.payload for e in body.journal.replay("mission.action") if e.payload["mission_id"] == mission_id)


def _critique(home, key, body_id, target, *, verdict="reject", evidence="founder_judgment", correction=None, **extra):
    payload = {"target_event_id": target, "verdict": verdict, "evidence_type": evidence,
               "text": "a placeholder note is worthless to me", **extra}
    if correction is not None:
        payload["correction"] = correction
    drop(home, signed(key, body_id, "CRITIQUE", payload))


AVOID_PLACEHOLDER = {"adjustment": "avoid", "scope": ["capability", "params.content"]}


@pytest.fixture
def corrected(tmp_path):
    """Mission 1 ran the placeholder strategy; Alfonso signed a critique with a correction."""
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", _note_mission(home, "m:one")))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        _run(body, clock, "m:one")
        first = _action(body, "m:one", "quick-note")
    assert first.payload["status"] == "DONE", "baseline chose the placeholder strategy"
    _critique(home, key, body_id, first.event_id, correction=AVOID_PLACEHOLDER,
              regression="placeholder notes must not be delivered as status")
    with Body(home, clock=clock) as body:
        body.tick()
        state = corrections.book(body.journal)
    assert list(state.values())[0]["state"] == "CANDIDATE"
    return home, key, body_id, clock


def test_b_held_out_mission_changes_choice_and_records_both_decisions(corrected):
    home, key, body_id, clock = corrected
    drop(home, signed(key, body_id, "MISSION", _note_mission(home, "m:two")))
    with Body(home, clock=clock) as body:
        _run(body, clock, "m:two")
        decision = _choice(body, "m:two")
        applied = [e.payload for e in body.journal.replay("correction.applied")]
    assert decision["action_id"] == "full-note"
    assert decision["routing"]["baseline_choice"] == "quick-note", "without the correction GREG picks A"
    assert decision["routing"]["changed_by"] and applied[0]["baseline_choice"] == "quick-note"


def test_insufficient_evidence_keeps_the_candidate_unresolved(corrected):
    home, key, body_id, clock = corrected
    drop(home, signed(key, body_id, "MISSION", _note_mission(home, "m:two")))
    with Body(home, clock=clock) as body:
        _run(body, clock, "m:two")
        state = list(corrections.book(body.journal).values())[0]
    assert state["state"] == "CANDIDATE" and not state["trials"], "no founder verdict yet: not retained"


def _accept_or_reject(home, key, body_id, clock, mission_id, verdict):
    with Body(home, clock=clock) as body:
        target = _action(body, mission_id, "full-note").event_id
    drop(home, signed(key, body_id, "CRITIQUE", {"target_event_id": target, "verdict": verdict,
                                                 "evidence_type": "founder_judgment",
                                                 "text": f"{verdict} the reviewed note"}))
    with Body(home, clock=clock) as body:
        body.tick()
        return corrections.book(body.journal), body.journal


def test_retained_closes_regression_and_survives_restart(corrected):
    home, key, body_id, clock = corrected
    drop(home, signed(key, body_id, "MISSION", _note_mission(home, "m:two")))
    with Body(home, clock=clock) as body:
        _run(body, clock, "m:two")
    state, journal = _accept_or_reject(home, key, body_id, clock, "m:two", "accept")
    c = list(state.values())[0]
    assert c["state"] == "RETAINED"
    closed = [e.payload for e in journal.replay("critique.regression_closed")]
    assert closed and closed[0]["disposition"] == "RETAINED" and closed[0]["prior_behavior"]["action_id"] == "quick-note"
    assert closed[0]["changed_behavior"]["chosen"] == "full-note"
    # E: a new process (restart) still applies the retained correction to a third mission.
    drop(home, signed(key, body_id, "MISSION", _note_mission(home, "m:three")))
    with Body(home, clock=clock) as body:
        body.boot()
        _run(body, clock, "m:three")
        assert _choice(body, "m:three")["action_id"] == "full-note"


def test_f_regressed_correction_stops_influencing_routing_and_is_surfaced(corrected):
    home, key, body_id, clock = corrected
    drop(home, signed(key, body_id, "MISSION", _note_mission(home, "m:two")))
    with Body(home, clock=clock) as body:
        _run(body, clock, "m:two")
    state, journal = _accept_or_reject(home, key, body_id, clock, "m:two", "reject")
    assert list(state.values())[0]["state"] == "REGRESSED"
    assert not list(journal.replay("critique.regression_closed")), "a failed correction does not close the regression"
    review = corrections.review(journal)
    assert review["founder_review"] and "Founder review recommended" in review["founder_review"][0]["message"]
    drop(home, signed(key, body_id, "MISSION", _note_mission(home, "m:three")))
    with Body(home, clock=clock) as body:
        body.boot()
        _run(body, clock, "m:three")
        assert _choice(body, "m:three")["action_id"] == "quick-note", "back to the baseline choice"


def test_c_same_words_different_typed_scope_does_not_match(corrected):
    home, key, body_id, clock = corrected
    # Same action ids, same rationale text; the placeholder content differs, so the typed scope differs.
    drop(home, signed(key, body_id, "MISSION", _note_mission(home, "m:other", placeholder="status: TBD")))
    with Body(home, clock=clock) as body:
        _run(body, clock, "m:other")
        decision = _choice(body, "m:other")
    assert decision["action_id"] == "quick-note" and not decision["routing"]["changed_by"]


def test_d_correction_never_widens_authority(corrected):
    home, key, body_id, clock = corrected
    # The later mission's cone does not admit fs.write at all: the correction changes nothing about that.
    drop(home, signed(key, body_id, "MISSION", _note_mission(home, "m:narrow", capabilities=("fs.read",))))
    with Body(home, clock=clock) as body:
        for _ in range(3):
            body.tick()
            clock.advance(61)
        done = [e for e in body.journal.replay("mission.action")
                if e.payload["mission_id"] == "m:narrow" and e.payload["status"] == "DONE"]
        cone = body.engine.book.missions["m:narrow"].cone
    assert not done, "no action executes outside the signed light cone"
    assert "fs.write" not in cone.capabilities


def test_a_same_mission_later_choice_is_corrected(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    spec = _note_mission(home, "m:watch", closure={"kind": "infinite", "cadence_seconds": 60})
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        for _ in range(3):
            body.tick()
            clock.advance(61)
        first = _action(body, "m:watch", "quick-note")
    _critique(home, key, body_id, first.event_id, correction=AVOID_PLACEHOLDER)
    (workspace(home, "m:watch") / "status.txt").unlink()  # drift: the note disappears
    with Body(home, clock=clock) as body:
        for _ in range(4):
            body.tick()
            clock.advance(61)
        later = [e.payload for e in body.journal.replay("mission.action") if e.payload["mission_id"] == "m:watch"]
    assert later[-1]["action_id"] == "full-note" and later[-1]["routing"]["baseline_choice"] == "quick-note"


def test_objective_close_condition_retains_on_reobserved_checks(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    broken = "stale"  # does not contain "status": objectively ineffective
    drop(home, signed(key, body_id, "MISSION", _note_mission(home, "m:one", placeholder=broken)))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        _run(body, clock, "m:one")
        first = _action(body, "m:one", "quick-note")
    _critique(home, key, body_id, first.event_id, evidence="objective_failure", correction=AVOID_PLACEHOLDER)
    drop(home, signed(key, body_id, "MISSION", _note_mission(home, "m:two", placeholder=broken)))
    with Body(home, clock=clock) as body:
        _run(body, clock, "m:two")
        c = list(corrections.book(body.journal).values())[0]
    assert c["close_condition"] == "checks" and c["state"] == "RETAINED"


def test_g_contrary_evidence_on_a_founder_rule_is_preserved_and_surfaced(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", _note_mission(home, "m:one")))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        _run(body, clock, "m:one")
        first = _action(body, "m:one", "quick-note")
    _critique(home, key, body_id, first.event_id, correction={**AVOID_PLACEHOLDER, "binding": True})
    drop(home, signed(key, body_id, "MISSION", _note_mission(home, "m:two")))
    with Body(home, clock=clock) as body:
        _run(body, clock, "m:two")
    state, journal = _accept_or_reject(home, key, body_id, clock, "m:two", "reject")
    c = list(state.values())[0]
    assert c["state"] == "RULE" and c["contradicted"], "a founder rule is not silently regressed"
    assert c["trials"][0]["result"] == "did_not_help", "the counterevidence is retained"
    assert corrections.review(journal)["founder_review"]


def test_h_conflicting_corrections_are_exposed_not_silently_resolved(corrected):
    home, key, body_id, clock = corrected
    with Body(home, clock=clock) as body:
        first = _action(body, "m:one", "quick-note")
    _critique(home, key, body_id, first.event_id, verdict="note",
              correction={"adjustment": "prefer", "scope_values": {"capability": "fs.write",
                                                                   "params.content": PLACEHOLDER}})
    drop(home, signed(key, body_id, "MISSION", _note_mission(home, "m:two")))
    with Body(home, clock=clock) as body:
        _run(body, clock, "m:two")
        decision = _choice(body, "m:two")
        conflicts = [e.payload for e in body.journal.replay("correction.conflict")]
    assert conflicts and conflicts[0]["action_id"] == "quick-note"
    assert decision["routing"]["conflicts"], "the decision record shows the conflict"
    assert decision["action_id"] == "quick-note", "neutralized: baseline order, no silent winner"


def test_scope_must_be_typed_and_capability_bound(corrected):
    home, key, body_id, clock = corrected
    with Body(home, clock=clock) as body:
        first = _action(body, "m:one", "quick-note")
    for bad in ({"adjustment": "avoid", "scope": ["rationale"]},
                {"adjustment": "prefer", "scope_values": {"params.content": REAL}},
                {"adjustment": "avoid", "min_trials": 0}):
        _critique(home, key, body_id, first.event_id, correction=bad)
    with Body(home, clock=clock) as body:
        body.tick()
        rejected = list(body.journal.replay("command.rejected"))
        assert len(corrections.book(body.journal)) == 1
    assert len(rejected) >= 3
