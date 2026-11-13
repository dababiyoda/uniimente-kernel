"""A check its faulted sensor capability could not read is never pursued, and a mission never retries it unseen.

    python scripts/ci/check_unmeasured_check_mutants.py

The rule in MissionEngine (greg/missions.py), each part removed in a scratch copy:
- beside another check's real failure, the unread check's strategies are left out (before: a completed write was
  dispatched a second time and overwrote what a person had added), and the real failure is still pursued in that
  same pass;
- when nothing is left to pursue, the mission re-observes (with the first part alone it asked the founder for a
  strategy and never looked again);
- a route that waits only on a check at its first fault waits for the repair and asks nobody;
- a fault the Mind's answer names is recorded as an unmeasured, typed reading, so the retry path counts it, the
  founder is asked after three unmeasured rounds, self-repair sees it under a long predicate, the strategy is not
  blamed, and a failure closure names it;
- a refused read beside such a fault keeps its route.
A mutant is caught only when a test FAILS. The second file builds constructions, so it needs networkx and scipy
(requirements-cognition.txt); without them its tests are skipped and its mutants would be reported as surviving.
Exit status 1 if any mutant survives or no longer applies.
"""
from pathlib import Path

from mutation_harness import run  # scripts/ci/mutation_harness.py: the shared loop

ROOT = Path(__file__).resolve().parents[2]
MISSIONS = "greg/missions.py"
# The shared loop judges one test file per run, so each half is judged by the file that pins it.
PURSUABLE = "        pursuable = failing - self.inconclusive - set(self.capability_faults)"
RETRY = "        errors = set(failing) if not pursuable or failing <= set(self.sensor_errors) - self.mind_faults else set()"
BESIDE = ("tests/unit/test_greg_functional_reconstitution.py", [
    (MISSIONS, "a check a faulted capability could not read is pursued beside a real failure: a completed write "
               "is dispatched again",
     PURSUABLE, "        pursuable = failing - self.inconclusive"),
    (MISSIONS, "any capability fault makes the whole pass a retry: the check that really fails waits a pass",
     RETRY, RETRY.replace("if not pursuable or", "if self.capability_faults or not pursuable or")),
    (MISSIONS, "a route that waits only on a first fault asks the founder for a strategy",
     '        if not candidates and held and waits_on <= set(getattr(self, "awaiting_repair", ())):',
     "        if False:"),
    (MISSIONS, "self-repair no longer names the faults at their first strike",
     "                self.awaiting_repair.add(check_id)", "                pass"),
])
ALONE = ("tests/integration/test_greg_mind_constructs_capability.py", [
    (MISSIONS, "when only a faulted construction keeps a check from passing, the mission pursues nothing and the "
               "founder is asked for a strategy",
     RETRY, RETRY.replace("if not pursuable or failing", "if failing")),
    (MISSIONS, "a refused read beside a fault the Mind named loses its route",
     RETRY, RETRY.replace(" - self.mind_faults", "")),
    (MISSIONS, "a fault the Mind named is recorded without a type: a long predicate hides it from self-repair",
     '                        failure_class = failure_class or "executor_error"\n', ""),
    (MISSIONS, "a fault the Mind named is recorded as a measured failure: the retry rounds never count it",
     '                        detail = f"sensor inconclusive (capability fault): {detail}"\n', ""),
    (MISSIONS, "a fault the Mind named is not among the pass's unmeasured checks: a failure closure does not name it",
     '                        sensor_errors.add(check["check_id"])\n                        self.mind_faults',
     "                        self.mind_faults"),
])


def main() -> int:
    status = 0
    for tests, mutants in (BESIDE, ALONE):
        status |= run(mutants, tests, "greg-unmeasured-check-mutants-", root=ROOT)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
