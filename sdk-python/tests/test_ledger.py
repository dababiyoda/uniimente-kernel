"""Tests for the generalized decision ledger, kill switch, and rate governor.

Runs on stdlib unittest only: python -m unittest discover -s sdk-python/tests
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from uniimente_kernel.ledger import (  # noqa: E402
    DecisionLedger,
    KillSwitch,
    RateGovernor,
)


def _valid_decision():
    return {
        "decision_id": "3f6b2a7c-0000-4000-8000-000000000001",
        "decider": "spiffe://uniimente.internal/organ/daleobanks/publisher",
        "legal_principal": "alfonso_lopez",
        "objective": "test objective",
        "question": "ship the extraction?",
        "options_considered": ["yes", "no"],
        "chosen": "yes",
        "rationale": "verifier green",
        "evidence_refs": [],
        "policy_version": "1.0.0",
        "reversibility": "reversible",
        "authority_chain": ["spiffe://uniimente.internal/organ/daleobanks/publisher"],
        "expected_outcome": "module importable by organs",
    }


class TestDecisionLedger(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.dir.name, "ledger.jsonl")
        self.ledger = DecisionLedger(path=self.path)

    def tearDown(self):
        self.dir.cleanup()

    def test_append_and_verify(self):
        self.ledger.record("boot", {"ok": True})
        self.ledger.record("decision", {"chosen": "yes"})
        ok, bad = self.ledger.verify_chain()
        self.assertTrue(ok)
        self.assertIsNone(bad)
        self.assertEqual(len(self.ledger.entries()), 2)

    def test_chain_detects_tampering(self):
        self.ledger.record("a")
        self.ledger.record("b")
        with open(self.path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        first = json.loads(lines[0])
        first["payload"] = {"forged": True}
        lines[0] = json.dumps(first) + "\n"
        with open(self.path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        ok, bad = self.ledger.verify_chain()
        self.assertFalse(ok)
        self.assertEqual(bad, 1)

    def test_corrupt_line_detected(self):
        self.ledger.record("a")
        with open(self.path, "a", encoding="utf-8") as f:
            f.write("not-json\n")
        ok, _ = self.ledger.verify_chain()
        self.assertFalse(ok)

    def test_replay_filter_and_limit(self):
        for i in range(5):
            self.ledger.record("tick", {"i": i})
        self.ledger.record("other")
        self.assertEqual(len(self.ledger.replay(event="tick")), 5)
        self.assertEqual(len(self.ledger.replay(limit=2)), 2)

    def test_record_decision_requires_all_fields(self):
        with self.assertRaises(ValueError):
            self.ledger.record_decision({"decision_id": "x"})
        self.assertEqual(len(self.ledger.entries()), 0)

    def test_record_decision_happy_path(self):
        entry = self.ledger.record_decision(_valid_decision())
        self.assertEqual(entry["event"], "decision")
        ok, _ = self.ledger.verify_chain()
        self.assertTrue(ok)

    def test_two_instances_serialize_appends(self):
        other = DecisionLedger(path=self.path)
        self.ledger.record("one")
        other.record("two")
        ok, _ = self.ledger.verify_chain()
        self.assertTrue(ok)
        self.assertEqual([e["seq"] for e in self.ledger.entries()], [1, 2])


class TestKillSwitch(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.ledger = DecisionLedger(path=os.path.join(self.dir.name, "l.jsonl"))

    def tearDown(self):
        self.dir.cleanup()

    def test_default_disarmed(self):
        sw = KillSwitch(ledger=self.ledger)
        self.assertFalse(sw.armed)

    def test_transitions_are_applied_and_ledgered(self):
        applied = []
        sw = KillSwitch(ledger=self.ledger, apply=applied.append)
        sw.set_armed(True, "human ceremony")
        sw.set_armed(False, "test over")
        self.assertEqual(applied, [True, False])
        events = self.ledger.replay(event="kill_switch")
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["payload"]["reason"], "human ceremony")

    def test_noop_when_unchanged(self):
        sw = KillSwitch(ledger=self.ledger)
        sw.set_armed(False, "already off")
        self.assertEqual(len(self.ledger.entries()), 0)


class TestRateGovernor(unittest.TestCase):
    def test_cap_enforced(self):
        gov = RateGovernor(max_actions=3, window_seconds=60)
        self.assertTrue(gov.allow("x"))
        self.assertTrue(gov.allow("x"))
        self.assertTrue(gov.allow("x"))
        self.assertFalse(gov.allow("x"))
        self.assertEqual(gov.remaining("x"), 0)

    def test_keys_are_independent(self):
        gov = RateGovernor(max_actions=1, window_seconds=60)
        self.assertTrue(gov.allow("a"))
        self.assertTrue(gov.allow("b"))
        self.assertFalse(gov.allow("a"))


if __name__ == "__main__":
    unittest.main()
