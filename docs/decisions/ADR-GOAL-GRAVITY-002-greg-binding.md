# ADR: Bind Goal Gravity to the GREG body as one canonical persistent operating path

- Decision ID: ADR-GOAL-GRAVITY-002
- Status: proposed (branch `gg-binding` on the GREG convergence lineage `57a086e`; adoption into `main` is a founder decision)
- Date: 2026-10-14
- Decision owner: Alfonso Lopez
- Deliberation level: Constitutional (adds two founder command kinds and a body-hosted mode to the canonical runtime)
- Founder intent references: `INTENT-20261013-GOAL-GRAVITY` (Mission F; completion items 5 and 14), `INTENT-0030`
  (effect, not metaphor), `SR001-FOUNDER-LOOP-ENTRY`; ADR-GOAL-GRAVITY-001's reconciliation table, which named this
  adapter ("missions consume goals from `GoalRegistry` and answer asks via `founder_answer`")
- Supersedes: none (additive). Superseded by: none.

## Problem

Two Goal Gravity lineages exist on the convergence line and both are preserved: the egregore loop
(`egregore/gravity.py`, persistent goals on any ledger, declared-lineage authority, an optional Gate path) and #158's
one-turn read-only analysis (`greg/gravity.py`, `greg gravity --situation`). The GREG body has the only real founder
authentication (Ed25519 commands, nonce, TTL, body binding), the only mission engine and the only founder-ask path,
but no persistent goals. The residual deficit is a binding: a founder-signed goal on the body ledger that wakes on
relevant evidence, makes its signed missions act sooner, and reaches the founder only through the one ask path,
without becoming a second authority, ledger, engine or ask channel.

## Decision

Land the **minimal-adapter** design (three designs were judged; it won both judges) with every required graft and
the recommended ones, as `greg/goal_gravity.py` plus additive lines elsewhere:

```text
founder-signed GOAL --Body.apply (Ed25519, nonce, TTL)--> egregore GoalRegistry on the one body ledger
Body.tick -> goal_gravity.tick (before the mission engine; no goal record = no work, no record)
   admission  founder_facts: every retained GOAL / GOAL_CONTROL re-judged at its own ledger position (key valid
              there, this body, unused nonce, accepted inside its signed validity, goal record dated inside it,
              and the command path's own check_goal / check_control); anything else preserved and quarantined
   guard      every signed closure (revoke, supersede), stop / change, narrowing preference and priority floor is
              restored if an unsigned record widened it (narrowing only)
   settle     a DECISION for exactly that request and answer, signature-verified, becomes the goal's route
              refusal (both lineages remember)
   sense      the Gate receipt of each check's own sensor read with the check predicate recomputed,
              separate-process appraisals, greg.path, non-quarantined intake (untrusted, judged by the mission
              and goal subjects its text names); only new or changed evidence
   reopen     a completed goal whose plan node an attributed observation shows regressed is dormant again
   loop       egregore GoalGravityLoop.turn in body mode: no gate, no executor, no grants (ContractError otherwise)
                awake goal  -> MissionEngine.observe_now for its signed missions (timing only, rate-limited); a
                               mission awaiting an APPROVAL then prepares in cone while the decision stays open
                decision    -> MissionEngine.request_decision: the engine's own APPROVAL, exact scope, same id
                               (refused while the mission is paused or closed: one notice, never a fault)
                information -> greg.goal.notice
MissionEngine -> AuthorityOffice -> ConsequenceGate stays the only execution path.
```

`GOAL` is founder-key only. `GOAL_CONTROL` is device-delegable, but a device may only narrow a goal
(`stop_pushing` true, `lower_priority`, `never_use_tactic`, `do_not_monitor`, `ask_before`, `forget_route`,
`revoke_capability`); un-pause, `change_goal` and `revoke` need the founder key.

## Grafts

