# Seed Genome on the canonical GREG path

GREG can now execute a signed, bounded structured reasoning mission, use real heterogeneous methods, check their artifacts in a separate process, retain a conditional receipt, recover after SIGKILL, and retain a separately approved synthetic or reported assessment. This is a development implementation. It has not demonstrated routing superiority, external acceptance, or a founder-owned device closure.

The controlling source is [the October 1 directive](../intent/sources/POLYINTELLIGENCE-SEED-2026-10-01.txt). [The requirement register](SEED_GENOME_REQUIREMENTS.json) retains every nonblank source line and all **122** Appendix A identifiers. The earlier PR141 register's 121 rows describe a different source inventory. Neither count proves completion. Section limitations and executable evidence govern each claim.

## Run a bounded mission

From the source checkout, install the optional solver dependencies into your chosen development Python environment:

```bash
python -m pip install -r requirements-dev.txt -r requirements-cognition.txt
python -m greg --home /path/to/development-body mission new cognition --problem docs/cortex/examples/seed-genome/mixed.json --print-only
python -m greg --home /path/to/development-body mission new cognition --problem docs/cortex/examples/seed-genome/mixed.json --key /path/to/your-existing-founder-key.pem
python -m greg --home /path/to/development-body run --tick-seconds 1
python -m greg --home /path/to/development-body status
```

Use the existing GREG enrollment and body setup instructions in [greg/README.md](../../greg/README.md). These commands do not create a model server, acquire weights, provision hardware, or authorize an external action. Review the printed mission before signing it. Use a new problem ID when changing inputs; the durable receipt binds an ID to the exact input digest.

The sample combines interval estimation and CP-SAT allocation. A successful result says the computation agrees with its original encoded assumptions. It does not establish that those assumptions describe the world. The console and authenticated phone status project the methods, rationale, result, remaining limits and next step. Actual iPhone and Chromebook rendering have not been verified here.

## Execution and ownership

| Owner | Behavior |
| --- | --- |
| `greg/cli.py`, `greg/templates.py` | Existing signed MISSION entry point; exact cognition target and read-only light cone |
| `greg/missions.py`, `greg/authority.py` | Existing scheduler, worker identity, grants and Consequence Gate; no second authority service |
| `capabilities/genome.py`, `greg/capabilities.py` | Compatible optional cognitive profiles in the existing GenomeRegistry; empty legacy profiles preserve manifest digests |
| `cortex/seed/` | Pure bounded contracts, native method variants, independent arithmetic/constraint/binding checks and rich geometry projections |
| `greg/cognition/seed_path.py`, `greg/cognitive_worker.py` | Bounded process invocation, original-input checking and canonical journal events |
| `greg/routing.py` | Read-only conditional outcome projection; no autonomous weight or permission update |
| `greg/path.json` | One project path; P0–P13 and C1–C8 are a subordinate workstream, not another primary node |

PR137's runtime is the stack base at `3d2bb1762ff709ce74d3053aced060e70d4e6674`. The 25 commits from PR141 through `71b6f74` are preserved in its original branch and cherry-picked in the local build history, with their authors and historical evaluation. The connector upload carries the same file tree as an additive commit on PR137, with those source commit references; it does not claim identical commit ancestry. Its old router remains a sandbox comparison, not the product scheduler. The pure new variants are owned by the same `cortex` package. PR139 (`30d162b`) was inspected selectively: integration, outcome hooks, dependencies, commit summary and PR metadata/body. Its competing `egregore/cognition` runtime was not imported into this product path. Its original intent and stronger external-outcome lineage constraints remain at that commit for future extraction. PR139 and PR141 were not closed or merged.

There are five selectable scales: primitives, bounded workers, specialist methods, compositions and institutional evaluation. This implementation exercises deterministic primitives, bounded workers, specialist methods, a two-method composition and fixed evaluation. It does not implement adaptive cells, collective learning, a new ecology, or functional morphogenesis. The legacy freeze retains its historical taxonomy; the current directive controls active interpretation.

## Methods and proof limits

| Method | Real implementation | What the independent check establishes | Limit |
| --- | --- | --- | --- |
| Estimation | Decimal interval products/division, dimensions, sensitivity | Fraction arithmetic and dimensions agree | Nonnegative scenario bounds; no distribution, independence or anchor invention |
| Formal | Pinned Z3 integer linear feasibility | Exhaustive enumeration over at most 50,000 assignments | SAT/UNSAT within the supplied model; UNKNOWN remains a non-answer; core is not claimed minimal |
| Optimization | Pinned OR-Tools CP-SAT | Assignment, source constraints, objective, optimum/bound/gap | Bounded integer allocation and fixed-order scheduling; FEASIBLE is not OPTIMAL |
| Evidence | Digest, freshness, exact quotations and contradiction retention | Source-byte binding and omission checks | Source quality, truth and stated stance are declarations |
| Causal | Declared randomized two-arm mean difference and uncertainty | Independent rational means/variance and sign/refutation | Conditional synthetic/reported design; no observational identification; small samples get no 95% interval |
| Semantic | Existing `greg.models.OllamaRoute`, explicit requested/served model and digest | Exact bindings and model provenance | Live model NOT_RUN; fixture proves protocol only; proposals are unverified |

