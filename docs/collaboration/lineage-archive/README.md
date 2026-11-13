# Lineage archive

Byte-identical archival copies of files that two GREG Mind lineages froze at the same path
(`INTENT-20261014-MIND-LINEAGE-CONVERGENCE`): `pr155-ef5f078/` holds PR #155's bytes at `ef5f078`, and
`pr158-a832c73/` holds PR #158's at `a832c73`. One file has no collision: `pr155-ef5f078/cortex/evaluation/evolution/run.py`
keeps #155's original P8 runner, whose live copy had its import retargeted (review of #179, M20).

Nothing here is executed or imported. Each copy's identity is (commit, original path, sha256), checked against git
by `tests/unit/test_greg_mind_convergence.py`. Never edit these files; a correction goes in a new, dated file.
