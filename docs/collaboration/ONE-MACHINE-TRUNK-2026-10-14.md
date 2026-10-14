# One-machine integration trunk — 2026-10-14

Status: **draft for founder review**. Nothing here is merged, deployed or activated.
Founder intent: `docs/intent/INTENT-20261014-ONE-MACHINE.json` (source:
`docs/intent/sources/ONE-MACHINE-CORRECTIVE-DIRECTIVE-2026-10-14-source.md`).
Branch: `claude/greg-one-machine`. Evidence: `tests/evidence/one-machine-20261014/`.

## 1. Trunk selection (measured, not assumed)

Ancestry, refreshed on 2026-10-14 at 12:38 UTC, counting commits not contained in #175 `e34dfe0`:

| Lineage | Head | Commits not in #175 | What they are |
|---|---|---|---|
| main | d64a6c9 | 0 | #165 and #170 included |
| #173 | b6d9f20 | 0 | #175 is its descendant (+6) |
| #164 | c6f6370 | 0 | RECOMBINE; already in #173 |
| #172 | cda9818 | 8 | #169 increment 3 (5), recovery patch-equivalent to 7cc8187 (1), merge (1), clock fix (1) |
| #169 | 3356be9 | 6 | the same increment 3, plus an alternative clock fix |
| #176 | 1c109ff | 6 | the same increment 3, plus a third alternative clock fix |
| #129 | 9309fd8 | 5 | egregore Genesis Loop, swappable parts |
| #157 | f66f860 | 7 | cancellable, OS-confined workers (+cortex convergence) |
| #143 | 6fa9b89 | 28 | seed-genome stack on a base before Foundry-55 (44/55) |
| #166, #171, #174 | 6dd27fd, 98143d6, e253262 | 3, 2, 1 | witness, organ bridge, per-organ keys (this session) |

**Selected trunk:** #175 `e34dfe0`. It is the descendant with the broadest history (main, #173, #164 and the original #172 construction line) and the smallest integration burden. #169's unique behavior arrives through the #172 head, which already merged it.

## 2. Imported lineages: provenance and decisions

| Source (commit) | Mechanism | Trunk equivalent before | Missing behavior | Conflicts and resolution | Proving tests | Rejected / restore |
|---|---|---|---|---|---|---|
| #172 `cda9818` carrying #169 `858610d..9c46810` | Whole loop on one path: Foundry page, memory, fixture commerce, attacks; #26 relay confining `http.get`; money columns; §13 attack map; #165/#170 router registration | none | all of it | `foundry/completion.yaml` systems 9/10, `greg/capabilities.py` InvocationContext, `greg/missions.py` observation: independent additions, both kept | acceptance, adversarial machine, confined egress, first mission, mission control, venture rehearsal (130 passed at the merge) | #169 `3356be9`, #176 `1c109ff`: alternative 2-line clock fixes, superseded by `cda9818`; restore by cherry-picking either one |
| #172 `32f99ce` | governed recovery | `7cc8187` (patch-equivalent) | none | resolved by git as identical | test_greg_capability_recovery (9) | — |
| #174 `e253262` | per-organ bridge keys; identity isolation claim | shared key only | isolated sender identity | none | test_per_organ_bridge_keys | — |
| #166 `6dd27fd` | witnessed append-only checkpoints (RFC 6962/9162), cross-organ harness | `greg/anchor.py` RFC 3161 anchoring (complementary) | witness cosigning, split-view evidence | none | test_append_only_witness, test_cross_organ_mission | — |
| #171 `98143d6` | organ exchanges observable by #44; dataplane redelivery fix; mission-trace binding | none | organ facts on GREG's journal | two latent laundering paths found by merging into the canonical body (section 3) | test_greg_organ_bridge (15) | — |
| #157 `f66f860` (partial) | `supervised_run` cancellation and bounded output; trusted git metadata during collection | blocking `subprocess.run`; no metadata protection | STOP mid-work; worker git metadata cannot run in GREG | — | test_one_machine_attacks: STOP and git-hook attacks fail on the previous code | **Not ported:** `greg/worker_isolation.py` (bubblewrap PID/user/IPC namespaces, read-only root). It refuses every worker on hosts without bubblewrap, including macOS. Founder decision; restore by porting the module and calling `prepare_worker` in `ClaudeCodeWorker.run` / `CliAgentWorker.run` |
| #129, #143 | Genesis Loop / seed genome | partial (see gap map) | under investigation in this run | not merged | — | preserved on their branches |

## 3. Defects found by integrating, and fixed

1. **Organ appraisal laundering.** `organ_bridge.record_appraisal` wrote `mission.appraised: REPRODUCED`. The body skips closure appraisal for any mission id that already has one, and VEPMC and routing read the latest. The organ appraisal now uses `organ.appraised`.
2. **Organ observation corruption.** Organ messages were `mission.observed`, which the mission engine rebuilds check state from, so it crashed with `KeyError: check_id`. Now `organ.observed`.
3. **Mind → Hands handoff impossible after Genesis.** The answer existed only in a re-observation receipt, and bindings read action receipts only. Added check-sourced bindings: a strategy may bind the receipt of the latest *passing* observation of a check it requires.
4. **Founder reconciliation crashed Mission Control and the Morning Tribunal.** No test had ever answered a reconciliation.
5. **Mission traces mis-ordered.** Timestamps came from different clocks. Traces now follow ledger sequence.
6. **STOP waited for in-flight workers** (up to 3600 s).
7. **Worker-planted git hooks/filters executed inside GREG's collection.**
8. **Silent provider-side model substitution.** `fallbacks="default"` re-ran refused requests on a provider-chosen model.
9. **Frozen-history tests failed in shallow checkouts.** This explains part of the #173/#175 discrepancy (`suite-discrepancy.json`).

## 4. Founder-reserved decisions (not taken by this run)

- Merge of this trunk, and which convergence line is canonical upstream.
- Worker OS confinement policy: adopt #157's bubblewrap-required envelope (refuses on hosts without it, including macOS), or allow a labeled lower-assurance mode per host.
- Organ pin upgrade from `uniimente-kernel-boundaries` 4999acff so organ identities are isolated (per-organ keys need organ-side support).
- The first VEPMC device: Mac or Chromebook. The source conflict is preserved, not resolved.
- Re-admission of recovered capabilities under existing mission scopes (#175's open question).
- Any provider fallback list (`anthropic_fallback_models`). Default: none.

## 5. Rollback

Every change is a separate commit on `claude/greg-one-machine`. Reverting any one leaves the others intact; reverting the whole branch is deleting the branch. No data migration was introduced. The new event types `organ.observed` and `organ.appraised` are additive, and readers tolerate their absence.
