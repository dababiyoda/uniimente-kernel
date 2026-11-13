"""Each safeguard that makes a retained Gate receipt read as the call that produced it read it must fail its unit
tests when removed.

    python scripts/ci/check_retained_receipt_mutants.py

A capability that refused leaves a negative receipt. The office reported any retained receipt of the same proposal as
DONE, so a body stopped between that receipt and the mission's record of it recorded the refusal as done after the
restart (a refused compensation on the record as DONE with the founder never asked; a refused read passing an
``absent`` check). The mutants below remove, one at a time: the reading of the receipt's result, what a retained
refusal keeps (its reason, its failure class), what a reused success keeps (its cost, its whole output), the reuse
itself, and the three consumers fixed with it (a refused compensation's lost question, an interrupted worker's
recovered receipt, the legacy-scope receipt). An adversarial review of e24b326c added the rules its own mutants showed
no test for: the cost booked for a recovered paid receipt, which compensation records leave a question for the
founder, the worker rule's limit to commissioned workers, and an unreadable receipt read through ``act``.

HISTORY_MUTANTS are judged by a second test file. They remove what makes the Gate's own record decide after a restart
whatever the capability's state is now: for a strategy (``_recover_dispatch``) and for a compensation
(``_run_compensation`` reads the Gate's record of the compensation's proposal before it looks at the capability).

Mutants are applied to greg/authority.py and greg/missions.py in a scratch copy of the repository, never to the
working tree; the copy runs without bytecode and its __pycache__ is purged before each mutant. A mutant is caught only
when its test file (tests/unit/test_greg_retained_receipt.py for MUTANTS,
tests/unit/test_greg_retained_receipt_history.py for HISTORY_MUTANTS) reports a FAILED test; an import or collection
error does not count. Both lists always run. Exit status 1 if any mutant of either survives or no longer applies.

Mutants of this change that are not listed, and why:

- reading the receipt of a fresh dispatch by a separate two-way reading (positive: DONE; anything else: REFUSED)
  where ``act`` calls ``outcome_of``. Equivalent: the Gate stores the executor's result unchanged, and the
  executor defined in ``act`` returns a mapping whose class is "positive" or "negative" and nothing else, so no
  fresh receipt reaches the third reading. A test could tell the two apart only by replacing that executor.
- removing the dispatch site's own copy of the interrupted-worker rule. Equivalent: ``_record_outcome`` applies
  the same rule to the same outcome immediately afterwards (the copy is kept so PR #273 merges without a conflict).
"""
from pathlib import Path

from mutation_harness import run  # scripts/ci/mutation_harness.py: the shared loop

ROOT = Path(__file__).resolve().parents[2]
TESTS = "tests/unit/test_greg_retained_receipt.py"
HISTORY_TESTS = "tests/unit/test_greg_retained_receipt_history.py"
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
    ("a retained receipt under the earlier scope form is reported under the new proposal, not the one it was "
     "dispatched as", "greg/authority.py",
     'reused="retained legacy receipt; no redispatch",\n                                       **old_base)',
     'reused="retained legacy receipt; no redispatch",\n                                       **base)'),
    ("an unreadable retained receipt asked about again through act is reported as a refusal", "greg/authority.py",
     '            return self.outcome_of(receipt, cost_usd=cost_usd, reused="retained receipt reused after restart", '
     '**base)',
     '            _o = self.outcome_of(receipt, cost_usd=cost_usd, reused="retained receipt reused after restart", '
     '**base)\n'
     '            if _o.status == "UNCERTAIN":\n'
     '                _o.status = "REFUSED"\n'
     '            return _o'),
    ("an unreadable retained receipt under the earlier scope form is reported as a refusal", "greg/authority.py",
     '                return self.outcome_of(old_receipt, cost_usd=cost_usd, '
     'reused="retained legacy receipt; no redispatch",\n'
     '                                       **old_base)',
     '                _o = self.outcome_of(old_receipt, cost_usd=cost_usd, '
     'reused="retained legacy receipt; no redispatch",\n'
     '                                       **old_base)\n'
     '                if _o.status == "UNCERTAIN":\n'
     '                    _o.status = "REFUSED"\n'
     '                return _o'),
    # the engine: the consumers of that reading
    ("a compensation that did not complete is not asked about once its record exists", "greg/missions.py",
     '                if closed[aid].get("status") not in COMPENSATION_SETTLED:\n', '                if False:\n'),
    ("a refused compensation counts as settled", "greg/missions.py",
     'COMPENSATION_SETTLED = ("DONE", "FOUNDER_DECIDED", "DECLINED")',
     'COMPENSATION_SETTLED = ("DONE", "FOUNDER_DECIDED", "DECLINED", "REFUSED")'),
    ("the question a crash lost is asked without the reasons the record kept", "greg/missions.py",
     'failure=closed[aid].get("reasons") or [closed[aid].get("status")])', 'failure=[closed[aid].get("status")])'),
    ("a lost question about a record that kept no reasons names no failure (it then says no compensation was signed)",
     "greg/missions.py",
     'failure=closed[aid].get("reasons") or [closed[aid].get("status")])', 'failure=closed[aid].get("reasons"))'),
    ("a compensation the founder declined is asked about again", "greg/missions.py",
     'COMPENSATION_SETTLED = ("DONE", "FOUNDER_DECIDED", "DECLINED")',
     'COMPENSATION_SETTLED = ("DONE", "FOUNDER_DECIDED")'),
    ("an uncertain compensation counts as settled: its lost question is never asked", "greg/missions.py",
     'COMPENSATION_SETTLED = ("DONE", "FOUNDER_DECIDED", "DECLINED")',
     'COMPENSATION_SETTLED = ("DONE", "FOUNDER_DECIDED", "DECLINED", "UNCERTAIN")'),
    ("an unavailable compensation counts as settled: its lost question is never asked", "greg/missions.py",
     'COMPENSATION_SETTLED = ("DONE", "FOUNDER_DECIDED", "DECLINED")',
     'COMPENSATION_SETTLED = ("DONE", "FOUNDER_DECIDED", "DECLINED", "UNAVAILABLE")'),
    ("only a refused compensation's lost question is asked", "greg/missions.py",
     '                if closed[aid].get("status") not in COMPENSATION_SETTLED:\n',
     '                if closed[aid].get("status") == "REFUSED":\n'),
    ("a compensation that completed is asked about as if it had not", "greg/missions.py",
     '                if closed[aid].get("status") not in COMPENSATION_SETTLED:\n', '                if True:\n'),
    # the copy in _record_outcome (it follows ``aid = s["action_id"]``); the dispatch keeps an identical, redundant one
    ("an interrupted worker's receipt is recorded DONE", "greg/missions.py",
     '        aid = s["action_id"]\n'
     '        if (manifest.capability_id == "worker.commission" and outcome.status == "DONE"\n'
     '                and isinstance(outcome.output, dict) and outcome.output.get("status") == "UNCERTAIN"):\n',
     '        aid = s["action_id"]\n'
     '        if False:\n'),
    ("the interrupted-worker rule is applied to every capability", "greg/missions.py",
     '        aid = s["action_id"]\n'
     '        if (manifest.capability_id == "worker.commission" and outcome.status == "DONE"\n',
     '        aid = s["action_id"]\n'
     '        if (True and outcome.status == "DONE"\n'),
    ("a recovered interrupted worker keeps the reuse reason, not the interruption's", "greg/missions.py",
     'without a conflict there.)\n'
     '            outcome.status = "UNCERTAIN"\n'
     '            outcome.reasons = ["worker execution interrupted; partial outcome and spend require '
     'reconciliation"]\n',
     'without a conflict there.)\n'
     '            outcome.status = "UNCERTAIN"\n'),
    ("a recovered receipt of a paid action books no spend", "greg/missions.py",
     '                    receipt, cost_usd=float(s.get("cost_usd", 0.0)),\n'
     '                    reused="retained receipt of a dispatch',
     '                    receipt, cost_usd=0.0,\n'
     '                    reused="retained receipt of a dispatch'),
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


