"""The inventory must not flatter the institution, and must not flatter itself.

Kimi's Final Plan names the active gate as *"no proof that one action family is
non-bypassable end to end"* and the active metric as *"Verified Mediated
Side-Effect Coverage, baseline unknown until inventory."* These tests defend the
inventory that supplies it, because a measurement nobody attacked is not a
baseline.
"""
from __future__ import annotations

import ast
import os

import pytest

from assurance.side_effects import (
    Family,
    Mediation,
    Site,
    _classify_call,
    _imported_capabilities,
    coverage,
    inventory,
    render,
)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _families(source: str) -> set[Family]:
    tree = ast.parse(source)
    found = {f for node in ast.walk(tree) if isinstance(node, ast.Call)
             for f in [_classify_call(node)] if f is not None}
    return found | {f for _, f, _ in _imported_capabilities(tree)}


# ----------------------------------------------- the evasion that was possible
def test_a_from_import_cannot_hide_a_network_capability():
    """The hole this detector actually had, closed and pinned.

    It matched `socket.socket()` and missed `from socket import socket` followed
    by a bare `socket()`. Nothing in the tree imports a network module today, so
    the zero was accidentally correct rather than defended — and an accidentally
    correct guard is not a guard.
    """
    assert Family.NETWORK in _families("from socket import socket\ns = socket()")
    assert Family.NETWORK in _families("import urllib.request")
    assert Family.NETWORK in _families("from urllib.request import urlopen")
    assert Family.PROCESS in _families("from subprocess import run\nrun(['ls'])")


def test_dotted_calls_are_still_caught():
    assert Family.NETWORK in _families("import socket\nsocket.create_connection(x)")
    assert Family.PROCESS in _families("import subprocess\nsubprocess.run(['ls'])")
    assert Family.PROCESS in _families("import os\nos.system('ls')")


def test_reads_and_path_arithmetic_are_not_side_effects():
    """A detector that flags every `open()` and `os.path.join` is ignored."""
    assert _families("open('f')") == set()
    assert _families("open('f', 'r')") == set()
    assert _families("import os\nos.path.join(a, b)") == set()
    assert _families("import os\nos.listdir(d)") == set()


@pytest.mark.parametrize("mode", ["w", "a", "x", "r+", "wb"])
def test_every_writing_mode_counts_as_a_filesystem_effect(mode):
    assert Family.FILESYSTEM in _families(f"open('f', {mode!r})")


def test_mode_passed_by_keyword_is_not_missed():
    assert Family.FILESYSTEM in _families("open('f', mode='w')")


# --------------------------------------------------- honesty of the metric
def test_coverage_returns_a_pair_so_zero_over_zero_cannot_render_as_full():
    """An empty family is not 100% coverage; it is a stronger, different claim.

    Returning a percentage would make `0/0` render as either 0% or 100%, and both
    are lies about a family the institution cannot exercise at all.
    """
    mediated, total = coverage(Family.NETWORK)
    assert (mediated, total) == (0, 0)
    assert "NO SITES" in render()
    assert "stronger than full coverage" in render()


def test_the_mediator_is_not_counted_as_evidence_for_itself():
    """policy/ mediating policy/ proves nothing and must not inflate the ratio."""
    sites = inventory()
    mediator = [s for s in sites if s.mediation is Mediation.IS_THE_MEDIATOR]
    for site in mediator:
        assert site.module.startswith("policy.")
        assert not site.counts_toward_coverage


def test_the_report_states_that_coverage_is_a_floor():
    """Static reading cannot prove runtime reachability, and the report says so.

    Without this the number would be quoted as assurance it has not earned.
    """
    text = render()
    assert "FLOOR, NOT AN ESTIMATE" in text
    assert "never a proven bypass" in text


# ------------------------------------------- the measured state of the tree
def test_the_institution_holds_no_network_capability_at_all():
    """The strongest assurance fact available, and it had never been measured.

    Not "network effects are gated" — there is no network capability in
    institutional code to gate. Checked at both call and import level, so adding
    `import socket` anywhere outside tests and scripts breaks this test.
    """
    mediated, total = coverage(Family.NETWORK)
    assert total == 0, [s for s in inventory() if s.family is Family.NETWORK]


def test_process_spawn_sites_are_known_and_confined_to_read_only_tooling():
    """Seven sites in three modules, none of them mediated. Named, not hidden.

    A subprocess can do anything, so these are the real review candidates. All
    three modules shell out to `git` for read-only history, and two of the three
    are instrumentation this branch added — the inventory indicts its author's
    own work, which is the only reason to trust it about anyone else's.
    """
    process = [s for s in inventory() if s.family is Family.PROCESS]
    modules = {s.module for s in process}
    assert modules == {"blueprint.peer_evidence", "handoff.conform",
                       "verifier.v2.verify"}, modules
    assert all(s.mediation is Mediation.UNMEDIATED_BY_STATIC_READING
               for s in process)


def test_tests_and_scripts_are_excluded_and_the_reason_is_recorded():
    """Test code opens sockets deliberately; counting it would drown the signal."""
    from assurance.side_effects import EXCLUDED

    assert "tests" in EXCLUDED and "scripts" in EXCLUDED
    assert all(EXCLUDED.values()), "every exclusion must carry its reason"
    assert not any(s.module.startswith(("tests.", "scripts."))
                   for s in inventory())
