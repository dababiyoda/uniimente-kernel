"""Tests for the heartbeat supervisor. Stdlib unittest only."""

import asyncio
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from uniimente_kernel.ledger import DecisionLedger, KillSwitch  # noqa: E402
from uniimente_kernel.heartbeat import Heartbeat  # noqa: E402


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class TestHeartbeat(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.ledger = DecisionLedger(path=os.path.join(self.dir.name, "l.jsonl"))
        self.applied = []
        self.sw = KillSwitch(ledger=self.ledger, apply=self.applied.append, initially_armed=True)
        self.hb = Heartbeat(self.sw, self.ledger, max_consecutive_failures=3)

    def tearDown(self):
        self.dir.cleanup()

    def test_success_resets_streak(self):
        self.hb.record_failure("plan", ValueError("x"))
        self.hb.record_success("plan")
        self.assertEqual(self.hb.consecutive_failures, 0)

    def test_breaker_trips_at_cap_and_disarms(self):
        for i in range(3):
            self.hb.record_failure("act", ValueError(f"e{i}"))
        self.assertTrue(self.hb.breaker_tripped)
        self.assertEqual(self.applied, [False])
        self.assertEqual(len(self.ledger.replay(event="breaker_tripped")), 1)

    def test_reset_breaker_does_not_rearm(self):
        for i in range(3):
            self.hb.record_failure("act", ValueError("e"))
        self.hb.reset_breaker()
        self.assertFalse(self.hb.breaker_tripped)
        self.assertEqual(self.applied, [False])   # no re-arm

    def test_run_cycle_isolates_stages(self):
        calls = []

        async def ok():
            calls.append("ok")

        async def bad():
            calls.append("bad")
            raise RuntimeError("boom")

        run(self.hb.run_cycle({"a": ok, "b": bad}))
        self.assertEqual(calls, ["ok", "bad"])
        self.assertEqual(self.hb.consecutive_failures, 1)

    def test_supervise_wraps_failures(self):
        async def bad():
            raise RuntimeError("boom")

        run(self.hb.supervise("job", bad)())
        self.assertEqual(self.hb.consecutive_failures, 1)


if __name__ == "__main__":
    unittest.main()
