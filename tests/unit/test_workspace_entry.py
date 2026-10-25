"""Workspace discovery without silently replacing contributor instructions."""
from pathlib import Path
import tempfile
import unittest

from scripts.workspace_entry import FILES, check_or_install


class WorkspaceEntryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.kernel = self.root / "kernel"
        (self.kernel / "docs/collaboration").mkdir(parents=True)
        (self.kernel / "AGENTS.md").write_text("local rules")
        (self.kernel / "docs/collaboration/START_HERE.md").write_text("canonical guide")
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()

    def test_check_is_read_only_and_install_is_repeatable(self):
        self.assertEqual(check_or_install(self.workspace, self.kernel), list(FILES))
        self.assertEqual(list(self.workspace.iterdir()), [])
        check_or_install(self.workspace, self.kernel, install=True)
        self.assertEqual(check_or_install(self.workspace, self.kernel), [])
        self.assertEqual(check_or_install(self.workspace, self.kernel, install=True), [])
        self.assertIn("alwaysApply: true", (self.workspace / FILES[-1]).read_text())

    def test_conflicting_file_refuses_before_any_other_write(self):
        (self.workspace / "CLAUDE.md").write_text("my rules")
        with self.assertRaisesRegex(ValueError, "differ"):
            check_or_install(self.workspace, self.kernel, install=True)
        self.assertFalse((self.workspace / "AGENTS.md").exists())
        self.assertEqual((self.workspace / "CLAUDE.md").read_text(), "my rules")

    def test_changed_managed_file_is_not_overwritten(self):
        check_or_install(self.workspace, self.kernel, install=True)
        path = self.workspace / "AGENTS.md"
        path.write_text(path.read_text() + "\nadditional local rules\n")
        with self.assertRaisesRegex(ValueError, "differ"):
            check_or_install(self.workspace, self.kernel, install=True)
        self.assertIn("additional local rules", path.read_text())

    def test_symlink_parent_cannot_write_outside_workspace(self):
        outside = self.root / "outside"
        outside.mkdir()
        (self.workspace / ".github").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            check_or_install(self.workspace, self.kernel, install=True)
        self.assertEqual(list(outside.iterdir()), [])
        self.assertFalse((self.workspace / "AGENTS.md").exists())

    def test_missing_canonical_guide_is_not_installed(self):
        (self.kernel / "docs/collaboration/START_HERE.md").unlink()
        with self.assertRaisesRegex(ValueError, "Kernel checkout"):
            check_or_install(self.workspace, self.kernel, install=True)
        self.assertEqual(list(self.workspace.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
