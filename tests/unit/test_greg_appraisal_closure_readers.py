"""Every reader of an appraisal asks about the closure it means, not about the mission's latest record.

Founder ruling of 2026-11-12: "Bind an appraisal to the specific closure and evidence it actually evaluates." "A
stale appraisal cannot qualify a different closure." "Late appraisal mismatch: classify stale or mismatched evidence
accurately. It cannot establish a timely appraisal or grant permission. Preserve any separately valid refutation,
and request fresh appraisal when required."

A mission can close more than once: a failure closure and later an achievement, or the successive holds of a
standing mission. Each ``mission.appraised`` record judges one of those closures. Before this change several readers
took the latest record of the mission whatever closure it judged, so a verdict recorded late about an old closure
replaced the standing of a newer one. What must hold now (greg/appraisal.py ``standings`` is the one reader):

- an appraisal counts only for the closure it names: a verdict on an old failure closure never changes the standing
  of a later achievement, and a verdict on one hold never changes the standing of another;
- a closure with no appraisal of its own is unappraised, whatever any other closure of the mission was found to be;
- of several appraisals of one closure the final one stands, and a final UNAVAILABLE establishes nothing;
- a refutation stays a refutation of the closure it names and is readable as such;
- a record written before closures were named (no ``closure_event``) is read as the appraisal of the mission's
  achievement.

The tests named "on a real body" run a real ``Body`` with a per-test Ed25519 founder key (not Alfonso's: SANDBOX)
and the body's real separate appraiser process. The only instrument is ``Appraiser``: a run for a named closure can
be made to give no verdict, as a killed process does. The tests named "hand-ordered" write every fact themselves
onto a real ledger, so the order is exact and nothing in them ran.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess

import pytest

import greg.appraisal as appraisal
from greg import acceptance, autonomy, metrics, routing, sop
from greg.body import Body
from greg.cognition import settlement
from greg.journal import Journal
from events.spine import EventSpine
from provenance.ledger import EvidenceLedger
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, signed, workspace, write_strategy

ROOT = Path(__file__).resolve().parents[2]
MID = "m:first-mission-note"       # the acceptance report reads missions named m:first-mission-*
CHECKS = {c: True for c in sop.REQUIRED_CHECKS}
FS_WRITE = {"capability": "fs.write", "action_class": "internal_write", "target_pattern": "workspace:*",
            "budget_band": "$0"}


class Appraiser:
    """The body's real appraiser child (``python -m greg.appraisal``), run unchanged on the body's own request.

    ``kill[closure] = n`` makes the next n runs for that closure give no verdict (exit 137, nothing printed), as a
    killed process does. The key is the closure's event id, or None for the mission's achievement."""

    def __init__(self, monkeypatch):
        self.requests, self.kill = [], {}
        spawn = subprocess.run

        def run(argv, *args, **kwargs):
            if list(argv[1:]) == ["-m", "greg.appraisal"]:     # the body's appraiser child, and nothing else
                request = json.loads(kwargs["input"])
                self.requests.append(request)
                closure = request.get("closure_event")
                if self.kill.get(closure, 0) > 0:
                    self.kill[closure] -= 1
                    return subprocess.CompletedProcess(argv, 137, "", "killed")
            return spawn(argv, *args, **kwargs)

        monkeypatch.setattr(subprocess, "run", run)


@pytest.fixture
def appraiser(monkeypatch):
    return Appraiser(monkeypatch)


def facts(body, kind, mid=MID):
    return [e for e in body.journal.replay(kind) if e.payload.get("mission_id") == mid]


def verdicts(body, mid=MID):
    return [(e.payload["verdict"], e.payload.get("closure_event")) for e in facts(body, "mission.appraised", mid)]


def stop_at(home, clock, kind, *, count=1, mid=MID, ticks=12, step=600.0):
    """Run the body until the mission's ``count``-th closure of this kind is recorded and stop it in that same turn,
    as ``greg stop --local`` does while the engine is stepping: ``Body.tick`` returns before ``_close_out``, so that
    closure waits for its appraisal. The clock is not advanced after the stopping turn. Returns the closure."""
    with Body(home, clock=clock) as body:
        engine_tick = body.engine.tick

        def tick_then_stop(now, **kw):
            out = engine_tick(now, **kw)
            if len(facts(body, kind, mid)) >= count:
                body.layout.stop_file.touch()
            return out

        body.engine.tick = tick_then_stop
        result = {}
        for _ in range(ticks):
            result = body.tick()
            if result.get("stopped"):
                break
            clock.advance(step)
        assert result.get("stopped") is True, result
        closure = facts(body, kind, mid)[count - 1]
        assert closure.event_id not in {e.payload.get("closure_event") for e in facts(body, "mission.appraised", mid)}
    (Path(home) / "STOP").unlink()                    # the founder starts the body again
    return closure


def failing_mission(tmp_path, mid=MID):
    """A mission that fails: its one strategy writes a file the check does not read, so it closes unmet."""
    home, key, body_id, data = make_body(tmp_path)
    status = data / "status.txt"
    status.write_text("not yet")
    drop(home, signed(key, body_id, "MISSION", mission(
        mid, checks=[note_check("status", status, "shipped")],
        strategies=[write_strategy("nudge", "nudge.txt", "nudged", ["status"])], capabilities=["fs.read", "fs.write"])))
    return home, key, body_id, status


def note_mission(tmp_path, mid=MID, *, closure=None):
    """A mission that succeeds: write note.txt, then read it back. With an infinite closure it stands and holds."""
    home, key, body_id, _ = make_body(tmp_path)
    note = workspace(home, mid) / "note.txt"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text("original")
    drop(home, signed(key, body_id, "MISSION", mission(
        mid, checks=[note_check("c", note, "final")], strategies=[write_strategy("w", "note.txt", "final", ["c"])],
        capabilities=["fs.read", "fs.write"], **({"closure": closure} if closure else {}))))
    return home, key, body_id, note


def fs_write(journal) -> dict:
    return routing.track_record(journal).get("fs.write", {})


def earned(journal) -> dict:
    [row] = [r for r in autonomy.report(journal)["tuples"] if r["tuple"] == FS_WRITE]
    return row


# -- hand-ordered ledgers ------------------------------------------------------------------------------------------

class Hand:
    """A hand-ordered ledger: a real Journal over a real EvidenceLedger, every fact written by the test."""

    def __init__(self, tmp_path):
        self.j = Journal(EventSpine(EvidenceLedger("sha256:" + "4" * 64, path=str(tmp_path / "hand.jsonl"))),
                         actor="spiffe://uniimente.internal/test/closure-readers")
        self.n = 0

    def rec(self, kind, data):
        self.n += 1
        return self.j.record(kind, data, key=[kind, self.n])

    def register(self, mid):
        spec = mission(mid, checks=[note_check("c", Path("/nowhere/c.txt"), "ok")],
                       strategies=[write_strategy("w", "c.txt", "ok", ["c"])], capabilities=["fs.read", "fs.write"])
        return self.rec("mission.registered", {"mission_id": mid, "command_digest": "sha256:" + mid, "spec": spec})

    def run(self, mid, action="w", receipt=None):
        return self.rec("mission.action", {"mission_id": mid, "action_id": action, "attempt": self.n,
                                           "status": "DONE", "capability": "fs.write",
                                           "receipt": receipt or f"sha256:r{self.n}"})

    def observe(self, mid, check="c"):
        return self.rec("mission.observed", {"mission_id": mid, "check_id": check, "passed": True})

    def close(self, mid, kind):
        return self.rec("mission." + kind, {"mission_id": mid})

    def appraise(self, mid, verdict, closure=None, **more):
        checks = {**CHECKS, "world_reobserved": verdict != "REFUTED"}
        return self.rec("mission.appraised", {"mission_id": mid, "head": "sha256:h", "verdict": verdict,
                                              "checks": checks, "findings": [], "appraiser": "separate process",
                                              **({"closure_event": closure.event_id} if closure else {}), **more})


@pytest.fixture
def late(tmp_path):
    """m:late closes unmet, is achieved, the achievement is appraised VERIFIED, and only then is the failure
    closure's appraisal recorded: REFUTED. Returns (ledger, the achievement's appraisal, the late one)."""
    led = Hand(tmp_path)
    led.register("m:late")
    led.run("m:late")
    unmet = led.close("m:late", "unmet")
    led.close("m:late", "achieved")
    won = led.appraise("m:late", "VERIFIED")
    refuted = led.appraise("m:late", "REFUTED", unmet)
    return led, won, refuted


def test_hand_ordered_sop_reads_the_achievements_own_appraisal(late):
    led, won, refuted = late
    assert sop.verified_appraisals(led.j) == {"m:late": won.event_id}
    assert sop.current_appraisals(led.j)["m:late"][1].event_id == won.event_id
    assert sop.compounding_metrics(led.j)["verified_outcomes"] == 1


def test_hand_ordered_metrics_read_the_achievements_own_appraisal(late):
    led, won, refuted = late
    [row] = metrics.vepmc(led.j)["missions"]
    assert row["appraised_verified"] is True
    [stage] = metrics.sandbox_whole_machine(led.j)["missions"]
    assert stage["appraised_verified"] is True


def test_hand_ordered_routing_judges_a_run_by_the_newest_closure_that_covers_it(late):
    led, won, refuted = late
    assert routing.track_record(led.j)["fs.write"] == {"done": 1, "failed": 0, "ineffective": 0, "refuted": 0,
                                                       "verified": 1, "founder_reconciled": 0}


def test_hand_ordered_settlement_settles_under_the_current_closures_own_appraisal(late):
    led, won, refuted = late
    assert {m: e.event_id for m, e in settlement._settling_appraisals(led.j).items()} == {"m:late": won.event_id}


def test_hand_ordered_holds_each_judge_the_runs_and_readings_of_their_own_window(tmp_path):
    """Hand-ordered. Three holds of a standing mission, the second refuted: each run and each reading follows the
    hold that closed its window, and no hold's verdict reaches another hold's."""
    led = Hand(tmp_path)
    led.register("m:holds")
    seen, appraised = [], []
    for verdict in ("VERIFIED", "REFUTED", "VERIFIED"):
        led.run("m:holds")
        seen.append(led.observe("m:holds"))
        appraised.append(led.appraise("m:holds", verdict, led.close("m:holds", "held")))
    after = led.observe("m:holds")                               # after the newest hold: no closure claims it yet
    record = routing.track_record(led.j)["fs.write"]
    assert (record["done"], record["verified"], record["refuted"]) == (3, 2, 1)
    assert sop.verified_appraisals(led.j) == {"m:holds": appraised[2].event_id}
    appraisal_of = settlement._observation_appraisal(led.j)
    assert [getattr(appraisal_of(o), "event_id", None) for o in seen] == [
        appraised[0].event_id, None, appraised[2].event_id]
    assert appraisal_of(after).event_id == appraised[2].event_id
    book = appraisal.standings(led.j)
    assert [c.verdict for c in book.of("m:holds")] == ["VERIFIED", "REFUTED", "VERIFIED"]
    # a fourth hold with no appraisal yet: the mission is unappraised, and the third hold's verdict stays its own
    led.run("m:holds")
    led.close("m:holds", "held")
    assert sop.verified_appraisals(led.j) == {} and settlement._settling_appraisals(led.j) == {}
    record = routing.track_record(led.j)["fs.write"]
    assert (record["done"], record["verified"], record["refuted"]) == (4, 2, 1)
    assert settlement._observation_appraisal(led.j)(after) is None     # the fourth hold claims that reading now


def test_a_record_written_before_closures_were_named_is_read_as_the_achievements(tmp_path):
    """Hand-ordered. Until 2026-09-27 only achievements were appraised, and a record named no closure: mission id,
    head, verdict, checks, findings, appraiser. Such a record is the appraisal of the mission's achievement. On a
    ledger that holds no achievement it still stands for one, placed where the record sits. A record that names a
    closure the ledger does not hold counts for no closure."""
    led = Hand(tmp_path)
    old = {"head": "sha256:h", "checks": CHECKS, "findings": [], "appraiser": "separate process"}
    led.register("m:old")
    led.run("m:old")
    unmet = led.close("m:old", "unmet")
    achieved = led.close("m:old", "achieved")
    first = led.rec("mission.appraised", {"mission_id": "m:old", "verdict": "VERIFIED", **old})
    led.appraise("m:old", "REFUTED", unmet)                      # the failure closure's, recorded late
    led.register("m:cut")                                        # its achievement is not on this ledger
    led.run("m:cut")
    cut = led.rec("mission.appraised", {"mission_id": "m:cut", "verdict": "VERIFIED", **old})
    stray = led.rec("mission.appraised", {"mission_id": "m:cut", "verdict": "REFUTED", **old,
                                          "checks": {**CHECKS, "world_reobserved": False},
                                          "closure_event": "ev-not-on-this-ledger"})
    led.register("m:failed")                                     # the old word for a run that gave no verdict
    led.close("m:failed", "achieved")
    led.rec("mission.appraised", {"mission_id": "m:failed", "verdict": "APPRAISAL_FAILED", **{**old, "checks": {}}})

    assert sop.verified_appraisals(led.j) == {"m:old": first.event_id, "m:cut": cut.event_id}
    record = routing.track_record(led.j)["fs.write"]
    assert (record["done"], record["verified"], record["refuted"]) == (2, 2, 0)
    assert set(settlement._settling_appraisals(led.j)) == {"m:old", "m:cut"}
    rows = {r["mission_id"]: r["appraised_verified"] for r in metrics.vepmc(led.j)["missions"]}
    assert rows == {"m:old": True, "m:failed": False}

    book = appraisal.standings(led.j)
    assert book.named_by(first.event_id) is book.closure(achieved.event_id)
    assert book.current("m:old").verdict == "VERIFIED" and book.closure(unmet.event_id).verdict == "REFUTED"
    implied = book.current("m:cut")
    assert (implied.event_id, implied.kind, implied.verdict) == (None, "achieved", "VERIFIED")
    assert book.named_by(cut.event_id) is implied and [e.event_id for e in book.unbound] == [stray.event_id]
    assert book.current("m:failed").verdict is None and book.current("m:failed").record is not None


def test_of_several_appraisals_of_one_closure_the_final_one_stands(tmp_path):
    """Hand-ordered. A closure answered UNAVAILABLE and then VERIFIED is VERIFIED; one whose final answer is
    UNAVAILABLE is unappraised, and so is one that has no appraisal at all."""
    led = Hand(tmp_path)
    for mid in ("m:again", "m:stale", "m:never"):
        led.register(mid)
        led.run(mid)
        led.close(mid, "achieved")
    waiting = {"not_run": {"fs.read": "fs.read is DETACHED"}}
    led.appraise("m:again", "UNAVAILABLE", **waiting)
    final = led.appraise("m:again", "VERIFIED")
    led.appraise("m:stale", "UNAVAILABLE", **waiting)
    led.appraise("m:stale", "UNAVAILABLE", appraised_late={"waited_on": ["fs.read"]})
    assert sop.verified_appraisals(led.j) == {"m:again": final.event_id}
    assert sop.awaiting_appraisal(led.j) == set()                # a stale answer waits for nothing
    record = routing.track_record(led.j)["fs.write"]
    assert (record["done"], record["verified"], record["refuted"]) == (3, 1, 0)
    assert set(settlement._settling_appraisals(led.j)) == {"m:again"}
    assert earned(led.j)["evidence"]["verified"] == 1 and earned(led.j)["evidence"]["unappraised"] == 2
    book = appraisal.standings(led.j)
    assert book.current("m:again").standing.event_id == final.event_id
    assert (book.current("m:stale").verdict, book.current("m:never").verdict) == (None, None)
    assert book.current("m:stale").record is not None and book.current("m:never").record is None


def test_hand_ordered_the_earned_level_reads_each_runs_own_closure_and_its_final_appraisal(tmp_path):
    """Hand-ordered. m:own: a run, a failure closure with no appraisal yet, then the achievement, VERIFIED. The run
    belongs to the failure closure, so it is unappraised, and stays so when that closure's own verdict lands late.
    m:twice: one closure answered UNAVAILABLE and then VERIFIED: its run is verified."""
    led = Hand(tmp_path)
    led.register("m:own")
    led.run("m:own")
    unmet = led.close("m:own", "unmet")
    led.close("m:own", "achieved")
    led.appraise("m:own", "VERIFIED")
    assert {k: earned(led.j)["evidence"][k] for k in ("runs", "verified", "unappraised")} == {
        "runs": 1, "verified": 0, "unappraised": 1}
    led.appraise("m:own", "VERIFIED_UNMET", unmet)               # the failure closure's own verdict, recorded late
    assert {k: earned(led.j)["evidence"][k] for k in ("runs", "verified", "unappraised")} == {
        "runs": 1, "verified": 0, "unappraised": 1}
    led.register("m:twice")
    led.run("m:twice")
    led.close("m:twice", "achieved")
    led.appraise("m:twice", "UNAVAILABLE", not_run={"fs.read": "fs.read is DETACHED"})
    assert earned(led.j)["evidence"]["verified"] == 0 and earned(led.j)["level"] == "SHADOW"
    led.appraise("m:twice", "VERIFIED")
    row = earned(led.j)
    assert {k: row["evidence"][k] for k in ("runs", "verified", "unappraised")} == {
        "runs": 2, "verified": 1, "unappraised": 1}
    assert row["level"] == "RECOMMENDER"


def test_hand_ordered_the_acceptance_report_reads_the_achievements_own_appraisal(tmp_path):
    """Hand-ordered, on the ledger of a real body home (the report reads a home): the First Mission closed unmet,
    was achieved and appraised VERIFIED, and the failure closure's REFUTED was recorded after that."""
    home, _, _, _ = make_body(tmp_path)
    mid = "m:first-mission-hand"
    with Body(home) as body:
        led = Hand.__new__(Hand)
        led.j, led.n = body.journal, 0
        led.register(mid)
        led.run(mid)
        unmet = led.close(mid, "unmet")
        led.close(mid, "achieved")
        led.appraise(mid, "VERIFIED")
        led.appraise(mid, "REFUTED", unmet)
    report = acceptance.report(home)
    first = {p["property"]: p["status"] for p in report["properties"]}["first_mission_verified"]
    assert first == "PASS" and report["first_mission"]["appraised_verified"] is True


