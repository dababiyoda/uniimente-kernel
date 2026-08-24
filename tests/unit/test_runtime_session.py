"""Adoption: the first caller that actually boots the institution.

`runtime/` composed a durable body. This is the module that proves something
uses it, which is a different fact and the only one that counts as progress —
the distinction `identity/pki/` was held to when it shipped adversarially tested
and deliberately unadopted, and `identity/mesh.py` then satisfied a day later.

The decisive test is `test_a_full_traversal_is_readable_from_a_later_process`:
Bridge A crosses three organs in one process, every object is discarded, and a
second process reads the four events, their causal ancestry and the verified
chain back out of the state directory.
"""
from __future__ import annotations

import json
import os

import pytest

from runtime import BootRefused
from runtime.__main__ import main
from runtime.session import FIXTURE_ASSESSMENT, FIXTURE_PACKET, Session


@pytest.fixture()
def state_dir(tmp_path):
    return str(tmp_path / "institution")


# ================================================================== the traversal
def test_a_traversal_completes_over_a_durable_ledger(state_dir):
    session = Session.open(state_dir)
    traversal = session.rehearse()

    assert traversal.completed, traversal.reason
    assert len(traversal.event_ids) == 4
    assert traversal.causal_depth == 4, (
        "four events in the same ledger is adjacency; four in one ancestry is a "
        "pathway, and only the second is what Bridge A claims")
    assert traversal.records_after > traversal.records_before


def test_a_full_traversal_is_readable_from_a_later_process(state_dir):
    """The adoption proof. Nothing but the directory crosses the boundary."""
    first = Session.open(state_dir)
    traversal = first.rehearse()
    assert traversal.completed
    ids = set(traversal.event_ids)
    first.close(sealed_by="alfonso", reason="end of session")
    del first, traversal

    second = Session.open(state_dir)

    assert second.runtime.report.resumed is True
    assert second.runtime.report.events_replayed == 4
    replayed = {e["event_id"] for e in second.history()}
    assert ids <= replayed, "the earlier process's traversal is still in the chain"
    assert [e["type"] for e in second.history()] == [
        "bridge.opportunity_signal_received",
        "bridge.opportunity_signal_accepted",
        "bridge.venture_assessment_received",
        "bridge.decision_episode_recorded",
    ]
    ok, detail = second.runtime.ledger.verify_chain()
    assert ok, detail


def test_evidence_accumulates_across_sessions_rather_than_resetting(state_dir):
    """Two rehearsals in two processes leave two traversals, not one."""
    Session.open(state_dir).rehearse()
    second = Session.open(state_dir)
    assert second.runtime.report.events_replayed == 4
    second.rehearse()

    third = Session.open(state_dir)
    assert third.runtime.report.events_replayed == 8


def test_a_rehearsal_claims_nothing_about_the_outside_world(state_dir):
    """A pathway exercised on fixtures is connected, not proven.

    The field is on the record rather than left to context, because context does
    not travel with a record that a later reader finds on its own.
    """
    traversal = Session.open(state_dir).rehearse()
    assert traversal.proves_external_reality is False


# ============================================== the whole chain, one durable ledger
def _branch(kind):
    from evolution.strategy_tree import StrategyBranch

    return StrategyBranch(
        kind=kind, title=f"{kind} branch",
        governing_assumption="the narrowing holds under selection",
        mechanism="experiment.run", required_capabilities=["experiment.run"],
        cost_usd=0.0, founder_attention_minutes=10, time_to_proof_days=1,
        authority_requirements=["kernel.grant"], irreversible_downside="none",
        expected_result="the metric clears its threshold",
        strongest_counterargument="the metric may be measuring the wrong thing",
        cheapest_falsification_test="re-run against the frozen corpus",
        kill_condition="measured exceeds 100")


def _analysis():
    """The caller's analysis, built here because it is the caller's to build.

    `Session` deliberately has no method that produces a strategy tree. A
    composition root that generated its own would be inventing the
    institutional judgement Bridge B exists to refuse to proceed without.
    """
    from evolution.spider_web import (COMPLETENESS_REQUIREMENTS, EIGHT_SIDES,
                                      SpiderWebAudit)
    from evolution.strategy_tree import BRANCH_KINDS, StrategyTree

    tree = StrategyTree(bottleneck="no verified outcome exists",
                        objective="resolve one decisive unknown")
    for kind in BRANCH_KINDS:
        tree.add(_branch(kind))
    audit = SpiderWebAudit(subject="the selected branch")
    for side in EIGHT_SIDES:
        audit.set_side(side, True, notes="probe")
    for requirement in COMPLETENESS_REQUIREMENTS:
        audit.set_completeness(requirement, True)
    return tree, audit


