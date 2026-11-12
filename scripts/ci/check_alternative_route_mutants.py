"""Each rule that lets a mission finish through a signed alternative, and no further, must fail its tests when removed.

    python scripts/ci/check_alternative_route_mutants.py

Founder, 2026-11-12: "Determine whether GREG can repair the missing function through an allowed alternative, obtain
appraisal, and finish." "Capability repair cannot restore revoked authority." The rule is in greg/missions.py
``_pursue``: a candidate whose signed capability the founder detached is passed over while another candidate remains,
and the next one runs under its own scope, cone and approval. ``first_choice`` applies the same rule to asks made ahead
of the mission's loop. The mutants remove or widen that rule at each decision point the founder named:

* detached against revoked: only a founder detach is passed over, not a quarantined tool and not an approval a
  revoked device gave;
* inside against outside the cone: an alternative outside the cone stops at its own approval;
* the attach ask: none is raised while an alternative remains, and the record says why the preferred one was passed
  over;
* the completed effect: the alternative is one of the strategies that advance a failing check, so a completed effect
  is never chosen again.

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
     '    runnable = [r for r in ranked if r[3] not in detached]\n', '    runnable = []\n'),
]


if __name__ == "__main__":
    raise SystemExit(run(MUTANTS, TESTS, prefix="greg-alternative-route-mutants-"))
