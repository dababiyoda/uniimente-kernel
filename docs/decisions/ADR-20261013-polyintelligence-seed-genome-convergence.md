# ADR: Converge the Polyintelligence Seed Genome v0.1 on main as cortex 0.1.6 (recommended: EXPERIMENT)

- Decision ID: polyintelligence-seed-genome-20261013
- Status: proposed
- Date: 2026-10-13
- Decision owner: Alfonso Lopez
- Deliberation level: Constitutional (shared contract names, closure registry and manifest entries; creates no authority)
- Founder intent references: [`INTENT-20261013-polyintelligence-seed-genome-v0.1`](../intent/INTENT-20261013-polyintelligence-seed-genome-v0.1.json); SG-001 to SG-012 in [`intents-polyintelligence-seed-genome-20261013.json`](../collaboration/intents-polyintelligence-seed-genome-20261013.json); INTENT-20260930-polyintelligence-cortex; INTENT-0030
- Machine-readable deliberation: [`deliberation-polyintelligence-seed-genome-20261013.json`](../collaboration/deliberation-polyintelligence-seed-genome-20261013.json)
  (passes the protocol's `validate_deliberation.py`)
- Supersedes: none (ADR-20260930-polyintelligence-cortex-seed stays in force for 0.1.5)
- Superseded by: none

## Problem

Sixteen draft lineages implement overlapping seeds (thirteen when this work began) and none is on `main`; every frozen comparison was
`INCONCLUSIVE` because no model was reachable; the main-compatible cortex had four verified defects and no caller;
the founder re-sent the review with "Build this: … in GitHub".

## Proposal

Recommended `EXPERIMENT`: productize PR #141 as cortex 0.1.6 (defects fixed with reproductions, frozen before the reported run),
recombine PR #139's binding seam into the standing cognition runtime, run the declared baselines from a recorded
frontier-model transcript through the unchanged frozen harness, register every lineage with a disposition.
Merge, attachment to a live runtime and promotion remain founder decisions.

## Measured result (frozen held-out, 42 items)

routed_seed 1.000 [1.000, 1.000], always_llm 0.905 [0.810, 0.976], llm_committee 0.929 [0.833, 1.000], always_abstain 0.577 [0.452, 0.696]; critical errors routed/llm/committee = 0/2/1; unsupported certainty = 0/3/3; exit GAIN_ABSENT.

| Geometry | routed_seed | always_llm | llm_committee |
| --- | --- | --- | --- |
| claim:association | 1.000 (n=1) | 1.000 (n=1) | 1.000 (n=1) |
| claim:factual_support | 1.000 (n=5) | 1.000 (n=5) | 1.000 (n=5) |
| claim:intervention | 1.000 (n=5) | 1.000 (n=5) | 1.000 (n=5) |
| claim:prediction | 1.000 (n=1) | 1.000 (n=1) | 1.000 (n=1) |
| composition | 1.000 (n=2) | 1.000 (n=2) | 1.000 (n=2) |
| estimate | 1.000 (n=6) | 1.000 (n=6) | 1.000 (n=6) |
| formal | 1.000 (n=11) | 0.909 (n=11) | 0.909 (n=11) |
| legal | 1.000 (n=1) | 1.000 (n=1) | 1.000 (n=1) |
| none | 1.000 (n=1) | 1.000 (n=1) | 1.000 (n=1) |
| normative_value | 1.000 (n=1) | 0.000 (n=1) | 1.000 (n=1) |
| options | 1.000 (n=5) | 0.600 (n=5) | 0.600 (n=5) |
| semantic | 1.000 (n=3) | 1.000 (n=3) | 1.000 (n=3) |

Where the baselines failed: H-F08 [formal]: always_llm recommend (unsupported certainty), llm_committee recommend (unsupported certainty); H-G03 [options]: always_llm abstain, llm_committee recommend (unsupported certainty); H-G04 [options]: always_llm recommend (critical, unsupported certainty, gate violation), llm_committee recommend (critical, unsupported certainty, gate violation); H-N01 [normative_value]: always_llm recommend (critical, unsupported certainty). The routed seed failed no item.

Kill criterion: not met: this is the first frozen version with the baselines run, and the routed seed has the critical-error advantage.

Addendum, 2026-10-14. The experiment report's own first kill condition does apply: once the baselines ran and the
exit was `GAIN_ABSENT`, the router stopped being a performance claim. The gates, receipts, verifier and abstention
stay as a safety layer because they reduced critical errors on this suite. That reduction is observed but not
established: exact one-sided McNemar p = 0.125 for harmful failures. At 42 items the frozen rule had only 10% power
to establish the observed gain over `always_llm`, and 3% over `llm_committee`. A future frozen version that decides
the question needs about 1,045 items on the frozen quality rule, or 93 items (144 if the seed itself failed harmfully 1% of the time) on a harmful-failure endpoint
fixed before any baseline reply is collected. That choice is the founder's. The full reasoning is in
`docs/cortex/SEED_EXPERIMENT_REPORT.md` (section "the decisive test, kill condition 1, and what would decide the
gain") and the numbers are in `tests/evidence/cortex-seed-v0.1.6/power-analysis.json`.

Read narrowly: the baseline model is from the same vendor family as the suite's authors; the suite is self-authored and
structured-only; 42 items give wide intervals; cost and latency are not comparable across arms. Full limits:
`tests/evidence/cortex-seed-v0.1.6/README.md`.

## Baseline and evidence

| Claim | Tier | Source | Finding |
| --- | --- | --- | --- |
| Frozen held-out comparison with the declared baselines RUN | deterministic_fixture | `tests/evidence/cortex-seed-v0.1.6/heldout-results.json` | routed_seed 1.000 [1.000, 1.000], always_llm 0.905 [0.810, 0.976], llm_committee 0.929 [0.833, 1.000], always_abstain 0.577 [0.452, 0.696]; critical errors routed/llm/committee = 0/2/1; unsupported certainty = 0/3/3; exit GAIN_ABSENT |
| Where the baselines failed | deterministic_fixture | `tests/evidence/cortex-seed-v0.1.6/README.md` | H-F08 [formal]: always_llm recommend (unsupported certainty), llm_committee recommend (unsupported certainty); H-G03 [options]: always_llm abstain, llm_committee recommend (unsupported certainty); H-G04 [options]: always_llm recommend (critical, unsupported certainty, gate violation), llm_committee recommend (critical, unsupported certainty, gate violation); H-N01 [normative_value]: always_llm recommend (critical, unsupported certainty); the routed seed failed none |
| Single-model baseline | sandbox_execution | `tests/evidence/cortex-seed-v0.1.6/baseline-transcript-audit.json` | every reported reply attributed to one frontier model (frontier-model-A) from its agent transcript; 55 baseline and 5 semantic replies first served by another (frontier-model-B) after a mid-collection model switch were re-collected with identical prompts and kept as unused partial transcripts |
| Per-geometry means | deterministic_fixture | `tests/evidence/cortex-seed-v0.1.6/README.md` | claim:association | 1.000 (n=1) | 1.000 (n=1) | 1.000 (n=1); claim:factual_support | 1.000 (n=5) | 1.000 (n=5) | 1.000 (n=5); claim:intervention | 1.000 (n=5) | 1.000 (n=5) | 1.000 (n=5); claim:prediction | 1.000 (n=1) | 1.000 (n=1) | 1.000 (n=1); composition | 1.000 (n=2) | 1.000 (n=2) | 1.000 (n=2); estimate | 1.000 (n=6) | 1.000 (n=6) | 1.000 (n=6); formal | 1.000 (n=11) | 0.909 (n=11) | 0.909 (n=11); legal | 1.000 (n=1) | 1.000 (n=1) | 1.000 (n=1); none | 1.000 (n=1) | 1.000 (n=1) | 1.000 (n=1); normative_value | 1.000 (n=1) | 0.000 (n=1) | 1.000 (n=1); options | 1.000 (n=5) | 0.600 (n=5) | 0.600 (n=5); semantic | 1.000 (n=3) | 1.000 (n=3) | 1.000 (n=3) |
| Baseline replies are tool-free and prompt-exact | sandbox_execution | `tests/evidence/cortex-seed-v0.1.6/baseline-transcript-audit.json` | 168 prompts requested, 168 served, 0 missing; every collected reply audited (one Read of its prompt file plus the structured output); semantic route served_by=transcript, observed {"model_label_on_receipts": "frontier-model-A", "prompts_missing": 0, "prompts_requested": 4, "prompts_served": 4} |
| Four 0.1.5 defects reproduced and fixed; one hard rule ported | unit_test | `tests/unit/test_cortex_defect_fixes.py` | D1 wrong-version settlement, D2 composition geometry, D3 cap disclosure, D4 expiry without as_of; D5 declared harm raises the consequence class (ported from #143) |
| Named Epistemic Finality Rule and typed CapabilityDeficit | unit_test | `tests/unit/test_cortex_finality_deficit.py` | every epistemic class has exactly one deciding jurisdiction; every receipt cites the rule, per route when composed; abstentions carry a typed CapabilityDeficit that requests formation and authorizes nothing |
| Binding to the standing runtime creates no authority | unit_test | `tests/unit/test_cortex_proposer.py` | runtime ticked with the real proposer; receipts ledgered; forged or authority-claiming receipts refused; no actuator import |
| Safeguards resist removal | unit_test | `scripts/ci/check_cortex_mutants.py` | 43 of 43 safeguard-removing mutants caught on 0.1.6 by behavioural tests; freeze-hash checks are deselected in the mutant run so that an edit to frozen code no longer counts as caught by the hash alone |
| Pre-run independent review | unit_test | `tests/unit/test_cortex_defect_fixes.py, test_cortex_finality_deficit.py, test_cortex_proposer.py, test_cortex_replay.py` | three reviewers attacked receipts, replay and authority before the reported run; an independent verifier re-ran each finding; 14 of 17 confirmed, each fixed with a regression test and a mutant; the 42 held-out routed items are unchanged on every scoring field |

Counterevidence:

| Claim | Tier | Source | Finding |
| --- | --- | --- | --- |
| Routing value over a strong model | deterministic_fixture | `tests/evidence/cortex-seed-v0.1.6/heldout-results.json#/exit` | GAIN_ABSENT: gain over always_llm not established (lower bound 0.024); gain over llm_committee not established (lower bound 0.000) |
| Suite independence | historical_artifact | `docs/cortex/SEED_EXPERIMENT_REPORT.md` | self-authored, structured-only; six geometry groups with n>=3 |
| Real outcomes | other | `cortex/memory.py` | no real outcome settled; in-memory ledger; causal-memory writer absent |
| Development partitions | deterministic_fixture | `tests/evidence/cortex-seed-v0.1.6/smoke-results.json` | smoke (4 items) replayed with both transcripts: all RUN arms 1.0; not a reported result |

## Alternatives

| Alternative | Advantages | Disadvantages | Evidence | Kill / rollback |
| --- | --- | --- | --- | --- |
| Another implementation from scratch | exactly the review's list, nothing else | duplicates #141 and #139; violates one-authority-many-capabilities (§3, §9); no measured history | docs/cortex/COGNITION_LINEAGES.json | rejected before build |
| Re-label #141 as approved | zero new code | exit stays INCONCLUSIVE; four defects stay live; no caller on main; lineages stay uncoordinated | PR #141 body; reader findings in CONVERGENCE_2026-10-13.md §5 | rejected: directive says build |
| Converge on the #137 stack (#143 bridge) | one-entry bridge; open-source engine certification; narrow measured gain vs run baselines | cannot reach main before #137 is decided; gain is vs non-model baselines; 47k-line dependency | PR #143 body; COGNITION_LINEAGES.json pr-143 | deferred to the #137 decision; mechanisms queued |
| Proposed design (this branch) | main-compatible; exit rule finally resolves on real baseline replies; defects fixed with reproductions; nothing activates | baseline model is a sibling of the suite's authors; transcript audit is post hoc; suite is self-authored and structured-only | tests/evidence/cortex-seed-v0.1.6/ | GAIN_ABSENT on two frozen versions with no critical-error advantage; any receipt asserting authority |
| Do nothing | no review burden | directive unexecuted; no evidence either way | — | rejected |
| Reversible experiment | one revert restores main | review burden | git log ebc2130..HEAD | as proposed design |

## Five-role review

| Role | Position | Material concerns | Recommendation |
| --- | --- | --- | --- |
| Founder-Intent Steward | The directive's own translation paragraphs are binding: meniscus = verified-envelope frontier, shield = layered verification, dominance = lawful capability. Every quoted paragraph is preserved byte for byte; the review's eight corrections are implemented or preserved in contracts. 'Build this' is read as approval of the review's closing proposal. | the goal set's rhetoric ('impermeable', 'total systemic dominance') must stay prohibited as literal claims; verbatim preservation versus the review's corrected forms | EXPERIMENT |
| Systems Architect | One authority, many governed capabilities: productize the main-compatible lineage, port the one missing seam from #139, register the rest. The binding uses the runtime's existing proposer slot, so there is no second runtime, gate or authority path. Replay serves the frozen harness without touching the freeze. | the composition cap is disclosed, not lifted; no persistence for the competence ledger yet | EXPERIMENT |
| Adversarial Reviewer | The frozen held-out result is GAIN_ABSENT: routed_seed 1.000 [1.000, 1.000], always_llm 0.905 [0.810, 0.976], llm_committee 0.929 [0.833, 1.000], always_abstain 0.577 [0.452, 0.696]; critical errors routed/llm/committee = 0/2/1; unsupported certainty = 0/3/3; exit GAIN_ABSENT. Read it narrowly: the baseline model is a sibling of the suite's authors; the suite is self-authored and structured-only; cost and latency are not comparable across arms; the routed seed's semantic organ was served by the same recorded model on four sourced items. A gain here is not superiority over a strong model in the wild; an absence here does not prove the opposite on free-text problems. | strongest counterexample: a strong single model with tools is hard to beat (LLMRouterBench); the comparison must be repeated on an externally authored suite before any promotion claim; the tool-free audit is post hoc, not a runtime restriction | EXPERIMENT |
| Operator and Maintainer | Reproducible: freeze v0.1.6 cut before the run; transcripts, audits and provenance committed beside the results; CI job 6 runs the new tests and mutants and labels its held-out artifact a drift guard. The cortex now closes its five closures under verifier V3 and declares the buildability standard under V5. | document volume; replay adds a code path that must stay out of the freeze by design | EXPERIMENT |
| Evidence and Welfare Guardian | Declared harm may raise the consequence class, never lower it (ported from #143's hard failure); an expiring mandate cannot pass without a reference instant; receipts that claim authority or spend beyond the ceiling are refused before ledgering; victim-protection and deterrence handoffs are unchanged from 0.1.5. | no real outcome has settled competence; the semantic organ has never run against a live local model | EXPERIMENT |

One agent performed all five roles; an independent reviewer pass and a pre-run independent review attacked the code.
That is a limitation, not independent human review.

## Pass 1 — structural inversion

- Intended outcome: A main-compatible, consequence-inert Seed Genome whose exit rule can finally resolve, bound to the one place GREG already deliberates, with every competing lineage registered.
- ADV-1 Replay lets the frozen harness measure real baselines: amplified — every later version can re-run the same transcript; negative results change routing evidence; reverses if a transcript produced under different prompts or with tool use would be a simulation, not a baseline
- ADV-2 Defects fixed with reproductions: amplified — settlement and composition keys are now trustworthy inputs for learned routing; reverses if a fix that changed held-out behaviour silently; checked item for item against 0.1.5
- ADV-3 Binding through the existing proposer slot: amplified — Goal Gravity (#160) and future callers get one entry; reverses if a downstream evaluator mapping draft.prepare to an executable capability; the adapter must never do this
- ADV-4 Lineage registry: amplified — mechanisms from the fourteen lineages that carry #137 are queued, not lost; reverses if registry rot if dispositions are not revisited after the #137 decision
- DIS-1 Baseline model is a sibling of the suite's authors: observable: recorded in provenance; bounded: next suite externally authored
- DIS-2 Post hoc tool audit: observable: audit file committed; convertible: a tool-less agent type when the runtime supports it
- DIS-3 Cost/latency not comparable: bounded: the exit rule's cost and latency criteria are reported as non-discriminating
- DIS-4 No real outcomes: accepted with owner: first outcome through the runtime binding is the review trigger
- Literalization check: No component exists because of a metaphor: cortex/organ/genome/seed name ordinary software; biological concepts must compile to mechanism or registration is refused.

## Pass 2 — adversarial compounding

- Attack: Attacked the strengthened design for evaluator capture (the replay could mislabel arms), authority creep through records_provider, freeze drift, and overclaiming in docs.
- NW-1 (gaming) A transcript could be relabelled as a local-model arm: arm_provenance replaces the disclosure and names the model; a missing provenance field refuses the run
- NW-2 (other) records_provider could inject permission-bearing records: gates accept permission only from provenance-checked origins; the candidate stays internal_write with execution_authority none; the Gate revalidates downstream
- NW-3 (overfit) Ported harm rule after the first 0.1.6 freeze: freeze re-cut before any reported run; the reported run's manifest hash is recorded on the results
- NW-4 (comprehensibility) A verified gain could be read as superiority: report and ADR read it narrowly; promotion stays a founder decision
- NW-5 (dependency) The session's serving model changed mid-collection, so one arm mixed two models: replies attributed per reply from agent transcripts; the 55 affected replies re-collected under one model; the earlier ones kept unused
- NW-6 (fragility) A transcript missing replies could score baselines as failures and read as a verified gain: found by the pre-run independent review; a replayed arm with any missing reply is NOT_RUN; mutant-checked
- Pass-1 downsides: DIS-1 accepted, owner Alfonso, threshold: externally authored suite; DIS-2 accepted, observable; DIS-3 bounded; DIS-4 accepted with review trigger
- Effect attacked separately: The underlying effect (better answers than a strong single model) is measured once, on one self-authored suite, with verdict GAIN_ABSENT; the safety properties are tested; neither is proof of value in the wild.

## Dissent

- Adversarial Reviewer: Do not read the held-out verdict as a claim about frontier models in general. Rationale: sibling-model baseline, self-authored structured suite, non-comparable cost and latency. Threshold: the same verdict on an externally authored free-text suite with a model from a different vendor family.

## Authority impact

- Changes authority: no. Level: constitutional.
- Authorized-human approval required: yes. Approval state: pending. Chat text does not
  authenticate the founder (Founder Intent Ledger SR-INTENT-3), so this record does not mark approval.

## Migration, rollback and kill criteria

- Migration: Merge the draft branch after founder review; no data migration; cortex stays SANDBOXED; every earlier freeze and result kept; #141 can merge first (its commits are ancestors).
- Rollback: revert the branch's commits (or the merge); the closure registry, manifest entry and KNOWN_CONTRACTS names leave with the revert.
- Kill criteria: GAIN_ABSENT against the declared baselines on two frozen versions with no critical-error advantage; any receipt or candidate found asserting authority; any cortex import of an actuator.
- Review trigger: Founder review of the draft PR; the #137 decision; the first real outcome settled through the runtime binding.

## Decision

`NEEDS_FOUNDER_DECISION` — the five roles recommend `EXPERIMENT` (merge SANDBOXED, unpromoted); merge, attachment to a live runtime and promotion are Alfonso's decisions.
