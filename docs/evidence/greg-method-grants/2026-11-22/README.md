# Standing method grants: rehearsal evidence (2026-11-22)

**Question.** A signed read-only mission whose question fits a registered, verified, read-only method stops and
asks for a CAPABILITY_ATTACH (`tests/unit/test_greg_cognition_genesis.py::test_a_deficit_that_fits_a_withheld_
genome_names_it_as_the_attach_candidate`). Does one founder-signed `METHOD_GRANT` let GREG do that work without
an ask per method, without attaching anything permanently?

**Run.** `PYTHONPATH=. python docs/evidence/greg-method-grants/2026-11-22/rehearse.py business|transfer`
(results in `results-business.json` and `results-transfer.json`). Each arm is a fresh real Body: real Genesis,
the real Competency Compiler and the real frozen evidence index. There are 10 missions per arm (5 method
families with 2 seeds each), and the questions come from the genomes' own instance generators. The inputs are
synthetic; no external data is used. A tick is 31 simulated seconds.

Arms:

- **baseline:** today. The founder answers each attach ask the moment it appears.
- **grant:** the founder signs one grant naming the 5 families the questions were drawn from, and answers
  nothing else.
- **grant_and_answers:** that grant, plus the founder answers any remaining ask.
- **suggested_grant:** the founder signs one grant built by `method_grants.suggest` from sample questions on
  seeds 0 and 1, which are never the questions the missions then ask.

| set | arm | achieved | founder actions | mission-ticks unanswered | methods left attached body-wide | grant uses |
|---|---|---|---|---|---|---|
| business | baseline | 8/10 | 4 | 25 | 4 | 0 |
| business | grant | 8/10 | 1 | 17 | 0 | 8 |
| business | grant_and_answers | 8/10 | 1 | 17 | 0 | 8 |
| business | suggested_grant | 8/10 | 1 | 17 | 0 | 8 |
| transfer | baseline | 10/10 | 5 | 11 | 5 | 0 |
| transfer | grant | **6/10** | 1 | 32 | 0 | 6 |
| transfer | grant_and_answers | 10/10 | 3 | 5 | 2 | 6 |
| transfer | suggested_grant | **10/10** | **1** | **1** | **0** | 10 |

**Findings.**

1. A grant whose method set matches what the compiler routes to does the same work with one founder action
   instead of one per method. Unanswered mission-time falls by 32% (business) and 91% (transfer), and nothing
   is left attached body-wide. The baseline leaves every attached method usable by every future mission.
2. **Negative, kept:** a grant built from the families the questions were *drawn* from is worse on the transfer
   set (6/10). The compiler answers minimax questions with `game_lp_dual` and pathfinding questions with
   `grid_dijkstra`, which the founder had not listed. `method_grants.suggest` (`greg grant suggest`) was built
   in response: it previews, recording nothing, which methods the compiler would use, and the grant built from
   it closes 10/10.
3. **Where GREG still stops (all arms):** the two `newsvendor_compile` questions. That family is a composition
   stage with no standalone decision, so the compiler correctly declines a standalone question. The mission
   then ends in the generic "no admissible strategy, founder revises mission" ask instead of naming the
   composition the question needs. The preview correctly leaves newsvendor out of the suggested grant.

**Not run, and why.**

- The founder's Tampa opportunity task, and the three-way comparison with Claude. This environment has no
  model key (the API answers 401), and its network policy refuses public data hosts (census.gov and bls.gov
  were refused by the proxy). A Claude arm run by this session's own author would not be a fair same-budget
  baseline, so it is NOT_RUN rather than simulated.
- Messy evidence with a midway correction, and answer-quality scoring: these need the task above.
- Wall time is per arm on this container. Ticks, not wall time, measure founder-facing delay.

Authority: no arm attached anything through a grant, and nothing was spent, sent or published.
