"""CANARY-0001: preregistered, rehearsed, and incapable of claiming reality.

FOUNDER-RULING-2026-08-22 ruling 8 required an External Reality Graduation
Packet and, in the same breath, that the wall not be weakened: *"HARDENED = 0
and CVO/SBM = 0 are currently useful truths. Keep them true until reality
changes them."*

The dangerous object in this directory is the rehearsal. A consequence-inert
run that could move the Single Bottleneck Metric would let internal effort look
like external proof — the precise failure the whole institution is built to
refuse. Most of what follows exists to make that impossible rather than merely
unlikely.
"""
from __future__ import annotations

import ast
import os

import pytest

from graduation import candidates, packet, rehearsal
from graduation.packet import PACKET, PREREGISTRATION_SHA256
from graduation.rehearsal import (
    REHEARSAL_MARKER,
    REHEARSAL_PREFIX,
    RehearsalRefused,
    rehearse,
)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ------------------------------------------------------- preregistration
def test_the_preregistration_seal_matches_what_is_committed():
    """An edit to what counts as success must fail the build, not pass quietly."""
    assert PACKET.preregistration.seal() == PREREGISTRATION_SHA256


def test_the_seal_moves_when_a_success_criterion_changes():
    """The guard is exercised, not assumed.

    A seal nobody has watched break is a seal nobody knows is connected.
    """
    from dataclasses import replace

    tampered = replace(
        PACKET.preregistration,
        success_criteria=PACKET.preregistration.success_criteria + ("or close enough",))
    assert tampered.seal() != PREREGISTRATION_SHA256


def test_the_seal_covers_prediction_and_criteria_and_not_operational_detail():
    """Deliberately narrow: operational fields can be corrected, criteria cannot."""
    from dataclasses import replace

    # Changing the rollback text is an operational correction and must not
    # disturb the seal — the seal is over the preregistration only.
    moved = replace(PACKET, rollback="a different rollback description")
    assert moved.sealed == PREREGISTRATION_SHA256

    # Changing the predicted confidence is a change to the experiment.
    changed = replace(PACKET.preregistration, predicted_confidence=0.95)
    assert changed.seal() != PREREGISTRATION_SHA256


def test_the_prediction_is_not_flattering():
    """A first integration predicted at 0.9 would be miscalibrated on arrival.

    The point of preregistering a confidence is to be wrong in public when
    wrong. A number chosen to look good defeats the mechanism before it runs.
    """
    assert 0.3 <= PACKET.preregistration.predicted_confidence <= 0.7


def test_failure_criteria_include_the_failure_this_canary_exists_to_detect():
    """A claimed effect with no consequence is the whole reason for a canary."""
    failures = " ".join(PACKET.preregistration.failure_criteria)
    assert "returns success but no item exists" in failures
    assert "self-attestation" in failures.lower() or "attesting" in failures


# ----------------------------------------------------- it authorizes nothing
def test_the_packet_is_not_an_authorization():
    assert PACKET.is_authorized is False
    assert PACKET.authorized_by is None
    assert PACKET.authorization_ref is None


def test_no_code_path_sets_authorized_by():
    """Structural. A packet that could authorise itself is the thing forbidden.

    FBO: no component may authorize its own promotion or expand its own
    sovereignty. Here that means the field exists to be filled by a founder and
    by nothing in this package.
    """
    for name in ("packet.py", "rehearsal.py", "candidates.py"):
        with open(os.path.join(ROOT, "graduation", name), encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.keyword) and node.arg in (
                    "authorized_by", "authorization_ref"):
                assert isinstance(node.value, ast.Constant) and node.value.value is None, (
                    f"{name} sets {node.arg} to a non-None value")
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Attribute) and target.attr in (
                            "authorized_by", "authorization_ref"):
                        pytest.fail(f"{name} assigns {target.attr}")


def test_the_module_states_it_is_unexecuted_and_unauthorized():
    assert "NOT EXECUTED AND NOT AUTHORIZED" in packet.EXECUTION_STATUS
    assert "do not execute" in packet.EXECUTION_STATUS.lower()


# ------------------------------------------- the rehearsal cannot claim reality
def test_a_rehearsal_result_can_never_prove_external_reality():
    """No flag, no argument, no path makes this True."""
    result = rehearsal.RehearsalResult(completed=True, reached=())
    assert result.proves_external_reality is False
    assert result.is_rehearsal is True
    assert result.clean_verified_outcomes == 0


def test_proves_external_reality_is_a_property_with_no_setter():
    """Structural: it returns a literal False and reads no state.

    A property computed from a field could be made True by setting the field.
    This one cannot be influenced at all.
    """
    with open(os.path.join(ROOT, "graduation", "rehearsal.py"),
              encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "proves_external_reality")
    returns = [n for n in ast.walk(fn) if isinstance(n, ast.Return)]
    assert len(returns) == 1
    assert isinstance(returns[0].value, ast.Constant)
    assert returns[0].value.value is False


