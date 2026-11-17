"""Real git worktrees and processes exercise the local enrollment boundary."""
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[2] / 'scripts/collaboration_gate.py'
spec = importlib.util.spec_from_file_location('collaboration_gate', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
Gate, GateError = module.Gate, module.GateError


def stamp(delta=0):
    return (datetime.now(timezone.utc) + timedelta(seconds=delta)).strftime('%Y-%m-%dT%H:%M:%SZ')


class CollaborationGateTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.repo = self.root / 'repo'; self.repo.mkdir()
        self.git('init', '-q')
        self.git('config', 'user.name', 'Test')
        self.git('config', 'user.email', 'test@example.invalid')
        (self.repo / 'initial.txt').write_text('initial')
        self.git('add', '.')
        self.git('commit', '-qm', 'initial')
        self.gate = Gate(self.root)
        self.reads = []
        for kind in ('protocol', 'discussion', 'board'):
            p = self.root / (kind + '.md'); p.write_text(kind + ' snapshot')
            self.reads.append(dict(kind=kind, path=str(p), sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
                                   reference='https://github.com/example/work/' + kind, retrieved_at=stamp(-1)))

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], text=True).strip()

    def manifest(self, sid='worker-A', paths=None, interfaces=None, repo=None):
        repo = repo or self.repo
        return dict(version=1, session_id=sid, repository=str(repo),
                    head_sha=self.git('rev-parse', 'HEAD'), source_reads=self.reads,
                    work_item='https://github.com/example/work/issues/1', paths=paths or ['src/a.py'],
                    interfaces=interfaces or [], expires_at=stamp(600))

    def event(self, tool='Write', sid='worker-A', path='src/a.py'):
        return dict(session_id=sid, tool_name=tool, cwd=str(self.repo), tool_input=dict(file_path=path))

    def test_missing_enrollment_blocks_write_but_reads_do_not_create_db(self):
        self.gate.hook(self.event('Read'))
        with self.assertRaises(GateError): self.gate.hook(self.event())
        self.assertFalse(self.gate.db.exists())

    def test_database_traversal_is_refused_without_outside_write(self):
        outside = self.root.parent / 'outside.sqlite'
        with self.assertRaisesRegex(GateError, 'traversal'):
            Gate(self.root, self.root / '..' / 'outside.sqlite')
        with self.assertRaisesRegex(GateError, 'under shared workspace'):
            Gate(self.root, outside)
        self.assertFalse(outside.exists())

    def test_cli_finish_preserves_pending_handoff_for_receiver_acceptance(self):
        self.gate.enroll(self.manifest())
        self.gate.handoff('worker-A', 'worker-B', 'https://ack/offer')
        p = subprocess.run([sys.executable, str(SCRIPT), '--workspace', str(self.root),
                            'finish', '--session', 'worker-A'], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        with self.assertRaises(GateError): self.gate.enroll(self.manifest('worker-C'))
        self.gate.accept('worker-B', 'worker-A', 'https://ack/accept')
        self.gate.check('worker-B')

    def test_finish_releases_active_and_is_idempotent_without_cancelling_handoff(self):
        self.gate.finish('absent')
        self.assertFalse(self.gate.db.exists())
        self.gate.enroll(self.manifest())
        self.gate.finish('worker-A')
        self.gate.finish('worker-A')
        self.gate.finish('absent')
        self.gate.enroll(self.manifest('worker-B'))
        db = sqlite3.connect(self.gate.db)
        events = db.execute("SELECT action FROM audit WHERE action='finish'").fetchall()
        db.close()
        self.assertEqual(events, [('finish',)])

    def test_notebook_edit_and_malformed_hook_inputs(self):
        self.gate.enroll(self.manifest(paths=['notebooks/']))
        e = self.event('NotebookEdit')
        e['tool_input'] = {'notebook_path': 'notebooks/a.ipynb'}
        self.gate.hook(e)
        e['tool_input']['notebook_path'] = 'other/a.ipynb'
        with self.assertRaises(GateError): self.gate.hook(e)
        for e in ({}, [], {'tool_name': 'Write'}, {'tool_name': 'NotebookEdit', 'session_id': 'worker-A', 'cwd': str(self.repo), 'tool_input': {}}):
            with self.subTest(event=e), self.assertRaises(GateError): self.gate.hook(e)

    def test_claim_survives_process_restart_and_allows_only_claimed_paths(self):
        self.gate.enroll(self.manifest(paths=['src/']))
        Gate(self.root).hook(self.event(path='src/nested/new.py'))
        for path in ('other.py', '../outside.py', str(self.root / 'outside.py')):
            with self.subTest(path=path), self.assertRaises(GateError): self.gate.hook(self.event(path=path))

    def test_atomic_conflict_across_processes(self):
        commands = []
        for sid in ('first', 'second'):
            p = self.root / (sid + '.json'); p.write_text(json.dumps(self.manifest(sid)))
            commands.append(subprocess.Popen([sys.executable, str(SCRIPT), '--workspace', str(self.root),
                           'enroll', '--manifest', str(p)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True))
        outcomes = [p.communicate(timeout=20) for p in commands]
        self.assertEqual(sorted(p.returncode for p in commands), [0, 2], outcomes)

    def test_directory_and_interface_claims_collide_but_independent_files_run_parallel(self):
        self.gate.enroll(self.manifest('A', ['src/'], ['shared-contract']))
        self.gate.enroll(self.manifest('B', ['tests/']))
        for m in (self.manifest('C', ['src/child.py']), self.manifest('C', ['docs/'], ['shared-contract']),
                  self.manifest('C', ['.'])):
            with self.assertRaises(GateError): self.gate.enroll(m)

    def test_linked_worktrees_share_logical_repo_claims(self):
        other = self.root / 'worktree'
        self.git('worktree', 'add', '-qb', 'worker-branch', str(other))
        self.gate.enroll(self.manifest())
        with self.assertRaisesRegex(GateError, 'conflict'):
            self.gate.enroll(self.manifest('worker-B', repo=other))

    def test_expired_claim_is_not_stolen_and_owner_can_release(self):
        self.gate.enroll(self.manifest())
        db = sqlite3.connect(self.gate.db)
        data = json.loads(db.execute('SELECT manifest FROM claims').fetchone()[0])
        data['expires_at'] = stamp(-60)
        db.execute('UPDATE claims SET manifest=?', (json.dumps(data),)); db.commit(); db.close()
        with self.assertRaisesRegex(GateError, 'expired'): self.gate.check('worker-A')
        with self.assertRaisesRegex(GateError, 'conflict'): self.gate.enroll(self.manifest('worker-B'))
        self.gate.release('worker-A')
        self.gate.enroll(self.manifest('worker-B'))

    def test_head_and_source_drift_require_fresh_enrollment(self):
        self.gate.enroll(self.manifest())
        self.git('commit', '--allow-empty', '-qm', 'moved')
        with self.assertRaisesRegex(GateError, 'stale'): self.gate.check('worker-A')
        self.gate.enroll(self.manifest())
        (self.root / 'board.md').write_text('new competing claim')
        with self.assertRaisesRegex(GateError, 'source drift'): self.gate.check('worker-A')

    def test_bash_requires_exclusive_whole_repo_claim(self):
        self.gate.enroll(self.manifest())
        with self.assertRaisesRegex(GateError, 'Bash requires'): self.gate.hook(self.event('Bash'))
        self.gate.release('worker-A')
        self.gate.enroll(self.manifest(paths=['.']))
        self.gate.hook(self.event('Bash'))
        with self.assertRaisesRegex(GateError, 'conflict'): self.gate.enroll(self.manifest('worker-B'))

    def test_handoff_reserves_scope_until_distinct_receiver_accepts(self):
        self.gate.enroll(self.manifest())
        with self.assertRaisesRegex(GateError, 'self'): self.gate.handoff('worker-A', 'worker-A', 'https://ack/a')
        self.gate.handoff('worker-A', 'worker-B', 'https://ack/offer')
        with self.assertRaises(GateError): self.gate.check('worker-A')
        with self.assertRaises(GateError): self.gate.enroll(self.manifest('worker-C'))
        with self.assertRaises(GateError): self.gate.accept('worker-C', 'worker-A', 'https://ack/c')
        self.gate.accept('worker-B', 'worker-A', 'https://ack/b')
        self.gate.check('worker-B')
        with self.assertRaises(GateError): self.gate.check('worker-A')

    def test_hook_uses_actual_session_and_cwd(self):
        self.gate.enroll(self.manifest())
        with self.assertRaises(GateError): self.gate.hook(self.event(sid='other-worker'))
        other = self.root / 'other'; other.mkdir()
        e = self.event(); e['cwd'] = str(other)
        with self.assertRaises(GateError): self.gate.hook(e)

    def test_unsafe_claim_and_symlink_refused(self):
        for path in ('../outside', '/absolute', 'src//bad', 'src/../bad'):
            with self.subTest(path=path), self.assertRaises(GateError): self.gate.enroll(self.manifest(paths=[path]))
        outside = self.root / 'outside'; outside.mkdir()
        (self.repo / 'linked').symlink_to(outside)
        with self.assertRaises(GateError): self.gate.enroll(self.manifest(paths=['linked/file']))

    def test_corrupt_registry_fails_closed_in_hook_process(self):
        self.gate.db.parent.mkdir()
        self.gate.db.write_bytes(b'corrupt database')
        p = subprocess.run([sys.executable, str(SCRIPT), '--workspace', str(self.root), 'hook'],
                           input=json.dumps(self.event()), capture_output=True, text=True)
        self.assertEqual(p.returncode, 2)
        self.assertIn('blocked', p.stderr)

    def test_all_three_sources_required_and_source_changes_refused(self):
        manifest = self.manifest(); manifest['source_reads'] = self.reads[:2]
        with self.assertRaises(GateError): self.gate.enroll(manifest)
        self.reads[0]['sha256'] = '0' * 64
        with self.assertRaises(GateError): self.gate.enroll(self.manifest())


if __name__ == '__main__':
    unittest.main()
