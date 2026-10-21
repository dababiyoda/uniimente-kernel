# Validation of the OPUS MAXIMUS branch stacked on #178 (2026-10-15)

Deliverable J. Each claim below is a command that was run, on the commit named, with its result. Nothing here was run on a founder device. Nothing counts toward VEPMC, which is 0.

## Environment

| | |
|---|---|
| Host | One Linux container, kernel 6.18.44, 4 CPUs |
| Python | 3.13.16 (system interpreter `/usr/bin/python`); pytest 9.1.1 |
| Isolation | bubblewrap 0.9.0 with unprivileged namespaces available |
| Organs | DALEOBANKS `667439f`, WealthMachineIntelligence `ec82b80` (local checkouts; organ venv on Python 3.13.16) |
| Base | #178 `claude/greg-one-machine` at `baf630d` (merged here in `8cb4043` for `44f7c35` and `cd8046a` for `baf630d`; it was `4ed91f7` until about 16:40 UTC) |
| Final code commit | `42f888f`: #169 `ebfc5f7` merged (`029c3a8`), with CI job 6's gate fix (`55cf26a`) and the fifth review's two rounds of fixes (`6906df6`, `42f888f`) (earlier finals: `e3427ad`, `16f53f5`, `f59eee4`, `16900ca`, `cd8046a` and `d965bb7`, results kept below) |

The organ variables used by every proof run:

```
UNIIMENTE_DALEOBANKS_ROOT=/home/user/DALEOBANKS        UNIIMENTE_DALEOBANKS_PYTHON=<organ venv python>
UNIIMENTE_WEALTHMACHINE_ROOT=/home/user/WealthMachineIntelligence  UNIIMENTE_WEALTHMACHINE_PYTHON=<organ venv python>
UNIIMENTE_REQUIRE_ORGANS=1
GREG_TEST_DALEOBANKS=/home/user/DALEOBANKS  GREG_TEST_WMI=/home/user/WealthMachineIntelligence
```

## Commands

```
python -m pytest -q -p no:cacheprovider tests/unit/test_greg_organs.py
python -m pytest -q -p no:cacheprovider tests/integration/test_one_machine.py          # #178's one-mission proof
python -m pytest -q -p no:cacheprovider tests/integration/test_one_machine_ten_steps.py  # GREG_ONE_MACHINE_EVIDENCE=<dir>
python -m pytest -q -p no:cacheprovider -rfEs --ignore=tests/integration/test_one_machine.py \
    --ignore=tests/integration/test_one_machine_ten_steps.py                            # full suite (the two proofs run separately)
python -m greg rehearse --dir <scratch> --kernel-root <tree>                             # credential-free rehearsal
python -m cortex.evaluation.seed_genome.run --freeze                                     # wrote freeze-v8.json, then v9, v10 and v11, once each
python scripts/ci/replay_seed_compatibility.py --out <file>                              # the runner freeze CI pins
python scripts/ci/check_worker_appraisal_mutants.py; python scripts/ci/check_pipeline_mutants.py
```

## Results on the final code commit `42f888f`

`029c3a8` merges #169 `ebfc5f7` onto `b48c867`. That head brings four commits: device acceptance reads #26 confinement from the body's relay journal, hosted page checks name their evidence kind, and Foundry #52 repairs a copied multi-file source tree inside the worker envelope. `55cf26a` fixes CI job 6 (negative result 16). `6906df6` and `42f888f` fix the fifth review (negative result 17).

