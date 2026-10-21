# Installed-body convergence — 2026-10-14

Branch `installed-body`, started at `4b0de6a`. That commit is the canonical GREG convergence line:
3124 passed, 16 skipped, 0 failed, and every CI script passes. This record covers four things: what
the branch brings onto that line, the conditions applied while merging, the trade-off it accepts, and
the review that followed with its dispositions and residuals. Facts here come from commits, tests and
verifier runs. Nothing in this record authorizes anything. Alfonso remains root authority.

## 1. Lineages merged or ported

| Lineage | How | Commits | What it brings |
| --- | --- | --- | --- |
| #168, the installed GREG body (head `92e66e9`) | merged | `496e80c` | N3 business case (`greg/business_loop.py`, `business.reconcile`, `business_loop_closed`); N4 SOP compounding (`greg/sop.py`); N6 shared work with honored refusal (`declined_if`, `human_work_shared`); N7 venture books (`greg/venture_books.py`); the stranded capability-ask fix (`8531595`); the human-work latency fix (`924bede`); the lineage map; and its rehearsal and verifier records |
| #137, ledger hot paths (head `291e037`) | merged | `1d1208e` | `e2440a6`: verify only new ledger history on hot paths. Retained records never leave the ledger, since readers get plain copies. The verifier run is `291e037` (PASS V1-V5) |
| #138, proof integrity (head `11ba661`) | ported, not merged | `e83234a`, `8203339`, `c496ad9`, `af19b07` | closure-bound appraisal (`b8a0ccd`); the installer checks the signer it actually uses (`b8a0ccd`); the structural-candidate gate (`673726a`), re-expressed on the one founder-tier rule for N1-N7; and the proof and audit records, kept byte for byte, with the 09-30 inheritance records reconciled by hand |

Where they conflicted, the convergence line won:

- The one resolver: `foundry.systems.implementation_for`, `module` and `ALTERNATES`, with qualified
  `impl.op` names and the #169 rule.
- The one mission engine: `greg/missions.py`.
- The console parts: `greg/console.py` `home_parts`, which `greg/mission_control.py` consumes.
- The seed genome `freeze-v6` and the dual replay seal.

Where #137 or #168 built the other half of a numbered Foundry system, that half is registered as an
alternate; the canonical module was not replaced. No module, test or record was deleted:
`git diff --diff-filter=D 4b0de6a HEAD` is empty. Two test names changed, each with its reason in a
commit.

## 2. Conditions applied

- **#137 verifier conditions** (`994098f`):
  - N6 and N7 are back to `evidence_source: external`.
  - The founder tier: a `FOUNDER_TIER` attestation that grants nothing. `metrics.founder_tier` reads
    it, and `met` on N3, N4, N6 and N7 needs every closure the result rests on to be at that tier.
- **Merge interactions repaired** (`dc20679`):
  - The SOP observer no longer stops the body on a typed handoff.
  - The Consequence Gate is restored byte for byte, so the SR-002 subject hash matches again. The
    full-chain check at commit moved into the ledger: a Commit Witness is appended only onto a chain
    reconstructed whole at that moment.
- **#138 port** (`e83234a`, `c496ad9`). Two adaptations:
  - The appraisal binder re-derives the params the engine handed the Gate, so typed handoffs still
    verify.
  - N1 and N2 use the founder-tier rule instead of a hardcoded `met=False`, so a genuine founder run
    can still clear N1.

## 3. The `e2440a6` trade-off

- **Gained.** A body can tick for months:
  - one emit at 5,000 records went from 395 ms to 0.42 ms;
  - writing 5,000 events went from 619 s to 2.3 s;
  - a real tick takes 32 ms at 6,517 records.
- **Given up.** Appends and reads outside a Gate commit verify only records not yet verified. Code
  inside the process that alters the ledger's private list can be served as altered in-memory
  history for up to 300 s, or until the next explicit `verify_chain()`.
- **Kept.**
  - Every Commit Witness is appended only onto a chain verified whole at that moment. Nothing is
    witnessed, claimed or executed on altered history (`dc20679`,
    `test_a_commit_witness_is_appended_only_onto_a_wholly_verified_chain`).
  - The separate-process appraiser reopens the file read-only and verifies the whole chain.
