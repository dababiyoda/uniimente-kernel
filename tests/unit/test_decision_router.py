"""The router recommends. It must never be able to do anything else."""
from __future__ import annotations

import pytest

from closure.nervous_system_registry import package_imports
from discovery.service import CapabilityDiscoveryService
from routing.decision_router import (
    Candidate,
    DecisionRouter,
    RouterError,
    RoutingCriteria,
)


def _c(cid: str, **kw) -> Candidate:
    base = {"organ_id": "spiffe://uniimente.internal/organ/x", "contract": "evidence"}
    base.update(kw)
    return Candidate(cid, **base)


# ------------------------------------------------------------------ the rule
def test_router_authorizes_nothing():
    """A routing decision is a recommendation with a rationale. Nothing more."""
    router = DecisionRouter()
    decision = router.route(RoutingCriteria(contract="evidence"),
                            [_c("a", evidence_maturity="PROVEN")])

    # 1. The decision object carries no grant and says so structurally.
    assert decision.authorizes is None
    assert decision.to_dict()["grants_issued"] == 0

    # 2. No method on the router acts.
    forbidden = ("execute", "invoke", "call", "grant", "authorize", "approve", "run")
    surface = [n for n in dir(router) if not n.startswith("_")]
    assert [n for n in surface if any(f in n.lower() for f in forbidden)] == []

    # 3. Structurally: the package never imports the gate or the policy engine.
    imports = package_imports("routing")
    assert not any(i.startswith("policy") for i in imports), (
        f"the router imports authority machinery: {sorted(imports)}"
    )

    # 4. The explanation says out loud that a grant is still required.
    assert "grants no authority" in decision.explain()


def test_the_canonical_selector_never_invokes_a_provider():
    """The invariant that separates this router from the one in draft PR #70.

    PR #70's `capabilities/router.py` has a `resolve()` that returns
    `chosen.provider()` — it instantiates code. A decision-only selector must
    have no call site that invokes a candidate, under any name.
    """
    import ast
    import pathlib

    source = pathlib.Path(__file__).parents[2] / "routing" / "decision_router.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))

    invocations = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        # Any `<something>.provider(...)`, `.execute(...)`, `.invoke(...)`,
        # `.run(...)` or a bare call to an attribute named like a candidate.
        if isinstance(func, ast.Attribute) and func.attr in (
            "provider", "execute", "invoke", "run", "call", "apply"
        ):
            invocations.append(f"line {node.lineno}: .{func.attr}()")
    assert invocations == [], (
        "the canonical decision router invokes something: " + "; ".join(invocations)
    )

    # And it exposes no resolve()-shaped entry point at all.
    assert not hasattr(DecisionRouter, "resolve")


def test_the_router_conflict_is_recorded_as_resolved_and_says_how():
    """Technology #25 was settled by a founder, and the record must show it.

    This test previously asserted the opposite — that #25 read as UNRESOLVED —
    and that was correct while two routers competed with no ruling between them.
    FOUNDER-RULING-2026-08-22 ruling 4 selected `routing/decision_router.py`, so
    asserting the question is still open would now be the falsehood.

    What is asserted instead is the harder property: a resolution recorded with
    its mechanism. "We picked one" is not enough — the register must say what
    happened to the one not picked, because the Build Order's whole preservation
    rule turns on the difference between superseded and deleted.
    """
    from blueprint.registry import BINDINGS

    gaps = " ".join(BINDINGS[25].gaps)
    assert "CANONICAL SELECTOR RESOLVED" in gaps
    # Preserved, and specifically where its machinery went.
    assert "capabilities/implementations.py" in gaps
    assert "capabilities/instantiate.py" in gaps
    assert "resolve()" in gaps, "the record must say what happened to resolve()"
    # And the claim that is still NOT made.
    assert "No live traffic has routed through either router" in gaps


def test_the_registry_does_not_claim_the_routers_were_benchmarked():
    """The ruling's explicit caution, held in the register.

    > Architectural selection today must not be misrepresented as evidence that
    > one router produces better outcomes.
    """
    from blueprint.registry import BINDINGS

    gaps = " ".join(BINDINGS[25].gaps)
    assert "NOT yet benchmarked" in gaps


def test_a_request_beyond_every_ceiling_refuses_rather_than_picking_least_bad():
    router = DecisionRouter()
    decision = router.route(
        RoutingCriteria(contract="evidence", consequence_class="financial"),
        [_c("readonly", authority_ceiling="read_only", evidence_maturity="PROVEN"),
         _c("internal", authority_ceiling="internal_write", evidence_maturity="PROVEN")],
    )
    assert decision.is_refusal
    assert decision.selected is None
    assert decision.ranking == ()
    assert len(decision.refused) == 2
    for _, reason in decision.refused:
        assert "ceiling" in reason


