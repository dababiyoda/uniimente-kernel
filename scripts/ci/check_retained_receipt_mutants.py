"""Each safeguard that makes a retained Gate receipt read as the call that produced it read it must fail its unit
tests when removed.

    python scripts/ci/check_retained_receipt_mutants.py

A capability that refused leaves a negative receipt. The office reported any retained receipt of the same proposal as
DONE, so a body stopped between that receipt and the mission's record of it recorded the refusal as done after the
restart (a refused compensation on the record as DONE with the founder never asked; a refused read passing an
``absent`` check). The mutants below remove, one at a time: the reading of the receipt's result, what a retained
refusal keeps (its reason, its failure class), what a reused success keeps (its cost, its whole output), the reuse
itself, and the three consumers fixed with it (a refused compensation's lost question, an interrupted worker's
recovered receipt, the legacy-scope receipt).

Mutants are applied to greg/authority.py and greg/missions.py in a scratch copy of the repository, never to the
working tree; the copy runs without bytecode and its __pycache__ is purged before each mutant. A mutant is caught only
when tests/unit/test_greg_retained_receipt.py reports a FAILED test (an import or collection error does not count).
Exit status 1 if any mutant survives or no longer applies.
"""
from pathlib import Path

from mutation_harness import run  # scripts/ci/mutation_harness.py: the shared loop

ROOT = Path(__file__).resolve().parents[2]
TESTS = "tests/unit/test_greg_retained_receipt.py"
# (name, target, old, new), with the target written out: scripts/repo_review.py reads a literal path followed by its
# anchor, so tests/unit/test_repo_health_gates.py fails on a stale anchor here before this gate ever runs.
MUTANTS = [
    # the office: one reading of a receipt
    ("a retained refusal is not reported as the refusal it was", "greg/authority.py",
     '        if klass == "negative":\n            return ActionOutcome("REFUSED", [result.get(',
     '        if False:\n            return ActionOutcome("REFUSED", [result.get('),
    ("a receipt that is not positive is reported DONE (the defect)", "greg/authority.py",
     '        if klass != "positive":\n            return ActionOutcome("UNCERTAIN", [',
     '        if False:\n            return ActionOutcome("UNCERTAIN", ['),
    ("an inconclusive, unclassed or unreadable result is read as a refusal, which lets the action be tried again",
     "greg/authority.py", '        if klass == "negative":\n', '        if klass != "positive":\n'),
    ("a result that is not a mapping crashes the reading", "greg/authority.py",
     '        result = result if isinstance(result, dict) else {}\n', ''),
    ("a retained refusal loses the capability's own reason", "greg/authority.py",
     '[result.get("observed_outcome", "capability failed")]', '[reused or "capability failed"]'),
    ("a retained refusal loses its failure class", "greg/authority.py",
     'failure_class=result.get("failure_class"), **kept)', '**kept)'),
    ("a reused success loses its cost", "greg/authority.py",
     'output=result.get("output"), cost_usd=cost_usd,', 'output=result.get("output"),'),
    ("a reused success loses the whole output its receipt kept", "greg/authority.py",
     '                             output_artifact=result.get("output_artifact"), **kept)',
     '                             **kept)'),
    ("a reused success loses its output", "greg/authority.py",
     'return ActionOutcome("DONE", [reused] if reused else [], output=result.get("output"), ',
     'return ActionOutcome("DONE", [reused] if reused else [], '),
    ("a reused receipt is not said to be reused", "greg/authority.py",
     'return ActionOutcome("DONE", [reused] if reused else [], ', 'return ActionOutcome("DONE", [], '),
    ("the retained receipt of this proposal is not found again (its answer becomes UNCERTAIN)", "greg/authority.py",
     '        if receipt is not None:  # already dispatched before an interruption: reuse, never redo',
     '        if False:  # already dispatched before an interruption: reuse, never redo'),
    ("a retained receipt under the earlier scope form is not found again", "greg/authority.py",
     '            if old_receipt is not None:   # a refusal keeps its own reason and failure class, as below',
     '            if False:   # a refusal keeps its own reason and failure class, as below'),
    ("no retained dispatch under the earlier scope form is looked for: the act runs again", "greg/authority.py",
     '        if legacy_scope != scope:\n', '        if False:\n'),
    # the engine: the consumers of that reading
    ("a compensation that did not complete is not asked about once its record exists", "greg/missions.py",
     '                if closed[aid].get("status") not in COMPENSATION_SETTLED:\n', '                if False:\n'),
    ("a refused compensation counts as settled", "greg/missions.py",
     'COMPENSATION_SETTLED = ("DONE", "FOUNDER_DECIDED", "DECLINED")',
     'COMPENSATION_SETTLED = ("DONE", "FOUNDER_DECIDED", "DECLINED", "REFUSED")'),
    ("the question a crash lost is asked without the reasons the record kept", "greg/missions.py",
     'failure=closed[aid].get("reasons") or [closed[aid].get("status")])', 'failure=[closed[aid].get("status")])'),
    # the copy in _record_outcome (it follows ``aid = s["action_id"]``); the dispatch keeps an identical, redundant one
    ("an interrupted worker's receipt is recorded DONE", "greg/missions.py",
     '        aid = s["action_id"]\n'
     '        if (manifest.capability_id == "worker.commission" and outcome.status == "DONE"\n'
     '                and isinstance(outcome.output, dict) and outcome.output.get("status") == "UNCERTAIN"):\n',
     '        aid = s["action_id"]\n'
     '        if False:\n'),
    ("a recovered receipt is recorded DONE whatever its result", "greg/missions.py",
     '                outcome = self.office.outcome_of(\n'
     '                    receipt, cost_usd=float(s.get("cost_usd", 0.0)),\n'
     '                    reused="retained receipt of a dispatch the body did not record before it stopped", **base)',
     '                outcome = ActionOutcome("DONE", ["retained receipt"], receipt_hash=receipt.hash,\n'
     '                                        output=(receipt.payload.get("result") or {}).get("output"), **base)'),
    ("a dispatch the body never recorded is not settled on a mission the founder ended", "greg/missions.py",
     '            if self._recover_dispatch(m, now) is not None:\n'
     '                # The founder ended the mission before the restarted body stepped it',
     '            if False:\n'
     '                # The founder ended the mission before the restarted body stepped it'),
]


def main() -> int:
    return run([(target, name, old, new) for name, target, old, new in MUTANTS], TESTS,
               prefix="retained-receipt-mutants-", root=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
