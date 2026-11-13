# Founder decisions, prepared 2026-10-21

**Status: prepared, not decided.** These are the decisions that INTENT-20261021-MIND-MAXIMUM-CONTINUATION keeps
separate. Each section gives:
- the exact change proposed;
- the strongest alternative;
- the evidence;
- the tradeoff;
- how it would be rolled back.

No engineering work that does not depend on a decision is waiting for it. Nothing here creates authority.

## D1. How the frozen P8 `RULE` treats wrong answers

**The problem.** `evolution.RULE` reads "no stress set worsens by > 5%" and "RETAIN iff … lower mean loss". On
targets where a wrong answer scores +inf, one wrong answer makes a mean infinite. Two consequences follow:
- **Held-out step:** a candidate with any wrong answer can never show a "lower mean". This is why immune-7 and
  immune-8 are NOT_VIABLE (`2026-10-21-immune-7/`, `2026-10-21-immune-8/`).
- **Stress gate:** the executable gate (32246ee, audited in `2026-10-21-stress-gate-audit/`) orders wrong-answer
  counts with zero tolerance. The text does not say this (audit item P5).

**Proposed change (`RULE` v2).** Wrong answers and the loss on answered items become separate criteria at both
gates:
1. The candidate's wrong-answer count may not exceed the incumbent's on any stress set or on held-out.
2. The one-sided exact Clopper-Pearson 95% upper bound on the candidate's wrong-answer rate is reported beside the
   verdict.
3. Loss is compared on the items both answered:
   - the stress gate allows at most 5% worsening;
   - the held-out step RETAINs iff its sign test gives p < alpha and the both-answered mean is lower.
4. Abstentions keep their declared finite cost (audit P4).

**Strongest alternative: keep `RULE` v1 as frozen.**
- It is simpler and has been in every freeze since cycle 1.
- Under it, immune targets cannot RETAIN, and that blocks only that target family.
- Constraint release, which has finite losses, is unaffected.

**Evidence.**
- Immune-8: every pick improves paired F1, 339-206 to 404-150 on 640 fresh items, but makes 4-6 false-alarm
  violations per 640 against the incumbent's 3.
- Hotelling beats the incumbent 546-81, yet makes 11 violations.
- So the second criterion would not have rescued immune-8. Its picks have more wrong answers, and the proposed rule
  still rejects them.
- The change would make the rule's text match what it does. It would not make immune passable.

**Tradeoff.**
- v2 is more honest and target-neutral.
- But it changes every future freeze and evaluator seal, and it adds a statistic (the both-answered subset, audit P2)
  that drops items either side got wrong.

**Rollback.** Freezes record the `RULE` text and its digest, so v1 stays reproducible by name.

## D2. Cycle 6's proposal: adopt it, adopt random restart instead, or neither

**Proposed change, option A.** Set `CR_DEFAULT_CONFIG.p_restart` to 0.807 (and `p_extra_mutation_recombined` to
0.55), bump `develop_constraint_release` to 1.3.0 together with its pin, and re-admit on fresh seeds.

**Strongest alternative, option B.** Replace the genome's evolutionary search with random restart, its own
admission competitor.

**Evidence.**

| Measurement | Result |
|---|---|
| Cycle 6, held-out | 105-73 vs the incumbent, p = 0.00995. Survives the four-attempt threshold, not the programme-wide 0.00833 |
| Canary, 240 fresh seeds | 107-74 vs the incumbent, p = 0.0086 |
| Random restart vs the proposal | 89-80 (cycle 6) and 95-79 (canary, p = 0.128): not significant either time |
| Random restart's mean loss | Lowest in every measurement and subregion |
| Admission v2 / v3 | Random restart 15-5 and 13-10 |

**Tradeoff.**
- A is the first output of protected evolution, through the verified route.
- B is simpler and at least as good by every point estimate. Its advantage over A is not statistically established.
- Either is far better than the incumbent: mean loss is about 30-34% lower.

**Rollback.** Revert the constant and the pin to `cfg-111751096c0d` / 1.2.0. Admission evidence for 1.2.0 stays
valid by version.

## D3. Attaching genomes

**Proposed change.** Attach the admitted exact methods where evidence shows they are canonical for their geometry:
- `flow_expansion_mcf`: DEFAULT; matches F7 200/200 at 0.26x latency;
- `grid_dijkstra` 1.1.0: DEFAULT.

In addition, after admission v5 (not yet run), consider:
- the exact node-cut genome (in development);
- `crowd_weighted_vote`;
- `community_louvain`.

**Strongest alternative.** Keep everything withheld. The composition and the Genesis route keep serving these
geometries, at higher latency.

**Evidence.**
- The natural-ops family (`docs/evidence/greg-natural-ops-2026-10-21/`): in-process exact NetworkX beats every GREG
  arm, and GREG's isolated path costs about 263x the latency.

**Tradeoff.** Attaching raises the capability that is actually used. The canonical path's per-call isolation cost is
a separate engineering item.

**Rollback.** Detach. This is the existing signed-detach path.

## D4. Third-party data rights (release blocker)

**Unchanged.**
- M4, fpp3, the NYC/FiveThirtyEight extract and SNDlib have uncleared redistribution terms.
- The release-exclusion check keeps them out of a release (#179).
- Options:
  - obtain permission;
  - acquire the data through a permitted route;
  - replace it.
- **Not an option:** working around the network policy.

## D5. Environment: fresh F8 data

The network policy refuses `data.cityofnewyork.us` and the TLC CDN. Allowing those hosts is an environment setting
the founder controls. Until then, F8's successor evaluation is blocked.
