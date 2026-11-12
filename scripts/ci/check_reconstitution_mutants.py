"""Each safeguard the functional-reconstitution lock rests on must fail it when removed.

    python scripts/ci/check_reconstitution_mutants.py

The lock is tests/unit/test_greg_functional_reconstitution.py: a lost function returns by another mechanism, a
completed write is not dispatched again, and a capability the founder detached is not brought back. The safeguards
are older than the lock; no gate removed any of them before, and neither test_greg_self_repair.py nor
test_greg_genesis_builder.py is run by a gate. Mutants are applied to greg/genesis.py and greg/missions.py in a scratch
copy of the repository, never to the working tree; the copy runs without bytecode and its __pycache__ is purged
before each mutant. A mutant is caught only when the test file reports a FAILED test (an import or collection error
does not count). Exit status 1 if any mutant survives or no longer applies.
"""
from pathlib import Path

from mutation_harness import run  # scripts/ci/mutation_harness.py: the shared loop

ROOT = Path(__file__).resolve().parents[2]
GENESIS = "greg/genesis.py"
MISSIONS = "greg/missions.py"
TESTS = "tests/unit/test_greg_functional_reconstitution.py"
MUTANTS = [
    (GENESIS, "a rebuilt implementation the founder detached is registered and attached again",
     '                if self.registry.state.get(manifest.capability_id) == "DETACHED":\n'
     '                    self._route(deficit_id, "builder", "founder-detached; explicit attach required",',
     '                if False:\n'
     '                    self._route(deficit_id, "builder", "founder-detached; explicit attach required",'),
    (GENESIS, "the search for a withheld implementation attaches one the founder detached",
     '        # 2. registered but detached\n        for manifest in self.registry.by_function(function):\n'
     '            if self.registry.state[manifest.capability_id] == "VERIFIED":',
     '        # 2. registered but detached\n        for manifest in self.registry.by_function(function):\n'
     '            if self.registry.state[manifest.capability_id] in ("VERIFIED", "DETACHED"):'),
    (MISSIONS, "a formed capability that keeps faulting is never re-formed",
     '            if streak < 2:\n                self.awaiting_repair.add(check_id)\n                continue\n'
     '            repaired, deferred = self._form(m, manifest.function, now, lambda: self.genesis.repair(',
     '            if True:\n                self.awaiting_repair.add(check_id)\n                continue\n'
     '            repaired, deferred = self._form(m, manifest.function, now, lambda: self.genesis.repair('),
    (MISSIONS, "a check that could not be measured is pursued alone: the write it reads is dispatched again",
     '        if errors and errors == failing:', '        if False:'),
]


if __name__ == "__main__":
    raise SystemExit(run(MUTANTS, TESTS, "greg-reconstitution-mutants-", root=ROOT))
