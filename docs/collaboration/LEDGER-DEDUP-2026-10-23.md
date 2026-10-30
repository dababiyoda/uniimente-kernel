# One fewer copy of a signed command on the body ledger — 2026-10-23

Finding (recorded in `INTEGRATION-196-HANDOFF-2026-10-22.md`): a founder-signed mission carrying a 509 KB
cognition request grew the body ledger by 3.2 MB. Its 1 MB spec holds the request twice (a sensor and a
strategy), and the ledger kept the spec three times:

- `greg.command.accepted` stored `body` and also the full signed `envelope`, which already contains that body;
- `greg.mission.registered` stored the validated spec again.

## Measured (`tests/unit/test_greg_large_inline_mission.py`, development seed 5)

| | ledger growth for the mission | `command.accepted` | `mission.registered` |
| --- | ---: | ---: | ---: |
| before (`982168a8`) | 3,241,260 bytes | 2,138,951 | 1,069,551 |
| after | 2,172,544 bytes | 1,070,235 | 1,069,551 |

The spec is 1,068,706 bytes, so the mission now costs about two copies of it, not three (33% less). The test
now asserts growth of at most two spec copies plus 64 KiB; it fails on `982168a8`.

## What changed

- `Body.apply` records `command.accepted` without the top-level `body`. The body is `envelope["body"]`, exactly the
  bytes that were signed (the dropped field was always `env["body"]`).
- `greg.founder.accepted_body(payload)` reads a record of either shape: the envelope's body first, a bare `body`
  only when a record has no envelope. It verifies nothing.
- The only readers of the top-level field were `greg/metrics.py` `founder_tier` and `tier_status` (the
  FOUNDER_TIER attestation check); they now use `accepted_body`. One test read it and now reads the envelope.

Every other reader (the appraiser, the verified fold in `goal_gravity.founder_facts`, `MissionBook`,
`signed_answer`, `signed_mission`, `ledger_closure`, `Body.apply`'s replay check, nonce accounting) already read
`envelope` and its `body`. Signature verification is unchanged and uses the same envelope bytes.

## Compatibility

Append-only stays: no record is rewritten. Records written before this change keep both fields and still read,
replay, verify and appraise. `tests/unit/test_greg_command_record_shape.py` runs the same signed mission (with a
FOUNDER_TIER attestation) through the old writer and the new one, then reopens the body with current code and
checks, for both: the re-applied envelope is ALREADY_APPLIED, the mission is ACHIEVED, `signed_mission_spec`
re-verifies it, the recorded and a fresh appraisal are VERIFIED with the founder signature verified, and the
founder tier holds. The new-shape case fails if `metrics.py` still reads the top-level `body`.

## Not changed, and why

- `mission.registered` still stores the spec. More than twenty readers take `payload["spec"]` directly
  (`MissionBook.fold`, the appraiser, path, tribunal, venture books, settlement, learned routing, seed path, sop,
  organ bridge, metrics). Replacing it with a digest and a reference to the envelope would make each of them
  resolve the accepted command, and the registration would then depend on a second record to be read at all
  (today the appraiser and `signed_mission` compare the two independently, `env["body"] == spec`). That is
  option (b); it would save the second copy, but it is not clearly safe as a minimal change.
- The spec still holds the request twice (sensor and strategy). That is the founder's signed content; GREG does not
  rewrite what was signed.

Tests run: listed in the commit message. Authority delta: none.
