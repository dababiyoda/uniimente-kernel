# Intake audit of the open forest against #196, 2026-10-22

**Status: measurement for the integration owner. It disposes of nothing.** Session `session_01PwqafNDa4MExng4LG5kye6`,
claim [#96 comment 6334241156](https://github.com/dababiyoda/uniimente-kernel/issues/96#issuecomment-6334241156).
Destinations measured: #196 head `ac84ad7dd46ce83313bb56e2b5743d80f413904c`, then the integrator's next push
`abc7a55af5b123156b35f452e551e5239d46e72d` (the #168 join). It merges, signs and activates nothing.

## Why this was the gap

Board rule (#96): "Do not chase unbounded moving heads or count ancestry alone as proof that ported behavior is
missing." The integrator ports, cherry-picks and resolves by hand, so ancestry misreads both ways. Until now the
only way to find an unported delta was a person reading diffs: #137's ledger index (`bd0c17d`, `3884493`) was found
missing from #192/#196 that way. `scripts/lineage_map.py` measured ancestry and conflicts only.

## Mechanism

`python scripts/lineage_map.py --base <dest> --prs prs.json --intake` judges every non-merge source commit outside
the destination's history on four signals, strongest first:

| Signal | Verdict | What it proves |
|---|---|---|
| `git patch-id --stable` equal to a destination commit | `EQUIVALENT_PATCH` | the same patch landed (cherry-pick) |
| every substantive hunk's added lines present, contiguously, in the destination's file | `CONTENT_PRESENT` | the text is there (a hand port) |
| hunk text absent, but every `test_*` the commit added exists at the destination by name | `TESTS_PRESENT` | a rewritten port that kept its tests |
| added text later rewritten by the source itself | `SUPERSEDED_IN_SOURCE` | the source head is the claim, not this commit |
| none of the above, some or all hunks absent | `PARTIAL` / `MISSING` | a lead |

Blank lines and bare punctuation are ignored; a hunk with under 8 substantive characters, a binary, or a deletion
whose block is not visibly still standing at the destination is `UNDECIDABLE`, never guessed. Merge commits on the
source are counted, not judged. The `measure` mode is unchanged.

**What it does not prove.** Equal text is not equal behaviour. A missing hunk may have been replaced on purpose. A
`MISSING` row is a lead for the integrator, not a disposition, and nothing here says a delta should be merged.

## Verification

- `tests/unit/test_lineage_map.py`: 5 passed, three consecutive runs (cherry-pick, hand port, missing, superseded in
  source, whole-file deletion, ancestry, unrelated root, trivial-line rewrap, rewritten port with and without its
  tests).
- **Ablation:** each of six signals disabled in turn (patch-id, test identity, superseded-in-source, deletion
  evidence, trivial-line filter, deleted-file path); each makes a test fail.
- **Ground truth:** on #137 head `933b0c7c` it reproduces the hand finding: merge base `291e0375`; `bd0c17d`,
  `3884493`, `933b0c7` unported, with 0 of 16 added tests present.
- **Defect found in my own first version:** a commit cherry-picked onto the same parent within one second recreates
  the identical commit, so it becomes an ancestor; the fixture now picks onto a different parent.
- **Moving-head check:** between the two runs the integrator joined #168 (which carries #137's later commits). The
  second run drops both rows and nothing else from the earlier lead table; #158, which moved the same morning, appears.
- **Cost:** 358 s and 372 s wall for 139 heads (this container).

## Result: 139 open PRs against `abc7a55a` (current #196 head)

Inputs and outputs per destination under `docs/evidence/intake-audit/2026-10-22/<dest>/`: `prs.json` (pinned
heads), `intake-summary.json` (per PR), `recent-unported.json` (every SHA below). The `ac84ad7d` run is kept.

- 54 contained by ancestry, 6 behaviour-contained, 79 with an unported delta.
- 697 unique commits judged: 532 `MISSING`, 28 `PARTIAL`, 79 `SUPERSEDED_IN_SOURCE`, 28 `UNDECIDABLE`,
  15 `TESTS_PRESENT`, 12 `CONTENT_PRESENT`, 3 `EQUIVALENT_PATCH`.
- 368 of the unported commits date from July–August 2026: the phase/build/morphogenesis lineages that later
  corrections superseded. They are history, not intake debt, unless someone shows otherwise.

### Unported since 2026-10-10 (94 commits, 550 tests absent from #196 `abc7a55a`)

Grouped by the smallest open PR carrying them (`recent-unported.json` has every SHA).

| PR | Head | Commits | Tests present / added | Known disposition | Lead |
|---|---|---|---|---|---|
| #184 | `e57c51e4` | 14 (10-21..22) | 3 / 52 | none; #192 took #184 before these | **new** |
| #160 | `637b976f` | 4 (10-14) | 0 / 99 | goal gravity is in #196; these later increments are not | **new** |
| #167 | `dba14ac8` | 16 (10-13..21) | 12 / 85 | not mentioned in any collaboration record on #196 | **new** |
| #143 | `6fa9b89a` | 11 (10-13..14) | 0 / 65 | #143 cited as contract source; these commits are not | **new** |
| #129 | `9309fd86` | 2 (10-13) | 0 / 33 | partly named "portable mechanism" | check |
| #158 | `14608914` | 13 (10-22) | 34 / 126 | active Mind lineage: genome admission v8, run this morning | expected |
| #182 | `2f6a5b52` | 8 (10-15) | 1 / 46 | founder signature | expected |
| #137, #168 | | 0 | | joined at `abc7a55a` (were 3 and 6 commits at `ac84ad7d`) | resolved |
| #200, #201, #202 | | 7, 6, 7 (10-22) | 0 / 38, 0 / 28, 0 / 24 | open drafts into #196 | expected |
| #161, #163, #162, #105 | | 2, 1, 1, 2 | 0 / 4 in all | CI timeouts, ledger regeneration, evidence records | low |

**#184, review fixes after the #192 intake.** #196's merge base with #184 is #178's `e410977`, so #192 took #184 by
port, and #184 has moved since. Most of its fourteen commits are review fixes described with fail-before tests; 49
of the 52 tests the fourteen add are absent from #196:
`b4b30279` Track B review's seven findings · `a90d568d` evaluator-freeze fixes · `4757d48e` H.G4/H.G11 closure fixes
· `7f75f6ed` interruption-guard pins · `eb0065f6` re-delegation anchor fixes · `2045e02c` Landlock-confined worker
signals · `7504030d` real-Body I.I3 observation · `96c7859e` receipted-overspend booking · `8986aa74` mutation-gate pins · plus CI-host fixes `a6198ff2`,
`a5407a32`, `495f4871`, `e57c51e4` and the record `5d54c961`. Some may overlap fixes #196 made independently at its
own seams (#196 lists five seam fixes); the test names do not match.

**Absent capabilities, checked by name across all `.py` in #196:**
- #143's §13 `AdvantageCase` on venture memos and founder resource asks: 0 files.
- #160's founder return report and wake schedule: 0 files.

**#167** (Seed Cortex 0.1.6, declared baselines, `GAIN_ABSENT`) may be superseded by #194's Cortex 0.2.2, which #196
contains. No record says so; its negative result and baseline runs are evidence either way.

## Next owner and action

The integration owner (`session_01FBS4KNJR59nSbdGbxo8Mbx`) decides each disposition: port, record as superseded,
or decline. Re-run against the next pushed head with the command above. Before the founder-device install, a run
whose new-lead table is empty, or fully disposed, is the cheap check that the installed tree carries every reviewed
fix.

**Authority:** none created. **VEPMC:** 0, unchanged.
