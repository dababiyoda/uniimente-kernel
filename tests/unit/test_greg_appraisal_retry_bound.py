"""Acceptance H.G7: the appraisal retry bound holds across a crash between the last run and its final record.

The last unavailable run and the final appraised UNAVAILABLE are two records. A body killed between them found the
full count of unavailable runs on restart, ran the appraiser once more and could record that fourth run's verdict. A
closure whose attempts are used up is now finished from its retained runs, with no further appraiser run.

In-process Body with a test clock; the founder key is a per-test key, not Alfonso's.
"""
from __future__ import annotations

from greg.body import APPRAISAL_ATTEMPTS, Body
from tests.greg_fixtures import Clock, make_body


def test_a_closure_whose_attempts_are_used_up_is_finished_without_another_run(tmp_path, monkeypatch):
    home = make_body(tmp_path)[0]
    clock = Clock()

    def fourth_run(self, *args, **kwargs):
        raise AssertionError("the appraiser ran again after its attempts were used up")

    with Body(home, clock=clock) as b:
        for attempt in range(1, APPRAISAL_ATTEMPTS + 1):
            b.journal.record("mission.appraisal_unavailable", {
                "mission_id": "m:x", "closure_event": "evt", "attempt": attempt, "of": APPRAISAL_ATTEMPTS,
                "head": "sha256:h", "why": f"run {attempt} was killed", "boot_id": None, "at": "t"},
                key=["m:x", "evt", "appraisal_unavailable", attempt])
        monkeypatch.setattr(Body, "appraise", fourth_run)
        b._appraise_closure("m:x", "evt", clock())
        [final] = [e.payload for e in b.journal.replay("mission.appraised")]
    assert final["verdict"] == "UNAVAILABLE" and final["attempts"] == APPRAISAL_ATTEMPTS
    assert final["findings"] == [f"run {i} was killed" for i in range(1, APPRAISAL_ATTEMPTS + 1)]
    assert final["closure_event"] == "evt"


def test_the_third_unavailable_run_is_final_on_its_own_tick(tmp_path, monkeypatch):
    # Carried from the PR #184 port branch's review (f63f218): the final UNAVAILABLE is recorded right after the
    # third unavailable run, not left for a later tick (or a restart) to finish. A hung appraiser stands in for each.
    import subprocess
    real_run, requests = subprocess.run, []

    def hung_appraiser(argv, *args, **kwargs):
        if list(argv[1:]) != ["-m", "greg.appraisal"]:
            return real_run(argv, *args, **kwargs)
        requests.append(kwargs["input"])
        raise subprocess.TimeoutExpired(argv, kwargs["timeout"])
    monkeypatch.setattr(subprocess, "run", hung_appraiser)
    home = make_body(tmp_path)[0]
    clock = Clock()
    with Body(home, clock=clock) as b:
        b.journal.record("mission.achieved", {"mission_id": "m:x", "at": "t"}, key=["m:x", "achieved"])
        for tick in range(APPRAISAL_ATTEMPTS + 2):        # two more ticks after the bound: nothing more runs
            clock.advance(30)
            b._close_out(clock())
            verdicts = [e.payload["verdict"] for e in b.journal.replay("mission.appraised")]
            assert verdicts == ([] if tick < APPRAISAL_ATTEMPTS - 1 else ["UNAVAILABLE"]), f"tick {tick}"
    assert len(requests) == APPRAISAL_ATTEMPTS
