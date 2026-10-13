# ADE-1 standing cognition

This package implements the useful core of the ADE-1 blueprint as a bounded
UNIIMENTE organ. It is continuously schedulable, restartable, evidence-bound,
resource-bounded, and capable of multi-organ deliberation. It is not a legal
person, sovereign actor, autonomous treasurer, or self-preserving process.

The invariant is simple:

> Standing cognition may produce a candidate. Only the kernel Consequence Gate
> may turn a bound proposal into an external effect.

## What is implemented

- Content-addressed telemetry envelopes with duplicate suppression and
  contradiction retention.
- Idempotent cognition ticks that rebuild from the Evidence Ledger.
- Deterministic proposer/evaluator deliberation with required Guardian and
  Treasury assessments, explicit vetoes, preserved dissent, and isolated organ
  failure.
- Hard model-call and estimated-cost ceilings with conservation and hibernation.
- An unconditional suspend path and hash-authorized resume path.
- Immutable self-change proposals with tests and rollback declarations, but no
  self-apply function.
- A narrow adapter into the existing `policy.engine.Proposal` and
  `ConsequenceGate.run` path.
- Five-closure checks, an output schema, and adversarial unit tests.

## Detachable parts (`parts.py`, `model_parts.py`)

Every proposer and evaluator sits in a named slot (`proposer:<role>`,
`evaluator:<role>`). Any implementation (rules, a local open-weight model, whatever comes
next) is a registered *part* for a slot.

| Operation | Effect | Authority |
|---|---|---|
| `register(spec, fn)` | Describe a part; hold its code | None granted |
| `change(..., mode="shadow")` | Trial: runs on the same inputs, compared and recorded, never selected | Gate + single-action grant |
| `change(..., mode="active")` | Make it the slot's live part | Gate + single-action grant |
| `change(..., part_id=None)` | Detach an optional slot | Gate + grant; Guardian/Treasury can be replaced, never emptied |
| `rollback_target(slot)` then `change` | Re-bind the previous part | Gate + grant |
| `runtime()` | Rebuild standing cognition from the live parts | Refuses gaps |
| `shadow_run(cycle, ...)` | Record shadow vs. active comparisons | Own resource budget |

Each grant is bound to the slot's current ledger head, so an approval
cannot be replayed after the slot moves. Code is never stored in the
ledger: after a restart, bound parts must be registered again or the board
reports them as unresolved instead of guessing.

`local_draft_part` wraps the local-only `LocalDraftProposer` (below) as a
part, so a newer or larger local open-weight model is a new part rather than
new code: register it, shadow it against the current one, then bind it or roll
back. Endpoint rules and proposal scope come from `local_model.py`: loopback
only, no redirects, fixed internal draft scope, zero confidence. Hosted models
are deliberately not offered as parts (see `docs/OPEN_SOURCE_STACK.md`).

```python
board = PartsBoard(ledger=ledger)
spec, fn = local_draft_part(role="strategist",
                            config=LocalModelConfig(model="qwen3.6:27b"))
part = board.register(spec, fn)
grant = issuer.issue_single_action(
    proposal=board.change_proposal(actor=actor, slot=spec.slot, part_id=part, mode="shadow"),
    policy_version="1.0.0")
board.change(actor=actor, slot=spec.slot, part_id=part, mode="shadow", gate=gate, grant=grant)
```

## Capability Genesis Loop (`genesis.py`)

Canonical morphogenesis (INTENT-0030): capability formation in response to a
*verified* deficit. The loop connects existing mechanisms and adds no authority.

