# Repository Convergence Map

Deliverable C. Measured on 2026-10-15 with `git rev-list --left-right --count` and `git merge-tree`, against heads fetched from GitHub that day. Counts read "commits only on this branch | commits only on the other line". Nothing here claims a conflict-free merge that was not run.

## The one trunk

| Line | Head | Role |
|---|---|---|
| `main` | `d64a6c9` | Constitutional Kernel; no merged GREG |
| #178 `claude/greg-one-machine` | `baf630d` (was `4ed91f7` when this branch stacked on it) | The integration trunk: #175 `e34dfe0`, #172 with #169 increment 3, #166 witness, #171 organ observability, #174 per-organ keys, the one-mission whole-machine test, its 2026-10-15 second review and the Goal Gravity merge fixes. Merged here through `baf630d` (`8cb4043`, `cd8046a`) |
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
| `ba371d8` | Merge #169 `dcb9cd7`: `browser.session`, paid model routes, anchoring and the DALEOBANKS bridge behind the #26 relay; confined egress by default; confined programs barred from the founder key and body home; two recovery paths; a person's step stays visible. The confined model child now sends only the founder's priced allowlist (never `default`) and returns the per-attempt usage #178's accounting reads. Both lineages' freeze v6 and v7 kept byte for byte; the joined tree sealed as `freeze-v8.json` by `run.py --freeze` | `tests/unit/test_greg_model_child_policy.py` 8 passed; seal, model, packaging, confined-egress and #169 recovery suites 83 passed, 3 skipped, 1 environment-only failure that reproduces on #169's own head (below) |
| `e291d9c` | Deliverables A-L, intent record, verbatim prompt, convergence deliberation | `docs/opus-maximus/` |
| `f6d146e` | #178's attack suite in #178's posture again: three of its attacks had failed since `5d23901`; receipts again carry #178's supervision statement where it is true; envelope-posture cases added | `tests/integration/test_one_machine_attacks.py` 11 passed; worker suites 127 passed |
| `9a7776c` | Merge #169 `b14e4f5` (it moved after `dcb9cd7`): `mcp.call`, one tool on a founder-installed MCP server, confined with no network and a read-only filesystem; installed MCP tools in Mission Control and the planner. The only conflict was the capability control-point table; all entries kept. No seed-freeze input changed | MCP, planner, Mission Control, capability, packaging and standing-reconciliation suites 76 passed, 2 skipped |
| `d965bb7` | The alternate organ exchange (`organs.exchange`) runs DALEOBANKS and WealthMachine with no network on a confined body, and its appraisal accepts the `confined` argument #169's appraiser passes. Found by the ten-step proof on `9a7776c`, whose organ step ended APPRAISAL_FAILED | Three regression tests that fail on the previous module; ten-step proof with the real organ checkouts passes |
| records and evidence commits | The #169 merges and the fixes in the deliverables, ledger and intent record; the validation bundle | `docs/evidence/one-machine-ten-steps/2026-10-15/` |
| `c2a50ba` | Merge #169 `5244cb9` (it moved again after validation): `mcp.act`, a tool on a founder-installed MCP server that may write only approved paths and reach only approved hosts through the relay, class external_contact so it always asks; npm-installed MCP servers; a runbook step. Clean merge; the standing-reconciliation predicates exclude `mcp.act` by consequence class | Full suite 3,670 passed, 26 skipped, 1 failed (negative result 4 of the evidence README); both proofs with the real organs passed |
| `67cae30` | #178's independent verifier now asks GREG's appraiser the body's question, with the body's worker posture and egress setting (`Body.appraisal_request`). CI on PR #184 found it: without bubblewrap, the verifier re-ran a supervised body's acceptance under the fail-closed default and reported NOT_REDERIVED for a VERIFIED mission | Reproduced by hiding bubblewrap locally (fails before, passes after); appraisal-touching suites 574 passed, 7 skipped; both proofs passed |
| `8cb4043` | Merge #178 `44f7c35` (its second review of the trunk, and the institutional verifier as its own CI job). #178 bills refused and empty model answers; ported onto #169's confined child path, so both paths book the same cost. Missions keep this branch's standing reconciliation and adopt #178's per-attempt reconciliation question. Segmentation keeps both sides' hardening. #178's `freeze-v8.json` is kept byte for byte, this branch's is `freeze-v8-pr184.json`, and `freeze-v9.json` seals the joined tree (only `run.py` and `greg/models.py` differ from #178's v8) | 225 affected tests passed; seal, segmentation and organ-exchange suites 54 passed, 1 skipped |
| `3ded0a7` | Closes an adversarial review of this branch (12 confirmed findings, each reproduced by a separate skeptic). A kill between an UNCERTAIN record and its question no longer retries blind; supervision covers only workers the envelope cannot confine; a workspace script runs in the envelope; the confined organ exchange gets no network on the mission path; receipts state supervision only when it happened; a goal's paid or `mcp.act` ask is the mission's own ask | 13 regression tests, each failing on `8cb4043`; affected suites 292 passed, 3 skipped |
| `cd8046a` | Merge #178 `baf630d` (it moved again): Goal Gravity joined with the trunk, four defects fixed there. One conflict (`greg/missions.py`, both sides added methods); both kept | Goal Gravity, missions, reconciliation and organ suites 155 passed, 2 skipped; full suite and both proofs in the evidence README |

