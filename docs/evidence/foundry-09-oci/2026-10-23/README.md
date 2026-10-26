# Foundry system 9: hosted OCI evidence

This record supports a **bounded `SANDBOX_VERIFIED`** completion claim for the
restricted-rule container capability only. It does not claim live activation,
full-machine portability, privileged execution, deployment, or VEPMC.

## Acceptance mapping

| Criterion | Evidence |
| --- | --- |
| Same owned source | Run `39984114068`, job `120524216169`, head `fa80ace79eb1ac2cc4bf745918baf5587e1ae3f6`; source SHA-256 values in `hosted-run-39984114068.json`. |
| Identical independent rebuild | The successful hosted proof executed `scripts/ci/prove_oci.py`, which performs two no-cache Buildx builds and raises unless their parsed OCI layouts are equal. |
| Second-environment behavior | The same proof executes six valid/hostile cases in networkless, read-only, non-root, capability-dropped containers and raises unless every result equals host evaluation. Only then does it write `reproduced=true` and `identical_second_environment=true`. |
| Exact hosted conclusion | OCI job and proof step 5 concluded `success`; overall canonical CI was **not** all green because job 1 was cancelled after its timeout. |
| Local deterministic evidence | `foundry/evidence/system-09.json` retains `image_built=false`; `python -m foundry.completion --audit` reruns context packaging and compares both result and SHA-256. |

## Evidence boundary

The artifact metadata identifies immutable artifact `12515337331`, but archive
download returned HTTP 401 and the job-log API returned HTTP 403. No
artifact-internal `report.json`, per-case output, OCI layout, or image digest was
locally inspected. The archive SHA-256 is **not** an OCI image digest and does
not prove artifact contents. These limitations keep the evidence tier at
`SANDBOX_VERIFIED`; they are not silently converted into independent case-level
verification.

The earlier Docker 29 Buildx failure remains negative historical evidence. The
successful run is a later hosted result, not a reason to erase that failure.
System 10 and stronger general-code/full-machine execution remain open.

## Local validation (2026-10-26)

On a native-filesystem worktree, the exact base and changed tree each passed the
focused OCI suite (`7 passed`). The changed tree then passed the complete
Foundry audit:

```text
PASS: 51/55 complete; 0 problem(s)
PARTIAL: 10, 26, 28, 52
```

The completion-contract suite, including its forged/missing-evidence negative
tests, passed `66` tests. Its `27` warnings were third-party Stripe deprecation
warnings. The signed-mission OCI test refuses owned files on `/mnt/agents`
because that mount reports `st_nlink=0`; the same exact source passes on the
native filesystem with `st_nlink=1`. The guard was not weakened.

The first full-audit attempts stopped on missing declared dependencies and two
commissioning child-CI environment failures (`KeyError: 'proposal'`). Those were
inconclusive environment attempts, not Foundry evidence mismatches. Installing
the actual declared packages and exposing them through a native virtual
environment's normal `.pth` site initialization allowed the intentionally
scrubbed child CI to run. Focused system 51 then matched its retained result
hash, followed by the successful full audit above. No project code, fake module,
live provider call, or scrubbing exception was introduced.

These are local exact-tree checks, not hosted CI on the eventual child head,
not an entire-repository test run, and not integration or independent review.

## Recovery

Rebuild locally with `foundry.apply package` and inspect with
`foundry.apply inspect`. The hosted proof removes its disposable builder in
`finally`. Any local rebuild/result/hash mismatch, source drift, or later
contradiction of the hosted evidence restores system 9 to `PARTIAL` with the
failed criterion named. Retain this record and the former gap lineage; stale
success is never reused.
