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