# Judged by HISTORY_TESTS: the Gate's record decides after a restart, whatever the capability's state is now.
HISTORY_MUTANTS = [
    # a strategy the body did not record (_recover_dispatch)
    ("a recovered receipt is not said to be recovered", "greg/missions.py",
     'reused="retained receipt of a dispatch the body did not record before it stopped", **base)', '**base)'),
    ("the engine's recovery records an unreadable receipt as a refusal, which lets the action be tried again",
     "greg/missions.py",
     '                    reused="retained receipt of a dispatch the body did not record before it stopped", **base)\n',
     '                    reused="retained receipt of a dispatch the body did not record before it stopped", **base)\n'
     '                if outcome.status == "UNCERTAIN":\n'
     '                    outcome.status = "REFUSED"\n'),
    # a compensation the body did not record (_run_compensation, _dispatched_compensation)
    ("the Gate's record of a compensation is not read before its capability's state decides", "greg/missions.py",
     '        if settled is not None:\n', '        if False:\n'),
    ("a compensation whose capability is detached has no scope to look its dispatch up by", "greg/missions.py",
     '        known = manifest or self.registry.manifests.get(declared.get("capability"))\n',
     '        known = manifest\n'),
    ("a compensation's dispatch claim with no receipt is not an unknown outcome: the capability's state decides",
     "greg/missions.py",
     '        claim, receipt = self.office.prior(proposal_id)\n        if claim is None:\n',
     '        claim, receipt = self.office.prior(proposal_id)\n        if claim is None or receipt is None:\n'),
    ("a compensation's retained receipt is recorded DONE whatever its result", "greg/missions.py",
     '            return self.office.outcome_of(\n'
     '                receipt, cost_usd=0.0,\n'
     '                reused="retained receipt of a compensation the body did not record before it stopped", **base)',
     '            return ActionOutcome("DONE", ["retained receipt"], receipt_hash=receipt.hash, **base)'),
    ("a compensation's retained receipt is not said to be one the body did not record", "greg/missions.py",
     '                reused="retained receipt of a compensation the body did not record before it stopped", **base)',
     '                **base)'),
    ("the lookup names another proposal than the one the compensation was dispatched as", "greg/missions.py",
     '        proposal_id = self.office.proposal_id(scope, compensation_attempt(aid, original))\n',
     '        proposal_id = self.office.proposal_id(scope, compensation_attempt(aid, None))\n'),
]


def main() -> int:
    # Both lists run to the end: a survivor in the first does not hide one in the second.
    codes = [run([(target, name, old, new) for name, target, old, new in mutants], tests,
                 prefix="retained-receipt-mutants-", root=ROOT)
             for tests, mutants in ((TESTS, MUTANTS), (HISTORY_TESTS, HISTORY_MUTANTS))]
    return int(any(codes))


if __name__ == "__main__":
    raise SystemExit(main())
