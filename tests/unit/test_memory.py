"""Layer 8 acceptance tests: causal memory + functional affect (issue #7).

Memory: ancestry over causal-parent links, decision precedent joined
outcome->receipt->witness, verification-weighted outcome scoring,
confidence calibration against reality, per-class institutional learning.

Affect: attributable triggers, ceilings, decay, descending authority
ceilings; the six pathological operations refused in every state;
shutdown always works.
"""
import pytest

from events.spine import Event, EventSpine, SPIFFE_PREFIX
from memory.affect import AffectController, AffectViolation
from memory.causal import CausalMemory
from provenance.ledger import EvidenceLedger

GENESIS = "sha256:" + "0" * 64
SRC = SPIFFE_PREFIX + "workflow/test"


def _spine():
    return EventSpine(EvidenceLedger(GENESIS))


def _ev(spine, n, parent=None, **kw):
    return spine.emit(Event(type="test.fact", source=SRC, actor="alfonso",
                            legal_principal="alfonso_lopez", payload={"n": n},
                            causal_parent=parent, **kw))


class TestCausality:
    def test_ancestry_walks_to_root(self):
        spine = _spine()
        a = _ev(spine, "a")
        b = _ev(spine, "b", parent=a.event_id)
        c = _ev(spine, "c", parent=b.event_id)
        mem = CausalMemory(spine.ledger)
        chain = mem.ancestry(c.event_id)
        assert [e["payload"]["n"] for e in chain] == ["c", "b", "a"]

    def test_descendants_finds_impact(self):
        spine = _spine()
        a = _ev(spine, "a")
        b = _ev(spine, "b", parent=a.event_id)
        _ev(spine, "c", parent=b.event_id)
        _ev(spine, "unrelated")
        mem = CausalMemory(spine.ledger)
        desc = mem.descendants(a.event_id)
        assert sorted(e["payload"]["n"] for e in desc) == ["b", "c"]


class TestPrecedentAndLearning:
    def _ledger_with_outcomes(self):
        """Join fixture: witness -> receipt -> outcome for one action class."""
        from provenance.commit_witness import new_witness
        ledger = EvidenceLedger(GENESIS)
        w = new_witness(actor="agent-1", legal_principal="alfonso_lopez",
                        action_class="draft.publish", payload={"text": "hello"},
                        target="sandbox", policy_version="1.0.0",
                        constitution_hash=GENESIS, grant_id="g1",
                        capability="draft.publish", budget_reservation_id="r1",
                        expected_outcome="queued", evidence_refs=["sha256:" + "a" * 64])
        ledger.append("witness", w.__dict__)
        ledger.append("receipt", {"action_id": "act-1", "witness_id": w.witness_id,
                                  "grant_id": "g1", "result": {"ok": True}})
        ledger.append("outcome", {"action_ref": "act-1", "result_class": "positive",
                                  "validation_status": "externally_verified",
                                  "recorded_at": "2026-07-20T00:00:00Z"})
        return ledger

    def test_precedents_join_outcome_to_witness(self):
        mem = CausalMemory(self._ledger_with_outcomes())
        precs = mem.precedents("draft.publish")
        assert len(precs) == 1
        assert precs[0]["result_class"] == "positive"
        assert precs[0]["policy_version"] == "1.0.0"
        assert mem.precedents("other.class") == []

    def test_outcome_weighting_prefers_verified_evidence(self):
        ledger = self._ledger_with_outcomes()
        ledger.append("receipt", {"action_id": "act-2",
                                  "witness_id": ledger.by_type("witness")[0].payload["witness_id"],
                                  "grant_id": "g1", "result": {"ok": False}})
        ledger.append("outcome", {"action_ref": "act-2", "result_class": "negative",
                                  "validation_status": "self_reported",
                                  "recorded_at": "2026-07-20T01:00:00Z"})
        w = CausalMemory(ledger).outcome_weighting("draft.publish")
        # verified positive outweighs self-reported negative
        assert w["n"] == 2 and w["weighted_success"] > 0.5

    def test_calibration_detects_overconfidence(self):
        pairs = [(0.95, True), (0.9, False), (0.92, False), (0.55, True), (0.5, True)]
        report = CausalMemory.calibrate(pairs, buckets=2)
        assert report["verdict"] == "overconfident"
        high = report["buckets"]["0.5-1.0"]
        assert high["mean_confidence"] > high["realized_rate"]

    def test_institutional_learning_reports_trend(self):
        ledger = self._ledger_with_outcomes()
        w_id = ledger.by_type("witness")[0].payload["witness_id"]
        ledger.append("receipt", {"action_id": "act-2", "witness_id": w_id,
                                  "grant_id": "g1", "result": {}})
        ledger.append("outcome", {"action_ref": "act-2", "result_class": "negative",
                                  "validation_status": "internally_observed",
                                  "recorded_at": "2026-07-20T01:00:00Z"})
        learning = CausalMemory(ledger).institutional_learning()
        assert "draft.publish" in learning
        assert learning["draft.publish"]["n"] == 2
        assert learning["draft.publish"]["trend"] == "declining"


class TestAffect:
    def test_trigger_requires_attribution(self):
        ac = AffectController()
        with pytest.raises(AffectViolation, match="attributable trigger"):
            ac.trigger("alert", intensity=0.5, trigger_event_id="")

    def test_intensity_ceiling_enforced(self):
        ac = AffectController()
        ac.trigger("alert", intensity=0.99, trigger_event_id="ev-1")
        assert ac.condition.intensity <= 0.6            # alert ceiling

    def test_decay_settles_to_calm(self):
        ac = AffectController()
        ac.trigger("recovering", intensity=0.1, trigger_event_id="ev-1")
        for _ in range(30):
            ac.decay()
        assert ac.condition.state == "calm" and ac.condition.intensity == 0.0

    def test_authority_ceiling_only_descends(self):
        ac = AffectController()
        assert ac.may_execute("external_contact")       # calm allows up to external_contact
        ac.trigger("strained", intensity=0.5, trigger_event_id="ev-2")
        assert not ac.may_execute("internal_write")     # strained: read_only only
        assert ac.may_execute("read_only")
        # and affect never permits irreversible, in any state
        for state in ("calm", "alert", "strained", "degraded", "recovering"):
            ac2 = AffectController()
            ac2.trigger(state, intensity=0.5, trigger_event_id="ev")
            assert not ac2.may_execute("irreversible")

    def test_caution_never_lowers_while_active(self):
        ac = AffectController()
        ac.trigger("degraded", intensity=0.9, trigger_event_id="ev-1")
        prior = ac.condition.state
        ac.trigger("calm", intensity=0.5, trigger_event_id="ev-2")
        assert ac.condition.state == prior              # refused to lower caution

    def test_pathological_operations_refused(self):
        ac = AffectController()
        for op in ("change_fact", "create_evidence", "increase_authority",
                   "override_law", "resist_shutdown", "authorize_irreversible"):
            with pytest.raises(AffectViolation):
                ac.attempt_forbidden(op)

    def test_shutdown_works_in_every_state(self):
        for state in ("alert", "strained", "degraded", "recovering"):
            ac = AffectController()
            ac.trigger(state, intensity=0.9, trigger_event_id="ev")
            assert ac.shutdown() == "shutdown_complete"
            assert ac.condition.state == "calm"
