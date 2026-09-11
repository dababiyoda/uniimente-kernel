"""Executable guards on the planning round's own integrity.

These tests are the reason the planning artifacts can be trusted as projections
rather than as forty documents that happen to agree today. They enforce, in
order: the graph is well-formed; nothing is asserted without evidence; the
Founder-Horizon Override is present and intact; unreachable repositories are
never cited; the compiler is inert and detachable; and regeneration is exactly
idempotent.

Every check that could pass vacuously carries a witness asserting it examined a
non-empty population — the failure mode PR #66 documented eight times in its own
workstream was an instrument whose silence looked like success.
"""
from __future__ import annotations

import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from planning.compiler import render, validate  # noqa: E402
from planning.compiler.model import (  # noqa: E402
    EVIDENCE_STATUSES,
    Node,
    PlanningGraph,
    load_graph,
    repo_root,
    validate_node,
)


@pytest.fixture(scope="module")
def graph() -> PlanningGraph:
    return load_graph()


# --------------------------------------------------------------- graph integrity

def test_graph_loads_and_is_not_trivially_small(graph):
    # Non-vacuity witness: every later assertion in this file is meaningless if
    # the graph failed to load and silently produced nothing.
    assert len(graph) >= validate.MIN_NODES, f"graph has only {len(graph)} nodes"


def test_graph_satisfies_its_own_invariants(graph):
    assert graph.validate() == []


def test_every_node_has_a_known_evidence_status(graph):
    for node in graph:
        assert node.evidence_status in EVIDENCE_STATUSES, node.id


def test_no_node_asserts_anything_without_evidence(graph):
    """The anti-fabrication rule: no evidence refs means status must be unresolved."""
    offenders = [
        n.id
        for n in graph
        if not n.evidence_refs and n.evidence_status not in ("unresolved", "derived")
    ]
    assert offenders == [], f"nodes asserting without evidence: {offenders}"


def test_every_derived_conclusion_traces_back_to_real_evidence(graph):
    """A conclusion resting only on other conclusions is ungrounded."""
    check = validate.check_derived_chains_are_grounded(graph)
    assert check.examined > 0, "vacuous: no derived nodes to check"
    assert check.problems == []


def test_node_ids_are_unique(graph):
    ids = [n.id for n in graph]
    assert len(ids) == len(set(ids))


def test_no_value_was_truncated_by_an_unquoted_yaml_comment(graph):
    """Guard a bug class that silently corrupted four values on first authoring.

    In YAML an unquoted ``#`` begins a comment, so a plain scalar like
    ``title: PR #66 body is stale`` loads as the single word ``PR``. It fails no
    schema, raises no error, and quietly destroys meaning — exactly the class of
    silent corruption this round exists to catch. Any value ending in a token
    that normally precedes ``#`` is treated as truncated.
    """
    suspects = ("PR", "Issue", "issue", "no", "No", "number", "#")
    truncated: list[tuple[str, str, str]] = []

    def walk(node_id: str, path: str, value) -> None:
        if isinstance(value, str):
            if value.rstrip().split(" ")[-1] in suspects and len(value.split()) <= 8:
                truncated.append((node_id, path, value))
        elif isinstance(value, dict):
            for key, sub in value.items():
                walk(node_id, f"{path}.{key}", sub)
        elif isinstance(value, list):
            for index, sub in enumerate(value):
                walk(node_id, f"{path}[{index}]", sub)

    examined = 0
    for node in graph:
        examined += 1
        walk(node.id, "title", node.title)
        walk(node.id, "body", node.body)
    assert examined > 0, "vacuous: walked no nodes"
    assert truncated == [], (
        "values look truncated by an unquoted '#'; quote the scalar: "
        f"{truncated}"
    )


def test_cross_references_resolve(graph):
    dangling = [
        (n.id, target)
        for n in graph
        for target in (n.body.get("refs") or [])
        if not graph.has(target)
    ]
    assert dangling == []


# ------------------------------------------------------- protected founder intent

def test_founder_horizon_override_is_frozen(graph):
    """The round's first instruction: freeze the Override as protected nodes."""
    intents = graph.of_kind("protected_intent")
    assert len(intents) >= 20, f"only {len(intents)} protected intent nodes"
    for node in intents:
        assert node.body.get("protected") is True, node.id
        assert node.body.get("override_section"), node.id


def test_the_load_bearing_intents_are_present(graph):
    """Named individually: losing any of these would shrink the destination.

    Override §2 forbids treating an unimplemented aspiration as an unintended
    one, so the horizon-defining nodes are asserted by id rather than by count.
    """
    for node_id in (
        "intent.identity.fixed",
        "intent.aspirations.are_destinations",
        "intent.metaphor.functional_translation",
        "intent.topology.three_region",
        "intent.track_a_track_b",
        "intent.first_developmental_proof",
        "intent.closure_ladder",
        "intent.evaluator_sovereignty",
        "intent.infinite_goal_chase",
        "intent.regenerative_civilization",
        "intent.anti_self_deception",
        "intent.round_authority",
    ):
        assert graph.has(node_id), f"protected intent {node_id} missing from the graph"


