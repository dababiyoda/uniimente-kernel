# Intent Record INTENT-0001

Recorded under `docs/FOUNDER_INTENT_LEDGER.md`. This is the first `prohibited`
record. It was **not invented to populate the state** — it documents a proposal
that was actually considered and refused, and the refusal is enforced in code.

| Field | Value |
|---|---|
| `intent_id` | `INTENT-0001` |
| `statement` | UNIIMENTE may act as a legal principal. |
| `source_refs` | `authority/legal-principals.yaml`; `compiler/ucl_compiler.py` invariant `never_uniimente_principal`; `docs/UCL.md` ("An accountable legal actor. UNIIMENTE itself is never one") |
| `owner` | Alfonso Lopez |
| `state` | **prohibited** |
| `binding_scope` | Every organ, Venture Cell, adapter, and future body. Applies to all consequential effects without exception. |
| `constitutional_constraints` | UNIIMENTE has no independent legal personhood, no survival objective, and no sovereignty. Every consequential effect attaches to exactly one accountable human or registered entity. |
| `success_evidence` | `authority/legal-principals.yaml` records `UNIIMENTE` as `type: not_a_legal_actor`, `status: prohibited`. The UCL compiler refuses to compile a constitution that fails to prohibit it, and records the refusal as invariant `never_uniimente_principal`. Policy evaluation rejects any proposal whose `legal_principal` is absent from the compiled registry (`policy/engine.py`). |
| `failure_evidence` | Any record, proposal, grant, receipt, or manifest naming UNIIMENTE as `legal_principal`. Any compiled constitution lacking the invariant. Any external effect attached to no accountable entity. |
| `dependencies` | The legal-principal registry and the UCL compiler must both remain in the required CI set. |
| `conflicts` | None recorded. |
| `next_review_trigger` | Any proposal to grant UNIIMENTE contractual capacity, or any jurisdiction recognising non-human legal personhood in a form a founder might wish to use. |
| `supersedes` | — |
| `superseded_by` | — |
| `implementation_refs` | `authority/legal-principals.yaml`; `compiler/ucl_compiler.py`; `policy/engine.py`; `identity/machine_passport.py` |

## Why this is a legitimate prohibited record

The founder's rule is that a `prohibited` record may exist only where an actual
proposal or earlier intention was **rejected** — not to make the ledger look
complete.

This qualifies. The registry does not merely omit UNIIMENTE; it names it and
classifies it as `prohibited`, with the note *"The institution may never be
named as legal principal. It has no independent legal personhood and no survival
objective."* A thing is only refused explicitly if it was first considered.

The rejection is additionally **structural**: the compiler will not compile a
constitution that omits the prohibition. That is a refusal the system cannot
forget.

## Related, and deliberately NOT recorded as prohibited

`IVIO_NEMT_LLC` is recorded as `status: proving_ground`, `jurisdiction:
to_be_confirmed_by_founder`. That is **unconfirmed**, not prohibited. It remains
a valid registered principal for internal and simulated use, and may not create
contractual effects until its registered identity and jurisdiction are confirmed.
Recording it as prohibited would misstate its status.
