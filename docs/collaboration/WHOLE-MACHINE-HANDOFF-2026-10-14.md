# GREG whole-machine handoff — 2026-10-14

Status: **development branch handoff** for draft PR #169 (`claude/greg-whole-machine-convergence`). It creates no
authority, merges nothing, and leaves VEPMC at 0. The full increment-by-increment record, with every defect,
attack and negative result, is `WHOLE-MACHINE-CONVERGENCE-2026-10-14.md`. This document answers the nine items the
OPUS MAXIMUS continuation directive (section 16) requires.

## 1. What Alfonso can now command that was impossible or fragmented before

| Command | What happens | Before this branch |
|---|---|---|
| Press **Run the First Mission** in Mission Control (or `greg rehearse` with a throwaway key) | One signed mission does five things: (1) reads GREG's own developmental path and Foundry contract; (2) sends what only Alfonso can unblock to his decision queue; (3) selects the best work under a signed effort budget with an exact solver, against a greedy baseline; (4) names the existing machinery and the missing capabilities; (5) delivers one private dossier, renders it as a Foundry page and retains its bytes. An independent appraisal re-derives all of it before it counts | No such mission; "what next" was a chat answer |
| Open the private link `greg console` prints | Mission Control answers the five questions from retained state (what GREG is, what it can do now, what it is doing, what it can be commanded to do, what needs Alfonso's authority). It has ten views, and signed controls for pause, resume, revoke, attach, decide, accept and stop. Only the owner's browser session can sign | Two of five questions answered (baseline in `docs/evidence/mission-control-acceptance/2026-10-14/baseline.json`); any local process could get a mission signed |
| Search **"What outcome do you want?"** | Ranks mission paths, capabilities and the 55 Foundry systems against his words, each shown with its true state and gap | A request GREG could not plan was a dead end |
| Commission a coding work order | The worker runs in a bubblewrap OS envelope, or not at all. GREG's git never runs a worker-planted hook. A signed STOP kills it mid-run, and an interrupted run is reconciled as UNCERTAIN with its spend reserved | Workers were bounded by tool permissions only |
| Initialise a body with `--confined-egress` | `http.get`, GitHub reads and briefs, `browser.render` and coding workers reach the network only through one relay. The relay enforces per-identity allowlists, journals every decision in a hash chain, and chains through the mandated proxy | Every capability had its own direct network access |
| Rehearse the commerce loop on the dossier (FIXTURE) | Company assembly, a signed fixture order, delivery, signed acceptance, and books reconciled to the cent. No money moves | Not connected to any mission |

What GREG now refuses or surfaces on its own, each attacked through a signed mission on a real body (all 14
section 13 classes):

- **Participant rights.** An offer with pressured copy for unlicensed content is refused at publication and at sale.
- **Local gain, whole damaged.** A strategy that lifts its own metric by breaking a check that already passed is
  blamed and not repeated, and a pure trade-off goes to Alfonso. It used to oscillate forever.
- **Disagreement.** Disagreeing intelligences are shown side by side, never voted.
- **Stale community state.** It cannot overwrite a recent event.
- **Network loss.** A lost network is treated as an unmeasured world, not a failed goal.
- **Budgets.** A NaN or infinite budget is refused.
- **Paid approvals.** One paid approval cannot fund a second attempt.

## 2. Canonical integration: which lineages are joined in the tested tree

| Lineage | Where it lives | Joined how | Tested by |
|---|---|---|---|
| Mind (cognition, genome admission, Competency Compiler) | `greg/cognition/`, `cortex/` | Canonical base (#143/#145 → #148, #158, #161, #163, #164); `cognition.dp_knapsack` selects in the First Mission | `tests/integration/test_greg_first_mission.py`, cortex CI job 6 |
| Body (supervised persistent process, one ledger, founder authentication) | `greg/body.py`, `provenance/ledger.py` | The one mission path; kill -9 and torn-write recovery | `tests/integration/test_greg_product_path.py` |
| Hands (workers, browser) | `greg/workers.py`, `greg/worker_isolation.py`, `greg/capabilities.py` | #159 binding cherry-picked; #157 isolation extracted (increment 4); browser and workers behind the relay (increment 8) | `test_greg_workers.py`, `test_greg_confined_egress.py` |
| Foundry | `foundry/` (55 systems) | #132 recombined: its modules canonical where named, the Mind-line modules registered as alternates under one dispatch rule | Foundry audit 50/55 COMPLETE, 0 problems |
| Genesis and RECOMBINE | `greg/genesis.py`, `greg/recombine.py` | Merged clean into the Mind line | `test_greg_recombine.py`; interrupted construction attacked in `test_greg_adversarial_machine.py` |
| Gravity | `egregore/gravity.py` (#160), `greg/gravity.py` | #160 joined by merge as the standing runtime | `test_goal_gravity*.py`, `test_greg_gravity.py` |
| Organs | `greg/ventures.py` (RailScout appraiser + WealthMachine venture engine), `greg/daleobanks_bridge.py` | Capabilities on the mission path, through each organ's own code | Real organs, run this session: `test_greg_ventures.py` 16/16 against RailScout `232f724` (`founder/railscout-coded-slice-20260926`, exported read-only) and WealthMachineIntelligence `ec82b80`. DALEOBANKS: contract tests only; its checkout here has no `.venv`, so the real-organ tests skip |
| Router (#165, #170) | `capabilities/router.py` | RETAIN_AS_EVIDENCE, labelled non-canonical; no second compiler wired in | — |

## 3. First-use proof

Run it yourself (no credentials, network, model or money):

```
python -m greg rehearse --console 8766     # then open the private link it prints, once
```

On the Chromebook: `greg/CHROMEBOOK_FIRST_MISSION.md`, steps 4–8, then `greg acceptance`.

Recorded evidence:

- **Interface acceptance.** `docs/evidence/mission-control-acceptance/2026-10-14/` holds the results and screenshots:
  14/14 properties at 1366×768 and at 390×844, ten founder clicks to a verified dossier and the controls, plus the
  baseline comparison. The same suite passes through the owner session in this session's integration run.
- **Rehearsal.** `docs/evidence/whole-machine-handoff/2026-10-14/rehearsal-summary.json` and the dossier it produced
  (`first-mission-dossier.md`).

## 4. A complete mission trace

`docs/evidence/whole-machine-handoff/2026-10-14/first-mission-trace.json`, read from the rehearsal body's own ledger
by `scripts/mission_trace.py`. That script is a view over the canonical `greg foundry trace` spans.

| Element | Recorded |
|---|---|
| Intended outcome | One private dossier whose objective, selection, composition and next step an independent appraisal re-derives from the sources; three success checks |
| Selected intelligence | `institution.survey` → `cognition.dp_knapsack` (exact 0/1 knapsack, independently verified) and `institution.compose` → `institution.dossier` |
| Chosen tools | `institution.*`, `cognition.dp_knapsack`, `foundry.apply`/`foundry.query` (#31 owned page), `artifact.store` |
| Authority decision | Signed light cone: 8 capabilities, `internal_write` ceiling, **$0 budget**, 24 h horizon. The exact solver is attached only by a founder-signed `CAPABILITY_ATTACH` |
| Executed steps | survey, compose, select, dossier, retain, owned-page: 6 DONE, 0 repeated across a simulated process crash |
| Artifacts | Dossier `.md` (6,842 B) and `.json` (10,142 B), with SHA-256 digests in the trace |
| Proof | 6 receipts on the ledger. Independent appraisal **VERIFIED**, with 12 checks true (re-derived from receipts, world re-observed, exactly once, founder signature verified, chain intact) |
| Persistence | Ledger chain verified: 852 records |
| Retained learning | "With 11 candidates and an effort budget of 8, the greedy baseline matched the exact optimum (99); the simpler method suffices at this scale." A second First Mission read this lesson back from the receipts |

## 5. Measured performance

| Measure | Result |
|---|---|
| Unit tests (`6faaea6` tree) | 2840 passed, 12 skipped, 0 failed (13 min 27 s) |
| Integration tests (same tree) | 201 passed, 0 failed (10 min 28 s) |
| CI on `7fc65cb` | 6/6 green |
| Guards | Worker-appraisal mutants 3/3 caught, with and without bubblewrap; schema refs, authority singleton and sealed developmental all pass |
| Baseline: interface | Mission Control answers 5/5 founder questions against the classic page's 2/5 |
| Baseline: selection | Exact solver 99 = greedy 99 at this scale; the dossier says the simpler method suffices |
| Latency | The First Mission spans 11.1 s from first to last event. The whole rehearsal takes 64 s wall: First Mission with crash, commerce rehearsal, second First Mission |
| Resources | Peak RSS 59 MiB (largest process); 59 s user CPU and 3.5 s system CPU for the whole rehearsal |
| Cost | $0. No network, model, money or messages used |
| Failures found and fixed this session | 13 defects, each fixed with a regression test. For the console, hook, budget, offer, oscillation and CI-mutant fixes, the test was also shown to fail on the old code. Details below |

The 13 holes were:

- the console signed for any local process;
- a worker-planted git hook ran inside GREG;
- acceptance tests had full filesystem reach;
- a NaN budget admitted any spend;
- a paid approval funded repeated attempts;
- an offer could be published around the editorial constitution;
- the engine oscillated between conflicting strategies;
- a disagreement was hidden in an ask;
- a CI mutant survived on the runner;
- pipeline steps were scored as failures;
- status over-claimed capabilities;
- phone taps were misplaced;
- the browser could not reach its own door (found while building increment 8, before it was pushed).

## 6. Reality classification

| Claim | Level |
|---|---|
| First Mission, Mission Control, commerce rehearsal, section 13 attacks, worker isolation, confined egress | IMPLEMENTED, INTEGRATED, LABORATORY-VERIFIED (this container and CI) |
| Interface acceptance at Chromebook and phone sizes | LABORATORY-VERIFIED (headless Chromium at those viewports), not on Alfonso's devices |
| Real-organ venture assessment | LABORATORY-VERIFIED against local organ checkouts |
| Founder-device | **Not verified.** No mission has run on a designated first body |
| Externally verified | **None** |
| Commercially validated | **None.** Commerce is FIXTURE only, with a published test buyer key; nobody bought anything |
| VEPMC | **0** |

## 7. Open obligations

- **Founder-only actions.**
  - Enable ChromeOS Linux and run `greg/chromebook/install.sh`, then the runbook and `greg acceptance`. This is the
    N1 gate and the only route to VEPMC 1.
  - Choose a dedicated host for #9/#10 privileged runtimes, or decline
    (`PRIVILEGED-RUNTIME-TEST-HOST-2026-10-14.md`).
  - Decide on merging PR #169.
- **#26 PARTIAL.** `browser.session` joined the relay in increment 10, and the paid model routes in increment 11.
  Still outside the relay:
  - anchoring;
  - the DALEOBANKS bridge.
  Confinement is also still opt-in.
- **#9, #10, #28 and #52 PARTIAL** (Foundry 50/55).
- **N3 and later need #137/#168's business machinery.** `greg/path.json` names N3, N4, N6 and N7, but the
  `business_case` and `shared_work` templates and their measures exist only on #137/#168, so those nodes cannot be
  measured from this tree. Porting them is its own increment. #168's two runbook defects (a stranded attach; human
  work noticed up to an hour late) were ported in increment 9.
- **Risks recorded with kill conditions in the convergence record:**
  - the owner link can leak through terminal scrollback;
  - the rights screen checks wording and declarations and does not prove title, so "emergency" in a title is a
    false positive;
  - regression blame is by sequence, not proven causation.
- **Untested here.**
  - DALEOBANKS real-organ runs.
  - A process kill in the middle of a self-repair.
  - Loss of a model vendor end to end; it is tested at component level only.
- **Future technology.** Chromium cannot run its own sandbox inside GREG's namespace (`os_sandboxed: false`). A
  privileged or rootless-sandbox route depends on the #9/#10 host decision.

## 8. Source provenance

- **Repository:** `dababiyoda/uniimente-kernel`.
- **Branch:** `claude/greg-whole-machine-convergence`.
- **PR:** draft #169.
- **This session's commits:** `74e65b4` (first convergence merge) through `57dce89`, with the increments named in
  the PR body.
- **Organ commits used:** RailScout `232f724`; WealthMachineIntelligence `ec82b80`.
- **CI:** run for `7fc65cb`, all six jobs green (job 1 id `115957758600`).

Reproduce:

```
python -m pytest -q tests/unit                     # 2840 passed, 12 skipped
python -m pytest -q tests/integration              # 201 passed
python scripts/ci/check_worker_appraisal_mutants.py
python -m greg rehearse --dir /tmp/greg-rehearsal
python scripts/mission_trace.py /tmp/greg-rehearsal/body <mission id from the rehearsal output>
GREG_TEST_RAILSCOUT=<railscout checkout with railscout/appraise.py> GREG_TEST_WMI=<WMI checkout> \
  python -m pytest -q tests/unit/test_greg_ventures.py
```

## 9. Continuity

- **Rollback.** Revert the branch commits. Every path is additive, no data migration exists, `/classic` keeps the
  previous front page, and a body without `--confined-egress` keeps its previous network route.
- **Negative results kept** (in the convergence record and evidence folders):
  - the unreproduced BLOCKED run;
  - the failed caching attempt;
  - the vacuous first version of the paid-worker attack;
  - the CI mutant that survived for the wrong reason;
  - the browser that could not reach its own door;
  - greedy tying the exact solver;
  - the proxy-bypass evidence from 2026-09-30.
- **Next active dependency.** The founder's first-body run, which is the N1 gate. Until then, the strongest next
  buildable work is to bring anchoring and the DALEOBANKS bridge behind the relay door (`browser.session` and the
  paid model routes joined it in increments 10 and 11). That would make confined egress safe to turn on by default,
  which is the remaining #26 criterion.
