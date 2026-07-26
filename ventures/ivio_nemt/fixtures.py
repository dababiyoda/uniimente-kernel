"""IVIO-NEMT domain fixtures — VENTURE CELL, not core.

Preserves the healthcare-specific closure example that was previously hardcoded
as the DEFAULT inside closure/advantage_registry.py. The core now exposes
generic builders requiring explicit values; this file supplies the original
worked instance so the example survives intact rather than being deleted.

Nothing here is attached, active, or authoritative. Importing this module
grants no authority and activates no venture.

Venture -> core imports are permitted. Core -> venture imports are forbidden
and enforced by tests/unit/test_core_venture_boundary.py.
"""
from closure.advantage_registry import build_composition_request, build_opportunity


def ivio_opportunity(*, legal_operator="alfonso_lopez"):
    """The original healthcare instance, byte-equivalent to the pre-Package-2
    default in closure/advantage_registry.py::_opportunity."""
    return build_opportunity(
        legal_operator=legal_operator,
        buyer="facility CFO",
        beneficiary="patient",
        pain_owner="case management",
        budget_owner="facility CFO",
        mandate_actor="compliance executive",
        recurring_transaction="patient transport discharge",
        broken_state="missing payer-grade transport proof",
        trapped_value_usd=250000.0,
        accepted_artifact="Request-Accept-Evidence packet",
        external_consequence="accepted and reconciled transport outcome",
        lawful_path="BAA plus fair-market-value evidence service",
    )


def ivio_composition_request(*, legal_principal="alfonso_lopez", max_budget=100.0):
    """The original healthcare instance, byte-equivalent to the pre-Package-2
    default in closure/advantage_registry.py::_composition_request."""
    return build_composition_request(
        legal_principal=legal_principal,
        max_budget=max_budget,
        market_failure="missing payer-grade transport proof",
        beneficiaries=("patient",),
        payer="facility CFO",
    )
