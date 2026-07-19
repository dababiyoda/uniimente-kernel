# HANDOFF WP-02: UCL Constitutional Compiler

Status: COMPLETE. Branch `build/ucl-compiler` (stacked on `build/consequence-gate`, PR #21).
Repo: dababiyoda/uniimente-kernel. Date: 2026-07-20.

## What exists now

The five real `.ucl` files in `constitution/` are no longer documentation. They
compile into the gate's `policy_fn`. Every gate EVALUATE stage now runs the
constitution itself: shutdown ladder, permanent prohibitions, hard-refusal
participant rights, consequence-class defaults.

```
constitution/*.ucl  -->  lexer  -->  parser (AST)  -->  Constitution model
                                                          |
                                            compile_policy_fn
                                                          |
                                    Gate(..., policy_fn=compiled)   [WP-01 pipeline]
```

## Files added (this work package)

- `kernel/ucl/__init__.py` — public API: parse, parse_file, Constitution, compile_policy_fn, UCLError
- `kernel/ucl/lexer.py` — hand-rolled tokenizer; comments, strings, numbers, bools, null; UCLError with file:line:col
- `kernel/ucl/ast.py` — frozen Block tree with attr/child/children_of/walk helpers
- `kernel/ucl/parser.py` — recursive-descent parser; fails closed on any syntax ambiguity; Document with find/find_all
- `kernel/ucl/model.py` — semantic Constitution over exactly five documents; validates all constitutional content; fails closed, never invents content
- `kernel/ucl/version.py` — content-addressed versions: `ucl-8874e52869b5bb0e` (files), `policy-5c79eb3ae32cfe63` (model)
- `kernel/ucl/compiler.py` — `compile_policy_fn(model, *, policy_version, constitution_version)`
- `tests/ucl/` — 7 files: fixtures + lexer + parser + model + compiler + gate-integration suites

## Compiled policy_fn semantics (evaluation order)

1. `ucl:shutdown_state` — safety ladder. normal: no constraint. manual_approval_only: force REQUIRE_HUMAN. All other states: DENY external effects (C2+); C0/C1 internal allowed.
2. `ucl:permanent_prohibitions` — 14 non-delegable matters. Exact match on `payload["reserved_matter"]`; normalized keyword match on action_type/objective. DENY. `constitutional_amendment` always DENYs for any actor.
3. `ucl:participant_rights` — hard-refusal rights (rank 1). `participant_harm` truthy DENYs (safety). `requires_unlawful_conduct` truthy DENYs (lawful_treatment).
4. `ucl:consequence_default` — doctrine.humans_authorize: C0/C1 PERMIT, C2/C3/C4 REQUIRE_HUMAN, C5 DENY. The compiler never emits PERMIT for C2 or above.

Every step appends to the decision trace. DENY short-circuits. No wall-time,
no randomness: same inputs produce a byte-identical trace (Hard Rule 5).

## Verification evidence

- 143 tests green (36 WP-01 + 107 WP-02), independently re-run by the orchestrator, rc=0.
- Determinism: two independent compiles produce identical policy_version; two full gate runs produce byte-identical decision traces.
- Gate integration: golden C2 intent closes an episode end to end; a constitutional_amendment intent with a genuine founder approval is DENIED at EVALUATE before APPROVE is reached, and replaying the approval still refuses; a replayed happy-path approval is refused at APPROVE (nonce consumed); quarantined state denies before approval.
- Git blob SHA parity: 0 mismatches across all pushed files (transcription risk eliminated).

## Key decisions (ADRs)

1. **C3/C4 map to REQUIRE_HUMAN, not DENY.** The WP-01 default evaluator denied C3+. The compiled constitution follows `doctrine.humans_authorize` and requires a human instead. This is the constitution's own choice, stricter in authority terms, recorded in the trace.
2. **Keyword matching is normalized substring.** The constitution names effects, not syntax, so "Shutdown Override" hits "shutdown_override". Reserved-matter payload keys are exact match only.
3. **`current_state` is excluded from the canonical model dump.** Runtime posture never changes the content-addressed policy version.
4. **No parser library.** Hand-rolled lexer + parser: zero new dependencies, full control of error positions, fail-closed on every ambiguity.

## Known limitations (do not silently fix)

- Participant-harm and unlawful-conduct flags are proposer assertions inside `payload`. The constitution DENYs when they are set, but nothing yet independently detects harm. That is a later organ (evidence/witness layer), not a compiler gap.
- Keyword prohibition matching can false-positive on benign text containing a prohibited phrase. Fail-closed is the intended bias; a human can still route around it by rewriting the objective, which is itself logged on the spine.
- The constitution's `status` is "unratified" and `ratified_by` is null. The compiler enforces it anyway. Ratification is a founder act, not a code act.

## How to resume (next agent)

1. Read `HANDOFF.md` (WP-01) then this file.
2. `git fetch && git checkout build/ucl-compiler`; `pip install pytest pydantic cryptography`; `pytest -q` from the slice root (needs `constitution/` beside `kernel/`).
3. **WP-03 is next: real adapter loop.** Wrap one DALEOBANKS read-only capability in `kernel/adapters/http_research.py` with a declared egress allowlist. Run ONE full loop against reality: Evidence to Policy to Authority to CommitWitness to Execution to Receipt to Reconciliation to Outcome to DecisionEpisode. Capture the Proof Capsule.
4. Then WP-04: Postgres spine backend behind the Spine interface; rebuild-from-spine drill.
5. Do not open later organs (Loom, Rabbit Hole, Foundry, IaaS, Swarm, Treasury, Federation) before WP-03/WP-04 close. The build order is locked.
