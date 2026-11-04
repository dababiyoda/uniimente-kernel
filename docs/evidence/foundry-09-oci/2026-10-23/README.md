# Foundry 9 — owned OCI completion evidence

## Bounded disposition

System 9 is `COMPLETE` at `SANDBOX_VERIFIED` for the owned restricted-rule capability only. This is not a full-machine, general-code isolation, deployment, or external-outcome claim. VEPMC remains 0 and no authority is created.

Two different evidence forms close the two acceptance criteria:

| Acceptance criterion | Evidence | Boundary |
|---|---|---|
| Reproducible OCI image with pinned inputs | Exact-head hosted run `39984114068`, job `120524216169`, proof step 5 succeeded. The inspected `scripts/ci/prove_oci.py` resolves immutable base and builder addresses, performs two independent no-cache Buildx builds, and exits nonzero unless their parsed OCI layouts are identical. | The local Foundry exercise packages only a context and continues to return `image_built: false`. It is not presented as an image build. |
| Identical capability execution in a second environment | The same proof step succeeded. The script compares six valid and hostile container results with host evaluation and cannot reach success unless all six match. | Per-case output and the artifact-internal `report.json` were not locally inspected. The successful exact-head job is the execution evidence, not a claim that this session reran Docker. |

The machine-readable record is `hosted-run-39984114068.json`. The local reproducible record is `foundry/evidence/system-09.json`; `python -m foundry.completion --audit` re-derives that local result and hash. Hosted CI remains responsible for rerunning the real image proof on later heads.

## Local validation on 2026-10-26

- The exact-base and changed-tree `tests/unit/test_greg_oci.py` suites each passed **7/7** in a native-filesystem worktree. The working mount's `st_nlink=0` refusal is retained in the deliberation rather than hidden or mislabeled as a project regression.
- The changed-tree full `python -m foundry.completion --audit` completed: **`PASS: 51/55 complete; 0 problem(s)`**. Systems **10, 26, 28, and 52 remain PARTIAL**. This local audit is neither hosted CI on a child head nor integration.
- `tests/unit/test_foundry_systems.py` passed **66/66** tests. Its 27 Stripe deprecation warnings are retained as warnings, not rewritten as failures or silent success output.
- Earlier attempts were inconclusive environmental stops at missing declared packages. Commissioning also failed before its scrubbed child CI could see the target-only pytest installation. A temporary native virtual environment supplied the actual declared packages without changing the repository or weakening environment scrubbing; the focused commissioning rerun then matched its retained result hash exactly.

## Exact hosted identity

- Source head: `fa80ace79eb1ac2cc4bf745918baf5587e1ae3f6` on #196's branch.
- OCI job: `120524216169`, completed `success` from `2026-10-23T16:18:41Z` to `2026-10-23T16:19:46Z`.
- Proof step: `Build immutable owned capability twice and run second environment`, completed `success`.
- Artifact: `owned-oci-capability-evidence`, ID `12515337331`, 94,599,696 bytes.
- Artifact archive metadata digest: `sha256:b09d8597f3cf50e701ebdd30e51860b1535c28ce8a37414630390f65a13e97da`.
- Artifact expiration metadata: `2026-11-22T16:19:40Z`; unexpired when observed.

The archive digest identifies GitHub's uploaded artifact. It is not an OCI image digest and does not prove that the archive contents were inspected.

## Retrieval failures and negative evidence

- Artifact archive download returned **HTTP 401 Unauthorized**. No archive, internal report, image digest, OCI layout, or case result was inspected locally.
- The job-log API returned **HTTP 403 — “Must have admin rights to Repository.”** No raw log was obtained.
- The public job page says **“Sign in to view logs.”** It nevertheless confirms the OCI job succeeded on October 23, 2026 in 1m 5s; it supplies no case-level output.
- Overall Canonical CI is **not** represented as green: jobs 2–9 succeeded, while job 1 (`Kernel and organ tests`) was cancelled after timeout.
- Earlier run `70a89457` failed the OCI job under Docker 29/containerd image-ID semantics. The manifest-digest compatibility fix is present at the exact head used here; the failure remains lineage, not a hidden result.
- The previous PARTIAL gap, paused privileged-runtime work, and full-machine/general-execution limitations remain in `state_lineage` in `foundry/completion.yaml`.

## Recovery and review trigger

Rebuild local context from reviewed owned bytes with `foundry.apply package`; `foundry.query inspect` rejects changed or incomplete context. The hosted proof removes its disposable builder in `finally` and pushes no image.

If a later local reproduction, immutable rebuild, or host/container comparison fails, restore system 9 to `PARTIAL`, name the failed criterion, and retain this record. Do not reuse stale success. Inspect the artifact report/raw evidence or obtain a fresh independently reviewed hosted proof before elevating beyond `SANDBOX_VERIFIED`.

System 10, full GREG and organ dependency images, general source admission, live activation, founder-device acceptance, and every VEPMC/real-world gate remain separate obligations.

## Receiver verification, 2026-10-28

The integration owner of #196 (session `session_01FBS4KNJR59nSbdGbxo8Mbx`) read the raw log of job `120524216169` through the GitHub job-log API, which this account can reach. The proof step printed `{"reproduced": true, "image": "sha256:cb1a0359804fcb3982c1ceabd00e54070900a4fe461a2e518a5383bc813bc4b0", "cases": 6}`. `scripts/ci/prove_oci.py` prints that line only after both no-cache layouts compare equal (it raises `OCI independent rebuild differs` otherwise) and all six container results equal host evaluation (it raises `container result differs` otherwise). The artifact archive itself was not downloaded, so the per-case `report.json` remains uninspected; the tier stays `SANDBOX_VERIFIED`. Locally on the adopted tree: `tests/unit/test_greg_oci.py` and `tests/unit/test_foundry_systems.py` 73 passed; `python -m foundry.completion --audit` PASS, 51/55 complete, 0 problems.
