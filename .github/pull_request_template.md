## Purpose

Describe the problem, affected system boundary, and why this belongs in this repository.

## Founder-intent trace

- Intent IDs or source references:
- Advances:
- Conflicts with:
- Defers or supersedes:

## Reality status

- [ ] Live
- [ ] Sandbox
- [ ] Simulated
- [ ] Proposed

## Alternatives considered

| Alternative | Benefits | Liabilities | Evidence | Rollback / kill criteria |
|---|---|---|---|---|
| Proposed design | | | | |
| Simplest viable | | | | |
| Strongest competitor | | | | |
| Do nothing | | | | |
| Reversible experiment | | | | |

## Five-role debate

### Builder

### Adversary

### Operator

### Beneficiary representative

### Constitutional reviewer

## Upward pass 1 - structural inversion

For each advantage, state how it compounds and when it reverses into a liability. For each disadvantage, remove, bound, observe, reverse, or convert it into a useful constraint or advantage.

## Upward pass 2 - adversarial compounding

Attack the Pass-1 design again. Preserve every prior downside and mark it resolved, accepted with owner and threshold, or converted into a kill condition.

## Dissent and unresolved uncertainty

Do not manufacture consensus. Record the strongest remaining objection and the evidence that would change the decision.

## Authority and safety

- [ ] No new authority source or direct external-effect bypass.
- [ ] Human constitutional authority remains final.
- [ ] Model output is not represented as evidence.
- [ ] Live, sandbox, simulated, and proposed states are not conflated.
- [ ] Migration and rollback are explicit.

## Verification

- Tests run:
- Verifier strength:
- Negative / hostile cases:
- Proof artifacts:

## Decision

- [ ] Retain
- [ ] Regress
- [ ] Kill
- [ ] Defer
- [ ] Experiment

Decision owner and rationale:

---

## Collaboration receipt

Required by `AGENTS.md` / `docs/collaboration/START_HERE.md` for work governed by the shared collaboration protocol. Replace every placeholder and update `base_sha` / `head_sha` after revision changes. This is a self-declaration checked for shape and revision consistency; it is not proof of reading, truth, authority or independent review.

<!-- uniimente:receipt -->
```json
{
  "version": 1,
  "repository": "dababiyoda/uniimente-kernel",
  "base_sha": "<full PR base commit>",
  "head_sha": "<full PR head commit>",
  "protocol_ref": "https://github.com/dababiyoda/uniimente-kernel/blob/<full guide commit>/docs/collaboration/START_HERE.md",
  "intent_refs": ["<scoped intent record>"],
  "read_set": [
    {"path": "AGENTS.md", "revision": "<commit actually read>"},
    {"path": "<same protocol_ref URL>", "revision": "<full guide commit>"}
  ],
  "scope": "<one bounded outcome and exclusions>",
  "classification": "lightweight",
  "deliberation_ref": null,
  "validation": [{"command": "<actual command>", "result": "not_run", "evidence": "<why or result location>"}],
  "limitations": ["<unexecuted checks, negative results or unresolved risks>"],
  "rollback": "<safe rollback preserving evidence>",
  "handoff": {"owner": "<next owner>", "next_action": "<specific action>", "stop_condition": "<boundary>"},
  "review": {"status": "pending", "reference": null}
}
```
<!-- /uniimente:receipt -->