- **Cost.** One full verification per Gate commit, sensor observations included. That costs about
  33-37 ms at 5,000 records and 124-128 ms at 20,000, so the cost still grows linearly with history.
- **Founder decision.** Making the Gate commit cheaper would trade the guarantee again; that choice
  is left to the founder.

The full finding is in `docs/collaboration/FINDING-LEDGER-APPEND-COST-2026-10-14.md`.

## 4. Review of `af19b07` and its dispositions

Two reviewers reproduced every finding with a test that passed while the defect was present (scratch
`proof_integrity/test_pi_*.py` and `test_rb_*.py`). Each finding below is now fixed with a regression
test, or recorded as a known limitation. Unless a row names another file, the tests are in
`tests/unit/test_greg_closure_integrity.py`.

The repairs landed in these commits on `installed-body`, each verified on its own index export
before it was committed:

| Commit | Findings |
| --- | --- |
| `b7ffcc0` | 2 (SOP pre-approval per exact step) and 1 (appraiser re-derives approval boundaries) |
| `1322fd7` | 5 (`fs.write` binds to its signed target) |
| `289d89f` | 4, 6, 7, 8, 9/14 (path measures, payment notice, `SCOPE_RENEWAL`, external gate) |
| `8d6a508` | 3/10 (the founder tier is a claim, labelled everywhere) and 15 (attestation state shown, installer re-run) |
| `bd6c172` | 11, 12, 13 (runbook as written, `greg path --node`, SOP text) |
| this record's commit | the "closure integrity" mutant group, the cognition mutant anchor, this record |

Re-running the reviewers' scratch reproductions on the repaired tree: 10 of the 11
`proof_integrity/test_pi_*.py` tests now fail, as they should (each asserted a defect). The one
still passing is `test_pi_founder_tier_self_attested.py`, which pins the residual of findings 3/10;
that residual is recorded, not fixed. Of the three `test_rb_*.py` tests, `test_rb_sop_expression.py`
and `test_rb_external_n6.py` now fail as they should; `test_rb_tier_bypass.py` still passes for the
same recorded residual.

