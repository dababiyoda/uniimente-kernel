# MC-0004 — Intake counted by independent source

Status: **built and on GREG's wake path.** Every founder-signed GOAL on a body uses it (`greg/goal_gravity.py`, `IntakeAccumulation`). It decides when a goal wakes. It decides nothing else.
Reality tier: a cloud container, per-test keys, no founder device, VEPMC 0. Real Body, real ledger and Gate, in-process.
Founder lineage: directive section 42 ("ENGAGEMENT IS NOT TRUTH."), gap-map unit S42-B. The founder's minimum test for this extension: "relevant combined signals awaken the right dormant goal; duplicated and irrelevant signals do not. Preparation stays within existing authority."
Evidence: `docs/evidence/greg-goal-intake/2026-11-11/`.

## Residual CapabilityDeficit

Reproduced on the integration head `8d205324` with a real Body and a signed GOAL:

- Three weak reports about a goal's subject, from three independent sources, never woke the goal. Each was scored alone and each was under the threshold.
- One sentence repeated by four sources woke the goal four times and pulled its mission four times.

The data plane already counted those four copies as one flagged claim (`dataplane.community_evidence`). That count was a report. No wake read it.

## Sources

Cited from memory. Nothing was fetched in this session and no code was copied.

1. **Noisy-OR combination of independent causes** (Pearl, *Probabilistic Reasoning in Intelligent Systems*, 1988; the leak term is usually credited to Henrion, 1989).
2. **Resemblance of documents by shingle sets** (Broder, "On the resemblance and containment of documents", 1997), and MinHash sketches that estimate it.

Reused from this repository, not transplanted:

- `greg/dataplane.py`: one unit of weight per source per claim, the normalised clustering key, and the campaign cap. Now public as `claim_key` and `claim_support`, and called, not copied.
- `greg/cognition/evidence.py`: the restatement refuter's negation and direction classes, to tell a denial from a repeat.
- `GoalSpec.intersection_window_seconds`: the founder-signed window in which weak signals may combine.

## Source behaviour

- Noisy-OR: an effect has several possible causes. Each cause that is present can produce it on its own with some probability. The causes act independently. The effect's probability is one minus the product of the causes' failure probabilities. A cause counts once, however strongly it is present. Adding an independent cause never lowers the result.
- Resemblance: two texts are near-duplicates when the sets of their shingles overlap enough: the size of the intersection over the size of the union.

## Mutation

- **A cause is a source cluster, not an item.** All reports that state one claim on one side form one cluster. It counts one unit per source, and never more than the data plane's cap of two.
- **The product became a sum.** Units add in the goal's own signed wake weights and are compared with the goal's signed `wake_threshold`. No probability is produced.
- **A wake spends what had arrived.** The goal's own wake record on the ledger marks every earlier report as used. A claim the goal already woke on adds nothing when it is repeated.
- **A claim has two sides.** A report that denies a claim counts on the other side. The heavier unspent side counts. The sides never add to each other.
- **One-word shingles, exact Jaccard, threshold 0.8.** The threshold was written down before the paraphrase test ran, and was not changed after.
- **Bounded and derived.** Per goal, at most 256 relevant reports inside the signed window. Nothing is stored. The count is read from the ledger, so a restart changes no wake.

## Preserved invariant

1. One cause counts once: a repeated claim adds nothing. Test: `test_one_claim_repeated_by_four_sources_wakes_the_goal_once`.
2. Only independent causes combine: one source repeating itself, or a campaign behind one claim, does not add up. Tests: `test_one_source_repeating_its_claim_in_other_punctuation_adds_nothing`, `test_a_campaign_cannot_push_one_weak_claim_over_a_threshold_it_does_not_reach`.
3. One more independent agreeing cause never lowers the weight. Test: `test_two_sources_that_disagree_do_not_add_up_as_agreement` (the third source on the first side wakes the goal).

## New interaction

Three things that existed apart now act together:

- the data plane's per-source weighting decides a wake, where before it only filled a report;
- the goal's signed window bounds untrusted intake, where before only the egregore intersection detector read it, over beliefs;
- the goal's wake record is read back as "this evidence was used".

Together they do what none did alone: independent weak reports wake the right goal once, and copies do not wake it again. An unchanged composition of the three would not do this: the data plane has no notion of a goal or a wake, and the router has no notion of a source.

It never becomes a belief. The count is the score of one new report in the existing router. It sets when the goal's signed missions look. What is true is still decided by the mission's own sensor read through the Gate.

## Expected benefit, as measured

One scenario set of 16 scenarios and 17 wanted wakes, each on its own real Body (`tests/unit/test_greg_goal_intake_counts.py`). The scenarios are the author's, not a sample of real intake.

| Rule | Right wakes | False alerts | Missed |
|---|---|---|---|
| Per item (integration head) | 10 | 10 | 7 |
| Accumulated by independent source | 16 | 3 | 1 |

## New failure

Three scenarios are worse than under the per-item rule. All three are counted in the table above.

- Two weak reports that disagree by an opposite word ("is broken", "is fine") now add up. Only a negation or a reversed direction is seen as a denial.
- Passing mentions that report nothing now add up. The count reads which words a report uses, not what it means.
- A sentence the goal already woke on is not news inside the window, even when the fault it names has come back. The mission then finds the fault at its own next look, not sooner.

Other limits:

- A claim retold in other words by another source still counts as new. It did before, too.
- Beyond 256 relevant reports a goal forgets the oldest, and a forgotten claim counts again.
- Counting a full window of 256 distinct claims took about 85 ms here. It is done once per goal per turn, not once per report.

## Simpler comparator

- The per-item rule on the integration head: every item scored alone. It is the baseline in the table.
- Ablation: accumulate, but count every item instead of independent sources. It is worse on repetition than no accumulation at all: every copy still wakes the goal, and one source or one campaign can add itself up over a threshold (`test_ablation_counting_items_brings_the_repetition_false_alerts_back`).

## Decisive experiment

```
python -m pytest -q tests/unit/test_greg_goal_intake_accumulation.py tests/unit/test_greg_goal_intake_counts.py
python scripts/ci/check_goal_intake_mutants.py
```

The first file fails on the integration head: the two reproductions by behaviour, the rest because the count does not exist there. The mutation gate removes each safeguard in turn and requires a named test to fail.

## Disposition

**RETAIN** on the wake path, as timing only.

Review when: intake from a founder-used body exists; or a wake caused by passing mentions or by an opposite-word disagreement is observed there.

Next step, buildable now: let an attributed change in the goal's own mission observations clear what the goal has "already woken on". That would wake the goal when the same sentence arrives after the fault has come back. It needs a decision on the trade: one more look after a real change, against one more look on a late copy.

## Not transplanted, and why

- **The probability product.** It needs a reliability for each source. Nobody has measured one, and an invented one would be an unsupported probability estimate. Its result also cannot be compared with a signed threshold that is a sum of weights.
- **The leak term.** The mission's own cadence already plays that part: it looks without any report.
- **Shingles of two or more words.** Intake items are single short sentences. One inserted word removes one two-word shingle and adds two ("c.txt looks broken" against "c.txt looks really broken" is 0.4 on two-word shingles and 0.8 on single words).
- **MinHash sketches and banding.** They estimate resemblance across large collections. Here a goal compares at most 256 reports, so the exact value is cheap, repeatable and has no hash seed.
- **Stemming and synonyms.** Not built. This is why a retelling in other words counts as a new claim.
