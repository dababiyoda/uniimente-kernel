# Whole-machine acceptance harness

Directive 2026-10-13, section 33 (Missions A–L) and section 35 (the full-machine completion contract).

| File | What it holds |
| --- | --- |
| `missions.json` | Each obligation of Missions A–L, the test nodes that demonstrate it, the evidence tier those tests can establish, how much of the obligation they show (`coverage`: covered, partial or gap), and every known gap with its dependency. `body_process_tests` lists the test files that drive a real Body process. Mission L also carries the nine-link trace (Goal → Mind → Organs → Body → Action → Evidence → Outcome → Learning → Updated Goal), with an owner, code paths, proofs and the tier those proofs can establish for each link. |
| `completion-contract.json` | One record per required function of the Body, Mind, Organs and the operating loop, holding the section-35 fields, plus the fifteen current-machine conditions with their assessments. A function's evidence tier is **computed** from the mission requirements it cites. It is never declared. |
| `missions.schema.json`, `contract.schema.json` | JSON Schema 2020-12 for both files. |

```
python -m acceptance check                      # static: schemas, nodes, symbols, trace, contract refs, real-process rule
python -m acceptance run --out report.json      # run every cited node once and report
python -m acceptance run --mission H            # one mission
python -m acceptance report --outcomes o.json   # report from recorded outcomes
```

## Rules

- A requirement reaches its declared tier only when **every** cited node is collected and passes.
  A failure, an error, a skip, or a node that collects nothing leaves it at its implementation
  status, and the observed reason is recorded. A skip is never counted as a pass.
- A tier says how strongly the cited tests ran; `coverage` says how much of the obligation they show.
  Reaching a tier is not meeting the obligation:
  - `gap`: the cited tests do not show the obligation at any tier. The requirement may not declare a
    tier, never attains one, and stays at its implementation status.
  - `partial`: the requirement can reach its tier, and the report says it covers only part of its
    obligation. Its notes name the clauses without evidence.
  - `covered`: the cited tests show the whole obligation at the declared tier.

  The summary gives both counts: how many requirements reach their declared tier, and how many of those
  cover the whole obligation and how many only part. A mission or a contract function is reported
  `partial` when any requirement it rests on is `partial` or `gap`.
- `BODY_VERIFIED` needs at least one cited node that drives a real Body process. The node's file must
  be listed under `body_process_tests`, and `check` verifies statically that its test starts the declared
  process: `greg run` (as a CLI subprocess or through a helper called with `run`), supervisord running
  `service.supervisord_program` (which runs `greg run`), or a driver subprocess whose script calls
  `Body(...).run(` (the loop `greg run` runs, with a test capability added). Calls to functions and
  fixtures in the same module are followed; anything else counts as in-process. An in-process Body
  with a test clock is `SANDBOX_VERIFIED` at most.
- Tests can establish at most `BODY_VERIFIED`. `FOUNDER_ACCEPTED`, `AUTHORIZED_LIVE`,
  `EXTERNALLY_VERIFIED` and `COMMERCIAL_OUTCOME_VERIFIED` need records that no test produces, so the
  manifest cannot declare them and the harness never assigns them.
- Each mission, and each contract function, is only as verified as its least-verified requirement.
  `BLOCKED_WITH_REASON` dominates.
- Each Mission L trace link declares the tier its proofs can establish (held to the `BODY_VERIFIED` rule
  above). The run computes the tier each link reached from its own proofs, by the requirement rule; a
  link whose proofs fall short reports `IMPLEMENTED` (its code paths exist) and is named as short.
  Requirement L3 says one run passes through all nine links; it does not lift any link's own tier.
- Every founder key used in this evidence is a per-test key. None of it is Alfonso's.
- `run` exits 0 only when every tested requirement and every trace link attains its declared tier.
- The harness reads code and runs tests. It does not grant, attach or activate anything.

## Not checked mechanically

- `SANDBOX_VERIFIED` against `UNIT_VERIFIED`. The manifest reads `SANDBOX_VERIFIED` as canonical code with
  a real ledger and Gate, in-process. No static rule tells a canonical Body from a fake journal or a
  stub executor reliably, so a requirement declared `SANDBOX_VERIFIED` on unit-level nodes is caught
  only by review.
- Whether `coverage` is honest. The harness enforces what each value permits, but a requirement marked
  `covered` whose tests miss a clause is caught only by review, against the obligation and the notes.
- Process detection is static. A test that starts its process through code in another module (a fixture
  from a conftest, a helper imported from elsewhere) is not recognised, and its requirement cannot
  declare `BODY_VERIFIED` until the start is visible in its own module.

Recorded runs are kept under `docs/evidence/acceptance/`.