| # | Graft (judges) | Status | Where |
|---|---|---|---|
| 1 | Router excludes `superseded`; per-goal wake failures isolated and recorded; sensing cursor advances only after `turn` succeeds; regression test | DONE | `egregore/relevance.py`, `egregore/gravity.py` (`egregore.goal_wake_refused`), `greg/goal_gravity.py::_tick`; `test_after_a_signed_supersede_relevant_evidence_wakes_the_replacement_without_a_fault`, `test_a_faulted_turn_does_not_lose_the_waking_evidence`, `test_superseded_goal_never_wakes_and_its_replacement_does` |
| 2 | Goal decision asks through a public `MissionEngine.request_decision` (APPROVAL, exact `AuthorityOffice.scope_digest`, deterministic id); no `req-goal-*`, no ask-then-withdraw | DONE | `greg/missions.py::strategy_scope/request_decision`; asserted in `test_mission_F_end_to_end` |
| 3 | Body-hosted attention store writes no `egregore.founder_ask/answer` (information becomes `greg.goal.notice`), unsigned `answer()` raises; closure: no founder answer without a verified DECISION | DONE | `egregore/attention.py` (store seam), `greg/goal_gravity.py::BodyAttentionStore`, `ledger_closure` |
| 4 | Constructor-level body mode: on a ledger carrying `greg.founder.enrolled` `turn()` raises `ContractError` for any gate, executor or grants | DONE | `egregore/gravity.py` (`body_mode`, decided by the ledger as well as the flag) |
| 5 | `GOAL_CONTROL` device-delegable only for narrowing kinds; un-pause, `change_goal`, `GOAL` founder-key only | DONE | `greg/founder.py`, `greg/goal_gravity.py::_control` |
| 6 | Quarantine stray `goal_transition` / `goal_preference` records on a body ledger instead of raising forever | DONE | `egregore/goals.py` (`quarantine_unhydratable`, `refresh`), `greg.goal.record_quarantined` |
| 7 | Founder operation without code | DONE | `greg gravity authorize --from-mission`, `goals`, `evidence`, `control`; `status()['gravity']` (phone `/api/status`), morning report `goal_gravity`, console "Persistent goals", phone list |
| 8 | Founder-paused missions labelled `paused` alongside the preserved #158 `dormant` contract (`dormant` list, `wake.was`, `named_mission_state` unchanged; `paused` list, `wake.was_label`, `named_mission_label` added); `status()` no longer presents missions and goals under one unlabelled key | DONE | `greg/gravity.py::_goals`; `greg/body.py::status` (`missions`, legacy `goals`, `keys`, `gravity`) |
| 9 | Zero confidence with an explicit label when a goal has no world evidence | DONE, scoped to body mode | `egregore/gravity.py::_evidence` (`no_world_evidence`). Applying it to standalone egregore loops breaks three tests that pin that lineage's documented `caller_attested_only` semantics (probe: 3 failed); both lineages are preserved, so the standalone label stays and is honest there |
| 10 | Detective closure: every `grant_dispatch` traces to a `greg.authority.grant_issued` whose `authority_ref` is a verified founder MISSION digest | DONE | `greg/goal_gravity.py::ledger_closure`; `closure/gravity_registry.py::greg_goal_gravity_closures` (evidence closure); projection and morning report |
| 11 | Retained envelopes verify against the founder key enrolled at that ledger position; device revocation and expiry apply to mirrored DECISIONs | DONE | `greg/goal_gravity.py::signed_commands` (ledger order; rotation, enrollment and revocation count only as founder-signed accepted commands) |
| - | Fold signed LIFECYCLE PAUSED/ABANDONED of bound missions into goal preferences (optional) | SKIPPED | A paused mission already yields nothing to a goal: `observe_now` and `request_decision` refuse it, so no pull and no ask; the refused ask is one `ask_not_recorded` notice, recorded once and settled until the refusal reason changes (fix stage 2; before it, every later wake faulted the turn). Folding would make the binding a second writer of goal preferences from mission facts; revisit if notices for paused missions prove noisy |
| - | Fold-time re-verification of `mission.registered` / `decision.answered` (ledger-first P2) | DEFERRED | A separate hardening scope (it changes every mission fold and fixtures that write `mission.registered` directly). The goal lineage already refuses unsigned answers; the mission lineage does not yet |

Existing tests touched: the phone guardrail in `test_greg_platform` adds `GOAL` to the founder-only set (an
extension). The binding stage also *replaced* one assertion of
`test_greg_gravity::test_dormant_goals_wake_only_as_a_founder_proposal` (`wake.was` `dormant` -> `paused`); that was a
change of the preserved #158 contract, not an extension, and an earlier version of this ADR said otherwise. The fix
stage restored the #158 value (`dormant`) in the code and the assertion, and asserts the new `paused` labels alongside;
the 57a086e copy of that test passes unchanged.

