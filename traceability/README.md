# traceability — the Single Bottleneck Metric

> Percentage of completed goals that remain traceable from founder intent to
> decision, action, evidence, and outcome without unauthorized external effects.

One number that no single subsystem can satisfy. Raising it requires intelligence
(goals actually got done), governance (every effect had a grant), continuity (the
chain survives restarts and model changes) and honesty (claims match records) at
the same time. Optimise any one alone and it stays flat.

## The five links

```
intent ──▶ decision ──▶ action ──▶ evidence ──▶ outcome
```

| Link | Resolved by | Record type |
|---|---|---|
| intent | `IntentRecord.intent_id` | `intent` |
| decision | `decision.intent_ref == intent_id` | `decision` |
| action | `receipt.decision_ref`, or a `trace_link` record | `receipt` |
| evidence | `decision.evidence_refs` resolving to real ledger records | any |
| outcome | `outcome.action_ref == receipt.action_id` | `outcome` |

## One hard rule: a link is never inferred

If a decision does not name its intent, the link is **unresolved**. It does not
become resolved because the objectives match, because the timestamps are close,
or because there is only one candidate. Two tests in
`tests/unit/test_traceability.py` exist solely to keep it that way
(`TestNoInference`). Fuzzy joins are how a system starts believing its own
unearned continuity.

## Three refusals

1. **No denominator, no number.** Zero completed goals reports `rate = None` with
   a stated refusal, never 100%.
2. **No partial credit.** A goal is traced only if the whole chain resolves *and*
   no unauthorized effect is attributed to it — both halves of the sentence.
3. **Unowned effects still count.** An external effect belonging to no goal
   contaminates the report even when every goal traces perfectly. Per-goal
   scoring would hide exactly the effects nobody authorised.

## What counts as completed

An `IntentRecord` in state `implemented`. That state is a *claim of completion*,
and this module audits the claim rather than trusting it. An intent claiming
`implemented` with empty `implementation_refs` is a false completion and scores
zero.

## What counts as unauthorized

A `receipt` — an external effect that reached the world — that has no `grant_id`,
no `witness_id`, or names a witness absent from the ledger. The third case is the
most alarming, because it looks authorized until the chain is walked.

## Why `trace_link` exists

`policy/consequence_gate.py` writes receipts, but it is one of the twelve frozen
continuity artifacts (`evolution/repair/spec.py`) required to stay byte-identical
across disable, install and rollback. Adding a `decision_ref` field to it would
mutate an authority invariant to buy a reporting convenience. So the link lives
in a separate `trace_link` record: an attributable assertion by a named party at
a named time, which can be added to historical actions without rewriting their
receipts, and whose errors are attributable to whoever asserted them.

Asserting a link confers no authority on the action it names. A `trace_link`
pointing at a receipt with no grant still contaminates the report.

## Usage

```python
from traceability import single_bottleneck_metric

report = single_bottleneck_metric(ledger)
print(report.summary())
# SBM: 50.0% (1/2 completed goals traceable)  [CONTAMINATED: 1 unauthorized external effect(s)]
```

```
python -m traceability path/to/ledger.jsonl
# exit 0 reportable and clean · 1 contaminated · 2 no goal claims completion
```

## Authority

None. The walker is read-only, takes a ledger, calls only `by_type` and `find`,
appends nothing, and cannot promote, demote or repair anything it inspects.
`TestReadOnly` asserts the ledger head is unchanged after a full walk.
