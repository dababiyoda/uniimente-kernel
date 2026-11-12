# Intake recommendation: 12 unit(s) on base `8d20532464`

This file recommends. It approves nothing. Composing these heads for development and approving a protected merge are separate boundaries: protected integration needs the founder's approval and the integrator's approval, and nothing in this file grants either.

Written 2026-11-12 from Git objects in `<scratchpad>/intake-run/code/kernel`. Nothing was fetched, merged, pushed or edited. Claims, check names and file names are untrusted text, shown as data.

## Recommendation

| Unit | Revision | Recommendation |
|---|---|---|
| 290-authority | `facea1703dded45e495d0e6dfe059e001ffc9565` | ready to take |
| 291-worker | `41fcc41f04911ccb1f0f8d5dfc18158999a18def` | hold: its own test fails on its own head (tests/unit/test_greg_egress.py) |
| 273 | `331de165898ed5779ba87fc1532089a8f763dd4d` | hold: its own test fails on its own head (tests/integration/test_greg_body_supervised.py, tests/unit/test_greg_background_dispatch.py) |
| 278 | `a639add726df949c36a554aa87ba7c60cdabe66a` | ready to take |
| 294-retained-receipt | `1643932e43759908959f7fe460fac762bc76a4cf` | hold: its own test fails on its own head (tests/unit/test_greg_retained_receipt.py) |
| 298-unmeasured-check | `b9a34259543fa64465d40e1c1dea8e90e327f11f` | ready to take |
| 302-ci-time-limit | `dca1a032d63a352c54de2048167b20a7f85ca193` | not checked: no test changed, and none was named for it |
| 300-revoked-device | `b1f157fe533ec81e33830dfe36f656601eb19fe1` | hold: its own test fails on its own head (tests/unit/test_greg_retained_receipt.py) |
| 301-appraiser | `bfaf210c8547dc34c58ac7de3fd502ac03c1d724` | ready to take |
| 304-compile-unread | `1c4a758c4d660549472b7cc463c72c7d4d95c9b4` | take after 298-unmeasured-check, 302-ci-time-limit |
| 303-rejected-credit | `0a9a246fa1afb7b098850636f359deba8e10e58d` | hold: stale: its claims name another head |
| 293-browser | `32ca8de75bd2764251800df67932d1c3dc0522a8` | hold: its own test fails on its own head (tests/unit/test_greg_browser.py) |