# -- on a real body ------------------------------------------------------------------------------------------------

def test_a_late_verdict_on_a_failure_closure_never_changes_the_standing_of_the_achievement(tmp_path, appraiser):
    """On a real body. A failure closure's first appraiser run is killed; the founder does the work; the mission
    achieves and its achievement is appraised VERIFIED; the retry of the failure closure's appraisal is recorded
    after it, REFUTED (the world it claimed is gone). Every reader that means the achievement still finds VERIFIED,
    and the failure closure's own verdict is still on the ledger, readable as its own."""
    home, key, body_id, status = failing_mission(tmp_path)
    clock = Clock()
    unmet = stop_at(home, clock, "mission.unmet")
    with Body(home, clock=clock) as body:
        appraiser.kill[unmet.event_id] = 1
        body.tick()
        clock.advance(3600)
        assert verdicts(body) == [] and len(facts(body, "mission.appraisal_unavailable")) == 1
        status.write_text("shipped")                             # the founder does the work
        for _ in range(3):
            body.tick()
            clock.advance(3600)
        assert body.engine.book.missions[MID].status == "ACHIEVED"
        assert verdicts(body) == [("VERIFIED", None), ("REFUTED", unmet.event_id)]     # the old closure's is last
        won, late = facts(body, "mission.appraised")
        journal = body.journal

        assert sop.verified_appraisals(journal) == {MID: won.event_id}
        assert sop.current_appraisals(journal)[MID][1].event_id == won.event_id
        [row] = [r for r in metrics.vepmc(journal)["missions"] if r["mission_id"] == MID]
        assert row["appraised_verified"] is True and row["founder_signed"] is True
        [stage] = [r for r in metrics.sandbox_whole_machine(journal)["missions"] if r["mission_id"] == MID]
        assert stage["appraised_verified"] is True and stage["founder_signed_via_inbox"] is True
        # the one run sits in both windows; the newest closure covering it is the achievement
        assert (fs_write(journal)["refuted"], fs_write(journal)["verified"]) == (0, 1)
        assert {m: e.event_id for m, e in settlement._settling_appraisals(journal).items()} == {MID: won.event_id}
        assert sop.awaiting_appraisal(journal) == set()
        # the refutation is not erased where it is evidence about its own closure's runs
        assert sorted(f["kind"] for f in autonomy.failures(journal)) == ["ineffective", "refuted"]

        book = appraisal.standings(journal)                      # the one reader's own view of the two closures
        current = book.current(MID)
        assert (current.kind, current.verdict, current.standing.event_id) == ("achieved", "VERIFIED", won.event_id)
        failure = book.closure(unmet.event_id)                   # its own verdict, kept and attributed to it
        assert (failure.kind, failure.verdict, failure.standing.event_id) == ("unmet", "REFUTED", late.event_id)
        assert book.named_by(late.event_id) is failure and book.unbound == []


        from greg import goal_gravity
        signals, _ = goal_gravity._sense(body, goal_gravity.binding_for(body).loop, 0)
        readings = [o["value"] for s in signals for o in s.payload["observations"]
                    if (o["subject"], o["attribute"]) == (MID, "appraised_verified")]
        assert readings == [True]
    report = acceptance.report(home)
    first = {p["property"]: p["status"] for p in report["properties"]}["first_mission_verified"]
    assert first == "PASS" and report["first_mission"]["appraised_verified"] is True


