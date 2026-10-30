# Whole-machine acceptance harness

Directive 2026-10-13, section 33 (Missions A–L) and section 35 (the full-machine completion contract).

| File | What it holds |
| --- | --- |
| `missions.json` | Each obligation of Missions A–L, the test nodes that demonstrate it, the evidence tier those tests can establish, how much of the obligation they show (`coverage`: covered, partial or gap), and every known gap with its dependency. `body_process_tests` lists the test files that drive a real Body process. Mission L also carries the nine-link trace (Goal → Mind → Organs → Body → Action → Evidence → Outcome → Learning → Updated Goal), with an owner, code paths, proofs and the tier those proofs can establish for each link. |
| `completion-contract.json` | One record per required function of the Body, Mind, Organs and the operating loop, holding the section-35 fields, plus the fifteen current-machine conditions with their assessments. A function's evidence tier is **computed** from the mission requirements it cites. It is never declared. |
| `missions.schema.json`, `contract.schema.json` | JSON Schema 2020-12 for both files. |
| `directive-sections.json` | The 2026-10-28 directive (`docs/intent/sources/OPUS-MAXIMUS-MASTER-BUILD-DIRECTIVE-2026-10-28-source.md`) section by section: one record per section 1-77 with the source's exact heading and its testable asks. Each ask has a paraphrase, a verbatim excerpt, owner paths, the evidence it rests on (contract functions, mission requirements, pytest nodes), the tier it requires and the tier that evidence computes, and, while open, its blocker. A gap-map units table orders the buildable residual. Checked by `directive.py`; schema `directive-sections.schema.json`. |
| `directive-asks.pin.json` | Every ask id ever issued in the directive map, with the blocker class it may claim while open besides BUILDABLE_NOT_BUILT. An ask is retired, never deleted; `directive --against <base>` refuses a pin change that drops an id or moves a class out of the build residual. Schema `directive-asks.pin.schema.json`. |

```
python -m acceptance check                      # static: schemas, nodes, symbols, trace, contract refs, real-process rule
python -m acceptance run --out report.json      # run every cited node once and report
python -m acceptance run --mission H            # one mission
python -m acceptance report --outcomes o.json   # report from recorded outcomes
python -m acceptance directive                  # the directive's 77 sections: statuses, blockers, buildable residual
python -m acceptance directive --collect        # ... and pytest collects every node the map cites
python -m acceptance directive --outcomes o.json  # ... with tiers recomputed from a recorded run
python -m acceptance directive --against origin/main  # ... and no pinned ask dropped or moved out of the residual
```

## Rules

- A requirement reaches its declared tier only when **every** cited node is collected and passes.
  A failure, an error, a skip, or a node that collects nothing leaves it at its implementation
  status, and the observed reason is recorded. A skip is never counted as a pass.
- A tier says how strongly the cited tests ran; `coverage` says how much of the obligation they show.
  Reaching a tier is not meeting the obligation:
  - `gap`: the cited tests do not show the obligation at any tier. The requirement may not declare a
    tier, never attains one, and stays at its implementation status. Its cited tests still run: what
    they did is recorded and printed, and one that fails, errors or collects nothing fails the run.
  - `partial`: the requirement can reach its tier, and the report says it covers only part of its
    obligation. Its notes name the clauses without evidence at that tier; those lowered by the
    2026-10-15 coverage audit start with `Partial (coverage audit 2026-10-15):`.
  - `covered`: the cited tests show the whole obligation at the declared tier.

  A requirement counts as covering its whole obligation only when it reached its declared tier in the
  run **and** is declared `covered`; a declaration alone covers nothing. The summary gives both counts:
  how many requirements reach their declared tier, and how many of those cover the whole obligation
  and how many only part. A mission or a contract function is reported `partial` unless every
  requirement it rests on covers its whole obligation (and, for Mission L, every trace link reached
  its tier).
