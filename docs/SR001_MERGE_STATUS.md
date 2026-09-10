# SR-001 authorized adoption — 2026-09-10

The founder directed “Yes merge and push” and “Continue until done” after the bounded adoption packet. This authorizes development-branch adoption; it does not turn missing evidence into a pass or activate the institution. The earlier HOLD recommendation and all negative evidence remain in SR001_ADOPTION_DECISION.md. This is an adoption record under the existing decisions, not another strengthening pass.

## Reconciliation and publication

Shell Git had no write credentials. The connected GitHub API published tree-identical commits; new commit IDs reflect API commit metadata, not changed source. No force update was used. The original local commit bundles remain in the handed-off packet.

| Reviewed local commit | Published counterpart | Verified tree |
| --- | --- | --- |
| Kernel 671606777c2dc9c712d92ecb5711e20a0a7ce075 | aaf791f3c87da733f723dc6ee7ff8af5e55f74ec | bbd199ddce22d297e6cd7584e527eabe50ecc528 |
| Kernel 94c18d2a20cb92a8d3d5ce5f3b2a1a83ff3d0752 | 1397ff98cdda94bbe6bf978ccc546056c2ab5a18 | 7fb430633571d6605cbe0caee0a8a9013f863ec2 |
| Kernel aac9d1a10946732b0265bb8cc3974f16519d2564 | 1cda7160978522829615e499f3a0281c55e3001d | caa21103dcd7d2a445e536492c49ec624956c0fa |
| DALEOBANKS 4448825356431dd2cd656cf4041b564a2419d17d | 3d5e402d206be59bc16efc70b66c492a70797f71 | 6bc8d12bd00dc36bc083964ed7305acafc7ccbf3 |
| DALEOBANKS 9e00e252501c47ef765f10b1e18379c090164f14 | 2f81e9c5489aa1c029e56c9be774b218499cda2d | 870de8469e00e4f95ff55cb7de740a55862bf116 |
| WMI authentication merge 8249770 | 965e597488a1a01e5922ea1647c11611ba0329c0 | 5c3510033cff075011dc8310412bb7cbdea07cc0 |
| WMI c828f72ac08444ba4f31e97435a8a7b4f139a4f6 | 1b9a386ae3ba542072181399dfc0557d1bc7eaf3 | 4c62456f5b08fe80a0611983e4666f3c2e14798a |

Kernel publication initially refused a non-fast-forward update: remote 4999acff1a69502c05af455fbccfca380cad18ee arrived during this work. It is retained as an ancestor, including its strict timestamp schemas, canonical adapter validation and additional negative controls. Local merge de64097 reconciles it. Experimental subject hashes have one owner in evolution/repair/subjects.py, with compatibility exports in evolution/compatibility.py. The original frozen repair entry point still requires an explicitly selected current subject. The retained-source W2 fixture rollback is used by the adversarial integration test; the data-only W0 conversion remains separately bounded and tested. Original experiment seals, tests and counterevidence remain intact.

## Evidence and dependency order

- Current-main Kernel composition: 556 offline passes before concurrent work; reconciled composition: 574 offline passes. Final subject-record correction: 47 focused passes. The new tests do not replace the original 17 dispositions.
- DALEOBANKS broad suite: 324 passes / 9 warnings with installed package 0.1.2 under inherited seccomp no-network isolation.
- WMI broad local suite: 128 passes / 2 visible socket-EPERM failures / 429 warnings with installed package 0.1.2. The two failures are the preserved exact-CMD TCP and producer/consumer TCP tests. No skip or guard removal.
- WMI 0.1.1 published CI run 34466777810: 128 tests-only passes / 6 warnings; Ruff reports 2,099 observations under the unchanged non-blocking lint step. This is distinct from the original 2,100 inventory, original 129-root/127-CI comparison, and the later 0.1.2 run recorded on PR35.
- One local attempt included the WMI repository in child PYTHONPATH and failed producer import (127 passes / 3 failures). Rerunning with only installed dependencies and the explicit producer source gives the retained 0.1.2 result above. An earlier focused 0.1.1 rerun also passes. This environment failure is preserved, not silently counted green.
- Initial package build interpreter lacked pip; the primary interpreter built and installed 0.1.2 with --no-index, --no-deps, --no-build-isolation under the same OS isolation. All 28 installed source files equal pin 4999acff and current source.

WMI #33 is merged at 829db6f7a763060bae6f56efdfd7e2a545757e36 after successful CI 34422276294. Remaining order: Kernel #98, DALEOBANKS #77, then WMI #35 (retargeted to main after #33). Exact final heads, check runs and merge commits are recorded in those PRs; no claim of those merges is made before GitHub confirms them.

## Remaining boundaries

No Docker facility exists here; ASGI/subprocess and GitHub CI results are not an image claim. Ordinary GitHub CI is not the independently isolated offline runner. Independent review remains outstanding and is explicitly not claimed by this founder-directed development adoption. Lint debt remains visible, with no threshold reduction. No service, deployment, production credential, founder authentication, external business effect or authority expansion is authorized.

The #93/#94 composition map and founder-loop-entry-gate.json remain PREPARED_NOT_RUN: persistent obligations, a durable autonomous trigger/supervisor, canonical mission selection, bounded capability resolution, protected appraisal, reconciliation, founder communication and retained learning must be composed and tested. The proof must include a due obligation, interruption, autonomous resumption, an exception and persistent mission update; a human manually advancing a harness does not qualify. CMC and VDM remain zero. Rollback must stop writers, preserve history/claims/obligations and refuse unsupported state; a code revert cannot erase external consequences.
