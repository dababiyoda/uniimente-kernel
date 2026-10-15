# Repository Convergence Map

Deliverable C. Measured on 2026-10-15 with `git rev-list --left-right --count` and `git merge-tree`, against heads fetched from GitHub that day. Counts read "commits only on this branch | commits only on the other line". Nothing here claims a conflict-free merge that was not run.

## The one trunk

| Line | Head | Role |
|---|---|---|
| `main` | `d64a6c9` | Constitutional Kernel; no merged GREG |
| #178 `claude/greg-one-machine` | `4ed91f7` | The integration trunk: #175 `e34dfe0`, #172 with #169 increment 3, #166 witness, #171 organ observability, #174 per-organ keys, and the one-mission whole-machine test |
| This branch `claude/opus-maximus-one-greg-20261014` | see the draft PR | Stacked on #178. Base for review: #178 |

This branch began on 2026-10-14 as a separate trunk (#175 + #169). On 2026-10-15 a fresh read showed #178 had already been declared the trunk, so this branch merged #178 and became a stacked contribution. Decision record: `docs/collaboration/deliberation-opus-maximus-converge-on-178-20261015.json`.

## This branch's commits over #178

| Commit | What | Evidence |
|---|---|---|
| `5d23901` | Merge #178 into this session's line: #169's increments up to `94d4289` (worker envelope, relay door, owner-session console, community pages behind the owner gate, mission trace script, venture rehearsal, section 13 attacks), the envelope symlink fix, the script worker, the alternate organ exchange, the learning tie-break fix, the ten-step proof | Ten-step proof passed on this merge with real organs |
| `7b54e76` | Merge #175 `0ae4c94`: #173's Goal Gravity bound to the body (GOAL, GOAL_CONTROL, `MissionBook.fold`, goal pulls). Fixed a name collision with #178's mission ordering that broke 86 tests, and a duplicated block from `5d23901` | Goal Gravity suites 128 passed; GREG unit set 1177 passed, 2 failed (both inherited from `5d23901`) |
| `a02a258` | A reconciliation settles an interrupted attempt's held cap once; resilience keeps the interruption as a failure episode | Fixes `5d23901`'s two failures and the stall of #178's whole-machine test |
| `b4289ca` | Worker confinement is the founder's `greg init` choice: `required` by default, `supervised` by opt-in | #178's whole-machine test passes (supervised); the ten-step proof passes (required) |
| `0bc57f4` | Proof-carrying standing reconciliation (the selected invention) and ten-step step 7c | 21 unit tests; 7c on a real SIGKILL: no founder question, one completed run |
| docs commit | Deliverables A-L, intent record, verbatim prompt, convergence deliberation, evidence bundle | `docs/opus-maximus/`, `docs/evidence/one-machine-ten-steps/2026-10-15/` |

## Where two lines fixed the same defect

| Defect | This branch | #178 | Kept |
|---|---|---|---|
| Mission Control and the morning report crash after a founder reconciliation | `ce1d090` | `ce7d04a`, `ba0c0f5` | #178's record, which also books the signed cap on "executed" |
| Silent model substitution and wrong pricing | `740062c` (opt-in) | `0f7191d` and follow-ups (removed; priced allowlist) | #178's stricter policy |
| A whole-machine test | ten steps on one supervised body | one mission across Mind, Genesis, organs and Hands | Both; they prove different things, and both pass on one tree |
| Signed organ exchange on the mission path | `organs.exchange` | `organ.exchange` | Both; #178's is canonical on the one-machine mission, this branch's is a registered alternate |
| Worker posture | #169 envelope, fail closed | supervision, stated as unconfined | Both, as the founder's body setting |

## Other material lines

| Line | Head | This branch vs line | State |
|---|---|---|---|
| #175 `claude/greg-construction-on-full-convergence` | `0ae4c94` | 79 \| 0 | Merged (`7b54e76`) |
| #173 `claude/greg-full-machine-convergence-20261013` | `19bbdcb` | 86 \| 0 | Contained through #175 |
| #169 `claude/greg-whole-machine-convergence` | `dcb9cd7` | 127 \| 10 | **Next merge.** It moved twice on 2026-10-15: `2fcd872` (`browser.session`, paid routes, anchoring and the DALEOBANKS bridge behind the relay; seed freeze v6) and `dcb9cd7` (confined egress on by default; confined programs can no longer read the founder key or the body home; two recovery paths; a person's step stays visible). `merge-tree` conflicts: `greg/body.py`, `greg/cli.py`, `greg/models.py`, `tests/unit/test_greg_models.py`, `cortex/evaluation/seed_genome/run.py`, and add/add on `freeze-v6.json` and `freeze-v7.json`. Both lineages created a freeze v6 and v7 with different pinned inputs, and `greg/models.py` is itself a frozen input, so the merge needs a fresh freeze by the evaluation's own procedure, not a hand edit of either freeze. A trial merge on 2026-10-15 resolved `greg/body.py` and `greg/cli.py` mechanically but found a design conflict in `greg/models.py`: #178's model policy (no `default` fallback, a priced allowlist, withholding an answer from a model outside it) reads the full provider response, including per-attempt iterations and refusal details; #169 moves the SDK call into a confined child (`greg/model_child.py`) whose normalized answer lacks those fields. The merge must extend the child to carry the allowlist request and per-attempt evidence. The trial was aborted, not committed |
| #179 Track B Mind convergence | `e19226a` | 169 \| 91 | Different base (`8e37cd8`); converges #155 and #158 |
| #180, #181 (stacked on #179) | `88e7f6d`, `73d5197` | 169 \| 89, 169 \| 94 | Converged Mind residuals; venture case on real organs |
| #160 Goal Gravity on `egregore/` | `637b976` | 422 \| 6 | Main's standing runtime; #175's binding is its GREG-side counterpart. Watched by this session |
| #143 seed genome | `6fa9b89` | 252 \| 28 | Older base; deferred by #178 |
| #129 parts board and deficit loop | `9309fd8` | 426 \| 5 | Under investigation by #178 |
| #132 Foundry 55 | `4eff574` | 323 \| 0 | Absorbed through #173 |

## Organ contracts

| Organ | Pin | Contract state |
|---|---|---|
| DALEOBANKS `667439f` | `uniimente-kernel-boundaries` 0.1.2 at `4999acff` (unhashed archive URL) | OpportunityPacket 1.1 producer; shared-key HMAC transport; Kernel manifest 32 commits stale |
| WealthMachineIntelligence `ec82b80` | same pin | VentureAssessment producer; replay-protected HTTP intake; manifest 13 commits stale |
| RAILSCOUT `232f724` (PR #9 branch) | none | `railscout.appraisal/1` duck-typed by `greg/ventures.py`; no manifest |

Per-organ keys (#174) are on the trunk; the organs still pin the one-key package. Upgrading the pin is a founder decision.

## Migration and recovery

- Every merge is a merge commit; no PR's history is rewritten.
- Reverting this branch's stacked PR leaves #178 untouched.
- The #169 merge follows the same procedure: separate worktree, explicit hunk choices, a fresh seed freeze by `cortex/evaluation/seed_genome/run.py`'s own procedure, targeted suites, both whole-machine proofs, full suite.
