# Intent Record INTENT-0027

Recorded under `docs/FOUNDER_INTENT_LEDGER.md`. Machine-readable form:
`docs/collaboration/intent-records-kimi-0027-0028.json` (validator exit 0).
IDs 0022–0026 are deliberately skipped: they were allocated in issue #80's
lost local-only artifact; skipping preserves referential integrity with that
record.

| Field | Value |
|---|---|
| `intent_id` | `INTENT-0027` |
| `title` | Organize around what Claude and ChatGPT have already done |
| `statement` | "Organize around what Claude and ChatGPT have already done. Find the canonical owner, avoid duplication, strengthen with evidence and leave a clean handoff and trail of what u did. Explain your goals and what u are currently working on so all is transparent and collaborative." |
| `source_refs` | Founder directive 2026-08-22 (goal-mode session); kernel issue #80; `docs/REPOSITORY_RATIONALIZATION_PLAN.md` |
| `owner` | alfonso_lopez |
| `state` | **active** |
| `authority_level` | active_requirement (pendingADR001) |
| `consequence_class` | material (pendingADR001) |
| `intended_outcome` | Any qualified agent can identify canonical owners, duplications, and open founder decisions from in-repository records in under 30 minutes; no cross-model work is overwritten for preference; every Kimi action leaves a durable in-repo trail (pendingADR001) |
| `binding_scope` | uniimente-kernel; DALEOBANKS; WealthMachineIntelligence |
| `constitutional_constraints` | No execution of convergence while founder ruling pending; preserve all contributor lineages; draft-PR norm for material changes |
| `rationale` | The directive is an explicit operating instruction for this session, addressed to Kimi, with material structural scope (three repositories) but no request for irreversible action (pendingADR001) |
| `success_evidence` | Draft PR landing reconciliation record + ownership map + intent records; skill validators exit 0; handoff comment on issue #80 |
| `failure_evidence` | Duplication register silently dropped; another model's implementation overwritten for preference; a trail that exists only in a chat or local worktree (the 2026-08-21/22 loss recurring) |
| `dependencies` | INTENT-0028 |
| `conflicts` | None recorded |
| `next_review_trigger` | Founder response to issue #80 or the reconciliation PR |
| `supersedes` | — |
| `superseded_by` | — |
| `implementation_refs` | `docs/collaboration/RECONCILIATION-2026-08-22-KIMI.md`; `docs/collaboration/ARCHITECTURE-OWNERSHIP-MAP.yaml`; `docs/collaboration/COLLAB-HANDOFF-KIMI-002.yaml`; `docs/collaboration/deliberation-kimi-2026-08-22.json` |
| `unresolved_questions` | WP-line (`build/*`) authorship attribution is not verifiable from git metadata; recorded as unresolved rather than claimed (pendingADR001) |

## Notes

This record binds Kimi's own conduct. It grants Kimi no authority over any
other contributor's work. The reconciliation it authorizes is records-only:
every convergence execution it recommends is held at NEEDS_FOUNDER_DECISION.
