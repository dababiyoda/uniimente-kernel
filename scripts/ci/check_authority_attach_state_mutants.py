"""Each safeguard of the authority office's attach-state check (behaviour B) must fail its tests.

    python scripts/ci/check_authority_attach_state_mutants.py

Mutants are applied to greg/authority.py and greg/body.py in a scratch copy of the repository, never to the working
tree. A mutant is caught only when tests/unit/test_greg_authority_attach_state.py reports a FAILED test. Exit status 1
if any mutant survives or no longer applies.
"""
from pathlib import Path

from mutation_harness import run  # scripts/ci/mutation_harness.py: the shared loop

ROOT = Path(__file__).resolve().parents[2]
AUTHORITY = "greg/authority.py"
BODY = "greg/body.py"
TESTS = "tests/unit/test_greg_authority_attach_state.py"
MUTANTS = [
    (AUTHORITY, "the office never consults attach state",
     "        unattached = self.attach_refusal(manifest)\n", "        unattached = None\n"),
    (AUTHORITY, "a non-ATTACHED state executes", 'if state != "ATTACHED":', "if False:"),
    (AUTHORITY, "an unregistered capability executes", "        if state is None:\n            return f",
     "        if False:\n            return f"),
    (AUTHORITY, "the refusal leaves no record", '"type": "greg.authority.refused_unattached"',
     '"type": "greg.authority.refused_unattached_unrecorded"'),
    (BODY, "the body builds its office without the registry",
     "ledger=self.ledger, registry=self.registry)", "ledger=self.ledger)"),
]


def main() -> int:
    return run(MUTANTS, TESTS, prefix="authority-attach-state-mutants-", root=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
