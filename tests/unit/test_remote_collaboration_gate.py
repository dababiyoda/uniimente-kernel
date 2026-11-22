"""Separate clones and local DBs coordinate through one conditional registry."""
import unittest
from pathlib import Path
from tests.unit import test_collaboration_gate as local
from tests.unit.test_remote_collaboration_registry import MemoryContents
from scripts.remote_collaboration_registry import RemoteRegistry, RemoteError
from scripts.install_collaboration_gate import settings


class RemoteGateIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.fixtures = []
        self.store = MemoryContents()
        for _ in range(2):
            fixture = local.CollaborationGateTests()
            fixture.setUp()
            self.addCleanup(fixture.doCleanups)
            fixture.git('remote', 'add', 'origin', 'git@github.com:Owner/Organ.git')
            fixture.gate = local.Gate(fixture.root, remote=RemoteRegistry(
                'owner/kernel', 'coordination/test', self.store))
            self.fixtures.append(fixture)
        self.a, self.b = self.fixtures

    def test_cross_clone_conflict_and_fresh_receiver_handoff(self):
        self.a.gate.enroll(self.a.manifest('A', ['src/']))
        with self.assertRaisesRegex(RemoteError, 'conflict'):
            self.b.gate.enroll(self.b.manifest('B', ['src/nested/']))
        self.a.gate.handoff('A', 'B', 'https://github.com/owner/kernel/issues/1#offer')
        self.a.gate.finish('A')
        self.b.gate.accept('B', 'A', 'https://github.com/owner/kernel/issues/1#accept',
                           self.b.manifest('B', ['src/']))
        self.b.gate.check('B')
        with self.assertRaises(ValueError):
            self.a.gate.check('A')
        self.b.gate.finish('B')
        self.assertEqual(self.store.state['claims']['B']['state'], 'released')

    def test_same_database_receiver_accepts_remote_handoff(self):
        self.a.gate.enroll(self.a.manifest('A', ['src/']))
        self.a.gate.handoff('A', 'B', 'https://github.com/owner/kernel/issues/1#offer')
        self.a.gate.accept('B', 'A', 'https://github.com/owner/kernel/issues/1#accept',
                           self.a.manifest('B', ['src/']))
        self.a.gate.check('B')

    def test_remote_outage_refuses_local_hook_and_keeps_claim(self):
        self.a.gate.enroll(self.a.manifest('worker-A'))
        self.store.error = RemoteError('unavailable')
        with self.assertRaisesRegex(RemoteError, 'unavailable'):
            self.a.gate.hook(self.a.event())
        with self.assertRaises(RemoteError):
            self.a.gate.finish('worker-A')
        self.assertEqual(self.store.state['claims']['worker-A']['state'], 'active')

    def test_installer_binds_remote_args_and_refuses_silent_mode_change(self):
        source = Path(__file__).resolve().parents[2]
        path, _ = settings(self.a.repo, self.a.root, source, True,
                           'owner/kernel', 'coordination/test')
        import json
        hook = json.loads(path.read_text())['hooks']['PreToolUse'][0]['hooks'][0]
        self.assertIn('--remote-registry', hook['args'])
        self.assertIn('coordination/test', hook['args'])
        self.assertEqual(hook['onFailure'], 'block')
        with self.assertRaisesRegex(ValueError, 'differs'):
            settings(self.a.repo, self.a.root, source, True)
        with self.assertRaises(ValueError):
            settings(self.b.repo, self.b.root, source, True, 'owner/kernel', 'main')
        self.assertFalse((self.b.repo / '.claude').exists())