def test_each_hold_of_a_standing_mission_stands_on_its_own_appraisal(tmp_path, appraiser):
    """On a real body. Hold 1 is VERIFIED. Hold 2 is really refuted: its deliverable is edited before it is
    appraised. The mission's current standing is then REFUTED. The mission heals and holds a third time, VERIFIED:
    the current standing is VERIFIED, and hold 2's refutation is still attributed to hold 2 and to its run alone.
    While a hold waits for its own appraisal it is unappraised, whatever the hold before it was found to be."""
    home, key, body_id, note = note_mission(tmp_path, "m:standing", closure={"kind": "infinite"})
    mid, clock = "m:standing", Clock()
    with Body(home, clock=clock) as body:
        for _ in range(3):
            body.tick()
            clock.advance(60)
        [hold1] = facts(body, "mission.held", mid)
        assert verdicts(body, mid) == [("VERIFIED", hold1.event_id)]
        [first] = facts(body, "mission.appraised", mid)
        assert sop.verified_appraisals(body.journal) == {mid: first.event_id}
    note.write_text("drifted")
    hold2 = stop_at(home, clock, "mission.held", count=2, mid=mid, step=3600.0)
    with Body(home, clock=clock) as body:                        # hold 2 waits for its appraisal: unappraised
        journal = body.journal
        assert sop.verified_appraisals(journal) == {} and settlement._settling_appraisals(journal) == {}
        assert (fs_write(journal)["done"], fs_write(journal)["verified"], fs_write(journal)["refuted"]) == (2, 1, 0)
        assert (earned(journal)["evidence"]["verified"], earned(journal)["evidence"]["unappraised"]) == (1, 1)
        assert mid not in sop.current_appraisals(journal)
        book = appraisal.standings(journal)
        assert book.current(mid).event_id == hold2.event_id and book.current(mid).verdict is None
        assert book.closure(hold1.event_id).verdict == "VERIFIED"

        note.write_text("edited after the hold")                 # the deliverable hold 2 claims is edited
        body.tick()
        assert verdicts(body, mid)[-1] == ("REFUTED", hold2.event_id)
        refuted = facts(body, "mission.appraised", mid)[-1]
        assert refuted.payload["checks"]["world_reobserved"] is False
        assert sop.verified_appraisals(journal) == {} and settlement._settling_appraisals(journal) == {}
        # hold 2's refutation reaches hold 2's run only: hold 1's run keeps hold 1's verdict
        assert (fs_write(journal)["verified"], fs_write(journal)["refuted"]) == (1, 1)
        assert (earned(journal)["evidence"]["verified"], earned(journal)["evidence"]["refuted"]) == (1, 1)
        book = appraisal.standings(journal)
        assert (book.current(mid).event_id, book.current(mid).verdict) == (hold2.event_id, "REFUTED")
        assert sop.current_appraisals(journal)[mid][1].event_id == refuted.event_id
    clock.advance(3600)
    hold3 = stop_at(home, clock, "mission.held", count=3, mid=mid, step=3600.0)
    with Body(home, clock=clock) as body:                        # hold 3 waits: not refuted by hold 2's verdict
        journal = body.journal
        assert (fs_write(journal)["done"], fs_write(journal)["verified"], fs_write(journal)["refuted"]) == (3, 1, 1)
        assert mid not in sop.verified_appraisals(journal) and mid not in sop.current_appraisals(journal)
        assert appraisal.standings(journal).current(mid).verdict is None
        body.tick()
        assert verdicts(body, mid) == [("VERIFIED", hold1.event_id), ("REFUTED", hold2.event_id),
                                       ("VERIFIED", hold3.event_id)]
        third = facts(body, "mission.appraised", mid)[-1]
        assert sop.verified_appraisals(journal) == {mid: third.event_id}
        assert {m: e.event_id for m, e in settlement._settling_appraisals(journal).items()} == {mid: third.event_id}
        # hold 2's refutation is still hold 2's, and still counts against the one run of its window
        assert (fs_write(journal)["verified"], fs_write(journal)["refuted"]) == (2, 1)
        assert (earned(journal)["evidence"]["verified"], earned(journal)["evidence"]["refuted"]) == (2, 1)
        book = appraisal.standings(journal)
        assert (book.current(mid).event_id, book.current(mid).verdict) == (hold3.event_id, "VERIFIED")
        assert (book.closure(hold2.event_id).verdict, book.closure(hold2.event_id).standing.event_id) == (
            "REFUTED", refuted.event_id)
        [failure] = autonomy.failures(journal)
        runs = facts(body, "mission.action", mid)
        assert (failure["kind"], failure["evidence"], failure["run"].event_id) == (
            "refuted", refuted.event_id, runs[1].event_id)
        # each reading settles under the closure it belongs to: hold 2's readings under none
        appraisal_of = settlement._observation_appraisal(journal)
        position = journal.positions("mission.")
        settles = [(appraisal_of(o) or o).event_id for o in facts(body, "mission.observed", mid)
                   if position[hold1.event_id] < position[o.event_id] < position[hold2.event_id]]
        assert settles and third.event_id not in settles and first.event_id not in settles


