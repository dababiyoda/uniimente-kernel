# Lineage pointer (PR #155 evidence)

The results in this directory are PR #155 lineage evidence. Their README names runner, freeze and suite paths
that now hold PR #158's files: the two lineages froze different evaluations at the same paths
(`INTENT-20261014-MIND-LINEAGE-CONVERGENCE`). #155's files are identified by (commit, path, sha256) and kept
byte-identical in the lineage archive:

| path named by this evidence | #155 commit | sha256 at that commit | archived copy |
|---|---|---|---|
| `cortex/evaluation/learned_routing/run_v3.py` | `ef5f078` | `8f7142fdca134e205e8579b4e2c8a35a5a602fdb9a244389b799bbb2c29925a5` | `docs/collaboration/lineage-archive/pr155-ef5f078/cortex/evaluation/learned_routing/run_v3.py` |
| `cortex/evaluation/learned_routing/freeze-v3.json` | `ef5f078` | `2c8df0ee9b50203a71b0182932bb54f81cc724d95ff0ccfa6481bed988fc9681` | `docs/collaboration/lineage-archive/pr155-ef5f078/cortex/evaluation/learned_routing/freeze-v3.json` |
| `cortex/evaluation/learned_routing/suite-v3.json` | `ef5f078` | `9dd97ac31dd3eab7a05d343a7cf5115c7301f1494af8b56b50e50c72f60a49ff` | `docs/collaboration/lineage-archive/pr155-ef5f078/cortex/evaluation/learned_routing/suite-v3.json` |

To reproduce a run, extract the whole tree at its freeze commit (`git archive <commit> | tar -x -C <dir>`); a
per-file `git show` is not enough. Every frozen runner of both lineages refuses at the convergence head except `cortex/evaluation/developmental_sweep/run.py`, whose frozen inputs are unchanged here, so it would run; its historical result is pinned by sha256 in a test (review of #179, L22; corrected after the round-2 review, N6).
Added after the independent review of PR #179 (L1). This file is new; nothing in this directory was edited.
