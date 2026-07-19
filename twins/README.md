# twins

Phase 5 — Institutional Twins + the Counterfactual Tribunal: change rehearsed, never guessed.

## Organs

- `twin.py` — `InstitutionalTwin`: a hermetic fork of the compiled
  constitution plus one declarative `Amendment` (e.g. evidence-floor
  override). Deep-copied by construction; evaluates proposals exactly as
  main would under the amendment; cannot touch main state, the ledger,
  or the outside world. Twins think; they do not act.
- `tribunal.py` — `CounterfactualTribunal`: hears main vs twin over one
  frozen, quality-labeled corpus. Profiles harm events (bad admitted —
  gravest), weak admissions, good refusals. Verdicts: `twin_superior`
  (dominance, no axis worse, one strictly better), `main_superior`,
  `inconclusive` (tradeoff). Recommends; never applies — application is
  the evolution cycle's job behind its own verifiers.

## Recorded proof

`tests/unit/test_twins.py` (7 tests): hermetic isolation (main floors
untouched after twin evaluation), floor-raise twin named superior over
the real policy engine, tradeoff → inconclusive, regression →
main_superior, harm increase bars superiority, empty corpus refused,
verdict ledgered.

## Buildability standard (14 conditions)

- **Existing mechanism**: shadow evaluation / champion-challenger — standard ML governance, no novel science.
- **Defined interface**: `InstitutionalTwin.evaluate(proposal)`; `CounterfactualTribunal.hear(corpus, main, twin) -> Verdict`.
- **Bounded authority**: twins hold zero authority (no ledger, no gate, no executor); the tribunal recommends and cannot apply.
- **Available dependencies**: Python 3 stdlib + `policy.engine`.
- **Security model**: deep-copy isolation; verdict geometry bars any verdict that increases harm.
- **Failure modes**: `ValueError` on empty corpus; non-dominance is inconclusive, never forced.
- **Acceptance tests**: `tests/unit/test_twins.py` (7 tests).
- **Recovery path**: inconclusive → refine the amendment or gather more corpus; nothing was applied, so nothing must be undone.
- **Resource ceiling**: corpus size × 2 evaluations per hearing.
- **Operating cost**: two in-memory evaluation passes; zero external calls.
- **Legal operator**: Alfonso (verdicts are advisory evidence for his ratification).
- **Handoff state**: the ledgered verdict record (profiles, rationale, corpus size) IS the handoff.
- **Replaceable**: evaluators and corpus injected; verdict geometry is data-independent.

## Orthogonal closures

Verified by `closure/kernel_registry.py` → module `twins`.
