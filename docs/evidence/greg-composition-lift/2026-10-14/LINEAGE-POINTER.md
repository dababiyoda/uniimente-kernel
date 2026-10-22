# Lineage pointer (PR #155 evidence)

The results in this directory are PR #155 lineage evidence. Their README names runner, freeze and suite paths
that now hold PR #158's files: the two lineages froze different evaluations at the same paths
(`INTENT-20261014-MIND-LINEAGE-CONVERGENCE`). #155's files are identified by (commit, path, sha256) and kept
byte-identical in the lineage archive:

| path named by this evidence | #155 commit | sha256 at that commit | archived copy |
|---|---|---|---|
| `cortex/evaluation/composition_lift/run_v2.py` | `ef5f078` | `d9278939e9097aaf01b9c0b9fa451905472ec82046eb4fb11196b579a5338d4d` | `docs/collaboration/lineage-archive/pr155-ef5f078/cortex/evaluation/composition_lift/run_v2.py` |
| `cortex/evaluation/composition_lift/freeze-v2.json` | `ef5f078` | `6da8c8493b2f6ad551a73c7f3948e10e29bf387058a5d499edf84ada26623fc7` | `docs/collaboration/lineage-archive/pr155-ef5f078/cortex/evaluation/composition_lift/freeze-v2.json` |
| `cortex/evaluation/composition_lift/run_v3.py` | `ef5f078` | `4d667a349d72e9a3d5510f68c39ff021e840f2189e9c2d6429a990ded477a911` | `docs/collaboration/lineage-archive/pr155-ef5f078/cortex/evaluation/composition_lift/run_v3.py` |
| `cortex/evaluation/composition_lift/freeze-v3.json` | `ef5f078` | `8da4ca74bc6905ae0946f2a00111ff26fb6db09396c18a79dca360a7892b9633` | `docs/collaboration/lineage-archive/pr155-ef5f078/cortex/evaluation/composition_lift/freeze-v3.json` |

To reproduce a run, extract the whole tree at its freeze commit (`git archive <commit> | tar -x -C <dir>`); a
per-file `git show` is not enough. Every frozen runner of both lineages refuses at the convergence head.
Added after the independent review of PR #179 (L1). This file is new; nothing in this directory was edited.
