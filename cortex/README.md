# cortex/

The Polyintelligence Cortex: GREG's governed selection among heterogeneous
competencies (solvers, verifiers, organs), each proving only what it can
legitimately prove, with outcomes settling which works where. See the package
docstring (`cortex/__init__.py`) for its invariants.

| Path | Role |
|---|---|
| `gates.py`, `genome.py` | eligibility first, optimization second |
| `routing.py` | selection among eligible competencies |
| `organs/` | Z3, CP-SAT, Fermi, evidence/causal and semantic organs |
| `memory.py`, `outcomes.py` | settled competence from outcomes |
| `evaluation/` | pre-registered, frozen evaluations (P4/P6/P8, admissions) |
| `seed/` | the Seed Genome |

**Authority:** none. Receipts carry `authority_created: false`; the package
imports neither the Consequence Gate nor any grant issuer. GREG reaches it
through `greg/cognition/`.

**Frozen evidence:** `cortex/evaluation/**/freeze*.json` pin source digests of
what was measured. Do not edit a frozen file; a new evaluation gets a new path
(`docs/collaboration/START_HERE.md`, "keep frozen evaluations identified").
CI: the `cortex_seed` job.
