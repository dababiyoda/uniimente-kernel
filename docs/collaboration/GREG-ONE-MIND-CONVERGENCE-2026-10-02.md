# One GREG: Mind (#143 + #145) converged with Hands (#148) — 2026-10-02

Founder instruction (verbatim): "Converge the strongest #143/#145 Mind with #148 Hands into one canonical GREG,
then continue automatically through the still-unfinished P4–P13 requirements instead of treating the Seed as the
completed Mind." Authority delta: none.

## What is canonical now (branch `claude/greg-one-mind-converged`)

| Concern | Canonical owner | Lineage kept as |
|---|---|---|
| Routed cognition `cognition.solve` | cortex 0.2.1 bridge (`greg/cognition/cortex.py` -> `cortex/routing.py`): Z3 + CP-SAT, extraction, declared-harm escalation, source re-check | #143 (incl. #140, #141) |
| Static seed router | `cognition.seed.solve` in `greg/cognition/seed_path.py` (was `greg/cognition.py`) — governed alternative, benchmark twin, fallback; `cognition.status` / `cognition.settle` unchanged | #142 |
| Receipt envelope | one `CognitiveReceipt`: #143 `outcome` taxonomy + #145 0.2 envelope (reason code, outcome state, model provenance, formalization coverage, contribution attribution) and artifact/output coherence; `cortex_receipt` bound to `cognition.cortex*` methods only | #143 + #145 |
| Activation of P5+ families | #145 rule: installed + verified is not attached; founder `CAPABILITY_ATTACH` activates (`catalog.initial_state`). #143 tests now attach explicitly | #145 |
| Settlement | #145 per-claim settlement; legacy receipts accepted without additive fields, unknown fields refused | #143 + #145 |
| #145 modules | `budget`, `evidence`, `seed_evaluation`, `semantic`, `presentation`, seed gates/boundary tests, multi-claim settlement test | #145 |
| Hands | `worker.*`, `browser.*`, `daleobanks.*` unchanged | #148 |
| Developmental path | one P0–P13 backcast in `greg/path.json` `subordinate_workstreams.polyintelligence_cortex`; #145's parallel `cognition_workstream` copy is not duplicated (kept in git) | #143 + #145 |
| Pins | one `ortools==9.15.6755`, `z3-solver==5.1.0.0` (cortex), `protobuf==6.33.5` (#145 security pin) | |

## Evidence

- Converged suite: 1,303 passed; remaining failures are the 3 + 1 base-stack environment failures that reproduce
  identically on `9389103` in this container (Landlock/DSL/packaging/MCP `librt.so.1`), green in #147 CI.
- Seed Genome freeze-v5 (2026-10-07, the committed tree; v4 was written before this commit's final
  `greg/models.py` merge and protobuf pin, so CI refused it; v1–v4 kept): INCONCLUSIVE, timing-independent
  gain 0.0, 100/100 matched, 0 hard failures (`docs/evidence/greg-one-mind/2026-10-07/`). Earlier v4 run: INCONCLUSIVE, timing-independent gain 0.0, 100/100 quality
  matched, 0 hard failures — the move preserved the seed path's behavior. `docs/evidence/greg-one-mind/2026-10-02/`.
- Seed-path mutation check: 6 mutants, 0 survived.

## Defects found and fixed by the convergence

- `cognition.solve` id collision (#142 block silently replaced #143's router) -> rename to `cognition.seed.solve`.
- `greg cognition mission` raised `UnboundLocalError` (a function-local `datetime` import) -> removed.
- Seed status sensor still matched the old capability id -> fixed.
- #145's native-proof binding rejected #143 cortex receipts -> explicit `cortex_receipt` binding.
- Owned-source inventory listed the moved module -> regenerated.

## Not done here

P4–P13 remain the parent objective; see the PR for what each increment proves and what stays open.
