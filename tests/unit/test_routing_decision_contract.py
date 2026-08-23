"""One canonical typed RoutingDecision, and construction behind the Gate.

FOUNDER-RULING-2026-08-22, ruling 4:

> Also close the adjacent typing gap if it can be done without creating another
> parallel contract: there should be one canonical typed RoutingDecision
> boundary owned by the Kernel. Organ adapters consume it; they do not copy it.

and

> Move provider construction/execution downstream to a caller possessing the
> required capability and crossing the Consequence Gate.

The schema is validated against decisions produced by the real router, not
against hand-written fixtures — a fixture would prove the schema self-consistent
and nothing about whether the code emits what the contract says.
"""
from __future__ import annotations

import json
import os

import jsonschema
import pytest

from capabilities.implementations import Implementation, ImplementationRegistry
from capabilities.instantiate import (
    CONSEQUENCE_CLASS,
    ESTIMATED_COST_USD,
    InstantiationRefused,
    instantiate,
)
from routing.decision_router import Candidate, DecisionRouter, RoutingCriteria

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCHEMA_PATH = os.path.join(ROOT, "contracts", "routing-decision.schema.json")


@pytest.fixture(scope="module")
def schema() -> dict:
    with open(SCHEMA_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def _candidates() -> tuple[Candidate, ...]:
    return (
        Candidate(candidate_id="linker-canonical", organ_id="kernel",
                  contract="linker.resolve", evidence_maturity="EXERCISED",
                  authority_ceiling="internal_write", latency_ms=10.0),
        Candidate(candidate_id="linker-experimental", organ_id="kernel",
                  contract="linker.resolve", evidence_maturity="BUILT",
                  authority_ceiling="internal_write", latency_ms=5.0),
    )


# ------------------------------------------------------------ the contract
def test_the_schema_is_registered_in_the_canonical_contract_directory():
    """`contracts/` is the only contract registry — the Linker's existing rule."""
    assert os.path.exists(SCHEMA_PATH)
    assert SCHEMA_PATH.endswith(".schema.json")


def test_a_real_routing_decision_validates_against_the_schema(schema):
    """Produced by the router, not written by hand."""
    router = DecisionRouter()
    decision = router.route(
        RoutingCriteria(contract="linker.resolve", consequence_class="internal_write"),
        candidates=_candidates())
    jsonschema.validate(decision.to_dict(), schema)


def test_a_refusal_also_validates(schema):
    """`selected: null` is a valid final answer and must type as one."""
    router = DecisionRouter()
    decision = router.route(
        RoutingCriteria(contract="linker.resolve",
                        consequence_class="irreversible"),
        candidates=_candidates())
    assert decision.is_refusal
    jsonschema.validate(decision.to_dict(), schema)


def test_the_boundary_refuses_to_carry_authority(schema):
    """`authorizes` is typed null and required, not merely omitted.

    Typed rather than absent so that a future attempt to pass a grant through
    this boundary fails schema validation instead of passing silently.
    """
    router = DecisionRouter()
    payload = router.route(
        RoutingCriteria(contract="linker.resolve", consequence_class="internal_write"),
        candidates=_candidates()).to_dict()
    assert payload["authorizes"] is None
    assert payload["grants_issued"] == 0

    payload["authorizes"] = {"grant_id": "grant-1"}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(payload, schema)


def test_a_router_claiming_to_have_issued_a_grant_fails_validation(schema):
    router = DecisionRouter()
    payload = router.route(
        RoutingCriteria(contract="linker.resolve", consequence_class="internal_write"),
        candidates=_candidates()).to_dict()
    payload["grants_issued"] = 1
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(payload, schema)


def test_an_extra_field_fails_rather_than_becoming_a_second_dialect(schema):
    """`additionalProperties: false` is what makes this ONE contract.

    Without it, an adapter could add its own field, the schema would still pass,
    and the institution would have two RoutingDecision shapes that agree until
    they do not.
    """
    router = DecisionRouter()
    payload = router.route(
        RoutingCriteria(contract="linker.resolve", consequence_class="internal_write"),
        candidates=_candidates()).to_dict()
    payload["organ_specific_hint"] = "please pick the fast one"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(payload, schema)


def test_weights_are_reported_as_declared_not_learned(schema):
    """Until real outcomes exist, saying otherwise would be a claim unearned.

    The ruling: architectural selection today must not be misrepresented as
    evidence that one router produces better outcomes.
    """
    router = DecisionRouter()
    payload = router.route(
        RoutingCriteria(contract="linker.resolve", consequence_class="internal_write"),
        candidates=_candidates()).to_dict()
    assert payload["weights_are_declared_not_learned"] is True


def test_the_gap_audit_check_now_sees_a_typed_contract():
    """The register said RoutingDecision was untyped. It is typed now."""
    from governance import gap_audit

    still_open, detail = gap_audit._routing_decision_is_untyped()
    assert still_open is False, detail


# ------------------------------------------- construction crosses the Gate
def test_instantiate_requires_a_gate_and_a_capability():
    """No default gate, no default actor. Both must be supplied deliberately."""
    import inspect

    params = inspect.signature(instantiate).parameters
    for required in ("gate", "actor", "legal_principal"):
        assert params[required].default is inspect.Parameter.empty, (
            f"{required} has a default; a default gate is no gate"
        )


def test_instantiate_cannot_also_select():
    """It takes an implementation_id. A constructor that could choose would
    have reassembled PR #70's `resolve()` under a new name."""
    import inspect

    params = inspect.signature(instantiate).parameters
    assert "implementation_id" in params
    assert "candidates" not in params
    assert "criteria" not in params


def test_construction_declares_itself_internal_and_free():
    """Stated as constants so a caller cannot quietly raise them.

    An instantiation that needed a higher consequence class or a non-zero budget
    would be doing something other than instantiating.
    """
    assert CONSEQUENCE_CLASS == "internal_write"
    assert ESTIMATED_COST_USD == 0.0


def test_a_quarantined_implementation_cannot_be_constructed():
    """Re-checked at construction time, not trusted from selection time.

    An implementation can be quarantined between being chosen and being built,
    which is exactly the window the Gate's own commit-time revalidation exists
    to close.
    """
    registry = ImplementationRegistry()
    registry.register(Implementation("impl-a", "linker.resolve",
                                     provider=lambda: object()))
    registry.mark_unavailable("linker.resolve", "impl-a", reason="compromised")

    with pytest.raises(InstantiationRefused, match="QUARANTINED"):
        instantiate(registry, "linker.resolve", "impl-a", gate=object(),
                    actor="mp-1", legal_principal="Alfonso Lopez")


def test_an_unhealthy_implementation_cannot_be_constructed():
    registry = ImplementationRegistry()
    registry.register(Implementation("impl-a", "linker.resolve",
                                     provider=lambda: object(),
                                     health=lambda: False))
    with pytest.raises(InstantiationRefused, match="health check"):
        instantiate(registry, "linker.resolve", "impl-a", gate=object(),
                    actor="mp-1", legal_principal="Alfonso Lopez")


def test_the_provider_is_called_in_exactly_one_place_in_the_institution():
    """Structural: `provider()` must be reachable only from inside the Gate.

    If a second call site appears, construction has escaped the governed path
    and this test is the only thing that would notice.
    """
    import ast

    call_sites = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames
                       if d not in {".git", "__pycache__", "tests", ".github"}]
        for name in filenames:
            if not name.endswith(".py"):
                continue
            path = os.path.join(dirpath, name)
            with open(path, encoding="utf-8", errors="ignore") as fh:
                try:
                    tree = ast.parse(fh.read())
                except SyntaxError:
                    continue
            for node in ast.walk(tree):
                if (isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute)
                        and node.func.attr == "provider"):
                    call_sites.append(os.path.relpath(path, ROOT))

    assert call_sites == ["capabilities/instantiate.py"], (
        f"provider() is called from {call_sites}; construction must happen only "
        "inside the Gate-mediated path"
    )
