# Seed Cortex — GREG Polyintelligence Cortex: Seed Genome v0.1

*Naming (review pass 2 §63): these organs are the **Seed Cortex**, not the full Polyintelligence Cortex. The founder's 2026-10-01 build prompt titles the experiment "Seed Experiment v0.1"; that title is kept wherever it is quoted.*

The `cortex` package is the seed of GREG's Polyintelligence Cortex: a router that classifies a problem's
geometry, checks which cognitive organs are eligible for it, runs the eligible ones under a budget, attacks
their output with an independent verifier, and returns a recommendation, abstention, bounded test or handoff
together with a content-addressed receipt.

**Status:** cortex 0.1.6 · six seed organs `SANDBOXED` · 28 reserved families registered and disabled ·
0.1.5 held-out result `INCONCLUSIVE` (declared baselines `NOT_RUN`) · 0.1.6 held-out result `GAIN_ABSENT` with both
declared baselines run (routed 1.000, no critical error; always-LLM 0.905, two; committee 0.929, one; paired-gain lower
bounds 0.024 and 0.000 against the frozen 0.05), see [`SEED_EXPERIMENT_REPORT.md`](SEED_EXPERIMENT_REPORT.md) § 0.1.6 and
[`tests/evidence/cortex-seed-v0.1.6/`](../../tests/evidence/cortex-seed-v0.1.6/README.md) · **not promoted**.
Convergence with the other cognition lineages and the standing-runtime binding: [`CONVERGENCE_2026-10-13.md`](CONVERGENCE_2026-10-13.md).

Source of requirements: the verbatim build prompt in
[`docs/intent/sources/POLYINTELLIGENCE-CORTEX-BUILD-PROMPT-SEED-V0.1-2026-09-30.md`](../intent/sources/POLYINTELLIGENCE-CORTEX-BUILD-PROMPT-SEED-V0.1-2026-09-30.md).
Every line of it is mapped to a status and evidence in [`BUILD_PROMPT_TRACEABILITY.json`](BUILD_PROMPT_TRACEABILITY.json),
which `tests/unit/test_cortex_traceability.py` keeps honest. Every section of the two earlier AI review passes has a
disposition in [`verbatim-register.json`](verbatim-register.json), checked by `tests/unit/test_cortex_register.py`.

## Authority boundary

Cognition creates no authority. Every receipt carries `authority_created: false` and
`execution_authority: "none"`, enforced by its schema. The package cannot import the Consequence Gate, adapters
or any actuator (`test_cortex_imports_nothing_that_can_act`). External consequences continue through the Kernel
policy engine → capability grant → Consequence Gate. Financial and irreversible questions, legal, normative and
institutional questions, and human-led victim-protection actions are handed off, never recommended.

## Five layers

The build prompt's five layers are a profile field (`profile.layer`) on each genome — selectable scales, not
services. One process runs everything.

| Layer (`profile.layer`) | Build prompt name | Enabled in the seed | Registered, disabled |
| --- | --- | --- | --- |
| `primitive_basal` | Primitive / basal intelligence | — | feedback control, molecular micro-agents, anomaly patterning |
| `distributed_collective` | Distributed / collective intelligence | — | ecology market, hive quorum, immune, slime network, stigmergy, swarm PSO, human panel |
| `solver_macro_cognitive` | Solver / macro-cognitive intelligence | Semantic, Fermi, Formal (Z3, incl. certified optimization), Evidence/Causal, Deterrence | mechanism design, graph search, heuristic search, exact symbolic, CP-SAT, Bayesian, bandit, simulation twin |
| `developmental_morphogenetic` | Developmental / morphogenetic intelligence | — | constraint release, evolutionary, MICA field, morphogenetic, program synthesis |
| `meta_polyintelligence_cortex` | Meta-intelligence / Polyintelligence Cortex | adversarial verifier (and the router itself) | value of information, active inference, global workspace, mental models, metaconsensus |

The earlier AI review used a different five-layer naming (L1–L5); `REVIEW_LAYER_MAP` in `cortex/contracts.py`
reconciles the two and both are preserved. Every biological concept attached to a genome must name its
mechanism, state variables, interface, feedback loop, measurable behavior, test and failure condition, or
registration is refused.

