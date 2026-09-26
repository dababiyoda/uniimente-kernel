# PR #112 supersession accounting (mechanism level)

PR #112 (`greg/usable-local-loop-20260925`, head `d0d0a34`, 3 commits by Artificial-Egregore-Uniimente)
is superseded by PR #113. This record proves that claim mechanism by mechanism instead of
assuming it from a summary. Method: every non-evidence file #112 changes relative to `main` was
compared against the #113 head. Git objects and tests were checked, not descriptions.

Founder instruction (2026-09-26): do not keep two competing active GREG futures; close #112 once
every useful mechanism is PORTED, REPLACED, intentionally NOT PORTED, or retained as
benchmark/evidence. Its branch and history are preserved and are not deleted.

## File-level comparison (32 non-evidence files)

| State in #113 | Files |
|---|---|
| Identical | `FOUNDER_EFFECT_COMPILER.md`, `UNIIMENTE_FINAL_BUILD_ORDER.md`, `FIRST_BODY_DECISION_2026-09-22.md`, `GREG-ONE-MISSION-PROOF.md`, `OPUS-RECONCILIATION.md`, `founder-loop-entry-gate.json`, `INTENT-2026-09-22-FIRST-BODY.json`, `INTENT-GREG-EMBODIED-2026-09-11.md`, `GREG-2026-09-11-excerpts.md`, `egregore/repository_audit.py`, `tests/greg_proof_driver.py`, `tests/greg_proof_observer.py`, `tests/unit/test_egregore_runtime.py`, `tests/unit/test_greg_local_mission.py`, `tests/unit/test_morning_review.py` |
| #113 is a strict superset (#112 adds 0 lines) | `AGENTS.md`, `CANONICAL_EXECUTION_ORDER.md`, `FOUNDER_INTENT_LEDGER.md`, `ARCHITECTURE-OWNERSHIP-MAP.yaml` |
| Differs | `egregore/runtime.py`, `egregore/local_mission.py`, `egregore/morning_review.py`, `verifier/local_repository_appraisal.py`, `tests/unit/test_greg_resume_authority.py` |
| Absent from #113 | `egregore/local_console.py`, `egregore/development_session.py`, `egregore/brief_learning.py`, `tests/unit/test_greg_console.py`, `tests/greg_acceptance_driver.py`, `tests/fixtures/greg_held_out.json`, `docs/GREG_LOCAL_START.md`, `docs/collaboration/GREG-USABLE-2026-09-25.md` |

## Mechanism ledger

