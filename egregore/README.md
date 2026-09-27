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
`evaluator:<role>`). Any implementation (rules, a local open-weight model, a
hosted model, whatever comes next) is a registered *part* for a slot.

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

`openai_compatible_proposer` turns any OpenAI-compatible chat endpoint
(Ollama, llama.cpp, vLLM, LM Studio, Groq, OpenRouter, Together, Gemini's
compatibility endpoint) into a proposer part. The model drafts objective,
outcome, payload and cited signals; action class, capability, target and
consequence class are fixed by the code that builds the part. Model
confidence is capped (default 0.5); the raw value is kept in the payload.

```python
board = PartsBoard(ledger=ledger)
spec, fn = openai_compatible_proposer(
    role="strategist", base_url="http://localhost:11434/v1", model="qwen3.6",
    envelope=Envelope(action_class="community_update",
                      requested_capability="social.publish.draft",
                      target="discord://community/main",
                      consequence_class="external_contact"),
    open_weights=True,
)
part = board.register(spec, fn)
grant = issuer.issue_single_action(
    proposal=board.change_proposal(actor=actor, slot=spec.slot, part_id=part, mode="shadow"),
    policy_version="1.0.0")
board.change(actor=actor, slot=spec.slot, part_id=part, mode="shadow", gate=gate, grant=grant)
```

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