The verifier has a separate process and algorithm. It shares source data, Python, repository and author with the builder. Those dependencies are recorded, not described as independent empirical review. Artifact identity, proof class, source substitution, false optimum and unsupported world/authority claims are checked. No solver certificate adjudicates values, rights, law or institutional acceptance.

The new rich geometry projection reuses `cortex.contracts.ProblemGeometry`, `ResourceLimits` and `ConsequenceVector`. It carries an extension for search space, observation, constraints, source provenance, actors, embodiment, deadline and attention. Unmeasured fields stay unknown; rejected input cannot populate asserted structural features. Twelve exposure dimensions carry declared severity plus explicit unknown likelihood, parties and reversibility. This is representation and conservative handoff, not a completed independent harm-assessment service.

## Recovery, settlement and authority

`cognition.receipt` and `cognition.outcome` are confidential events in the existing journal. No other database is added. Reusing a problem ID with changed content is refused. Observations are idempotent; a correction appends and must supersede the latest observation. Missing scores remain missing. Scores are reported assessments grouped by method version, geometry, evidence tier and conditions, not authenticated performance or causal credit.

Benchmark, synthetic, reported-observation and computation-verified tiers are distinct. A local mission appraisal supports computational integrity only. `independently_verified` real-world settlement is refused until an appropriate observation adapter exists. No outcome can edit a protected policy or autonomously promote a capability.

The signed settlement test uses the existing mission strategy/precondition path and `memory.precedents` sensor. Settlement outside the original light cone waits for a separately signed exact-scope approval. Replaying the mission or approval across restart creates no second observation.

A real CLI rehearsal SIGKILLs the body at two boundaries, then starts a new CLI process. The cognition receipt precedes the Gate action record: a kill in that gap can leave zero `mission.action` records for the computation. Recovery re-observes the retained result and does not recompute it. This proves one bounded internal computation, not universal exactly-once external effects. Recovery has a 20-second test bound; STOP persists and prevents further work. Revoked/abandoned missions do not recover authority.

Compute and verification share a 0–10 second wall envelope. Each worker has a 2 GiB address-space limit and a 12 CPU-second limit. Linux numeric/verifier workers use the existing network denial; semantic uses the existing loopback route. A stop check polls while a worker runs. Energy, maintenance, physical memory use, storage growth and total mission/persistence overhead remain unmeasured. A separately operated Ollama server is outside worker resource/cancellation enforcement; live semantic activation needs that server-specific envelope. Paid token fees are zero in these exercised paths, which is not a free-compute claim. The fixed policy performs no optional deeper reasoning; decision-specific VOI and learned attention allocation remain open.

## Frozen results and failure evidence

The [first result](evidence/seed-genome/results.json) and [first freeze](../../cortex/evaluation/seed_genome/freeze.json) are retained. The first frozen code is reconstructible at local commit `7522fb0`, preserved in the [history bundle](evidence/seed-genome/local-history.json). The bundle restores exact local authors and source commits; the connector upload uses a different commit with the same file tree. Its report's parent HEAD is supplemented by the frozen per-file digests. A scoring-text erratum: the first specification says 24 resampled families; its actual quality CI uses 20 because semantic availability is excluded.

The second freeze adds rich projection code, checks method identity and corrects that text. No route or holdout labels were optimized after the first measurement. [Version 2 results](evidence/seed-genome/results-v2.json) and [freeze](../../cortex/evaluation/seed_genome/freeze-v2.json) are preserved. Version 3 adds native solver/model/verifier cohort keys to settlement; [results](evidence/seed-genome/results-v3.json) and [freeze](../../cortex/evaluation/seed_genome/freeze-v3.json) are the current comparison. Both arms actually execute, with counterbalanced order. The proposed policy is the simple static specialist policy; there is no learned policy to compare.

There are 120 structured cases: 20 in each requested stratum. All related numeric variations stay together in heldout. These are self-authored engineering inputs related to development patterns, not independent evidence of population generalization. Twenty semantic cases test truthful unavailability, not semantic quality. Formal bounded-unknown cases exhaust the whole compute budget; native UNKNOWN is a separate controlled protocol test. Open-ended semantic/strategy quality requires the unavailable model and a predeclared independent rubric/workload. Do not call this coverage floor statistical sufficiency.

Correctness, false claims, unjustified abstention, unsupported certainty, token-fee violation and latency have predeclared weights. Authority remains a separate hard fail. Energy and full operational costs are disclosed gaps. Bootstrap intervals resample quality template families rather than pretend variants are independent tasks.

The always-LLM and strong tool-enabled local-model comparisons are NOT_RUN: no approved, licensed, resource-fit local model is configured or reachable. PR137 cannot consume this new wire contract or execute the new capability, so its comparison is a capability-absence statement, not a fabricated scored run. These gaps keep the experiment **INCONCLUSIVE**. The timing-independent gain over static rules is **zero**. No superiority, promotion, antifragility or durable compounding claim follows.

