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
    actor           = venture.ivio.sales_agent
    legal_principal = IVIO_NEMT_LLC
    objective       = ivio.buyer_commitment_proof

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

Semantics:

- `permit when`: every expression must evaluate true against current evidence state. Evaluation happens at proposal time and again at commit time.
- `require`: hard prerequisites. Missing capability, expired freshness, or budget overflow is a refusal.
- `prohibit`: reserved effect classes. Naming one anywhere in a payload is a refusal and an incident.
- `on_commit = reauthorize()`: mandatory commit-time revalidation. The grant must still be valid, fresh, applicable, unrevoked, within budget, bound to the same intended effect, and attached to the same legal principal at the moment the effect becomes real.
- `outcome`: the recording obligation. An executed action without its outcome record is an incomplete action and blocks autonomy promotion.

## Compilation targets

1. **Policy decisions**: OPA-style allow/deny with reasons.
2. **Relationship authorization**: Zanzibar/OpenFGA-style tuples (grantee, relation, object, context).
3. **Workflow constraints**: states an executor may enter, with evidence gates.
4. **Invariants**: model-checkable properties for the governance laboratory (`/tests`).
5. **Runtime grants**: capability tokens bound to identity, expiry, budget, and effect hash.
6. **Audit schemas**: the record shapes in `/contracts`.

## Non-goals

UCL is not a general programming language, not a smart-contract language, not a prompt format, and not a configuration dump. If a construct cannot change an authorization decision, it does not belong in UCL.