## Where two lines fixed the same defect

| Defect | This branch | #178 | Kept |
|---|---|---|---|
| Mission Control and the morning report crash after a founder reconciliation | `ce1d090` | `ce7d04a`, `ba0c0f5` | #178's record, which also books the signed cap on "executed" |
| Silent model substitution and wrong pricing | `740062c` (opt-in) | `0f7191d` and follow-ups (removed; priced allowlist) | #178's stricter policy |
| A whole-machine test | ten steps on one supervised body | one mission across Mind, Genesis, organs and Hands | Both; they prove different things, and both pass on one tree |
| Signed organ exchange on the mission path | `organs.exchange` | `organ.exchange` | Both; #178's is canonical on the one-machine mission, this branch's is a registered alternate |
| Worker posture | #169 envelope, fail closed | supervision, stated as unconfined | Both, as the founder's body setting |
| A reconciliation answer reused for a later interruption | none | per-attempt question (`44f7c35`) | #178's |
| A refused or empty model answer booked at $0 | none | billed (`44f7c35`, direct SDK path) | #178's rule, carried onto the confined child path |

## Other material lines

| Line | Head | This branch vs line | State |
|---|---|---|---|
| #175 `claude/greg-construction-on-full-convergence` | `834701e` (merged at `0ae4c94`) | 131 \| 81 against `cd8046a` | Merged at `0ae4c94` (`7b54e76`). Its new head merges #173 `a48e8fa`, which brings a second worker-confinement mechanism (Landlock grants in `greg/isolation.py`) and an evaluator freeze; `git merge-tree` reports conflicts in more than 20 files, including `greg/workers.py` and `greg/missions.py`. Not merged here: two worker-confinement mechanisms need one design decision, and #178 owns the trunk |
| #173 `claude/greg-full-machine-convergence-20261013` | `19bbdcb` | 86 \| 0 | Contained through #175 |
| #169 `claude/greg-whole-machine-convergence` | `3944a50` (merged through `5244cb9`) | 3 behind: `af1f05a` (a refused vendor key is benched), `772ad9f` (hosted MCP servers in Mission Control), `3944a50` (the console stops offering a refused key). One conflict, `greg/mission_control.py`; the next increment | **Merged through `5244cb9`** (`ba371d8` for `dcb9cd7`, `9a7776c` for `b14e4f5`, `c2a50ba` for `5244cb9`). Its 2026-10-15 heads `2fcd872`, `dcb9cd7`, `b14e4f5` and `5244cb9` are in. Conflicts were `greg/body.py`, `greg/cli.py`, `greg/models.py`, `tests/unit/test_greg_models.py`, `cortex/evaluation/seed_genome/run.py`, and add/add on `freeze-v6.json` and `freeze-v7.json`. The design conflict in `greg/models.py` was resolved by extending the confined child (`greg/model_child.py`) to carry #178's allowlist request and per-attempt evidence, so #178's withholding and billing work on both paths. #178's freezes stay `freeze-v6/v7.json`, #169's are `freeze-v6-pr169/v7-pr169.json`, and `freeze-v8.json` seals the joined tree |
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
- The #169 merge followed the same procedure: separate worktree, explicit hunk choices, a fresh seed freeze by `cortex/evaluation/seed_genome/run.py`'s own procedure, targeted suites, both whole-machine proofs, full suite (results in `docs/evidence/one-machine-ten-steps/2026-10-15/README.md`).
- One #169 test, `test_greg_python_still_runs_inside_when_its_runtime_lives_under_the_hidden_home[virtualenv]`, fails under a system interpreter (its `sys.prefix` is `/usr`, so the "home" it hides is `/`). It fails the same way on #169's own head `dcb9cd7` and passes under a virtualenv. It is recorded, not edited.
