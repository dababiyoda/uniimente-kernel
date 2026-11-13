# Founder's First Mission: VEPMC 0 -> 1 on Body 1 (founder's Chromebook; iPhone as remote interface)

*Reality: sandbox / local. Generated 2026-10-14T16:29:21+00:00 from sources `greg/path.json` sha256:a4877c6b75d9, `foundry/completion.yaml` sha256:491782cb46eb. Nothing was sent, published, spent or merged.*

## Where you are trying to go

- Primary node **N1**: A founder-signed mission runs on the designated body, survives an interruption, uses a real capability, honors an approval boundary, is independently appraised and accepted by Alfonso
- Gate: Alfonso enables ChromeOS Linux (availability 'Unavailable/unsure' on 2026-09-26), runs greg/chromebook/install.sh, then the runbook's signed repository-brief mission with a deliberate kill -9, approval and acceptance

## What only you can decide

- Alfonso enables ChromeOS Linux (availability 'Unavailable/unsure' on 2026-09-26), runs greg/chromebook/install.sh, then the runbook's signed repository-brief mission with a deliberate kill -9, approval and acceptance — *the primary node's gate names an act only Alfonso can perform* (`greg/path.json#N1`)
- Implementation exists (pinned base by digest with mirror failover and digest verification, deterministic capability layer, OCI layout, securejoin unpacking, runc and gVisor runtime specs). In-session runs on 2026-09-30 before the pause: identical image digest … — *the gap names an authorization or execution-environment decision* (`foundry/completion.yaml#9`)
- Implementation exists (gVisor runsc, read-only image root, no network, no capabilities, non-root, clean env, wall-clock kill, hash-chained journal, SIEM-shaped denials). In-session run on 2026-09-30 before the pause: 7 of 7 escape probes denied inside gVisor. … — *the gap names an authorization or execution-environment decision* (`foundry/completion.yaml#10`)
- Non-privileged mechanism implemented (foundry/systems/segmentation.py): components launched through run_confined run under the Kernel seccomp filter (no socket of any family, no connect/io_uring/pidfd_getfd/setns; kernel-enforced) and reach only … — *the gap names an authorization or execution-environment decision* (`foundry/completion.yaml#26`)

## The highest-value work GREG can advance now

Effort budget 8 units (signed in the mission). Exact selection (`cognition.dp_knapsack (exact; independently verified in the receipt)`): value **99** for effort 8. Greedy baseline: value 99. Greedy is as good here, so the simpler method's answer stands.

### GREG recognizes a problem, recruits the smallest competent method or composition, produces typed evidence, respects authority, and improves future selection from outcomes
- Source `greg/path.json#horizons/competency_compiler`; reality: INTEGRATION-TESTED seed (cognition.solve, bounded worker, signed missions, kill -9 rehearsal); frozen routing-gain verdict GAIN_VERIFIED_AGAINST_RUN_BASELINES (v0.3; v0.2 GAIN_ABSENT); model arms not …
- Value 27 ({'proximity': 3, 'readiness': 3, 'breadth': 3}) for effort 2
- Existing code: cortex/routing.py, greg/cognition/bridge.py, cortex/evaluation/crossgeo.py
- Existing machinery: capabilities cognition.cortex, cognition.cortex.deterrence.accountability, cognition.cortex.estimation.fermi, cognition.cortex.evidence_causal, cognition.cortex.extraction.schedule, cognition.cortex.formal.z3, cognition.cortex.optimization.cpsat, cognition.cortex.semantic; Foundry systems none
- Capability deficits: none

### Alfonso talks to one GREG, signs what it may do, and reviews what happened
- Source `greg/path.json#horizons/founder_interface`; reality: INTEGRATION-TESTED
- Value 27 ({'proximity': 3, 'readiness': 3, 'breadth': 3}) for effort 2
- Existing code: greg/console.py, greg/planner.py, greg/tribunal.py
- Existing machinery: capabilities none matched; Foundry systems none
- Capability deficits: none

### One institution keeps pursuing authorized goals across process, model and machine replacement
- Source `greg/path.json#horizons/persistent_goal_pursuit`; reality: INTEGRATION-TESTED
- Value 27 ({'proximity': 3, 'readiness': 3, 'breadth': 3}) for effort 2
- Existing code: greg/missions.py, greg/body.py, provenance/ledger.py, greg/gravity.py
- Existing machinery: capabilities none matched; Foundry systems none
- Capability deficits: none

### Form, acquire or repair the function a goal needs, verify it independently, and resume the original goal
- Source `greg/path.json#horizons/capability_genesis`; reality: INTEGRATION-TESTED: installed-software acquisition for two unrelated functions reached from plain words without a model and rehearsed to VEPMC-counting closures; builder route faked in tests (one …
- Value 18 ({'proximity': 2, 'readiness': 3, 'breadth': 3}) for effort 2
- Existing code: greg/genesis.py, greg/recombine.py, greg/builders.py, greg/capabilities.py
- Existing machinery: capabilities none matched; Foundry systems none
- Capability deficits: none

## Frozen acceptance contract for the next work order

```json
{
 "order": "advance-horizon-competency-compiler",
 "objective": "Advance 'GREG recognizes a problem, recruits the smallest competent method or composition, produces typed evidence, respects authority, and improves future selection from outcomes' to its next evidence tier using the existing machinery named in the dossier.",
 "acceptance": {
  "evidence_tier_before": "INTEGRATION-TESTED seed (cognition.solve, bounded worker, signed missions, kill -9 rehearsal); frozen routing-gain verdi",
  "must_cite": "greg/path.json#horizons/competency_compiler",
  "must_not": [
   "create authority",
   "contact anyone",
   "spend",
   "publish",
   "merge"
  ],
  "verifier": "independent appraisal re-derives the claim from sources"
 },
 "uses": [
  "cognition.cortex",
  "cognition.cortex.deterrence.accountability",
  "cognition.cortex.estimation.fermi",
  "cognition.cortex.evidence_causal",
  "cognition.cortex.extraction.schedule",
  "cognition.cortex.formal.z3",
  "cognition.cortex.optimization.cpsat",
  "cognition.cortex.semantic"
 ],
 "deficits_to_resolve_first": []
}
```

## How sure this is

- Scores come from a declared prior over source fields (see scoring_model), not measured value. The selection is provably optimal for that model and budget; whether the model ranks real value correctly is the open question your review answers.

## What changed since last time

- This is the first First Mission on this body; nothing to compare yet.

## Lesson retained

- With 11 candidates and an effort budget of 8, the greedy baseline matched the exact optimum (99); the simpler method suffices at this scale.

## Next authorized step

- Review the selection; sign the next work order as a mission to execute it, or change the effort budget or the scoring weights and run the mission again. Founder decisions above stay with you.
