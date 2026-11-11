export const meta = {
  name: 'representation-repair-design',
  description: 'Three independent designs for representation repair on the compile path, one adversary each, then one synthesized build brief',
  phases: [
    { title: 'Design', detail: 'three independent designs from different angles' },
    { title: 'Attack', detail: 'one adversary per design tries to refute it' },
    { title: 'Synthesize', detail: 'one build brief with the pre-registration text' },
  ],
}

const S = '/tmp/claude-0/-home-user/f78643ba-8a14-5107-b25c-e0462dfdc774/scratchpad'
const TREE = S + '/scout196'

const COMMON = `
You are designing (not building) one bounded unit for the UNIIMENTE kernel (repository checkout, READ-ONLY for you, at ${TREE}, detached at 8d20532464b1533b28d71d8331ca3412a90dbb11, the integration line of PR #196). Do not edit, commit, push, or post anything anywhere. Do not run the full test suite. You may run small read-only probes with ${S}/venv-mind/bin/python (it has networkx, scipy, z3, ortools, sympy; set PYTHONPATH=${TREE}). Write scratch files only under ${S}/repr-design/ (create it).

THE UNIT: "representation repair" on GREG's canonical cognition path, as a bounded experiment at Layer 5 of the Mind.

Founder's words, verbatim (directive of 2026-11-11, proposed extension A):
"Detect when an answer is correct for the wrong problem. Distinguish erroneous observation, assumption, formalization, method, implementation, evaluator, and environmental change. Generate competing representations and test their implications. Minimum test: two representations of a withheld problem produce conflicting recommendations; GREG identifies the invalid assumption and improves the final decision against a simple fixed-representation baseline."
Also verbatim: "These are proposed engineering extensions. Inspect existing mechanisms first; extend canonical owners rather than creating a new permanent subsystem for each name."
Also verbatim, on method: "Do not just clone products that do the intended result. Extract their primitive mechanisms, mutate them and recombine them into a new digital result."
Also binding: "Do not produce unsupported probability estimates or arbitrary process-quality scores." "Do not lower a test threshold after seeing a failure." Cognition proposes and never authorizes.

WHAT IS ALREADY KNOWN (verify what you rely on; do not re-derive the rest):
- The compile route is greg/cognition/compiler.py (run(), about 2,440 lines), reached through cognition.reason with {"problem_id", "compile": {...}}. It records derived_geometry.agrees and one dissent line when the declared geometry disagrees with what the inputs fit. A read-only scout found that it does not run two representations and compare their recommendations, does not name which assumption fails, and compares nothing with a fixed-representation baseline.
- It already has: typed mental-model operators (OPERATORS, _op with assumptions/failures fields), an inversion operator (invert_claim), a premises check (_premises_check: vacuous truth), sensitivity re-runs (_sensitivity_runs, _perturbation_runs), a thinking-budget Controller (greg/cognition/budget.py) that prices optional steps, settled competence (greg/cognition/settlement.py, condition_competence), the evidence index (docs/evidence/greg-mind-evidence-index.json), executable genomes under greg/cognition/genomes/ (for example a CUSUM change detector, robust anomaly detection, forecast quantiles, Erlang staffing, convex QP, flows), composition recipes (greg/cognition/composition.py), and an independent verifier (greg/cognition/verification.py).
- Repository conventions you must follow in the design: pre-register an evaluation before running it, freeze it at a commit, run it once on unspent seeds (docs/evidence/greg-data-exposure-ledger.json records exposure; find how seeds are reserved and how a pre-registration is validated), keep negative results, compare against the strongest simple alternative, and give every safeguard a mutation gate (scripts/ci/mutation_harness.py; a mutant counts only when a test FAILS).
- Hard limits: no new entry point, ledger, registry, mission engine or authority path; no model call and no network; do not touch greg/genesis.py or the builder route (held by open PRs #289 and #292); do not modify any frozen evidence file or any protected artifact (governance/integrity/manifest.json lists them).
- Overlap: no open branch newer than 2026-11-05 changes greg/cognition/compiler.py, cortex.py or composition.py.

WHAT A GOOD DESIGN STATES, concretely and briefly:
1. The seam: exact functions and files where the mechanism attaches on the compile route, the request shape that reaches it through cognition.reason, and what the compile receipt gains. A new module is allowed only as code the compile route calls.
2. What a "representation" is in code, and how its assumptions become executable tests over the request's own data (a prose assumption is not a test).
3. How a conflict between two representations' recommendations is detected, and how the cause is classified among the founder's seven classes. Say which classes you can separate by an executed check and which you cannot; an honest "not separable here" is better than a label.
4. Two or three problem families for the experiment, each with: two representations that can disagree, the assumption in dispute, its executable test, the decision, and a ground truth to score the decision against. Prefer families whose representations and tests reuse genomes or operations already in the tree.
5. The evaluation: arms, including every simple fixed-representation baseline AND "always the more general representation" AND "always the more conservative decision"; instances where no assumption is violated (so crying wolf is measured); the metric; the thresholds fixed before the run; how many withheld items; which seeds and why they are unspent; what result is NO_GAIN. State where repair is expected to lose.
6. Tests that fail on 8d205324 and pass after, and the mutants a gate must catch.
7. The strongest objection to your own design, and the simpler alternative you rejected with the reason.
Keep the design to what one careful builder can finish and verify in one session. Cite file paths and line numbers for every claim about the existing code.
`

