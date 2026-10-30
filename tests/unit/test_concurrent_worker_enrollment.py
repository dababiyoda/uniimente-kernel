"""Two processes share one claims file through the published enrollment gate.

The gate sources remain on #206. This test fails if overlapping admissions both
stick, if a disjoint admission is lost, or if the lost-update detector goes blind.
"""
from pathlib import Path
import json
import subprocess
import sys
import unittest

HARNESS = Path(__file__).resolve().parents[1] / 'harness' / 'concurrent_worker_enrollment.py'
PIN = '31d0c57af90d714da7d9be2c6d6317a41fdc9ca3'
ROOT = Path(__file__).resolve().parents[2]


class ConcurrentEnrollmentTests(unittest.TestCase):
    def test_two_processes_admit_disjoint_claims_and_refuse_overlap(self):
        proc = subprocess.run([sys.executable, str(HARNESS), '--pin', PIN, '--repo', str(ROOT)],
                              capture_output=True, text=True, timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stderr + '\n' + proc.stdout)
        report = json.loads(proc.stdout)
        self.assertEqual(report['product_races'], [])
        self.assertEqual(report['pin'], PIN)
        self.assertEqual(report['processes'], 2)
        self.assertEqual(report['containers'], 'not_run')
        self.assertEqual(report['overlap']['admitted'], 1)
        self.assertEqual(report['overlap']['refused'], 1)
        self.assertTrue(report['overlap']['refused_mentions_conflict'])
        self.assertEqual(report['disjoint']['admitted'], 2)
        self.assertEqual(report['disjoint']['active_sessions'], 2)
        self.assertEqual(report['disjoint']['reserve_audit'], 2)
        self.assertEqual(report['hooks']['in_scope'], 0)
        self.assertEqual(report['hooks']['outside'], 2)
        self.assertEqual(report['hooks']['unenrolled'], 2)
        self.assertTrue(report['hooks']['unenrolled_database_absent'])
        self.assertEqual(report['hooks']['active_after_finish'], 0)
        self.assertEqual(report['idempotent']['admitted'], 2)
        self.assertEqual(report['idempotent']['reserve_audit'], 1)
        self.assertTrue(report['handoff']['sender_head_differs'])
        self.assertEqual(report['handoff']['receiver_check'], 0)
        self.assertEqual(report['handoff']['sender_check'], 2)
        self.assertEqual(report['handoff']['reenroll_while_local_handoff'], 2)
        self.assertTrue(report['handoff']['reenroll_mentions_handoff'])
        self.assertEqual(report['handoff']['release_after_remote_accept'], 0)
        self.assertEqual(report['handoff']['reenroll_after_release'], 0)
        self.assertEqual(report['handoff']['active_after_finish'], 0)
        self.assertEqual(report['retry_budget']['writes'], 0)
        self.assertTrue(report['retry_budget']['mentions_contention'])
        self.assertTrue(report['detector']['lost_update'])

    def test_harness_does_not_vendor_the_gate(self):
        self.assertFalse((ROOT / 'scripts' / 'remote_collaboration_registry.py').exists())
        text = HARNESS.read_text(encoding='utf-8')
        self.assertIn(PIN, text)


if __name__ == '__main__':
    unittest.main()
