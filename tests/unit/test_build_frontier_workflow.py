"""The build-frontier workflow runs the gates the build frontier relies on, and its rehearsals cannot skip.

GitHub Actions cannot be run here, so this reads the workflow files: on every pull request Canonical CI runs the
path-predicate mutation gate (adopted with #236), and the build-frontier workflow installs requirements-dev.txt
(which provides supervisord), runs this unit's gate, and runs both supervised rehearsal modules with
GREG_REQUIRE_SUPERVISOR=1. Canonical CI is not edited.
"""
from __future__ import annotations

from pathlib import Path
import re
import shlex

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/build-frontier.yml"
CANONICAL = ROOT / ".github/workflows/canonical-ci.yml"
PREDICATE_GATE = "scripts/ci/check_path_predicate_mutants.py"
GATES = ("scripts/ci/check_fail_closed_build_instrument_mutants.py",)
REHEARSALS = ("tests/integration/test_greg_chromebook_rehearsal.py", "tests/integration/test_greg_vepmc_path.py")


def steps(workflow: Path = WORKFLOW) -> list:
    data = yaml.safe_load(workflow.read_text())
    triggers = data.get("on", data.get(True))        # YAML 1.1 reads a bare `on` key as True
    assert "pull_request" in triggers, triggers
    return [step for job in data["jobs"].values() for step in job.get("steps", [])]


def commands(step: dict) -> list[list[str]]:
    return [shlex.split(line) for line in str(step.get("run", "")).splitlines() if line.strip()]


def test_every_pull_request_installs_supervisord_and_runs_both_gates():
    runs = [c for s in steps() for c in commands(s)]
    installs = [c for c in runs if c[:2] == ["pip", "install"]]
    assert installs and "requirements-dev.txt" in installs[0], installs
    requirements = (ROOT / "requirements-dev.txt").read_text().splitlines()
    assert any(re.match(r"supervisor\b", line.strip()) for line in requirements)     # provides supervisord
    for gate in GATES:
        assert ["python", gate] in runs, gate
        assert (ROOT / gate).is_file(), gate
    canonical = [c for s in steps(CANONICAL) for c in commands(s)]
    assert ["python", PREDICATE_GATE] in canonical, "Canonical CI must run the path-predicate gate"
    assert (ROOT / PREDICATE_GATE).is_file()


def test_the_supervised_rehearsals_run_with_supervisord_required():
    rehearsal = [s for s in steps() if any(set(REHEARSALS) <= set(c) for c in commands(s))]
    assert len(rehearsal) == 1, rehearsal
    [step] = rehearsal
    assert any(c[:3] == ["python", "-m", "pytest"] for c in commands(step))
    assert str(step.get("env", {}).get("GREG_REQUIRE_SUPERVISOR")) == "1", step
    assert all((ROOT / r).is_file() for r in REHEARSALS)
