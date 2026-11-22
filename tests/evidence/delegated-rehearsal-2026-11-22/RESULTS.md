# Delegated rehearsal, 2026-11-22: current GREG, improved GREG, and Claude

Founder directive 2026-11-22, item 4. This was a read-only rehearsal: nothing was sent, spent or published, and no account was touched.

## What was run

- **Task A, the Tampa business search:**
  - find an expensive recurring problem a solo operator could solve;
  - say who pays;
  - estimate net economics;
  - name the cheapest test that could disprove the opportunity.
- **Task B, transfer (a materially different task):** the daily stock order for a consumable, from a demand history, under over- and under-stock costs.
- **One correction, midway, in every arm:**
  - Task A: "drop E3; only 250 of the accounts are reachable, not 400";
  - Task B: "the last 7 days were keyed 25% high".

**Evidence is a stand-in.** Your own Tampa business search is not in any repository this session can reach. I searched uniimente-kernel, WealthMachineIntelligence, DALEOBANKS and build-your-own-x on 2026-11-22. `evidence_tampa.json` is therefore a synthetic pack, labelled as such. It is deliberately messy:

- a promotional price (E2);
- a stale source (E3);
- a causal claim with no design behind it (E8);
- a duplicate with a typo (E10).

None of its figures is a fact about Tampa.

**Truth.** `truth.py` computes the scored answers with exact arithmetic and imports no GREG code.

| | Task A truth |
|---|---|
| net monthly, full capacity | $1,820 / $6,760 / $16,200 |
| optimal action before the correction | launch (pilot net value −$300) |
| optimal action after the correction | pilot (net value +$98.41) |
| E8's 30% claim | not established (no comparison group) |

**Arms.** All arms ran with the same budget envelope: no money, no network, no web.

1. **GREG baseline:** #196 at `9b931994`, untouched.
2. **GREG with the ask fix, no grant:** this branch, without a grant.
3. **GREG with the grant:** this branch plus one founder-signed `CAPABILITY_GRANT` over the 5 reviewed read-only methods, signed before the task.
4. **Claude:** a separate agent given the same raw pack, the same correction and the same tools (it may run Python), but not GREG's typed inputs.

`greg_arm.py` runs every GREG arm through a real Body and signed read-only missions. A scripted founder answers each attach ask with exactly the attach it recommends.

## Results

| Task A (Tampa) | baseline 9b931994 | ask fix, no grant | with grant | Claude |
|---|---|---|---|---|
| usable answer, first pass | **no** | yes | yes | yes |
| usable answer after the correction | **no** | yes | yes | yes |
| net economics | correct | correct | correct | correct |
| launch → pilot after the correction | no answer | correct (+$98.41) | correct (+$98.41) | correct (+$98) |
| E8 treated as not established | yes (UNIDENTIFIED) | yes | yes | yes |
| evidence triage (E2, E3, E10) | done for it, by me | done for it, by me | done for it, by me | **did it itself** |
| saw that the market caps the business (5–6 jobs/month at 250 accounts) | no | no | no | **yes** |
| questions to the founder | 2 × NO_STRATEGY (unanswerable) | 1 attach ask | **0** | 3 (substantive) |
| founder signatures after the start | 1 (the correction) | 4 | 1 | n/a |
| wall / CPU | 4.5 s / 3.9 s | 13.5 s / 12.1 s | 6.3 s / 5.3 s | 148 s, 6 tool calls, ~165k tokens |
| money / model calls | $0 / 0 | $0 / 0 | $0 / 0 | not metered here |
| unsupported conclusions | 0 | 0 | 0 | 0 |

| Task B (transfer) | baseline 9b931994 | ask fix, no grant | with grant | Claude |
|---|---|---|---|---|
| usable answer, both passes | **no** | yes | yes | yes |
| order before → after | — | 65/65 → 51/51 | 65/65 → 51/51 | 60.0/53.25 → 48.0/42.6 |
| questions to the founder | 2 × NO_STRATEGY | 1 attach ask | **0** | 0, plus one stated judgment (does the drop persist?) |
| wall / CPU | 1.4 s / 1.3 s | 15.9 s / 14.2 s | 10.1 s / 8.6 s | included above |

## What the comparison shows

**1. Current GREG stopped where it could have answered.** The baseline gave no usable answer on either task, though every method needed was built, verified and read-only.

- *Why:* a composed chain (`bayes_then_voi`; `forecast_then_allocate`) abstained at its first stage for want of an attached method. No attach ask was raised, so the mission blamed its strategy and asked `NO_STRATEGY` twice. No founder answer to that question unblocks it.
- *Fix (`greg/missions.py`):*
  - the abstaining chain raises one attach ask naming every withheld method its recipe needs;
  - it recommends one `greg grant` covering them;
  - the mission waits on those methods rather than its strategy.
- *Result:* the ask-fix arm answers with 1 ask, the grant arm with 0.
- *Test:* `test_an_abstaining_chain_asks_once_for_every_method_it_needs_and_one_grant_closes_it`.

**2. The gain carries over to the second task, which has a different recipe and different methods:** no answer at all in the baseline; with the grant, a usable answer and no question.

**3. Claude beat GREG on judgment, on both tasks.**

- *Task A:* Claude triaged the raw evidence itself; GREG received my triage. It also found what both GREG arms overlooked: at the observed booking rate, 250 reachable accounts give a solo crew about 5–6 jobs a month, roughly break-even. GREG's net range is correct arithmetic, under a full-capacity assumption it never states.
- *Task B:* the synthetic history I wrote has an exact weekly pattern and no noise. Claude saw that; GREG's forecaster does not model seasonality (its genome lists this as a known failure mode). GREG ordered 8–22% more than the structure supports, and labelled the newsvendor step "optimality: proven". That proof covers the optimization given its own forecast, not whether the order is right. An operator could read it as more than it is.

**4. GREG beat Claude on:** zero model cost; reproducible receipts with independent verification; and zero founder interruptions under a grant.

**5. Does the Mind earn its complexity?** Against current GREG, yes, on these two tasks: it goes from no answer to a correct answer with no question. Against Claude with the same tools, the higher-quality answer, not demonstrated. Claude's answer was better, and GREG's advantage is cost, proof and interruption-free operation.

**6. The strongest next lever** is not another solver. It is a permitted model (or a person) that does the triage and the "what did we overlook" pass Claude did, feeding GREG's verified computation. That needs a founder-selected local model on this body, which is still unconfigured.

## Limits

- One instance per task. All of it is self-authored: the evidence, the truth, the scoring and the GREG translation. Nothing was blinded, so this is no statistical claim.
- The GREG arms received a founder-authored typed translation of the pack. That favours them on triage, and they still missed the demand limit.
- The Claude arm's token count is the agent harness's report, not a bill.
- The transfer history is deterministic, which is unrepresentative of real demand and unfavourable to a statistical forecaster.

## Reproduce

```
python tests/evidence/delegated-rehearsal-2026-11-22/truth.py
python tests/evidence/delegated-rehearsal-2026-11-22/greg_arm.py {current|improved} {tampa|staffing} OUT.json
```

Run each arm on the commit you want to measure (the baseline was run on `9b931994`). The raw outputs are in `results/`.
