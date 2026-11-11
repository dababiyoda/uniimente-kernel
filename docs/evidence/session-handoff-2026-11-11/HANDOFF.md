# Session handoff, 2026-11-11 (session `session_01Kucyfm9exT5imDVYvHTYSv`)

Rewritten at 19:25 UTC; it replaces the 17:45 and 14:49 versions (kept in this branch's history). This branch is
evidence only: **not for merge**. It holds the exact continuation state, the connected staffing proof, raw review
results, the scout's experiments, the decision record for work selection and the workflow scripts.

Reality status of everything below: a cloud container, test keys, no founder device. VEPMC 0. No merge,
deployment, spending, publication or outside contact happened.

## 1. Refs, refreshed 19:10 UTC

| Ref | Head | Note |
|---|---|---|
| #196 `claude/greg-full-machine-completion-whgiee` | `8d20532464b1533b28d71d8331ca3412a90dbb11` | integration line, unchanged since 11:48 |
| #290 | `facea1703dded45e495d0e6dfe059e001ffc9565` | contains #196's head |
| #291 `egregore/fervent-mayer-syy5d6` | `41fcc41f04911ccb1f0f8d5dfc18158999a18def` | contains #290's head |
| #273 | `331de165898ed5779ba87fc1532089a8f763dd4d` | based on `8d205324` |
| #278 | `a639add726df949c36a554aa87ba7c60cdabe66a` | based on `f1646209`, an ancestor of #196's head |

## 2. Draft PRs opened by this session (all into #196's branch, base `8d205324`)

| PR | Branch | Head | State at 19:25 |
|---|---|---|---|
| #291 | `egregore/fervent-mayer-syy5d6` | `41fcc41f` | all ten Canonical CI jobs and every other check passed (job 6 on its one permitted re-run; its two failures were `apt-get` on the runner). The PR body does not yet record this |
| #293 | `claude/browser-render-qualified-binary-20261111` | `da2aff57` | receipt and build-frontier checks passed; Canonical CI queued; independent review running |
| #294 | `claude/retained-negative-receipt-20261111` | `e24b326c` | Canonical CI running (started 19:05 after an hour in the queue); independent review running |
| #295 | `claude/intent-20261111-absolute-opus-maximus` | `d86e83c2` | receipt and build-frontier checks passed; Canonical CI queued |
| #296 | `claude/compose-rehearsal-20261111` | `0b0bb6d3` | opened 19:13; checks not yet reported |

Board #96 comments by this session today: 6797070087, 6799013915, 6800963150, 6802130261, 6802820715, 6802927161,
6804957388 (handoff of #296 with intake findings), 6805031119 (claim: representation repair). No acknowledgment
from the #196 integrator or #290's owner yet.

## 3. What each PR shows

**#294, retained receipts.** On `8d205324`, in real processes: a `greg run` process sent SIGKILL after the Gate's
negative receipt of a refused compensation; the new process records the compensation DONE and never asks the
founder. On `e24b326c`: each killed run equals the run never killed. A receipt with no class or an unreadable
result is UNCERTAIN with one reconciliation ask. Mutation gate 18/18 on `e24b326c`. Commit `c4c0ca53`'s message
says 18/18 and was written before the gate finished; it was 17/18 (one anchor matched twice). `e24b326c` corrects
the anchor and says so. Left open: one strict xfail (a receipted, unrecorded dispatch of a mission the founder
ends before the restarted body steps it).

**#293, browser.** On `8d205324` here, `tests/unit/test_greg_browser.py`: 1 passed, 2 skipped. On the branch: 3
passed. 14 hermetic tests, mutation gate 24/24 on `da2aff57`. `greg/computer.py` is left to #233.

**#295, founder directives.** The three founder messages of 2026-11-11 byte for byte, with digests, an intent
record and a ledger entry.

**#296, composition rehearsal.** A read-only script: each head's changed tests on its own tree and on the merged
tree, cause named by leaving one head out. 15 tests, gate 15/15. Findings on real open heads are in
`docs/collaboration/COMPOSE-REHEARSAL-2026-11-11.md` on its branch and in board comment 6804957388.

**#291, authority identity.** Unchanged: 51 tests in the two authority files, gates 23/23 and 5/5.

## 4. Composed tree

Local branch `compose-20261111c`, worktree `scratchpad/compose3`, head `090b06a5`:
`8d205324` + #290 `facea170` + #291 `41fcc41f` + #273 `331de165` + #278 `a639add7` + one call-site line
(`adapter=adapter, around=wrap`) + #294 `e24b326c`. Receipt, authority, capabilities, handoff, egress,
compensation, kill-window, reconciliation, blockers, background dispatch and resource bounds files: 254 passed, 3
skipped, 1 xfailed. #294 now merges onto #273 without a conflict in `greg/missions.py`; the CI step list still
needs both sides kept.

## 5. Units built by workflow agents, not yet pushed in full

Read each branch head and its tests before trusting it. A label is not a result.

| Unit | Local branch | Local head | Pushed | State at 19:25 |
|---|---|---|---|---|
| revoked-device approvals | `claude/revoked-device-authority-20261111` | `f35b7986` | only `d7c43ce5` | built; independent review running |
| appraiser runs no detached sensor | `claude/appraiser-detached-sensor-20261111` | `bf8e4b9f` | no | built; review queued |
| S69.A6 map corrections | `claude/directive-map-s69a6-20261111` | `a69f5b72` | only `252be328` | built; review queued |
| corrected evidence stops earning credit | `claude/correction-containment-credit-20261111` | `b01d319f` | no | built; review queued |
| goal intake counted by independent source | `claude/goal-intake-accumulation-20261111` | `1106795d` | no | built; review queued |
| two acceptance locks (stale precondition; reconstitution without replay) | `claude/acceptance-locks-20261111` | none yet | no | build running |

Known issue to fix before pushing: the credit and intake units both name a Mechanism Card `MC-0003`. One becomes
`MC-0004`.

Workflows: `track-a-resume` (run `wf_c7bc9338-5cc`), `track-a-capability-wave` (run `wf_24637629-6ac`),
`representation-repair-design` (run `wf_2f744d95-777`, design only: three designs, one adversary each, one brief).
Their journals are under the session's `subagents/workflows/<run>/journal.jsonl`.

## 6. Next unit claimed: representation repair (directive extension A)

Board claim 6805031119. Branch `claude/representation-repair-20261111` (not created yet). Scope: the compile route
of `cognition.reason`. Minimum test, the founder's words: "two representations of a withheld problem produce
conflicting recommendations; GREG identifies the invalid assumption and improves the final decision against a
simple fixed-representation baseline." Order: design panel, build, one pre-registered run on withheld seeds with
thresholds fixed first.

A second virtual environment with the solver packages CI installs now exists at `scratchpad/venv-mind`
(networkx 3.7, scipy 1.18.1, z3, ortools). The shared `scratchpad/venv` is unchanged. Until now 69 test files
skipped some or all of their tests here.

## 7. Next steps, in order

1. As each review and fix round returns: read the diff, run its tests, rehearse with
   `scripts/compose_rehearsal.py --union .github/workflows/canonical-ci.yml --union docs/FOUNDER_INTENT_LEDGER.md`
   against #290, #291, #294 and the other units, push, open a draft PR with a v2 receipt, subscribe, hand off on #96.
2. #291: record the final CI in the PR body at the next push.
3. #294: fold in its review; decide the strict xfail.
4. Representation repair: read the synthesized brief, commit the pre-registration, build, run once.
5. Map the business engine before proposing any build there. Deferred: Genesis's own method search (its files are
   held by #289 and #292) and team organization (WU-03, WU-04).

## 8. Decisions that are the founder's

- Intake of #290, #291, #293, #294, #295, #296 into #196.
- #291 reverses #290's choice that an office without a registry "keeps its earlier behaviour".
- #294 reads an unclassed or unreadable receipt as UNCERTAIN. The alternative is REFUSED.
- Revoked-device approvals: the unit adds an optional `suspected_compromise: true` to a founder-signed
  DEVICE_REVOKE. No protected authority file is touched; adopting the field is the founder's.
- `GREG_REQUIRE_BROWSER=1` in Canonical CI.
- The stray tracked file at the root of `8d205324`
  (`orker-evidence-replay.py with the fallback tier in place of the constant policies#`, from `9ee9b612`).
- One CI step that runs every `scripts/ci/check_*_mutants.py`, which would end the recurring step-list conflict.
