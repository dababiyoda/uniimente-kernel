"""Tests for the commit witness. Stdlib unittest only."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from uniimente_kernel.commit_witness import (  # noqa: E402
    CommitWitness,
    action_fingerprint,
)
from uniimente_kernel.ledger import DecisionLedger, KillSwitch  # noqa: E402


class TestCommitWitness(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.ledger = DecisionLedger(path=os.path.join(self.dir.name, "l.jsonl"))
        self.applied = []
        self.sw = KillSwitch(ledger=self.ledger, apply=self.applied.append, initially_armed=True)
        self.witness = CommitWitness(self.ledger, kill_switch=self.sw)

    def tearDown(self):
        self.dir.cleanup()

    def _run(self, **kw):
        calls = []
        def executor():
            calls.append(1)
            return {"ok": True, "id": "post-123"}
        kw.setdefault("grant_id", "g1")
        kw.setdefault("action_type", "publish.post")
        kw.setdefault("resource", "draft-1")
        kw.setdefault("executor", executor)
        return self.witness.commit(**kw), calls

    def test_executes_once_and_ledgers(self):
        receipt, calls = self._run()
        self.assertEqual(calls, [1])
        self.assertEqual(receipt.status, "committed")
        self.assertEqual(len(self.ledger.replay(event="commit_witnessed")), 1)
        self.assertEqual(len(self.ledger.replay(event="commit_executed")), 1)

    def test_same_fingerprint_never_reexecutes(self):
        r1, calls1 = self._run()
        r2, calls2 = self._run()  # identical action
        self.assertEqual(calls2, [])  # executor never ran again
        self.assertEqual(r2.status, "deduplicated")
        self.assertEqual(r2.result, r1.result)
        self.assertEqual(len(self.ledger.replay(event="commit_deduplicated")), 1)

    def test_different_parameters_are_different_actions(self):
        self._run()
        _, calls = self._run(parameters={"variant": "b"})
        self.assertEqual(calls, [1])

    def test_dedupe_survives_restart(self):
        self._run()
        witness2 = CommitWitness(self.ledger)  # new instance, same ledger file
        calls = []
        receipt = witness2.commit(grant_id="g1", action_type="publish.post",
                                  resource="draft-1", executor=lambda: calls.append(1))
        self.assertEqual(calls, [])
        self.assertEqual(receipt.status, "deduplicated")

    def test_executor_failure_is_receipted_not_raised(self):
        def boom():
            raise RuntimeError("provider down")
        receipt = self.witness.commit(grant_id="g1", action_type="publish.post",
                                      resource="draft-1", executor=boom)
        self.assertEqual(receipt.status, "failed")
        self.assertIn("provider down", receipt.error)
        # a failed commit is NOT deduplicated: retry after repair must execute
        self.assertFalse(self.witness.already_committed(receipt.fingerprint))

    def test_postcondition_failure_opens_reconciliation_and_disarms(self):
        receipt, _ = self._run(postconditions={"provider_confirmed": lambda r: False})
        self.assertEqual(receipt.status, "postcondition_failed")
        self.assertEqual(self.applied, [False])
        self.assertEqual(len(self.ledger.replay(event="reconciliation_opened")), 1)

    def test_postconditions_pass(self):
        receipt, _ = self._run(postconditions={
            "id_returned": lambda r: bool(r.get("id")),
            "ok_flag": lambda r: r.get("ok") is True,
        })
        self.assertEqual(receipt.status, "committed")
        self.assertEqual(len(receipt.postconditions), 2)

    def test_postcondition_failed_dedupes_across_restart(self):
        # The effect happened (unverified); a restart must not re-execute it.
        receipt, calls = self._run(postconditions={"provider_confirmed": lambda r: False})
        self.assertEqual(receipt.status, "postcondition_failed")
        witness2 = CommitWitness(self.ledger)  # new instance, same ledger file
        calls2 = []
        r2 = witness2.commit(grant_id="g1", action_type="publish.post",
                             resource="draft-1", executor=lambda: calls2.append(1))
        self.assertEqual(calls2, [])
        self.assertEqual(r2.status, "deduplicated")

    def test_failed_commit_retries_across_restart(self):
        def boom():
            raise RuntimeError("provider down")
        receipt = self.witness.commit(grant_id="g1", action_type="publish.post",
                                      resource="draft-1", executor=boom)
        self.assertEqual(receipt.status, "failed")
        witness2 = CommitWitness(self.ledger)  # new instance, same ledger file
        calls = []
        r2 = witness2.commit(grant_id="g1", action_type="publish.post",
                             resource="draft-1", executor=lambda: calls.append(1) or {"ok": True})
        self.assertEqual(calls, [1])  # repair-and-retry executes
        self.assertEqual(r2.status, "committed")

    def test_fingerprint_canonical(self):
        a = action_fingerprint("publish.post", "d1", parameters={"x": 1, "y": 2})
        b = action_fingerprint("publish.post", "d1", parameters={"y": 2, "x": 1})
        self.assertEqual(a, b)
        self.assertTrue(a.startswith("sha256:"))
        c = action_fingerprint("publish.post", "d1", target="@someone")
        self.assertNotEqual(a, c)


if __name__ == "__main__":
    unittest.main()