- **290-authority** also: arrives with 291-worker
- **291-worker** also: behavioural conflict: merging it breaks 273's test tests/unit/test_greg_background_dispatch.py::test_a_cancel_ingested_after_the_adapter_returned_is_not_recorded_as_an_interruption
- **291-worker** also: behavioural conflict: merging it breaks 273's test tests/unit/test_greg_background_dispatch.py::test_a_cancel_the_worker_finished_before_seeing_is_reconciled_not_recorded_done
- **291-worker** also: behavioural conflict: merging it breaks 273's test tests/unit/test_greg_background_dispatch.py::test_a_dispatch_released_while_body_stopped_is_written_records_nothing_after_it
- **291-worker** also: behavioural conflict: merging it breaks 273's test tests/unit/test_greg_background_dispatch.py::test_a_long_worker_does_not_freeze_the_other_missions
- **291-worker** also: behavioural conflict: merging it breaks 273's test tests/unit/test_greg_background_dispatch.py::test_a_mission_stepped_after_its_own_background_outcome_landed_mid_turn_reads_the_recorded_state
- **291-worker** also: behavioural conflict: merging it breaks 273's test tests/unit/test_greg_background_dispatch.py::test_an_error_after_the_hand_off_kills_the_next_turn_as_it_did_inline
- **291-worker** also: behavioural conflict: merging it breaks 273's test tests/unit/test_greg_background_dispatch.py::test_nothing_is_written_after_body_stopped_names_an_unfinished_dispatch
- **273** also: behavioural conflict: its test tests/unit/test_greg_background_dispatch.py::test_a_cancel_ingested_after_the_adapter_returned_is_not_recorded_as_an_interruption passes on its own head and fails on the merged tree (cause: 291-worker)
- **273** also: behavioural conflict: its test tests/unit/test_greg_background_dispatch.py::test_a_cancel_the_worker_finished_before_seeing_is_reconciled_not_recorded_done passes on its own head and fails on the merged tree (cause: 291-worker)
- **273** also: behavioural conflict: its test tests/unit/test_greg_background_dispatch.py::test_a_dispatch_released_while_body_stopped_is_written_records_nothing_after_it passes on its own head and fails on the merged tree (cause: 291-worker)
- **273** also: behavioural conflict: its test tests/unit/test_greg_background_dispatch.py::test_a_long_worker_does_not_freeze_the_other_missions passes on its own head and fails on the merged tree (cause: 291-worker)
- **273** also: behavioural conflict: its test tests/unit/test_greg_background_dispatch.py::test_a_mission_stepped_after_its_own_background_outcome_landed_mid_turn_reads_the_recorded_state passes on its own head and fails on the merged tree (cause: 291-worker)
- **273** also: behavioural conflict: its test tests/unit/test_greg_background_dispatch.py::test_an_error_after_the_hand_off_kills_the_next_turn_as_it_did_inline passes on its own head and fails on the merged tree (cause: 291-worker)
- **273** also: behavioural conflict: its test tests/unit/test_greg_background_dispatch.py::test_nothing_is_written_after_body_stopped_names_an_unfinished_dispatch passes on its own head and fails on the merged tree (cause: 291-worker)
- **278** also: its head does not contain the base (16 commit(s) behind)
- **294-retained-receipt** also: the merge keeps both sides' lines in .github/workflows/canonical-ci.yml; nobody reviewed that resolution
- **294-retained-receipt** also: arrives with 300-revoked-device
- **298-unmeasured-check** also: the merge keeps both sides' lines in .github/workflows/canonical-ci.yml; nobody reviewed that resolution
- **298-unmeasured-check** also: arrives with 304-compile-unread
- **302-ci-time-limit** also: arrives with 300-revoked-device, 304-compile-unread
- **300-revoked-device** also: the merge keeps both sides' lines in .github/workflows/canonical-ci.yml; nobody reviewed that resolution
- **304-compile-unread** also: the merge keeps both sides' lines in .github/workflows/canonical-ci.yml; nobody reviewed that resolution
- **293-browser** also: the merge keeps both sides' lines in .github/workflows/canonical-ci.yml; nobody reviewed that resolution

## 1. Exact revisions

- base: `8d20532464b1533b28d71d8331ca3412a90dbb11`
- 290-authority: `facea1703dded45e495d0e6dfe059e001ffc9565`; contains the base; contains no other unit
- 291-worker: `41fcc41f04911ccb1f0f8d5dfc18158999a18def`; contains the base; contains 290-authority
- 273: `331de165898ed5779ba87fc1532089a8f763dd4d`; contains the base; contains no other unit
- 278: `a639add726df949c36a554aa87ba7c60cdabe66a`; does NOT contain the base (16 commit(s) of the base are missing from it); contains no other unit
- 294-retained-receipt: `1643932e43759908959f7fe460fac762bc76a4cf`; contains the base; contains no other unit
- 298-unmeasured-check: `b9a34259543fa64465d40e1c1dea8e90e327f11f`; contains the base; contains no other unit
- 302-ci-time-limit: `dca1a032d63a352c54de2048167b20a7f85ca193`; contains the base; contains no other unit
- 300-revoked-device: `b1f157fe533ec81e33830dfe36f656601eb19fe1`; contains the base; contains 294-retained-receipt, 302-ci-time-limit
- 301-appraiser: `bfaf210c8547dc34c58ac7de3fd502ac03c1d724`; contains the base; contains no other unit
- 304-compile-unread: `1c4a758c4d660549472b7cc463c72c7d4d95c9b4`; contains the base; contains 298-unmeasured-check, 302-ci-time-limit
- 303-rejected-credit: `0a9a246fa1afb7b098850636f359deba8e10e58d`; contains the base; contains no other unit
- 293-browser: `32ca8de75bd2764251800df67932d1c3dc0522a8`; contains the base; contains no other unit

