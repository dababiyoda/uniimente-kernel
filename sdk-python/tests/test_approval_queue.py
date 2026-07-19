"""Tests for the approval queue. Stdlib unittest only."""

import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, UTC

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "policy"))

from uniimente_kernel.ledger import DecisionLedger, KillSwitch  # noqa: E402
from approval_queue import ApprovalQueue, ApprovalRecord, InMemoryApprovalStore  # noqa: E402


class TestApprovalQueue(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.ledger = DecisionLedger(path=os.path.join(self.dir.name, "l.jsonl"))
        self.sw = KillSwitch(ledger=self.ledger, initially_armed=True)
        self.store = InMemoryApprovalStore()
        self.sent = []
        self.q = ApprovalQueue(self.store, self.ledger, self.sw,
                               notify=lambda msg: self.sent.append(msg) or True)

    def tearDown(self):
        self.dir.cleanup()

    def test_request_prompts_and_ledgers(self):
        r = self.q.request_approval("post", "Publish X?", priority="P1")
        self.assertEqual(len(self.sent), 1)
        self.assertIn(r.code, self.sent[0])
        self.assertEqual(len(self.ledger.replay(event="operator_prompted")), 1)

    def test_duplicates_collapse(self):
        p = {"content": "same"}
        r1 = self.q.request_approval("post", "s", payload=p)
        r2 = self.q.request_approval("post", "s", payload=p)
        self.assertEqual(r1.id, r2.id)

    def test_yes_by_code_approves_only_that(self):
        r = self.q.request_approval("post", "Publish X?")
        out = self.q.handle_command(f"YES {r.code}")
        self.assertTrue(out["ok"])
        self.assertEqual(self.store.all()[0].status, "approved")
        self.assertIn("only this request", out["reply"])

    def test_bare_yes_requires_p1(self):
        self.q.request_approval("post", "low stakes", priority="P2")
        out = self.q.handle_command("YES")
        self.assertFalse(out["ok"])

    def test_bare_yes_single_p1_works(self):
        self.q.request_approval("post", "urgent", priority="P1")
        out = self.q.handle_command("YES")
        self.assertTrue(out["ok"])

    def test_ambiguous_code_rejected(self):
        r1 = self.q.request_approval("a", "one")
        r2 = self.q.request_approval("b", "two")
        # force colliding codes
        r2.code = r1.code
        self.store.put(r2)
        out = self.q.handle_command(f"YES {r1.code}")
        self.assertFalse(out["ok"])

    def test_edit_replaces_payload(self):
        r = self.q.request_approval("post", "Publish X?")
        out = self.q.handle_command(f"EDIT {r.code} better text")
        self.assertTrue(out["ok"])
        self.assertEqual(self.store.all()[0].payload["operator_edit"], "better text")

    def test_hold_then_yes(self):
        r = self.q.request_approval("post", "Publish X?")
        self.q.handle_command(f"HOLD {r.code}")
        self.assertEqual(self.store.all()[0].status, "held")
        out = self.q.handle_command(f"YES {r.code}")
        self.assertTrue(out["ok"])

    def test_freeze_disarms(self):
        out = self.q.handle_command("FREEZE")
        self.assertTrue(out["ok"])
        self.assertFalse(self.sw.armed)

    def test_expiry_sweep_never_consents(self):
        r = self.q.request_approval("post", "old", ttl_hours=1)
        r.expires_at = datetime.now(UTC) - timedelta(hours=2)
        self.store.put(r)
        out = self.q.handle_command(f"YES {r.code}")
        self.assertFalse(out["ok"])
        self.assertEqual(self.store.all()[0].status, "expired")

    def test_opinion_weighed_not_obeyed(self):
        out = self.q.handle_command("OPINION: ship faster")
        self.assertTrue(out["ok"])
        self.assertIn("not obey it", out["reply"])

    def test_why_explains(self):
        r = self.q.request_approval("post", "Publish X?", rationale="evidence strong")
        out = self.q.handle_command(f"WHY {r.code}")
        self.assertIn("evidence strong", out["reply"])

    def test_every_command_ledgers(self):
        self.q.handle_command("NOPE")
        self.assertTrue(any(e["payload"]["command"] == "NOPE"
                            for e in self.ledger.replay(event="operator_command")))


if __name__ == "__main__":
    unittest.main()