## Fix stage: independent authority and security review (2026-10-14)

An adversarial reviewer reproduced eight defects against the binding (and a second reviewer two attribution and
contract defects). Governing principle of the fixes: every authority-relevant goal fact (admission, closure, narrowing
preferences, priority floor, stop, answers) is re-derived from signature-verified founder commands bound to this
`body_id`, at their ledger position, with the validator the command path uses; unsigned or mismatched records are
quarantined and labelled, never trusted. Each fix has a regression test that fails on the pre-fix head (`e75ad3b`).

| Finding | Fix | Regression test (`tests/unit/test_greg_goal_gravity_authority.py` unless named) |
|---|---|---|
| DECISION digest unbound (any verified digest counted as a signed DECISION) | `signed_answer()`: kind DECISION, same `request_id`, same answer; used by `_settle`, `answer_for`, `evidence()`, `ledger_closure` | `test_signed_answer_binds_kind_request_and_answer`, `test_a_forged_reject_citing_the_goal_digest_is_not_mirrored`, `test_a_forged_approve_is_never_reported_signature_verified` |
| `ledger_closure` passed an unsigned founder answer citing a real DECISION | every `egregore.founder_answer` on a body is a problem; every `decision.answered` without a matching signed DECISION is a problem (`unsigned_answers`) | `test_ledger_closure_flags_any_founder_answer_on_a_body` |
| Smuggled admission of a rejected (widening) or expired GOAL | `founder_facts()` re-judges each GOAL at its position: nonce unused (rejected GOAL / GOAL_CONTROL nonces are consumed), accepted inside its validity, goal record dated inside it and before acceptance, `check_goal` on the mission book and facts there | `test_a_goal_rejected_for_widening_authority_is_never_admitted_when_smuggled`, `test_a_never_delivered_widening_goal_fails_the_validator_at_its_position`, `test_an_expired_never_applied_goal_is_never_admitted_when_smuggled` |
| Guard gaps (unsigned un-supersede, un-mute, priority raise) | `_guard` restores signed revoke / supersede, stop / change, every signed narrowing value and the priority floor | `test_an_unsigned_record_cannot_resurrect_a_founder_superseded_goal`, `test_an_unsigned_record_cannot_undo_a_founder_revoke`, `test_an_unsigned_record_cannot_unmute_or_drop_any_signed_narrowing`, `test_an_unsigned_record_cannot_raise_priority_above_what_the_founder_signed` |
| Rejected duplicate GOAL replayed after a revoke | verified-then-rejected GOAL / GOAL_CONTROL record `consumed` (nonce); `consumed_nonces()` in `Body._seen_nonce` and the remote pre-check; a GOAL signed before a signed revoke / supersede of the same intent is refused | `test_a_rejected_goal_file_cannot_be_replayed_after_a_revoke`, `test_a_goal_signed_before_a_revoke_cannot_bring_the_intent_back` |
| Receipt substitution in `_sense` | `_sensor_receipt()`: grant under this mission's signed command, witness on the check's sensor capability and target, exact sensor scope digest for static params | `test_a_foreign_receipt_never_makes_a_forged_observation_evidence` |
| Ask for a founder-excluded strategy | `check_goal` refuses excluded strategies and rejected scopes; `request_decision` refuses excluded and failed strategies (as the mission's own selection does) | `test_a_goal_may_not_name_a_strategy_the_founder_excluded`, `test_the_goal_ask_path_refuses_an_excluded_strategy`, `test_the_goal_ask_path_refuses_a_strategy_the_mission_would_not_select` |
| Founder views verified without `body_id` | `signed_commands` / `founder_facts` default to the body the root enrollment names | `test_founder_views_do_not_admit_a_goal_signed_for_another_body` |
| Prewritten backdated goal record | `command()` refuses a GOAL whose goal record already exists outside the envelope's validity; admission requires the record inside it | `test_a_prewritten_backdated_goal_record_is_refused_and_never_admitted` |
| Surfaces misattribute stops | `stopped_by_founder` and `stop_label` come from the signed stop in force; unsigned and quarantine stops are labelled as such | `test_only_a_signed_stop_is_shown_as_stopped_by_you`, `test_a_quarantined_goal_is_labelled_as_quarantine_not_as_your_stop` |
| #158 `dormant` contract changed without alias | `dormant` kept in `wake.was` / `named_mission_state`; `paused` added as `was_label` / `named_mission_label` | `tests/unit/test_greg_gravity.py::test_dormant_goals_wake_only_as_a_founder_proposal` |

### Known limitations after the fix stage

- **Acceptance time is a body-clock claim.** An in-process writer that can append ledger records can still smuggle a
  genuine, never-delivered, unexpired-at-the-claimed-time founder envelope (unused nonce) by writing its goal record and
  a `command.accepted` with an in-window `accepted_at` / `authorized_at`; the ledger cannot tell that from a real
  acceptance. Bounded: it must be founder-signed for this body, pass every validator at its position, cannot undo a
  later-signed stop / resume (stale stop controls are refused) and cannot re-open an intent the founder closed later.
- **Mission-side P2 unchanged.** `MissionBook` still folds an unsigned `decision.answered` and executes on an approve;
  the goal side never vouches for it and `ledger_closure` now reports it (`unsigned_answers`). Owner: Alfonso; trigger:
  the separate fold-time re-verification change.
- **Function sensors and bound params.** For a sensor named by function (capability resolved at run time) or with
  `$from_action` params, the receipt binding checks the mission's signed authority, the witness target and the grant
  link, but not the exact scope digest.
- **Unsigned narrowing stays.** An unsigned record can still stop, close or complete a goal (narrowing); the views label
  such stops "stopped by an unsigned record, not by you" and never restore a widening.
- **Nonce consumption on rejection covers GOAL and GOAL_CONTROL only**; other kinds keep today's behaviour (a rejected
  DECISION may be re-dropped while valid, e.g. once its request exists).
