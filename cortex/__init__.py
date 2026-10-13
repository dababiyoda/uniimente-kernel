"""UNIIMENTE Seed Cortex — GREG Polyintelligence Cortex: Seed Genome v0.1 (Seed Experiment).

This is the Seed Cortex, not the full Polyintelligence Cortex (review pass 2 §63):
five executing organs (semantic, Fermi, formal, evidence/causal, deterrence) and an
adversarial verifier inside a genome that reserves 28 later cognition families as
disabled registrations (tested in tests/unit/test_cortex_gates_genome.py).

One governed GREG selecting among heterogeneous competencies, proving what each
can legitimately prove, and learning from reality which works where.

Invariants (tested in tests/unit/test_cortex_*.py):

* eligibility first, optimization second (cortex.gates, cortex.genome);
* cognition creates no authority: every receipt has ``authority_created: false``
  and ``execution_authority: "none"``; this package imports neither the
  Consequence Gate nor any grant issuer;
* receipts separate formal validity, empirical validity and legitimate authority;
* learning moves only on verified outcomes and can only reorder eligible routes.

Sources of intent: docs/intent/sources/POLYINTELLIGENCE-CORTEX-*-2026-09-30.md.
"""
from .contracts import CORTEX_VERSION  # noqa: F401