| Run | Result |
|---|---|
| Full suite on `42f888f` (`python -m pytest -q -p no:cacheprovider -rf`, the two proofs included without organ variables) | **5,186 passed, 31 skipped, 1 failed** in 2,887 s. The failure is negative result 4 (environment only) |
| Full suite on `029c3a8` (the merge, before the review's fixes) | 5,150 passed, 31 skipped, 1 failed (negative result 4) in 2,730 s |
| `tests/unit/test_greg_organs.py` with the real organs | 39 passed |
| #178's one-mission proof with the real organs, on `42f888f` | **Passed** (50.9 s). Independent verifier REDERIVED, 16 of 16 checks, no findings; three boots, two recoveries; Genesis formed `composed.assignment.staffing.networkx.5670bf4c5c` |
| Ten-step proof with the real organ checkouts, on `42f888f` | **Passed** (227.0 s): 11 missions closed, every appraisal VERIFIED |
| Both proofs on `029c3a8` and on `6906df6` | Passed each time (49.4 s and 217.3 s; 51.2 s and 227.4 s) |
| The fifth review's regression tests | 35 in `tests/integration/test_greg_ebfc5f7_review.py`; 24 fail on `8a03e40` (the merge plus `55cf26a`) and 7 more on `6906df6`, the rest are controls; all pass on `42f888f` |
| Every mutation gate CI runs | cortex 85 of 85; cognition residual 45 of 45; budget 3 of 3; native 4 of 4; GREG cognition 6 of 6; pipeline, worker appraisal and WASM lifecycle all caught; authority singleton, schema references and sealed developmental checks pass |
| Foundry #52 evidence | Re-recorded on this tree and re-derived (`completion._reproduces` is True); `completion.audit()` reports nothing |
| Seed replay and seals | Valid, 120 of 120; `freeze-v11.json` stays sealed (none of the merged or fixed files is one of its inputs) |
| CI on `55cf26a` | All nine jobs green |
| VEPMC | 0. Local bodies only |

## Results on the code commit `e3427ad`

`e3427ad` (with `a2b8b99`, a CI-gate fix that renames one loop variable) closes the fourth adversarial review (negative result 15) on `b4b4784`, which joins #169 `46719e4` (a credential a server reads from a file) onto `16f53f5`.

| Run | Result |
|---|---|
| Full suite (`python -m pytest -q -p no:cacheprovider -rf`, the two proofs included without organ variables) | **5,125 passed, 31 skipped, 1 failed** in 2,629 s. The failure is negative result 4 (environment only) |
| Full suite on `b4b4784` (the #169 merge, before the review's fixes) | 5,091 passed, 31 skipped, 1 failed (negative result 4) in 2,735 s |
| `tests/unit/test_greg_organs.py` with the real organs | 39 passed |
| #178's one-mission proof with the real organs | **Passed** (47.6 s). Independent verifier REDERIVED, 16 of 16 checks, no findings; three boots, two recoveries; Genesis formed `composed.assignment.staffing.networkx.5670bf4c5c` |
| Ten-step proof with the real organ checkouts | **Passed** (216.6 s): 11 missions closed, every appraisal VERIFIED |
| Real-organ venture tests (`GREG_TEST_RAILSCOUT` at the RailScout slice, `GREG_TEST_WMI` at WealthMachine) | 3 passed (run locally; CI has no RailScout checkout, so they skip there) |
| Every mutation gate CI runs | cortex 85 of 85 caught; cognition residual 45 of 45 (28 before this review), each targeted test passing unmutated first; budget 3 of 3 (after `a2b8b99`: COG-5 had duplicated the line its grant-horizon mutant targets, which made it stale); native 4 of 4; GREG cognition 6 of 6; pipeline, worker appraisal and WASM lifecycle all caught; authority singleton, schema references and sealed developmental checks pass |
| Seed replay and seals | Valid, 120 of 120; `freeze-v11.json` stays sealed (the review changes none of its inputs) |
| CI on `6523d35` | All nine jobs green |
| VEPMC | 0. Local bodies only |

## Results on the code commit `16f53f5`

`16f53f5` joins the converged Mind (Track B: #155 and #158 via #179, #180's fixes, #181's venture case on real organs) with this branch (negative result 14).

| Run | Result |
|---|---|
| Full suite (`python -m pytest -q -p no:cacheprovider -rfs`, the two proofs included without organ variables) | **5,084 passed, 31 skipped, 1 failed** in 2,850 s. The failure is negative result 4 (environment only) |
| `tests/unit/test_greg_organs.py` with the real organs | 39 passed |
| #178's one-mission proof with the real organs | **Passed** (51.8 s). Independent verifier REDERIVED, 16 of 16 checks, no findings; three boots, two recoveries; Genesis formed `composed.assignment.staffing.networkx.5670bf4c5c` |
| Ten-step proof with the real organ checkouts | **Passed** (255.3 s): 11 missions closed, every appraisal VERIFIED |
| Every mutation gate CI runs | cortex 85 of 85 caught; cognition residual 28 of 28; budget 3 of 3; native 4 of 4; GREG cognition 6 of 6; pipeline, worker appraisal and WASM lifecycle all caught |
| Seed replay and seals | Valid, 120 of 120; `freeze-v11.json` stays sealed (the merge changes none of its inputs) |
| CI on `24d5ebe` | All nine jobs green |
| VEPMC | 0. Local bodies only |

## Results on the code commit `f59eee4`

`f59eee4` closes the third adversarial review (negative result 12) on `a229f70`, which had fixed CI's job 1 (negative result 13).

| Run | Result |
|---|---|
| Full suite (`python -m pytest -q -p no:cacheprovider -rfs`, the two proofs included without organ variables) | **3,877 passed, 29 skipped, 1 failed** in 2,332 s. The failure is negative result 4 (environment only) |
| `tests/unit/test_greg_organs.py` with the real organs | 39 passed |
| #178's one-mission proof with the real organs | **Passed** (31.1 s). Independent verifier REDERIVED, 16 of 16 checks, no findings; three boots, two recoveries |
| Ten-step proof with the real organ checkouts | **Passed** (238.3 s): 11 missions closed, every appraisal VERIFIED |
| Seed replay and the frozen seed evaluation | Valid, 120 of 120; the evaluation accepts `freeze-v11.json` (each arm 100 of 100 matched, 0 hard failures) |
| The third review's regression tests | 25 of 26 fail on `a229f70` (the twenty-sixth is a control: the CLI's plain object output, which passes on both); the suites the fixes touch, 383 passed |
| CI on `a229f70` | All nine jobs green, including job 9 |
| VEPMC | 0. Local bodies only |

## Results on the code commit `16900ca`

`fd45060` joins #169 `854a021` (increments 21-29: MCP tools from the founder's words, hosted servers by URL, login or plain token, the credentials view, a benched refused key) with the second adversarial review's fixes (`2cf4bdc`, `6352c68`, negative result 10). `16900ca` changes only `verifier/v2/verify.py`, which neither proof imports; the proofs ran on `fd45060`, the full suite on `48e5116` (`16900ca` plus the ledger).

| Run | Result |
|---|---|
| Full suite (`python -m pytest -q -p no:cacheprovider -rfs`, the two proofs included without organ variables) | **3,851 passed, 29 skipped, 1 failed** in 2,206 s. The failure is negative result 4 (environment only) |
| `tests/unit/test_greg_organs.py` with the real organs | 39 passed |
| #178's one-mission proof with the real organs | **Passed** (32.8 s). Independent verifier REDERIVED; three boots, two recoveries |
| Ten-step proof with the real organ checkouts | **Passed** (252.1 s): 11 missions closed, one decision request after the SIGKILL restart, the independent appraiser VERIFIED |
| Seed replay and the frozen seed evaluation | Valid, 120 of 120; the evaluation accepts `freeze-v10.json` (each arm 100 of 100 matched, 0 hard failures) |
| The second review's regression tests | `2cf4bdc`'s 10 fail on `bc6c4b3`; of `6352c68`'s 12, 11 fail on `2cf4bdc` (the twelfth guards a plain CLI exit and passes on both); the suites they touch, 227 passed |
| VEPMC | 0. Local bodies only (`ten-step/vepmc.json`, `acceptance.json`: `first_body_designated` and `founder_accepted` NOT_YET) |

## Results on the earlier final code commit `d965bb7`

| Run | Result |
|---|---|
| Full suite (the two proofs excluded, run below) | **3,646 passed, 24 skipped, 1 failed** in 2,076 s. The failure is negative result 4 (environment only). The skips need optional SDKs, MCP server venvs or other organ checkouts |
| `tests/unit/test_greg_organs.py` with the real organs | 26 passed |
| #178's one-mission proof, `tests/integration/test_one_machine.py` | **Passed** (33.8 s). Independent verifier: 16 of 16 checks, no findings, appraisal VERIFIED. Three boots, two recoveries; Genesis formed `acquired.graph.max_flow.networkx` and `composed.assignment.staffing.networkx.5670bf4c5c` |
| Ten-step proof, `tests/integration/test_one_machine_ten_steps.py`, real organ checkouts | **Passed** (288.1 s). Every step's appraisal VERIFIED; step 6 on the real DALEOBANKS and WealthMachine, both legs verified, engine `go` capped to `needs_more_evidence` |
| Step 7b against step 7c (the invention) | Same in-flight SIGKILL: founder questions 1 then 0; completed runs 1 and 1; duplicate consequences 0 |
| Ten-step adversarial checks | Another key's envelope refused; a replayed envelope paused the body with no second effect; a reused nonce refused; a duplicate approval made no duplicate action; a tampered memo REFUTED, then VERIFIED once restored |
| `tests/unit/test_greg_organ_exchange.py::test_real_organs` with the real checkouts | 1 passed |
| `greg rehearse` | First Mission ACHIEVED, appraisal VERIFIED, ledger chain verified; FIXTURE venture rehearsal ACHIEVED with balanced books and no money moved; no network, model, money or message used (75 s) |
| VEPMC on the test bodies | 0. Each closure lacks founder acceptance and a founder-designated body (`ten-step/vepmc.json`) |

## Results on earlier commits, kept

| Commit | Run | Result |
|---|---|---|
| `9def804` (before #169) | Full suite | 3,564 passed, 3 failed, 17 skipped in 2,031 s. The 3 failures were #178 attack tests, fixed in `f6d146e` |
| `9def804` | #178 organ suite, one-mission proof, ten-step proof | 26 passed; passed (36.7 s); passed (276.7 s, stand-in organs for step 6, see negative result 3) |
| `9a7776c` (both #169 merges) | #178 organ suite and one-mission proof | 26 passed; passed (34.1 s), verifier 16 of 16 checks, appraisal VERIFIED |
| `9a7776c` | Ten-step proof | **Failed** at step 6: the organ exchange's appraisal raised a TypeError (negative result 2), fixed in `d965bb7` |
| `9a7776c` | `greg rehearse` | First Mission ACHIEVED, appraisal VERIFIED, ledger chain verified; venture rehearsal ACHIEVED with balanced fixture books; no network, model, money or message used (72 s) |
| `ba371d8` | Seal, model, packaging, confined-egress and #169 recovery suites | 83 passed, 3 skipped, 1 failed (negative result 4) |
| `f6d146e` | `tests/integration/test_one_machine_attacks.py`; worker suites | 11 passed; 127 passed |
| `9a7776c` | MCP, planner, Mission Control, capability, packaging, standing-reconciliation suites | 76 passed, 2 skipped |
| `d965bb7` | Organ exchange and venture suites | 27 passed, 3 skipped (3 skips need other real organ variables) |
| `c2a50ba` (#169 `5244cb9` merged) | Full suite; both proofs with the real organs | 3,670 passed, 26 skipped, 1 failed (negative result 4); both passed, step 7c again 0 founder questions against 1 |
| `67cae30` | #178's one-mission proof with bubblewrap hidden; appraisal-touching suites; both proofs | Passed (fails on `c2a50ba`, negative result 6); 574 passed, 7 skipped; both passed |
| `8cb4043` (#178 `44f7c35` merged) | Affected suites (missions, models, reconciliation, gravity, adversarial machine, one-machine attacks, compensation, projection, Chromebook rehearsal); seal, segmentation and organ exchange | 225 passed; 54 passed, 1 skipped. A full-suite run was stopped at 74% when #178 moved again (negative result 8) |
| `3ded0a7` | Suites the fixes touch | 292 passed, 3 skipped; Goal Gravity and mission suites 193 passed, 1 skipped; worker suites 116 passed |
| `cd8046a` (#178 `baf630d` merged; the then final code commit) | Full suite; organ suite; both proofs with the real organs; seed replay | 3,779 passed, 27 skipped, 1 failed (negative result 4) in 2,388 s; 39 passed; one-mission passed (32.2 s, REDERIVED, 16 of 16 checks), ten-step passed (263.7 s, step 7c 0 founder questions against 1); valid, 120 of 120 on `freeze-v9.json`. The first review's 11 regression tests fail on `8cb4043` |
| `bc6c4b3` (#169 `19e8fd0` merged) | CI; the unit suite here without bubblewrap | Jobs 1-8 green; job 9 failed (negative result 9); 3,456 passed, 80 skipped |

## Negative results

1. **Three of #178's attack tests had failed on this branch since the #178 merge (`5d23901`).** The full suite on `9def804` found them. The merge had dropped the `supervision` statement from worker receipts. The envelope (the default since `b4289ca`) makes #178's refusal to commit unnecessary, because the acceptance run cannot write `.git`. And #178's local CLI double is unreviewed, so a default body refuses it before dispatch. Fixed in `f6d146e`: the attacks run in #178's posture, and the envelope has its own cases.
2. **The #169 merge broke the alternate organ exchange's appraisal.** #169's appraiser passes `confined=` to every delivery verifier. `greg/organ_exchange.py`, which #169 never had, did not accept it, so every appraisal of `organs.exchange` ended APPRAISAL_FAILED. Only the ten-step proof's organ step found it. Behind it was a real gap: on a body with confined egress (#169's default) that exchange still gave the organs the body's network. Fixed in `d965bb7`, with three tests that fail on the previous module.
3. **Three earlier ten-step runs used stand-in organs for step 6** (`b4289ca` working tree, `0bc57f4` working tree, `9def804`). The scripted runner set the `UNIIMENTE_*` organ variables but not `GREG_TEST_DALEOBANKS` and `GREG_TEST_WMI`, which step 6 reads. #178's one-mission proof used the real organs in those runs. The runner now sets both, and every run on the final commit used the real checkouts.
4. **One #169 test fails under a system interpreter:** `tests/unit/test_foundry_namespace_privacy.py::test_greg_python_still_runs_inside_when_its_runtime_lives_under_the_hidden_home[virtualenv]`. It derives the founder's home from `sys.prefix`, which is `/usr` here, so the home it hides is `/`. It fails identically on #169's own head `dcb9cd7` and passes under a virtualenv (10 of 10). It is recorded, not edited.
5. **Step 7c measures the invention against step 7b on the same body.** The same in-flight SIGKILL cost the founder one reconciliation question without a standing mandate and none with one. Each produced one completed run and zero duplicate consequences.
6. **CI found what this host could not.** On the GitHub runner (no bubblewrap, Python 3.11) #178's one-mission proof failed at its independent verifier: NOT_REDERIVED with `greg_appraisal_verified` false, for a mission the body had VERIFIED. The verifier built its own appraisal request without the body's worker posture, so the appraiser re-ran a supervised body's acceptance under the fail-closed default and was refused. Every run here had bubblewrap, so the envelope succeeded and hid it. Reproduced by hiding bubblewrap: `c2a50ba` fails exactly as CI did and `67cae30` passes. The verifier and the body now build the same request, held equal by `tests/unit/test_verify_one_machine_request.py`.
7. **An adversarial review of this branch confirmed 12 defects** (separate finders per area; each finding kept only after a skeptic reproduced it at `67cae30`). Two were fixed by #178's second review (an answered reconciliation reused for a later interruption, then a crash loop), two by #178's billing of refused and empty model answers, which `8cb4043` carried onto #169's confined model path. The rest are fixed in `3ded0a7`: a body killed between an uncertain run's record and its question retried a non-retry-safe, possibly paid act blind on restart and held a cap it could never release; supervision covered any envelope refusal, so a reviewed provider ran with the body's reach over a CA path; acceptance looked `./check.sh` up in GREG's own directory and then ran the worker-modifiable script outside the envelope; the confined organ exchange still ran on the body's network on the mission path (the `d965bb7` test set `ctx.egress` by hand); a failed launch inside the envelope was reported as supervised; a goal's ask for a paid move named a scope the mission's dispatch never derives; and a goal's ask for `mcp.act` hid its reach. Each fix has a test that fails on `8cb4043`.
8. **The base moved twice during validation.** #178 went from `4ed91f7` to `44f7c35` (merged in `8cb4043`) and then to `baf630d` (merged in `cd8046a`). The full-suite run on `8cb4043` was stopped at 74% to validate the newer head instead; it had shown one failure whose name was not captured. The run on `cd8046a` shows only negative result 4, which falls at that point in the run order, but whether it was the same failure is not confirmed.

9. **CI's institutional verifier reported a unit failure it did not name.** On `bc6c4b3`, job 9's V2 (`pytest tests/unit`, no bubblewrap on the runner) printed only "1 failed, 3446 passed, 82 skipped". Job 1's full suite passed on the same commit, and the unit suite passed here with bubblewrap hidden (3,456 passed, 80 skipped), so the failure could not be named or reproduced. `16900ca` makes V2 print the FAILED and ERROR lines; the next CI run names it if it recurs.
10. **A second adversarial review, of `3ded0a7`, `8cb4043` and `cd8046a`, confirmed 13 of 14 findings** (a separate skeptic reproduced each at `3cf5dab`; one, about in-process providers, was rejected). Fixed in `2cf4bdc`: a kill in the uncertain window during Goal Gravity preparation or behind another blocker still retried blind; a crash between a reconciliation's record and its unblock crash-looped; #178's "asked again" check dropped the answer to a legacy unsalted question; provider binaries on a relative PATH resolved inside the worker's clone; a supervised Mac body's appraisal refused acceptance. Fixed in `6352c68`: a goal lost its ask, its signed reject and its evidence when the mission spent, and told the founder a paid approve was standing (it funds one run, #157); a goal asked about moves its body cannot run; the Claude Code CLI exits 1 on every error and refusal, so a billed CLI failure was booked at $0 and a refusal was shopped to the next vendor (Seed Genome re-sealed as `freeze-v10.json`); this README's digest table named the wrong seal.
11. **Two runs were stopped by limits, not by results.** The first full-suite run on `fd45060` was stopped at 63% by the tool's 30-minute background limit, with one failure shown at collection position 1,242, which is negative result 4's test; the complete re-run is the row above. The third review's finders hit a session limit before reporting and were re-run.
12. **A third adversarial review, of `6352c68` and the #169 `854a021` merge, confirmed 9 of 12 findings** (a separate skeptic reproduced each at `fd45060`; two were rejected: a goal ask beside a detached capability, which is the ask the loop raises once it is attached, and the digest test's coupling of this bundle's seal row to `RUNNER_FREEZE`, which is intended). Fixed in `f59eee4`. A paid approval is now used by its one run even when the run books $0 (the script worker reports no spend), where before a regression re-ran the move unasked. A paid ask the mission's spend overtook (Mission F's paid preparation) is withdrawn and asked again, where before an approve of it funded nothing. The goal no longer takes a used-up approve as the founder's answer, and matches pre-upgrade paid asks at the spend they show. The wording no longer offers a reject after an approve. The Claude Code CLI's verbose JSON array is read, an unknown cost or a timeout books the cap, the CLI's own model and refusal fallback is off, an answer its report says another model wrote is withheld, and `error_*` results keep their reason. Seed Genome re-sealed as `freeze-v11.json`.
13. **CI's job 1 on `77a3893` failed one of this branch's own regression tests** (`test_repository_file_never_runs_as_the_provider_through_commission`). It skipped only when the `bwrap` binary was missing; the runner has `bwrap` installed but its namespaces are unusable, so the required posture refused the order. Fixed in `a229f70`: on such a host the test asserts that neither binary ran. It passes with bubblewrap usable, missing, and installed but unusable (emulated with a `bwrap` that fails the namespace probe).


14. **Merging the Track B Mind line took decisions, recorded here.** 30 files conflicted; three readers mapped them and a completeness critic trial-merged the result, ran the full suite, both proofs with the real organs and every mutation gate, and found what the readers missed: the adversarial-machine test hook needed `Genesis._attach`'s new argument, and two cortex mutants survived until their anchors were re-pointed and two tests strengthened. Track B's code binding marks the control, game, information and probabilistic operation verdicts stale on the merged code, because this branch's #159 solvers changed what they measured; the binding was kept, they route as UNEVALUATED, and re-admission is a future pre-registered run (`docs/collaboration/MIND-LINEAGE-RECONCILIATION-2026-10-14.md`, section 18). (Re-admitted 2026-10-21, pre-registered at `462bd98`: control, game and information DEFAULT; probabilistic EXPERIMENTAL; section 19.) Ten reconciliation-map dispositions became "extended". A venture memo receipted before Track B's revenue section raised KeyError on the merged code; it now renders and verifies as it was. Deferred, each recorded: construction answers carrying `selected_receipt` and a Controller step; the compile route forwarding the caller's grant window; organ-stage Landlock signal scoping; a release guard for tags; real-organ venture tests as a CI gate (needs a RailScout checkout). Not brought in: #173's second worker-confinement mechanism, which is the founder's decision.

15. **A fourth adversarial review, of the Track B merge (`16f53f5`) and the #169 `46719e4` merge (`b4b4784`), confirmed 15 of 16 findings** (five finders by area; a separate skeptic reproduced each at `b4b4784` in its own worktree; one was rejected: a strict #159 solver refusing an input it does not read is #184's contract, not a merge defect). Fixed in `39ff3b7`: an attached construction answered before the merged compiler's step 4, so a high-consequence request was ANSWERED without a formal model, the call ran off the decision's thinking budget, the sensitivity operator was skipped and a misdeclared geometry reported agreement. Fixed in `70964a6`: the compile and chain routes dropped the caller's grant window (in both parents), so an expired grant still ran, a live one was labelled an inert standalone evaluation and the window's latency ceiling bounded nothing. Fixed in `2168e01`: a venture mission closed on any memo for its manifest, including one stating no revenue figure or built from another mission's economics; the memo, its cognition questions and the mission id are now bound to the signed economics. Fixed in `6f2a44e`: after a host outage the capability search re-ran without the compiler's deficit, so a mechanism the founder attached during the back-off counted as already tried and the mission stayed blocked. Fixed in `cc82deb` (#169's secret files): a server that echoed its key file wrote the key into a receipt on the append-only ledger; a call killed mid-flight left the key file in a workspace `fs.read` can read; an earlier action's output could choose the credential file, and the approval showed the unresolved reference; a malformed `secret_files` crashed every tick; `--from-file` read unbounded input. Fixed in `e3427ad`: three records (the requirements record's grant-window claim, section 18's list of changed functions, the convergence map's seal). On the way: the full suite caught my own outage fix counting a merely considered construction as tried, and the residual mutation gate was found counting a mutant as caught by a test that already failed unmutated; it now checks its baseline first, which also caught a test whose 1 s window a cold process cannot fit. Each fix has a test that fails without it (one secret-files variant never leaked and is kept as a guard); the residual gate grew from 28 to 45 mutants (44 in `e3427ad`, one more in `a2b8b99`). This closes two items item 14 deferred (a Controller step for constructions; the compile route's grant window). Still deferred: construction answers carrying `selected_receipt`, because settlement does not yet recognise a construction as a method.

16. **CI job 6 found two of those 45 mutants unguarded on its runner.** On `b48c867` the residual gate reported "a server echoing its key writes it into the ledger" and "a malformed scope is asked about instead of refused" as survivors: their targeted tests carry `needs_namespaces`, and job 6 installs no bubblewrap, so both skipped. A skip exits 0, so the baseline check I added counted them as passing unmutated. Locally both ran, because this container has usable bubblewrap. Fixed in the next commit without weakening anything: the echoed-key mutant now targets a test that drives `mcp_tools._invoke`'s error path with the gateway call stubbed, so it runs on any host (the namespace test stays); the malformed-scope test needs no namespace (the scope is refused before anything is dispatched), so its marker is gone; and the gate now stops with BASELINE_SKIPPED when any targeted test skips on the host it runs on. With bubblewrap unusable (a PATH whose `bwrap` fails) and with it usable, all 45 mutants are caught.

17. **A fifth adversarial review, of the #169 `ebfc5f7` merge (`029c3a8`), found eight defects in #169's newest code, and a second round on the fixes found nine more.** Round one (three finders by area; a separate skeptic reproduced six at `029c3a8`; two more, past the verification cap, were reproduced here; one finding was refuted: the relay journal's chain is unkeyed, so it records what the relay decided and is not proof against whoever can write the body's home, which the acceptance procedure now says). Fixed in `6906df6`: tree code that left a FIFO in its run's copy hung Foundry #52's tamper scan forever with the store locked, and a socket aborted it with a raw OSError; misshapen diagnosis rows crashed the repair; system 52's recorded evidence counted the frozen import closure (284 files then, 322 on this tree), so it stopped reproducing, and no CI check noticed because the audit re-runs only COMPLETE rows (records 28 and 52 claimed otherwise); `remote_evidence` called another tenant of a shared suffix (`vercel.app`, `github.io`, `co.uk`), a different IPv4 address or a bare suffix "the service's own host"; `network_confined` claimed a mission's connection while counting any part of GREG; `undeclared_destination_denied` counted a request limit as a destination refusal; a relay journal line a crash cut short crashed `greg acceptance` and `greg status`; and the report sent the founder to a runbook step that does not exist. Round two (three attackers on the fixes; each of the eight confirmed closed; four new findings reproduced by a skeptic, five more confirmed here by reading, two refuted). Fixed in `42f888f`: a sandbox still running after a timeout could swap the run's report for a FIFO between the parent's check and its blocking open, or point it at a host file through a link it made of its runtime tmp; `os.walk` stat-ed through links the tree planted; 600 sparse 8 MiB files made the tamper scan take minutes; a deeply nested report raised RecursionError; two torn tails at one offset overwrote one sidecar and the move left no record; a damaged committed row still crashed status and acceptance; and the acceptance procedure named the wrong relay identity, left out installing Chromium in the Linux container, described a render Mission Control does not show, and let step 2's own entries fail step 3. Accepted and recorded: system 52's evidence names lines of `dsl.py`, the file it repairs, so any edit to `dsl.py` needs a re-record; `greg status` keeps its broad denied count beside acceptance's destination count; the `system-35-media` record's command predates this branch. Each fix has a test that fails without it (two are controls the old code passes by chance). A handoff comment on #169 lists them.

18. **CI job 1 on `7418c82` failed `test_a_supervised_stage_leaves_no_process_behind` with ProcessLookupError, while the property it checks held.** The stage's leftover `sleep` had been killed. The test's liveness probe reads `/proc/<pid>/stat` and caught only FileNotFoundError, but a process reaped between that open and the read raises ESRCH (reproduced: open the file, kill and reap the process, read). The probe now treats any OSError as not alive, as the one-mission proof's probe already did; product code reads only `/proc/self` and `/proc/version`.

## Digests

| Artifact | sha256 |
|---|---|
| `cortex/evaluation/seed_genome/freeze-v11.json` (seal of the joined tree; `RUNNER_FREEZE`) | `bd3f9bddb3911d47f6b86e7a1772b5a77cfe811a8076d053f3e91b2606977b42` |
| `cortex/evaluation/seed_genome/freeze-v10.json` (the seal at `16900ca`) | `be5beafb740b494568b15f76c4bec6cdf242ead931c9cffc5352d0914f563a73` |
| `cortex/evaluation/seed_genome/freeze-v9.json` (the seal at `cd8046a`) | `761b35411ad15f303f92ed6248eefe521c04d3167c02845511af176a401994a9` |
| `cortex/evaluation/seed_genome/freeze-v8-pr184.json` (this branch's v8, the seal at `d965bb7`) | `c253504c11eb1f128d0687f6c5fbce2e5479b70b9b8bd183c5d5b22ec3d96039` |
| `cortex/evaluation/seed_genome/freeze-v8.json` (#178's v8) | `236da72cac0cf883688cb4e30aeabf7523caec8cb643aaa89ed62a99a0bf5b86` |
| Ten-step body ledger file, 848 records (not committed; the per-mission ledger heads are in `ten-step/mission-traces.json`) | `e38f1b79fb9d4a4c400cab5524604622187a161a9d89e36b20a5ac508fb250d7` |
| Ten-step body ledger file on `fd45060`, 849 records (not committed) | `03576a7ddf84eb133e26c4316d64c38d7bfdd53219411639c3a23a238cfef5a1` |
| One-mission ledger head on `fd45060` (`run.json` of that run, not committed) | `bea7e74f637e1dc425661d18d32102d04615da4a26eba37c97548eb233534cca` |
| Ten-step body ledger file on `f59eee4`, 849 records (not committed) | `7dd05a3cbab1941737bf0adb6887279f956439c48cd79502c1781217698d1c42` |
| One-mission ledger head on `f59eee4` (`run.json` of that run, not committed) | `df3ca819f5600cbf71947284ddd9347d5a88a2dd80be2a74f3551be19ee5293a` |
| Ten-step body ledger file on `16f53f5`, 849 records (not committed) | `be54708c1f2f93c8033bca971b2843a506eebcc2238ed942ca079477c9f73d1b` |
| One-mission ledger head on `16f53f5` (`run.json` of that run, not committed) | `346493c30b97be70f57cae521e4ed460eb0fad65f98584b9a4d2f09c5bb1e39c` |
| Ten-step body ledger file on `e3427ad`, 849 records (not committed) | `d04e1f20d88f2d66884d94423d5ccb0450ecb0578bdcf91c5a06fa32a56f22d6` |
| One-mission ledger head on `e3427ad` (`run.json` of that run, not committed) | `34c10501b8c6cd111d539683d327d7ebaa2d5f115d41a60c3737668144ebe3aa` |
| Ten-step body ledger file on `42f888f`, 849 records (not committed) | `abea6a09b3c6d9840c1ba9fc12636964372f24f5364cd0aafcd2deb4640d2417` |
| One-mission ledger head on `42f888f` (`run.json` of that run, not committed) | `e6aaae09ed579743fe8f9749af74d323907d7263bdfd84120d0fcd9f55bddfa0` |
| One-mission ledger head (`one-mission/run.json`) | `0e1cb9cf01996baaecd969a4b64d96ee16a84e21435cab1eca6a63276f5a373c` |
| `ten-step/one-machine-trace.json` | `dd29bdbb89484f4c2d9b59d4ba70e3fc8a7ffcd013ce2183c544168a5baf9514` |
| `one-mission/verify.json` | `b3437146e3d4f8cfc0588699977012e3d41d308cdd055105adffeb440081451d` |
| `rehearse.json` | `85b536d5d7194615a2b461004528d162bc92452e352a8bc62ae01aa4613d0f20` |

The proofs use per-test Ed25519 keys and a REHEARSAL key. None of them is Alfonso's key, and none authenticates him.

## Files

| Path | What |
|---|---|
| `ten-step/one-machine-trace.json` | Each of the ten steps plus 7b and 7c with mission ids, statuses, appraisal verdicts, the adversarial checks and the 7b/7c comparison |
| `ten-step/mission-traces.json` | Per-mission action traces from the body's ledger |
| `ten-step/acceptance.json` | `greg acceptance` on the test body: chain verified; reality LOCAL, not founder-device |
| `ten-step/vepmc.json` | The VEPMC classifier on the test body: 0, and why each closure does not count |
| `ten-step/mission-control-*.png` | Mission Control rendered at desktop, Chromebook and phone widths from the test body |
| `ten-step/pytest.log`, `one-mission/pytest.log` | The two proof runs on `d965bb7` |
| `one-mission/*.json` | #178's one-mission proof: mission, trace, metrics, run facts and the independent verifier (16 of 16 checks) |
| `rehearse.json` | `greg rehearse` on `d965bb7`: First Mission and the FIXTURE venture rehearsal, no network, model, money or message |
| `full-suite.txt` | The full-suite summary lines on `d965bb7` |