- **Records without `accepted_at`.** `Body.apply` now records it. A GOAL without it falls back to its goal record's
  `authorized_at`; a GOAL_CONTROL without it is not counted (only test ledgers of the binding stage carry such
  records); MISSION and DECISION records without it skip the validity check (pre-existing body ledgers). Device expiry
  is judged at the acceptance time when recorded, at `issued_at` otherwise.
- **Capability manifests for re-validation** are the built-ins plus `greg.capability.registered` records; a goal move on
  a capability registered without a journal record is refused (narrowing).
- **Cost.** `founder_facts` is one ordered pass over the ledger (chain verify, signature checks, mission fold) per tick,
  command and founder view, the same order as before; cache by ledger length if measured hot.

## Fix stage 2: founder-effect review (2026-10-14)

A second reviewer judged the binding against the founder effect itself (Mission F; INTENT-0030: preserve the effect,
do not literalize the metaphor) rather than its authority. Target effect: a persistent goal ignores noise, wakes on
meaningful evidence judged by content, recalculates the bottleneck, has its missions do permitted in-cone
preparation through the Gate even while a consequential decision is pending, and asks Alfonso only for that
decision, once, on the one ask path; approval executes once. Mechanisms chosen are the simplest that produce it:
a lexical relevance rule over names the founder already signed (no model), the mission engine's own loop and Gate
for preparation (no new executor), observation-tier reopening (no new goal status). Each fix has a regression test
in `tests/unit/test_greg_goal_gravity_founder_effect.py` (unless named) that fails on `e75ad3b`.