| Stage | Mechanism | Grant needed |
|---|---|---|
| Observe | `DeficitDetector.scan(cycles)` turns repeated component failures, budget refusals and refusal/silence/veto streaks into content-addressed `CapabilityDeficit`s; `observe()` opens or recurs a case | none |
| Propose | `propose()` admits candidates only in resourcefulness-ladder order: a rung may hold a candidate only when every cheaper rung records `candidate`, `searched_none` or `not_applicable`; `new_architecture` only when no cheaper rung holds a candidate | none |
| Trial | `shadow()` binds the candidate as a shadow via the parts board; `record_trials()` aggregates `shadow_result` records (samples, agreement, consequence classes, failure classes) | Gate + grant (shadow) |
| Dossier | `dossier()` renders the Capability Genesis contract fields with a content hash | none |
| Ratify | `ratify()` with an `evolution.capsule.VerifierRecord`: hypothesis-only tiers cannot retain; retain needs the minimum samples, no `doctrinal_refusal` in trial, the reviewed dossier hash, and a whole-body closure that is not FALSELY_CLOSED; it then binds through the board and registers a `CapabilityGenome` | Gate + grant (active) |
| Reuse | `reuse_candidates(slot)` offers retained parts as rung-1 candidates for later deficits | none |
| Stop | `ratify(decision="regress"|"kill")` and `close()` | none |

Case states: `open → trialing → ready_for_ratification → retained | regressed | killed | lapsed`.
Cases rebuild from the ledger; a retained label is applied only when the ledger
holds the authorized binding it names, so forged decision records change nothing.
Design record: `docs/CAPABILITY_GENESIS_LOOP.md`, `docs/intent/INTENT-0031-*.json`,
`docs/collaboration/deliberation-genesis-2026-10-13.json`.

## What is intentionally absent

- Private keys, wallet signing, swaps, transfers, staking, or treasury control.
- Direct social publishing or external API execution.
- A legal principal named UNIIMENTE.
- Attention-driven permission or budget expansion.
- Automatic prompt, policy, model, code, or infrastructure mutation.
- Claims of consciousness, life, sovereign intent, or cryptographic truth.

## Scheduler integration

Temporal, cron, a block trigger, or another durable scheduler can call `tick`.
The scheduler must supply a globally stable `trigger_id`; retrying that ID with
the same inputs returns the recorded cycle, while changing the inputs under the
same ID is retained as a conflict and refused.

```python
cycle = runtime.tick(
    trigger_id="temporal:ade1:2026-07-22T12:00Z",
    signal_ids=signal_ids,
    resources=ResourceGovernor(
        max_model_calls=12,
        max_estimated_cost_usd=0.25,
    ),
    call_costs={
        "proposer:strategist": 0.04,
        "evaluator:guardian": 0.02,
        "evaluator:treasury": 0.01,
    },
)
```

The runtime stops at `cycle.selected_candidate_id`. A separate, explicitly
accountable service may bind that candidate to a real machine passport and
legal principal with `bind_for_gate`, then call `submit_through_gate`. No other
effect path belongs in this package.

## Active inference boundary

This release does not label multi-agent voting as active inference. A future
active-inference organ must declare a generative probabilistic model, latent
states, observations, preferences, posterior approximation, and a testable
free-energy objective. Until then, this implementation is accurately described
as bounded deliberation.

## Local open-source draft model

`egregore.local_model.LocalDraftProposer` supplies an optional local Qwen
proposer through the existing constructor's proposer mapping. It uses Ollama,
llama.cpp, vLLM or LocalAI's loopback /v1 protocol, rejects hosted URLs and
redirects, and makes no paid fallback calls. A legacy OpenAI key is ignored.

The model supplies only draft objective/text; source/evidence references and
fixed internal proposal scope come from the adapter. Confidence is zero pending
the existing required evaluators. Call limits, suspension, idempotent replay and
the Consequence Gate remain owned by the existing runtime.

See [the researched stack and setup](../docs/OPEN_SOURCE_STACK.md).
Use a positive existing resource cost ceiling even for zero-token-fee local
inference: a zero ceiling means hibernation in ResourceGovernor. Hardware and
electricity are real costs; zero provider token fees are not unlimited resources.
No server, scheduler or production activity starts by importing this adapter.
