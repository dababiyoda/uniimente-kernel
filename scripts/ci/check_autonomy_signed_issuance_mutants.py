"""Each safeguard of signed autonomy issuance (acceptance I.G5) must fail its tests.

    python scripts/ci/check_autonomy_signed_issuance_mutants.py

Mutants are applied to autonomy/levels.py and greg/founder.py in a scratch copy of the repository, never to the
working tree. A mutant is caught only when tests/unit/test_autonomy_signed_issuance.py reports a FAILED test. Exit
status 1 if any mutant survives or no longer applies.
"""
from pathlib import Path

from mutation_harness import run  # scripts/ci/mutation_harness.py: the shared loop

ROOT = Path(__file__).resolve().parents[2]
LEVELS = "autonomy/levels.py"
FOUNDER = "greg/founder.py"
TESTS = "tests/unit/test_autonomy_signed_issuance.py"
MUTANTS = [
    (LEVELS, "a name alone issues A1+ again (the signature is never required)",
     "            signed = self._verified_grant(subject, tuple_, level, authorization)\n",
     "            signed = self._verified_grant(subject, tuple_, level, authorization) if authorization else None\n"),
    (LEVELS, "no verifier means no check",
     "        if self.verifier is None:\n            raise ValueError(",
     "        if self.verifier is None:\n            return {}\n            raise ValueError("),
    (LEVELS, "the signature is not verified",
     "            env = self.verifier.verify(authorization, expected_kind=GRANT_KIND)\n",
     "            env = authorization\n"),
    (LEVELS, "any principal may sign the grant",
     '        if principal != "founder":\n', '        if False:\n'),
    (LEVELS, "a grant for another subject, tuple or level is honoured",
     '        if env["body"] != wanted:\n', '        if False:\n'),
    (LEVELS, "a grant may be used twice",
     '        if self._spent(env["nonce"]):\n', '        if False:\n'),
    (LEVELS, "the ledger does not keep the signature",
     '                                **({"authorization": signed} if signed else {})})',
     '                                })'),
    (FOUNDER, "a delegated device may sign the grant",
     'DEVICE_KINDS = ("DECISION", "CRITIQUE", "LIFECYCLE", "BODY_PAUSE", "BODY_RESUME", "BODY_STOP", "GOAL_CONTROL")',
     'DEVICE_KINDS = ("DECISION", "CRITIQUE", "LIFECYCLE", "BODY_PAUSE", "BODY_RESUME", "BODY_STOP", "GOAL_CONTROL",'
     ' "AUTONOMY_GRANT")'),
]


def main() -> int:
    return run(MUTANTS, TESTS, prefix="autonomy-signed-issuance-mutants-", root=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
