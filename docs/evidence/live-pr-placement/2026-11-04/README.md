# Section 53 placement from live state, 2026-11-04

Directive 2026-10-28 section 53 ("Do not rely on hard-coded PR numbers without verifying current state"), unit
S53-A in `acceptance/directive-sections.json`. Canonical head: #196 `d35d92a58008a458fad65954e99db00c3ea4b137`.

```sh
python scripts/lineage_map.py --base <canonical head> --prs open-prs-and-branches.json --place \
  --canonical-ref claude/greg-full-machine-completion-whgiee \
  --record docs/collaboration/KERNEL-PR-PLACEMENTS.json \
  --inheritance docs/collaboration/DEVELOPMENTAL-INHERITANCE-2026-09-30.json \
  --intake-json intake-verdicts.json          # or omit it to recompute the intake verdicts (~6 min)
```

- **Input, read live at 16:30Z:** the 162 open PRs (`gh api repos/.../pulls?state=open`) and the 100 branches without
  an open PR (`git ls-remote --heads`, `main` excluded: it is the default branch, not a lineage).
- **Result:** every one of the 262 placed, 0 violations, exit 0, 74 s.
  - Sources: 81 PRs and 78 branches derived from facts (canonical head; stacked on it; carried by it; a branch
    contained in an open PR follows that PR), 59 PRs inherited from the reviewed developmental-inheritance record,
    22 PRs and 23 branches recorded with the head they were decided at.
  - Dispositions: CANONICAL ACTIVE 1, STACKED NEXT 23, PORT MECHANISM 23, RESTACK 18, FUTURE NODE 10,
    EVIDENCE ONLY 147, SUPERSEDED IMPLEMENTATION 18, DEFERRED 3, HISTORICAL 17, NEEDS FOUNDER DECISION 2.
- **S53.A2 finding (negative):** 167 placements of a closing kind (evidence only, superseded, historical) have not had
  section 53's nine fields extracted; 15 are close-ready. Nothing on GitHub runs this check when a PR is closed or a
  branch deleted, so S53.A2 stays BUILDABLE_NOT_BUILT.
- **Not changed:** `tests/unit/test_developmental_inheritance.py` still checks a hard-coded `OPEN_KERNEL_PRS` set.
  Proposed to its owner: replace that set with this placement's live run.
- **What a placement is:** facts are measured; inherited and recorded dispositions are human judgments, revalidated
  against the live facts every run (a moved head, a closed PR or a contradicting fact is a violation), never re-made.
