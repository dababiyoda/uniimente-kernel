# Independent review: a compile receipt that did not answer is no measured failure (`0f2b5052`)

Recorded by the commissioning session from the reviewer agent's hand-back at 10:09 UTC on 2026-11-12 (read from the clock). The
reviewer was a separate agent process on the same model: a second process, not an independent operator. Probes:
`scratchpad/rcu-probes/`; outputs: `scratchpad/rcu-out/`. Base tree `b9a34259`, head tree `0f2b5052`, untouched.

**Verdict: sound, with fixes.** The change does what it says for the three host stops it types, and no neighbouring
mission shape the reviewer built regressed against `b9a34259`. Two gaps remain against the founder's rule, both
also on the base.

## Findings

| # | Severity | Finding | Where | Reproduction | Smallest fix |
|---|---|---|---|---|---|
| 1 | medium | A reading the host stopped can still pass a check, close the mission ACHIEVED and be appraised VERIFIED (predicate `absent` on `result.counterexample`, solver timed out on every launch). Same on base; on head the receipt says `host_stop` and the engine ignores it on the passing side | `greg/missions.py:2562`; `greg/appraisal.py:461`, `:499` | `absent_pass.py` | a compile receipt whose `host_stop` is set never counts as passed; the same where the appraiser re-derives a success closure |
| 2 | medium/low | "Isolation unavailable" is typed `transient` where it is raised and the change does not carry it: the founder is still asked NO_STRATEGY at the first stall, and with a strategy the strategy is dispatched into the refused host | `greg/capabilities.py:497,502`; `cortex.py:140-146`, `:187-192`; `bridge.py:185-186` | `ctxvar.py` case 4; `untyped.py isolation` | the three launchers note a `CapabilityError` typed `transient` or `budget_exceeded` |
| 3 | low | The same stall through the direct cortex route still asks for a strategy at once (four of six cognition sensors in `greg/templates.py` use that route) | `greg/missions.py:595-599`, `:2576-2588` | `untyped.py direct_timeout`, `direct_crash` | needs a typed stop from `cortex.reason`, whose source 16 verdicts bind: a founder question |
| 4 | low | Every non-zero worker exit is typed `transient`; `greg/mechanisms.py:175-180` types SIGXCPU/SIGKILL as `budget_exceeded` and other exits as `executor_error`. A signed `latency_budget` of 0.01 s is retried three rounds though no retry can change it | `cortex.py:149,194`; `bridge.py:191`; `compiler.py:1903-1904` | `fuzz_worker.py 20`; `neighbours.py decline_budget_sensor` | reuse the `mechanisms.run` mapping for the return code |
| 5 | low | State REFUTED is pinned as a measured failure of the check, but it means the verifier refuted the engine's own answer (`cortex/outcomes.py:87` maps it to ABSTAIN / CONTRADICTION). Unchanged behaviour; the new gate adds a mutant that enforces it | `greg/missions.py:573` | `ctxvar.py` case 5; `untyped.py refuted strategy` | a founder question |
| 6 | low | The credit branch (`29c6c2cc`) has its own reader of "did this compile answer" (`greg/corrections.py:117`, `:173`, `:183`); the two readers disagree on five cases when merged; no test fails today | credit branch | `rcu-out/two-readers-credit-merge.txt` | that branch calls `greg.missions.unanswered` |
| 7 | low | Three of the reviewer's 27 mutants survive the unit's test file: a non-dict output read as "not a receipt"; `refused[-1]` to `refused[0]`; the schema left at 0.2. `budget.py` has no mutant in the new gate | — | reviewer's mutants R09, R15, R18 | tests and mutants |
| 8 | info | One textual conflict when merged with `e6905364`, `934a9f77`, `1643932e` and the credit branch: the CI step list | `.github/workflows/canonical-ci.yml` | — | keep both sides |
| 9 | info | A reading the Mind declined now marks `cognition.solve` as a failed observation method in routing (reorders several attached implementations of one function) | `greg/routing.py:163-168` | `derank.py` | do not count a declined reading as a method failure |
| 10 | info | One whole-file freeze digest moved: `cortex/evaluation/composition_lift/freeze-joined-v1.json` lists a `greg/cognition/bridge.py` digest that no longer matches. No routing binding changed | — | `binding_probe.py`: 7 recipes and 111 families, zero differences | record |
| 11 | info, on base too | After the founder answers the one question and nothing changed, the mission re-observes and re-blocks on the same answered request every cadence, with no open question | `greg/missions.py:1859` | `answered_ask.py` | the separate unit already specified (the appraiser review's F5) |
| 12 | info | Blame recorded on an older ledger (base's `routing.outcome ineffective` and `mission.unmet` for a host stall) is not reconciled when head reads it | — | `old_ledger.py` | record |
| 13 | info | Beside a host-stopped check, a faulted construction's second-strike repair comes one back-off later (62 s on base, 93 s on head); nobody is asked on either | — | `fault_beside.py stall` | record |

## Hunts (eleven asked)

1. Neighbouring shapes: 17 scenarios plus the builder's deficit flows, base against head: no regression.
2. Silent loop: none introduced; finding 11 is on the base.
3. Classification: no state carrying a real negative about the world became unanswered. The unmeasured-read-as-
   measured case that exists is on the passing side (finding 1).
4. Second reader: none on this tree; one on the credit branch (finding 6).
5. Schema bump: consumers on head read by prefix or `COMPILE_SCHEMAS`; a ledger of 0.2 receipts is read correctly
   by head. Not run: a branch without this change reading a 0.3 ledger (by reading, its settlement would skip them).
6. Bindings: no admitted verdict's binding changed (51 DEFAULT, 19 NICHE, 14 SUPERSEDED, 12 UNEVALUATED,
   7 EXPERIMENTAL, 5 REJECTED, 3 COMPOSITION_ONLY on both trees). Finding 10 is the one digest that moved.
7. Context variable: no leak found; only a launch from a different thread than the compile would lose a note, and
   no such pool exists on this tree.
8. Mutants: new gate 38/38 and 3/3, unmeasured-check 4/4 and 5/5, reconstitution 4/4 re-run by the reviewer;
   24 of the reviewer's own 27 caught. Not re-run: whole-output, ask-terms, cognition budget, cognition residual,
   cortex groups, seed.
9. Composition with `e6905364`: one textual conflict; 106 and 92 tests passed on the merged tree; nothing passes on
   each side and fails merged.
10. Builder's admissions: checked; a stall after a strategy ran is not blamed until the reading is measured false.
11. A question raised at 93 s and withdrawn at 124 s: facts recorded; judgment left to the founder.

## Not checked

Six of nine gates; the full suite; a real kill or timeout of a worker process (stalls were injected at
`run_isolated`); the appraiser with its own host stalled; goal gravity's downstream use of a stale belief; a 0.3
ledger read by a branch without the change.

## Questions for the founder (reviewer's)

1. Should a reading whose receipt says the host stopped it ever count as passing a check?
2. Is "the verifier refuted the engine's answer" a measured failure of the check, or an unmeasured reading?
3. Should a host stall on the direct cortex route get the same retry, at the cost of re-measuring the verdicts
   bound to `cortex.reason`?
4. When the Mind declines, should goal gravity and routing treat the check as unknown (as now) or as not satisfied?
5. Is a question raised at the third unmeasured round and withdrawn 31 s later acceptable?
6. After the founder answers a SENSOR_FAILURE or NO_STRATEGY question and nothing changed, should the mission ask
   again, stop, or keep re-observing silently as now?
