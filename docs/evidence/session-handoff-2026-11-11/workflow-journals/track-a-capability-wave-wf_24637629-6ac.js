export const meta = {
  name: 'track-a-capability-wave',
  description: 'Build correction-containment credit, goal-intake accumulation and two acceptance locks; adversarially review them and the browser repair; fix confirmed findings',
  phases: [
    { title: 'Build', detail: 'one worker per unit in its own worktree and branch' },
    { title: 'Review', detail: 'an independent adversarial reviewer per unit' },
    { title: 'Fix', detail: 'apply confirmed findings and re-verify' },
  ],
}

const S = '/tmp/claude-0/-home-user/f78643ba-8a14-5107-b25c-e0462dfdc774/scratchpad'
const COMMON = `
SHARED FACTS (read carefully):
- Kernel repo: /home/user/uniimente-kernel. Its main checkout belongs to the coordinating session: DO NOT modify that working tree, do not checkout or commit there. Work only inside git worktrees under ${S}/ (git -C /home/user/uniimente-kernel worktree add ...). Other workers own other worktrees under ${S}/; do not touch a worktree you did not create unless your task names it.
- Local refs: pr196 = 8d20532464b1533b28d71d8331ca3412a90dbb11, the live integration head (PR #196). main is far behind it; never base work on main. The local branch compose-20261111b (worktree ${S}/compose2, do not edit it) is a rehearsal of the integrated machine: pr196 + PR #290 (the office refuses a capability that is not ATTACHED) + PR #291 (the office runs only the registered adapter) + PR #273 (background dispatch) + PR #278 (resource bounds) + PR #294 (retained receipts read by their result).
- Python: source ${S}/venv/bin/activate (Python 3.13, the kernel's requirements-dev installed). Never pip install into that venv. It has NO networkx, scipy, z3, ortools or sympy: tests that importorskip them skip here. A skip is not a pass: name every skipped test that matters to your claim.
- Tests: python -m pytest -q -p no:cacheprovider <files>. 4 CPUs shared with up to three other workers: targeted files only, never the whole suite, and at most one mutation gate at a time.
- Known failures of THIS CONTAINER on pr196 itself (not yours): tests/unit/test_greg_acceptance_reality.py (3), test_greg_condition_competence_hooks.py (2), test_greg_large_inline_mission.py (1), test_greg_rehearsal_founder_tier.py (1), tests/integration/test_greg_cognition_mission.py recombined_native_game (2), tests/integration/test_greg_acceptance.py::test_report_tracks_founder_acts_and_never_claims_a_device_it_cannot_show (1). If you see another failure, check it on a detached worktree of pr196 before calling it yours or not yours.
- A read-only scout already mapped this work on pr196. Its experiment scripts and outputs are in ${S}/scout-out/ (exp_b.py, exp_b.out, exp_c.py, exp_c.out, exp_g.py, exp_g.out, directive.txt). Read the ones your task names; they are starting points, not proofs.
- Authority limits: no push, no pull request, no GitHub comment, no merge, no network use beyond what tests already do. Commit locally only: git -c user.name=Claude -c user.email=noreply@anthropic.com commit, ending each message with the two lines "Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>" and "Claude-Session: https://claude.ai/code/session_01Kucyfm9exT5imDVYvHTYSv".
- Never edit a protected artifact (governance/integrity/manifest.json lists them: constitution/*.ucl, authority/*.yaml, identity/*.yaml, policy/consequence_gate.py, governance/integrity/founder-keys.json). python -m governance.integrity --check must stay clean. Nothing you build may create authority, issue a grant, attach a capability or dispatch an effect on its own: it may only change what GREG believes, when it wakes, or what it withholds.
- Project evidence standard: reproduce a failure on pr196 before fixing it; every safeguard gets a test that fails without it; add or extend a mutation gate under scripts/ci (use scripts/ci/mutation_harness.py; a mutant counts as caught only when a named test FAILS; every old string must occur exactly once) and, for a new gate, wire it into job 10 of .github/workflows/canonical-ci.yml; report what you did not run; negative results are valid. Extend the canonical owner module; no second authority path, ledger, mission engine or framework. Compare against the simplest baseline and run the ablation your task names.
- When you transplant a mechanism from outside (an algorithm or a mature tool's primitive), record it as a Mechanism Card beside the existing ones in docs/mechanisms/ (read MC-0002 for the format): source behaviour, mutation, preserved invariant, new interaction, expected benefit, new failure, simpler comparator, decisive experiment, disposition. No card for ordinary code.
- The founder's rules for this pass, verbatim: "Do not produce unsupported probability estimates or arbitrary process-quality scores in place of engineering results." "Do not relabel unfinished software as an external blocker to improve a count. Do not lower a test threshold after seeing a failure." "Do not call extra code a reusable asset until it has a justified next use."
- Writing: commit messages, docstrings and docs in plain short sentences. State the reality tier where you claim a result: a cloud container, test keys, no founder device, VEPMC 0.
- Before finishing, also run: tests/unit/test_repo_health_gates.py, test_effect_call_allowlist.py, test_governance_integrity.py, test_greg_packaging.py, test_sources_parse.py, test_import_layering.py; python -m acceptance check; python -m acceptance directive --against 8d20532464b1533b28d71d8331ca3412a90dbb11 (the ratchet must pass). If you add a tracked runtime source file, run PYTHONPATH=. python scripts/refresh_owned_source.py after git add and commit its result.
`

