# tools/collaboration_protocol/

The founder's collaboration-protocol validator for deliberation records, vendored unchanged from the skill
`install-recursive-founder-intent-collaboration-protocol`. Provenance and hashes are in `PROVENANCE.json`.

```bash
python tools/collaboration_protocol/scripts/validate_deliberation.py docs/collaboration/deliberation-<name>.json
```

It fails closed on fewer than five roles, missing do-nothing or competing alternatives, anything other than exactly
two strengthening passes, a Pass-1 disadvantage with no disposition, unhandled dissent, missing residual risks,
invalid authority handling or missing rollback, and on a decision other than exactly one of RETAIN, REGRESS, KILL,
DEFER, EXPERIMENT or NEEDS_FOUNDER_DECISION.

`tests/unit/test_deliberation_records.py` runs it over every deliberation record in the tree (directive ask S65.A1).
Records written before this check, which it refuses, are listed there with the reason. That list only shrinks.
