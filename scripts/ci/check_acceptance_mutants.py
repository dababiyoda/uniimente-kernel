"""The acceptance report's reality label and runtime property must not drift back to over-claiming.

Each mutant reverts one guard in greg/acceptance.py. Its named test must pass on the unmutated copy and fail on the
mutant; the verdict is read from pytest's JUnit report, never from its console text. Bytecode is never written, so
a mutant cannot run stale code.
"""
from pathlib import Path
import os, shutil, subprocess, sys, tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
T = "tests/unit/test_greg_acceptance_reality.py::"
HEARTBEAT = T + "test_a_heartbeat_is_not_a_running_body_when"
MUTANTS = [
    ("a designated test-key run reads FOUNDER-DEVICE", "greg/acceptance.py",
     'if on_body and signature.get("tier") == metrics.FOUNDER_TIER:', "if on_body:",
     T + "test_a_designated_body_whose_mission_a_test_key_signed_is_not_founder_device"),
    ("a dead process passes", "greg/acceptance.py",
     "and alive is True and reused is not True)", "and reused is not True)",
     HEARTBEAT + "[its process is dead-<lambda>]"),
    ("a vanished process reads alive", "greg/acceptance.py",
     "        except ProcessLookupError:\n            alive = False",
     "        except ProcessLookupError:\n            alive = True",
     HEARTBEAT + "[its process is dead-<lambda>]"),
    ("a stale heartbeat passes", "greg/acceptance.py",
     "and 0 <= age < STALE_HEARTBEAT_SECONDS and", "and 0 <= age and",
     HEARTBEAT + "[it is older than three minutes-<lambda>]"),
    ("a heartbeat dated in the future passes", "greg/acceptance.py",
     "and 0 <= age < STALE_HEARTBEAT_SECONDS and", "and age < STALE_HEARTBEAT_SECONDS and",
     HEARTBEAT + "[it is dated in the future-<lambda>]"),
    ("a boolean is read as a process id", "greg/acceptance.py",
     "if isinstance(pid, int) and not isinstance(pid, bool) and pid > 0:", "if isinstance(pid, int) and pid > 0:",
     HEARTBEAT + "[its process is not a number-<lambda>]"),
    ("a process started after its heartbeat passes as its writer", "greg/acceptance.py",
     "and alive is True and reused is not True)", "and alive is True)",
     T + "test_a_process_started_after_the_heartbeat_did_not_write_it"),
    ("a held body passes", "greg/acceptance.py",
     'running = (heartbeat.get("state") in ("RUNNING", "PAUSED") and age is not None',
     "running = (age is not None",
     HEARTBEAT + "[the body is held-<lambda>]"),
]


def outcome(repo: Path, node: str, env: dict) -> str:
    """PASSED, FAILED or ERROR for exactly one collected test, else why the run cannot decide."""
    report = repo / "mutant-junit.xml"
    report.unlink(missing_ok=True)
    try:
        subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", f"--junitxml={report}", node],
                       cwd=repo, env=env, capture_output=True, text=True, timeout=600, start_new_session=True)
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
    with tempfile.TemporaryDirectory(prefix="greg-acceptance-mutants-") as temp:
        repo = Path(temp) / "repo"
        shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
        env = {**os.environ, "PYTHONPATH": str(repo), "PYTHONDONTWRITEBYTECODE": "1"}
        for node in sorted({m[4] for m in MUTANTS}):              # every named test must pass before it can catch
            base = outcome(repo, node, env)
            if base != "PASSED":
                print("BASELINE_NOT_PASSING", base, node)
                invalid += 1
        if invalid:
            return 1
        for name, relative, old, new, node in MUTANTS:
            path = repo / relative
            original = path.read_text()
            if original.count(old) != 1:
                print("STALE", name)
                invalid += 1
                continue
            path.write_text(original.replace(old, new))
            try:
                result = outcome(repo, node, env)
            finally:
                path.write_text(original)
            caught = result in ("FAILED", "ERROR")
            print("CAUGHT" if caught else f"SURVIVED_OR_INVALID ({result})", name)
            invalid += not caught
    print(f"{len(MUTANTS)} mutants, {invalid} survived, stale or invalid")
    return int(bool(invalid))


if __name__ == "__main__":
    raise SystemExit(main())
