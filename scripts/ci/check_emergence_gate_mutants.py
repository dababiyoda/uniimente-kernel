"""Each safeguard of the emergence gate (directive section 20, S20.A2) must fail its unit tests when removed.

    python scripts/ci/check_emergence_gate_mutants.py

Mutants are applied to greg/recombine.py and greg/genesis.py in a scratch copy of the repository, never to the working
tree; the copy runs without bytecode and its __pycache__ is purged before each mutant. A mutant is caught only when
tests/unit/test_greg_emergence_gate.py reports a FAILED test (an import or collection error does not count). Exit status
1 if any mutant survives or no longer applies.
"""
from pathlib import Path

from mutation_harness import run  # scripts/ci/mutation_harness.py: the shared loop

ROOT = Path(__file__).resolve().parents[2]
RECOMBINE = "greg/recombine.py"
GENESIS = "greg/genesis.py"
TESTS = "tests/unit/test_greg_emergence_gate.py"
MUTANTS = [
    (RECOMBINE, "a reduction without a runnable baseline passes",
     '    if spec is None:\n        return {**report, "verdict": "INTEGRATION",',
     '    if False:\n        return {**report, "verdict": "INTEGRATION",'),
    (RECOMBINE, "a baseline that cannot run counts as beaten",
     '            return {**report, "verdict": "INTEGRATION",\n'
     '                    "why": f"the baseline could not run on {case[\'name\']}: {type(exc).__name__}: {str(exc)[:120]}"}',
     '            reached = False'),
    (RECOMBINE, "the baseline's own answer is never compared",
     'reached = bool(spec.agrees(spec.baseline(reduction.normalize(case["input"])), case["expected"]))',
     'reached = False'),
    (RECOMBINE, "a construction worse than its baseline passes", '    if worse:\n', '    if False:\n'),
    (RECOMBINE, "an uncertified construction passes", '    if certified < len(cases):\n', '    if False:\n'),
    (RECOMBINE, "a baseline that reaches the exact answer everywhere passes", '    if not beaten:\n', '    if False:\n'),
    (RECOMBINE, "the gate does not decide qualification",
     'return not report["failures"] and report["emergence"]["verdict"] == "EMERGENT", report',
     'return not report["failures"], report'),
    (RECOMBINE, "the traps are not run", '    cases = head.oracle(seed) + traps\n', '    cases = head.oracle(seed)\n'),
    (RECOMBINE, "a trap's expected answer is not brute force",
     '"expected": spec.expect(reduction.normalize(params))', '"expected": spec.baseline(reduction.normalize(params))'),
    (RECOMBINE, "a construction that states no claim passes", '    if not str(spec.claim).strip():\n',
     '    if False:\n'),
    (RECOMBINE, "a construction that fails its oracle is recorded as refused by the gate",
     'if report is not None and not report.get("failures") and gate.get("verdict") == "INTEGRATION":',
     'if report is not None and gate.get("verdict") == "INTEGRATION":'),
    (RECOMBINE, "a construction qualified under a different gate counts as current",
     'gate.get("spec_digest") == emergence_digest(reduction) is not None', 'True'),
    (RECOMBINE, "the budgeted baseline keeps costs nothing needs",
     '        best = {i for i in best if value[i] > 0 or i in needed}\n', ''),
    (RECOMBINE, "the budgeted baseline ends below the empty plan",
     'return {"profit": max(0, sum(value[i] for i in best))}', 'return {"profit": sum(value[i] for i in best)}'),
    (GENESIS, "a refusal as integration reads as a failed qualification",
     'if (refusal := recombine.integration_refusal(report)) is None else refusal', 'if True else refusal'),
    (GENESIS, "a later tick relabels a refusal as integration",
     'refusal = None if prior["passed"] else recombine.integration_refusal(prior.get("report"), earlier=True)',
     'refusal = None'),
    (GENESIS, "a restore trusts a construction qualified under a different gate",
     'elif not recombine.gate_current(manifest.provenance.get("qualification"), found[0][0]):', 'elif False:'),
]


def main() -> int:
    return run(MUTANTS, TESTS, prefix="emergence-gate-mutants-", root=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
