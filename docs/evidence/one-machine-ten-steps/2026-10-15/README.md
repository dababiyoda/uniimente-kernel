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
| Final code commit | `cd8046a` (earlier final: `d965bb7`, results kept below) |

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
python -m cortex.evaluation.seed_genome.run --freeze                                     # wrote freeze-v8.json, later freeze-v9.json, once each
python scripts/ci/replay_seed_compatibility.py --out <file>                              # the runner freeze CI pins
python scripts/ci/check_worker_appraisal_mutants.py; python scripts/ci/check_pipeline_mutants.py
```

## Results on the final code commit `cd8046a`

`cd8046a` joins #178 `baf630d` (its second review, the institutional verifier as its own CI job, and the Goal Gravity merge fixes) with this branch and closes an adversarial review of this branch (`3ded0a7`, negative result 7).

| Run | Result |
|---|---|
| Full suite (`python -m pytest -q -p no:cacheprovider -rfs`, the two proofs included without organ variables) | **3,779 passed, 27 skipped, 1 failed** in 2,388 s. The failure is negative result 4 (environment only) |
| `tests/unit/test_greg_organs.py` with the real organs | 39 passed |
| #178's one-mission proof with the real organs | **Passed** (32.2 s). Independent verifier REDERIVED: 16 of 16 checks, no findings |
| Ten-step proof with the real organ checkouts | **Passed** (263.7 s); its assertions include every appraisal VERIFIED and step 7c's 0 founder questions against step 7b's 1 |
| Seed replay (`scripts/ci/replay_seed_compatibility.py`) and the frozen seed evaluation | Valid, 120 of 120; the evaluation accepts `freeze-v9.json` |
| CI checks run outside pytest | Worker-appraisal and pipeline mutants all caught; authority singleton and schema references pass |
| The review's regression tests on `8cb4043` (before the fixes) | All 11 fail; all pass on `3ded0a7` and `cd8046a` |
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

## Negative results

1. **Three of #178's attack tests had failed on this branch since the #178 merge (`5d23901`).** The full suite on `9def804` found them. The merge had dropped the `supervision` statement from worker receipts. The envelope (the default since `b4289ca`) makes #178's refusal to commit unnecessary, because the acceptance run cannot write `.git`. And #178's local CLI double is unreviewed, so a default body refuses it before dispatch. Fixed in `f6d146e`: the attacks run in #178's posture, and the envelope has its own cases.
2. **The #169 merge broke the alternate organ exchange's appraisal.** #169's appraiser passes `confined=` to every delivery verifier. `greg/organ_exchange.py`, which #169 never had, did not accept it, so every appraisal of `organs.exchange` ended APPRAISAL_FAILED. Only the ten-step proof's organ step found it. Behind it was a real gap: on a body with confined egress (#169's default) that exchange still gave the organs the body's network. Fixed in `d965bb7`, with three tests that fail on the previous module.
3. **Three earlier ten-step runs used stand-in organs for step 6** (`b4289ca` working tree, `0bc57f4` working tree, `9def804`). The scripted runner set the `UNIIMENTE_*` organ variables but not `GREG_TEST_DALEOBANKS` and `GREG_TEST_WMI`, which step 6 reads. #178's one-mission proof used the real organs in those runs. The runner now sets both, and every run on the final commit used the real checkouts.
4. **One #169 test fails under a system interpreter:** `tests/unit/test_foundry_namespace_privacy.py::test_greg_python_still_runs_inside_when_its_runtime_lives_under_the_hidden_home[virtualenv]`. It derives the founder's home from `sys.prefix`, which is `/usr` here, so the home it hides is `/`. It fails identically on #169's own head `dcb9cd7` and passes under a virtualenv (10 of 10). It is recorded, not edited.
5. **Step 7c measures the invention against step 7b on the same body.** The same in-flight SIGKILL cost the founder one reconciliation question without a standing mandate and none with one. Each produced one completed run and zero duplicate consequences.
6. **CI found what this host could not.** On the GitHub runner (no bubblewrap, Python 3.11) #178's one-mission proof failed at its independent verifier: NOT_REDERIVED with `greg_appraisal_verified` false, for a mission the body had VERIFIED. The verifier built its own appraisal request without the body's worker posture, so the appraiser re-ran a supervised body's acceptance under the fail-closed default and was refused. Every run here had bubblewrap, so the envelope succeeded and hid it. Reproduced by hiding bubblewrap: `c2a50ba` fails exactly as CI did and `67cae30` passes. The verifier and the body now build the same request, held equal by `tests/unit/test_verify_one_machine_request.py`.
7. **An adversarial review of this branch confirmed 12 defects** (separate finders per area; each finding kept only after a skeptic reproduced it at `67cae30`). Two were fixed by #178's second review (an answered reconciliation reused for a later interruption, then a crash loop), two by #178's billing of refused and empty model answers, which `8cb4043` carried onto #169's confined model path. The rest are fixed in `3ded0a7`: a body killed between an uncertain run's record and its question retried a non-retry-safe, possibly paid act blind on restart and held a cap it could never release; supervision covered any envelope refusal, so a reviewed provider ran with the body's reach over a CA path; acceptance looked `./check.sh` up in GREG's own directory and then ran the worker-modifiable script outside the envelope; the confined organ exchange still ran on the body's network on the mission path (the `d965bb7` test set `ctx.egress` by hand); a failed launch inside the envelope was reported as supervised; a goal's ask for a paid move named a scope the mission's dispatch never derives; and a goal's ask for `mcp.act` hid its reach. Each fix has a test that fails on `8cb4043`.
8. **The base moved twice during validation.** #178 went from `4ed91f7` to `44f7c35` (merged in `8cb4043`) and then to `baf630d` (merged in `cd8046a`). The full-suite run on `8cb4043` was stopped at 74% to validate the newer head instead; it had shown one failure whose name was not captured. The run on `cd8046a` shows only negative result 4, which falls at that point in the run order, but whether it was the same failure is not confirmed.

## Digests

| Artifact | sha256 |
|---|---|
| `cortex/evaluation/seed_genome/freeze-v10.json` (seal of the joined tree; `RUNNER_FREEZE`) | `be5beafb740b494568b15f76c4bec6cdf242ead931c9cffc5352d0914f563a73` |
| `cortex/evaluation/seed_genome/freeze-v9.json` (the seal at `cd8046a`) | `761b35411ad15f303f92ed6248eefe521c04d3167c02845511af176a401994a9` |
| `cortex/evaluation/seed_genome/freeze-v8-pr184.json` (this branch's v8, the seal at `d965bb7`) | `c253504c11eb1f128d0687f6c5fbce2e5479b70b9b8bd183c5d5b22ec3d96039` |
| `cortex/evaluation/seed_genome/freeze-v8.json` (#178's v8) | `236da72cac0cf883688cb4e30aeabf7523caec8cb643aaa89ed62a99a0bf5b86` |
| Ten-step body ledger file, 848 records (not committed; the per-mission ledger heads are in `ten-step/mission-traces.json`) | `e38f1b79fb9d4a4c400cab5524604622187a161a9d89e36b20a5ac508fb250d7` |
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
