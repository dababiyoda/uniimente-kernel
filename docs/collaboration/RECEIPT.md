# Collaboration receipt v2

Copy the block below into the existing PR body. Replace placeholders with facts;
never invent an owner, acknowledgment, source read or test. Keep exactly one block.
This version consolidates #95's checker and adds coordination declarations. V1
remains historical evidence; it does not satisfy the v2 check.

Read AGENTS.md at the current PR head after each push. Record the guide's full
commit in both its URL and read_set. The PR event's repository/base/head must
match. For file claims use exact repo-relative paths or clearly labeled directory
prefixes; list shared interfaces separately. Inspected refs must include relevant
open work and the board, even when the result is no overlap. `split` requires the
counterpart's real acknowledgment references; `blocked` cannot become non-draft.
Recheck UTC syntax is validated, but expiry is a worker responsibility and never
permits stealing another worker's files. An integration owner may be `unassigned`;
do not merge until the destination and applicable review are acknowledged.

````text
<!-- uniimente:receipt -->
```json
{
  "version": 2,
  "repository": "dababiyoda/<repo>",
  "base_sha": "<40-character current PR base SHA>",
  "head_sha": "<40-character current PR head SHA>",
  "protocol_ref": "https://github.com/dababiyoda/uniimente-kernel/blob/<40-character guide SHA>/docs/collaboration/START_HERE.md",
  "intent_refs": ["<intent ID or source>"],
  "read_set": [
    {"path": "AGENTS.md", "revision": "<current PR head SHA>"},
    {"path": "<same protocol_ref URL>", "revision": "<guide SHA>"}
  ],
  "scope": "<bounded outcome>",
  "classification": "lightweight",
  "deliberation_ref": null,
  "coordination": {
    "task_ref": "<existing issue/PR URL>",
    "session_id": "<actual opaque worker/session ID; shared GitHub login is insufficient>",
    "files": ["<repo-relative path or directory prefix>"],
    "interfaces": [],
    "recheck_at": "<next recheck in YYYY-MM-DDTHH:MM:SSZ>",
    "overlap": {
      "status": "clear",
      "inspected_refs": ["https://github.com/dababiyoda/uniimente-kernel/issues/96", "<relevant open work inspected>"],
      "acknowledgment_refs": []
    },
    "integration": {
      "repository": "dababiyoda/<repo>",
      "branch": "<agreed destination>",
      "base_sha": "<40-character destination SHA>",
      "owner": "unassigned"
    }
  },
  "validation": [{"command": "<actual command/check>", "result": "not_run", "evidence": "<result or reason>"}],
  "limitations": ["<unknown or unverified claim>"],
  "rollback": "<scoped reversible steps preserving evidence>",
  "handoff": {
    "owner": "unassigned",
    "next_action": "<specific next action>",
    "stop_condition": "<boundary>",
    "acknowledgment": {"status": "pending", "receiver_session": null, "reference": null}
  },
  "review": {"status": "pending", "reference": null}
}
```
<!-- /uniimente:receipt -->
````

The outer text fence is explanatory; paste the markers and inner JSON fence only.
`integration.branch` names the destination the work is proposed into (a PR's base), not the branch
that carries the work; the PR's head branch already names that.
Standard/constitutional changes need a deliberation_ref and recorded completed
review before becoming non-draft. Review and receiver acknowledgment are separate:
a reviewer need not become the next implementer. A receiver may remain pending;
accepted requires another actual session and a verifiable acknowledgment reference.
No timestamp, review link or passed check authenticates the declaration.

For an unresolved collision, set overlap.status to `blocked`, retain the other
worker's task in inspected_refs, leave acknowledgment_refs empty, and make the
next action obtaining a split. Do not edit the contested files while waiting.
After the counterpart acknowledges, use `split`, link that acknowledgment, and
claim only the agreed files/interfaces. This acknowledgment is not code review.

For a handoff awaiting a receiver, keep acknowledgment.status `pending` and
reference null. Change to `accepted` only after another actual session has
acknowledged the exact source head; record its ID and acknowledgment reference.
If a source is unavailable, record the failed access in limitations/validation;
do not fabricate a read_set entry. Choose a real next recheck time, not a copied
timestamp from a prior receipt.

Run the exact validator tests with:

```sh
python3 tests/unit/test_collaboration_receipt.py
```

No runtime dependencies or repository runtime import are needed. Tests execute
only the reviewed inline validator, which is the single implementation shared by
consumers. Old receipts and negative results remain inspectable in prior commits.
