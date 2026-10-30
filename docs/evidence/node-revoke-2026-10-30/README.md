# NODE_REVOKE and revocable node enrollment (WU-06 part a1), 2026-10-30

Base `66f9d5ac` (WU-05's final head; this branch is stacked on it). Branch `claude/node-revoke-20261030`.

## What changed

Before this change, a node was only a `node.enrolled` row:

- nothing could revoke it;
- the same `node_id` could never be enrolled again, because a second enrollment collided with the first's fact
  identity (`EventError: fact identity greg.node.enrolled reused with different content`);
- its key could be the founder's key or a device key.

Now:

- `greg/founder.py`: `NODE_REVOKE` is a command kind, founder key only. The verifier refuses a device any kind
  outside `DEVICE_KINDS`, whatever its delegation record lists. A device delegated every device kind, or a forged
  delegation record that names `NODE_ENROLL`/`NODE_REVOKE`, cannot sign either. `DEVICE_KINDS` was never narrowed
  in git history, so no delegation that was ever valid is refused.
- `greg/compute.py`:
  - `enroll_node` refuses:
    - a `node_id` that is enrolled and neither revoked nor expired;
    - a key ever enrolled for the founder (rotated-out keys too) or ever delegated to a device (revoked too);
    - another active node's key.
  - `enroll_node` accepts an optional `expires_at`: ISO 8601 with a timezone, later than the command time.
  - Each enrollment is its own fact (`[node_id, command_digest]`), so enrol, revoke and re-enrol works.
  - `revoke_node` refuses an unknown node or one already revoked. It records `node.revoked` with the command
    digest and the enrollment it ended. An expired enrollment may still be revoked, which records it.
  - `node_states` / `active_nodes` are the read-only fold, and an expired node is inactive.
  - The same signed command applied again after a crash returns its retained record.
- `greg/body.py`: exactly one dispatch branch, `NODE_REVOKE` -> `compute.revoke_node`, beside `NODE_ENROLL`.
  No other line changed.
- `greg/cli.py`:
  - `greg node enroll NODE_ID --pubkey HEX --cone CONE.json [--expires-at T] --key K`, added because
    `NODE_ENROLL` had no CLI;
  - `greg node revoke NODE_ID --key K`, signed exactly like `greg device revoke`;
  - `greg node list`, read-only through `observe`.
- `docs/opus-maximus/ONE_GREG_SYSTEM_SPEC.md`: one command-table row.

Consumers of `node.enrolled`: `grep` finds none in `greg/` besides `enroll_node` itself, so the new fold has no
second reader to update. `greg node list` and the enrollment and revocation checks read `node_states`.

## Commands and results

Python `/home/user/venv311/bin/python`. Every run used `PYTHONDONTWRITEBYTECODE=1 ... -B -m pytest -q -p no:cacheprovider`.

| Run | Result |
| --- | --- |
| Fail-before: the final `tests/unit/test_greg_node_revoke.py` copied into a detached worktree of `66f9d5ac`, then the worktree removed | **24 failed, 2 passed**. Both passes are malformed keys that decode to 31 bytes, which the base already refused by length. Highlights: `'NODE_REVOKE' in COMMAND_KINDS` false; a forged delegation naming `NODE_ENROLL` **verified** (DID NOT RAISE); the founder's key and a device key were **accepted** as node keys; enrol-revoke-re-enrol crashed on the fact-identity collision; `greg node` was an invalid choice |
| Pass-after: `tests/unit/test_greg_node_revoke.py` | 26 passed |
| `scripts/ci/check_node_revoke_mutants.py` (scratch copy; the live tree is never mutated) | **25/25 mutants caught**, unmutated PASS, exit 0 |
| Related suites: `test_greg_platform`, `test_greg_founder_and_scope`, `test_greg_founder_tier`, `test_greg_remote`, `test_greg_venture_books`, `test_greg_command_record_shape`, `test_greg_runbook_commands` | 75 passed |
| Related suites: `test_greg_compute_closure`, `test_greg_restore`, `test_greg_restore_fold`, `test_greg_crash_loop_breaker`, `tests/integration/test_greg_device_revocation_process` | 91 passed |
| A real CLI session in separate processes: `greg init`, `founder keygen/enroll`, `node enroll` twice, `run --max-ticks 1`, `node list`, `node revoke` twice, `run --max-ticks 1`, `node list` (test key, scratch home) | `body-2` ACTIVE, then REVOKED. Two refusals recorded: `a node key may not be a key enrolled for the founder or delegated to a device`, and `node body-2 is already revoked`. Accepted: `NODE_ENROLL`, `NODE_REVOKE` |

The full suite was not run (too slow on this shared 4-core host). No timing-sensitive test failed, so none was re-run.

## Limitations

- **The command time for `enroll_node` is this host's clock.** The `NODE_ENROLL` dispatch line passes no clock,
  and the scope forbids touching it before #221. A test clock therefore does not reach enrollment, though
  revocation gets the body's clock. Follow-up: pass `now=now` there once #221 has merged.
- **Key separation is one-directional.** A node key cannot be a founder or device key. `DEVICE_ENROLL` and
  `ROTATE_FOUNDER_KEY` do not yet refuse an active node's key; those checks belong in `greg/body.py` branches that
  #221 touches. Today only a founder-signed command could do it.
- **The light cone's horizon is not folded into node state.** A node whose cone horizon has passed still lists as
  ACTIVE unless its `expires_at` passed. The cone itself refuses any action past its horizon (`LightCone.admits`).
- **Admission, not activation.** Nothing leases work to a node or verifies anything a node signs, so
  `node.run`, receipts and the two-process lease test are part a2. The N8 predicate is also out of scope.
- Every key here is a test key. Nothing is founder-device verified.

## Reality level

- **INTEGRATION-TESTED:** the body, the inbox, the ledger and the CLI in pytest.
- **LOCAL-REAL:** one CLI session in separate processes on this container, with the body's own `greg run` loop and
  a test key.
- **Not done:** no founder key, no second machine, and no node doing work.
