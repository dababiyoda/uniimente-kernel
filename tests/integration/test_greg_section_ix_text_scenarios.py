"""Directive of 2026-10-22, section IX: end-to-end scenarios on GREG's one mission path, for text sources.

Each scenario runs a founder-signed mission through the real engine, the judge and the separate appraiser, and checks
what the founder is told. The other section IX scenarios have their tests where their code lives:

* long outputs whose required or forbidden phrase lies past the preview, and an incomplete observation replayed by
  a restarted body: ``tests/unit/test_greg_whole_output_judgment.py`` (#209);
* a file of any size: ``tests/unit/test_greg_text_query.py`` (this branch);
* PDFs, licences and reuse of an acquired component: ``tests/unit/test_greg_document_text.py`` (#201) and its fixes.

In-process Body with a test clock (SANDBOX); the founder key is a per-test key.
"""
from __future__ import annotations

import hashlib

from greg.body import Body
from tests.greg_fixtures import Clock, make_body, mission
from tests.unit.test_greg_missions import events, run, submit


def _never(check_id, path, phrase, **params):
    return {"check_id": check_id, "description": f"{path.name} never mentions {phrase}",
            "sensor": {"capability": "fs.search", "params": {"path": str(path), "phrases": [phrase], **params},
                       "target": f"fs:{path.name}"},
            "predicate": {"op": "equals", "field": "queries.0.found", "value": False}}


def _mentions(check_id, path, phrase, **params):
    check = _never(check_id, path, phrase, **params)
    check["description"] = f"{path.name} mentions {phrase}"
    check["predicate"]["value"] = True
    return check


def _submit(home, key, body_id, mission_id, checks):
    submit(home, key, body_id, "MISSION", mission(mission_id, checks=checks, strategies=[],
                                                  capabilities=["fs.search"], ceiling="read_only"))


def _observed(home, mission_id):
    return [e for e in events(home, "mission.observed") if e["mission_id"] == mission_id]


def _asks(requests, mission_id):
    return [r.get("kind") for r in requests if r.get("mission_id") == mission_id]


def _broken_sensor_mission(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    target = data / "audit.log"
    target.mkdir()                                                                # fs.search refuses a directory
    _submit(home, key, body_id, "m:audit", [_never("clean", target, "FATAL")])
    clock = Clock()
    missions, requests = run(home, clock, ticks=12, step=600.0)
    assert missions["m:audit"].status != "ACHIEVED"
    observed = _observed(home, "m:audit")
    assert observed and not any(e["passed"] for e in observed)
    assert all("not a regular file" in e["detail"] for e in observed)            # the reason is kept
    assert _asks(requests, "m:audit") == ["SENSOR_FAILURE"]                      # asked about the sensor
    return home, key, body_id, target, clock, observed


def test_a_failed_capability_hands_off_truthfully_and_the_mission_resumes_when_the_world_is_fixed(tmp_path):
    """Scenario 7. The sensor fails (the path is a directory, which fs.search refuses). The mission does not close,
    the founder is asked about the sensor, not told the phrase was found or absent, and the refusal's reason is on
    the record. GREG keeps re-reading at the mission's cadence. When the world is fixed, the question is withdrawn
    as moot, the same signed mission closes without being signed again, and the separate appraiser verifies it.
    Before: after the third failed round nothing was read again until the founder answered."""
    home, key, body_id, target, clock, observed = _broken_sensor_mission(tmp_path)
    target.rmdir()
    target.write_text("all quiet\n" * 5000)                                       # the world is fixed
    missions, requests = run(home, clock, ticks=12, step=600.0)
    assert missions["m:audit"].status == "ACHIEVED"
    assert _asks(requests, "m:audit") == []
    [withdrawn] = [e for e in events(home, "decision.withdrawn") if e["mission_id"] == "m:audit"]
    assert "read again" in withdrawn["why"]                                       # withdrawn, never answered
    assert not [e for e in events(home, "decision.answered")]
    assert [e for e in events(home, "mission.submitted") if e.get("mission_id") == "m:audit"][1:] == []
    appraised = [e for e in events(home, "mission.appraised") if e["mission_id"] == "m:audit"]
    assert appraised and appraised[-1]["verdict"] == "VERIFIED"
    after = _observed(home, "m:audit")
    assert after[: len(observed)] == observed                                     # the failures stay on the record


def test_a_sensor_that_stays_broken_asks_once_and_is_read_only_at_the_missions_cadence(tmp_path):
    home, key, body_id, target, clock, observed = _broken_sensor_mission(tmp_path)
    missions, requests = run(home, clock, ticks=24, step=3600.0)                  # one day
    assert missions["m:audit"].status != "ACHIEVED"
    assert _asks(requests, "m:audit") == ["SENSOR_FAILURE"]                      # the same one question
    later = _observed(home, "m:audit")[len(observed):]
    assert 20 <= len(later) <= 25 and all("not a regular file" in e["detail"] for e in later)   # hourly, no more


def test_a_sensor_that_reads_again_on_a_failing_world_turns_the_question_into_the_right_one(tmp_path):
    home, key, body_id, target, clock, observed = _broken_sensor_mission(tmp_path)
    target.rmdir()
    target.write_text("ok\nFATAL: ledger corrupt\n")                             # readable, and the fault is real
    missions, requests = run(home, clock, ticks=12, step=600.0)
    assert missions["m:audit"].status != "ACHIEVED"
    assert _asks(requests, "m:audit") == ["NO_STRATEGY"]                         # a failed check, not a sensor
    assert [e["why"] for e in events(home, "decision.withdrawn") if e["mission_id"] == "m:audit"]


def test_evidence_that_is_valid_but_too_narrow_never_proves_an_absence(tmp_path):
    """Scenario 8. A reading capped at 64 KiB of a 2.4 MiB log is authentic: its digest is the digest of exactly
    the bytes it read. It cannot prove that the whole log never mentions a phrase, so the mission stays open, the
    founder is told the cap is why, and nothing is certified. A phrase the same capped reading did find is proved."""
    home, key, body_id, data = make_body(tmp_path)
    log = data / "app.log"
    log.write_bytes(b"service healthy\n" * (150 * 1024) + b"FATAL: ledger corrupt\n")
    cap = 64 * 1024
    _submit(home, key, body_id, "m:capped", [_never("clean", log, "FATAL", max_bytes=cap)])
    _submit(home, key, body_id, "m:seen", [_mentions("seen", log, "service healthy", max_bytes=cap)])
    missions, requests = run(home, Clock(), ticks=12, step=600.0)
    assert missions["m:capped"].status != "ACHIEVED"
    capped = _observed(home, "m:capped")
    assert capped and not any(e["passed"] for e in capped)
    assert all(f"byte limit: read the first {cap} bytes" in e["detail"] for e in capped)
    assert _asks(requests, "m:capped") == ["SENSOR_FAILURE"]                     # not a claim that FATAL is there
    assert not [e for e in events(home, "mission.appraised") if e["mission_id"] == "m:capped"]
    with Body(home) as body:                                                      # the reading names its bytes
        output = body.ledger.find(capped[-1]["receipt"]).payload["result"]["output"]
    assert output["read_sha256"] == hashlib.sha256(log.read_bytes()[:cap]).hexdigest()
    assert output["bytes_read"] == cap and output["complete"] is False and output["stopped"].startswith("byte limit")
    assert missions["m:seen"].status == "ACHIEVED"                                # a found phrase is decided
    appraised = [e for e in events(home, "mission.appraised") if e["mission_id"] == "m:seen"]
    assert appraised and appraised[-1]["verdict"] == "VERIFIED"