## 2. Dependency order

1. 290-authority (arrives with 291-worker)
2. 291-worker (after 290-authority)
3. 273
4. 278
5. 294-retained-receipt (arrives with 300-revoked-device)
6. 298-unmeasured-check (arrives with 304-compile-unread)
7. 302-ci-time-limit (arrives with 300-revoked-device, 304-compile-unread)
8. 300-revoked-device (after 294-retained-receipt, 302-ci-time-limit)
9. 301-appraiser
10. 304-compile-unread (after 298-unmeasured-check, 302-ci-time-limit)
11. 303-rejected-credit
12. 293-browser

The order above follows ancestry only: a head comes after every head it contains.

## 3. Textual conflicts

- **294-retained-receipt**: both sides' lines were kept in `.github/workflows/canonical-ci.yml` (asked for by the mission for these files only; nobody reviewed the result)
- **298-unmeasured-check**: both sides' lines were kept in `.github/workflows/canonical-ci.yml` (asked for by the mission for these files only; nobody reviewed the result)
- **300-revoked-device**: both sides' lines were kept in `.github/workflows/canonical-ci.yml` (asked for by the mission for these files only; nobody reviewed the result)
- **304-compile-unread**: both sides' lines were kept in `.github/workflows/canonical-ci.yml` (asked for by the mission for these files only; nobody reviewed the result)
- **293-browser**: both sides' lines were kept in `.github/workflows/canonical-ci.yml` (asked for by the mission for these files only; nobody reviewed the result)

Merged, in this order: 290-authority, 291-worker, 273, 278, 294-retained-receipt, 298-unmeasured-check, 302-ci-time-limit, 300-revoked-device, 301-appraiser, 304-compile-unread, 303-rejected-credit, 293-browser.

## 4. Behavioural conflicts a clean merge does not reveal

- `tests/unit/test_greg_background_dispatch.py::test_a_cancel_ingested_after_the_adapter_returned_is_not_recorded_as_an_interruption`, a test of **273**: passes on its own head, fails on the merged tree. Cause: **291-worker**; passes when this head is left out.
- `tests/unit/test_greg_background_dispatch.py::test_a_cancel_the_worker_finished_before_seeing_is_reconciled_not_recorded_done`, a test of **273**: passes on its own head, fails on the merged tree. Cause: **291-worker**; passes when this head is left out.
- `tests/unit/test_greg_background_dispatch.py::test_a_dispatch_released_while_body_stopped_is_written_records_nothing_after_it`, a test of **273**: passes on its own head, fails on the merged tree. Cause: **291-worker**; passes when this head is left out.
- `tests/unit/test_greg_background_dispatch.py::test_a_long_worker_does_not_freeze_the_other_missions`, a test of **273**: passes on its own head, fails on the merged tree. Cause: **291-worker**; passes when this head is left out.
- `tests/unit/test_greg_background_dispatch.py::test_a_mission_stepped_after_its_own_background_outcome_landed_mid_turn_reads_the_recorded_state`, a test of **273**: passes on its own head, fails on the merged tree. Cause: **291-worker**; passes when this head is left out.
- `tests/unit/test_greg_background_dispatch.py::test_an_error_after_the_hand_off_kills_the_next_turn_as_it_did_inline`, a test of **273**: passes on its own head, fails on the merged tree. Cause: **291-worker**; passes when this head is left out.
- `tests/unit/test_greg_background_dispatch.py::test_nothing_is_written_after_body_stopped_names_an_unfinished_dispatch`, a test of **273**: passes on its own head, fails on the merged tree. Cause: **291-worker**; passes when this head is left out.