## Pipeline

```
problem → geometry → cognitive eligibility → budget → route or bounded composition
        → typed artifact → adversarial verification → abstain / recommend / bounded test / handoff → receipt
```

Routing policy `cortex-route-policy/0.1` is deterministic: the structure of the payload selects routes
(`formal_model` → Formal, `estimation_model` → Fermi, `claim` → Evidence/Causal, `sources` → Semantic). A model
may *propose* geometry features through the `proposer` hook; a proposal is kept only when the structured payload
supports it, and its confidence is recorded. When options are present, hard gates run before any ranking and
ranking sees only options that passed every gate.

## Routes

| Organ | Mechanism | Proof class | Explicit non-OK states |
| --- | --- | --- | --- |
| `cortex.semantic@0.1.0` | existing `egregore.local_model` client; only claims quoting an exact span of a cited source survive | `semantic_sourced` | `DEPENDENCY_UNAVAILABLE`, `BUDGET_EXHAUSTED`, `INSUFFICIENT_EVIDENCE`, `MALFORMED_INPUT` |
| `cortex.estimation.fermi@0.1.0` | unit-checked decomposition, Gaussian-copula Monte Carlo, sensitivity, reference class | `estimation` | `DIMENSION_MISMATCH`, `CONTESTED`, `INSUFFICIENT_EVIDENCE`, `MALFORMED_INPUT` |
| `cortex.formal.z3@0.2.0` | requirement → model → reverse translation → discrepancy check → counterexample search → Z3 feasibility, entailment, or optimization with an independent UNSAT optimality certificate | `formal` | `FORMALIZATION_INCOMPLETE`, `WORLD_UNVERIFIED`, `DEPENDENCY_UNAVAILABLE`, `TIMEOUT`, `INCONCLUSIVE`, `BUDGET_EXHAUSTED` |
| `cortex.evidence_causal@0.1.0` | evidence rules (provenance, freshness, contradictions, missing observations); stratified/linear adjustment with bootstrap CI and refutations, only under declared identification | `evidence_assessment`, `causal_estimate` | `INSUFFICIENT_EVIDENCE`, `CONTESTED`, `NOT_IDENTIFIED`, `MALFORMED_INPUT` |
| `cortex.deterrence.accountability@0.1.0` | Becker expected-value condition (gain − p_detect · p_sanction · sanction) over declared ranges; closed lawful intervention vocabulary; coercive and hard-harm interventions refused; levers labelled certainty / severity / opportunity; actions reaching another party handed off | `deterrence_assessment` | `INSUFFICIENT_EVIDENCE`, `MALFORMED_INPUT` |
| `cortex.verifier.adversarial@0.1.0` | rule-based, model-free attack on artifacts and evidence; records shared dependencies | `verifier_findings` | findings only lower a disposition; a critical finding blocks `recommend` |

## Receipts: truth, accountability, protection

Every receipt separates **formal validity**, **empirical validity** and **legitimate authority**, and carries an
**accountability** section: the strongest counterargument the verifier found, a falsification condition for each
route's claim, and the missing information that would resolve the question. When victim protection is relevant,
declared actions are ordered (protect now → preserve evidence → contain → safe contact → escalate → repair → prevent
recurrence); unmeasured harm, unpreserved evidence, a missing safe channel or retaliation risk without disclosure
controls are *gaps* that force a human handoff; and the receipt records only whether a person or safe channel was
declared — never who or which.

## Deterrence, lawfully

Deterrence here means changing the expected value of misconduct for a risk-neutral actor (Becker 1968): misconduct
pays when the gain exceeds detection probability × sanction probability × sanction. The organ samples the declared
ranges, then ranks only interventions from a closed lawful vocabulary (detection, evidence preservation, access
control, process change, independent audit, victim support; and, handed off to the competent authority, reporting,
contractual remedies, transparency, restitution). Threats, retaliation, intimidation, extortion, deception, doxxing,
unconsented surveillance, vigilantism, harassment and coercion are refused and never ranked. Each intervention is
labelled by the lever it moves; a best option that moves only severity is flagged, because the evidence supports
certainty of apprehension far more consistently (Nagin 2013).

