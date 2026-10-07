"""Signed claim settlement through the Body; test keys are not Alfonso's key."""
from greg.body import Body
from greg.cognition.contracts import digest
from greg.cognition.settlement import competence, measured_outcomes, reconcile
from tests.greg_fixtures import drop, make_body, mission, signed


def _two_claim_mission(home, key, body_id):
    checks = []
    for number in (1, 2):
        params = {"problem_id": "claim:arithmetic", "operation": "calculate",
                  "data": {"expression": f"{number}+{number}"}}
        checks.append({"check_id": f"sum-{number}", "description": f"exact sum {number}",
                       "sensor": {"capability": "cognition.solve", "target": "cognition:sum", "params": params},
                       "predicate": {"op": "equals", "field": "output.exact", "value": str(2 * number)}})
    spec = mission("m:two-cognitive-claims", checks=checks, strategies=[],
                   capabilities=["cognition.solve"], targets=("cognition:*",), ceiling="read_only")
    drop(home, signed(key, body_id, "MISSION", spec))
    return spec


def _latest_settlements(journal):
    return {event.payload["outcome_id"]: event for event in journal.replay("cognition.settled")}


def test_same_geometry_claims_settle_separately_and_corrections_replay(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    spec = _two_claim_mission(home, key, body_id)
    with Body(home) as body:
        body.boot()
        assert body.tick()["missions"][0]["state"] == "ACHIEVED"
        initial = body.journal.replay("cognition.settled")
        assert len(initial) == 2
        assert len({e.payload["outcome_id"] for e in initial}) == 2
        assert len({e.payload["input_digest"] for e in initial}) == 2
        assert len({e.payload["geometry_key"] for e in initial}) == 1
        assert {e.payload["check_id"] for e in initial} == {"sum-1", "sum-2"}
        registered = body.journal.replay("mission.registered")[0].payload
        for event in initial:
            check = next(c for c in spec["success_checks"] if c["check_id"] == event.payload["check_id"])
            assert event.payload["check_digest"] == digest(check)
            assert event.payload["command_digest"] == registered["command_digest"]
            assert event.payload["authority_created"] is False
            assert event.payload["supersedes"] is None
        assert next(iter(competence(body.journal).values()))["count"] == 2
        appraisal = body.journal.replay("mission.appraised")[-1].payload
        assert appraisal["verdict"] == "VERIFIED"
        receipt_count = len(body.ledger.by_type("receipt"))
        reconcile(body.journal)
        reconcile(body.journal)
        assert len(body.journal.replay("cognition.settled")) == 2

    with Body(home) as body:
        body.boot()
        body.tick()
        assert len(body.ledger.by_type("receipt")) == receipt_count
        assert len(body.journal.replay("cognition.settled")) == 2
        body.journal.record("mission.appraised", {"mission_id": spec["mission_id"], "verdict": "REFUTED", "checks": {}},
                            key="test-later-refutation")
        reconcile(body.journal)
        invalidations = _latest_settlements(body.journal)
        assert len(invalidations) == 2
        assert all(e.payload["invalidated"] for e in invalidations.values())
        assert {e.payload["supersedes"] for e in invalidations.values()} == {e.event_id for e in initial}
        assert competence(body.journal) == {}
        reconcile(body.journal)
        assert len(body.journal.replay("cognition.settled")) == 4

    with Body(home) as body:
        body.boot()
        body.tick()
        assert len(body.journal.replay("cognition.settled")) == 4
        assert competence(body.journal) == {}
        # This is a correction-contract test, not new external outcome evidence.
        body.journal.record("mission.appraised", appraisal, key="test-later-supported-correction")
        reconcile(body.journal)
        restored = _latest_settlements(body.journal)
        assert all(not e.payload["invalidated"] for e in restored.values())
        assert {e.payload["supersedes"] for e in restored.values()} == {e.event_id for e in invalidations.values()}
        assert next(iter(competence(body.journal).values()))["count"] == 2
        reconcile(body.journal)
        assert len(body.journal.replay("cognition.settled")) == 6

    with Body(home) as body:
        body.boot()
        body.tick()
        assert len(body.journal.replay("cognition.settled")) == 6
        assert len(body.ledger.by_type("receipt")) == receipt_count


def test_legacy_settlement_is_superseded_without_rewriting_history(tmp_path, monkeypatch):
    import greg.cognition.settlement as settlement

    home, key, body_id, _ = make_body(tmp_path)
    _two_claim_mission(home, key, body_id)
    with Body(home) as body:
        body.boot()
        with monkeypatch.context() as context:
            context.setattr(settlement, "reconcile", lambda journal: None)
            assert body.tick()["missions"][0]["state"] == "ACHIEVED"
        measured = measured_outcomes(body.journal)
        assert len(measured) == 2
        # Reproduce the old append-only payload, which had no signed claim fields.
        new_fields = {"input_digest", "check_id", "check_digest", "command_digest", "problem_id", "identity_version"}
        retained, priors = [], []
        for outcome in measured:
            legacy = {k: v for k, v in outcome.items() if k not in new_fields}
            legacy_id = digest({k: legacy[k] for k in ("mission_id", "method", "method_version", "geometry_key")})
            legacy.update(outcome_id=legacy_id, evidence_class="validated_local_computation", invalidated=False, supersedes=None)
            retained.append(legacy)
            priors.append(body.journal.record("cognition.settled", legacy,
                          key=[legacy_id, legacy["observation_event"], legacy["appraisal_event"]],
                          causal_parent=legacy["observation_event"]))
        assert len({e.payload["outcome_id"] for e in priors}) == 1
        reconcile(body.journal)
        records = body.journal.replay("cognition.settled")
        assert len(records) == 4
        assert [e.payload for e in records[:2]] == retained
        modern = records[2:]
        assert len({e.payload["outcome_id"] for e in modern}) == 2
        assert {e.payload["supersedes"] for e in modern} == {e.event_id for e in priors}
        assert all(not e.payload["invalidated"] for e in modern)
        assert next(iter(competence(body.journal).values()))["count"] == 2
        reconcile(body.journal)
        assert len(body.journal.replay("cognition.settled")) == 4
    with Body(home) as body:
        body.boot()
        body.tick()
        assert len(body.journal.replay("cognition.settled")) == 4
        body.journal.record("mission.appraised", {"mission_id": "m:two-cognitive-claims", "verdict": "REFUTED", "checks": {}},
                            key="test-legacy-refutation")
        reconcile(body.journal)
        assert len(body.journal.replay("cognition.settled")) == 6
        assert all(e.payload["invalidated"] for e in _latest_settlements(body.journal).values() if e.payload["outcome_id"] != legacy_id)
        assert competence(body.journal) == {}
        reconcile(body.journal)
        assert len(body.journal.replay("cognition.settled")) == 6


def test_return_to_same_evidence_appends_revision_instead_of_reusing_fact_identity(tmp_path, monkeypatch):
    import greg.cognition.settlement as settlement

    home, key, body_id, _ = make_body(tmp_path)
    _two_claim_mission(home, key, body_id)
    with Body(home) as body:
        body.boot()
        assert body.tick()["missions"][0]["state"] == "ACHIEVED"
        supported = _latest_settlements(body.journal)
        # Simulate temporary evidence unavailability, without manufacturing a new appraisal.
        with monkeypatch.context() as context:
            context.setattr(settlement, "measured_outcomes", lambda journal: [])
            reconcile(body.journal)
            reconcile(body.journal)
        invalidated = _latest_settlements(body.journal)
        assert all(e.payload["invalidated"] for e in invalidated.values())
        assert len(body.journal.replay("cognition.settled")) == 4
        reconcile(body.journal)
        restored = _latest_settlements(body.journal)
        assert len(body.journal.replay("cognition.settled")) == 6
        for identity, event in restored.items():
            assert not event.payload["invalidated"]
            assert event.payload["supersedes"] == invalidated[identity].event_id
            assert event.payload["appraisal_event"] == supported[identity].payload["appraisal_event"]
            assert event.payload["observation_event"] == supported[identity].payload["observation_event"]
            assert event.event_id != supported[identity].event_id
        reconcile(body.journal)
        assert len(body.journal.replay("cognition.settled")) == 6
    with Body(home) as body:
        body.boot()
        body.tick()
        assert len(body.journal.replay("cognition.settled")) == 6