const DESIGN_SCHEMA = {
  type: 'object',
  properties: {
    title: { type: 'string' },
    design_markdown: { type: 'string', description: 'The full design, at most about 1,800 words, plain prose and short lists' },
    seam_files: { type: 'array', items: { type: 'string' } },
    families: { type: 'array', items: { type: 'string' } },
    baselines: { type: 'array', items: { type: 'string' } },
    thresholds: { type: 'array', items: { type: 'string' } },
    classes_separable: { type: 'array', items: { type: 'string' } },
    classes_not_separable: { type: 'array', items: { type: 'string' } },
    strongest_objection: { type: 'string' },
    facts_verified: { type: 'array', items: { type: 'string' }, description: 'claims about existing code you checked, with path:line' },
  },
  required: ['title', 'design_markdown', 'seam_files', 'families', 'baselines', 'thresholds', 'strongest_objection', 'facts_verified'],
}

const ANGLES = [
  { key: 'seam', prompt: `YOUR ANGLE: seam first. Start from the code. Read greg/cognition/compiler.py run() end to end, the Controller in greg/cognition/budget.py, and how candidates()/fitting()/_rank() already produce more than one fitting method for one request. Find the smallest change that makes the compile route run two fitting representations under the existing thinking budget, compare their recommendations, and test the assumptions in dispute. Minimize new surface.` },
  { key: 'isolation', prompt: `YOUR ANGLE: fault isolation by recombined mechanisms. Mechanism sources to take apart (primitives only, do not clone any product): fault detection, isolation and recovery in spacecraft and process control (analytical redundancy, parity relations, fault-signature matrices), differential testing of compilers, metamorphic testing, delta debugging, and model criticism by predictive checks. Extract their primitives, change at least two of them materially, and combine them into one diagnosis procedure that separates the founder's seven causes by the signature of controlled interventions (swap the method and keep the formalization; swap the formalization and keep the method; drop or perturb one observation; split the data in time; swap the evaluator). State exactly what the combination does that neither source does alone, and which rows of the signature table are not unique.` },
  { key: 'skeptic', prompt: `YOUR ANGLE: evaluation first, as a skeptic. Design the experiment before the mechanism. Choose the families and generators, the withheld seeds, every baseline that could tie or beat repair (always the more general representation, always the more conservative decision, a fixed window, a fixed robust estimator), the metric and the thresholds. Work out by a small probe with ${S}/venv-mind/bin/python, if you can do it in a few minutes, whether "always the more general representation" already ties an oracle on your families; if it does, the family cannot show a gain and you must change it or say so. Then design the cheapest mechanism that could pass honestly. Say plainly where repair must lose and what a NO_GAIN result would look like.` },
]

phase('Design')
const results = await pipeline(
  ANGLES,
  a => agent(COMMON + '\n' + a.prompt, { label: 'design:' + a.key, phase: 'Design', schema: DESIGN_SCHEMA }),
  (design, a) => {
    if (!design) return null
    return agent(`You are an adversarial reviewer. Another session wrote the design below for "representation repair" on the UNIIMENTE kernel's compile route. Your job is to REFUTE it, not to improve its prose. The repository is READ-ONLY for you at ${TREE} (8d205324). Do not edit, commit, push or post. You may run small read-only probes with ${S}/venv-mind/bin/python (PYTHONPATH=${TREE}); scratch files only under ${S}/repr-design/attack-${a.key}/.

Founder's minimum test, verbatim: "two representations of a withheld problem produce conflicting recommendations; GREG identifies the invalid assumption and improves the final decision against a simple fixed-representation baseline." Also: "Distinguish erroneous observation, assumption, formalization, method, implementation, evaluator, and environmental change." "Inspect existing mechanisms first; extend canonical owners rather than creating a new permanent subsystem for each name." "Do not produce unsupported probability estimates or arbitrary process-quality scores."

Check each of these and answer with evidence (path:line or a probe's output):
1. Are the design's claims about existing code true? Open the cited lines.
2. Is "identifies the invalid assumption" circular: does the generator's label equal the test's own statistic, so that the identification proves nothing? What would make it non-circular?
3. Does a simple baseline tie or beat the proposed arm by construction (always the more general representation; always the more conservative decision; a fixed robust estimator)? If you can probe it in a few minutes, do.
4. Evaluator leakage: can the mechanism see the truth it is scored on, or were the thresholds tunable after the fact?
5. Does it reach a real GREG path (cognition.reason -> compile -> receipt), or is it a free-standing harness?
6. Does it create a second owner (a new entry point, registry, ledger, router or authority path), or touch greg/genesis.py, a frozen evidence file or a protected artifact?
7. Which of the seven classes does it claim to separate without an executed check that could tell them apart?
8. Is it finishable and verifiable by one builder in one session? What must be cut?
Default to "refuted" on any point you cannot confirm.

THE DESIGN (${a.key}):
Title: ${design.title}
Seam files: ${JSON.stringify(design.seam_files)}
Families: ${JSON.stringify(design.families)}
Baselines: ${JSON.stringify(design.baselines)}
Thresholds: ${JSON.stringify(design.thresholds)}
Its own strongest objection: ${design.strongest_objection}
Facts it says it verified: ${JSON.stringify(design.facts_verified)}

${design.design_markdown}`, {
      label: 'attack:' + a.key, phase: 'Attack',
      schema: {
        type: 'object',
        properties: {
          survives: { type: 'boolean', description: 'true only if no fatal point stands' },
          fatal_points: { type: 'array', items: { type: 'string' } },
          false_code_claims: { type: 'array', items: { type: 'string' } },
          baseline_that_ties_or_beats: { type: 'string' },
          required_changes: { type: 'array', items: { type: 'string' } },
          worth_keeping: { type: 'array', items: { type: 'string' } },
          probes_run: { type: 'array', items: { type: 'string' } },
        },
        required: ['survives', 'fatal_points', 'required_changes', 'worth_keeping'],
      },
    }).then(attack => ({ angle: a.key, design, attack }))
  },
)

