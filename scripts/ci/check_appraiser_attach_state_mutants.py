"""Each safeguard that keeps the separate appraiser from running a capability that is not ATTACHED must fail its unit
tests when removed (founder directive re-issued 2026-11-04, behaviour B: "the Kernel must deny affected execution
immediately").

    python scripts/ci/check_appraiser_attach_state_mutants.py

Mutants are applied to greg/appraisal.py and greg/body.py in a scratch copy of the repository, never to the working
tree; the copy runs without bytecode and its __pycache__ is purged before each mutant. A mutant is caught only when
tests/unit/test_greg_appraiser_attach_state.py reports a FAILED test (an import or collection error does not count).
Exit status 1 if any mutant survives or no longer applies. The mission engine's safeguard that the same founder
commands exposed (one failure closure per completed-action count) is gated with the failure closure's own tests, in
scripts/ci/check_cognition_residual_mutants.py.
"""
from mutation_harness import run  # scripts/ci/mutation_harness.py: the shared loop

APPRAISAL = "greg/appraisal.py"
BODY = "greg/body.py"
TESTS = "tests/unit/test_greg_appraiser_attach_state.py"
MUTANTS = [
    # the rule: only ATTACHED runs, and only the reviewed read-only built-in this body holds registered
    (APPRAISAL, "a sensor that is not ATTACHED is re-run",
     '    if state != "ATTACHED":\n        return (f"{cid} is {state or',
     '    if False:\n        return (f"{cid} is {state or'),
    (APPRAISAL, "only a DETACHED sensor is refused (a quarantined or never-attached one runs)",
     '    if state != "ATTACHED":\n        return (f"{cid} is {state or',
     '    if state == "DETACHED":\n        return (f"{cid} is {state or'),
    (APPRAISAL, "a capability this body does not hold registered is taken for attached",
     '    state = registry.state.get(cid)\n    if state != "ATTACHED":',
     '    state = registry.state.get(cid, "ATTACHED")\n    if state != "ATTACHED":'),
    (APPRAISAL, "an adapter that is not the registered one is run",
     '(registry.manifests.get(cid) is not manifest or registry.adapters.get(cid) is not adapter)',
     '(registry.manifests.get(cid) is not manifest)'),
    (APPRAISAL, "a manifest that is not the registered one is run under",
     '(registry.manifests.get(cid) is not manifest or registry.adapters.get(cid) is not adapter)',
     '(registry.adapters.get(cid) is not adapter)'),
    (APPRAISAL, "a sensor that is not read-only is re-run",
     '    if manifest.consequence_class != "read_only":\n        return f"{cid} is',
     '    if False:\n        return f"{cid} is'),
    (APPRAISAL, "the attach rule is skipped where a sensor is re-run",
     'withheld = _withheld(registry, cap) if cap in REOBSERVABLE else None', 'withheld = None'),
    (APPRAISAL, "the read-only rule is skipped where a sensor is re-run",
     'never = _never_rerun(cap) if cap in REOBSERVABLE else None', 'never = None'),
    (APPRAISAL, "a delivery is re-derived for a capability that is not ATTACHED",
     'withheld = _not_attached(registry, action["capability"])', 'withheld = None'),
    # the verdict: never VERIFIED on what was not run, never REFUTED for it alone, never hiding a real refutation
    (APPRAISAL, "the re-observation check passes on a sensor that was not run",
     'checks["world_reobserved"] = reobserved and not unmeasured', 'checks["world_reobserved"] = reobserved'),
    (APPRAISAL, "the delivery check passes on a delivery that was not re-derived",
     'checks["deliveries_bound_to_evidence"] = delivered_ok and not underived',
     'checks["deliveries_bound_to_evidence"] = delivered_ok'),
    (APPRAISAL, "a capability that was not run refutes the closure",
     '            judged["verdict"] = "UNAVAILABLE"', '            judged["verdict"] = "REFUTED"'),
    (APPRAISAL, "UNAVAILABLE hides what an attached sensor re-read",
     'otherwise_whole=reobserved and delivered_ok)', 'otherwise_whole=delivered_ok)'),
    (APPRAISAL, "UNAVAILABLE hides a delivery that fails its re-derivation",
     'otherwise_whole=reobserved and delivered_ok)', 'otherwise_whole=reobserved)'),
    (APPRAISAL, "UNAVAILABLE hides a check that fails on the record",
     '        if otherwise_whole and all(checks.get(k) for k in required if k not in NOT_RUN_CHECKS):',
     '        if otherwise_whole:'),
    (APPRAISAL, "the appraisal does not say which capability it did not run",
     '        judged["not_run"] = dict(sorted(not_run.items()))\n', ''),
    (APPRAISAL, "the appraisal does not name the checks it could not re-measure",
     '            judged["unmeasured_checks"] = sorted(unmeasured)', '            pass'),
    # the body: recorded once as a verdict, appraised again only after an attach of what was not run
    (BODY, "the appraiser's answer is dropped as an unreadable verdict",
     'if not isinstance(verdict, dict) or not (verdict.get("verdict") in APPRAISER_VERDICTS\n'
     '                                                 or not_run_by_appraiser(verdict)):',
     'if not isinstance(verdict, dict) or not (verdict.get("verdict") in APPRAISER_VERDICTS):'),
    (BODY, "a capability that was not run counts as a failed appraiser run",
     'if verdict["verdict"] in APPRAISER_VERDICTS or not_run_by_appraiser(verdict):',
     'if verdict["verdict"] in APPRAISER_VERDICTS:'),
    (BODY, "a re-attach never lets the closure be appraised again",
     '        for mid, closure_event in self._reattached_closures():', '        for mid, closure_event in []:'),
    (BODY, "a closure is appraised again every tick, with no attach since",
     '            if all(self.registry.state.get(cid) == "ATTACHED" for cid in needed) \\\n'
     '                    and any(changed_at.get(cid, -1) > since for cid in needed):',
     '            if all(self.registry.state.get(cid) == "ATTACHED" for cid in needed):'),
    (BODY, "a closure is appraised again while something it waits on is still not ATTACHED",
     '            if all(self.registry.state.get(cid) == "ATTACHED" for cid in needed) \\\n'
     '                    and any(changed_at.get(cid, -1) > since for cid in needed):',
     '            if any(changed_at.get(cid, -1) > since for cid in needed):'),
    (BODY, "an attach of any capability has the closure appraised again",
     'and any(changed_at.get(cid, -1) > since for cid in needed):',
     'and any(at > since for at in changed_at.values()):'),
    (BODY, "a REFUTED appraisal that names something not run is appraised again",
     '    if not isinstance(verdict, dict) or verdict.get("verdict") != "UNAVAILABLE":\n        return {}',
     '    if not isinstance(verdict, dict):\n        return {}'),
    (BODY, "anything a child prints under not_run is taken for the appraiser's answer",
     '    return named if isinstance(named, dict) else {}', '    return named or {}'),
    (BODY, "a later appraisal of the same closure reuses the first one's identity",
     '        again = [earlier] if earlier else []', '        again = []'),
]

if __name__ == "__main__":
    raise SystemExit(run(MUTANTS, TESTS, prefix="greg-appraiser-attach-state-mutants-"))
