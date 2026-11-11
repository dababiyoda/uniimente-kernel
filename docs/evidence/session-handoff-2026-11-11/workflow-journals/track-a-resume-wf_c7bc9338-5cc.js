export const meta = {
  name: 'track-a-resume',
  description: 'Finish the revoked-device policy, fix two pre-existing authority defects, correct the map entry, and scout the next capability unit',
  phases: [
    { title: 'Build', detail: 'one worker per unit in its own worktree and branch' },
    { title: 'Review', detail: 'an independent adversarial reviewer per unit' },
    { title: 'Fix', detail: 'apply confirmed findings and re-verify' },
  ],
}

const S = '/tmp/claude-0/-home-user/f78643ba-8a14-5107-b25c-e0462dfdc774/scratchpad'
const OLD = '/root/.claude/projects/-home-user/f78643ba-8a14-5107-b25c-e0462dfdc774/workflows/scripts/track-a-units-wf_b8002a7a-692.js'
const COMMON = `
SHARED FACTS (read carefully):
- Kernel repo: /home/user/uniimente-kernel. Its main checkout belongs to another worker who is editing greg/authority.py there right now: DO NOT modify that working tree, do not checkout or commit there. Work only inside git worktrees under ${S}/ (git -C /home/user/uniimente-kernel worktree add ...).
- Local refs: pr196 = 8d20532464b1533b28d71d8331ca3412a90dbb11, the integration head (PR #196). main is far behind it; never base work on main. pr290 = facea170 (office refuses non-ATTACHED capabilities), branch egregore/fervent-mayer-syy5d6 = PR #291 (office runs only the registered adapter; still receiving commits), pr273 = 331de165, pr278 = a639add7.
- Python: source ${S}/venv/bin/activate (Python 3.13, the kernel's requirements-dev installed). Never pip install into that venv.
- Tests: python -m pytest -q -p no:cacheprovider <files>. 4 CPUs shared with other workers: targeted files only, never the whole suite.
- Known failures of THIS CONTAINER on pr196 itself (not yours): tests/unit/test_greg_acceptance_reality.py (3), test_greg_condition_competence_hooks.py (2), test_greg_large_inline_mission.py (1), test_greg_rehearsal_founder_tier.py (1), tests/integration/test_greg_cognition_mission.py recombined_native_game (2), test_greg_browser.py error.
- Saved review findings can be read with: python ${S}/handoff/show.py list   and   python ${S}/handoff/show.py "<substring of a finding title>"  (prints claim, reproduction, output, suggested fix, skeptic verdict). Scratch probes other reviewers wrote are under ${S}/ (for example ${S}/wt-preauth*, ${S}/audit-ev-scripts, ${S}/skeptic-*).
- Authority limits: no push, no pull request, no GitHub comment, no merge. Commit locally only: git -c user.name=Claude -c user.email=noreply@anthropic.com commit, ending each message with the two lines "Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>" and "Claude-Session: https://claude.ai/code/session_01Kucyfm9exT5imDVYvHTYSv".
- Never edit a protected artifact (governance/integrity/manifest.json lists them: constitution/*.ucl, authority/*.yaml, identity/*.yaml, policy/consequence_gate.py, governance/integrity/founder-keys.json). python -m governance.integrity --check must stay clean.
- Project evidence standard: reproduce a failure before fixing it; every safeguard gets a test that fails without it; add a mutation gate under scripts/ci (use scripts/ci/mutation_harness.py, follow check_node_revoke_mutants.py) and wire it into the mutation job of .github/workflows/canonical-ci.yml; report what you did not run; negative results are valid. Fix the defect in its canonical owner; no second authority path, no new framework.
- Before finishing, also run: tests/unit/test_repo_health_gates.py, test_effect_call_allowlist.py, test_governance_integrity.py, test_greg_packaging.py, test_sources_parse.py; python -m acceptance check; python -m acceptance directive --against 8d20532464b1533b28d71d8331ca3412a90dbb11 (ratchet must pass; do not edit the directive map unless that is your task).
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
  },
  required: ['verdict', 'summary', 'findings', 'checked_and_clean'],
}

const ATTACK = (branch, worktree, what) => `You are an adversarial reviewer of a draft change in the kernel's GREG runtime. Your job is to break it, with runnable probes on a real Body (tests/greg_fixtures.py), not to admire it.
${COMMON}
THE CHANGE: local branch ${branch} (worktree ${worktree}), based on pr196. Read git -C /home/user/uniimente-kernel diff pr196 ${branch} in full. Do not edit that branch; make your own detached worktree of it for probes.
WHAT IT CLAIMS: ${what}
ATTACK: (1) does the reproduced defect really stop, on the production path, in every variant (restart, replay, both orders of events, the mission engine and not only a direct call)? (2) what legitimate behaviour did it break: run the neighbouring test files and probe exactly-once recovery (a completed act must never be re-dispatched; a refused act must not be reported as done; an uncertain act must not be retried blind). (3) can the new rule strand a mission, crash-loop the body or flood the ledger? (4) test quality: write at least six mutants of the new code that the builder's mutation gate does not list and run the builder's tests against each; a surviving mutant is a finding. (5) composition: merge the branch with egregore/fervent-mayer-syy5d6 (PR #291) in a scratch worktree and run both sides' tests on the merged tree; a clean textual merge proves nothing. (6) boundaries: protected artifacts untouched, no new authority path, governance integrity clean.
Report findings with reproductions you ran and their output, and what you tried that came back clean.
BUILDER'S REPORT:
`

const FIXER = (task) => `You built a draft change in the kernel and an independent adversarial reviewer found defects in it. Verify each finding yourself by running its reproduction; fix every one that is real, in the same worktree and branch, each with a test that fails before your fix; say plainly which findings you reject and why (with what you ran). Then re-run your full verification list. Commit locally. Never weaken or delete a test to make it pass.
${COMMON}
YOUR ORIGINAL TASK:
${task}
`

const UNITS = [
  {
    key: 'device',
    build: `You are finishing an interrupted piece of work: the founder's revoked-device approval policy in the kernel's GREG runtime.
${COMMON}
STATE: branch claude/revoked-device-authority-20261111, worktree ${S}/revoked-device, one WIP commit d7c43ce5 on top of pr196 (17 files, about 2,200 lines: greg/revocation.py, changes in greg/body.py, missions.py, asks.py, appraisal.py, cli.py, goal_gravity.py, remote.py, a test file, a mutant gate, an ADR, a deliberation record, an intent record, plus edits to foundry/owned-source.json and docs/FOUNDER_INTENT_LEDGER.md). The previous builder was stopped mid-build before it could report. NOTHING on that branch is verified. Treat it as someone else's unfinished draft: read all of it critically, keep what is right, fix or remove what is wrong.
YOUR FULL ORIGINAL TASK is the text of the 'build' field of the unit whose key is 'device' in the JavaScript file ${OLD} (read it; it contains the founder's policy verbatim and the complete step list). Carry that task to completion on this branch:
1. Read the WIP diff (git diff pr196 HEAD) and the ADR and intent record it wrote. Check the design against the founder's policy sentence by sentence.
2. Run its test file and the neighbouring device, decision, approval and goal-gravity tests; fix what fails. Confirm the reproduce-first test really fails on pr196 (use a pr196 worktree).
3. Complete every step of the original task that the WIP did not finish (tests for each listed adversarial case, the mutation gate and its CI wiring, the suspected-compromise review, restart behaviour).
4. Check the two edits outside greg/: is the change to foundry/owned-source.json warranted (what is that file, and does a test require it)? Is the docs/FOUNDER_INTENT_LEDGER.md entry accurate, quoting the founder verbatim and claiming nothing unverified? Fix or revert as needed.
5. Run the full verification list of the original task, then commit (new commits on top of the WIP commit; do not rewrite history).
Report as the original task asks, including founder_questions for every behaviour the founder's sentence does not settle.`,
    review: (built) => `You are an adversarial security reviewer. The full review brief is the text of the 'review' field of the unit whose key is 'device' in the JavaScript file ${OLD}: read it and carry it out against local branch claude/revoked-device-authority-20261111 (worktree ${S}/revoked-device; do not edit it, make your own detached worktree for probes).
${COMMON}
BUILDER'S REPORT:
${JSON.stringify(built).slice(0, 22000)}`,
  },
  {
    key: 'negreceipt',
    build: `You are fixing a pre-existing defect in the kernel's authority office, found by an adversarial review and confirmed by a skeptic.
${COMMON}
THE DEFECT: in greg/authority.py, AuthorityOffice.act, the retained-receipt branch ("already done before an interruption: reuse, never redo") returns ActionOutcome("DONE", ...) for ANY retained receipt of this exact proposal without looking at the receipt's result_class. A receipt whose result was negative (the capability refused or failed: result_class != "positive") is therefore reported as DONE after a restart; the reviewer showed a refused compensation recorded DONE after a kill, with the founder never asked. The legacy-scope branch a few lines above does check positive. Read the full finding and its reproduction: python ${S}/handoff/show.py "retained negative receipt"
TASK:
1. Create a worktree on a new local branch: git -C /home/user/uniimente-kernel worktree add -b claude/retained-negative-receipt-20261111 ${S}/negreceipt pr196.
2. Reproduce first on a real Body, both by a direct office call and through the mission engine across a real restart (close and reopen the Body): an act whose adapter raises CapabilityError gets a negative receipt and returns REFUSED; the same attempt after a restart must return the same REFUSED outcome with the same receipt (never DONE, never a second dispatch). Also reproduce the compensation case the reviewer describes. Keep these as tests that fail on pr196.
3. Fix it in AuthorityOffice.act so a retained receipt is reported exactly as the fresh call reported it: positive -> DONE with its kept output; negative -> REFUSED with the receipt's observed_outcome and failure_class, and in neither case a redispatch. Check every consumer of the outcome (greg/missions.py _record_outcome, compensation, reconciliation, the appraiser's replay) so the mission ends in the same state it would have reached without the restart, and so a refused compensation still reaches the founder. Do not change what a positive retained receipt does.
4. Look for the same mistake elsewhere: any other place that treats "a receipt exists" as "it succeeded" (grep receipt reuse in greg/missions.py, greg/appraisal.py, greg/recovery.py, greg/reconcile*). Fix what is real, with tests; report what is not.
5. Tests for: positive reuse unchanged; negative reuse REFUSED with the same receipt hash; failure_class preserved; no second dispatch and no second grant; mission-level equality of end state with and without the restart; the compensation case. Mutation gate and CI wiring per the shared facts.
6. Run your tests plus tests/unit/test_greg_capabilities.py, test_greg_reconciliation.py, test_greg_standing_reconciliation.py, test_greg_blockers.py, tests/integration/test_greg_compensation.py, tests/integration/test_greg_reconciliation_legacy_question.py and the standard list in the shared facts. Commit locally.
Return the branch, commits, fail-before evidence and every command with its result.`,
    review: (built) => ATTACK('claude/retained-negative-receipt-20261111', `${S}/negreceipt`, 'a retained NEGATIVE receipt is reported as REFUSED (same receipt, no redispatch) instead of DONE after a restart; positive reuse is unchanged') + JSON.stringify(built).slice(0, 20000),
  },
  {
    key: 'appraiser',
    build: `You are fixing a pre-existing defect in the kernel's GREG runtime, found by an adversarial review and confirmed by a skeptic.
${COMMON}
THE DEFECT: the independent appraiser re-runs a mission's success-check sensors by calling the capability adapter directly, with no authority office, no grant, no receipt and no attach check. A capability the founder has DETACHED (or that Genesis has QUARANTINED) is therefore still executed by the appraiser. Path: Body.tick -> _close_out -> _appraise_closure -> Body.appraise. Read the full finding and its reproduction: python ${S}/handoff/show.py "appraiser executes a founder-detached"
The founder's rule (2026-11-04 re-issue, behaviour B): "Grant revocation is separate: the Kernel must deny affected execution immediately. Epistemic requalification cannot restore permission." A founder detach must mean the capability does not execute on any path.
TASK:
1. Create a worktree on a new local branch: git -C /home/user/uniimente-kernel worktree add -b claude/appraiser-detached-sensor-20261111 ${S}/appraiser pr196.
2. Map how appraisal works before changing it: greg/appraisal.py and Body.appraise; why the appraiser is deliberately independent of the mission engine (it must not trust the worker's own records) and what it is allowed to do (read-only sensors only? which capabilities, under what confinement, with a read-only ledger?); how it gets manifests and adapters (its own read-only registry restore?); every place it or the closure path invokes an adapter. Read the tests around appraisal (tests/unit/test_greg_appraisal*.py, test_greg_closure_integrity.py).
3. Reproduce first on a real Body through the real tick path: a mission closes on a read-only sensor; the founder detaches that sensor capability; the appraisal runs; show the detached adapter executed (count its calls). Also the QUARANTINED case. Keep these as tests that fail on pr196.
4. Fix it in the canonical owner, keeping the appraiser independent: the appraiser must consult the registry's attach state (and that the adapter it runs is the registered one) before running any sensor, and must not run a capability that is not ATTACHED. Decide and implement what the appraisal then says: it cannot re-observe, so the closure must NOT be reported VERIFIED on a sensor it could not run; it should be reported with an explicit verdict/reason of the kind the appraiser already uses when evidence cannot be re-derived (find the existing vocabulary; do not invent a parallel one), recorded on the ledger, and surfaced to the founder the way such verdicts already are. A later founder re-attach lets a later appraisal run. Never let the appraiser's failure to run a sensor mark the mission failed or delete evidence. If the appraiser legitimately may only run read-only capabilities, enforce that too if it is not already enforced, with a test.
5. Tests: detached sensor not executed and the closure not VERIFIED, with the reason recorded; quarantined likewise; attached sensor unchanged (still VERIFIED); re-attach then re-appraise works; restart between detach and appraisal; an adapter object that is not the registered one is not run; no crash-loop and no ledger flood when the appraisal repeats every tick. Mutation gate and CI wiring per the shared facts.
6. Run your tests plus every appraisal and closure test file, tests/unit/test_greg_recombine.py, and the standard list in the shared facts. Commit locally.
Return the branch, commits, fail-before evidence, the verdict vocabulary you used and why, founder_questions for anything the founder's sentence does not settle, and every command with its result.`,
    review: (built) => ATTACK('claude/appraiser-detached-sensor-20261111', `${S}/appraiser`, 'the independent appraiser no longer executes a capability that is not ATTACHED (or an adapter that is not the registered one); such a closure is not reported VERIFIED and the reason is recorded; attached sensors are unchanged') + JSON.stringify(built).slice(0, 20000),
  },
  {
    key: 'map',
    build: `You are applying an independent reviewer's corrections to a completion-map change in the kernel.
${COMMON}
STATE: branch claude/directive-map-s69a6-20261111, worktree ${S}/map-s69a6, head 252be328 (two commits on pr196). It corrects ONE entry, S69.A6, in acceptance/directive-sections.json: the entry now cites five passing tests, computes UNIT_VERIFIED, declares coverage "partial", stays open under unit S69-A; no count moves (82/272 met, 125 buildable). The reviewer judged it sound with fixes. Read the reviewer's findings: python ${S}/handoff/show.py list   then show each finding whose source is the wf_b8002a7a journal (titles begin: "No test pins what a gate counts", "Other asks still record gated", "The tree still says the seed gate catches 7/7", "The note's stale-anchor sentence", "'Shrink-only' kept list can grow", "Commit message says the surviving mutant", "The reason carries a commit-pinned fact").
TASK: verify each finding by running its reproduction, then, on the same branch with new commits (do not rewrite history):
1. Correct every statement in the S69.A6 entry (reason, note, evidence list) that the reviewer showed to be inaccurate, so it says exactly what is enforced and what is not (for example which gates the stale-anchor check actually covers; that the kept list is not shrink-only within one change; that no test pins what a gate counts as caught unless you add one).
2. Where the fix is a small real test rather than a wording change, add it (for example a test that pins scripts/ci/mutation_harness.py's rule that a mutant counts only when a named test FAILS; a test that the kept-unwired list cannot grow without failing). Each new test must fail when its safeguard is removed; show that.
3. The seed-gate figure: establish by execution how many of check_seed_mutants.py's mutants are caught with the requirements installed, and correct the text in the tree that states a different number (cite both). Do not change the gate itself; report the surviving mutant precisely as a finding for its owner.
4. Other asks: the reviewer listed other asks whose recorded blocker is contradicted by passing tests. For each, verify by running the cited tests, and correct the entry the same way S69.A6 was corrected ONLY if the evidence is unambiguous and the module's rules allow it; otherwise list it in details with the evidence. State the before/after summary line of python -m acceptance directive and explain any count that moves.
5. Since the earlier commit message contains an inaccurate sentence, add a short note to the branch (in the new commit message) that corrects it.
6. Verify: python -m acceptance check; python -m acceptance directive --against 8d20532464b1533b28d71d8331ca3412a90dbb11; tests/unit/test_directive_sections.py; tests/unit/test_acceptance_harness.py; tests/unit/test_repo_health_gates.py; the directive mutant gate (scripts/ci/check_directive_sections_mutants.py); python scripts/repo_review.py --check; python -m governance.integrity --check. Commit locally.
Return the branch, commits, the exact before/after JSON of every entry you changed, and every command with its result.`,
    review: null,
  },
  {
    key: 'scout',
    build: `You are choosing the next capability to build for the kernel's GREG runtime. This is a READ-ONLY scouting task: change no file, commit nothing.
${COMMON}
BACKGROUND: the founder wants "the next verified capability improvement" after a run of authority fixes: something GREG can newly DO, on its canonical path, that also leaves a reusable mechanism making later capability construction, verification, repair or execution more effective. The directive completion map (python -m acceptance directive, run from a pr196 worktree) lists about 54 open buildable units. Candidates noticed so far: S40-A (SOP-first planning: a ratified procedure answers the founder's words with zero model calls), S40-C (from a compounding SOP to a callable capability, and to an organ proposal; asks S17.A2, S38.A3, S40.A2), S50-A (qualify a newly selected model route before mission use; MODEL_ROUTE_SET skips qualification), S51-A (organ consequence seams verify a Kernel gate decision instead of an organ-local approximation), S3-A (repository-wide AST check for the one authority path; four asks), S47-B (black-start recovery core), S21-A (acquire before building: qualify project-history sources and installed tools against the frozen contract).
TASK:
1. In a detached pr196 worktree, run python -m acceptance directive and read the entries for at least ten open units in acceptance/directive-sections.json and docs/evidence/directive-completion-contract-2026-10-30/README.md (the gap map with each unit's intended design), including all the candidates above.
2. For each candidate establish from the CODE (not the map's prose) what already exists and what is genuinely missing: grep for the relevant modules and tests, and run the tests that exist. A unit whose behaviour already exists is a map correction, not a build: say so with the test node ids.
3. Check for competing work: list the open pull requests with the GitHub MCP tools (ToolSearch "select:mcp__github__list_pull_requests", owner dababiyoda, repo uniimente-kernel, state open, fields number,title,head; page through all of them) and read the newest comments of work board issue #96 (ToolSearch "select:mcp__github__issue_read"; the comment API pages oldest first, about 185 comments, so read the last pages). A unit someone has claimed or has an open PR for is out.
4. Rank the top three unclaimed units by: how much it lets the real GREG do that it cannot do now; how many directive asks it closes; whether it can be built and verified in this container with no founder input (no credentials, no device, no network beyond package registries); what reusable mechanism it leaves; and how contained the change is (files, risk to authority paths).
5. For the top pick, write a build brief precise enough for another engineer to execute without re-deriving anything: the exact observable behaviour, the files and functions to change, the existing mechanisms to reuse, the reproduce-first test (what fails today), the acceptance tests, the strongest simpler baseline to compare against, the ablation that shows the new mechanism causes the gain, the mutation gate, which asks' evidence it would satisfy and at what tier, and the limits.
Return the ranking with evidence in details, the full build brief for the top pick in what_can_greg_do_now, and commands you ran.`,
    review: null,
  },
]

const results = await pipeline(
  UNITS,
  unit => agent(unit.build, { label: `build:${unit.key}`, phase: 'Build', schema: BUILD }),
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
    return agent(FIXER(unit.build) + `\nYOUR EARLIER REPORT:\n${JSON.stringify(state.built).slice(0, 14000)}\n\nREVIEWER FINDINGS TO RESOLVE:\n${JSON.stringify(real).slice(0, 22000)}`,
      { label: `fix:${unit.key}`, phase: 'Fix', schema: BUILD })
      .then(fixed => ({ ...state, fixed }))
  }
)

return results.filter(Boolean)
