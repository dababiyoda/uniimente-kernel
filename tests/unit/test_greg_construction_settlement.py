"""A construction's verified answer reaches settlement, so retained outcomes can choose between competing fits.

Before this, a signed portfolio mission the Mind answered through the constructed ``selection.closure`` was
appraised VERIFIED, yet ``settlement.measured_outcomes`` dropped it: it credits a compiled answer only through the
selected method's own cognitive receipt, and a construction's answer is a problem-level certificate with no such
receipt. Its successes and failures never reached competence, so ``_settled_preference`` and the inhibition rule
could never weigh a construction against another fit (record ``LOOP-15-MAP-2026-10-22.md``, step 13).

Rule kept: only a construction Capability Genesis registered on this body (``capability.registered`` with a
``composed`` origin) is credited, at the version its registration pinned, under the signed check's identity. A
compile receipt that names any other method, or whose identity digest does not hold, credits nothing. The founder
key is a per-test Ed25519 key.
"""
from __future__ import annotations

import pytest

pytest.importorskip("networkx")

from greg.body import Body  # noqa: E402
from greg.cognition import compiler, settlement  # noqa: E402
from greg.cognition.contracts import digest  # noqa: E402
from greg.templates import compiled_question  # noqa: E402
from tests.greg_fixtures import Clock, drop, make_body, signed  # noqa: E402
from tests.unit.test_greg_recombine import PORTFOLIO, ticks  # noqa: E402


def answered_portfolio(tmp_path, n=6):
    home, key, body_id, _ = make_body(tmp_path)
    spec = compiled_question(problem_id="portfolio-1", data=PORTFOLIO, allow_construction=True,
                             objective="which offers to take")
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    body = Body(home, clock=clock)
    body.__enter__()
    body.boot()
    states = ticks(body, clock, n)
    assert "ACHIEVED" in [s["state"] for s in states]
    return body, clock


def construction_id(body):
    return next(e.payload["manifest"]["capability_id"] for e in body.journal.replay("capability.registered")
                if (e.payload.get("origin") or {}).get("kind") == "composed")


def compile_receipts(body):
    return [r.payload["result"]["output"] for r in body.ledger.by_type("receipt")
            if isinstance(r.payload["result"].get("output"), dict)
            and r.payload["result"]["output"].get("schema") == compiler.SCHEMA]


def test_a_constructions_verified_answer_settles_once_and_reaches_the_compilers_counts(tmp_path):
    body, clock = answered_portfolio(tmp_path)
    try:
        cid = construction_id(body)
        assert compile_receipts(body)[-1]["method_or_composition_selected"] == cid
        outcomes = [o for o in settlement.measured_outcomes(body.journal) if o["method"] == cid]
        assert len(outcomes) == 1, "the construction's verified answer did not reach settlement"
        [o] = outcomes
        assert o["correct"] is True and o["selected_by"] == "competency_compiler" and o["authority_created"] is False
        assert o["method_version"] == next(e.payload["manifest"]["version"]
                                           for e in body.journal.replay("capability.registered")
                                           if e.payload["manifest"]["capability_id"] == cid)
        ticks(body, clock, 3)                                  # reobservation revises the claim, never adds one
        settlement.reconcile(body.journal)
        settlement.reconcile(body.journal)
        live = {}
        for e in body.journal.replay("cognition.settled"):
            if e.payload["method"] == cid:
                live[settlement._outcome_identity(e.payload)] = e.payload
        assert len(live) == 1 and not next(iter(live.values())).get("invalidated")
        assert compiler._settled_counts(body.journal)[cid] == (1, 1)
    finally:
        body.__exit__(None, None, None)


def test_a_compile_receipt_naming_anything_but_a_registered_construction_credits_nothing(tmp_path):
    body, _ = answered_portfolio(tmp_path)
    try:
        cid = construction_id(body)
        constructed = settlement._constructed_versions(body.journal)
        receipt = compile_receipts(body)[-1]
        assert settlement._constructed(receipt, constructed) is receipt
        for forged_method in ("composed.selection.closure.networkx.forged", "cognition.optimization"):
            forged = {k: v for k, v in receipt.items() if k != "receipt_id"}
            forged["method_or_composition_selected"] = forged_method
            forged["receipt_id"] = digest(forged)               # a self-consistent digest does not make it Genesis's
            assert settlement._constructed(forged, constructed) is None
        tampered = {**receipt, "method_or_composition_selected": cid, "latency_s": 0.0}
        assert settlement._constructed(tampered, constructed) is None       # its identity digest no longer holds
        unanswered = {k: v for k, v in receipt.items() if k != "receipt_id"}
        unanswered["state"] = "ABSTAIN"
        unanswered["receipt_id"] = digest(unanswered)
        assert settlement._constructed(unanswered, constructed) is None     # an abstention is no construction's answer
        assert cid in constructed and "acquired.graph.max_flow.networkx" not in constructed
    finally:
        body.__exit__(None, None, None)
