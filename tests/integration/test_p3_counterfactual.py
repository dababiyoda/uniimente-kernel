"""P3 — the first cross-repository four-state counterfactual, run for real.

This is the test that answers frozen-contract conditions 2 and 7 for the seam:
does a running process actually *consume* ``institutional.cross_organ_edge_
resolution``, and does work actually *route through* it? A detached benchmark
cannot satisfy either, which is why nothing here is mocked.

Skipped — never failed — when the DALEOBANKS and WealthMachineIntelligence
checkouts are absent. An unrunnable experiment reported as a pass is the exact
failure this workstream has produced before; reported as a boundary failure it
would be equally wrong.
"""
from __future__ import annotations

import pytest

from runtime.seam import bindings_p3
from runtime.seam.episode import EpisodeUnrunnable, run_episode


@pytest.fixture(scope="module")
def episode() -> dict:
    available, why = bindings_p3.organs_available()
    if not available:
        pytest.skip(f"cross-repository episode cannot run here: {why}")
    try:
        return run_episode()
    except EpisodeUnrunnable as exc:      # pragma: no cover - environment
        pytest.skip(f"episode unrunnable: {exc}")


def _state(episode: dict, name: str) -> dict:
    return next(s for s in episode["states"] if s["state"] == name)


def _control(episode: dict, name: str) -> dict:
    return next(c for c in episode["controls"] if c["control"] == name)


# --- the four states --------------------------------------------------------

def test_state_a_healthy_produces_an_assessment(episode):
    a = _state(episode, "A_healthy")
    assert a["routes"] == 1, f"no route materialised: {a['refused']}"
    assert a["assessment_present"], f"healthy state produced nothing: {a.get('error')}"


def test_state_b_damaged_loses_the_function(episode):
    """Not a failing health probe — an absent function.

    This is what disqualified Route A: disabling edge resolution there would
    have made a self-check report unhealthy, which is the institution noticing
    a problem rather than the institution losing a capability.
    """
    b = _state(episode, "B_damaged")
    assert b["routes"] == 0
    assert not b["assessment_present"]
    assert "ROUTE_NOT_ESTABLISHED" in (b["error"] or "")


def test_state_c_repair_restores_the_function(episode):
    c = _state(episode, "C_repaired")
    assert c["routes"] == 1
    assert c["assessment_present"]


def test_state_d_rollback_reapplies_the_damage(episode):
    """A loss that cannot be reproduced was never really a loss."""
    d = _state(episode, "D_rolled_back")
    assert d["routes"] == 0
    assert not d["assessment_present"]


def test_the_four_states_discriminate(episode):
    assert episode["discriminates"], (
        "healthy and damaged were not behaviourally different; the episode "
        "measures nothing"
    )


# --- controls: without these the four states prove nothing -------------------

def test_a_binding_without_a_proven_edge_is_refused(episode):
    ctrl = _control(episode, "binding_without_proven_edge")
    assert ctrl["fired"], (
        "a binding for an organ with no proven edge still routed — the router "
        "is matching on something other than the linker's edges"
    )


def test_the_bypass_detector_is_alive(episode):
    """The decisive control.

    WealthMachineClient's credential-free default is ``mock``, where DALEOBANKS
    computes the assessment itself. If that path can execute undetected, then
    'no bypass in STATE B' means nothing at all.
    """
    ctrl = _control(episode, "bypass_binding_detected")
    assert ctrl["fired"], f"the bypass detector did not fire: {ctrl['outcome']}"
    assert "wealthmachine_client" in ctrl["outcome"]


def test_the_decisive_path_never_touches_the_transport_client(episode):
    for name in ("A_healthy", "C_repaired"):
        receipt = _state(episode, name)["receipt"]
        assert receipt["bypass_candidates"] == [], (
            f"{name} executed the bypass: {receipt['bypass_candidates']}"
        )


def test_the_assessment_really_came_from_wealthmachine(episode):
    """Non-vacuity: the consumer's own repository must have executed."""
    a = _state(episode, "A_healthy")
    assert a["executed_files_in_consumer_repo"] > 0
    evidence = a["receipt"]["consumer_evidence"]
    assert evidence["module"] == "src.services.opportunity_intake"
    assert evidence["module_file"].startswith(bindings_p3.WEALTHMACHINE_ROOT)
    assert evidence["method"] == "evaluate_packet"


# --- invariants that must not move ------------------------------------------

def test_human_approval_invariant_holds(episode):
    assert episode["human_approval_invariant_held"], (
        "an assessment came back without requires_human_approval"
    )


def test_the_seam_granted_no_authority(episode):
    for name in ("A_healthy", "C_repaired"):
        assert _state(episode, name)["receipt"]["authority_granted"] is False


def test_geometry_b_holds_end_to_end(episode):
    from runtime.seam.router import CONTRACT_DELIVERY_EVENT

    for name in ("A_healthy", "C_repaired"):
        receipt = _state(episode, name)["receipt"]
        assert receipt["event_type"] == CONTRACT_DELIVERY_EVENT
        assert bindings_p3.CONTRACT not in receipt["event_type"]


def test_verdict_requires_every_component(episode):
    """PROVEN needs discrimination AND live controls AND a non-vacuous run."""
    if episode["verdict"] == "RUNTIME_CONSUMPTION_PROVEN":
        assert episode["discriminates"]
        assert episode["controls_fired"]
        assert episode["non_vacuous"]
        assert episode["human_approval_invariant_held"]
    else:                                  # pragma: no cover - failure path
        pytest.fail(f"episode verdict: {episode['verdict']}")


def test_the_episode_writes_nothing_into_the_kernel_repository(episode):
    """Inertness, measured rather than asserted.

    Two real escapes were found and fixed: importing the organs rewrote
    nineteen tracked ``.pyc`` files inside WealthMachineIntelligence, a declared
    read-only repository; and WMI's agent store logged to
    ``data/agent_store.jsonl`` relative to the working directory, landing inside
    the kernel checkout. Both were caused by import-time behaviour, so
    containment has to start before the producer runs.
    """
    import os

    repo_root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    assert not os.path.exists(os.path.join(repo_root, "data")), (
        "the episode deposited an organ-local data directory in the kernel"
    )


def test_organ_side_effects_were_contained_and_counted(episode):
    """A side effect nobody counted is the kind that later turns out to matter."""
    a = _state(episode, "A_healthy")
    assert a["organ_files_written_in_scratch"], (
        "the organs wrote nothing at all — either containment is measuring the "
        "wrong directory, or the consumer never really ran"
    )


def test_the_record_states_which_organ_revisions_ran(episode):
    """Evidence must not let pinned provenance be inferred where none exists.

    This implementation does not enforce the manifest pin — the canonical probe
    does, and a second enforcer would be a second authority over one question.
    What it must do is say which revision it ran, so a reader never assumes.
    """
    revisions = episode["organ_revisions"]
    for organ in ("daleobanks", "wealthmachine"):
        assert revisions[organ]["head"], f"no revision recorded for {organ}"
        assert "matches_manifest_pin" in revisions[organ]


def test_unrunnable_is_not_reachable_as_a_pass():
    assert issubclass(EpisodeUnrunnable, RuntimeError)