def test_an_over_ceiling_candidate_is_removed_not_down_ranked():
    """Exceeding authority is disqualifying; it must not be a scoring penalty."""
    router = DecisionRouter()
    decision = router.route(
        RoutingCriteria(contract="evidence", consequence_class="external_contact"),
        [_c("weak_but_permitted", authority_ceiling="external_contact",
            evidence_maturity="SKETCHED"),
         _c("strong_but_over", authority_ceiling="read_only",
            evidence_maturity="HARDENED")],
    )
    assert decision.selected == "weak_but_permitted"
    assert "strong_but_over" in dict(decision.refused)


# ------------------------------------------------------------------- ranking
def test_evidence_maturity_outranks_speed():
    router = DecisionRouter()
    decision = router.route(
        RoutingCriteria(contract="evidence"),
        [_c("proven_slow", evidence_maturity="PROVEN", latency_ms=900.0),
         _c("sketched_fast", evidence_maturity="SKETCHED", latency_ms=1.0)],
    )
    assert decision.selected == "proven_slow", (
        "the router preferred the faster unproven implementation"
    )


def test_ranking_is_deterministic_including_ties():
    router = DecisionRouter()
    pool = [_c("b", evidence_maturity="BUILT"), _c("a", evidence_maturity="BUILT")]
    first = router.route(RoutingCriteria(contract="evidence"), pool)
    second = router.route(RoutingCriteria(contract="evidence"), list(reversed(pool)))
    assert first.selected == second.selected == "a"     # tie broken by id, not order
    assert [s.candidate_id for s in first.ranking] == \
           [s.candidate_id for s in second.ranking]


def test_unhealthy_quarantined_and_irreversible_candidates_are_excluded():
    router = DecisionRouter()
    decision = router.route(
        RoutingCriteria(contract="evidence", require_reversible=True),
        [_c("sick", healthy=False, evidence_maturity="PROVEN"),
         _c("quarantined", lifecycle="QUARANTINED", evidence_maturity="PROVEN"),
         _c("oneway", reversible=False, evidence_maturity="PROVEN"),
         _c("fine", evidence_maturity="PROVEN")],
    )
    assert decision.selected == "fine"
    assert set(dict(decision.refused)) == {"sick", "quarantined", "oneway"}


def test_a_candidate_serving_a_different_contract_never_competes():
    router = DecisionRouter()
    decision = router.route(
        RoutingCriteria(contract="evidence"),
        [_c("wrong", contract="outcome", evidence_maturity="PROVEN")],
    )
    assert decision.is_refusal
    assert "serves outcome, not evidence" in dict(decision.refused)["wrong"]


# ------------------------------------------------------------------- honesty
def test_the_weights_are_declared_and_the_router_says_so():
    router = DecisionRouter()
    decision = router.route(RoutingCriteria(contract="evidence"),
                            [_c("a", evidence_maturity="PROVEN")])
    assert decision.weights_are_declared_not_learned is True
    assert router.outcomes_compared() == 0, (
        "the router claims to have compared decisions against outcomes; "
        "the verified external outcome count is 0"
    )


def test_every_decision_is_recorded_with_its_full_rationale():
    router = DecisionRouter()
    router.route(RoutingCriteria(contract="evidence"), [_c("a")])
    router.route(RoutingCriteria(contract="outcome"), [])
    assert len(router.decisions) == 2
    for decision in router.decisions:
        assert decision.decided_at.endswith("Z")
        assert decision.criteria


def test_malformed_candidates_and_criteria_fail_closed():
    with pytest.raises(RouterError):
        _c("bad", authority_ceiling="godmode")
    with pytest.raises(RouterError):
        _c("bad", evidence_maturity="LEGENDARY")
    with pytest.raises(RouterError):
        _c("bad", cost_units=-1.0)
    with pytest.raises(RouterError):
        RoutingCriteria(contract="")
    with pytest.raises(RouterError):
        RoutingCriteria(contract="evidence", consequence_class="godmode")


def test_routing_without_candidates_or_a_directory_fails_closed():
    with pytest.raises(RouterError, match="no discovery service"):
        DecisionRouter().route(RoutingCriteria(contract="evidence"))


# ----------------------------------------------------------- with discovery
def test_candidates_from_discovery_default_to_unproven():
    """Discovery reports what an organ declares. A declaration is not evidence."""
    router = DecisionRouter(discovery=CapabilityDiscoveryService())
    candidates = router.candidates_for("outcome")
    assert candidates
    assert all(c.evidence_maturity == "BLUEPRINT" for c in candidates)
    decision = router.route(
        RoutingCriteria(contract="outcome", minimum_maturity="PROVEN"), candidates)
    assert decision.is_refusal, (
        "declared capabilities were routed to as though they were proven"
    )