def test_round_authority_prohibitions_are_recorded(graph):
    node = graph.get("intent.round_authority")
    prohibited = node.body["prohibited_this_round"]
    for forbidden in ("merge", "deploy", "modify PR #66", "move money"):
        assert forbidden in prohibited


# ------------------------------------------------------------- unavailable sources

def test_unreachable_repositories_are_declared(graph):
    """What we could not reach must be stated, not silently omitted."""
    unavailable = graph.of_kind("repository_unavailable")
    assert len(unavailable) >= 3
    for node in unavailable:
        assert node.evidence_status == "unresolved", node.id
        assert node.body.get("reason"), node.id


def test_unreachable_repositories_are_never_cited_as_evidence(graph):
    check = validate.check_unavailable_never_cited(graph)
    assert check.examined > 0, "vacuous: examined no nodes"
    assert check.problems == []


# ------------------------------------------------------------------- inertness

def test_no_kernel_package_imports_planning():
    check = validate.check_inertness(repo_root())
    assert check.examined > 0, "vacuous: scanned no kernel python files"
    assert check.problems == []


def test_planning_only_writes_inside_planning_trees():
    """render_all is pure and targets only the three permitted trees."""
    root = repo_root()
    paths = render.render_all(load_graph(), root)
    allowed = (
        os.path.join(root, "docs", "planning"),
        os.path.join(root, "artifacts", "planning"),
    )
    for path in paths:
        assert path.startswith(allowed), f"{path} escapes the planning trees"


# ------------------------------------------------------------------ idempotence

def test_regeneration_is_byte_identical():
    """Rendering twice from one graph must produce identical bytes."""
    root = repo_root()
    first = render.render_all(load_graph(), root)
    second = render.render_all(load_graph(), root)
    assert first.keys() == second.keys()
    for path in first:
        assert first[path] == second[path], f"non-deterministic render: {path}"


def test_committed_artifacts_match_the_committed_graph():
    """Catches a hand-edited artifact, or a graph edit without a re-render."""
    root = repo_root()
    for path, content in render.render_all(load_graph(), root).items():
        rel = os.path.relpath(path, root)
        assert os.path.exists(path), f"{rel} was never generated"
        with open(path, encoding="utf-8") as handle:
            assert handle.read() == content, (
                f"{rel} differs from the graph — either it was hand-edited or the "
                "graph changed without running planning/compiler/render.py"
            )


def test_generated_artifacts_carry_provenance():
    root = repo_root()
    docs = os.path.join(root, render.DOCS_REL)
    seen = 0
    for name in sorted(os.listdir(docs)):
        if name.endswith(".md"):
            seen += 1
            with open(os.path.join(docs, name), encoding="utf-8") as handle:
                head = handle.read(400)
            assert render.GENERATED_BANNER in head, name
            assert "graph-digest:" in head, name
    assert seen > 0, "vacuous: no markdown artifacts found"


# ------------------------------------------------- the instrument can actually fail

def test_negative_control_proves_the_validator_can_fail():
    """A validator that cannot fail is not evidence. Prove it rejects bad input."""
    bad = Node(
        id="test.fabricated",
        kind="finding",
        title="claim with no evidence",
        evidence_status="verified_by_execution",
        body={},
        evidence_refs=[],
    )
    problems = validate_node(bad)
    assert problems, "validate_node accepted a node asserting with zero evidence"
    assert any("must be 'unresolved'" in p for p in problems)


def test_negative_control_entrypoint_exits_zero_when_it_catches_the_fault():
    assert validate.negative_control() == 0


def test_validator_rejects_a_graph_below_the_non_vacuity_floor(tmp_path):
    """A near-empty graph must fail rather than pass on nothing."""
    (tmp_path / "tiny.yaml").write_text(
        "nodes:\n"
        "  - id: only.one\n"
        "    kind: finding\n"
        "    title: lonely\n"
        "    evidence_status: unresolved\n",
        encoding="utf-8",
    )
    small = load_graph(str(tmp_path))
    assert len(small) < validate.MIN_NODES


def test_validator_runs_from_an_unrelated_working_directory(tmp_path):
    """§31: no hardcoded paths; identical result from any cwd."""
    script = os.path.join(repo_root(), "planning", "compiler", "validate.py")
    result = subprocess.run(
        [sys.executable, script, "--json"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert '"result": "PASS"' in result.stdout


def test_validator_reports_vacuous_checks_as_unknown_not_pass():
    """'Examined nothing' must never render as a pass."""
    check = validate.Check("synthetic")
    assert check.vacuous is True
    assert check.to_dict()["status"] == "UNKNOWN_VACUOUS"
    check.examined = 1
    assert check.to_dict()["status"] == "PASS"
