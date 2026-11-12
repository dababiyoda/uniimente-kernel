"""Each safeguard that keeps the separate appraiser from running a capability that is not ATTACHED must fail its unit
tests when removed (founder directive re-issued 2026-11-04, behaviour B: "the Kernel must deny affected execution
immediately").

    python scripts/ci/check_appraiser_attach_state_mutants.py

Mutants are applied in a scratch copy of the repository, never to the working tree: to greg/appraisal.py and
greg/body.py, and to the readers that must not take an appraisal that judged nothing for a failed one
(greg/routing.py, greg/sop.py, greg/compounding.py, greg/mission_control.py). The copy runs without bytecode and its
__pycache__ is purged before each mutant. A mutant is caught only when
tests/unit/test_greg_appraiser_attach_state.py reports a FAILED test (an import or collection error does not count).
Exit status 1 if any mutant survives or no longer applies. The mission engine's safeguard that the same founder
commands exposed (one failure closure per completed-action count) is gated with the failure closure's own tests, in
scripts/ci/check_cognition_residual_mutants.py.
"""
from mutation_harness import run  # scripts/ci/mutation_harness.py: the shared loop

APPRAISAL = "greg/appraisal.py"
BODY = "greg/body.py"
ROUTING = "greg/routing.py"
SOP = "greg/sop.py"
COMPOUNDING = "greg/compounding.py"
MISSION_CONTROL = "greg/mission_control.py"
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
    (APPRAISAL, "only a brief is held back: a detached venture or organ exchange has its organs re-run",
     'withheld = _not_attached(registry, action["capability"])',
     'withheld = _not_attached(registry, action["capability"]) if action["capability"] == "brief.engineering" else None'),
    # the verdict: never VERIFIED on what was not run, never REFUTED for it alone, never hiding a real refutation
    (APPRAISAL, "the re-observation check passes on a sensor that was not run",
     'checks["world_reobserved"] = reobserved and not unmeasured and not outdated',
     'checks["world_reobserved"] = reobserved and not outdated'),
    (APPRAISAL, "the delivery check passes on a delivery that was not re-derived",
     'checks["deliveries_bound_to_evidence"] = delivered_ok and not underived',
     'checks["deliveries_bound_to_evidence"] = delivered_ok'),
    (APPRAISAL, "a capability that was not run refutes the closure",
     '            judged["verdict"] = "UNAVAILABLE"', '            judged["verdict"] = "REFUTED"'),
    (APPRAISAL, "UNAVAILABLE hides what an attached sensor re-read",
     'otherwise_whole=reobserved and delivered_ok,', 'otherwise_whole=delivered_ok,'),
    (APPRAISAL, "UNAVAILABLE hides a delivery that fails its re-derivation",
     'otherwise_whole=reobserved and delivered_ok,', 'otherwise_whole=reobserved,'),
    (APPRAISAL, "UNAVAILABLE hides a check that fails on the record",
     '        if otherwise_whole and all(checks.get(k) for k in required if k not in NOT_RUN_CHECKS):',
     '        if otherwise_whole:'),
    (APPRAISAL, "the appraisal does not say which capability it did not run",
     '        judged["not_run"] = dict(sorted(not_run.items()))\n', ''),
    (APPRAISAL, "the appraisal does not name the checks it could not re-measure",
     '            judged["unmeasured_checks"] = sorted(unmeasured)', '            pass'),
    # a late appraisal (after a re-attach): a reading that disagrees is no evidence about the closure
    (APPRAISAL, "a late reading that disagrees refutes the closure",
     'if (now_ok is None or now_ok == unmet) and waited_on:', 'if False:'),
    (APPRAISAL, "a first appraisal's disagreeing reading is excused as a late one",
     'if (now_ok is None or now_ok == unmet) and waited_on:', 'if now_ok is None or now_ok == unmet:'),
    (APPRAISAL, "a late reading that disagrees passes as re-observed",
     'checks["world_reobserved"] = reobserved and not unmeasured and not outdated',
     'checks["world_reobserved"] = reobserved and not unmeasured'),
    (APPRAISAL, "the late answer is not told apart from a refutation",
     'late={"waited_on": sorted(waited_on), "checks": sorted(outdated)} if outdated else None,', 'late=None,'),
    (APPRAISAL, "a late answer is given only when a capability was also not run",
     '    if not_run or late:', '    if not_run:'),
    (APPRAISAL, "an appraisal of another closure of the mission makes this one late",
     'if (data.get("mission_id") == mid and data.get("closure_event") == closure_event',
     'if (data.get("mission_id") == mid'),
    (APPRAISAL, "another mission's appraisal makes this one late",
     'if (data.get("mission_id") == mid and data.get("closure_event") == closure_event',
     'if (data.get("closure_event") == closure_event'),
    (APPRAISAL, "a REFUTED appraisal that names something not run makes a later appraisal late",
     'and data.get("verdict") == "UNAVAILABLE" and isinstance(data.get("not_run"), dict)):',
     'and isinstance(data.get("not_run"), dict)):'),
    # a check left open is named, and only then
    (APPRAISAL, "a check left open is not named",
     '        judged["not_established"] = sorted(not_established)', '        pass'),
    (APPRAISAL, "a check a sensor measured failing is named as left open",
     'if held and left_open]', 'if left_open]'),
    # the body: recorded once as a verdict, appraised again only after an attach of what was not run
    (BODY, "the appraiser's own UNAVAILABLE is dropped as an unreadable verdict",
     '        if not appraiser_answered(verdict):',
     '        if not isinstance(verdict, dict) or verdict.get("verdict") not in APPRAISER_VERDICTS:'),
    (BODY, "the appraiser's own UNAVAILABLE counts as a failed appraiser run",
     '        if appraiser_answered(verdict):', '        if verdict["verdict"] in APPRAISER_VERDICTS:'),
    (BODY, "an answer that ran nothing is not taken for the appraiser's",
     'or bool(not_run_by_appraiser(verdict)) or bool(appraised_late(verdict)))', 'or bool(appraised_late(verdict)))'),
    (BODY, "a late answer is not taken for the appraiser's, and is retried as a failed run",
     'or bool(not_run_by_appraiser(verdict)) or bool(appraised_late(verdict)))',
     'or bool(not_run_by_appraiser(verdict)))'),
    (BODY, "a REFUTED appraisal that carries appraised_late reads as a late answer",
     '    if not isinstance(verdict, dict) or verdict.get("verdict") != "UNAVAILABLE":\n        return {}\n'
     '    late = verdict.get("appraised_late")',
     '    if not isinstance(verdict, dict):\n        return {}\n    late = verdict.get("appraised_late")'),
    (BODY, "anything a child prints under appraised_late is taken for the appraiser's answer",
     '    return late if isinstance(late, dict) else {}', '    return late or {}'),
    (BODY, "a closure that waited is appraised after the closures recorded since",
     '        self._appraise_reattached(now)\n        self._appraise_new_closures(now)',
     '        self._appraise_new_closures(now)\n        self._appraise_reattached(now)'),
    (BODY, "the final record written after a kill reuses the first appraisal's identity",
     '                key=[mid, "appraised", closure_event or last["head"], *again])',
     '                key=[mid, "appraised", closure_event or last["head"]])'),
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
     '    if not isinstance(verdict, dict) or verdict.get("verdict") != "UNAVAILABLE":\n        return {}\n'
     '    named = verdict.get("not_run")',
     '    if not isinstance(verdict, dict):\n        return {}\n    named = verdict.get("not_run")'),
    (BODY, "anything a child prints under not_run is taken for the appraiser's answer",
     '    return named if isinstance(named, dict) else {}', '    return named or {}'),
    (BODY, "a later appraisal of the same closure reuses the first one's identity",
     '        again = [earlier] if earlier else []', '        again = []'),
    # the readers: a check that was not measured is not the capability's; a waiting appraisal is not a failed one
    (ROUTING, "routing blames a capability for a check the appraiser left open",
     'effect_ok = all(data.get("checks", {}).get(c, False) or c in left_open for c in EFFECT_CHECKS)',
     'effect_ok = all(data.get("checks", {}).get(c, False) for c in EFFECT_CHECKS)'),
    (SOP, "a run whose appraisal waits for an attach counts as a failed SOP run",
     '    for mid in awaiting_appraisal(journal):', '    for mid in ():'),
    (SOP, "every UNAVAILABLE appraisal reads as waiting for an attach",
     '    return {mid for mid, appraisal in latest.items() if not_run_by_appraiser(appraisal)}',
     '    return {mid for mid, appraisal in latest.items() if appraisal.get("verdict") == "UNAVAILABLE"}'),
    (COMPOUNDING, "a reuse whose appraisal waits for an attach is worded as rejected",
     ' - set(verified) - awaiting\n', ' - set(verified)\n'),
    (MISSION_CONTROL, "the Proof list does not carry why an appraisal was UNAVAILABLE",
     '    if data.get("verdict") == "UNAVAILABLE":\n        row["why"]', '    if False:\n        row["why"]'),
    (MISSION_CONTROL, "the Proof view does not show why an appraisal was UNAVAILABLE",
     '_e(x.get("why", ""))', '""'),
    (MISSION_CONTROL, "every appraisal row reads as the achievement's",
     'f"{closure_kinds.get(closure, \'closure\')} {str(closure)[:8]}" if closure else "achievement"', '"achievement"'),
    (MISSION_CONTROL, "the Proof view does not show which closure an appraisal is for",
     '_e(x.get("closure", ""))', '""'),
]

if __name__ == "__main__":
    raise SystemExit(run(MUTANTS, TESTS, prefix="greg-appraiser-attach-state-mutants-"))