- `BODY_VERIFIED` needs at least one cited node that drives a real Body process. The node's file must
  be listed under `body_process_tests`, and `check` verifies statically that its test starts the declared
  process: an argv must reach a process-spawning call (`subprocess.Popen`, `run`, `call`, `check_call`,
  `check_output`, or `asyncio.create_subprocess_exec`). The argv counts when it is `python -m greg
  [--home H] run`; when it starts supervisord with a `-c` file holding `service.supervisord_program`
  (which runs `greg run`); or when it runs python on a driver script that calls `Body(...).run(` (the
  loop `greg run` runs, with a test capability added), as a file or with `-c`. The reader follows
  values through names, list displays and concatenation, starred arguments, `+`, f-strings, `str()` and
  files written with `write_text`, into the same-module functions the test calls and the same-module
  fixtures it requests. It does not count an argv that is only built, an in-process `Body.run`, a
  supervisord configuration that is written but not launched, a driver that is never spawned, a
  function or lambda that is never called, a constant-false `if`, or a spawning call the test patches
  with `mock.patch` as a decorator or `monkeypatch.setattr`. It is a pattern reader, not an evaluator:
  the limits below say what it still counts that never runs. An in-process Body with a test clock is
  `SANDBOX_VERIFIED` at most.
- Tests can establish at most `BODY_VERIFIED`. `FOUNDER_ACCEPTED`, `AUTHORIZED_LIVE`,
  `EXTERNALLY_VERIFIED` and `COMMERCIAL_OUTCOME_VERIFIED` need records that no test produces, so the
  manifest cannot declare them and the harness never assigns them.
- Each mission, and each contract function, is only as verified as its least-verified requirement.
  `BLOCKED_WITH_REASON` dominates.
- Each Mission L trace link declares the tier its proofs can establish (held to the `BODY_VERIFIED` rule
  above). The run computes the tier each link reached from its own proofs, by the requirement rule; a
  link whose proofs fall short reports `IMPLEMENTED` (its code paths exist) and is named as short.
  Mission L is only as verified as its least-verified requirement **or trace link**, and so is every
  contract function that cites a Mission L requirement. Requirement L3 says one run passes through all
  nine links; it does not lift any link's own tier.
- Every founder key used in this evidence is a per-test key. None of it is Alfonso's.
- `run` exits 0 only when every tested requirement and every trace link attains its declared tier and
  no cited test fails, errors or collects nothing, whether or not its requirement declares a tier.
- The harness reads code and runs tests. It does not grant, attach or activate anything.

## Not checked mechanically

- `SANDBOX_VERIFIED` against `UNIT_VERIFIED`. The manifest reads `SANDBOX_VERIFIED` as canonical code with
  a real ledger and Gate, in-process. No static rule tells a canonical Body from a fake journal or a
  stub executor reliably, so a requirement declared `SANDBOX_VERIFIED` on unit-level nodes is caught
  only by review.
- Whether `coverage` is honest. The harness enforces what each value permits, but a requirement marked
  `covered` whose tests miss a clause is caught only by review, against the obligation and the notes.
- Process detection is static and only partly conservative. It does not evaluate conditions other than
  constants, so a spawn in a branch counts, and so do some spawns that never run: code after a `return`,
  `raise` or `pytest.skip()`, a loop over an empty sequence, a generator or coroutine helper never
  iterated or awaited, `greg run --help`, and a spawn patched by an autouse fixture, `usefixtures`, a conftest, a direct
  assignment such as `subprocess.Popen = ...` or `mock.patch.multiple`. No registered test relies on any
  of these (each was read on 2026-10-15), and a patched test that asserts real-process effects fails when
  run; the registry and the run are the backstops. A test that starts its process through code in another module (a
  fixture from a conftest, a helper imported from elsewhere), through a method, or with an argv it
  cannot follow is not recognised, and its requirement cannot declare `BODY_VERIFIED` until the start
  is visible in its own module. A driver is recognised by parsing its source for a `Body(...).run(` call,
  so one that only mentions the call in a comment or a printed string does not count, and neither does a
  driver held as an indented constant or built from a `%` template (both fail closed).

## The directive's sections (founder, 2026-10-30: "That is done when we completely build the prompt")

`check` also validates `directive-sections.json` and its pin, `directive-asks.pin.json`; `directive` prints the map.
The rules carry the ones above over to the 77 sections and their asks:

- An ask's tier is computed, never declared: the least-verified of the mission requirements (with the trace links of a
  mission that carries a trace, as for contract functions), contract functions and pytest nodes it cites. Its own nodes
  establish the tier the ask declares for them (`tests_tier`, UNIT_VERIFIED by default, BODY_VERIFIED only with a
  cited node that starts a real Body process, by the same static rule). A cited node must name a test pytest
  collects, not a helper. An ask that cites nothing is INTENDED. Without a run the computed tier is the ceiling the
  cited evidence could establish if every cited test passed; `directive --outcomes` recomputes it from a run, where a
  failure, an error, a skip or a node that collects nothing leaves the ask unmet.
- An ask's coverage is never above that of a requirement, trace or function it cites.
- An ask is met only at or above its required tier and covered. Tests reach at most BODY_VERIFIED, so an ask that
  requires FOUNDER_ACCEPTED or above is never met by tests, and its blocker must be FOUNDER_ONLY or EXTERNAL.
- An open ask names its blocker: FOUNDER_ONLY, EXTERNAL, BUILDABLE_NOT_BUILT (with its gap-map unit when one exists)
  or PRINCIPLE (guarded by named tests among its own evidence, or UNGUARDED). A met ask names none. A FOUNDER_ONLY or
  EXTERNAL blocker on a tier a test can reach cites the record that holds it: `gap:<mission>.<gap>` (an open
  missions.json gap building cannot close, dependency founder or credential for FOUNDER_ONLY; external, technical,
  legal or physical for EXTERNAL) or `<path>#<verbatim words in that file>`.
- A section's listed lines are its bullets and the lines that start "Do not" or "Never". A section is DONE only when
  every ask is met and every listed line is answered (an ask's excerpt quotes it whole, or the ask names it in
  `lines`) or set aside in `not_asks` with a reason; OPEN when no ask is met, PARTIAL otherwise. Its recorded status
  must equal the computed one.
- "The prompt is completely built" holds only when no ask is BUILDABLE_NOT_BUILT, an UNGUARDED PRINCIPLE, a PRINCIPLE
  whose guard fell short in the run, or open with no blocker named, every listed line of every section is accounted
  for, and all 77 sections are present. "Every section DONE" also needs every founder and external record.
- The asks are pinned (`directive-asks.pin.json`): every ask id ever issued, with the class it may claim while open
  besides BUILDABLE_NOT_BUILT. `check` refuses a pinned ask missing from the map, an ask not pinned, and an open ask
  whose blocker left its pinned class for anything but BUILDABLE_NOT_BUILT. An ask leaves only by retirement, kept in
  the map: superseded by a live ask that requires at least as much (it is met when its successor is), or withdrawn by
  a founder intent record under `docs/intent/` quoted verbatim. `directive --against <ref>` compares the pin with the
  pin committed at `<ref>` (a pull request's base in CI): an id that disappeared or a class that left
  BUILDABLE_NOT_BUILT fails, so editing the pin in the same change does not get past it.
- Every gap-map unit is named by an open ask, is a prerequisite of a unit that is, or records `closed_by`; the buildable
  list prints each unit after its prerequisites, prerequisites without asks of their own included.
- `check` fails on each of the above, and on a missing, duplicated or out-of-order section, a source other than the
  directive, a heading or excerpt that is not the source's, a changed source digest, a cited node or guard that does
  not resolve, an unknown contract function, mission requirement, gap or unit, a dependency cycle, a tier or coverage
  claimed above the evidence (or a stale tier), and a DONE section with an open ask or an unanswered line.
  `directive --collect` also runs pytest's collection over every distinct cited node and guard and fails on one that
  collects nothing (CI installs `requirements-cognition.txt` and Playwright so that every cited file can collect).

Not checked mechanically: whether an ask is a faithful reading of its section, whether its required tier is what the
section's words ask, SANDBOX_VERIFIED against UNIT_VERIFIED for an ask's own nodes, whether `covered` is honest within
what its citations allow, whether a blocker class is the true reason (a record shows the blocker exists, not that it is
the only one), and whether a set-aside line is truly not an ask. These are review questions, like the coverage
questions above. The pin and its ratchet make each such judgement a visible, separate change instead of a silent one.

Recorded runs are kept under `docs/evidence/acceptance/`.