const BUILD = {
  type: 'object',
  properties: {
    summary: { type: 'string' },
    blocked: { type: 'string', description: 'empty string if not blocked; otherwise the precise blocker' },
    worktree: { type: 'string' },
    branch: { type: 'string' },
    base_commit: { type: 'string' },
    head_commit: { type: 'string' },
    files_changed: { type: 'array', items: { type: 'string' } },
    what_can_greg_do_now: { type: 'string' },
    commands: { type: 'array', items: { type: 'object', properties: { command: { type: 'string' }, result: { type: 'string' } }, required: ['command', 'result'] } },
    fail_before_evidence: { type: 'string' },
    baseline_and_ablation: { type: 'string' },
    limitations: { type: 'array', items: { type: 'string' } },
    founder_questions: { type: 'array', items: { type: 'string' } },
    details: { type: 'string' },
  },
  required: ['summary', 'blocked', 'commands', 'limitations', 'details'],
}

const REVIEW = {
  type: 'object',
  properties: {
    verdict: { type: 'string', enum: ['sound', 'sound_with_fixes', 'unsound'] },
    summary: { type: 'string' },
    findings: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          title: { type: 'string' },
          severity: { type: 'string', enum: ['critical', 'high', 'medium', 'low', 'info'] },
          claim: { type: 'string' },
          reproduction: { type: 'string' },
          observed_output: { type: 'string' },
          suggested_fix: { type: 'string' },
        },
        required: ['title', 'severity', 'claim', 'reproduction', 'observed_output'],
      },
    },
    checked_and_clean: { type: 'array', items: { type: 'string' } },
    not_checked: { type: 'array', items: { type: 'string' } },
  },
  required: ['verdict', 'summary', 'findings', 'checked_and_clean'],
}

