# GREG bounded cognition

GREG can now run structured mathematical and review tasks through its existing signed mission lifecycle. It selects an eligible specialized method, retains a typed receipt and proof, reobserves supported computations through the separate appraiser, and derives local competence and computational cell state from the canonical journal.

Install the optional numerical dependencies and inspect or prepare a mission:

```sh
python -m pip install -r requirements-cognition.txt
python -m greg cognition inventory
python -m greg cognition mission --request examples/cognition/request.json --id m:exact --field output.exact --equals '"3"' --print-only
```

On an initialized and enrolled body, submit the ordinary mission with the existing founder key:

```sh
python -m greg cognition mission --request examples/cognition/request.json --id m:exact --field output.exact --equals '"3"' --key /path/to/founder.pem
python -m greg run
python -m greg cognition knowledge
```

The implementation includes 20 families: set-point micro rules; rational arithmetic and degree-at-most-four real polynomial roots; nonnegative product interval estimates; linear real-variable Z3 feasibility; bounded integer CP-SAT optimization; explicit graph and state search; Beta-Bernoulli updates; declared randomized differences in means; bounded PID; finite information value; seeded Bernoulli simulation; finite zero-sum minimax; protection review packets; population z-score anomalies; finite-horizon fully observed MDPs; local semantic interpretation; human review packets; independent-group quorums; and fixed-quadratic differential evolution. Every family has a declared scope and abstention boundary. Examples and the frozen assessment supply bounded inputs.

`cognition.solve` compiles an explicit typed operation, checks dependency and registry eligibility, selects among eligible methods using appraised local competence and cost/latency estimates, executes a fixed reviewed worker, and checks the returned artifact. Unknown, detached, unavailable, expired, prohibited, unidentified, incomplete and high-consequence world-unverified requests abstain.

`cognition.compose` performs one to four independent first passes within a shared declared budget. It preserves question identity, epistemic jurisdiction, assumptions and dissent. It does not vote truth or claim a measured composition advantage.

`cognition.knowledge` returns current competence and bounded cell state replayed from the existing journal. Cell identity and credit survive restart; later appraisal refutation removes current credit. Native producer witnesses must match a signed mission's sensor, exact input digest, method version and fully verified current appraisal before settlement can earn routing credit.

Receipts distinguish supplied-model formal validity, empirical validity and legitimate authority. Empirical validity remains `WORLD_UNVERIFIED`; authority remains `EXISTING_KERNEL_GATE_REQUIRED`; `authority_created` is false. Supplied completeness and randomization flags are assumptions rather than independent findings. High-consequence requests cannot acquire action authority from solver success. Law, consent and rights constraints cannot be traded for upside. Oversized proof abstains so retained receipts preserve all proof bytes.

Workers enforce bounded input/output, time, CPU and memory on supported POSIX hosts using the existing isolation mechanism. Supplied code is never evaluated. Numerical extras and bounded synthetic cases do not establish general cognition, calibrated real-world predictions, identified real-world causality, autonomous homeostasis, optimality beyond declared solver/model limits or an external product outcome. Compute limits are domain-specific ceilings; actual operations and energy are not generally measured.

The semantic seam reuses the existing local-model client only when GREG's effective configuration explicitly selects an installed local Ollama model. Hosted-provider fallback is disabled. Live local inference and comparative LLM baselines were unavailable in the development environment; missing local model evidence abstains.

This change adds capabilities to the existing manifests and genomes, signed inbox, Gate, body, appraiser and event journal. It creates no second service, identity, ledger or consequence authority. Existing detach, stop, pause and lifecycle controls apply. Rollback detaches the added capabilities and reverts the patch while retaining history.

Run the focused checks and frozen assessment:

```sh
python -m pytest -q tests/unit/test_greg_cognition.py tests/integration/test_greg_cognition_mission.py
python -m greg.cognition.benchmark
```

The frozen assessment contains 22 structured operation and abstention cases. It exits unsuccessfully on a contract failure. Comparative scoring requires callable baselines with compatible answer/abstention structure and reported cost. Without all required baselines and an acceptance/utility policy, superiority and cross-geometry regret remain unmeasured. Local evidence is in `tests/evidence/cognition-2026-09-30/verification.json`; GitHub CI is separate evidence.
