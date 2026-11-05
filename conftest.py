import os, sys
import subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)


def _is_shallow_clone() -> bool:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--is-shallow-repository"],
            cwd=ROOT, capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return out.stdout.strip() == "true"


def pytest_report_header(config):
    # Frozen-experiment continuity tests (test_migration_spec_frozen,
    # test_repair_spec_frozen) read reviewed baseline commits with `git show`.
    # In a shallow clone they fail with a bare CalledProcessError; say why up
    # front instead. CI uses `fetch-depth: 0` for the same reason.
    if _is_shallow_clone():
        return ("WARNING: shallow git clone. Frozen-experiment continuity tests "
                "need full history: run `git fetch --unshallow` first.")
    return None