Failing before the merge (not a composition problem):
- `tests/unit/test_greg_egress.py::test_a_repaired_redirect_through_the_authority_office_is_done_not_uncertain` (from 291-worker)
- `tests/unit/test_greg_egress.py::test_a_request_http_client_cannot_form_is_a_definite_refusal` (from 291-worker)
- `tests/unit/test_greg_egress.py::test_a_same_host_location_urllib_repairs_is_repaired_then_checked[/nopath-/]` (from 291-worker)
- `tests/unit/test_greg_egress.py::test_a_same_host_location_urllib_repairs_is_repaired_then_checked[/space-/My%20Report]` (from 291-worker)
- `tests/unit/test_greg_egress.py::test_a_same_host_location_urllib_repairs_is_repaired_then_checked[/utf8-/caf%C3%A9]` (from 291-worker)
- `tests/integration/test_greg_body_supervised.py::test_body_survives_hard_kill_waits_for_founder_and_stops_on_command` (from 273)
- `tests/unit/test_greg_background_dispatch.py::test_a_body_closing_on_an_error_stops_and_records_its_running_worker_before_the_ledger_closes` (from 273)
- `tests/unit/test_greg_background_dispatch.py::test_a_founder_cancel_or_detach_while_the_worker_runs_interrupts_it[cancel]` (from 273)
- `tests/unit/test_greg_background_dispatch.py::test_a_founder_cancel_or_detach_while_the_worker_runs_interrupts_it[detach]` (from 273)
- `tests/unit/test_greg_background_dispatch.py::test_a_founder_cancel_or_detach_while_the_worker_runs_interrupts_it[supersede]` (from 273)
- `tests/unit/test_greg_background_dispatch.py::test_a_pause_while_the_worker_runs_does_not_interrupt_the_admitted_act` (from 273)
- `tests/unit/test_greg_background_dispatch.py::test_a_worker_that_ignores_its_stop_has_its_process_group_killed_when_the_body_closes` (from 273)
- `tests/unit/test_greg_retained_receipt.py::test_a_refused_read_reused_after_a_restart_passes_no_check_and_closes_no_mission[False-observed0]` (from 294-retained-receipt)
- `tests/unit/test_greg_retained_receipt.py::test_a_refused_read_reused_after_a_restart_passes_no_check_and_closes_no_mission[False-observed0]` (from 300-revoked-device)
- `tests/unit/test_greg_browser.py::test_a_mission_observes_javascript_rendered_truth_and_the_page_cannot_phone_home` (from 293-browser)
- `tests/unit/test_greg_browser.py::test_the_signed_target_must_name_the_host_the_browser_contacts` (from 293-browser)

Every test file, on the unit's own head and on the merged tree:

| Unit | Test file | Own head | Merged tree |
|---|---|---|---|
| 290-authority | `tests/unit/test_greg_authority_attach_state.py` | passed | passed |
| 291-worker | `tests/unit/test_greg_authority_attach_state.py` | passed | passed |
| 291-worker | `tests/unit/test_greg_authority_registered_identity.py` | passed | passed |
| 291-worker | `tests/unit/test_greg_capabilities.py` | passed | passed |
| 291-worker | `tests/unit/test_greg_egress.py` | failed | failed |
| 291-worker | `tests/unit/test_greg_handoff_evidence.py` | passed | passed |
| 273 | `tests/integration/test_greg_body_supervised.py` | failed | failed |
| 273 | `tests/unit/test_greg_background_dispatch.py` | failed | failed |
| 278 | `tests/unit/test_genomes_formal_b.py` | passed | passed |
| 278 | `tests/unit/test_resource_bounds.py` | passed | passed |
| 294-retained-receipt | `tests/integration/test_greg_retained_receipt_process.py` | passed | passed |
| 294-retained-receipt | `tests/unit/test_greg_retained_receipt.py` | failed | failed |
| 294-retained-receipt | `tests/unit/test_greg_retained_receipt_history.py` | passed | passed |
| 298-unmeasured-check | `tests/integration/test_greg_mind_constructs_capability.py` | passed | passed |
| 298-unmeasured-check | `tests/unit/test_greg_functional_reconstitution.py` | passed | passed |
| 298-unmeasured-check | `tests/unit/test_greg_precondition_unheld.py` | passed | passed |
| 300-revoked-device | `tests/integration/test_greg_retained_receipt_process.py` | passed | passed |
| 300-revoked-device | `tests/unit/test_greg_retained_receipt.py` | failed | failed |
| 300-revoked-device | `tests/unit/test_greg_retained_receipt_history.py` | passed | passed |
| 300-revoked-device | `tests/unit/test_greg_revoked_device_authority.py` | passed | passed |
| 300-revoked-device | `tests/unit/test_greg_revoked_device_review.py` | passed | passed |
| 301-appraiser | `tests/unit/test_greg_appraiser_attach_state.py` | passed | passed |
| 301-appraiser | `tests/unit/test_greg_failure_closure.py` | passed | passed |
| 304-compile-unread | `tests/integration/test_greg_mind_constructs_capability.py` | passed | passed |
| 304-compile-unread | `tests/unit/test_greg_compile_host_stop.py` | passed | passed |
| 304-compile-unread | `tests/unit/test_greg_compile_unanswered.py` | passed | passed |
| 304-compile-unread | `tests/unit/test_greg_functional_reconstitution.py` | passed | passed |
| 304-compile-unread | `tests/unit/test_greg_precondition_unheld.py` | passed | passed |
| 303-rejected-credit | `tests/unit/test_greg_evidence_corrections.py` | passed | passed |
| 293-browser | `tests/unit/test_greg_browser.py` | failed | failed |
| 293-browser | `tests/unit/test_greg_browser_binary.py` | passed | passed |

