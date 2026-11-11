"""Each safeguard binding the authority office to the registered capability must fail its tests.

    python scripts/ci/check_authority_registered_identity_mutants.py

The office refuses a manifest, an adapter or an invocation context that is not the one the registry holds under the
capability's id (tests/unit/test_greg_authority_registered_identity.py). Mutants are applied to greg/authority.py in
a scratch copy of the repository, never to the working tree. Exit status 1 if any mutant survives or no longer
applies.
"""
from pathlib import Path

from mutation_harness import run  # scripts/ci/mutation_harness.py: the shared loop

ROOT = Path(__file__).resolve().parents[2]
AUTHORITY = "greg/authority.py"
TESTS = "tests/unit/test_greg_authority_registered_identity.py"
MUTANTS = [
    (AUTHORITY, "the office checks the id but not what it was handed to run",
     "        unattached = self.attach_refusal(manifest, adapter, ctx)\n",
     "        unattached = self.attach_refusal(manifest)\n"),
    (AUTHORITY, "a substituted adapter executes",
     "if adapter is not None and self.registry.adapters.get(cid) is not adapter:", "if False:"),
    (AUTHORITY, "a manifest that differs from the registered one executes",
     "if registered is not manifest and (registered is None or registered.digest() != manifest.digest()):",
     "if False:"),
    (AUTHORITY, "the context may name another capability",
     "            if named is not manifest and (named is None or named.capability_id != cid\n",
     "            if False and (named is None or named.capability_id != cid\n"),
    (AUTHORITY, "an equal copy of the registered manifest is refused",
     "if registered is not manifest and (registered is None or registered.digest() != manifest.digest()):",
     "if registered is not manifest:"),
]


def main() -> int:
    return run(MUTANTS, TESTS, prefix="authority-registered-identity-mutants-", root=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