| Finding | Fix | Regression test |
|---|---|---|
| (blocking) A paused or abandoned bound mission faulted every later turn (`goal.notice` identity reused with a new time) and other goals' missions were no longer pulled | `BodyAttentionStore`: a notice is recorded once per (item, kind, reason); a decision whose ask the engine refuses stays settled while the same `MissionEngine.ask_refusal` holds and is routed again when it changes; any contained error in one ask becomes that goal's notice | `test_a_closed_bound_mission_never_faults_the_turn_and_other_goals_keep_pulling[PAUSED,ABANDONED]`, `test_a_refused_ask_is_settled_until_the_founder_resumes_the_mission_then_asked_once` |
| Mission F's core order not demonstrated: with the ask open, a relevant trigger woke the goal but nothing was prepared | `MissionEngine.observe_now` may pull a mission awaiting an APPROVAL (one pull pending at a time); `_step` then runs `_prepare`: re-observe through the Gate, pursue the failing checks the awaited strategy does not advance with static in-cone strategies only (`_pursue(prepare_for=...)` never asks or blocks), record `mission.prepared` when nothing more can be done. Only `observe_now` sets the pull, so goal-less missions are unchanged (differential: identical 67-record ledger sequence) | `test_a_pulled_mission_awaiting_an_approval_repairs_in_cone_and_never_runs_the_awaited_move`; `tests/unit/test_greg_goal_gravity.py::test_mission_F_end_to_end_while_the_decision_is_open`; guard `test_a_mission_without_a_goal_still_only_waits_on_its_decision` |
| Noise vs meaning decided by channel only | `intake_about` names the missions and goal subjects an intake text mentions (mission id and its last segment, base names of sensor and strategy targets, relevant entities; whole words, case-folded); `BodyRelevanceRouter` (through the new `GoalRelevanceRouter.score` hook) counts such a mention as a subject match on any channel and drops the channel match for a goal the text does not name | `test_intake_wakes_a_goal_by_what_its_content_names_not_by_its_channel`, `test_a_channel_only_goal_wakes_only_on_content_about_it`, the end-to-end test above (noise and meaning on one channel) |
| A goal from `authorize --from-mission` could never be woken by external evidence | covered by the content rule: intake naming the mission or its targets matches the derived goal's `subject` condition on any channel | `test_a_goal_derived_without_code_wakes_on_external_evidence_and_its_mission_repairs` |
| A goal of an infinite mission completed for good and refused founder controls | `_reopen`: a completed admitted goal whose plan-node metric an attributed observation shows regressed is dormant again before the turn (same turn may wake it); `command()` records any control on a completed goal (stop / change pause it, narrowing keeps it completed); surfaces label it `holding` (`completion_label`) | `test_a_goal_of_an_infinite_mission_reopens_when_a_check_regresses_and_takes_controls`, `test_a_founder_narrowing_on_a_completed_goal_is_recorded_and_it_stays_completed` |
| A goal could ask for a move its mission never runs (the closure world's ladder held `c` only) | `missions.pursued_checks`; `check_goal`, `MissionEngine.request_decision` / `ask_refusal` and `goal_from_mission` require the strategy to advance a pursued check; the closure world's ladder is `[["c"], ["d"]]` | `test_a_goal_may_not_ask_for_a_move_its_mission_never_runs`, `test_the_registered_closure_world_asks_only_for_a_move_its_mission_runs` |
| `--print-only` output rejected by `authorize FILE`; no no-code supersede | `authorize FILE` accepts the printed `{kind: GOAL, body}` shape; `--supersedes GOAL_ID_PREFIX` | `test_the_reviewed_print_only_file_is_what_authorize_signs`, `test_a_goal_is_superseded_without_code` |

Existing tests touched in this stage (reasons in the commit messages): `test_an_executor_claim_never_becomes_goal_evidence`
now asserts on the forged claim's own experience (untrusted, False), because the goal's pull may since have had the
waiting mission re-observe `d`; three negative tests whose intake text named nothing
(`test_a_forged_goal_is_preserved_but_never_woken`, `test_an_unsigned_record_cannot_unmute_or_drop_any_signed_narrowing`
and the `regenerative` closure) now ingest text about the goal so that admission, the restored mute and the signed
stop remain what keeps the goal asleep.

### Known limitations after fix stage 2

- **Lexical relevance.** Intake counts for a goal only when its text names a signed mission id (or its last
  segment), a target base name or a goal subject as whole words; synonyms and paraphrase ("the note file is broken")
  do not wake a goal, and a short or common mission name matches common words. Untrusted text naming a mission on any
  channel can wake its goal: timing only, pulls rate-limited to one per mission per minute (per open body process)
  with one pending at a time while a decision is open, preparation inside the signed cone only. Learned relevance stays a preserved future target (section 4).
- **Preparation scope.** Only static, capability-bound strategies whose exact scope the cone admits run while a
  decision is open; bound (`bind`, `$from_action`) strategies wait for the answer. A sensor deficit or an uncertain
  outcome found while preparing replaces the APPROVAL blocker as it would in the mission's own loop; the APPROVAL
  request stays open and is found again when the loop reaches the strategy.
- **Reopening needs a plan-node observation.** A completed goal reopens only on an attributed observation of one of
  its plan nodes' metrics; a regression of a check that is not a plan node (e.g. `c` for the Mission F goal, whose
  nodes are `d` and N1) leaves it completed, as its desired state still holds.
