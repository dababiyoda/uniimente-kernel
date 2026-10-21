# Frozen continuity history (Package 3 subjects)

Byte-identical copies of every continuity artifact pinned by the three subject
bindings of the sealed Package 3 experiment:

| Binding | Where it is pinned | Source commit | Combined sha256 |
|---|---|---|---|
| `package3-original` (FROZEN) | `evolution/repair/spec.py` | `cb234faf…` | `c1d621a8…` |
| `sr001-boundary-0.1.1` | `evolution/repair/subjects.py` SR001 | `3e059c20…` | `5594003e…` |
| `sr002-0.1.0` | `evolution/repair/subjects.py` SR002 | `07af5758…` | `7755bdc6…` |

Twelve artifacts each (the five constitutional documents, the three authority
documents, the three identity registries and `policy/consequence_gate.py`),
sixteen distinct byte strings in all.

## Layout

`objects/<sha256>` holds exactly the bytes whose sha256 is the file name.
Content addressing is deliberate: the three bindings share most artifacts, and
a copy named `constitution.ucl` or `consequence_gate.py` would be a second
Constitution or a second Gate to `scripts/ci/check_authority_singleton.py`.
`MANIFEST.json` lists every binding, its source commit, a reachable witness
commit carrying the same bytes, and which paths each object served.
`.gitattributes` turns off end-of-line conversion for the objects.

## How the copies were made

For each binding, each artifact was read with
`git show <source_commit>:<path>`, hashed, compared with the pinned digest and
only then written. SR-002's source commit `07af5758…` is not in this
repository's object store; it was fetched by sha from the origin repository into
a scratch repository and read there. Its bytes are also byte-identical at
`d7c235ae…` (#103, the merge that recorded the SR-002 binding), which is an
ancestor of this branch, so the provenance test can run anywhere the history is
checked out. No pinned digest was changed, re-measured or moved.

## What reads this, and what does not

Read here (history): `SubjectBinding.matches()` and `.fingerprint()` with no
root, and `evolution.repair.harness.continuity_fingerprint()` with no root, so
the sealed experiment's continuity gates, its `continuity.before/while_absent/
after` fields and the SR002 dependent tests reproduce exactly as they did at
freeze time.

Read live, deliberately, because the experiment is about the running
institution: the measurement corpus (`organs/`, `contracts/`), the candidates,
the detector, the runtime disable, the on-disk original linker, the
Constitution compiled while the function is absent, shutdown, and the twelve live
artifacts compared only with themselves across one run. The run record carries
this split in `readings`.

Still live and unchanged here: `evolution/migration/harness.py` compares the
live tree with SR-001 and has done so, non-matching, since SR-002; it is not part
of this change.

## This is not the live tripwire

This store will keep reproducing forever, by construction. It says nothing
about whether the live Constitution is intact. That question belongs to
`governance/integrity/` (`python -m governance.integrity --check`), which reads
the live tree and accepts a change only under an Ed25519 authorisation signed by
an enrolled founder key. Neither reading may be presented as the other.

A frozen copy that no longer hashes to its name fails every binding that reads
it (`tests/unit/test_repair_continuity_history.py`). It is never repaired from
the live tree.
