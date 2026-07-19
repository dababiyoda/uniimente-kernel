"""Tests for the generalized capability service. Stdlib unittest only."""

import os
import sys
import tempfile
import unittest
from datetime import timedelta, datetime, UTC

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from uniimente_kernel.ledger import DecisionLedger  # noqa: E402
from uniimente_kernel.capability import (  # noqa: E402
    CapabilityError,
    CapabilityService,
    GrantRecord,
    InMemoryGrantStore,
)


def make_service(tmp, *, approved=True, crisis=None):
    ledger = DecisionLedger(path=os.path.join(tmp, "ledger.jsonl"))
    store = InMemoryGrantStore()
    svc = CapabilityService(
        store, ledger,
        approval_verifier=lambda aid: approved,
        crisis_check=crisis,
    )
    return svc, store, ledger


def make_grant(**kw):
    base = dict(
        grantee="spiffe://uniimente.internal/organ/daleobanks/publisher",
        granted_by="spiffe://uniimente.internal/alfonso",
        legal_actor="alfonso_lopez",
        objective="test",
        permitted_actions=["post.reply"],
        resource="x:account:@daleobanks",
        spending_limit_usd=0.0,
        maximum_uses=1,
        initial_stage="simulate",
        revocable_by=["spiffe://uniimente.internal/alfonso"],
    )
    base.update(kw)
    return GrantRecord(**base)


class TestMint(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.dir.cleanup()

    def test_mint_requires_verified_approval(self):
        svc, store, ledger = make_service(self.dir.name, approved=False)
        with self.assertRaises(CapabilityError):
            svc.mint(make_grant(), approval_request_id="a1")
        self.assertTrue(any(e["payload"].get("reason") == "approval_unverified"
                            for e in ledger.replay(event="capability_rejected")))

    def test_verifier_exception_fails_closed(self):
        ledger = DecisionLedger(path=os.path.join(self.dir.name, "l.jsonl"))
        svc = CapabilityService(InMemoryGrantStore(), ledger,
                                approval_verifier=lambda aid: 1 / 0)
        with self.assertRaises(CapabilityError):
            svc.mint(make_grant(), approval_request_id="a1")

    def test_executable_stage_rejected_at_issuance(self):
        svc, store, ledger = make_service(self.dir.name)
        with self.assertRaises(CapabilityError):
            svc.mint(make_grant(initial_stage="execute"), approval_request_id="a1")

    def test_child_grant_must_be_subset(self):
        svc, store, ledger = make_service(self.dir.name)
        parent = svc.mint(make_grant(), approval_request_id="a1")
        child = make_grant(permitted_actions=["post.reply", "post.create"],
                           parent_grant=parent.grant_id)
        with self.assertRaises(CapabilityError):
            svc.mint(child, approval_request_id="a2")

    def test_child_grant_subset_ok(self):
        svc, store, ledger = make_service(self.dir.name)
        parent = svc.mint(make_grant(maximum_uses=5), approval_request_id="a1")
        child = svc.mint(make_grant(parent_grant=parent.grant_id), approval_request_id="a2")
        self.assertIsNotNone(child.grant_id)


class TestValidateAndConsume(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.svc, self.store, self.ledger = make_service(self.dir.name)
        self.grant = self.svc.mint(make_grant(), approval_request_id="a1")

    def tearDown(self):
        self.dir.cleanup()

    def test_happy_path_consumes_once(self):
        g = self.svc.validate_and_consume(self.grant.grant_id, "post.reply", "x:account:@daleobanks")
        self.assertEqual(g.uses_consumed, 1)

    def test_replay_refused_when_exhausted(self):
        self.svc.validate_and_consume(self.grant.grant_id, "post.reply", "x:account:@daleobanks")
        with self.assertRaises(CapabilityError):
            self.svc.validate_and_consume(self.grant.grant_id, "post.reply", "x:account:@daleobanks")

    def test_action_mismatch(self):
        with self.assertRaises(CapabilityError):
            self.svc.validate_and_consume(self.grant.grant_id, "post.create", "x:account:@daleobanks")

    def test_resource_mismatch(self):
        with self.assertRaises(CapabilityError):
            self.svc.validate_and_consume(self.grant.grant_id, "post.reply", "x:account:@other")

    def test_target_mismatch(self):
        g = self.svc.mint(make_grant(named_targets=["@alice"], maximum_uses=5), approval_request_id="a2")
        with self.assertRaises(CapabilityError):
            self.svc.validate_and_consume(g.grant_id, "post.reply", "x:account:@daleobanks", target="@mallory")

    def test_cost_ceiling(self):
        g = self.svc.mint(make_grant(spending_limit_usd=1.0, maximum_uses=5), approval_request_id="a2")
        with self.assertRaises(CapabilityError):
            self.svc.validate_and_consume(g.grant_id, "post.reply", "x:account:@daleobanks", cost=5.0)

    def test_expired_grant_fails(self):
        g = self.svc.mint(make_grant(), approval_request_id="a2")
        g.expires_at = datetime.now(UTC) - timedelta(hours=1)
        self.store.put(g)
        with self.assertRaises(CapabilityError):
            self.svc.validate_and_consume(g.grant_id, "post.reply", "x:account:@daleobanks")

    def test_revoked_grant_fails(self):
        self.svc.revoke(self.grant.grant_id, revoked_by="spiffe://uniimente.internal/alfonso", reason="test")
        with self.assertRaises(CapabilityError):
            self.svc.validate_and_consume(self.grant.grant_id, "post.reply", "x:account:@daleobanks")

    def test_broken_ledger_disarms_everything(self):
        path = self.ledger.path
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        lines[0] = lines[0].replace("capability_granted", "capability_forced")
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        with self.assertRaises(CapabilityError):
            self.svc.validate_and_consume(self.grant.grant_id, "post.reply", "x:account:@daleobanks")

    def test_crisis_unreadable_fails_closed(self):
        svc, store, ledger = make_service(self.dir.name, crisis=lambda: 1 / 0)
        g = svc.mint(make_grant(), approval_request_id="a9")
        with self.assertRaises(CapabilityError):
            svc.validate_and_consume(g.grant_id, "post.reply", "x:account:@daleobanks")

    def test_crisis_paused_fails_closed(self):
        svc, store, ledger = make_service(self.dir.name, crisis=lambda: True)
        g = svc.mint(make_grant(), approval_request_id="a9")
        with self.assertRaises(CapabilityError):
            svc.validate_and_consume(g.grant_id, "post.reply", "x:account:@daleobanks")


if __name__ == "__main__":
    unittest.main()
