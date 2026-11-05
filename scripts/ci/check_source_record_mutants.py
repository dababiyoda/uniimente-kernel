"""The October 22 directive's part 1 record must not drift from the founder's words without a test failing.

    python scripts/ci/check_source_record_mutants.py

Each mutant edits the record (or the 2026-10-22 record it repeats) the way a careless or motivated edit would. Its
named test must pass on the unmutated copy and fail on the mutant; the verdict is read from pytest's JUnit report,
never from its console text. Mutants are applied to a scratch copy holding only the files the test reads.
"""
from pathlib import Path
import hashlib, os, re, shutil, subprocess, sys, tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "docs/intent/sources/OPUS-MAXIMUS-FULL-MACHINE-ASCENT-2026-10-22-source.md"
PART_TWO = "docs/intent/sources/GREG-FULL-MACHINE-COMPLETION-2026-10-22-source.md"
TEST = "tests/unit/test_full_machine_ascent_source.py"
FILES = ["conftest.py", "tests/unit/__init__.py", TEST, SOURCE, PART_TWO]
ONE = TEST + "::test_part_one_is_kept_whole_and_its_digest_matches"
TWO = TEST + "::test_part_two_is_the_october_22_record_word_for_word"


def replace(old, new):
    def edit(text):
        if text.count(old) != 1:
            raise LookupError(old)
        return text.replace(old, new)
    return edit


def restated(old, new):
    """Change the words and restate the header's digest to match them: only the pinned digest can catch this."""
    def edit(text):
        text = replace(old, new)(text)
        start = text.index("````text\n") + len("````text\n")
        digest = hashlib.sha256(text[start:text.rindex("\n````")].encode("utf-8")).hexdigest()
        return re.sub(r"(Its SHA-256 is\s+`)[0-9a-f]{64}", lambda m: m.group(1) + digest, text, count=1)
    return edit


MUTANTS = [
    ("a typographic apostrophe is straightened", SOURCE,
     replace("PRESERVE THE FOUNDER’S EXACT WORDS", "PRESERVE THE FOUNDER'S EXACT WORDS"), ONE),
    ("a section heading is dropped", SOURCE, replace("XII. ACCEPTANCE GATES\n\n", ""), ONE),
    ("the header states another digest", SOURCE,
     replace("`8c900e05284c2a683f829d4aea68ba07885fb5aa7b99aeddb1033a41864c0b0a`",
             "`" + "0" * 64 + "`"), ONE),
    ("one word changes and the header is restated to match", SOURCE,
     restated("The work is not complete until all applicable gates pass.",
              "The work is now complete until all applicable gates pass."), ONE),
    ("the 2026-10-22 record of part 2 drifts", PART_TWO,
     replace("You are the engineering lead and production coordinator for UNIIMENTE / GREG.",
             "You are the engineering lead and coordinator for UNIIMENTE / GREG."), TWO),
]


def outcome(repo: Path, node: str, env: dict) -> str:
    """PASSED, FAILED or ERROR for exactly one collected test, else why the run cannot decide."""
    report = repo / "mutant-junit.xml"
    report.unlink(missing_ok=True)
    try:
        subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", f"--junitxml={report}", node],
                       cwd=repo, env=env, capture_output=True, text=True, timeout=300, start_new_session=True)
    except subprocess.TimeoutExpired:
        return "TIMEOUT"
    if not report.is_file():
        return "NO_REPORT"
    cases = list(ET.parse(report).getroot().iter("testcase"))
    if len(cases) != 1:
        return f"COLLECTED_{len(cases)}"
    case = cases[0]
    if case.find("skipped") is not None:
        return "SKIPPED"
    if case.find("error") is not None:
        return "ERROR"
    return "FAILED" if case.find("failure") is not None else "PASSED"


def main() -> int:
    invalid = 0
    with tempfile.TemporaryDirectory(prefix="source-record-mutants-") as temp:
        repo = Path(temp) / "repo"
        for relative in FILES:
            (repo / relative).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, repo / relative)
        env = {**os.environ, "PYTHONPATH": str(repo), "PYTHONDONTWRITEBYTECODE": "1"}
        for node in sorted({m[3] for m in MUTANTS}):              # every named test must pass before it can catch
            base = outcome(repo, node, env)
            if base != "PASSED":
                print("BASELINE_NOT_PASSING", base, node)
                invalid += 1
        if invalid:
            return 1
        for name, relative, edit, node in MUTANTS:
            path = repo / relative
            original = path.read_text(encoding="utf-8")
            try:
                path.write_text(edit(original), encoding="utf-8")
            except LookupError:
                print("STALE", name)
                invalid += 1
                continue
            try:
                result = outcome(repo, node, env)
            finally:
                path.write_text(original, encoding="utf-8")
            caught = result in ("FAILED", "ERROR")
            print("CAUGHT" if caught else f"SURVIVED_OR_INVALID ({result})", name)
            invalid += not caught
    print(f"{len(MUTANTS)} mutants, {invalid} survived, stale or invalid")
    return int(bool(invalid))


if __name__ == "__main__":
    raise SystemExit(main())