| # | #112 mechanism | Disposition | Where it lives now / why not |
|---|---|---|---|
| 1 | Resume of standing cognition consumes an exact-suspension Gate grant; bare-hash resume records never clear a stop | **PORTED** | Hotfix PR #116, merged to `main` (`25ab9b4`); merged into #113. Tests: `tests/unit/test_resume_authority.py` (3 fail on the old code). |
| 2 | `runtime.py` without #111's institutional-leverage proposer | **Intentionally NOT PORTED** | #112 was based on `main`, where #111's code does not exist. Removing it would regress #111, which #113 preserves. |
| 3 | `integration-v1` audit profile: exact blobs of boundary + runtime/Gate/reflection/bridge files; AST finding "resume checks a hash without the Gate"; reflection outcome gap | **PORTED + PRODUCTIZED** | File identical in #113. Productized as GREG capability `repo.integration_audit` and template `integration-watch`. On the real repositories it raised one founder decision for mechanism 1's defect. |
| 4 | `GIT_NO_LAZY_FETCH=1` in exact-object Git reads | **PORTED** | Part of mechanism 3's identical file. |
| 5 | Intentional stop bound into the job; stop survives process restart | **REPLACED (stronger)** | GREG: a signed `BODY_STOP` (founder key or delegated phone key) now persists as the STOP file plus `greg.body.stop_persisted`. A restart (login, reboot, `launchctl kickstart`) exits without mission work until a human runs `greg start --local`. A plain SIGTERM (OS shutdown) is not persisted. Test: `test_a_founder_stop_survives_restart_until_a_human_clears_it`. |
| 6 | Stop/dispatch admission serialization and in-flight worker termination in the #101 finite host | **Intentionally NOT PORTED to the #101 host; REPLACED in GREG** | The #101 host is a benchmark/regression oracle in #113, not the product path. GREG is a single process with a single writer, and stop is checked before every tick and every inbox cycle. **Accepted residual:** GREG does not kill an adapter already running; the bound is the adapter's own timeout (browser ≤45 s, CLI ≤30 s). |
| 7 | Attempt budget 0..3 that cannot be refilled by restart | **REPLACED** | GREG budgets are the founder-signed light cone (`budget_usd`, horizon), derived from the ledger, so a restart cannot refill them. Uncertain dispatch becomes a founder reconciliation, never a blind retry. |
| 8 | Hard-killed host reconstructs its claim and refuses redispatch | **REPLACED** | GREG `AuthorityOffice`: claim without receipt → `UNCERTAIN` → one reconciliation request; retained receipt reused. Tests: `test_greg_body_supervised.py` (SIGKILL), `test_greg_vepmc_path.py`. |
| 9 | `morning_review.py` / `verifier/local_repository_appraisal.py` profile parameters | **Intentionally NOT PORTED** | They only serve mechanism 6's profiled #101 jobs. GREG's separate-process appraiser (`greg/appraisal.py`) re-observes `repo.integration_audit` directly. |
| 10 | Loopback web console (`local_console.py`): submit, status, stop, review, CSRF token | **REPLACED; code RETAINED AS EVIDENCE in the #112 branch** | GREG CLI + `greg serve` + phone client. Every read and command is signed by the founder key or a delegated device key, which the console's CSRF token (explicitly "not identity") could not provide. Keeping both would be two active founder interfaces. |
| 11 | Synthetic authority provisioning (`development_session.py`, label `SYNTHETIC_DEVELOPMENT_ONLY_NOT_FOUNDER_AUTHENTICATION`) | **Intentionally NOT PORTED; RETAINED AS EVIDENCE in branch** | GREG uses Ed25519 founder enrollment and Kernel grants. Synthetic authority has no product role. |
| 12 | Source-backed brief (`brief()`): goal, what changed since the previous brief, blocker, next action | **REPLACED (partly)** | The `integration-watch` decision carries each finding's evidence and `next_action`, and the morning tribunal lists decisions. **Gap not ported:** a "what changed since the previous brief" coverage diff. Candidate addition to the tribunal. |
| 13 | Held-out comparison gate (`brief_learning.compare`): retain a change only on strict gain on separate labelled cases; ties and regressions stay history; a later negative comparison withdraws the change | **Intentionally NOT PORTED as code; mechanism recorded for extraction** | It currently gates only the ordering of briefs. Its general form ("learned changes need held-out gain") is the same gate as DALEOBANKS #79. It becomes the admission rule when GREG gains model-driven learning (router weights, SOP promotion). Recorded in `REPOSITORY-METABOLISM-2026-09-25.json`. |
| 14 | Acceptance driver, console tests, held-out fixture, `tests/evidence/greg-usable/` | **RETAINED AS EVIDENCE in branch** | Preserved in the #112 branch history; the branch is not deleted. |
| 15 | `GREG_LOCAL_START.md`, `GREG-USABLE-2026-09-25.md` (decision record, two passes) | **RETAINED AS EVIDENCE in branch** | Lineage preserved there. The GREG-USABLE negative evidence (Chromium unavailable to #112; workspace reset lost commits) is cited here. The #113 phone test later ran real Chromium. |

## Conclusion

Every #112 mechanism is PORTED (1, 3, 4), REPLACED by a stronger GREG mechanism (5–8, 10, 12),
intentionally NOT PORTED with a reason (2, 9, 11, 13), or RETAINED AS EVIDENCE in the preserved
branch (10, 11, 14, 15).

Two residuals are named rather than hidden:
- in-flight adapter termination on stop (bounded by adapter timeouts);
- the "what changed since the previous brief" diff.

#112 is closed as superseded by #113. Its branch `greg/usable-local-loop-20260925` is not deleted.
