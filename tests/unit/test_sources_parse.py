"""Every tracked Python source parses under the interpreter running the suite.

CI pins Python 3.11 (.github/workflows/canonical-ci.yml). A script that nothing imports, such as
scripts/admission_readme.py, is otherwise never parsed there, so a 3.12-only construct (an f-string reusing its own
quote inside a replacement field) passed CI on #158 and failed only when #179's source-scanning test read it."""
from __future__ import annotations

import ast
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_every_tracked_python_file_parses():
    listed = subprocess.run(["git", "ls-files", "*.py"], cwd=ROOT, capture_output=True, text=True, check=True)
    bad = []
    for rel in listed.stdout.split():
        path = ROOT / rel
        if not path.is_file():
            continue
        try:
            ast.parse(path.read_text(encoding="utf-8"), rel)
        except SyntaxError as exc:
            bad.append((rel, exc.lineno, exc.msg))
    assert not bad, bad
