# Section 16 venture case on the converged Mind — 2026-10-15

Directive section 16: "WealthMachine may consume them for estimation, venture evaluation, incentive analysis,
and bounded optimization ... a venture case can test whether missing causal support prevents a confident
revenue conclusion. Never publish, message others, spend, or activate live accounts solely to demonstrate
integration."

## Provenance: carried, not rebuilt

The PR #143 session built the venture case on its own lineage in `a3c5e2dd`
(`claude/greg-seed-genome-build-y43kmg`). The converged Mind (#179, #180) did not have it. Commit `7ccccae` carries
it unchanged except for one merge conflict in `greg/missions.py`, where the convergence's `stop_check` is kept. No
later #143 commit changed its revenue or causal logic. #143 itself is untouched.

**The rule:** a revenue figure may not outrun its causal support. When a signal carries economics, the venture
mission asks GREG's own cognition two questions, read-only and inside the signed cone: a revenue range (the
estimation family) and causal support (the causal family, identification-gated). The memo's revenue section
renders only those ledger receipts, as one of three outcomes:

| Outcome | When |
|---|---|
| `none` | there is no estimate GREG could certify |
| `conditional` | an estimate is shown, but no causal support is identified, so no revenue conclusion is drawn |
| `stated` | an identified (randomized) effect supports the estimate, still conditional on its assumptions |

## What changed on the converged code (`567245a`)

- **The organ bridge reads through `LedgerReader`.** It gets the canonical ledger's `by_type` and nothing else:
  no journal `record`, no `replay`, no `append`. #143 handed it the whole journal while it only reads receipts.
  - **Limit:** in-process Python is not a sandbox. This removes every write path from the handle; it does not
    stop code that introspects deliberately.
- **The receipt contract is stronger here.** The converged `CognitiveReceipt` binds the proof artifact to the
  output. #143's off-ledger forgery (output edited, artifact not) is therefore refuted as invalid before the
  ledger check runs. The test now covers both cases:
  - the half-edited forgery is invalid;
  - a fully self-consistent forgery, with the artifact edited too, passes validation and is refuted as off-ledger.
- **One wording difference:** the converged causal family names the assumption "random assignment"; #143's
  test expected "randomization". The memo was already right.

## Real organs, one signed body mission (`real-organs-mission.log`, `memo-*.md`)

- **Checkouts:**
  - RailScout `232f724` (`founder/railscout-coded-slice-20260926`), its `examples/project-source-packet` signal;
  - WealthMachineIntelligence `ec82b80`.
  - Both were read only: each organ runs in its own process, which receives no GREG secrets, keys or ledger.
- **Path:** a signed mission enters the body, runs `cognition.solve` twice (revenue, causal), runs both organs
  and delivers one memo. The appraiser re-derives the memo and requires every receipt to be on the ledger.

| Causal design | Mission | Appraisal | Revenue section |
|---|---|---|---|
| observational (treated 9, 11; control 4, 6) | ACTED → ACHIEVED | VERIFIED | **conditional**: causal support UNIDENTIFIED (NON_IDENTIFIABLE), so no revenue conclusion is drawn |
| randomized (same numbers) | ACTED → ACHIEVED | VERIFIED | **stated**: randomized difference in means 5, conditional on random assignment, consistency, no interference, complete observations and independent units |

**What the real organs said:**
- the WealthMachine venture engine said **go** (opportunity score 0.72);
- RailScout's NEEDS_EVIDENCE capped the binding verdict at **needs_more_evidence**;
- GREG's own revenue section stayed conditional.

So the organ that would conclude "go" did not determine what the memo concludes about revenue.

**Read these results with care:**
- **The economics are a stated test input** (brokers 20/60/150; fee per broker-year 1200/2400/4800 USD), not
  market evidence. The memo calls them stated factors, and the estimate an interval enclosure, not a probability.
- **The treated and control numbers are illustrative.** The randomized case shows that the rule admits an
  identified effect. It is not a claim that such a trial was run.
- **Each question runs twice:** once as the mission's action and once as its success-check sensor. The memo
  uses the latest receipt, which is why the log lists each one twice.

## Verification

- `venture-tests.log`: 22 passed with the real organs set (`GREG_TEST_RAILSCOUT`, `GREG_TEST_WMI`). Without them,
  20 pass and the two real-organ tests skip.
- `mutants.log`: 28 of 28 caught. Four target this case:
  - a conclusion drawn from any causal receipt;
  - an abstained estimate still shown;
  - an off-ledger receipt accepted;
  - the writable journal handed to the bridge.
- `full-suite.log`: the whole suite at `852e5cd` gave 3750 passed, 5 failed, 23 skipped. The five are the environmental
  Landlock tests, which fail identically at the pristine base; two of the 23 skips are the real-organ tests.
- `venture_evidence.py` reproduces the two missions. Run it from the repository root as
  `python venture_evidence.py <out> <railscout> <wealthmachine>`.

**Not done:**
- the media case (DALEOBANKS truth-preserving paraphrase);
- Task Fabric and worker leases;
- any live use.

Nothing was sent, spent, published or activated. Authority delta: the organ bridge's ledger access became
narrower. VEPMC: 0.