- **Probe that cannot discriminate.** The reviewer's `test_probe_supersede_has_no_cli_route` still passes: its first
  assertion (re-deriving the identical goal is refused) is intended behaviour, and its last (`--supersedes x` exits 2)
  also holds for the fix's refusal of an unknown prefix. Supersede is proven by `test_a_goal_is_superseded_without_code`.

## Alternatives

- **Do nothing.** Persistent goals stay off the only authenticated body. Rejected: Mission F cannot run.
- **Port egregore into `greg/missions.py`.** One engine, but it deletes or forks a preserved lineage. Rejected.
- **Egregore executes through `office.gate` with binding-minted grants.** A second authority path. Rejected.
- **Ledger-first** (re-verify founder facts at every fold, body mode across five egregore modules, ~2050 LOC).
  Strongest authority model; largest blast radius; its trigger/boot-id scheme collides on reopened bodies and its
  per-tick turn record breaks idle-body anchoring. Grafts 4, 5, 6, 10 taken; P2 deferred.
- **Founder-operation-first** (a gravity block on MISSION, ~2100 LOC). Best founder UX; makes egregore
  classification a precondition for execution and stalls on zero confidence. Grafts 1, 3, 7, 8, 11 taken.
- **Minimal adapter (selected)**, as a reversible experiment on a branch.

## Five-role review (brief)

| Role | Position | Material concern | Recommendation |
|---|---|---|---|
| Builder | Mission F runs end to end on a real body with a real Ed25519 test key, in both orders: with the ask still open, noise on the goal's own channel is silent, meaningful text on it wakes the goal, the mission repairs `c` in cone through the Gate, nothing new is asked and the awaited move does not run; then approve executes once and the bottleneck re-fixes to N1 | goal-level moves must restate a static mission strategy the mission pursues; relevance is lexical | EXPERIMENT |
| Adversary | forged goal, smuggled acceptance, backdated envelope, over-ceiling GOAL, duplicate intent, device-signed GOAL, unsigned un-pause, retired-key GOAL, revoked-device DECISION, forged founder answer, forged executor pass: all refused or not mirrored (tests) | in-process writers can still narrow goals (stop, supersede) and the mission fold still trusts unsigned `decision.answered` (P2) | EXPERIMENT with P2 as a named follow-up |
| Operator | one ledger file; idle body writes nothing; dormant goal writes nothing; faults contained once per reason; one CLI entry | O(commands) signature checks per tick; ledger growth per non-dormant turn | EXPERIMENT; cache by digest if measured hot |
| Beneficiary Representative | the founder signs a pre-filled GOAL from a mission instead of writing JSON; asks keep the section-60 contract and wording screen; a phone can only quiet a goal | attention defaults have no founder-signed quiet hours yet | EXPERIMENT |
| Constitutional Reviewer | intelligence creates no authority: the loop cannot hold a gate, executor or grant on a body; answers come only from signed DECISIONs; building is not activating (nothing runs without a signed GOAL) | the egregore lineage gained a host-detection marker (`greg.founder.enrolled`) | EXPERIMENT |

## Pass 1 and Pass 2 (brief)

Pass 1: the advantage (one authenticated path for goals, missions and asks) becomes a default pathway; it reverses
if goal specs drift from mission strategies, so admission requires exact restatement and a scope-parity test pins the
digest. The disadvantage "two founder-signed objects" is bounded by deriving the GOAL from a signed mission.
Pass 2 (re-attack of the strengthened design): a stray goal record faulting every tick (closed by quarantine); a
supersede faulting every later wake (closed by the router and isolation); a FAULT dropping the waking signal
(closed by cursor-after-success); a phone un-pausing a founder stop (closed by graft 5); a retained device DECISION
outliving revocation (closed by graft 11). Attacked separately from internal metrics: the claimed effect is "the
mission acts sooner on relevant evidence and the founder is asked once", measured on the ledger, not "the goal
advanced".

