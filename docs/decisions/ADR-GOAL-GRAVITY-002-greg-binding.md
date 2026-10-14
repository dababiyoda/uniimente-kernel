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
   admission  retained GOAL envelope re-verified under the key valid at its ledger position, spec rebuilt byte
              for byte; anything else preserved and quarantined (narrowing only)
   guard      a signed founder stop / change / revoke is restored if an unsigned record undid it
   settle     a signature-verified DECISION reject becomes the goal's route refusal (both lineages remember)
   sense      Gate receipts with the check predicate recomputed, separate-process appraisals, greg.path,
              non-quarantined intake (untrusted); only new or changed evidence
   loop       egregore GoalGravityLoop.turn in body mode: no gate, no executor, no grants (ContractError otherwise)
                awake goal  -> MissionEngine.observe_now for its signed missions (timing only, rate-limited)
                decision    -> MissionEngine.request_decision: the engine's own APPROVAL, exact scope, same id
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
| 8 | Founder-paused missions reported as `paused` (`dormant` kept as alias); `status()` no longer presents missions and goals under one unlabelled key | DONE | `greg/gravity.py::_goals`; `greg/body.py::status` (`missions`, legacy `goals`, `keys`, `gravity`) |
| 9 | Zero confidence with an explicit label when a goal has no world evidence | DONE, scoped to body mode | `egregore/gravity.py::_evidence` (`no_world_evidence`). Applying it to standalone egregore loops breaks three tests that pin that lineage's documented `caller_attested_only` semantics (probe: 3 failed); both lineages are preserved, so the standalone label stays and is honest there |
| 10 | Detective closure: every `grant_dispatch` traces to a `greg.authority.grant_issued` whose `authority_ref` is a verified founder MISSION digest | DONE | `greg/goal_gravity.py::ledger_closure`; `closure/gravity_registry.py::greg_goal_gravity_closures` (evidence closure); projection and morning report |
| 11 | Retained envelopes verify against the founder key enrolled at that ledger position; device revocation and expiry apply to mirrored DECISIONs | DONE | `greg/goal_gravity.py::signed_commands` (ledger order; rotation, enrollment and revocation count only as founder-signed accepted commands) |
| - | Fold signed LIFECYCLE PAUSED/ABANDONED of bound missions into goal preferences (optional) | SKIPPED | A paused mission already yields nothing to a goal: `observe_now` and `request_decision` refuse it, so no pull and no ask; a goal-level notice can still be recorded. Folding would make the binding a second writer of goal preferences from mission facts; revisit if notices for paused missions prove noisy |
| - | Fold-time re-verification of `mission.registered` / `decision.answered` (ledger-first P2) | DEFERRED | A separate hardening scope (it changes every mission fold and fixtures that write `mission.registered` directly). The goal lineage already refuses unsigned answers; the mission lineage does not yet |

Two existing tests were extended, not removed: `test_greg_gravity::test_dormant_goals_wake_only_as_a_founder_proposal`
now asserts the `paused` label and the `dormant` alias; the phone guardrail in `test_greg_platform` adds `GOAL` to the
founder-only set.

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
| Builder | Mission F runs end to end on a real body with a real Ed25519 test key: noise silent, relevant evidence wakes, the bottleneck re-fixes, in-cone repair through the Gate, exactly one ask, approve executes once | goal-level moves must restate a static mission strategy exactly | EXPERIMENT |
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

- Adversary: unsigned in-process records can still narrow a goal (stop, revoke, supersede the founder's goal with a
  quarantined one). Accepted: narrowing only; the guard restores signed stops, not every narrowing. Owner: kernel
  maintainers. Trigger: any narrowing record without a signed command observed on a real body.
- Adversary: `MissionBook` folds unsigned `decision.answered` and `mission.registered` (P2). Owner: Alfonso. Trigger:
  the separate fold-time re-verification change.
- Operator: a goal cannot pull a mission that is blocked on a founder decision; the mission waits for the answer by
  design. Owner: kernel maintainers. Trigger: a founder report that a goal woke and nothing happened.
- Evidence Guardian: goal completion is observation-tier (attributed ledger observations), never external
  verification; CMC/VEPMC are unchanged. Threshold: one real consequence under a signed mission, independently
  appraised.
- Constitutional Reviewer: device expiry for retained envelopes is judged at the signed `issued_at`, not acceptance
  time. Owner: kernel maintainers. Trigger: a device key compromise drill.

## Evidence

Executable evidence on this branch (exact counts in the commit messages and the implementer report):
`tests/unit/test_greg_goal_gravity.py` (Mission F end to end, the attacks, crash replay, idle body),
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
- a goal resumes a founder-paused mission, or a device key widens a goal.

## Authority impact

- Changes authority: no. The binding issues no grant, opens no ledger, constructs no Gate, writes no
  `decision.requested` of its own and holds no executor; every projection says `execution_authority: none`.
- Founder approval required: yes, for adoption into `main` and for signing any GOAL on a real body.
- Approval state: pending. Approver: Alfonso Lopez.

## Decision outcome

`EXPERIMENT` on branch `gg-binding`; `NEEDS_FOUNDER_DECISION` for adoption.