def test_a_closure_appraised_verified_after_an_unavailable_answer_counts_as_verified(tmp_path, appraiser):
    """On a real body. The achievement waits for its appraisal while its sensor is detached: the appraiser answers
    UNAVAILABLE (it ran nothing). The founder attaches the sensor again and the same closure is appraised VERIFIED.
    The final appraisal of that closure is the one that judged it: the run is verified for the earned level."""
    home, key, body_id, note = note_mission(tmp_path, "m:reattach")
    mid, clock = "m:reattach", Clock()
    stop_at(home, clock, "mission.achieved", mid=mid, step=1.0)
    drop(home, signed(key, body_id, "CAPABILITY_DETACH", {"capability_id": "fs.read"}))
    with Body(home, clock=clock) as body:
        body.tick()
        clock.advance(60)
        assert verdicts(body, mid) == [("UNAVAILABLE", None)]
        assert sop.awaiting_appraisal(body.journal) == {mid} and sop.verified_appraisals(body.journal) == {}
        waiting = earned(body.journal)
        assert (waiting["evidence"]["verified"], waiting["evidence"]["unappraised"], waiting["level"]) == (
            0, 1, "SHADOW")
        drop(home, signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": "fs.read"}))
        body.tick()
        assert verdicts(body, mid) == [("UNAVAILABLE", None), ("VERIFIED", None)]
        row = earned(body.journal)
        assert (row["evidence"]["verified"], row["evidence"]["unappraised"], row["level"]) == (1, 0, "RECOMMENDER")
        closure = appraisal.standings(body.journal).current(mid)
        assert len(closure.appraisals) == 2 and closure.verdict == "VERIFIED"
        assert sop.awaiting_appraisal(body.journal) == set() and mid in sop.verified_appraisals(body.journal)
        assert fs_write(body.journal)["verified"] == 1


def test_a_run_is_judged_by_its_own_closure_and_never_by_a_later_one_in_its_place(tmp_path, appraiser):
    """On a real body. w2 runs first and leaves c2 failing; w1 fixes c1; nothing is left for c2, so the mission
    closes unmet. That failure closure's appraiser runs are killed, the founder fixes c2 and the mission achieves,
    VERIFIED. w1's run belongs to the failure closure, which has no appraisal yet: it is unappraised for the earned
    level, and the achievement's VERIFIED does not judge it in the failure closure's place (it would be taken away
    again the moment the failure closure's own appraisal landed)."""
    home, key, body_id, _ = make_body(tmp_path)
    mid, clock = "m:two-checks", Clock()
    ws = workspace(home, mid)
    drop(home, signed(key, body_id, "MISSION", mission(
        mid, checks=[note_check("c1", ws / "c1.txt", "ok"), note_check("c2", ws / "c2.txt", "ok")],
        strategies=[write_strategy("w2", "c2.txt", "wrong", ["c2"]), write_strategy("w1", "c1.txt", "ok", ["c1"])],
        capabilities=["fs.read", "fs.write"])))
    unmet = stop_at(home, clock, "mission.unmet", mid=mid)
    with Body(home, clock=clock) as body:
        appraiser.kill[unmet.event_id] = 2
        body.tick()
        clock.advance(3600)
        (ws / "c2.txt").write_text("ok")                         # the founder does the work, and says so
        [ask] = [e.payload for e in body.journal.replay("decision.requested") if e.payload["kind"] == "NO_STRATEGY"]
        drop(home, signed(key, body_id, "DECISION", {"request_id": ask["request_id"], "answer": "approve"}))
        for _ in range(6):                                       # stop in the turn the mission achieves
            body.tick()
            clock.advance(3600)
            if facts(body, "mission.achieved", mid):
                break
        assert len(facts(body, "mission.achieved", mid)) == 1
        assert verdicts(body, mid) == [("VERIFIED", None)]       # the failure closure still has no verdict
        assert len(facts(body, "mission.appraisal_unavailable", mid)) == 2
        assert [a.payload["action_id"] for a in facts(body, "mission.action", mid)] == ["w2", "w1"]
        row = earned(body.journal)
        assert {k: row["evidence"][k] for k in ("runs", "verified", "ineffective", "unappraised")} == {
            "runs": 2, "verified": 0, "ineffective": 1, "unappraised": 1}
        assert row["level"] == "SHADOW"
        assert mid in sop.verified_appraisals(body.journal)      # the achievement itself is verified


# -- one reader ----------------------------------------------------------------------------------------------------

# Every product file that reads ``mission.appraised`` itself, and the question it asks. A reader of standing (is
# this closure, or this mission, verified, refuted or unappraised?) belongs in greg/appraisal.py ``standings``; a
# new file here must say why its question is a different one.
READS_APPRAISALS = {
    "greg/appraisal.py": "the one reader of standing (standings), and the appraiser's own check whether an earlier "
                         "appraisal of this same closure waited (_waited_on)",
    "greg/body.py": "the writer: which closures still need an appraiser run, keyed by closure",
    "greg/mission_control.py": "history: the Proof list shows every appraisal, one row each, with its closure",
    "greg/tribunal.py": "history: the morning report lists every appraisal as recorded",
    "greg/rehearsal.py": "history: the error text of a rehearsal whose mission did not close lists its appraisals",
    "greg/corrections.py": "per closure: each REFUTED appraisal is a cause for the claims of the closure it names, "
                           "requalified only by a later VERIFIED of that same closure",
    "greg/path.py": "identity: whether the founder's signed critique names an achievement or an appraisal of these "
                    "missions (event ids, no verdict read)",
    "greg/goal_gravity.py": "perception: which new ledger records are appraisals; the reading comes from standings",
    "greg/cognition/seed_path.py": "citation: whether the evidence a cognition outcome cites includes a VERIFIED "
                                   "appraisal of its own mission (the cited event, by id)",
}


def test_no_other_product_file_reads_appraisals_on_its_own():
    """Static. The readers of standing all go through greg/appraisal.py; this is the list of every other file under
    greg/ that names the fact, so a new reader of "the latest appraisal" is noticed."""
    found = set()
    for path in sorted((ROOT / "greg").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if re.search(r"""["'](greg\.)?mission\.appraised["']""", text):
            found.add(path.relative_to(ROOT).as_posix())
    assert found == set(READS_APPRAISALS), sorted(found ^ set(READS_APPRAISALS))
