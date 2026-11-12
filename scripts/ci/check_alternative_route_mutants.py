"""Each rule that lets a mission finish through a signed alternative, and no further, must fail its tests when removed.

    python scripts/ci/check_alternative_route_mutants.py

Founder, 2026-11-12: "Determine whether GREG can repair the missing function through an allowed alternative, obtain
appraisal, and finish." "Capability repair cannot restore revoked authority." The rule is in greg/missions.py
``_pursue``: a candidate whose signed capability the founder detached is passed over for the next candidate, when that
one's own capability resolves now, and the next one runs under its own scope, cone and approval. ``first_choice``
applies the same rule to asks made ahead of the mission's loop, and ``_withdraw_moot_asks`` to asks already open. The
mutants remove or widen that rule at each decision point the founder named:

* detached against revoked: only a founder detach is passed over, not a quarantined tool and not an approval a
  revoked device gave;
* inside against outside the cone: an alternative outside the cone stops at its own approval;
* the attach ask: none is raised while an alternative remains, and the record says why the preferred one was passed
  over;
* the completed effect: the alternative is one of the strategies that advance a failing check, so a completed effect
  is never chosen again;
* an alternative whose own tool cannot run now is not chosen: the detached tool's attach is asked for, and its
  re-attach unblocks the mission (review of #312, X3);
* an open APPROVAL is withdrawn, as a body event, when a founder detach or attach made it one no approve can run: the
  move's own tool is detached while the selection runs another, or a strategy the ask records as passed over is no
  longer detached and the selection runs it again; nothing else withdraws it (review of #312, X1, X2, X4, X5).

Mutants are applied in a scratch copy of the repository, never to the working tree; the copy runs without bytecode and
its __pycache__ is purged before each mutant. A mutant is caught only when tests/unit/test_greg_alternative_route.py
reports a FAILED test (an import or collection error does not count). Exit status 1 if any mutant survives or no
longer applies.
"""
from mutation_harness import run  # scripts/ci/mutation_harness.py: the shared loop

MISSIONS = "greg/missions.py"
TESTS = "tests/unit/test_greg_alternative_route.py"
DETACHED = '        return cid if cid is not None and self.registry.state.get(cid) == "DETACHED" else None\n'
RUNNABLE = '        runnable = [c for c in candidates if self._detached(c[3]) is None]\n'
MUTANTS = [
    # the attach ask: the preferred strategy is pursued whatever its tool's state, so its attach is asked for and the
    # signed alternative never runs
    (MISSIONS, "a detached strategy is pursued first: its attach is asked for while a signed alternative could serve",
     RUNNABLE, '        runnable = []\n'),
    (MISSIONS, "the record of the alternative does not say the preferred strategy was passed over, or why",
     '        if passed:      # said where the founder reads the run', '        if False:       # said where'),
    # detached against revoked
    (MISSIONS, "any capability not ATTACHED is passed over: a quarantined tool is routed around, not searched for",
     DETACHED, DETACHED.replace('== "DETACHED"', '!= "ATTACHED"')),
    (MISSIONS, "an approval a revoked device gave counts as a detached tool: the alternative runs instead of the ask",
     DETACHED, '        return cid if cid is not None and (self.registry.state.get(cid) == "DETACHED" or any(\n'
               '            (self.book.requests.get(rid) or {}).get("action_id") == s.get("action_id")\n'
               '            for rid in self.book.voided)) else None\n'),
    # inside against outside the cone
    (MISSIONS, "an alternative chosen in place of a detached strategy runs as if the signed mission pre-approved it",
     '        signed = frozenset({scope}) if pre_approved(m.spec, s, manifest) else frozenset()\n',
     '        signed = frozenset({scope}) if pre_approved(m.spec, s, manifest) or passed else frozenset()\n'),
    # the completed effect: the next strategy in signed order, not the next candidate for a failing check
    (MISSIONS, "the alternative is the next strategy in signed order: the completed effect A is chosen and runs again",
     RUNNABLE, '        runnable = [(0.0, 0, i, x, 0.5) for i, x in enumerate(m.spec["strategies"])\n'
               '                    if self._detached(x) is None and x["action_id"] not in m.failed] \\\n'
               '            if self._detached(candidates[0][3]) else [c for c in candidates if self._detached(c[3]) is None]\n'),
    # asks made ahead of the loop follow the mission's own selection
    (MISSIONS, "an ask ahead of the loop may name the detached strategy the mission will not run",
     '    runnable = [a for a in ranked if a not in detached]\n', '    runnable = []\n'),
    # an alternative is chosen only when its own tool can run now (X3)
    (MISSIONS, "the detached strategy is passed over for an alternative whose tool is not attached",
     '        ranked = runnable if runnable and self._resolve(runnable[0][3])[0] is not None else candidates\n',
     '        ranked = runnable or candidates\n'),
    (MISSIONS, "the selection behind an ask passes over a detached strategy for an alternative that cannot run",
     '    if runnable and runnable[0] not in unresolved:\n', '    if runnable:\n'),
    (MISSIONS, "the engine gives the selection no alternative that cannot resolve",
     '                             unresolved={s["action_id"] for s in strategies if self._resolve(s)[0] is None})\n',
     '                             unresolved=())\n'),
    # an open APPROVAL a detach made moot is withdrawn (X2, X5), and only when the selection runs another move
    (MISSIONS, "an open APPROVAL for a detached strategy stays the blocker while the selection runs another",
     '            if gone is not None:\n                moot.append((rid, f"the founder detached {gone}',
     '            if False:\n                moot.append((rid, f"the founder detached {gone}'),
    (MISSIONS, "an open APPROVAL for a detached strategy is withdrawn even when no other strategy remains",
     '            if first is None or first == aid:\n                continue\n            if gone is not None:\n',
     '            if (first is None or first == aid) and gone is None:\n                continue\n'
     '            if gone is not None:\n'),
    # an open APPROVAL a re-attach made moot is withdrawn (X1, X4)
    (MISSIONS, "the alternative's ask stays the blocker after the passed-over tool is attached again",
     '            back = back.get(first)\n', '            back = None\n'),
    (MISSIONS, "an unpaid ask raised for an alternative does not record which strategy was passed over",
     '                                evidence={"routing": routing_decision} if routing_decision.get("passed_over") else None,\n',
     '                                evidence=None,\n'),
    (MISSIONS, "an ask made ahead of the loop does not record which strategy the selection passed over",
     '        passed = {"passed_over": scope["passed_over"]} if scope["passed_over"] else {}\n',
     '        passed = {}\n'),
]


if __name__ == "__main__":
    raise SystemExit(run(MUTANTS, TESTS, prefix="greg-alternative-route-mutants-"))
