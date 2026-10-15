# governance/integrity — live constitutional integrity

The live half of CONTRADICTION-0002 Option A
([FOUNDER-RULING-2026-08-23](../../docs/deliberations/FOUNDER-RULING-2026-08-23-infinite-goal-chase.md)):
"a separate live constitutional-integrity mechanism whose purpose is to detect
unauthorized changes to constitutional/authority artifacts. Do not use the
historical experiment as the live tripwire."

The historical half is `evolution/repair/continuity/`: frozen copies that let
the sealed Package 3 experiment reproduce. Neither reading stands in for the
other.

## What is checked

`python -m governance.integrity --check` reads the live tree.

| Exit | Meaning |
|---|---|
| 0 | every protected artifact equals its authorized digest |
| 1 | at least one finding; each is named with the founder's exact steps |
| 2 | the record of what is authorized is unsound; no verdict is given |

Protected (`manifest.json`): the twelve SR-002 continuity artifacts
(`constitution/*.ucl` ×5, `authority/*.yaml` ×3, `identity/*.yaml` ×3,
`policy/consequence_gate.py`) with the SR-002 founder-ratified digests as
baseline, plus `founder-keys.json`. A new `.ucl` in `constitution/` or `.yaml`
in `authority/` or `identity/` that nothing authorized is an
`UNGOVERNED_ADDITION`.

The digest an artifact is authorized to have today is the baseline replayed
through `authorizations.json`. Each record is an Ed25519 envelope of kind
`INTEGRITY_AUTHORIZE` (artifact, previous digest, new digest, reason,
`issued_at`, nonce, scope `uniimente-kernel/governance/integrity`) signed by a
key listed in `founder-keys.json`. A record that does not start from the
current authorized digest, reuses a nonce, names another scope or kind, carries
extra fields, or was not signed by an enrolled key makes the record unsound.

**Only a signature by an enrolled founder key authorizes.** A path, a document
reference, a caller string, a hash or a workflow's text never does
(REPOSITORY_RATIONALIZATION_PLAN: "do not import amendment by caller string";
FOUNDER_INTENT_LEDGER SR-INTENT-3).

## Founder keys

`founder-keys.json` is committed empty. No key is invented; no test key is
committed (tests generate keys in temporary directories).

* Initial enrollment is a founder act: Alfonso commits his own public key as
  `genesis`. That is trust on first use, the same model `greg/founder.py`
  states; the check prints the enrolled key ids on every run.
* After that, the key set changes only by an `INTEGRITY_KEYS` record signed by
  a key already listed, which names the digest of the key set it changes.
* Authorizations are verified against the current key set, so a removed
  key's signatures stop verifying and the record becomes unsound. Because
  the record is append-only (below), `keys --remove` refuses to remove a key
  that signed an authorization on record. To rotate, add the new key and stop
  signing with the old one. Revoking a compromised key whose signatures are
  on record is not supported in record version 1; it is a founder decision.

## The records only grow

A record file cannot remember its own past, so in a git checkout the check
reads every committed version of `founder-keys.json` and
`authorizations.json` reachable from HEAD (`git rev-list --full-history`,
`git cat-file`; plumbing only, no hook, filter or repository code runs, and
`GIT_*` variables are ignored):

* once a genesis has been committed, it never changes;
* no committed key change or authorization is removed or reordered (each
  committed list must stay a subsequence of the current one, so two branches
  that each appended a signed record can merge in either order).

A violation makes the record unsound (exit 2), and no signature can authorize
a rewrite. This closes two holes the files alone cannot see: an edited
genesis before the founder's first signature (nothing else in the file
depends on it yet), and a dropped authorization that makes bytes he later
superseded read as authorized again. A shallow checkout in which a record
file already exists at the shallow boundary is refused, so CI job 3 checks
out full history (`fetch-depth: 0`). Outside a git checkout (an export, a
test tree) the history is not checked and the report says so.

Keys are those `python -m greg founder keygen` makes. Key ids and canonical
JSON follow `greg/founder.py` and `egregore.contracts` exactly (asserted by
test). The signing domain differs from GREG's, so a GREG command cannot be
replayed as an integrity record or the reverse.

## Founder steps

On a device that holds the founder key, in a checkout of the branch:

```
python -m greg founder keygen --key ~/.greg-founder.pem          # once; or reuse the GREG founder key
python -m governance.integrity enroll --key ~/.greg-founder.pem --label alfonso
git add governance/integrity/founder-keys.json && git commit     # your commit, once
python -m governance.integrity authorize --artifact <path> --sha256 <digest> \
    --key ~/.greg-founder.pem --reason "<why>"
git add governance/integrity/authorizations.json && git commit
python -m governance.integrity --check                           # exit 0
```

`authorize` refuses unless the digest is the one on disk, so the signature
covers exactly the bytes reviewed. To reject a change instead, restore the
artifact to its authorized digest. The `--check` output prints these steps with
the exact path and digest for each finding.

## Trust boundary, stated plainly

* The check imports only the standard library and `cryptography`: it runs none
  of the code it judges (not the Gate, not `policy.engine`, not GREG, not the
  sealed experiment). Asserted by test.
* It cannot authenticate its own code, `manifest.json` or the CI step. Edits to
  those are visible in review, and a test ties the manifest baseline to the
  SR-002 digests and to git at the SR-002 witness commit `d7c235ae`.
* Before a founder key is enrolled, replacing the empty key file is
  indistinguishable from enrollment. That is the trust-on-first-use window; it
  closes with Alfonso's own commit, after which the committed history pins
  his genesis. The check cannot tell who made a commit: a git author string
  authenticates nobody, so the first enrollment is reviewed as his.
* The history is only as good as the history: someone who can rewrite the
  branch itself (force-push) can rewrite the record's past. Branch protection
  and review cover that, not this check.
* It reports. It does not block, ratify or grant: CI fails and a human reads
  why. Authorizing a digest here changes no grant, policy or Gate behaviour.
