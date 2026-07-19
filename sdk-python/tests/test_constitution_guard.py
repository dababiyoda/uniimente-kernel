"""Tests for the constitution guard. Stdlib unittest only."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "policy"))

from uniimente_kernel.ledger import DecisionLedger, KillSwitch  # noqa: E402
from constitution_check import ConstitutionGuard  # noqa: E402


class TestConstitutionGuard(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.dir.name, "constitution.ucl")
        with open(self.path, "w") as f:
            f.write('constitution "uniimente" { version = "1.0.0" }\n')
        self.ledger = DecisionLedger(path=os.path.join(self.dir.name, "l.jsonl"))
        self.applied = []
        self.sw = KillSwitch(ledger=self.ledger, apply=self.applied.append, initially_armed=True)
        self.guard = ConstitutionGuard([self.path], ledger=self.ledger, kill_switch=self.sw)

    def tearDown(self):
        self.dir.cleanup()

    def test_load_records_hash(self):
        h = self.guard.load_and_record()
        self.assertIsNotNone(h)
        self.assertEqual(len(self.ledger.replay(event="constitution_hash")), 1)

    def test_verify_passes_when_unchanged(self):
        self.guard.load_and_record()
        self.assertTrue(self.guard.verify())
        self.assertEqual(self.applied, [])

    def test_drift_disarms_and_ledgers(self):
        self.guard.load_and_record()
        with open(self.path, "a") as f:
            f.write("// tampered\n")
        self.assertFalse(self.guard.verify())
        self.assertEqual(self.applied, [False])
        self.assertEqual(len(self.ledger.replay(event="constitution_tampered")), 1)

    def test_missing_file_ledgers(self):
        guard = ConstitutionGuard([os.path.join(self.dir.name, "nope.ucl")],
                                  ledger=self.ledger, kill_switch=self.sw)
        self.assertIsNone(guard.load_and_record())
        self.assertEqual(len(self.ledger.replay(event="constitution_missing")), 1)
        # nothing recorded -> verify trivially true, armed state untouched
        self.assertTrue(guard.verify())


if __name__ == "__main__":
    unittest.main()