def test_a_rehearsal_refuses_a_target_that_is_not_marked_as_one():
    """The difference between a rehearsal and an unauthorised publication."""
    with pytest.raises(RehearsalRefused, match="not a rehearsal target"):
        rehearse(gate=object(), actor="mp-1", legal_principal="Alfonso Lopez",
                 target="https://example.com/real")


@pytest.mark.parametrize("target", [
    "https://daleobanks.example/post",
    "rehearsal",                      # missing the scheme separator
    "REHEARSAL://upper",              # case matters; refuse rather than normalise
    "x-rehearsal://sneaky",
    "",
])
def test_only_the_exact_rehearsal_prefix_is_accepted(target):
    with pytest.raises(RehearsalRefused):
        rehearse(gate=object(), actor="mp-1", legal_principal="Alfonso Lopez",
                 target=target)


def test_the_rehearsal_module_contains_no_network_primitive():
    """The one substitution is at the outermost point; nothing else is stubbed.

    Which means this module must itself be inert, or the 'consequence-inert'
    claim is false at its own boundary.
    """
    banned_imports = {"socket", "http", "urllib", "requests", "httpx", "asyncio",
                      "subprocess", "ssl", "socketserver"}
    banned_calls = {"socket", "urlopen", "connect", "bind", "listen", "Popen",
                    "getaddrinfo", "create_connection"}
    with open(os.path.join(ROOT, "graduation", "rehearsal.py"),
              encoding="utf-8") as fh:
        tree = ast.parse(fh.read())

    offenders = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            offenders += [a.name for a in node.names
                          if a.name.split(".")[0] in banned_imports]
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module.split(".")[0] in banned_imports:
                offenders.append(node.module)
        elif isinstance(node, ast.Call):
            func = node.func
            attr = func.attr if isinstance(func, ast.Attribute) else (
                func.id if isinstance(func, ast.Name) else None)
            if attr in banned_calls:
                offenders.append(attr)
    assert not offenders, f"the rehearsal is not inert: {offenders}"


def test_the_rehearsal_marker_is_unmissable_in_the_record():
    """A later reader of the ledger must not mistake a rehearsal for a run."""
    assert "NOT_REAL" in REHEARSAL_MARKER
    assert REHEARSAL_PREFIX.endswith("://")


# ----------------------------------------------- the comparison was real
def test_the_selected_canary_was_chosen_by_score_not_by_suggestion():
    """The founder suggested a publication and asked that it compete anyway."""
    ranked = candidates.ranked()
    assert len(ranked) >= 3, "a comparison needs alternatives to be one"
    assert candidates.selected().candidate_id == ranked[0].candidate_id
    assert PACKET.canary_id == "CANARY-0001"
    assert candidates.selected().candidate_id == "CAN-A-publication"
    # It wins on total, and the runner-up is close enough to be a real rival.
    assert ranked[0].total > ranked[1].total
    assert ranked[1].total >= ranked[0].total - 4


def test_every_candidate_carries_an_argument_not_only_a_score():
    """A table of numbers with no reasoning is a predetermined answer dressed up."""
    for candidate in candidates.CANDIDATES:
        assert len(candidate.argument) > 200, candidate.candidate_id


def test_the_forbidden_candidate_is_scored_and_kept_rather_than_dropped():
    """Recording that the most informative option is the forbidden one is the
    honest answer to 'why not just run the decisive experiment'."""
    payment = next(c for c in candidates.CANDIDATES
                   if c.candidate_id == "CAN-E-micropayment")
    assert payment.information_value == 5
    assert not payment.eligible
    assert "money movement" in payment.disqualifier
    assert payment not in candidates.ranked()


def test_the_read_only_option_is_rejected_for_the_right_reason():
    """Cheapest and most reversible, and it tests nothing that matters."""
    fetch = next(c for c in candidates.CANDIDATES
                 if c.candidate_id == "CAN-B-readonly-fetch")
    assert fetch.reversibility == 5
    assert fetch.information_value <= 1
    assert "nothing for reconciliation to reconcile" in fetch.argument


# ------------------------------------------------------------- the blockers
def test_the_blockers_are_reported_and_none_can_be_cleared_here():
    found = packet.blockers()
    joined = " ".join(found)
    assert "founder authorization" in joined
    assert "credential" in joined
    assert "network surface" in joined
    # And the one the institution can still act on is named as such.
    assert any("witness contract v2" in b for b in found)


def test_the_packet_names_the_second_canary_rather_than_hiding_the_runner_up():
    notes = " ".join(PACKET.notes)
    assert "CAN-C" in notes
    assert "second canary" in notes
