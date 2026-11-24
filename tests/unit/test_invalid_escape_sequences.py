"""No tracked Python file contains an invalid escape sequence (issue #343, Task B).

A backslash before a character that is not a defined escape (``"\\."``, ``"\\+"``, ``"\\d"``) is read
today as a backslash and that character, but CPython warns about it: DeprecationWarning on 3.11,
SyntaxWarning from 3.12, and the language reference says it will become an error. A run with warnings
as errors cannot compile such a file at all. On 2026-11-22 two mutant anchors in
``scripts/ci/check_cortex_mutants.py`` had this defect and nothing caught it.

The check compiles every file ``git ls-files`` lists with every warning recorded, so it sees exactly
what the interpreter sees (f-strings, byte strings and invalid octal escapes included) without running
any code. CPython reports only the first invalid escape in each literal, so a fixed line can reveal a
second one in the same string on the next run. It takes a few seconds over the whole tree. A first
test plants the defect in memory and requires the detector to catch it, so a change in CPython's
warning wording cannot silently turn the guard into a pass.
"""
from __future__ import annotations

import subprocess
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _tracked_python() -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z", "--", "*.py"], cwd=ROOT, capture_output=True, check=True)
    return [f for f in out.stdout.decode("utf-8").split("\0") if f]


def _escape_findings(source: bytes, name: str) -> list[str]:
    """Every invalid-escape warning, and any syntax error, compiling ``source`` produces."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            compile(source, name, "exec", dont_inherit=True)
        except SyntaxError as exc:
            return [f"{name}:{exc.lineno}: SyntaxError: {exc.msg}"]
    return [f"{name}:{w.lineno}: {w.category.__name__}: {w.message}"
            for w in caught if "escape sequence" in str(w.message)]


def test_detector_catches_a_planted_invalid_escape():
    planted = b'import re\nPATTERN = "\\d+\\.txt"\nRAW_OK = r"\\d+"\nBYTES = b"\\q"\n'
    found = _escape_findings(planted, "planted.py")
    # CPython reports the first invalid escape of each literal, so line 2 appears once.
    assert [f.split(":")[1] for f in found] == ["2", "4"], found
    assert _escape_findings(b'OK = r"\\d" + "\\\\." + "\\n"\n', "clean.py") == []


def test_no_tracked_python_file_has_an_invalid_escape_sequence():
    files = _tracked_python()
    assert len(files) > 100, "git ls-files found almost no Python files; is this a checkout?"
    findings = []
    for rel in files:
        path = ROOT / rel
        if path.is_symlink() or not path.is_file():
            continue
        findings.extend(_escape_findings(path.read_bytes(), rel))
    assert not findings, ("Invalid escape sequences (use a raw string, or double the backslash):\n"
                          + "\n".join(findings))