const ATTACK = (branch, worktree, what, extra) => `You are an adversarial reviewer of a draft change in the kernel's GREG runtime. You did not write it. Your job is to break it with runnable probes on a real Body (tests/greg_fixtures.py), not to admire it.
${COMMON}
THE CHANGE: local branch ${branch} (worktree ${worktree}), based on pr196. Read git -C /home/user/uniimente-kernel diff pr196 ${branch} in full. Do not edit that branch or its worktree; make your own detached worktree of it for probes.
WHAT IT CLAIMS: ${what}
ATTACK:
(1) Does the claimed behaviour hold on the production path in every variant (restart, replay, both orders of events, through the mission engine or Body.tick and not only a direct call)? Re-run the fail-before evidence yourself on a detached worktree of pr196.
(2) What legitimate behaviour did it break? Run the neighbouring test files. A simpler baseline may already do as well: build it if the builder did not and compare.
(3) Can the new rule strand a mission, crash-loop the body, flood the ledger, or change who is asked what? Can it be gamed by whoever writes the input it reads?
(4) Authority: does anything in the change issue a grant, attach or restore a capability, dispatch an effect, or let evidence or a signal restore a permission the founder withdrew? Probe it; do not reason about it.
(5) Test quality: write at least six mutants of the new code that the builder's mutation gate does not list and run the builder's tests against each; a surviving mutant is a finding. Check that no test passes vacuously (delete the product change and see what still passes).
(6) Composition: merge the branch onto a scratch worktree of compose-20261111b and run both sides' tests on the merged tree; a clean textual merge proves nothing. Report any conflict and its resolution.
(7) Claims: every number and every "before/after" statement in the builder's commit messages must match what you measure. An overstated claim is a finding.
${extra || ''}
Report findings with reproductions you ran and their output, what you tried that came back clean, and what you did not check.
BUILDER'S REPORT:
`

const FIXER = (task) => `You built a draft change in the kernel and an independent adversarial reviewer found defects in it. Verify each finding yourself by running its reproduction; fix every one that is real, in the same worktree and branch, each with a test that fails before your fix; say plainly which findings you reject and why (with what you ran). Then re-run your full verification list and the mutation gate. Commit locally. Never weaken or delete a test to make it pass.
${COMMON}
YOUR ORIGINAL TASK:
${task}
`

