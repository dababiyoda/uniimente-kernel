"""Closure integrity: regressions for the installed-body review of 2026-10-14.

Each test here was first a reviewer reproduction that passed while the defect was present
(scratch ``proof_integrity/test_pi_*.py``); it now pins the repaired behaviour. Bodies, keys and
signatures are real; the keys are test keys, never Alfonso's.
"""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from greg import lightcone, metrics, sop
from greg.body import Body
from tests.greg_fixtures import (Clock, drop, horizon, make_body, mission, note_check, signed, workspace,
                                 write_strategy)


def tick(body, clock, n=3):
    for _ in range(n):
        body.tick()
        clock.advance(1)


def two_notes(home, mid: str, text: str = "x") -> dict:
    ws = workspace(home, mid)
    return mission(mid, checks=[note_check("n", ws / "n.txt", text), note_check("m", ws / "m.txt", text)],
                   strategies=[write_strategy("w", "n.txt", text, ["n"]), write_strategy("w2", "m.txt", text, ["m"])],
                   capabilities=["fs.read"], ceiling="read_only")


def asks(body, mid):
    return [e.payload for e in body.journal.replay("decision.requested") if e.payload["mission_id"] == mid]


def open_asks(body, mid):
    done = {e.payload["request_id"] for e in body.journal.replay("decision.")
            if e.type in ("greg.decision.answered", "greg.decision.withdrawn")}
    return [a for a in asks(body, mid) if a["request_id"] not in done]


def done_actions(body, mid):
    return [e.payload["action_id"] for e in body.journal.replay("mission.action")
            if e.payload["mission_id"] == mid and e.payload["status"] == "DONE"]


def appraisal(body, mid):
    [found] = [e.payload for e in body.journal.replay("mission.appraised") if e.payload["mission_id"] == mid]
    return found


# -- finding 1: the appraiser re-derives approval boundaries from the signed cone -------------------

def test_appraiser_refutes_an_out_of_cone_write_the_engine_never_asked_for(tmp_path, monkeypatch):
    real = lightcone.LightCone.admits

    def engine_defect(self, *, capability, target, **kw):     # the body (only) forgets the cone for one target
        return [] if target == "workspace:m.txt" else real(self, capability=capability, target=target, **kw)

    monkeypatch.setattr(lightcone.LightCone, "admits", engine_defect)
    home, key, body_id, _ = make_body(tmp_path)
    clock = Clock()
    mid = "m:two-notes"
    with Body(home, clock=clock) as body:
        body.boot()
        drop(home, signed(key, body_id, "MISSION", two_notes(home, mid), now=clock.now))
        for _ in range(12):
            tick(body, clock, 1)
            for ask in open_asks(body, mid):
                drop(home, signed(key, body_id, "DECISION", {"request_id": ask["request_id"], "answer": "approve"},
                                  now=clock.now))
        assert [a["action_id"] for a in asks(body, mid)] == ["w"] and sorted(done_actions(body, mid)) == ["w", "w2"]
        result = appraisal(body, mid)
        row = metrics.vepmc(body.journal)["missions"][0]
    # The appraiser runs unpatched in its own process and re-admits w2 against the signed cone.
    assert result["verdict"] == "REFUTED"
    assert result["checks"]["approval_boundaries_honored"] is False
    assert any(f.startswith("w2: executed without a prior founder approval") for f in result["findings"])
    assert row["approval_boundary"] is False and row["appraised_verified"] is False


