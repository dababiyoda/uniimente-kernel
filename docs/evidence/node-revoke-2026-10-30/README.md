# NODE_REVOKE and revocable node enrollment (WU-06 part a1), 2026-10-30

Base `66f9d5ac` (WU-05's final head; this branch is stacked on it). Branch `claude/node-revoke-20261030`.
Round 1 ended at `e19c172c`. Round 2 fixes six review findings (below).

## What changed

Before this change, a node was only a `node.enrolled` row:

- nothing could revoke it (`NODE_REVOKE` was an unknown command kind);
- a second `NODE_ENROLL` for the same `node_id` was refused, always, because it reused the first enrollment's
  fact identity (`EventError: fact identity greg.node.enrolled reused with different content`, a `ValueError`
  the body records as a refusal). So a `node_id` could never be enrolled twice;
- its key could be the founder's key, a device key, or the body's own identity key;
- `node_id` had no length bound.

Now:

- `greg/founder.py`: `NODE_REVOKE` is a command kind, founder key only. The verifier refuses a device any kind
  outside `DEVICE_KINDS`, whatever its delegation record lists. A device delegated every device kind, or a forged
  delegation record that names `NODE_ENROLL`/`NODE_REVOKE`, cannot sign either. `DEVICE_KINDS` was never narrowed
  in git history, so no delegation that was ever valid is refused.
- `greg/compute.py`:
  - `enroll_node` refuses:
    - a `node_id` that is enrolled and neither revoked nor expired;
    - a `node_id` outside 1..128 characters, or equal to this body's own `body_id`;
    - a key ever enrolled for the founder (rotated-out keys too) or ever delegated to a device (revoked too);
    - this body's own identity key (round 2). The check derives `body_id` from the key the way `init_body` does
      and compares it with the `body_id` the ledger recorded at founder enrollment and at each boot;
    - another active node's key.
  - `enroll_node` accepts an optional `expires_at`: ISO 8601 with a timezone, later than the command time.
  - Each enrollment is its own fact (`[node_id, command_digest]`), so enrol, revoke and re-enrol works.
  - `revoke_node` refuses an unknown node or one already revoked. It records `node.revoked` with the command
    digest and the enrollment it ended. An expired enrollment may still be revoked, which records it.
  - `node_states` / `active_nodes` are the read-only fold, and an expired node is inactive. A revocation by a
    restore ends an enrollment like the founder's and lists as `revoked_by_restore`.
  - The same signed command applied again after a crash returns its retained record.
- `greg/recovery.py` (round 2): `restore_body` voids every node enrollment not already revoked, active or expired,
  as it already voided device delegations. Each is recorded as `node.revoked` (`by: restore`). The restore report
  lists them under `voided.node_enrollments` and asks the founder for `NODE_ENROLL again for each node still
  trusted`.
- `greg/lightcone.py` (round 2): `LightCone.from_dict` refuses a `budget_usd` beyond float range with
  `ScopeError`. Before, `float(10**400)` raised `OverflowError`, which no ingest path catches, so one founder-signed
  `NODE_ENROLL` or `MISSION` with such a budget stopped the running body on every restart. Mission, appraisal,
  Goal Gravity and node light cones all share this path.
- `greg/body.py`: exactly one dispatch branch, `NODE_REVOKE` -> `compute.revoke_node`, beside `NODE_ENROLL`.
  No other line changed.
- `greg/cli.py`:
  - `greg node enroll NODE_ID --pubkey HEX --cone CONE.json [--expires-at T] --key K`, added because
    `NODE_ENROLL` had no CLI;
  - `greg node revoke NODE_ID --key K`, signed exactly like `greg device revoke`;
  - `greg node list`, read-only through `observe`. Round 2 tests it while a `Body` holds the ledger's writer lock.
- `docs/opus-maximus/ONE_GREG_SYSTEM_SPEC.md`: one command-table row.

Consumers of `node.enrolled`: `grep` finds none in `greg/` besides `enroll_node` itself. `greg node list`,
the enrollment and revocation checks and the restore read `node_states`.

## Review findings, round 2

| Finding | Reproduced at `e19c172c` | Fix |
| --- | --- | --- |
| F1: a restore brought back a node revoked after the backup as ACTIVE | yes: `voided` had no nodes; `body-2` ACTIVE after restore | restore voids every unrevoked enrollment |
| F2: the body's own identity key was accepted as a node key | yes: `APPLIED` | refused, and so is `node_id` == this body's id |
| F3: a light cone with budget `10**400` crashed the running body | yes: `tick` raised `OverflowError`, file left in `inbox/` | `ScopeError`; both commands go to `rejected/` and the body runs on |
| FID-1: round 1 said re-enrolment "crashed" | yes: it was a recorded refusal | wording corrected above |
| FID-2: `node_id <= 128` was untested | yes: mutant survived | 129- and 128-character cases, two mutants |
| FID-3: `greg node list` read-only was untested | yes: mutant survived | list run under a held `Body`, one mutant |

## Commands and results

Python `/home/user/venv311/bin/python`. Every run used `PYTHONDONTWRITEBYTECODE=1 ... -B -m pytest -q -p no:cacheprovider`.

| Run | Result |
| --- | --- |
| Fail-before at the base: the round-2 `tests/unit/test_greg_node_revoke.py` in a detached worktree of `66f9d5ac`, then removed | **29 failed, 2 passed**. Both passes are malformed keys that decode to 31 bytes, which the base already refused by length. Highlights: `NODE_REVOKE` is an unknown kind; a forged delegation naming `NODE_ENROLL` **verified**; the founder's key, a device key and the body's own key were **accepted** as node keys; a 129-character `node_id` was accepted; a second `NODE_ENROLL` for `body-2` was refused with the fact-identity `EventError`, not the intended message; `test_enrol_revoke_re_enrol_is_allowed` fails earlier, on `KeyError: 'expires_at'`; the cone overflow raised `OverflowError`; `greg node` was an invalid choice |
| Fail-before at round 1: the round-2 test file in a detached worktree of `e19c172c`, then removed | **3 failed, 28 passed**: the own-identity-key test (DID NOT RAISE), the restore test (`KeyError: 'node_enrollments'`), the cone-overflow test (`OverflowError`) |
| FID-2/FID-3 mutants at `e19c172c`: each run against round 1's test file, then round 2's | both **SURVIVED** round 1's 26 tests; both **CAUGHT** by round 2's |
| Pass-after: `tests/unit/test_greg_node_revoke.py` | 31 passed |
| `scripts/ci/check_node_revoke_mutants.py` (scratch copy; the live tree is never mutated) | **35/35 mutants caught**, unmutated PASS, exit 0 |
| Related suites: `test_greg_restore`, `test_greg_restore_fold`, `test_foundry_systems`, `test_greg_founder_and_scope`, `test_greg_budget_observation`, `test_greg_paid_scope` | 111 passed |
| Related suites: `test_greg_platform`, `test_greg_founder_tier`, `test_greg_remote`, `test_greg_venture_books`, `test_greg_command_record_shape`, `test_greg_runbook_commands`, `test_greg_compute_closure`, `test_greg_crash_loop_breaker`, `tests/integration/test_greg_device_revocation_process`, `test_greg_capabilities` | 155 passed |
| Round 1: a real CLI session in separate processes: `greg init`, `founder keygen/enroll`, `node enroll` twice, `run --max-ticks 1`, `node list`, `node revoke` twice, `run --max-ticks 1`, `node list` (test key, scratch home) | `body-2` ACTIVE, then REVOKED. Two refusals recorded: `a node key may not be a key enrolled for the founder or delegated to a device`, and `node body-2 is already revoked`. Accepted: `NODE_ENROLL`, `NODE_REVOKE` |
| Round 2: a real CLI session in separate processes: `greg init`, `founder keygen/enroll`; `node enroll` of `body-2`, of `body-3` with the body's own key from `body.json`, of `body-4` with `budget_usd` 10**400; `run --max-ticks 1`; `node list`; `foundry seed`; `node revoke body-2`; `run --max-ticks 1`; `node list`; the home moved away; `foundry restore` into the empty home; `node list` (test key, scratch home) | `body-2` ACTIVE, then REVOKED. Both bad enrollments refused and the body ran on (inbox empty): `a node key may not be this body's own identity key`, `ScopeError: budget must be finite and nonnegative`. The restore from the seed taken while `body-2` was ACTIVE reported `voided: ['body-2']` and `NODE_ENROLL again for each node still trusted`; the restored body lists `body-2` REVOKED, by the restore |

The full suite was not run (too slow on this shared 4-core host). No timing-sensitive test failed, so none was re-run.

## Limitations

- **The command time for `enroll_node` is this host's clock.** The `NODE_ENROLL` dispatch line passes no clock,
  and the scope forbids touching it before #221. A test clock therefore does not reach enrollment, though
  revocation and the restore get the body's clock. Follow-up: pass `now=now` there once #221 has merged.
- **Key separation is one-directional.** A node key cannot be a founder, device or body identity key.
  `DEVICE_ENROLL` and `ROTATE_FOUNDER_KEY` do not yet refuse an active node's key; those checks belong in
  `greg/body.py` branches that #221 touches. Today only a founder-signed command could do it.
- **The body's own key is recognised through its `body_id`,** a 64-bit digest of the key, read from the ledger's
  founder-enrollment and boot records. A different key with the same 64-bit digest would also be refused (a false
  refusal, never an acceptance). The test reads the real key from `body.json`, so a change to how `init_body`
  derives `body_id` fails it.
- **A restore voids nodes only when it runs through `restore_body`.** A body restored by the code before round 2
  keeps its old enrollments.
- **The light cone's horizon is not folded into node state.** A node whose cone horizon has passed still lists as
  ACTIVE unless its `expires_at` passed. The cone itself refuses any action past its horizon (`LightCone.admits`).
- **Admission, not activation.** Nothing leases work to a node or verifies anything a node signs, so
  `node.run`, receipts and the two-process lease test are part a2. The N8 predicate is also out of scope.
- Every key here is a test key. Nothing is founder-device verified.

## Reality level

- **INTEGRATION-TESTED:** the body, the inbox, the ledger, the restore from a seed and the CLI in pytest.
- **LOCAL-REAL:** two CLI sessions in separate processes on this container, with the body's own `greg run` loop,
  `greg foundry seed` / `greg foundry restore` and a test key.
- **Not done:** no founder key, no second machine, and no node doing work.