## Dissent (preserved)

- Adversary: unsigned in-process records can still narrow a goal (stop, revoke, complete it). Accepted: narrowing
  only; since the fix stage the guard restores every signed fact an unsigned record widened (closure, stop, narrowing
  preferences, priority floor) and the views label unsigned stops. Owner: kernel maintainers. Trigger: any narrowing
  record without a signed command observed on a real body.
- Adversary: `MissionBook` folds unsigned `decision.answered` and `mission.registered` (P2). Owner: Alfonso. Trigger:
  the separate fold-time re-verification change.
- Operator (closed by fix stage 2): a goal could not pull a mission blocked on a founder decision. A goal's pull now
  lets a mission awaiting an APPROVAL prepare in cone; the awaited move still waits for the signed answer. Residual:
  missions blocked on other decision kinds (scope renewal, sensor scope, capability) still only wait. Owner: kernel
  maintainers. Trigger: a founder report that a goal woke and nothing happened.
- Evidence Guardian: goal completion is observation-tier (attributed ledger observations), never external
  verification; CMC/VEPMC are unchanged. Threshold: one real consequence under a signed mission, independently
  appraised.
- Constitutional Reviewer: device expiry for retained envelopes was judged at the signed `issued_at`, not acceptance
  time. Partly closed by the fix stage: judged at the recorded `accepted_at` when present (all new acceptances).
  Owner: kernel maintainers. Trigger: a device key compromise drill.

## Evidence

Executable evidence on this branch (exact counts in the commit messages and the implementer report):
`tests/unit/test_greg_goal_gravity.py` (Mission F end to end, the attacks, crash replay, idle body),
`tests/unit/test_greg_goal_gravity_authority.py` (the fix stage's authority and security regressions),
`tests/unit/test_greg_goal_gravity_founder_effect.py` (fix stage 2: the founder-effect regressions),
`tests/unit/test_goal_gravity_body_mode.py` (egregore grafts), the existing egregore and greg suites, and the
`greg-goal-gravity` five closures in `closure/gravity_registry.py` (run by `tests/unit/test_closure.py`). Tier:
IMPLEMENTED / UNIT-TESTED on real temporary bodies with a test key; not SANDBOX-VERIFIED on the founder's body, not
EXTERNALLY VERIFIED, not FOUNDER-ACCEPTED.

## Rollback

Revert the binding and surface commits on this branch. Retained `egregore.*`, `greg.goal.*` and `GOAL` /
`GOAL_CONTROL` command records stay on the ledger as inert data: `MissionBook` ignores them, and nothing else reads
them once `goal_gravity.tick` is gone. Missions keep their own schedule and asks. The egregore grafts (commit 1) can
stay: standalone behaviour is unchanged by them.

## Kill criteria

Regress the binding if any of these is observed:

- a body-hosted loop executes, holds a gate, executor or grant, or any turn record lists an executed move;
- a second ledger file, or a goal ask that is not the engine's deterministic APPROVAL for an exact signed scope;
- an unadmitted (unsigned, forged or retired-key) goal wakes, pulls a mission or asks;
- an `egregore.founder_answer` on a body ledger without a signature-verified DECISION, or `ledger_closure` problems;
- an idle body (no GOAL) appends any record because of Goal Gravity;
- a goal resumes a founder-paused mission, or a device key widens a goal;
- a goal's pull runs the awaited strategy before a signed approve, or any strategy outside the mission's cone;
- a mission no goal is bound to records a pull or a `mission.prepared` (goal-less missions must behave as before).

## Authority impact

- Changes authority: no. The binding issues no grant, opens no ledger, constructs no Gate, writes no
  `decision.requested` of its own and holds no executor; every projection says `execution_authority: none`.
- Founder approval required: yes, for adoption into `main` and for signing any GOAL on a real body.
- Approval state: pending. Approver: Alfonso Lopez.

## Decision outcome

`EXPERIMENT` on branch `gg-binding`; `NEEDS_FOUNDER_DECISION` for adoption.
