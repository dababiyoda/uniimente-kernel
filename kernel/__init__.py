"""UNIIMENTE constitutional kernel — Consequence Gate vertical slice (v0.1.0).

Governing hard rules enforced by this package (see SPEC.md, "Hard rules"):
1. Adapters may only execute with a current, verified CommitWitness.
2. Approvals bind to the intent fingerprint; any change to payload, target,
   budget, legal_principal, policy_version or consequence_class invalidates.
3. requires_human_approval is unbypassable.
4. The spine is append-only; any ambiguity fails closed (GateRefusal).
5. Deterministic canonical-JSON hashing everywhere.
"""

__version__ = "0.1.0"
