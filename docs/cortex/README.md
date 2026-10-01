# Polyintelligence Cortex — Seed Experiment

The `cortex` package is the seed of GREG's Polyintelligence Cortex: a router that classifies a problem's
geometry, checks which cognitive organs are eligible for it, runs the eligible ones under a budget, attacks
their output with an independent verifier, and returns a recommendation, abstention, bounded test or handoff
together with a content-addressed receipt.

**Status:** cortex 0.1.3 · five seed organs `SANDBOXED` · 24 reserved families registered and disabled ·
frozen held-out result `INCONCLUSIVE` · **not promoted**. See [`SEED_EXPERIMENT_REPORT.md`](SEED_EXPERIMENT_REPORT.md).

Source of requirements: the verbatim build prompt in
[`docs/intent/sources/POLYINTELLIGENCE-CORTEX-BUILD-PROMPT-SEED-V0.1-2026-09-30.md`](../intent/sources/POLYINTELLIGENCE-CORTEX-BUILD-PROMPT-SEED-V0.1-2026-09-30.md).
Every line of it is mapped to a status and evidence in [`BUILD_PROMPT_TRACEABILITY.json`](BUILD_PROMPT_TRACEABILITY.json),
which `tests/unit/test_cortex_traceability.py` keeps honest.

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
| `solver_macro_cognitive` | Solver / macro-cognitive intelligence | Semantic, Fermi, Formal (Z3), Evidence/Causal | mechanism design, graph search, CP-SAT, Bayesian, bandit, simulation twin |
| `developmental_morphogenetic` | Developmental / morphogenetic intelligence | — | constraint release, evolutionary, MICA field, morphogenetic, program synthesis |
| `meta_polyintelligence_cortex` | Meta-intelligence / Polyintelligence Cortex | adversarial verifier (and the router itself) | value of information, active inference, global workspace |

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
| `cortex.formal.z3@0.1.1` | requirement → model → reverse translation → discrepancy check → counterexample search → Z3 | `formal` | `FORMALIZATION_INCOMPLETE`, `WORLD_UNVERIFIED`, `DEPENDENCY_UNAVAILABLE`, `TIMEOUT`, `INCONCLUSIVE`, `BUDGET_EXHAUSTED` |
| `cortex.evidence_causal@0.1.0` | evidence rules (provenance, freshness, contradictions, missing observations); stratified/linear adjustment with bootstrap CI and refutations, only under declared identification | `evidence_assessment`, `causal_estimate` | `INSUFFICIENT_EVIDENCE`, `CONTESTED`, `NOT_IDENTIFIED`, `MALFORMED_INPUT` |
| `cortex.verifier.adversarial@0.1.0` | rule-based, model-free attack on artifacts and evidence; records shared dependencies | `verifier_findings` | findings only lower a disposition; a critical finding blocks `recommend` |

## Contracts

JSON Schema 2020-12 in `contracts/`, validated strictly by `cortex/schemas.py` (deliberately not added to the
shared-boundary allowlist):

| Contract | Example (generated by a real run) |
| --- | --- |
| `cortex-problem-geometry` | [`examples/problem-geometry-formal.json`](examples/problem-geometry-formal.json) |
| `cortex-intelligence-genome` | [`examples/genome-formal-z3.json`](examples/genome-formal-z3.json), [`examples/genome-reserved-disabled.json`](examples/genome-reserved-disabled.json) |
| `cortex-proof-artifact` | [`examples/proof-formal.json`](examples/proof-formal.json), `proof-estimation`, `proof-evidence_assessment`, `proof-causal_estimate`, `proof-semantic_sourced` |
| `cortex-receipt` | eight receipts in [`examples/`](examples/), one per disposition path, incl. victim-protection handoff |
| `cortex-routing-memory` | [`examples/routing-memory-verified-success.json`](examples/routing-memory-verified-success.json) |

Regenerate with `python -m cortex.examples --out docs/cortex/examples`. Receipts carry measured expenditure, so
their ids change between runs; states and dispositions do not.

## Reproduce the benchmark

```bash
pip install -r requirements-dev.txt -r requirements-cortex.txt

# tests: contracts, gates, routes, pipeline, learning, evaluation integrity, traceability
python -m pytest -q tests/unit/test_cortex_gates_genome.py tests/unit/test_cortex_routes.py \
    tests/unit/test_cortex_pipeline.py tests/unit/test_cortex_traceability.py

# mutation check: 18 safeguard-removing mutants on a scratch copy; all must be caught
python scripts/ci/check_cortex_mutants.py

# development partitions (no freeze needed)
python -m cortex.evaluation.run --partition smoke --out smoke.json
python -m cortex.evaluation.run --partition dev --out dev.json

# reported partition: refused unless every frozen input hashes to cortex/evaluation/freeze-v<version>.json
python -m cortex.evaluation.run --partition heldout --out heldout.json
```

The LLM baselines (`always_llm`, `llm_committee`) need the configured local model (`egregore.local_model`,
default `qwen3.5:4b` behind an OpenAI-compatible endpoint on loopback, e.g. Ollama). Without it they are reported
`NOT_RUN` — never simulated — and the exit stays `INCONCLUSIVE`. To run them:

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
| `cortex/organs/` | the five seed organs |
| `cortex/memory.py` | outcome-conditional competence ledger; Kernel causal-memory adapter |
| `cortex/evaluation/` | suites, scoring, arms, runner, freeze manifests |
| `cortex/examples.py` | contract examples from real runs |
| `scripts/ci/check_cortex_mutants.py` | mutation check |
