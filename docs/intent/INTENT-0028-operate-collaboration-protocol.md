# Intent Record INTENT-0028

Recorded under `docs/FOUNDER_INTENT_LEDGER.md`. Machine-readable form:
`docs/collaboration/intent-records-kimi-0027-0028.json` (validator exit 0).

| Field | Value |
|---|---|
| `intent_id` | `INTENT-0028` |
| `title` | Install and operate the recursive founder-intent collaboration protocol |
| `statement` | "Use your /install-recursive-founder-intent-collabora' to Organize around what Claude and ChatGPT have already done." — the founder directs Kimi to adopt the installed protocol skill as its operating discipline for UNIIMENTE work. |
| `source_refs` | Founder directive 2026-08-22 (goal-mode session); user skill `install-recursive-founder-intent-collaboration-protocol`; kernel `docs/RECURSIVE_COLLABORATION_PROTOCOL.md` |
| `owner` | alfonso_lopez |
| `state` | **active** |
| `authority_level` | active_requirement (pendingADR001) |
| `consequence_class` | material (pendingADR001) |
| `intended_outcome` | Every material Kimi decision on UNIIMENTE runs the full protocol: intent record, classification gate, five-role deliberation, exactly two strengthening passes, dissent, evidence tiers, one decision state, durable record, cross-model handoff (pendingADR001) |
| `binding_scope` | All Kimi sessions operating on UNIIMENTE repositories |
| `constitutional_constraints` | Core invariant: models reason, agents propose, authorized humans decide; no model manufactures or expands its own authority; constitutional decisions end at NEEDS_FOUNDER_DECISION |
| `rationale` | The founder named the skill explicitly; the skill mirrors the kernel's own protocol documents, so adopting it converges vocabulary rather than creating a parallel canon (pendingADR001) |
| `success_evidence` | Material Kimi decisions carry deliberation records that pass `validate_deliberation.py`; intent records pass `validate_intent_ledger.py`; no direct writes to default branches |
| `failure_evidence` | A material Kimi change with no deliberation record; a constitutional decision executed while pending; a trail existing only outside the repositories |
| `dependencies` | — |
| `conflicts` | None recorded |
| `next_review_trigger` | First material Kimi decision after this record, or founder amendment |
| `supersedes` | — |
| `superseded_by` | — |
| `implementation_refs` | `docs/FOUNDER_INTENT_LEDGER.md`; `docs/RECURSIVE_COLLABORATION_PROTOCOL.md`; `docs/REPOSITORY_RATIONALIZATION_PLAN.md`; `.github/pull_request_template.md` |
| `unresolved_questions` | PR #54's `docs/intent/ledger.json` (INTENT-0001..0021) is unmerged at PR head; whether these records should also be appended there awaits ADR-001/D-001 (pendingADR001) |

## Notes

The protocol applies to itself: if operating it measurably degrades decision
quality, cycle time, or founder-intent fidelity, that is recorded as negative
evidence and the protocol is revised or regressed — not argued past.
