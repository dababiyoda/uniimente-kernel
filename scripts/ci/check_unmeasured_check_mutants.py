"""A check its faulted sensor capability could not read is never pursued, alone or beside a real failure.

    python scripts/ci/check_unmeasured_check_mutants.py

Two halves of one rule in MissionEngine (greg/missions.py), each removed in a scratch copy:
- beside another check's real failure, the unread check's strategies are left out (before: a completed write was
  dispatched a second time and overwrote what a person had added);
- when nothing else fails, the mission re-observes instead of pursuing nothing (with the first half alone, the
  mission asked the founder for a strategy and never looked again).
A mutant is caught only when a test FAILS. The second test builds a construction, so it needs networkx and scipy
(requirements-cognition.txt); without them it is skipped and its mutant would be reported as surviving.
Exit status 1 if any mutant survives or no longer applies.
"""
from pathlib import Path

from mutation_harness import run  # scripts/ci/mutation_harness.py: the shared loop

ROOT = Path(__file__).resolve().parents[2]
MISSIONS = "greg/missions.py"
# The shared loop judges one test file per run, so each half is judged by the file that pins it.
BESIDE = ("tests/unit/test_greg_functional_reconstitution.py", [
    (MISSIONS, "a check a faulted capability could not read is pursued beside a real failure: a completed write "
               "is dispatched again",
     "        return self._pursue(m, now, failing - self.inconclusive - set(self.capability_faults), evidence)",
     "        return self._pursue(m, now, failing - self.inconclusive, evidence)"),
])
ALONE = ("tests/integration/test_greg_mind_constructs_capability.py", [
    (MISSIONS, "when only a faulted construction keeps a check from passing, the mission pursues nothing and the "
               "founder is asked for a strategy",
     "        errors = set(self.sensor_errors) | set(self.capability_faults)",
     "        errors = set(self.sensor_errors)"),
])


def main() -> int:
    status = 0
    for tests, mutants in (BESIDE, ALONE):
        status |= run(mutants, tests, "greg-unmeasured-check-mutants-", root=ROOT)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
