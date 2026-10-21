# Whole-machine acceptance harness

Directive 2026-10-13, section 33 (Missions A–L) and section 35 (the full-machine completion contract).

| File | What it holds |
| --- | --- |
| `missions.json` | Each obligation of Missions A–L, the test nodes that demonstrate it, the evidence tier those tests can establish, and every known gap with its dependency. Mission L also carries the nine-link trace (Goal → Mind → Organs → Body → Action → Evidence → Outcome → Learning → Updated Goal), with an owner, code paths, proofs and a tier for each link. |
| `completion-contract.json` | One record per required function of the Body, Mind, Organs and the operating loop, holding the section-35 fields, plus the fifteen current-machine conditions with their assessments. A function's evidence tier is **computed** from the mission requirements it cites. It is never declared. |
| `missions.schema.json`, `contract.schema.json` | JSON Schema 2020-12 for both files. |

```
python -m acceptance check                      # static: schemas, nodes, symbols, trace, contract refs
python -m acceptance run --out report.json      # run every cited node once and report
python -m acceptance run --mission H            # one mission
python -m acceptance report --outcomes o.json   # report from recorded outcomes
```

## Rules

- A requirement reaches its declared tier only when **every** cited node is collected and passes.
  A failure, an error, a skip, or a node that collects nothing leaves it at its implementation
  status, and the observed reason is recorded. A skip is never counted as a pass.
- Tests can establish at most `BODY_VERIFIED`. `FOUNDER_ACCEPTED`, `AUTHORIZED_LIVE`,
  `EXTERNALLY_VERIFIED` and `COMMERCIAL_OUTCOME_VERIFIED` need records that no test produces, so the
  manifest cannot declare them and the harness never assigns them.
- Each mission, and each contract function, is only as verified as its least-verified requirement.
  `BLOCKED_WITH_REASON` dominates.
- Every founder key used in this evidence is a per-test key. None of it is Alfonso's.
- `run` exits 0 only when every tested requirement attains its declared tier.
- The harness reads code and runs tests. It does not grant, attach or activate anything.

Recorded runs are kept under `docs/evidence/acceptance/`.
