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