## Contracts

JSON Schema 2020-12 in `contracts/`, validated strictly by `cortex/schemas.py` (deliberately not added to the
shared-boundary allowlist):

| Contract | Example (generated by a real run) |
| --- | --- |
| `cortex-problem-geometry` | [`examples/problem-geometry-formal.json`](examples/problem-geometry-formal.json) |
| `cortex-intelligence-genome` | [`examples/genome-formal-z3.json`](examples/genome-formal-z3.json), [`examples/genome-reserved-disabled.json`](examples/genome-reserved-disabled.json) |
| `cortex-proof-artifact` | [`examples/proof-formal.json`](examples/proof-formal.json), `proof-estimation`, `proof-evidence_assessment`, `proof-causal_estimate`, `proof-semantic_sourced` |
| `cortex-receipt` | eleven receipts in [`examples/`](examples/), one per disposition path, incl. certified optimization, victim-protection handoff and deterrence (internal control recommended; report to authority handed off) |
| `cortex-routing-memory` | [`examples/routing-memory-verified-success.json`](examples/routing-memory-verified-success.json) |

Regenerate with `python -m cortex.examples --out docs/cortex/examples`. Receipts carry measured expenditure, so
their ids change between runs; states and dispositions do not.

## 0.1.6 additions

**Standing-runtime binding.** `egregore/cortex_proposer.py` attaches the cortex to `StandingCognitionRuntime`'s
existing proposer slot. Every call ledgers one `cortex.receipt`; `recommend` becomes a `draft.prepare` review
candidate, `handoff` a `human.adjudicate` candidate, both `internal_write` with `execution_authority: none`;
`abstain` and `bounded_test` propose nothing (the receipt names what is missing). The semantic organ's model budget
is clamped to the proposer's ceiling (default 0).

```python
from cortex.routing import Cortex
from egregore.cortex_proposer import CortexProposer, REQUEST_KEY
proposer = CortexProposer(Cortex(), ledger)                       # consequence-inert
runtime = StandingCognitionRuntime(ledger=ledger, proposers={proposer.name: proposer}, evaluators=...)
runtime.tick(trigger_id=..., signal_ids=..., resources=..., context={REQUEST_KEY: {"problem": problem_dict}})
```