def _chain(session):
    """A -> B -> C, each fed by the last, over one durable ledger."""
    tree, audit = _analysis()
    a = session.rehearse()
    b = session.traverse_venture_to_experiment(
        a.run.assessment, tree, audit,
        decisive_unknown="does the pathway hold end to end",
        selected_branch_id=tree.branches[0].branch_id,
        selection_reason="cheapest falsification per hour of founder attention",
        metric="verified_outcomes", baseline=0.0, threshold=1.0, direction="gte")
    c = session.traverse_experiment_to_reality(b.run.experiment,
                                               measure=lambda spec: 1.0)
    return a, b, c


def test_the_whole_bridge_chain_runs_over_one_durable_ledger(state_dir):
    """A's output is B's input is C's input, and all of it lands in one chain.

    Three adjacent traversals into three separate in-memory ledgers is what this
    replaces. The evidence of the whole pathway now accumulates in one place
    that outlives the process.
    """
    session = Session.open(state_dir)
    a, b, c = _chain(session)

    assert (a.completed, b.completed, c.completed) == (True, True, True), \
        (a.reason, b.reason, c.reason)
    assert (a.bridge, b.bridge, c.bridge) == ("A", "B", "C")
    assert c.run.resolved is True
    assert c.run.gate_state == "recorded"
    assert c.records_after > a.records_before
    ok, detail = session.runtime.ledger.verify_chain()
    assert ok, detail


def test_the_whole_chain_is_still_there_after_a_restart(state_dir):
    """The point of doing it over a runtime rather than three ledgers."""
    first = Session.open(state_dir)
    a, b, c = _chain(first)
    depth = len(first.runtime.ledger.records)
    receipt = c.run.receipt_hash
    del first, a, b, c

    second = Session.open(state_dir)

    assert second.runtime.report.resumed is True
    assert len(second.runtime.ledger.records) == depth + 1   # +1 boot record
    assert second.runtime.ledger.find(receipt) is not None
    assert second.runtime.ledger.verify_chain()[0]


def test_bridge_b_and_c_records_do_not_claim_a_causal_depth(state_dir):
    """Only Bridge A exposes an ancestry walker.

    `causal_depth` is None for B and C rather than 0 — absent and empty are
    different findings, and a 0 would read as "walked the ancestry and found
    none", which is not what happened.
    """
    session = Session.open(state_dir)
    a, b, c = _chain(session)
    assert a.causal_depth == 4
    assert b.causal_depth is None and c.causal_depth is None


def test_a_traversal_record_keeps_the_bridge_s_own_result(state_dir):
    """No information lost in the wrapper.

    Each bridge reports things the summary does not — B its rejected branches,
    C its granted-versus-requested budget. A record that flattened them would be
    the silent loss `adapters/` forbids by name, so the native run is carried
    whole and the summary states only what it *adds*.
    """
    session = Session.open(state_dir)
    a, b, c = _chain(session)

    assert b.run.rejected_branches, "B's preserved losers survive the wrapper"
    assert b.run.audit_verdict == "COMPLETE"
    assert c.run.requested_budget_usd is not None
    assert c.run.measured == 1.0 and c.run.threshold == 1.0
    assert a.run.signal is not None


def test_the_session_mints_no_grant_for_bridge_c(state_dir):
    """Bridge C never funds itself, and neither does its composition root."""
    import inspect

    import runtime.session as module
    assert "issue_single_action" not in inspect.getsource(module)


def test_bridge_c_refuses_an_actor_that_a_previous_session_issued(state_dir):
    """A caller holding a real actor id across a restart must not get to reuse it.

    The id below is genuinely issued and genuinely valid in the first session —
    not a made-up string, which would only prove the Gate rejects nonsense. What
    is being asserted is that a *real* passport stops working once the session
    that issued it is gone, because the registry is re-issued rather than
    restored.
    """
    first = Session.open(state_dir)
    _, b, _ = _chain(first)
    issued = first.runtime.passports.issue(
        kind="agent", creator="alfonso", owner_organ="uniimente-kernel",
        legal_principal="alfonso_lopez",
        declared_capabilities=["experiment.run"], budget_ceiling_usd=5.0,
        consequence_class="internal_write").passport_id
    assert first.runtime.passports.verify(issued)[0] is True
    spec = b.run.experiment
    del first

    second = Session.open(state_dir)
    record = second.traverse_experiment_to_reality(
        spec, measure=lambda s: 1.0, actor=issued)

    assert record.completed is False
    assert second.runtime.passports.verify(issued) == (False, "unknown_identity")