## 5. Claims matched to executed evidence

- **290-authority**: no claims supplied.
- **291-worker**: no claims supplied.
- **273**: no claims supplied.
- **278**: no claims supplied.
- **294-retained-receipt**: no claims supplied.
- **298-unmeasured-check**: a claims record was supplied with no validation entry.
- **302-ci-time-limit**: a claims record was supplied with no validation entry.
- **300-revoked-device**: a claims record was supplied with no validation entry.
- **301-appraiser**: no claims supplied.
- **304-compile-unread**: no claims supplied.
- **303-rejected-credit**: "pytest of 9 files on b27e81f5 + 9097b276" (claimed: pass): **stale: the claim names head 9097b276635742dfdcad98dfbae1dd78b3fddb5c, this unit is 0a9a246fa1afb7b098850636f359deba8e10e58d**.
- **293-browser**: no claims supplied.

## 6. Missing or stale appraisals

- **290-authority**: appraisal: **no result for this exact head** (nothing was supplied for this unit).
- **291-worker**: appraisal: **no result for this exact head** (nothing was supplied for this unit).
- **273**: appraisal: **no result for this exact head** (nothing was supplied for this unit).
- **278**: appraisal: **no result for this exact head** (nothing was supplied for this unit).
- **294-retained-receipt**: appraisal: **no result for this exact head** (nothing was supplied for this unit).
- **298-unmeasured-check**: check "1 Kernel and organ tests": **passed**.
- **298-unmeasured-check**: check "10 Mutation gates": **passed**.
- **302-ci-time-limit**: check "1 Kernel and organ tests": **passed**.
- **302-ci-time-limit**: check "9 Institutional verifier": **passed**.
- **302-ci-time-limit**: check "10 Mutation gates": **passed**.
- **300-revoked-device**: check "1 Kernel and organ tests": **passed**.
- **300-revoked-device**: check "9 Institutional verifier": **passed**.
- **300-revoked-device**: check "10 Mutation gates": **no result for this exact head** (concluded in_progress, which is not a result).
- **300-revoked-device**: check "10 Mutation gates": **result is for another head (stale)** (it names head 0aa09c87).
- **301-appraiser**: appraisal: **no result for this exact head** (nothing was supplied for this unit).
- **304-compile-unread**: appraisal: **no result for this exact head** (nothing was supplied for this unit).
- **303-rejected-credit**: appraisal: **no result for this exact head** (no check result was supplied for this revision).
- **293-browser**: appraisal: **no result for this exact head** (nothing was supplied for this unit).

## 7. Reproducible recipe