**Epistemic Finality Rule and CapabilityDeficit.** `cortex.routing.FINALITY_RULE` (`epistemic-finality/0.1`) gives
every epistemic class exactly one deciding jurisdiction: formal, empirical, semantic, strategic or human authority.
Each receipt records it in `route.finality`, per route for a composed question, so no part's proof is promoted to the
whole. When the repertoire cannot answer (`UNSUPPORTED_GEOMETRY`, `NO_ELIGIBLE_METHOD`), the receipt carries a typed
`capability_deficit`: the geometry, its jurisdiction, the registered-but-disabled families and the resolution order
(existing capability first, new architecture last). It is the input a later capability-formation loop would consume;
it requests formation and authorizes nothing. A handoff or a malformed input is not a deficit. One receipt is one
observation, so the record says `verified: false`: a capability-genesis loop verifies a deficit by its recurrence
across recorded cycles and diagnoses it before proposing anything (PR #129's `DeficitDetector` is that mechanism;
a trial merge of #129 with this branch passes the full suite).

**Pre-run independent review (2026-10-14).** Before the reported run, three reviewers attacked the 0.1.6 changes and
an independent verifier re-ran each finding; 14 of 17 were confirmed and fixed with fail-before/pass-after tests:
a replayed arm with any missing reply is `NOT_RUN` (an unasked prompt is never a baseline failure); the freeze
hashes every in-repo module the scored path imports; transcripts refuse repeated keys and runs refuse repeated arms;
provenance hashes the bytes that served the replies and names the replay code; a declared class without its input is
`INSUFFICIENT_EVIDENCE`, not a capability gap; a payload part with no eligible route is unanswered and never
recommended around; disabled families come from the registry; a handoff carries no deficit; options are parsed before
any organ spends; settlement checks the receipt's content address, settles only a route that ran, and settles a method
once per receipt; the proposer sets the mandate reference instant from its own clock and checks the model-call ceiling
on the receipt. The mutation check now deselects the freeze-hash tests, which had counted any edit to frozen code as
caught; all 43 mutants are caught by behavioural tests. The 42 held-out routed items are unchanged on every scoring
field.

**Replayed baseline arms.** When no model is reachable from the evaluation process, the declared arms can be run
from a transcript of replies produced elsewhere, keyed by `sha256(system + NUL + user)`; a missing reply is an
error on that item, never a guess; the frozen inputs are untouched; the model's provenance replaces the
local-model disclosure on the results. A second transcript may serve the routed seed's semantic organ with the same
model, as the frozen disclosure pre-registers.

```bash
python -m cortex.evaluation.replay --answers transcript.json --semantic-answers semantic.json \
    --provenance provenance.json --partition heldout --out heldout-results.json
```

**Defect fixes.** See the 0.1.6 row of the version table in `SEED_EXPERIMENT_REPORT.md` and
`tests/unit/test_cortex_defect_fixes.py`.

## Reproduce the benchmark

```bash
pip install -r requirements-dev.txt -r requirements-cortex.txt

# tests: contracts, gates, routes, pipeline, learning, evaluation integrity, traceability
python -m pytest -q tests/unit/test_cortex_gates_genome.py tests/unit/test_cortex_routes.py \
    tests/unit/test_cortex_pipeline.py tests/unit/test_cortex_traceability.py tests/unit/test_cortex_register.py

# mutation check: 43 safeguard-removing mutants on a scratch copy; behavioural tests must catch each (freeze-hash checks deselected)
python scripts/ci/check_cortex_mutants.py

# development partitions (no freeze needed)
python -m cortex.evaluation.run --partition smoke --out smoke.json
python -m cortex.evaluation.run --partition dev --out dev.json

# reported partition: refused unless every frozen input hashes to cortex/evaluation/freeze-v<version>.json
python -m cortex.evaluation.run --partition heldout --out heldout.json
```

The LLM baselines (`always_llm`, `llm_committee`) need the configured local model (`egregore.local_model`,
default `qwen3.5:4b` behind an OpenAI-compatible endpoint on loopback, e.g. Ollama). Without it they are reported
`NOT_RUN` — never simulated — and the exit stays `INCONCLUSIVE`. A recorded transcript can serve them instead
(`cortex/evaluation/replay.py`, see § 0.1.6 additions). To run them against a local model:

```bash
ollama pull qwen3.5:4b && ollama serve &
python -m cortex.evaluation.run --partition heldout --out heldout-with-baselines.json
```

Changing any frozen input (suites, scoring, arms, generators, route policy, organ code, budgets, thresholds)
makes the held-out run refuse. A change is a new cortex version with its own freeze; earlier manifests and results
are kept in `cortex/evaluation/` and `tests/evidence/cortex-seed-v*/`.

## Files

| Path | Role |
| --- | --- |
| `cortex/contracts.py` | vocabularies, `Problem`, `ProblemGeometry`, harm vector, victim protection, results |
| `cortex/genome.py` | `IntelligenceGenome` projection of the Capability Genome; seed organs; reserved families |
| `cortex/gates.py` | hard gates, permission-bearing records, Pareto ranking after gates |
| `cortex/routing.py` | geometry derivation, eligibility, budget, routes, disposition, receipts |
| `cortex/organs/` | the six seed organs |
| `cortex/memory.py` | outcome-conditional competence ledger; Kernel causal-memory adapter |
| `cortex/evaluation/` | suites, scoring, arms, runner, freeze manifests |
| `cortex/examples.py` | contract examples from real runs |
| `scripts/ci/check_cortex_mutants.py` | mutation check |
| `cortex/evidence_refs.py` | resolves evidence references in the traceability documents |
| `docs/cortex/INVENTION_DOSSIER.md`, `invention.json` | mechanism lineage, novelty boundary, decision |
