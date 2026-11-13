# Section 53 placement from live state, 2026-11-13: stacks through a merged parent

Whiteboard item W6 (#96 comment 6852550499) asked whether kernel PRs from #197 onward are placed. #257's live
placement (S53-A) is on the canonical head, so this run answers it. Canonical head: #196
`f383fd26d345c8ce745476086fd7126eb2608175`. Session `session_01D4ongq2uXi7w5w3HNCUAed`; claim #96 comments
6853284653 and 6853569093.

```sh
python scripts/lineage_map.py --base f383fd26d345c8ce745476086fd7126eb2608175 --prs open-prs-and-branches.json --place \
  --canonical-ref claude/greg-full-machine-completion-whgiee \
  --record docs/collaboration/KERNEL-PR-PLACEMENTS.json \
  --inheritance docs/collaboration/DEVELOPMENTAL-INHERITANCE-2026-09-30.json \
  [--intake-json intake-verdicts.json]
```

- **Input, read live at about 13:00Z:**
  - the 194 open PRs (`repos/.../pulls?state=open`, pages 1 to 4);
  - the 149 branches with no open PR (`git ls-remote --heads`), excluding `main`.
- **Before the fix** (`placement-before.json`, the intake verdicts recomputed in 9 min 36 s):
  - exit 1, with 14 violations: 12 unplaced, 1 moved (#200) and 1 stale record (`branch:claude/text-cut-inspect-review-250`);
  - of the 58 open PRs numbered 197 or higher, 52 are placed;
  - the six unplaced are #268, #277, #285, #305, #310 and #312.
- **Root cause:**
  - #285, #305, #310 and #312 are each stacked on a branch whose parent PR merged. The canonical head carries that
    branch's head, so its intake verdict is contained and it is placed EVIDENCE ONLY.
  - `_stacked_on` followed only open PRs. It stopped at a base with no open PR and reported the child unplaced.
- **The fix** (`scripts/lineage_map.py`):
  - A base whose intake verdict is contained now counts as reaching the canonical head.
  - This is a last-resort placement, below every recorded and inherited judgment. It never runs through a judged
    parent.
- **Negative result from the first version of the fix:**
  - Applied at the top precedence, the rule overrode 13 recorded or inherited judgments with STACKED NEXT:
    #145, #149, #150, #154, #157, #161, #162, #163, #182, #184, #200, #204 and #245.
  - Two of them, #182 and #200, are NEEDS FOUNDER DECISION. Those are old stacks on parents that merged long ago,
    so a fact about the base does not make them next.
  - Walking through #245 (recorded RESTACK) would also have placed #277 STACKED NEXT while its parent awaits a restack.
  - Both behaviours are now refused, and a test fails for each of them if they return.
- **After the fix** (`placement-after.json`, using the same intake verdicts):
  - exit 1, with 10 violations;
  - exactly four rows changed, from unplaced to STACKED NEXT derived: #285, #305, #310 and #312;
  - every other placement is unchanged;
  - 57 of the 58 open PRs from #197 onward are placed.
- **What W6 still needs:** judgments only the record's owner can make, in `docs/collaboration/KERNEL-PR-PLACEMENTS.json`:
  - #268, which is based on `main`;
  - #277, which is stacked on #245 (RESTACK);
  - #200's recorded decision, which predates its head `0954e8fd`;
  - six checkpoint or WIP branches with no PR and no containing PR;
  - one stale record. This run makes no judgment.
