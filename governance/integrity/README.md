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
* Removing a key retires its signatures: authorizations it signed stop
  counting, so the founder re-signs them with a current key.

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
  closes with Alfonso's own commit.
* It reports. It does not block, ratify or grant: CI fails and a human reads
  why. Authorizing a digest here changes no grant, policy or Gate behaviour.