```
python scripts/compose_rehearsal.py --repo <scratchpad>/intake-run/code/kernel --base 8d20532464b1533b28d71d8331ca3412a90dbb11 --unit 290-authority=facea1703dded45e495d0e6dfe059e001ffc9565 --unit 291-worker=41fcc41f04911ccb1f0f8d5dfc18158999a18def --unit 273=331de165898ed5779ba87fc1532089a8f763dd4d --unit 278=a639add726df949c36a554aa87ba7c60cdabe66a --unit 294-retained-receipt=1643932e43759908959f7fe460fac762bc76a4cf --unit 298-unmeasured-check=b9a34259543fa64465d40e1c1dea8e90e327f11f --unit 302-ci-time-limit=dca1a032d63a352c54de2048167b20a7f85ca193 --unit 300-revoked-device=b1f157fe533ec81e33830dfe36f656601eb19fe1 --unit 301-appraiser=bfaf210c8547dc34c58ac7de3fd502ac03c1d724 --unit 304-compile-unread=1c4a758c4d660549472b7cc463c72c7d4d95c9b4 --unit 303-rejected-credit=0a9a246fa1afb7b098850636f359deba8e10e58d --unit 293-browser=32ca8de75bd2764251800df67932d1c3dc0522a8 --union .github/workflows/canonical-ci.yml --timeout 900
```

Composed tree: `ae73028df2505a4de187165a55537d5f2de69859` (the tree of the in-memory merge; no ref points at it).
The command repeats the composition and the tests as you, outside GREG's confinement, with its timeout applied to a whole unit's test run. It prints its own report.

## 8. What remains unproven

- only the named tests were run: a clean result does not prove the heads are compatible
- a unit left out for a textual conflict was not tested in the merge
- where both sides' lines were kept in a named file, that resolution was not reviewed by a person
- read-only: nothing was merged, pushed or edited; no result here approves a merge
- **302-ci-time-limit**: no test changed, and none was named for it
- **290-authority**: no claims supplied
- **291-worker**: no claims supplied
- **273**: no claims supplied
- **278**: no claims supplied
- **294-retained-receipt**: no claims supplied
- **301-appraiser**: no claims supplied
- **304-compile-unread**: no claims supplied
- **293-browser**: no claims supplied
- **278**: its head does not contain the base (16 commit(s) behind)
- **294-retained-receipt**: the merge keeps both sides' lines in .github/workflows/canonical-ci.yml; nobody reviewed that resolution
- **298-unmeasured-check**: the merge keeps both sides' lines in .github/workflows/canonical-ci.yml; nobody reviewed that resolution
- **300-revoked-device**: the merge keeps both sides' lines in .github/workflows/canonical-ci.yml; nobody reviewed that resolution
- **304-compile-unread**: the merge keeps both sides' lines in .github/workflows/canonical-ci.yml; nobody reviewed that resolution
- **293-browser**: the merge keeps both sides' lines in .github/workflows/canonical-ci.yml; nobody reviewed that resolution
- the tests ran under: supervised: network denied, environment scrubbed, filesystem confined by Landlock (reads the runtime, writes only the clone) (body setting: supervised); a test that needs the network or a file outside its tree fails here on both trees alike
- a head's tests are that head's code: a head that forges its own test output is not detected here
- all units' tests ran in one exported copy of the merged tree, one after another: a test that rewrites that copy can change a later result
- the independent appraiser re-renders this file from its receipt and compares the bytes; it does not run the tests again
- claims and check results were supplied by the mission's author; none was read from a hosting service here

## 9. Approval boundaries

This file recommends. It approves nothing. Composing these heads for development and approving a protected merge are separate boundaries: protected integration needs the founder's approval and the integrator's approval, and nothing in this file grants either.

## Evidence

- request digest: `sha256:d352d08f0c497fafec4f5b4d0c9e3925bf9444eacf8079f45cdae117e4687503`
- inputs digest: `sha256:4f76a7e5891da2fa012a32ef159298c1bcbeac163fc05cdd09f28669944b67f0`
- renderer: `greg.intake.render/1`; test files started: 74