const kept = results.filter(Boolean)
log(`${kept.length} of ${ANGLES.length} designs returned with an attack`)

phase('Synthesize')
const brief = await agent(`You are writing ONE build brief for "representation repair" on the UNIIMENTE kernel's compile route, from three independent designs and the adversarial review of each. The repository is READ-ONLY for you at ${TREE} (8d205324). Do not edit, commit, push or post. You may run small read-only probes with ${S}/venv-mind/bin/python (PYTHONPATH=${TREE}); scratch files only under ${S}/repr-design/synth/.

Founder's words, verbatim: "Detect when an answer is correct for the wrong problem. Distinguish erroneous observation, assumption, formalization, method, implementation, evaluator, and environmental change. Generate competing representations and test their implications. Minimum test: two representations of a withheld problem produce conflicting recommendations; GREG identifies the invalid assumption and improves the final decision against a simple fixed-representation baseline." "Inspect existing mechanisms first; extend canonical owners rather than creating a new permanent subsystem for each name." "Do not lower a test threshold after seeing a failure." "Do not produce unsupported probability estimates or arbitrary process-quality scores."

Rules for the brief:
- Take the design that survived its attack best as the base, graft what the reviews marked worth keeping from the others, and apply every required change. Where a reviewer showed that a baseline ties by construction, change the family or drop it. Where a class cannot be separated by an executed check, the brief must say the mechanism reports it as not separated.
- Do not average. Where the designs disagree, choose and give the reason in one sentence.
- Verify by opening the file any claim about existing code that the brief relies on and that a reviewer disputed.
- The brief must be buildable and verifiable by one careful builder in one session. Cut scope to fit and list what was cut as remaining obligations (cut work stays owed; it is not dropped).
- Qualitative dispositions only; no invented scores.

The brief must contain, in this order: (1) the effect and the founder's minimum test; (2) the seam (files, functions, request shape, receipt fields); (3) the mechanism (representation, executable assumption tests, conflict detection, cause classification with the classes it separates and the ones it reports as not separated); (4) the families (two or three), each with representations, disputed assumption, test, decision, ground truth; (5) the pre-registration text, ready to commit before any withheld run: arms, baselines, metric, thresholds, number of items, seeds and why they are unspent, the rule for GAIN / NO_GAIN / REGRESSION, and where repair is expected to lose; (6) the tests that fail on 8d205324 and pass after; (7) the mutants the gate must catch; (8) what is cut and stays owed; (9) the dissent that remains between the designs.

INPUT (three designs, each with its adversarial review):
${JSON.stringify(kept.map(k => ({ angle: k.angle, title: k.design.title, design: k.design.design_markdown, seam_files: k.design.seam_files, families: k.design.families, baselines: k.design.baselines, thresholds: k.design.thresholds, classes_separable: k.design.classes_separable, classes_not_separable: k.design.classes_not_separable, strongest_objection: k.design.strongest_objection, attack: k.attack })), null, 1)}`, {
  label: 'synthesize', phase: 'Synthesize',
  schema: {
    type: 'object',
    properties: {
      base_design: { type: 'string' },
      brief_markdown: { type: 'string' },
      preregistration_markdown: { type: 'string' },
      files_to_change: { type: 'array', items: { type: 'string' } },
      cut_and_owed: { type: 'array', items: { type: 'string' } },
      remaining_dissent: { type: 'array', items: { type: 'string' } },
    },
    required: ['base_design', 'brief_markdown', 'preregistration_markdown', 'files_to_change', 'cut_and_owed', 'remaining_dissent'],
  },
})

return { designs: kept.map(k => ({ angle: k.angle, title: k.design.title, survives: k.attack ? k.attack.survives : null, fatal: k.attack ? k.attack.fatal_points : null })), brief }
