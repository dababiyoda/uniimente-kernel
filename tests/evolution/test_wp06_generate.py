"""WP-06 BranchGenerator suite (SPEC-WP06 4.2).

The generator enumerates the declared MutationSpace exactly (control
excluded), with deterministic content and the audit declaration embedded as
a parseable variant_config block. Fail-closed paths: unscored variant,
malformed rubric/declarations, invalid agent_callable drafts. MutationSpace
validation: empty axis refused, blank values refused, control must appear.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from kernel.contracts.evolution import StrategyBranch
from kernel.evolution import (
    BranchGenerator,
    CycleError,
    MutationSpace,
    parse_variant_config,
)
from kernel.evolution.generate import DEFAULT_DECLARATION

from scripts.run_fast_cycle import DECLARATIONS, SCORING, make_generator, make_space


def test_generator_enumerates_space_exactly_control_excluded():
    drafts = make_generator().generate(make_space())
    variants = [parse_variant_config(d)["variant_id"] for d in drafts]
    assert variants == ["stream", "chunk64", "chunk256", "no_commit_stream"]
    assert all(d.tree_id == "" for d in drafts)  # drafts only
    assert all(d.status == "proposed" for d in drafts)
    by_variant = {parse_variant_config(d)["variant_id"]: d for d in drafts}
    assert by_variant["stream"].scores == {
        "expected_value": 0.9,
        "risk": 0.1,
        "reversibility": 1.0,
        "cost": 0.2,
    }
    assert by_variant["stream"].expected_delta == -0.999
    assert by_variant["chunk256"].expected_delta == -0.744
    # Titles/hypotheses name the variant and its axes.
    assert "stream" in by_variant["stream"].title
    assert "fetch_strategy=stream" in by_variant["stream"].title
    assert "fetchall" in by_variant["stream"].title  # the control is named
    assert all(d.metric_id == make_space().metric_id for d in drafts)


def test_generator_content_is_deterministic_ids_are_fresh():
    first = make_generator().generate(make_space())
    second = make_generator().generate(make_space())
    for a, b in zip(first, second):
        assert a.title == b.title
        assert a.hypothesis == b.hypothesis
        assert a.scores == b.scores
        assert a.expected_delta == b.expected_delta
        assert a.id != b.id  # ids are uuid4


def test_unscored_variant_fails_closed():
    space = MutationSpace(
        objective="o",
        metric_id="m",
        axes={"fetch_strategy": ["fetchall", "stream", "mystery"]},
        control_variant="fetchall",
    )
    generator = BranchGenerator(
        {"stream": dict(SCORING["stream"])}, declarations=None
    )
    with pytest.raises(CycleError, match="no pre-registered scores"):
        generator.generate(space)


def test_malformed_rubric_fails_closed():
    space = MutationSpace(
        objective="o",
        metric_id="m",
        axes={"fetch_strategy": ["fetchall", "stream"]},
        control_variant="fetchall",
    )
    bad = {"stream": {"expected_value": 0.9, "risk": 0.1, "reversibility": 1.0}}
    with pytest.raises(CycleError, match="lacks rubric keys"):
        BranchGenerator(bad).generate(space)
    with pytest.raises(ValueError, match="non-empty scoring map"):
        BranchGenerator({})


def test_declarations_embedded_and_default_safe():
    drafts = make_generator().generate(make_space())
    configs = {parse_variant_config(d)["variant_id"]: parse_variant_config(d) for d in drafts}
    assert configs["stream"]["commit_strategy"] == "commit_after"
    assert configs["no_commit_stream"]["commit_strategy"] == "commit_never"
    assert configs["stream"]["modifies"] == []
    assert configs["stream"]["new_dependencies"] == []
    # Without a declarations map every variant carries the safe default.
    space = MutationSpace(
        objective="o",
        metric_id="m",
        axes={"fetch_strategy": ["fetchall", "stream"]},
        control_variant="fetchall",
    )
    (draft,) = BranchGenerator({"stream": dict(SCORING["stream"])}).generate(space)
    config = parse_variant_config(draft)
    assert config["commit_strategy"] == DEFAULT_DECLARATION["commit_strategy"]
    assert config["modifies"] == []


def test_missing_declaration_fails_closed():
    space = make_space()
    generator = BranchGenerator(SCORING, declarations={"stream": dict(DECLARATIONS["stream"])})
    with pytest.raises(CycleError, match="no audit declaration"):
        generator.generate(space)


def test_space_validation_empty_axis_and_unknown_control_refused():
    with pytest.raises(ValidationError, match="at least one axis"):
        MutationSpace(objective="o", metric_id="m", axes={}, control_variant="c")
    with pytest.raises(ValidationError, match="at least one value"):
        MutationSpace(
            objective="o", metric_id="m", axes={"a": []}, control_variant="c"
        )
    with pytest.raises(ValidationError, match="must appear among the axis values"):
        MutationSpace(
            objective="o",
            metric_id="m",
            axes={"a": ["x"]},
            control_variant="not-in-space",
        )


def _agent_draft(**overrides) -> StrategyBranch:
    fields = dict(
        title="Agent draft",
        hypothesis="agent-authored hypothesis",
        metric_id="pg_spine_verify_peak_rows",
        expected_delta=-0.5,
        scores={"expected_value": 0.6, "risk": 0.1, "reversibility": 1.0, "cost": 0.3},
    )
    fields.update(overrides)
    return StrategyBranch(**fields)


def test_agent_callable_drafts_validated_and_merged():
    drafts = make_generator().generate(
        make_space(), agent_callable=lambda space: [_agent_draft()]
    )
    assert len(drafts) == 5
    assert drafts[-1].title == "Agent draft"


def test_agent_callable_invalid_drafts_refused():
    with pytest.raises(CycleError, match="StrategyBranch instances"):
        make_generator().generate(make_space(), agent_callable=lambda space: [{"no": 1}])
    with pytest.raises(CycleError, match="tree_id=''"):
        make_generator().generate(
            make_space(), agent_callable=lambda space: [_agent_draft(tree_id="t" * 32)]
        )
    with pytest.raises(CycleError, match="lacks score keys"):
        make_generator().generate(
            make_space(),
            agent_callable=lambda space: [_agent_draft(scores={"expected_value": 0.5})],
        )
    with pytest.raises(CycleError, match="returned None"):
        make_generator().generate(make_space(), agent_callable=lambda space: None)