# =============================================================== what a session holds
def test_the_identity_mesh_is_re_minted_per_session(state_dir):
    """Same rule as passports, one layer up: workload certificates are
    short-lived credentials, so a session mints its own rather than reloading
    anyone else's."""
    first = Session.open(state_dir)
    first_serial = first.mesh.identity_for("bridge_daleobanks").serial
    del first

    second = Session.open(state_dir)
    assert second.mesh.identity_for("bridge_daleobanks").serial != first_serial


def test_one_mesh_is_shared_across_a_session_s_traversals(state_dir, monkeypatch):
    """The reason `run` takes a `mesh` at all — a session is one anchor.

    Asserted by watching what the bridge is handed, not by comparing the
    session's mesh to itself: `identity_for` is stable within a mesh, so that
    comparison holds whether or not the session passes its mesh down, and would
    pass just as well if `traverse` forgot the argument entirely.
    """
    import bridges.signal_to_venture as bridge

    seen = []
    original = bridge.run
    monkeypatch.setattr(bridge, "run",
                        lambda *a, **kw: (seen.append(kw.get("mesh")), original(*a, **kw))[1])

    session = Session.open(state_dir)
    session.rehearse()
    session.rehearse()

    assert len(seen) == 2
    assert seen[0] is seen[1] is session.mesh, (
        "each traversal must get the session's own mesh; a fresh one per "
        "traversal would re-mint every workload identity mid-session")


def test_a_session_refuses_the_same_ground_the_runtime_refuses(state_dir):
    """`Session.open` must not soften `boot`'s fail-closed conditions."""
    from provenance.ledger import EvidenceLedger

    os.makedirs(state_dir, exist_ok=True)
    EvidenceLedger("sha256:" + "f" * 64,
                   path=os.path.join(state_dir, "ledger.jsonl")).append("witness", {})

    with pytest.raises(BootRefused):
        Session.open(state_dir)


# ========================================================================= the CLI
def test_the_command_boots_rehearses_and_exits_clean(state_dir, capsys):
    assert main([state_dir, "--rehearse"]) == 0
    out = capsys.readouterr().out
    assert "fresh from" in out
    assert "rehearsal      completed" in out
    assert "proves_external_reality = False" in out


def test_the_command_reads_an_earlier_process_back(state_dir, capsys):
    main([state_dir, "--rehearse"])
    capsys.readouterr()

    assert main([state_dir]) == 0
    out = capsys.readouterr().out
    assert "resumed from" in out
    assert "4 replayed" in out
    assert "bridge.decision_episode_recorded" in out


def test_a_refused_boot_exits_louder_than_a_halt(state_dir, capsys):
    """2 for a refusal, 1 for a halt. A halted traversal is the institution
    working; a refused boot is it declining to run on ground it does not trust,
    and a caller reading only the exit code must be able to tell them apart."""
    from provenance.ledger import EvidenceLedger

    os.makedirs(state_dir, exist_ok=True)
    EvidenceLedger("sha256:" + "f" * 64,
                   path=os.path.join(state_dir, "ledger.jsonl")).append("witness", {})

    assert main([state_dir]) == 2
    assert "BOOT REFUSED" in capsys.readouterr().err


def test_the_command_grants_nothing(capsys):
    assert main(["--help"]) == 0
    import inspect

    import runtime.__main__ as cli
    source = inspect.getsource(cli)
    assert "issue_single_action" not in source
    assert "issue(" not in source


# ==================================================================== the fixtures
def test_the_rehearsal_uses_committed_fixtures_not_invented_data():
    """A rehearsal that made up its own packet would be testing the test.

    Both files are the ones `tests/integration/test_bridge_signal_to_venture.py`
    already runs against, so the CLI path and the integration path cannot drift
    into rehearsing different things.
    """
    for path in (FIXTURE_PACKET, FIXTURE_ASSESSMENT):
        assert os.path.isfile(path), path
        with open(path, encoding="utf-8") as handle:
            assert json.load(handle), f"{path} is empty"

    integration = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "integration", "test_bridge_signal_to_venture.py")
    text = open(integration, encoding="utf-8").read()
    assert "wire_opportunity_packet.json" in text
    assert "wire_venture_assessment.json" in text
