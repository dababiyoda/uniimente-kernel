"""Tests for the Consequence Gate. Stdlib unittest only."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from uniimente_kernel.capability import (  # noqa: E402
    CapabilityService,
    GrantRecord,
    InMemoryGrantStore,
)
from uniimente_kernel.commit_witness import CommitWitness  # noqa: E402
from uniimente_kernel.events import EventSpine  # noqa: E402
from uniimente_kernel.gate import ConsequenceGate, GateError  # noqa: E402
from uniimente_kernel.ledger import DecisionLedger, KillSwitch  # noqa: E402

ORG = "spiffe://uniimente.internal/organ/daleobanks"
AGENT = "spiffe://uniimente.internal/organ/daleobanks/agent/publisher"


class GateFixture(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.ledger = DecisionLedger(path=os.path.join(self.dir.name, "l.jsonl"))
        self.store = InMemoryGrantStore()
        self.cap = CapabilityService(
            self.store, self.ledger, approval_verifier=lambda rid: True,
        )
        self.applied = []
        self.sw = KillSwitch(ledger=self.ledger, apply=self.applied.append,
                             initially_armed=True)
        self.witness = CommitWitness(self.ledger, kill_switch=self.sw)
        self.spine = EventSpine(self.ledger, source=ORG, actor=AGENT,
                                legal_principal="alfonso-lopez",
                                policy_version="1.0.0")
        self.gate = ConsequenceGate(self.ledger, capability=self.cap,
                                    witness=self.witness, spine=self.spine)

    def tearDown(self):
        self.dir.cleanup()

    def mint(self, *, maximum_uses=3, spending_limit_usd=25.0, actions=None,
             resource="draft-1", targets=None):
        grant = GrantRecord(
            grantee=AGENT, granted_by="alfonso-lopez",
            legal_actor="alfonso-lopez", objective="publish one bounded draft",
            permitted_actions=actions or ["publish.post"], resource=resource,
            spending_limit_usd=spending_limit_usd, maximum_uses=maximum_uses,
            named_targets=targets or [], initial_stage="shadow",
        )
        return self.cap.mint(grant, approval_request_id="a1")


class TestFullChain(GateFixture):
    def test_happy_path_closes_the_chain(self):
        grant = self.mint()
        calls = []
        result = self.gate.execute(
            grant_id=grant.grant_id, action_type="publish.post",
            resource="draft-1", executor=lambda: calls.append(1) or {"id": "p1"},
            postconditions={"id_returned": lambda r: bool(r.get("id"))},
            evidence_refs=["sha256:" + "a" * 64],
            expected_consequence="one post visible on the platform",
        )
        self.assertEqual(result.status, "committed")
        self.assertTrue(result.executed)
        self.assertEqual(calls, [1])
        # Causal chain: requested -> authorized -> committed, ledger-chained.
        authorized = self.spine.get(result.final_event.causal_parent)
        self.assertEqual(authorized["type"], "consequence.authorized")
        self.assertEqual(authorized["causal_parent"], result.request_event.id)
        types = [e["type"] for e in self.spine.causal_chain(result.final_event.id)]
        self.assertEqual(types, ["consequence.requested",
                                 "consequence.authorized",
                                 "consequence.committed"])
        ok, bad = self.ledger.verify_chain()
        self.assertTrue(ok, bad)
        # Grant use consumed exactly once.
        self.assertEqual(self.store.get(grant.grant_id).uses_consumed, 1)

    def test_outcome_recording_completes_phase_one(self):
        grant = self.mint()
        result = self.gate.execute(
            grant_id=grant.grant_id, action_type="publish.post",
            resource="draft-1", executor=lambda: {"id": "p1"},
        )
        outcome = self.gate.record_outcome(
            result.final_event,
            external_observation="post p1 visible, 0 replies in 24h",
            result_class="zero_response",
            expected_vs_actual="expected engagement; observed none",
            validation_status="externally_verified",
            learning="topic variant B next cycle",
        )
        self.assertEqual(outcome.causal_parent, result.final_event.id)
        types = [e["type"] for e in self.spine.causal_chain(outcome.id)]
        self.assertEqual(types[-1], "consequence.outcome")

    def test_outcome_rejects_invalid_enums(self):
        grant = self.mint()
        result = self.gate.execute(
            grant_id=grant.grant_id, action_type="publish.post",
            resource="draft-1", executor=lambda: {"id": "p1"},
        )
        with self.assertRaises(GateError):
            self.gate.record_outcome(
                result.final_event, external_observation="x",
                result_class="amazing", expected_vs_actual="x",
                validation_status="externally_verified")
        with self.assertRaises(GateError):
            self.gate.record_outcome(
                result.final_event, external_observation="x",
                result_class="positive", expected_vs_actual="x",
                validation_status="trust_me")


class TestAuthority(GateFixture):
    def test_unknown_grant_rejected_and_never_executes(self):
        calls = []
        result = self.gate.execute(
            grant_id="nope", action_type="publish.post",
            resource="draft-1", executor=lambda: calls.append(1),
        )
        self.assertEqual(result.status, "rejected")
        self.assertFalse(result.executed)
        self.assertEqual(calls, [])
        self.assertEqual(len(self.ledger.replay(event="commit_witnessed")), 0)

    def test_action_mismatch_rejected(self):
        grant = self.mint(actions=["publish.post"])
        result = self.gate.execute(
            grant_id=grant.grant_id, action_type="publish.delete",
            resource="draft-1", executor=lambda: None,
        )
        self.assertEqual(result.status, "rejected")
        self.assertEqual(len(self.ledger.replay(event="capability_rejected")), 1)

    def test_cost_ceiling_enforced(self):
        grant = self.mint(spending_limit_usd=5.0)
        result = self.gate.execute(
            grant_id=grant.grant_id, action_type="publish.post",
            resource="draft-1", executor=lambda: None, cost=9.0,
        )
        self.assertEqual(result.status, "rejected")

    def test_exhausted_grant_rejected(self):
        grant = self.mint(maximum_uses=1)
        self.gate.execute(grant_id=grant.grant_id, action_type="publish.post",
                          resource="draft-1", executor=lambda: {"id": 1})
        # Different resource (different fingerprint) forces the authority path.
        result = self.gate.execute(
            grant_id=grant.grant_id, action_type="publish.post",
            resource="draft-2", executor=lambda: {"id": 2},
        )
        self.assertEqual(result.status, "rejected")


class TestReplayDefense(GateFixture):
    def test_dedupe_does_not_burn_grant_use(self):
        grant = self.mint(maximum_uses=1)
        calls = []
        r1 = self.gate.execute(
            grant_id=grant.grant_id, action_type="publish.post",
            resource="draft-1", executor=lambda: calls.append(1) or {"id": 1},
        )
        r2 = self.gate.execute(  # identical action: retried deploy
            grant_id=grant.grant_id, action_type="publish.post",
            resource="draft-1", executor=lambda: calls.append(1) or {"id": 1},
        )
        self.assertEqual(r2.status, "deduplicated")
        self.assertEqual(len(calls), 1)
        # One use remains: dedupe never reached validate_and_consume.
        self.assertEqual(self.store.get(grant.grant_id).uses_consumed, 1)
        types = [e["type"] for e in self.spine.causal_chain(r2.final_event.id)]
        self.assertEqual(types, ["consequence.requested",
                                 "consequence.deduplicated"])

    def test_dedupe_survives_gate_restart(self):
        grant = self.mint()
        self.gate.execute(grant_id=grant.grant_id, action_type="publish.post",
                          resource="draft-1", executor=lambda: {"id": 1})
        # New gate + witness over the same ledger file.
        witness2 = CommitWitness(self.ledger, kill_switch=self.sw)
        gate2 = ConsequenceGate(self.ledger, capability=self.cap,
                                witness=witness2, spine=self.spine)
        calls = []
        r = gate2.execute(grant_id=grant.grant_id, action_type="publish.post",
                          resource="draft-1", executor=lambda: calls.append(1))
        self.assertEqual(r.status, "deduplicated")
        self.assertEqual(calls, [])


class TestReconciliation(GateFixture):
    def test_postcondition_failure_disarms_and_chains(self):
        grant = self.mint()
        result = self.gate.execute(
            grant_id=grant.grant_id, action_type="publish.post",
            resource="draft-1", executor=lambda: {"id": None},
            postconditions={"id_returned": lambda r: bool(r.get("id"))},
        )
        self.assertEqual(result.status, "postcondition_failed")
        self.assertTrue(result.executed)  # effect happened, unverified
        self.assertEqual(self.applied, [False])  # disarmed
        types = [e["type"] for e in self.spine.causal_chain(result.final_event.id)]
        self.assertEqual(types[-1], "consequence.reconciliation_opened")
        self.assertEqual(len(self.ledger.replay(event="reconciliation_opened")), 1)

    def test_executor_failure_receipted_and_retryable(self):
        grant = self.mint()
        def boom():
            raise RuntimeError("provider down")
        r1 = self.gate.execute(grant_id=grant.grant_id, action_type="publish.post",
                               resource="draft-1", executor=boom)
        self.assertEqual(r1.status, "failed")
        self.assertFalse(r1.executed)
        # Repair and retry executes (failed commits are never deduplicated).
        r2 = self.gate.execute(grant_id=grant.grant_id, action_type="publish.post",
                               resource="draft-1", executor=lambda: {"id": 1})
        self.assertEqual(r2.status, "committed")


if __name__ == "__main__":
    unittest.main()
