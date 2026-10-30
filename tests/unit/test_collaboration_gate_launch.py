"""Exercise the real installer/enrollment/client boundary with a fake CLI fixture."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
import uuid
from tests.unit import test_collaboration_gate as gate_tests

SOURCE = Path(__file__).resolve().parents[2]


class LauncherIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = gate_tests.CollaborationGateTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.log = self.fixture.root / 'client-start.json'
        self.client = self.fixture.root / 'fake-claude'
        self.client.write_text('#!' + sys.executable + '\nimport json,sys\nfrom pathlib import Path\n'
            + f'Path({str(self.log)!r}).write_text(json.dumps(sys.argv[1:]))\n')
        self.client.chmod(0o700)
        self.manifest = self.fixture.root / 'claim.json'
        self.claim = self.fixture.manifest(str(uuid.uuid4()), ['.'])
        self.manifest.write_text(json.dumps(self.claim))
        self.command = [sys.executable, str(SOURCE / 'scripts/install_collaboration_gate.py'),
                        '--workspace', str(self.fixture.root), '--source', str(SOURCE)]

    def run_cli(self, *args):
        return subprocess.run(self.command + list(args), capture_output=True, text=True)

    def test_missing_install_and_conflicting_claim_never_start_client(self):
        args = ['start', '--manifest', str(self.manifest), '--claude-bin', str(self.client)]
        self.assertEqual(self.run_cli(*args).returncode, 2)
        self.assertFalse(self.log.exists())
        self.assertEqual(self.run_cli('install', '--repo', str(self.fixture.repo)).returncode, 0)
        self.fixture.gate.enroll(self.fixture.manifest('other-worker', ['src/']))
        self.assertEqual(self.run_cli(*args).returncode, 2)
        self.assertFalse(self.log.exists())

    def test_installed_client_has_exact_session_settings_and_releases_on_exit(self):
        self.assertEqual(self.run_cli('install', '--repo', str(self.fixture.repo)).returncode, 0)
        result = self.run_cli('start', '--manifest', str(self.manifest), '--claude-bin', str(self.client))
        self.assertEqual(result.returncode, 0, result.stderr)
        args = json.loads(self.log.read_text())
        self.assertNotIn('-p', args)
        self.assertEqual(args[args.index('--session-id') + 1], self.claim['session_id'])
        config = Path(args[args.index('--settings') + 1])
        hook = json.loads(config.read_text())['hooks']['PreToolUse'][0]['hooks'][0]
        self.assertEqual(hook['onFailure'], 'block')
        # Test the exact installed hook command with event-shaped stdin.
        event = dict(session_id=self.claim['session_id'], cwd=str(self.fixture.repo),
                     tool_name='Write', tool_input={'file_path': 'src/a.py'})
        refused = subprocess.run([hook['command'], *hook['args']], input=json.dumps(event),
                                  capture_output=True, text=True)
        self.assertEqual(refused.returncode, 2)  # client exit released enrollment
        self.fixture.gate.enroll(self.claim)
        admitted = subprocess.run([hook['command'], *hook['args']], input=json.dumps(event),
                                   capture_output=True, text=True)
        self.assertEqual(admitted.returncode, 0, admitted.stderr)

    def test_prompt_uses_headless_mode_and_preserves_literal_text(self):
        self.assertEqual(self.run_cli('install', '--repo', str(self.fixture.repo)).returncode, 0)
        for prompt in ('Perform the scoped task', '-literal option-like text', ''):
            with self.subTest(prompt=prompt):
                result = self.run_cli('start', '--manifest', str(self.manifest),
                                      '--claude-bin', str(self.client), '--prompt=' + prompt)
                self.assertEqual(result.returncode, 0, result.stderr)
                args = json.loads(self.log.read_text())
                self.assertEqual(args[-2:], ['-p', prompt])
                self.assertEqual(args.count('-p'), 1)

    def test_client_exit_preserves_offered_handoff_for_receiver(self):
        receiver = str(uuid.uuid4())
        handoff = [sys.executable, str(SOURCE / 'scripts/collaboration_gate.py'),
                   '--workspace', str(self.fixture.root), 'handoff', '--session',
                   self.claim['session_id'], '--receiver', receiver,
                   '--reference', 'https://github.com/example/work/issues/1#handoff']
        self.client.write_text('#!' + sys.executable + '\nimport subprocess\n'
                               + f'subprocess.run({handoff!r}, check=True)\n')
        self.assertEqual(self.run_cli('install', '--repo', str(self.fixture.repo)).returncode, 0)
        result = self.run_cli('start', '--manifest', str(self.manifest), '--claude-bin', str(self.client))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.fixture.gate.accept(receiver, self.claim['session_id'],
                                 'https://github.com/example/work/issues/1#accepted')
        self.assertEqual(self.fixture.gate.check(receiver)['session_id'], receiver)


if __name__ == '__main__':
    unittest.main()
