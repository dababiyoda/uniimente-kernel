"""Node N2's prerequisite: a no-model mission that must form a capability and still meet founder approval.

"Verify <file> against sha256 <hex>" needs a hashing function GREG does not have. Capability
Genesis acquires an installed tool and verifies it against a frozen oracle before it may attach;
filing the verification record is a write outside the read-only cone, so it stops for approval;
and the record `requires` the digest check, so a mismatched file is never recorded as verified.
The separate-process appraiser independently confirms every gated action ran only after its
precondition was observed passing.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from greg import genesis as genesis_mod
from greg import path as devpath
from greg.body import Body, Layout
from greg.capabilities import BUILTINS
from greg.missions import MissionError, validate_mission
from greg.planner import PlannerContext, template_route
from greg.templates import verify_download
from tests.greg_fixtures import Clock, drop, make_body, signed

pytestmark = pytest.mark.skipif(genesis_mod.installed_binary("sha256sum") is None
                                and genesis_mod.installed_binary("shasum") is None,
                                reason="no sha256 tool installed; genesis would correctly escalate")
PAYLOAD = b"founder download bytes\n"
DIGEST = hashlib.sha256(PAYLOAD).hexdigest()


def body_with_file(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    target = data / "tool.tar.gz"
    target.write_bytes(PAYLOAD)
    return home, key, body_id, data, target


def run(home, clock, ticks):
    with Body(home, clock=clock) as body:
        for _ in range(ticks):
            body.tick()
            clock.advance(1)


def events(home, kind):
    with Body(home) as body:
        return [e.payload for e in body.journal.replay(kind)]


def test_plain_words_draft_a_no_model_genesis_mission_and_refuse_what_greg_cannot_read(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "tool.tar.gz").write_bytes(PAYLOAD)
    ctx = PlannerContext(read_roots=(str(data),), capabilities=[], workspace=tmp_path / "ws")
    proposal = template_route(f"Verify {data / 'tool.tar.gz'} against sha256 {DIGEST.upper()}", ctx)
    assert proposal["status"] == "PROPOSED" and proposal["origin"] == "template:verify-download"
    spec = validate_mission(proposal["spec"])
    assert spec["strategies"][0]["requires"] == ["digest_matches"]
    assert spec["success_checks"][0]["sensor"]["function"] == "hash.sha256"      # no built-in: genesis must form it
    assert spec["light_cone"]["max_consequence_class"] == "read_only" and spec["auto_attach"]
    outside = template_route(f"Verify /etc/hostname against sha256 {DIGEST}", ctx)
    assert outside["status"] == "NEEDS_INPUT" and "may only read under" in outside["questions"][0]
    missing = template_route(f"Verify {data / 'nope.bin'} against sha256 {DIGEST}", ctx)
    assert missing["status"] == "NEEDS_INPUT" and "does not exist" in missing["questions"][0]
    assert template_route("check my failing PRs", ctx)["origin"] == "template:engineering-brief"  # unchanged


def test_a_matching_file_forms_a_capability_asks_before_filing_and_closes_verified(tmp_path):
    home, key, body_id, data, target = body_with_file(tmp_path)
    spec = verify_download(file=target, sha256=DIGEST, workspace_root=Layout(home).workspace)
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    run(home, clock, 3)
    record = Layout(home).workspace / "m_verify-tool-tar-gz" / "tool.tar.gz.sha256"
    resolved = events(home, "deficit.resolved")
    assert resolved and not resolved[0]["capability_id"].startswith(("fs.", "brief.", "git."))   # formed, not built in
    [ask] = [r for r in events(home, "decision.requested") if r["kind"] == "APPROVAL"]
    assert not record.exists()                                                  # nothing filed before approval
    drop(home, signed(key, body_id, "DECISION", {"request_id": ask["request_id"], "answer": "approve"}))
    run(home, clock, 4)
    assert record.read_text() == f"{DIGEST}  tool.tar.gz\n"
    [appraisal] = events(home, "mission.appraised")
    assert appraisal["verdict"] == "VERIFIED", appraisal["findings"]
    assert appraisal["checks"]["preconditions_honored"] is True
    with Body(home) as body:                     # N2's genesis half; the VEPMC half needs the body run (rehearsal)
        seq = {r.payload.get("event_id"): r.seq for r in body.ledger.by_type("event")}
        resolved = next(e for e in body.journal.replay("deficit.resolved"))
        achieved = next(e for e in body.journal.replay("mission.achieved"))
        assert resolved.payload["capability_id"] not in BUILTINS and seq[resolved.event_id] < seq[achieved.event_id]
        assert devpath.PREDICATES["genesis_closure"](body.journal)["met"] is False   # never counted without VEPMC


def test_a_file_that_does_not_match_is_never_recorded_as_verified(tmp_path):
    home, key, body_id, data, target = body_with_file(tmp_path)
    spec = verify_download(file=target, sha256="0" * 64, workspace_root=Layout(home).workspace)
    drop(home, signed(key, body_id, "MISSION", spec))
    run(home, Clock(), 5)
    assert not [a for a in events(home, "mission.action") if a["action_id"] == "file-record"]
    assert not [r for r in events(home, "decision.requested") if r["kind"] == "APPROVAL"]   # never even asks
    [blocked] = [r for r in events(home, "decision.requested") if r["kind"] == "NO_STRATEGY"]
    assert "digest_matches" in blocked["why_now"]
    assert blocked["evidence"]["held_by_precondition"] == {"file-record": ["digest_matches"]}
    assert not (Layout(home).workspace / "m_verify-tool-tar-gz" / "tool.tar.gz.sha256").exists()   # no false record


@pytest.mark.parametrize("change, message", [
    (lambda s: s["strategies"][0].update(requires=["no-such-check"]), "requires unknown checks"),
    (lambda s: s["strategies"][0].update(requires=["recorded"]), "cannot require a check it advances"),
])
def test_preconditions_must_name_real_checks_the_strategy_does_not_itself_advance(tmp_path, change, message):
    spec = verify_download(file=tmp_path / "x", sha256=DIGEST, workspace_root=tmp_path)
    change(spec)
    with pytest.raises(MissionError, match=message):
        validate_mission(spec)


def test_the_appraiser_refutes_a_gated_action_that_ran_before_its_precondition_passed(tmp_path):
    home, key, body_id, data, target = body_with_file(tmp_path)
    spec = verify_download(file=target, sha256=DIGEST, workspace_root=Layout(home).workspace)
    mid = spec["mission_id"]
    with Body(home) as body:                      # a crafted history: what a faulty engine would leave behind
        j = body.journal
        j.record("mission.registered", {"mission_id": mid, "spec": spec, "command_digest": "x"}, key=mid)
        j.record("mission.observed", {"mission_id": mid, "check_id": "digest_matches", "passed": False,
                                      "detail": "sensor mismatch", "receipt": None, "rung": 0, "at": "t"}, key=[mid, 1])
        j.record("mission.action", {"mission_id": mid, "action_id": "file-record", "attempt": 0, "status": "DONE",
                                    "reasons": [], "receipt": None, "capability": "fs.write", "route": "api",
                                    "cost_usd": 0.0, "scope_digest": "s", "at": "t"}, key=[mid, 2])
        j.record("mission.achieved", {"mission_id": mid, "evidence": []}, key=[mid, "achieved"])
        verdict = body.appraise(mid)
    assert verdict["checks"]["preconditions_honored"] is False and verdict["verdict"] == "REFUTED"
    assert any("ran before digest_matches was observed passing" in f for f in verdict["findings"])


@pytest.mark.skipif(genesis_mod.installed_binary("wc") is None, reason="no wc installed")
@pytest.mark.parametrize("phrase, limit", [("under 5 words", 4), ("at most 5 words", 5), ("no more than 5 words", 5)])
def test_a_word_limit_is_read_exactly_as_said(tmp_path, phrase, limit):
    data = tmp_path / "data"
    data.mkdir()
    (data / "draft.md").write_text("one two three four\n")
    ctx = PlannerContext(read_roots=(str(data),), capabilities=[], workspace=tmp_path / "ws")
    proposal = template_route(f"Confirm {data / 'draft.md'} is {phrase}", ctx)
    assert proposal["origin"] == "template:word-limit" and proposal["status"] == "PROPOSED"
    check = proposal["spec"]["success_checks"][0]
    assert check["sensor"]["function"] == "text.wordcount" and check["predicate"] == {"op": "lte", "field": "words",
                                                                                          "value": limit}


@pytest.mark.skipif(genesis_mod.installed_binary("wc") is None, reason="no wc installed")
@pytest.mark.parametrize("text, within", [("one two three\n", True), ("one two three four five six\n", False)])
def test_a_draft_is_recorded_within_the_limit_only_when_it_is(tmp_path, text, within):
    from greg.templates import word_limit
    home, key, body_id, data = make_body(tmp_path)
    draft = data / "draft.md"
    draft.write_text(text)
    drop(home, signed(key, body_id, "MISSION", word_limit(file=draft, max_words=4, workspace_root=Layout(home).workspace)))
    clock = Clock()
    run(home, clock, 3)
    record = Layout(home).workspace / "m_words-draft-md" / "draft.md.words"
    asks = [r for r in events(home, "decision.requested") if r["kind"] == "APPROVAL"]
    assert bool(asks) is within and not record.exists()
    if within:
        drop(home, signed(key, body_id, "DECISION", {"request_id": asks[0]["request_id"], "answer": "approve"}))
        run(home, clock, 4)
        assert record.read_text() == "draft.md: at most 4 words (checked by GREG)\n"
        [appraisal] = events(home, "mission.appraised")
        assert appraisal["verdict"] == "VERIFIED" and appraisal["checks"]["preconditions_honored"]
        assert events(home, "deficit.resolved")[0]["capability_id"].startswith("acquired.text.wordcount")