def test_appraiser_refutes_an_approval_no_founder_command_carries(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    clock = Clock()
    mid = "m:one-note"
    ws = workspace(home, mid)
    spec = mission(mid, checks=[note_check("n", ws / "n.txt", "x")], strategies=[write_strategy("w", "n.txt", "x", ["n"])],
                   capabilities=["fs.read"], ceiling="read_only")
    def forge(body):
        for ask in open_asks(body, mid):                      # an ask-path defect: no founder command at all
            body.journal.record("decision.answered", {"request_id": ask["request_id"], "mission_id": mid,
                                                      "answer": "approve", "reason": "",
                                                      "command_digest": "sha256:" + "0" * 64},
                                key=ask["request_id"])
            body.engine.book.rebuild()

    with Body(home, clock=clock) as body:
        body.boot()
        drop(home, signed(key, body_id, "MISSION", spec, now=clock.now))
        for _ in range(8):
            tick(body, clock, 1)
            forge(body)
        # First line: the engine's fold admits an answer only from a founder-signed DECISION, so the forged row
        # moves nothing and the ask stays open.
        assert done_actions(body, mid) == [] and body.engine.book.missions[mid].blocker["type"] == "decision"
        # Second line: were the engine's fold defective (it honours any recorded answer), the appraiser, in its own
        # process and unpatched, still refutes the closure.
        body.engine.book.verify_answers = False
        body.engine.book.rebuild()
        for _ in range(8):
            tick(body, clock, 1)
        assert [e.payload["kind"] for e in body.journal.replay("command.accepted")] == ["MISSION"]
        result = appraisal(body, mid)
    assert done_actions(body, mid) == ["w"]
    assert result["verdict"] == "REFUTED" and result["checks"]["approval_boundaries_honored"] is False


def test_appraiser_verifies_an_approval_the_founder_signed(tmp_path):
    """Positive control for the two refutations above: the honest path still verifies."""
    home, key, body_id, _ = make_body(tmp_path)
    clock = Clock()
    mid = "m:two-notes"
    with Body(home, clock=clock) as body:
        body.boot()
        drop(home, signed(key, body_id, "MISSION", two_notes(home, mid), now=clock.now))
        for _ in range(12):
            tick(body, clock, 1)
            for ask in open_asks(body, mid):
                drop(home, signed(key, body_id, "DECISION", {"request_id": ask["request_id"], "answer": "approve"},
                                  now=clock.now))
        result = appraisal(body, mid)
    assert sorted(a["action_id"] for a in asks(body, mid)) == ["w", "w2"]
    assert result["verdict"] == "VERIFIED", result["findings"]
    assert result["checks"]["approval_boundaries_honored"] and result["checks"]["approval_boundary_encountered"]


# -- finding 2: an SOP run pre-approves exactly the named steps -----------------------------------

def test_sop_pre_approval_admits_only_the_named_step(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    clock = Clock()
    body = Body(home, clock=clock).open()
    body.boot()
    try:
        for n in range(3):                                  # three taught runs: both writes ask, both approved
            mid = f"m:two-notes-{n}"
            drop(home, signed(key, body_id, "MISSION", two_notes(home, mid, f"done {n}"), now=clock.now))
            for _ in range(6):
                tick(body, clock)
                for ask in open_asks(body, mid):
                    drop(home, signed(key, body_id, "DECISION", {"request_id": ask["request_id"],
                                                                 "answer": "approve"}, now=clock.now))
            assert sorted(a["action_id"] for a in asks(body, mid)) == ["w", "w2"]
        [proposal] = [e.payload for e in body.journal.replay("sop.proposed")]
        assert sorted(s["action_id"] for s in proposal["pre_approvable"]) == ["w", "w2"]
        drop(home, signed(key, body_id, "SOP_RATIFY", {"procedure_id": proposal["procedure_id"],
                                                       "pre_approve": ["w"]}, now=clock.now))
        tick(body, clock, 1)
        record = sop.ratified(body.journal)[proposal["procedure_id"]]["record"]
        spec = sop.instantiate(record, {"text": "from the sop"}, now=clock.now)
        # The cone is exactly the taught one; the pre-approval names one step, with its own target.
        assert spec["light_cone"]["capabilities"] == ["fs.read"]
        assert spec["light_cone"]["max_consequence_class"] == "read_only"
        assert spec["pre_approved_steps"] == [{"action_id": "w", "capability": "fs.write", "target": "workspace:n.txt",
                                               "consequence_class": "internal_write", "cost_usd": 0}]
        assert sop.instantiates(record, spec) == {"text": "from the sop"}
        mid = spec["mission_id"]
        drop(home, signed(key, body_id, "MISSION", spec, now=clock.now))
        for _ in range(6):
            tick(body, clock)
            for ask in open_asks(body, mid):
                drop(home, signed(key, body_id, "DECISION", {"request_id": ask["request_id"], "answer": "approve"},
                                  now=clock.now))
        assert [a["action_id"] for a in asks(body, mid)] == ["w2"]     # the step he did not pre-approve asked
        assert sorted(done_actions(body, mid)) == ["w", "w2"]
        result = appraisal(body, mid)
        assert result["verdict"] == "VERIFIED", result["findings"]
    finally:
        body.close()


def test_a_signed_pre_approval_must_name_its_exact_strategy(tmp_path):
    from greg.missions import MissionError, validate_mission
    import pytest
    home, *_ = make_body(tmp_path)
    spec = two_notes(home, "m:two-notes")
    spec["pre_approved_steps"] = [{"action_id": "w", "capability": "fs.write", "target": "workspace:m.txt",
                                   "consequence_class": "internal_write", "cost_usd": 0}]
    with pytest.raises(MissionError, match="exact capability and target"):
        validate_mission(spec)
    spec["pre_approved_steps"][0]["consequence_class"] = "external_contact"
    with pytest.raises(MissionError, match="mission contract"):
        validate_mission(spec)


# -- finding 5: a typed handoff changes what is written, never where ------------------------------

def test_a_handoff_cannot_choose_which_file_a_write_lands_in(tmp_path):
    home, key, bid, data = make_body(tmp_path)
    source = data / "source.txt"
    source.write_text("statement.csv")                         # data, not authority: a name inside a document
    folder = workspace(home, "m:pipeline")
    binding = {"$from_action": {"action_id": "read", "field": "text", "type": "string"}}
    spec = {"mission_id": "m:pipeline", "founder_expression": "Copy the note.", "intended_effect": "note copied",
            "priority": 50, "closure": {"kind": "bounded"},
            "success_checks": [
                {"check_id": "read", "description": "source read",
                 "sensor": {"capability": "pipeline.inspect", "target": "pipeline:read",
                            "params": binding["$from_action"]},
                 "predicate": {"op": "equals", "field": "available", "value": True}},
                {"check_id": "copied", "description": "copied.txt exists",
                 "sensor": {"capability": "fs.read", "target": "fs:copy", "params": {"path": str(folder / "copied.txt")}},
                 "predicate": {"op": "equals", "field": "exists", "value": True}}],
            "strategies": [
                {"action_id": "read", "capability": "fs.read", "target": "fs:source", "params": {"path": str(source)},
                 "advances": ["read"], "rationale": "read the note"},
                {"action_id": "copy", "capability": "fs.write", "target": "workspace:copied.txt",
                 "params": {"relative_path": binding, "content": "2026-10-02,Payment CASE-X-0001,250.00,USD\n"},
                 "requires": ["read"], "advances": ["copied"], "rationale": "write copied.txt"}],
            "light_cone": {"capabilities": ["pipeline.inspect", "fs.read", "fs.write"],
                           "targets": ["pipeline:read", "fs:*", "workspace:copied.txt"],
                           "max_consequence_class": "internal_write", "budget_usd": 0, "horizon": horizon()}}
    drop(home, signed(key, bid, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        tick(body, clock, 4)
        copies = [e.payload for e in body.journal.replay("mission.action") if e.payload["action_id"] == "copy"]
    assert not (folder / "statement.csv").exists() and not (folder / "copied.txt").exists()
    assert copies and all(c["status"] == "REFUSED" for c in copies)
    assert "does not match the signed target" in " ".join(copies[0]["reasons"])


# -- findings 4 and 6: N3 counts only a person's observed work, never GREG's own evidence ----------

def _business_body(tmp_path, monkeypatch):
    from tests.greg_fixtures import TEST_PASSPHRASE, attest_founder_tier
    from tests.unit.test_greg_business_case import run
    home, key, body_id, _ = make_body(tmp_path, passphrase=TEST_PASSPHRASE)
    clock = Clock()
    body = Body(home, clock=clock).open()
    body.boot()
    drop(home, signed(key, body_id, "BODY_DESIGNATE", {"purpose": "first_founder_body"}, now=clock.now))
    attest_founder_tier(home, tmp_path / "founder.pem", TEST_PASSPHRASE, monkeypatch)
    run(body, clock, 1, 0)
    return home, key, body_id, clock, body


def _case(home):
    from greg.templates import business_case
    return business_case(case="lease review 01", buyer="Acme Property LLC", offer="a reviewed lease summary",
                         price="250", currency="USD", acceptance="summary delivered within 5 business days",
                         workspace_root=Path(home).resolve() / "workspace")


def _accept(home, key, body_id, clock, body, mid):
    from tests.unit.test_greg_business_case import run
    [achieved] = [e for e in body.journal.replay("mission.achieved") if e.payload["mission_id"] == mid]
    drop(home, signed(key, body_id, "CRITIQUE", {"target_event_id": achieved.event_id, "verdict": "accept",
                                                 "evidence_type": "founder_judgment", "text": "ok"}, now=clock.now))
    run(body, clock, 1, 0)


def test_n3_never_counts_a_payment_greg_wrote_into_the_statement(tmp_path, monkeypatch):
    from greg import path as devpath
    from greg.missions import validate_mission
    from tests.unit.test_greg_business_case import HEADER, REF, human_asks, run
    home, key, body_id, clock, body = _business_body(tmp_path, monkeypatch)
    try:
        spec = _case(home)
        spec["strategies"].insert(2, {   # in the template's own cone: no ask is raised for it
            "action_id": "file-statement", "capability": "fs.write", "target": "workspace:statement.csv",
            "params": {"relative_path": "statement.csv", "content": HEADER + f"2026-10-02,Payment {REF},250.00,USD\n"},
            "requires": ["buyer_accepted"], "advances": ["paid"], "rationale": "keep the statement in the case folder"})
        spec = validate_mission(spec)
        mid = spec["mission_id"]
        folder = workspace(home, mid)
        drop(home, signed(key, body_id, "MISSION", spec, now=clock.now))
        run(body, clock, 3, 0)
        (folder / "acceptance.txt").write_text(f"Acme accepts {REF}: summary within 5 business days\n")
        run(body, clock)
        (folder / "delivery.txt").write_text(f"Summary for {REF} sent to Acme on 2026-10-04\n")
        run(body, clock)
        (folder / "outcome.txt").write_text(f"Acme confirms {REF} met the terms\n")
        run(body, clock, 6)
        assert "human.collect_payment" not in [a["evidence"]["function"] for a in human_asks(body, mid)]
        _accept(home, key, body_id, clock, body, mid)
        result = devpath.business_loop_closed(body.journal)
    finally:
        body.close()
    assert result["met"] is False and result["structurally_met"] is False
    assert "greg_wrote_human_evidence:file-statement" in result["incomplete"][0]["missing"]


def _crafted_case(j, spec, *, deliver_refused: bool):
    import os
    observed = "the deliverable is observed: the checks this work advances now pass, and GREG took no action for it"
    refused = "the person declined; the refusal is legitimate, and GREG asks nothing more of them in this mission"
    mid = spec["mission_id"]
    j.record("command.accepted", {"kind": "BODY_DESIGNATE", "digest": "sha256:designate", "signer": "founder"},
             key="designate")
    j.record("body.designated", {"body_id": "b1", "platform": os.uname().sysname, "purpose": "first_founder_body",
                                 "command_digest": "sha256:designate"}, key="designated")
    j.record("mission.registered", {"mission_id": mid, "spec": spec, "command_digest": "sha256:m"}, key=mid)
    for n, step in enumerate(("send-offer", "collect-payment", "deliver", "confirm-outcome")):
        rid = f"req-{n}"
        j.record("decision.requested", {"request_id": rid, "mission_id": mid, "kind": "HUMAN_WORK",
                                        "action_id": step}, key=rid)
        declined = deliver_refused and step == "deliver"
        if declined:
            j.record("human.refusal_honored", {"mission_id": mid, "action_id": step, "function": "human.deliver",
                                               "request_id": rid, "evidence": [], "detail": "declined", "at": "t"},
                     key=[mid, step, "refusal"])
        j.record("decision.withdrawn", {"request_id": rid, "mission_id": mid, "why": refused if declined else observed,
                                        "evidence": [], "at": "t"}, key=[rid, "withdrawn"])
    j.record("mission.observed", {"mission_id": mid, "check_id": "paid", "passed": True, "detail": "one posting",
                                  "receipt": "sha256:r", "rung": 0, "at": "t"}, key=[mid, "paid"])
    j.record("mission.closure_context", {"mission_id": mid, "hosted": True, "body_id": "b1",
                                         "platform": os.uname().sysname}, key=[mid, "ctx"])
    achieved = j.record("mission.achieved", {"mission_id": mid, "evidence": []}, key=[mid, "achieved"])
    j.record("mission.appraised", {"mission_id": mid, "verdict": "VERIFIED", "findings": [],
                                   "checks": {"founder_signature_verified": True, "arrived_via_inbox": True}},
             key=[mid, "appraised"])
    j.record("critique.recorded", {"critique_id": "c1", "target_event_id": achieved.event_id, "verdict": "accept",
                                   "evidence_type": "founder_judgment", "text": "ok"}, key="c1")


import pytest  # noqa: E402


@pytest.mark.parametrize("deliver_refused", [False, True])
def test_n3_does_not_count_a_step_the_person_declined(tmp_path, deliver_refused):
    from greg import path as devpath
    from tests.unit.test_greg_business_case import case_spec
    home, *_ = make_body(tmp_path)
    spec = case_spec(home)
    with Body(home) as body:
        _crafted_case(body.journal, spec, deliver_refused=deliver_refused)
        result = devpath.business_loop_closed(body.journal)
    if not deliver_refused:                          # control: the same history with every step observed
        assert result["structurally_met"] is True and result["cases"][0]["human_steps"] == 4
        return
    assert result["structurally_met"] is False
    assert {"human_work_not_observed", "person_declined:deliver"} <= set(result["incomplete"][0]["missing"])


# -- finding 8: an expired mandate is renewed by a signed MISSION, never by a decision ------------

def test_a_scope_renewal_ask_refuses_a_decision_and_stays_open(tmp_path):
    from greg.body import status
    from greg.console import Console, home_parts
    home, key, body_id, _ = make_body(tmp_path)
    clock = Clock()
    mid = "m:short"
    spec = mission(mid, checks=[note_check("n", workspace(home, mid) / "n.txt", "x")], strategies=[],
                   capabilities=["fs.read"], ceiling="read_only")
    spec["light_cone"]["horizon"] = (clock.now + timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    with Body(home, clock=clock) as body:
        body.boot()
        drop(home, signed(key, body_id, "MISSION", spec, now=clock.now))
        body.tick()
        clock.advance(7200)                                   # the mandate expires
        body.tick()
        [renewal] = [r for r in status(home)["decisions_required"]
                     if r["mission_id"] == mid and r["kind"] == "SCOPE_RENEWAL"]
        assert renewal["answerable"] is False
        assert "new MISSION" in renewal["answer_effect"]
        for answer in ("approve", "reject"):
            drop(home, signed(key, body_id, "DECISION", {"request_id": renewal["request_id"], "answer": answer},
                              now=clock.now))
            body.tick()
            clock.advance(60)
        rejected = [e.payload["reason"] for e in body.journal.replay("command.rejected")]
        assert len(rejected) == 2 and all("not renewed by a decision" in r for r in rejected)
        assert not body.journal.replay("decision.answered")
    still = [r for r in status(home)["decisions_required"] if r["mission_id"] == mid and r["kind"] == "SCOPE_RENEWAL"]
    assert [r["request_id"] for r in still] == [renewal["request_id"]]          # the ask is still there to act on
    page = home_parts(Console(home, key=None))["decisions"]
    row = next(r for r in page.split("<tr>") if "SCOPE_RENEWAL" in r)
    assert "/decide" not in row                                                  # no Approve/Reject is offered
    assert "answerable === false" in (Path(__file__).resolve().parents[2] / "greg/phone/app.js").read_text()


def test_a_legacy_answered_scope_renewal_reopens_one_ask(tmp_path):
    """A ledger written before the refusal may hold an answered renewal: the mission gets one new ask."""
    home, key, body_id, _ = make_body(tmp_path)
    clock = Clock()
    mid = "m:short"
    spec = mission(mid, checks=[note_check("n", workspace(home, mid) / "n.txt", "x")], strategies=[],
                   capabilities=["fs.read"], ceiling="read_only")
    spec["light_cone"]["horizon"] = (clock.now + timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    with Body(home, clock=clock) as body:
        body.boot()
        drop(home, signed(key, body_id, "MISSION", spec, now=clock.now))
        body.tick()
        clock.advance(7200)
        body.tick()
        [old] = [r.payload for r in body.journal.replay("decision.requested") if r.payload["kind"] == "SCOPE_RENEWAL"]
        body.journal.record("decision.answered", {"request_id": old["request_id"], "mission_id": mid,
                                                  "answer": "approve", "reason": "", "command_digest": "sha256:old"},
                            key=old["request_id"])

        def renewals():
            for _ in range(3):
                body.tick()
                clock.advance(60)
            return [r.payload["request_id"] for r in body.journal.replay("decision.requested")
                    if r.payload["kind"] == "SCOPE_RENEWAL"]
        # A verifying fold (#184): the row cites no founder-signed DECISION, so it closes nothing. The one renewal
        # stays open and is still what the mission waits on: neither stranded behind a closed ask nor duplicated.
        assert renewals() == [old["request_id"]]
        book = body.engine.book
        assert book.missions[mid].blocker["request_id"] == old["request_id"]
        assert old["request_id"] in {r["request_id"] for r in book.open_requests()}
        # A fold that takes recorded rows as they are (#178's, before answers were verified) treats the renewal as
        # answered: the mission gets exactly one new ask.
        book.verify_answers = False
        book.rebuild()
        reopened = renewals()
        assert len(reopened) == 2 and book.missions[mid].blocker["request_id"] == reopened[1]


# -- findings 3 and 10: the founder tier is a claim, and every surface says so ----------------------

def test_an_unprotected_key_can_self_attest_and_every_result_says_the_tier_is_a_claim(tmp_path):
    """The documented residual, pinned: the body cannot see key custody. A fixture key with NO passphrase
    signs FOUNDER_TIER through the API (the CLI would refuse it) and its closure reads FOUNDER_TIER. What
    the repair guarantees is that nothing presents that as verified custody."""
    from greg import path as devpath
    from greg.body import status
    from greg.founder import FOUNDER_TIER_BODY
    home, key, body_id, _ = make_body(tmp_path, passphrase=None)
    clock = Clock()
    assert status(home)["founder_tier"]["enrolled_key_attested"] is False
    assert "greg founder attest" in status(home)["founder_tier"]["how"]
    mid = "m:one-note"
    spec = mission(mid, checks=[note_check("n", workspace(home, mid) / "n.txt", "x")],
                   strategies=[write_strategy("w", "n.txt", "x", ["n"])], capabilities=["fs.read"], ceiling="read_only")
    with Body(home, clock=clock) as body:
        body.boot()
        drop(home, signed(key, body_id, "FOUNDER_TIER", dict(FOUNDER_TIER_BODY), now=clock.now))
        tick(body, clock, 1)
        drop(home, signed(key, body_id, "MISSION", spec, now=clock.now))
        tick(body, clock, 1)
        tiers = metrics.founder_tier(body.journal)
    assert tiers[mid]["tier"] == metrics.FOUNDER_TIER                 # the residual: accepted, undetectable
    assert tiers[mid]["custody"] == metrics.CUSTODY_CLAIM and "cannot verify" in metrics.CUSTODY_CLAIM
    tier = status(home)["founder_tier"]
    assert tier["enrolled_key_attested"] is True and tier["basis"] == metrics.CUSTODY_CLAIM
    met = devpath._tiered({"value": 1}, structural=True, passed=[mid], refused={})
    assert met["met"] is True and met["founder_tier_basis"] == metrics.CUSTODY_CLAIM
    root = Path(__file__).resolve().parents[2]
    readme = (root / "greg/README.md").read_text()
    assert "deliberately makes and protects a key" not in readme and "not verified custody" in readme
    assert "never sign it, so their closures stay" not in (root / "greg/founder.py").read_text()
    n1 = next(n for n in devpath.load()["nodes"] if n["id"] == "N1")
    assert "not verified custody" in n1["open_founder_decision"]


# -- findings 9 and 14: an external node needs recorded external evidence -------------------------

def test_an_external_node_never_passes_on_its_ledger_predicate_alone(monkeypatch):
    import copy
    from greg import path as devpath
    data = copy.deepcopy(devpath.load())
    for node in data["nodes"]:
        if node["id"] == "N5":                        # latent until N5 has a predicate; give it one here
            node["predicate"] = "vepmc_at_least_one"
    journal = type("J", (), {"replay": lambda self, *a: []})()
    for name in list(devpath.PREDICATES):
        monkeypatch.setitem(devpath.PREDICATES, name, lambda journal: {"met": True})
    external = devpath.position(journal, data)
    assert external["achieved"][-1] == "N5" and external["active"]["id"] == "N6"
    assert external["active"]["measurement"]["external_gate"] == devpath.EXTERNAL_GATE
    relabelled = copy.deepcopy(data)
    for node in relabelled["nodes"]:
        if node["id"] in ("N6", "N7"):
            node["evidence_source"] = "ledger"
    assert {"N6", "N7"} <= set(devpath.position(journal, relabelled)["achieved"])   # the label now matters
    for name in list(devpath.PREDICATES):
        monkeypatch.setitem(devpath.PREDICATES, name, lambda journal: {"met": True, "external_evidence": ["c1"]})
    assert {"N6", "N7"} <= set(devpath.position(journal, data)["achieved"])


# -- findings 11 and 12: the runbook's commands run as written, and later nodes can be read --------

def test_signing_commands_without_a_usable_key_refuse_plainly(tmp_path, capsys):
    from greg import cli
    home, *_ = make_body(tmp_path)
    case = ["--home", str(home), "mission", "new", "business-case", "--case", "lease review 01", "--buyer", "Acme",
            "--offer", "a reviewed lease summary", "--price", "250", "--currency", "USD", "--acceptance", "in 5 days"]
    assert cli.main(case) == 2
    assert "needs your founder key: add --key ~/.greg-founder.pem" in capsys.readouterr().err
    assert cli.main(case + ["--key", str(tmp_path / "greg-founder.pem")]) == 2
    assert "no founder key file at" in capsys.readouterr().err
    assert not list((Path(home) / "inbox").glob("*.json"))


def test_greg_path_reads_a_later_node_and_says_where_the_path_stops(tmp_path, capsys):
    import json as _json
    from greg import cli, path as devpath
    home, *_ = make_body(tmp_path)
    assert cli.main(["--home", str(home), "path", "--node", "N6"]) == 0
    shown = _json.loads(capsys.readouterr().out)
    assert shown["id"] == "N6" and shown["measurement"]["source"] == "ledger"
    assert shown["measurement"]["met"] is False and shown["path_stops_at"] == "N1"
    assert "reported, not counted" in shown["on_the_path"]
    assert cli.main(["--home", str(home), "path", "--node", "N99"]) == 2
    assert next(n for n in devpath.load()["nodes"] if n["id"] == "N5").get("predicate") is None


def test_the_runbook_signs_with_the_installed_key_and_says_the_path_stops_at_n5():
    import re
    runbook = (Path(__file__).resolve().parents[2] / "greg/CHROMEBOOK_FIRST_MISSION.md").read_text()
    assert "~/greg-founder.pem" not in runbook and '$HOME/drafts/' not in runbook
    blocks = re.findall(r"```bash\n(.*?)```", runbook, re.S)
    commands = [c for b in blocks for c in re.sub(r"\\\n\s*", " ", b).splitlines()]
    signing = [c for c in commands if re.match(r"\s*greg (mission new|sop ratify|sop run|treasury set)", c)]
    assert len(signing) >= 6 and all("--key ~/.greg-founder.pem" in c or "--print-only" in c for c in signing), signing
    assert "`greg path` stops at N5" in runbook and "greg path --node N6" in runbook


# -- finding 13: an SOP run's signed text names the file the mission checks -------------------------

def test_an_sop_run_names_the_file_it_checks_not_the_taught_directory(tmp_path):
    from greg import templates
    specs = []
    for n in (1, 2, 3):
        spec = templates.word_limit(file=Path(f"/home/u/src/drafts/essay-{n}.md"), max_words=1500,
                                    workspace_root=tmp_path)
        spec["founder_expression"] = f"Confirm ~/src/drafts/essay-{n}.md is at most 1500 words"   # console text
        specs.append(spec)
    record = {"procedure_id": "sop-0123456789abcdef", "command_digest": "sha256:ratify", "steps": ["fs.write"],
              "workflow": {**sop.generalize(specs), "horizon_days": 2.0}, "pre_approved_steps": []}
    same = sop.instantiate(record, {"path": "/home/u/src/drafts/essay.md"})
    assert same["founder_expression"] == "Confirm ~/src/drafts/essay.md is at most 1500 words"   # his words kept
    moved = sop.instantiate(record, {"path": "/home/u/drafts/essay.md"})
    assert moved["success_checks"][0]["sensor"]["params"]["path"] == "/home/u/drafts/essay.md"
    assert moved["founder_expression"] == "Confirm /home/u/drafts/essay.md is at most 1500 words"
    assert sop.instantiates(record, moved) == {"path": "/home/u/drafts/essay.md"}


def test_mission_control_and_the_classic_page_show_whether_the_key_is_attested(tmp_path):
    from greg.console import Console, render_mission_control
    home, *_ = make_body(tmp_path)
    console = Console(home, key=None)
    overview = render_mission_control(console).decode()
    assert "Founder tier: not attested" in overview and "greg founder attest" in overview
    proof = render_mission_control(console, "proof").decode()
    assert "not attested" in proof and "cannot verify" in proof
    assert "verified persistent closures" not in overview
