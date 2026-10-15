# Lineage pointer (PR #155 evidence)

The results in this directory are PR #155 lineage evidence. Their README names runner, freeze and suite paths
that now hold PR #158's files: the two lineages froze different evaluations at the same paths
(`INTENT-20261014-MIND-LINEAGE-CONVERGENCE`). #155's files are identified by (commit, path, sha256) and kept
byte-identical in the lineage archive:

| path named by this evidence | #155 commit | sha256 at that commit | archived copy |
|---|---|---|---|
| `docs/evidence/greg-protected-evolution/2026-10-14/README.md` | `ef5f078` | `65c72ce1ee531c11077c39330142e41dcc23c34fe4e94a6859d42dfe3e64131d` | `docs/collaboration/lineage-archive/pr155-ef5f078/docs/evidence/greg-protected-evolution/2026-10-14/README.md` |
| `cortex/evaluation/evolution/run.py` | `ef5f078` | `e8ce354012a5ae12a579e96d7c1e35a0e33267dec1466268a7dde5986c9b3436` | `docs/collaboration/lineage-archive/pr155-ef5f078/cortex/evaluation/evolution/run.py` |

`results.json` in this directory is #155's P8 routing-genome run. The `README.md` beside it is #158's; #155's README for this run, including its held-out smoke-run disclosure, is the archived copy listed above.

To reproduce a run, extract the whole tree at its freeze commit (`git archive <commit> | tar -x -C <dir>`); a
per-file `git show` is not enough. Every frozen runner of both lineages refuses at the convergence head.
Added after the independent review of PR #179 (L1). This file is new; nothing in this directory was edited.
