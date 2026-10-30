"""The organ exchange's binding verdict must survive hostile, self-consistent local edits.

Each mutant removes one safeguard of greg/organs.py's verdict and must be caught by its named test in a separate copy
of the repository. Each named test is first run unmutated in that copy: a test that does not pass there (for example
because the organs are missing) cannot catch anything, so it counts as invalid, not caught. The live-exchange test
needs the real organs (CI job 8's environment).
"""
from pathlib import Path
import os, shutil, subprocess, sys, tempfile

ROOT = Path(__file__).resolve().parents[2]
T = "tests/unit/test_greg_organ_exchange_verdict.py::"
MUTANTS = [
    ("the engine's verdict is stated uncapped", "greg/organs.py",
     'return binding_verdict(assessment.get("go_no_go"), unresolved, packet.get("evidence", []))',
     'return assessment.get("go_no_go"), ""',
     T + "test_an_engine_go_on_a_packet_with_unevidenced_canonical_fields_is_capped"),
    ("unreadable wire messages leave every field evidenced", "greg/organs.py",
     'unresolved = [f"every field: the Kernel could not read the wire messages ({str(exc)[:160]})"]',
     "unresolved = []",
     T + "test_messages_the_kernel_cannot_read_leave_nothing_evidenced"),
    ("the receipt states the engine's verdict", "greg/organs.py",
     '"verdict": verdict, "verdict_why": why,',
     '"verdict": original.get("go_no_go"), "verdict_why": why,',
     T + "test_live_exchange_states_the_capped_verdict_beside_the_engines"),
]


def _run(repo: Path, node: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", node],
                          cwd=repo, env={**os.environ, "PYTHONPATH": str(repo), "PYTHONDONTWRITEBYTECODE": "1"},
                          capture_output=True, text=True, timeout=600)


def main():
    invalid = 0
    with tempfile.TemporaryDirectory(prefix="greg-organ-verdict-mutants-") as temp:
        repo = Path(temp) / "repo"
        shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
        for name, relative, old, new, node in MUTANTS:
            path = repo / relative
            original = path.read_text()
            if original.count(old) != 1:
                print("STALE", name); invalid += 1; continue
            base = _run(repo, node)
            if base.returncode != 0 or " passed" not in base.stdout:
                print("INVALID (the test does not pass unmutated)", name, base.stdout[-400:]); invalid += 1; continue
            path.write_text(original.replace(old, new))
            run = _run(repo, node)
            caught = (run.returncode == 1 and f"FAILED {node}" in run.stdout and "ERROR collecting" not in run.stdout)
            print("CAUGHT" if caught else "SURVIVED_OR_INVALID", name)
            invalid += not caught
            path.write_text(original)
    return int(bool(invalid))


if __name__ == "__main__":
    raise SystemExit(main())