The inherited v0.1.5 heldout was independently rerun without changing its freeze: [result](evidence/seed-genome/inherited-v015-rerun.json). Its model comparisons remain unavailable too. Six new source mutations deliberately remove permission, drop a constraint, relabel UNKNOWN, replace evidence, break duplicate settlement or allow a paid key to bypass missing configuration. All six targeted tests failed as required. Infrastructure/import errors cannot count as caught mutants. The prior 26-mutant suite is retained separately.

Failures are retained in the evidence directory: an initial CANCELLED lifecycle fixture used a nonexistent state, an early recovery assertion wrongly assumed the action record had already committed, and the first broad run's evidence fixture expired while unrelated tests ran. ABANDONED is the actual lifecycle state; both crash boundaries are now tested; the ordinary fixture's freshness window is longer while explicit stale-source tests remain strict. No production rule was weakened to fix these fixtures. The final catalog check also found the new GREG input beside the closed older schema examples; the unchanged input now lives in `examples/seed-genome/`, and all 159 catalog/continuity checks passed. The failed verifier and diagnosis are retained.

## Reproduce and review

```bash
python -m pytest -q tests/unit/test_greg_cognition.py tests/integration/test_greg_cognition_process.py
python scripts/ci/check_greg_cognition_mutants.py
python -m cortex.evaluation.seed_genome.run --out /tmp/seed-genome-results.json
python -m cortex.evaluation.run --partition heldout --out /tmp/inherited-cortex-results.json
python scripts/ci/check_schema_refs.py
python scripts/ci/check_authority_singleton.py
python scripts/ci/check_sealed_developmental.py
```

The runner refuses modified frozen inputs; do not replace a freeze to make a result pass. Create a new version and preserve the old one. The canonical CI cortex job installs the optional dependencies and runs the new tests, mutations and comparison. Solver-dependent tests skip in environments that deliberately omit those optional dependencies. Local focused, full-suite and verifier logs identify their scope and commit/tree state in [the evidence manifest](evidence/seed-genome/manifest.json).

[The two-pass decision](../collaboration/deliberation-seed-genome-20261001.json) records five perspectives from one agent, alternatives, preserved dissent, downside dispositions and rollback. The scoped decision is **EXPERIMENT**. Spider-Web's external decision is **Stage-gate**: this is an internal competency substrate, with no external accepting actor, mandate, commercial control, network effect or five-outcome economic proof. Institutional market/capital claims have not earned a Commit decision.

The mechanism lineage is known portfolio selection and proof-carrying computation, mutated to per-claim eligibility, separate permission and original-input challenge; durable workflow recovery is mutated to reuse typed conditional evidence without promoting it to world truth. Their project-specific interaction creates recoverable governed mixed computation. It does not establish scientific or patent novelty. The first corpus/source research from PR141 is retained in its [dossier](INVENTION_DOSSIER.md); those citations are not a fresh exhaustive literature or security audit.

## Completion states and next gates

| State | Evidence and scope |
| --- | --- |
| IMPLEMENTED | Narrow native methods, semantic protocol, static eligibility, diverse checks, rich unknown-preserving projections and durable reported settlement |
| INTEGRATED | Existing CLI, signed mission, GenomeRegistry, grants/Gate, journal, appraisal, read surfaces and recovery |
| VERIFIED IN TESTED ENVIRONMENT | Development Linux/Python and real solver tests; self-authored benchmark; signed test keys; no model-quality, actual phone/Chromebook, commercial or world outcome proof |
| AUTHORIZED/VERIFIED FOR LIVE USE | Not established; no live activation, merge, deployment, contact, spend or authority expansion performed |

The bounded slice is usable for reviewed development. **The complete directive remains active.** Residual work includes independent harm/evidence interpretation, fuller calibration and behavioral characterization, decision-specific VOI, downstream organ and Task Fabric/lease consumption, authentic real-outcome settlement, and stronger heldout/model comparisons. Existing lawful accountability/protection/deterrence advice remains a sandbox capability; all six advantage outcomes are not demonstrated on the real GREG path.

P1–P3 are one joined delivery obligation; their partial scope is explicit rather than three complete scaffold claims. Later P4–P13, all C1–C8 mappings, Foundry-55 and approved computer-use/team/embodiment horizons remain in the existing path with owners, dependencies, budget ceilings, review and falsification triggers. None is activated by the catalog.

Alfonso remains root human authority. Global VEPMC stays **0**. The operational primary node remains N1: the Chromebook run with his key, actual interruption, appraisal and acceptance. Phone and Mac horizons remain separately gated. Root project sources named only in the review, raw Project corpus, organ repository refresh, licensed model configuration, real devices and external institutions were unavailable or outside this inspected scope; no inspection or verification is invented for them.

Rollback is additive: keep this draft unmerged or revert its integration commits, use the existing signed detach/lifecycle/STOP mechanisms on a configured development body, and preserve source, history and receipts. A rollback cannot erase effects already taken elsewhere. No such external effects were taken here.