| # | Finding | Severity | Disposition | Mechanism | Regression test |
| --- | --- | --- | --- | --- | --- |
| 1 | The appraiser verified an out-of-cone write that ran with no approval, or with an approval no founder command carries | major | fixed | `greg/appraisal.py` step 5 re-admits every completed action in the window against the signed `LightCone` (capability, signed target, manifest class, cost, spend so far, the action's time). If an action falls outside the cone, or its grant claims a founder approval, it needs an exact-scope request answered `approve` before it ran. That answer's `command_digest` must name one accepted `DECISION` whose envelope re-verifies against a founder key, or a device key delegated `DECISION`, as of that ledger position | `test_appraiser_refutes_an_out_of_cone_write_the_engine_never_asked_for`, `test_appraiser_refutes_an_approval_no_founder_command_carries`, positive control `test_appraiser_verifies_an_approval_the_founder_signed` |
| 2 | An SOP run pre-approved sibling steps, because `instantiate` widened the whole cone | major | fixed | `instantiate` no longer touches the cone. The signed run carries `pre_approved_steps`: one exact strategy each, internal at most, free, validated by `validate_mission` and the schema. The engine passes exactly that scope to `AuthorityOffice.act(signed_scopes=...)`, which admits it past the cone only. A constitutional `REQUIRE_HUMAN` still needs a `DECISION`. The appraiser accepts the signed pre-approval for that step only, and the signing summary shows it | `test_sop_pre_approval_admits_only_the_named_step`, `test_a_signed_pre_approval_must_name_its_exact_strategy`; one assertion in `test_greg_sop_compounding.py` changed (it encoded the widening) |
| 3, 10 | `FOUNDER_TIER` is a bare self-claim: an unprotected test key can attest itself | major | fixed as honest labelling, residual recorded | The body cannot verify key custody. The CLI's refusal is the only custody check. `founder.py`, `metrics.py`, `path.py`, the README and the runbook now call the tier the key holder's claim. Founder-tier rows carry `custody`, a met result carries `founder_tier_basis`, and `greg status`, the console and Mission Control show it. The only fixture that self-attests with an unprotected key is marked as doing so on purpose. N1 carries an `open_founder_decision`: count on the claim plus Alfonso's inspection, or wait for an authenticated external-verification contract (#138) | `test_an_unprotected_key_can_self_attest_and_every_result_says_the_tier_is_a_claim` (pins the residual and the labels) |
| 4 | N3 counted a payment from a statement GREG wrote itself | major | fixed | `_greg_wrote_human_evidence`: a GREG write whose receipt path lands on a file that a `human.*` or `professional.*` step's check (or its `declined_if`) reads refuses the case. N3 and N6 both apply it | `test_n3_never_counts_a_payment_greg_wrote_into_the_statement` |
| 5 | A typed handoff picked which workspace file `fs.write` overwrote | major | fixed | `fs_write` requires `ctx.target == "workspace:" + normalized relative path`, as `artifact.materialize` already did. Data changes what is written, never where | `test_a_handoff_cannot_choose_which_file_a_write_lands_in`; one setup line in `test_greg_capabilities.py` now gives the context its signed target |
| 6 | N3 counted a declined human step as observed work | minor | fixed | N3 uses N6's rule: only an ask withdrawn because its evidence was observed counts, and refusals are reported as `person_declined:<step>` | `test_n3_does_not_count_a_step_the_person_declined` (with control) |
| 7 | The payment step (`business.reconcile`) was still noticed only at the hourly slot | minor | fixed | `_deliverable_arrived` checks the file named in the `path` param of any read-only sensor | `test_greg_human_work_latency.py::test_the_exported_payment_statement_is_noticed_within_minutes` |
| 8 | Answering a `SCOPE_RENEWAL` ask stranded the mission | minor | fixed | `MissionEngine.answer` refuses any `DECISION` on it. The surface marks it `answerable: false`, and the console and phone offer no Approve or Reject for it. A legacy answered renewal reopens one new ask | `test_a_scope_renewal_ask_refuses_a_decision_and_stays_open`, `test_a_legacy_answered_scope_renewal_reopens_one_ask` |
| 9, 14 | `evidence_source: external` on N6 and N7 had no effect | minor (latent) | fixed | `position()` passes an external node only when its predicate also returns `external_evidence`. For N6 and N7 that is Alfonso's signed accepting critiques of the closures the result rests on | `test_an_external_node_never_passes_on_its_ledger_predicate_alone` |
| 11 | The runbook's N6 and N7 steps cannot move `greg path`, which stops at N5 | major | fixed (docs plus a view), residual recorded | The runbook and README now say `greg path` stops at N5 until N5 has a ledger predicate. `greg path --node N6` reads one later node's own measurement and says where the path stops; that reading is reported, not counted. N5 still has no predicate | `test_greg_path_reads_a_later_node_and_says_where_the_path_stops`, `test_the_runbook_signs_with_the_installed_key_and_says_the_path_stops_at_n5` |
| 12 | Runbook commands failed as written: no `--key` at N3 and N6, the wrong key path at N4 and N7, an out-of-root example path | major | fixed | Every signing command in the runbook now uses `--key ~/.greg-founder.pem`, and the N4 example reads `~/src/drafts/...`. The CLI refuses a missing key, or a key file that does not exist, with a `BodyError` instead of a traceback | `test_signing_commands_without_a_usable_key_refuse_plainly`, `test_the_runbook_signs_with_the_installed_key_and_says_the_path_stops_at_n5` |
| 13 | An SOP run's signed `founder_expression` could name a different file than the one checked | minor | fixed | `sop.render`: when the literal directory before a `{slot|basename}` token is not the run's actual directory, the actual file is named. When it is, the founder's own words are kept | `test_an_sop_run_names_the_file_it_checks_not_the_taught_directory` |
| 15 | A body designated before `FOUNDER_TIER` existed stayed silently unattested | minor | fixed | Rerunning `install.sh` checks the attestation state in `greg status` and queues `greg founder attest` with the protected key. A `--no-passphrase` key is never attested. `status()["founder_tier"]`, the console and Mission Control show whether the key is attested, and the VEPMC stat is relabelled as structural candidates | `test_greg_chromebook_install.py::test_a_rerun_offers_the_founder_tier_to_a_body_designated_without_it` |
| 16 | A load-sensitive integration test fails under CPU load, both on HEAD and on the `4b0de6a` baseline | minor, pre-existing | recorded | Not changed here (see section 5) | none |

The handoff facts from the #168 session (PR #173) were each checked:

- Confined Python children work in a venv: `greg/isolation.py` is unchanged, and the Landlock tests
  pass under the installer's venv.
- The stranded capability ask (`8531595`) is kept with its test.
- The hour-late notice (`924bede`) is kept, and its last gap, the payment step, is fixed above
  (finding 7).
- The N3, N4, N6 and N7 templates and measures exist on this tree. N6 and N7 are measured with
  `greg path --node`.

## 5. Residuals and known limitations

- **The founder tier is a claim.** Anything holding an enrolled private key, protected or not, can
  sign `FOUNDER_TIER`. Against a deliberate self-attestation, N1's kill condition ("a closure counted
  with a test key") holds only through the supported tools. This is an open founder decision
  (`greg/path.json` N1). Trust on first use at enrollment also remains.
- **N5 has no ledger predicate.** `greg path` cannot pass N5, so N6 and N7 are measured but not
  counted on the path. A predicate for N5 needs its own founder-reviewed definition of the worker
  ecology.
- **Pre-approval and policy.** A signed pre-approval admits a step past the light cone only. It never
  answers a constitutional `REQUIRE_HUMAN`; that still needs a `DECISION`.
- **SOP runs instantiated before this change.** Their cones were widened, so `sop.instantiates` no
  longer recognizes them and they do not count as runs of the procedure. This is intended: they were
  made under the defective rule. Concretely, on the reviewer's runbook body the four SOP runs show as
  `claimed_but_not_instantiating`, so N4 there reads `met: false` ("0 of 3 verified runs from the SOP")
  where it read met before. No founder body has run N4 yet; a body that had would need three new
  signed runs of the ratified procedure.
- **The appraiser's horizon check uses the action's recorded body-clock time.** The engine's
  `AuthorityOffice.act` judges the horizon by wall clock, while its `_step` judges it by body clock.
  If an action has no recorded time, its horizon is not judged.
- **Reconciled actions.** An action the founder reconciled after an interruption (`reconcile_executed`)
  has no Gate receipt, so a closure that rests on one is REFUTED. This limit is kept from #138.
- **Load-sensitive tests** (finding 16, pre-existing). Two tests fail in some runs on both HEAD and the
  `4b0de6a` export when six busy loops share the machine:
  `test_greg_cognition_mission.py::test_recombined_native_game_uses_same_gate_appraisal_and_learning_after_restart`
  and `test_greg_cognition_process.py::test_cli_composition_survives_sigkill_without_duplicate_computation`.
  Without load they pass 3 of 3. Under load, a budget-bounded solve abstains, the engine's
  inconclusive-sensing backoff then runs past the test's six ticks, and three consecutive abstentions
  escalate. A deterministic fix needs a load-independent solve budget in the cognition path. That is
  out of this branch's scope and is recorded here instead.
- **Not exercised end to end:**
  - the N7 three-case run with a second venture and surplus;
  - the LP-engine example (the installer ran with `--no-engines`);
  - the real systemd user unit and ChromeOS behaviour;
  - the GitHub token ask.
  The runbook was run with supervisord standing in for systemd, in a container with less than 10%
  free disk, which raised an environment-driven COMPUTE ask.
- **A mutant anchor moved with the code.** `check_greg_cognition_mutants.py`'s "removed permission"
  mutant anchored on the old cone check in `greg/authority.py`, which `b7ffcc0` extended with
  `signed_scopes`. It reported STALE until its anchor was updated to the new line, with the same
  mutation (`if False:`); it is caught again.
- **Reviewer scratch incident.** One reviewer overwrote another session's
  `ibscratch/test_ib_payment_latency.py`. The tests importing it no longer collect, and the original
  content is lost. No repository file was affected.
