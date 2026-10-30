from pathlib import Path
import json
import tempfile
import unittest
from scripts.install_collaboration_gate import settings


class InstallationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        (self.root / 'scripts').mkdir()
        (self.root / 'scripts/collaboration_gate.py').write_text('# reviewed gate')
        (self.root / 'docs/collaboration').mkdir(parents=True)
        (self.root / 'docs/collaboration/START_HERE.md').write_text('SOP')

    def test_missing_gate_check_is_read_only(self):
        with self.assertRaisesRegex(ValueError, 'absent'):
            settings(self.repo, self.root, self.root)
        self.assertFalse((self.repo / '.claude').exists())

    def test_preserves_existing_hooks_and_permissions_and_is_repeatable(self):
        path = self.repo / '.claude/settings.local.json'
        path.parent.mkdir()
        original = {'permissions': {'deny': ['Bash(rm *)']}, 'hooks': {'PreToolUse': []}}
        path.write_text(json.dumps(original))
        settings(self.repo, self.root, self.root, True)
        data = json.loads(path.read_text())
        self.assertEqual(data['permissions'], original['permissions'])
        hook = data['hooks']['PreToolUse'][0]['hooks'][0]
        self.assertEqual(hook['onFailure'], 'block')
        self.assertNotIn('shell', hook)
        before = path.read_bytes()
        settings(self.repo, self.root, self.root, True)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(json.loads(path.with_name(path.name + '.before-collaboration-gate').read_text()), original)

    def test_edited_rule_and_symlink_refused(self):
        path, _ = settings(self.repo, self.root, self.root, True)
        data = json.loads(path.read_text())
        data['hooks']['PreToolUse'][0]['hooks'][0]['onFailure'] = 'continue'
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'differs'):
            settings(self.repo, self.root, self.root, True)
        other = self.root / 'other'
        other.mkdir()
        (other / '.claude').symlink_to(path.parent, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            settings(other, self.root, self.root, True)


if __name__ == '__main__':
    unittest.main()
