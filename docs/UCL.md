# UCL: UNIIMENTE Constitutional Language

UCL is a small declarative institutional language. It describes law, not logic. It compiles into policy decisions, relationship-based authorization, workflow constraints, model-checkable invariants, runtime capability grants, and audit schemas. It does not compile into application behavior.

Governing rule: **UCL authorizes. Application code executes. Nothing in UCL can make an effect real by itself.**

## Design rules

1. UCL is declarative. No loops, no functions with side effects, no I/O.
2. Every block is versioned and content-addressed. The constitution's hash anchors the Evidence Ledger.
3. Deny by default. A `permit` clause that does not match is a refusal, not an error.
4. No block may grant more authority than the block that created it holds.
5. No UCL construct can amend the Constitution. Amendment is a human ceremony defined in `amendment-policy.ucl`.

## Lexical structure

UCL uses HCL-compatible syntax so existing tooling can parse it:

```
block_type "optional_label" {
    field          = value
    nested_block {
        field = value
    }
}
```

Primitive types: string, number, boolean, duration (`15 minutes`, `72 hours`, `30 days`), money (`0 USD`), timestamp (RFC 3339), list, map.

## Top-level block types

| Block | Purpose |
|---|---|
| `identity` | A named human, service, agent, model instance, workflow, connector, or Venture Cell |
| `legal_principal` | An accountable legal actor. UNIIMENTE itself is never one |
| `action` | A consequential effect class with permit/require/prohibit clauses |
| `capability_grant` | An explicit, narrow, time-bound, revocable delegation |
| `policy` | A reusable evaluation rule referenced by actions |
| `budget` | Expenditure boundaries and loss limits |
| `evidence_requirement` | What proof must exist before a transition |
| `autonomy_level` | What an actor may do at a given earned level |
| `kill_condition` | A condition that forces pause, reduction, or termination |
| `amendment_rule` | Who may change which UCL, through which ceremony |
| `shutdown_rule` | Ordered shutdown propagation and black-start authority |

## Action block anatomy

```
action send_facility_followup {
    actor           = venture.example.sales_agent
    legal_principal = alfonso_lopez
    objective       = venture.buyer_commitment_proof

    permit when {
        lead.opted_in == true
        template.status == approved
        evidence.confidence >= 0.70
        constitution.aligned == true
    }
    require {
        capability = communication.followup
        spending <= 0 USD
        recipient in authorized_leads
        authorization_age <= 15 minutes
    }
    prohibit {
        contract_commitment
        legal_representation
        pricing_exception
        protected_health_information
    }
    on_exception = escalate(alfonso)
    on_commit    = reauthorize()
    outcome      = record(reply | meeting | rejection | no_response)
}
```