const UNITS = [
  {
    key: 'browser',
    prebuilt: {
      summary: 'browser.render picks the first installed browser that renders an offline page; headless shell first; founder choice never replaced; Playwright layouts chrome-linux and chrome-linux64; allowlist entry; mutation gate 25/25',
      blocked: '', worktree: `${S}/browser`, branch: 'claude/browser-render-qualified-binary-20261111',
      base_commit: '8d20532464b1533b28d71d8331ca3412a90dbb11', head_commit: '46ab6f890a7c711093d5eccd321dc69c4ca41cfc',
      commands: [
        { command: 'pytest tests/unit/test_greg_browser.py -rs on pr196', result: '1 passed, 2 skipped (browser did not finish rendering within 45 seconds)' },
        { command: 'GREG_REQUIRE_BROWSER=1 pytest tests/unit/test_greg_browser.py on the branch', result: '3 passed' },
        { command: 'pytest tests/unit/test_greg_browser_binary.py', result: '14 passed' },
        { command: 'python scripts/ci/check_browser_binary_mutants.py', result: '25/25 caught' },
      ],
      limitations: ['confined relay render not exercised (no bubblewrap)', 'browser.session not exercised (no Playwright for Python)', 'manifest binaries entry changes where a Playwright headless shell is installed'],
      details: 'See the commit message of 46ab6f89 and the PR body of #293.',
    },
    build: 'Review-only unit: the change is commit 46ab6f89 on claude/browser-render-qualified-binary-20261111 (worktree ' + S + '/browser). Read its commit message for the task it set itself. Files: greg/capabilities.py (chrome_candidates, installed_chrome, cannot_render, chrome_binary, browser_render), greg/computer.py (chromium), tests/unit/test_greg_browser.py, tests/unit/test_greg_browser_binary.py, tests/security/effect-call-allowlist.json, scripts/ci/check_browser_binary_mutants.py, .github/workflows/canonical-ci.yml.',
    review: (built) => ATTACK('claude/browser-render-qualified-binary-20261111', `${S}/browser`,
      'browser.render chooses the first installed browser that renders an offline data: page (headless shell first; the founder GREG_CHROMIUM choice is the only candidate when set), remembers a failure for ten minutes and a success until the binary changes, contacts no host during the check, and refuses with a CapabilityError when no browser renders or none is installed. On pr196 in this container the full Chrome binary never returns from a headless render and both real-browser tests skip; on the branch they pass.',
      `SPECIFIC QUESTIONS FOR THIS CHANGE:
- Real browser: run tests/unit/test_greg_browser.py on pr196 and on the branch yourself (Chromium is installed under /opt/pw-browsers; /usr/bin/google-chrome is a wrapper script). Then try to make the offline check reach the network or see the caller's environment: run the real headless shell through cannot_render behind a local listening socket and a recording proxy and show whether anything connects.
- The founder's choice: with GREG_CHROMIUM set to a working binary, a broken one, a directory, a relative path, an empty string. Is another browser ever run in its place?
- Manifest identity: installed_chrome() is evaluated at import and goes into the browser.render manifest's binaries. Find every consumer that stores or compares a built-in manifest or its digest across restarts or between processes (the registry, attach and detach records, Genesis restore, PR #291's AuthorityOffice._same_manifest on compose-20261111b). Can a changed binaries tuple detach, quarantine or refuse browser.render on a body that upgrades, or make two processes of one body disagree? Probe on a real Body: attach state recorded under one binary, reopen with another installed.
- The memory: _render_judged is a module-level dict. Concurrency (PR #273 runs adapters off the body's turn: two renders at once), a binary replaced between the check and the render, a symlinked binary whose target changes, clock behaviour of time.monotonic across suspend, unbounded growth.
- Time: a hanging first candidate now costs 45 s for the check before a working second candidate renders. Does any caller's own deadline (mission step, worker supervision, the Gate) break on a first render that takes up to 90 s?
- The confined path: _render_behind_relay mounts only the binary's parent directory read-only. Does the headless shell's directory contain everything it needs there, and does the check running outside the namespace say anything about inside it? You cannot run bubblewrap here; say what is unverified.
- The effect-call allowlist entry says cannot_render is reached only when browser.render chooses its binary. Find every caller of chrome_binary, installed_chrome and cannot_render and say whether that sentence is true.
- macOS and paths with spaces: read the code for "/Applications/Google Chrome.app/..." handling; the stand-in tests split logged arguments on spaces.
- greg/computer.py chromium(): does preferring the newest full build by number change which browser a body with several builds drives, and is that right?`) + JSON.stringify(built).slice(0, 12000),
  },
  {
    key: 'credit',
    build: `You are building one bounded capability in the kernel's GREG runtime: evidence that a correction already marks as wrong must stop earning competence credit.
${COMMON}
BACKGROUND (verified by the scout on pr196; re-verify): greg/corrections.py (Index.causes, descendants, requalified, contained_receipts, claims, propagate) records corrections, and greg/body.py calls corrections.propagate each tick immediately before cognition settlement. contained_receipts and claims have NO caller outside their own test and mutation gate. On a real Body the scout ran this: a cognition mission closed and was appraised VERIFIED, then the founder signed a CRITIQUE reject. Corrections recorded FOUNDER_REJECTED, listed the receipt as contained and marked the claim NEEDS_REVIEW, and yet compiler._settled_counts stayed {"cognition.swarm": (1, 1)} and no cognition.settled record was invalidated. The reproduction is ${S}/scout-out/exp_b.py with its output exp_b.out. The directive map records the same gap under S43.A4 (unit S45-A).
THE FOUNDER'S MINIMUM TEST FOR THIS EXTENSION, verbatim: "Link conclusions, qualifications, plans, and outputs to the observations they depend on. When a source is retracted or invalidated, identify affected descendants, suspend unsupported claims, preserve unaffected work, request the minimum necessary new evidence, and requalify. Minimum test: retract one shared observation; only its dependent conclusions change. Requalification never restores revoked execution permission."
TASK:
1. Create a worktree on a new local branch: git -C /home/user/uniimente-kernel worktree add -b claude/correction-containment-credit-20261111 ${S}/credit pr196.
2. Reproduce first, as tests that fail on pr196, on a real Body with a founder-signed CRITIQUE reject (start from exp_b.py).
3. Build, in the canonical owners only:
   - greg/corrections.py: contained_missions(journal), derived like contained_receipts from unrequalified corrections that impugn the measurement.
   - greg/cognition/settlement.py: measured_outcomes computes corrections.contained_receipts(journal) once and skips any observation whose receipt is listed; reconcile gives the invalidating revision the cause id and class as its reason. Withheld means scored as neither success nor failure, as disputes already are.
   - greg/sop.py: closed_procedures drops missions in contained_missions (and move its misplaced docstring to where a docstring belongs).
   Find every other projection that turns settled evidence into credit or routing (compiler selection, capability disposition, conditional competence, learned routing, precedents, SOP proposal) and show for each, by test or by reading with file:line, that it reads through the corrected projections or is unaffected. Do not touch greg/missions.py or greg/authority.py: several open pull requests change them.
4. Tests in tests/unit/test_greg_evidence_corrections.py: test_a_contained_reading_is_withheld_from_settled_competence (real Body, signed CRITIQUE reject; before: (1, 1); after: no credit, one invalidated cognition.settled naming the cause, and a second mission's outcome untouched); test_a_source_that_moved_on_withholds_no_credit (negative control); test_requalification_returns_the_credit_and_writes_no_capability_state; test_no_procedure_is_proposed_from_a_contained_mission; and the founder's minimum test at Body tier: one observation shared by two conclusions and not by a third is retracted; exactly the two dependents change; then requalify, and show a capability the founder DETACHED before the retraction is still refused by the mission path afterwards (on pr196 the mission engine's own resolution refuses a detached capability) and that the registry state, grants and attach records are byte-for-byte unchanged by correction and requalification.
5. Simpler baseline: "withhold everything a touched mission ever settled". Build it as a test-local function and show it wrongly drops the unaffected check of a two-check mission while your change keeps it. Ablation: remove the containment filter and show the first test fails.
6. Mutants added to scripts/ci/check_evidence_corrections_mutants.py: settlement ignores containment; a requalified cause stays withheld; the measurement-impugning filter is dropped; SOP ignores containment; plus one per further guard you add. Note that this gate's live mutant needs the organs in CI job 8: read how the workflow runs it and keep your mutants runnable where it runs.
7. Mechanism Card: the transplant here is truth-maintenance labelling (a conclusion is IN only while its justifications are IN) with the early cutoff of incremental computation (a re-reading with the same source digest and signed sensor marks dependents current without re-running them). Say precisely which part already existed in corrections.py, which part you added, and what you deliberately did not transplant.
8. Neighbouring files to run: tests/unit/test_greg_evidence_corrections.py, test_greg_failure_closure.py, test_greg_closure_scoped_settlement.py, test_greg_closure_scoped_claims.py, test_greg_capability_disposition.py, test_greg_condition_competence.py, test_greg_sop_compounding.py, test_import_layering.py; tests/integration/test_cognition_multi_claim_settlement.py; tests/integration/test_outcome_correction_changes_decision.py (needs networkx and scipy: it will skip here; say so). If the directive map's S43.A4 reason is now partly false, correct only that entry's text and evidence with the tests that prove it (acceptance/ files; read how PR-ready map edits are pinned by tests/unit/test_directive_sections.py and test_directive_ratchet.py) and do not move any count the ratchet does not accept.
9. Commit locally. Return the branch, commits, fail-before evidence, the baseline and ablation results, and every command with its result.`,
    review: (built) => ATTACK('claude/correction-containment-credit-20261111', `${S}/credit`,
      'a reading that an unrequalified correction marks as contained (for example one the founder rejected by a signed CRITIQUE) no longer earns settled competence credit and no procedure is proposed from its mission; unaffected readings and other missions keep their credit; requalification returns the credit; nothing in correction or requalification writes capability state, grants or attach records',
      `SPECIFIC QUESTIONS FOR THIS CHANGE:
- Who can cause a containment? Can anyone other than the founder (a device key, community intake, an organ reply, a worker's output, a replayed or forged record) make a reading contained and so strip credit from a competitor method or route? Probe each input path that reaches corrections.propagate.
- Oscillation and cost: contain, requalify, contain again across restarts. Is settlement idempotent, are revisions bounded, does replay give the same counts as live?
- Selective invalidation: one shared observation among three conclusions. Do exactly its dependents change? Find a case where an unaffected conclusion loses credit, or an affected one keeps it (a receipt reused by two missions, a procedure compounded from several missions, a closure-scoped claim).
- Downstream: after credit is withheld, does anything now crash or divide by zero on an empty count, and does routing fall back sanely when its only evidence is withheld?
- Permission: after requalification, is a capability the founder detached or quarantined still refused, on pr196 and on the merged tree with compose-20261111b?`) + JSON.stringify(built).slice(0, 20000),
  },
  {
    key: 'intake',
    build: `You are building one bounded capability in the kernel's GREG runtime: on a founder-signed GOAL, independent weak signals must add up and repetition must not.
${COMMON}
BACKGROUND (verified by the scout on pr196; re-verify): greg/goal_gravity.py (BodyRelevanceRouter, _sense) emits one signal per intake item and scores each item alone. egregore/intersections.py (FavorableIntersectionDetector.detect) and egregore/relevance.py (score_signal) combine factors at the loop level, and greg/dataplane.py (community_evidence, _normal) already weights one unit per source and flags campaigns. The scout ran two experiments on a real Body (${S}/scout-out/exp_g.py, output exp_g.out): three weak, relevant intake items from three independent sources, each below the wake threshold, never woke the goal; one sentence repeated by four sources woke the goal four times and pulled the mission four times, while community_evidence counted those four items as one claim flagged as a suspected campaign. opportunity_factors is not referenced under greg/ or in any body-mode test. The directive map lists this as S42.A1 (unit S42-B).
THE FOUNDER'S MINIMUM TEST FOR THIS EXTENSION, verbatim: "Combine weak but relevant observations across dormant goals, capabilities, constraints, timing, and available resources. Separate independent evidence from repetition. Test whether the intersection changes feasibility or the next action. Minimum test: relevant combined signals awaken the right dormant goal; duplicated and irrelevant signals do not. Preparation stays within existing authority." The founder also wrote: "A signal is useful when it changes a justified decision or preparation step. Merely sending more notifications is not progress." and asked to track "false alerts, missed relevant events".
TASK:
1. Create a worktree on a new local branch: git -C /home/user/uniimente-kernel worktree add -b claude/goal-intake-accumulation-20261111 ${S}/intake pr196.
2. Reproduce first, as tests that fail on pr196 on a real Body with a signed GOAL: (a) three weak relevant items from three independent sources do not wake the goal; (b) one claim repeated by four sources wakes it four times.
3. Build in greg/goal_gravity.py (the canonical owner; reuse greg/dataplane.py's source weighting, normalisation and campaign cap; do not copy them): per goal, accumulate intake over a window, one unit per independent source per normalised claim; wake on the accumulated weight; a repeated claim adds nothing after its first source cluster. The accumulation must be derived from the journal so it survives a restart and replays to the same wakes, must be bounded in size, and must store no intake text beyond what the journal already keeps. A wake changes timing only: it must not issue a grant, attach anything, dispatch an effect or raise a founder ask by itself beyond what the existing wake already does.
4. Tests (real Body, signed GOAL, per-test key): the two reproductions now passing the other way; a second dormant goal the signals are irrelevant to stays asleep; irrelevant items never accumulate; a paraphrased repeat (same claim, reworded) from the same campaign does not count twice (use word-shingle similarity only if a test shows normalisation alone misses it, and say what similarity threshold you chose before you ran the test); independent sources that DISAGREE do not add up as agreement; restart in the middle of the window gives the same wake as no restart; the window expires. Report, for your whole scenario set, how many wakes were right, how many were false alerts and how many relevant combinations were missed, before and after, as counts.
5. Simpler baseline: the existing per-item scoring. Ablation: count items instead of independent sources, and show the repetition test fails.
6. Mutation gate: add scripts/ci/check_goal_intake_mutants.py (or extend the existing goal-gravity gate if one covers this file: look first) with one mutant per guard, and wire a new gate into job 10.
7. Mechanism Card: the transplant is noisy-OR style combination over independent sources applied per source cluster (never promoted to a belief about the world: it sets when to look, not what is true) and, only if used, MinHash-style shingling for near-duplicate claims. Record what you did not transplant and why.
8. Neighbouring files to run: tests/unit/test_goal_gravity.py, tests/unit/test_greg_goal_gravity.py, every tests/unit/test_greg_goal_gravity_*.py and tests/integration/test_greg_goal_gravity_process.py, tests/unit/test_greg_dataplane*.py. If S42.A1's map entry is now met or partly met, correct only that entry with the tests that prove it and do not move any count the ratchet does not accept.
9. Commit locally. Return the branch, commits, fail-before evidence, the counts, and every command with its result.`,
    review: (built) => ATTACK('claude/goal-intake-accumulation-20261111', `${S}/intake`,
      'on a founder-signed GOAL, weak relevant intake from independent sources accumulates per goal and wakes it once the accumulated weight crosses the threshold; a repeated or paraphrased claim from one source cluster counts once; irrelevant or disagreeing items do not accumulate; the accumulation is journal-derived, bounded, survives restart, and a wake changes timing only',
      `SPECIFIC QUESTIONS FOR THIS CHANGE:
- Gaming: intake is untrusted. Can one actor wake a goal at will by inventing source names, rotating wording past the similarity check, or splitting one claim into many? Can one actor SUPPRESS a wake (poison the window, exhaust the bound, make a real independent report look like a repeat)? Probe each.
- Does a wake ever reach an effect, a grant, an attach or a new founder ask that the per-item path would not have raised? Compare journals of the baseline and the change on the same intake.
- Replay and restart: kill the body mid-window (close and reopen; and one real process test if tests/integration/test_greg_goal_gravity_process.py makes that cheap) and compare wakes.
- Cost and bound: 10,000 intake items for one goal, 500 goals. Time per tick and journal growth, measured.
- The reported counts of right wakes, false alerts and misses: recount them yourself from the tests.`) + JSON.stringify(built).slice(0, 20000),
  },
  {
    key: 'locks',
    build: `You are adding two test-only locks on behaviour that already exists in the kernel's GREG runtime and that no committed test asserts. No product code changes in this unit.
${COMMON}
TASK:
1. Create a worktree on a new local branch: git -C /home/user/uniimente-kernel worktree add -b claude/acceptance-locks-20261111 ${S}/locks pr196.
2. LOCK C, proof-bearing plans. The founder's minimum test, verbatim: "change a decisive prerequisite between planning and dispatch; the stale action is withheld and unrelated valid work continues. Preserve exactly-once claims only where the underlying protocol supports them." The scout ran this on pr196 (${S}/scout-out/exp_c.py, output exp_c.out): a precondition passed at planning and the out-of-cone action waited for approval; the prerequisite was changed, then the approval given; the action was withheld, an unrelated strategy completed, the ask named held_by_precondition, and when the prerequisite returned the standing approval admitted the action with no new ask and the mission was ACHIEVED. Commit that as tests in tests/unit/test_greg_precondition_unheld.py (the committed tests there cover only a precondition that fails from the start). Assert each clause separately, including that the withheld action was never dispatched (no dispatch claim, grant or receipt for it while held) and that it ran exactly once afterwards. Add one mutant (the hold on an unproven precondition is dropped) to the mutation gate that already covers this behaviour; find it first, and create a small gate only if none does.
3. LOCK H, functional reconstitution. The founder's minimum test, verbatim: "remove a dependency unknown to the repair designer; restore bounded function using a different permitted mechanism, without replaying completed effects or resurrecting revoked authority." Existing tests show each clause separately (tests/unit/test_greg_self_repair.py, test_greg_recombine.py, test_greg_adversarial_machine.py, test_greg_genesis_restore.py); none shows them together with a completed effect. Write one Body test, using the builder route so it runs in this venv (no networkx or scipy): a mission's write step completes; the provider of a function the mission still needs is then removed; the function returns under a different capability id by GREG's own repair, without a founder ask where the signed scope allows that; the completed write is not dispatched again (one adapter call, one dispatch claim, one receipt for it); and an alternative the founder DETACHED is not used even when it is the only other candidate (then the mission must ask or wait, not use it).
4. If either lock FAILS on pr196, that is a real defect and the most valuable result of this unit: do not change the test to pass and do not change product code. Reduce it to the smallest reproduction, commit the test marked xfail(strict=True) with the reason, and report it in details with the exact observed behaviour.
5. Run the neighbouring files of each lock (the files named above plus tests/unit/test_greg_bindings.py, test_greg_bind_from_check.py, test_greg_reservation_release.py, test_greg_genesis_builder.py) and the mutation gate you touched. Commit locally.
Return the branch, commits, what each lock asserts clause by clause, any defect found, and every command with its result.`,
    review: (built) => ATTACK('claude/acceptance-locks-20261111', `${S}/locks`,
      'two test-only locks: (C) a precondition that changes between planning and dispatch withholds the stale action while unrelated work continues, and the action runs exactly once when the prerequisite returns; (H) a mission that loses a provider after a completed write is reconstituted under a different capability without re-dispatching the write and without using a founder-detached alternative',
      `SPECIFIC QUESTIONS FOR THIS CHANGE:
- These are tests only. The question is whether they can fail: for each asserted clause, make the smallest product mutation that should break it and show the test fails. A clause no mutation can break is decoration.
- Do the tests depend on timing, tick counts or ordering that will flake on a slower runner? Run each twenty times.
- Is the "unknown to the repair designer" clause honest, or does the test hand the repair its answer?`) + JSON.stringify(built).slice(0, 16000),
  },
]

const results = await pipeline(
  UNITS,
  unit => unit.prebuilt ? unit.prebuilt : agent(unit.build, { label: `build:${unit.key}`, phase: 'Build', schema: BUILD }),
  (built, unit) => {
    if (!built) return { unit: unit.key, built: null, review: null }
    if (!unit.review || built.blocked) return { unit: unit.key, built, review: null }
    return agent(unit.review(built), { label: `review:${unit.key}`, phase: 'Review', schema: REVIEW })
      .then(review => ({ unit: unit.key, built, review }))
  },
  (state, unit) => {
    if (!state || !state.review) return state
    const real = state.review.findings.filter(f => ['critical', 'high', 'medium'].includes(f.severity))
    if (!real.length) return { ...state, fixed: null }
    return agent(FIXER(unit.build) + `\nTHE BUILD REPORT:\n${JSON.stringify(state.built).slice(0, 14000)}\n\nREVIEWER FINDINGS TO RESOLVE:\n${JSON.stringify(real).slice(0, 22000)}`,
      { label: `fix:${unit.key}`, phase: 'Fix', schema: BUILD })
      .then(fixed => ({ ...state, fixed }))
  }
)

return results.filter(Boolean)
