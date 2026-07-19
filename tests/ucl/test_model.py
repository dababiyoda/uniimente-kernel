"""Model tests: the semantic Constitution over the FIVE REAL .ucl files.

Asserts the real-file facts (SPEC-WP02 "Tests"): 14 non_delegable matters,
7 participant rights with 3 hard_refusal, 8 safety states, 10 sovereignty
ranks, 2 kill_conditions, humans_authorize is True, status "unratified".
Validation: missing/duplicate/ill-typed constitutional content raises
UCLError — the model fails closed, never invents content.
"""
import pytest

from kernel.ucl import Constitution, UCLError, parse

# ---------------------------------------------------------------- real files


def test_constitution_header_facts(model):
    assert model.version == "1.0.0"
    assert model.status == "unratified"
    assert model.ratified_by is None  # unratified pending founder signature
    assert model.current_state == "normal"


def test_fourteen_permanent_prohibitions(model):
    prohibitions = model.permanent_prohibitions
    assert isinstance(prohibitions, frozenset)
    assert len(prohibitions) == 14
    assert "constitutional_amendment" in prohibitions
    assert "shutdown_override" in prohibitions
    assert "unlawful_conduct" in prohibitions
    assert "physical_harm" in prohibitions
    assert "expansion_of_uniimentes_own_sovereignty" in prohibitions


def test_doctrine_humans_authorize(model):
    assert model.humans_authorize is True


def test_failure_posture(model):
    posture = model.failure_posture
    assert posture["never_fails_toward"] == "uncontrolled_external_action"
    assert posture["fails_toward"] == [
        "silence",
        "containment",
        "preservation",
        "degraded_service",
        "human_escalation",
    ]


def test_seven_participant_rights_three_hard_refusal(model):
    rights = model.participant_rights
    assert len(rights) == 7
    labels = [r.label for r in rights]
    assert labels == [
        "safety",
        "lawful_treatment",
        "no_deception",
        "data_dignity",
        "exit",
        "no_hidden_burden_transfer",
        "error_correction",
    ]
    hard_refusal = model.hard_refusal_rights
    assert len(hard_refusal) == 3
    assert {r.label for r in hard_refusal} == {"safety", "lawful_treatment", "no_deception"}
    for right in hard_refusal:
        assert right.attrs["enforcement"] == "hard_refusal"
        assert isinstance(right.attrs["rule"], str) and right.attrs["rule"]


def test_eight_safety_states_ordered_ladder(model):
    states = model.safety_states
    assert len(states) == 8
    # The ladder order is constitutional content (most to least capable).
    assert list(states) == [
        "normal",
        "constrained",
        "read_only",
        "manual_approval_only",
        "quarantined",
        "recovery",
        "archived",
        "shutdown",
    ]
    assert states["normal"] == "permitted_under_grants"
    assert states["manual_approval_only"] == "only_with_fresh_human_approval"


def test_shutdown_may_never_block(model):
    assert model.shutdown_may_never_block == [
        "any_agent",
        "any_venture_cell",
        "any_workflow",
        "any_model",
    ]


def test_ten_sovereignty_ranks(model):
    ranks = model.sovereignty_ranks
    assert len(ranks) == 10
    assert [r[0] for r in ranks] == list(range(1, 11))  # sorted, rank 1 highest
    assert ranks[0] == (1, "law_safety_rights", "external")
    assert ranks[1] == (2, "alfonso_reserved_authority", "alfonso")
    assert ranks[-1] == (10, "individual_tasks", "agents")


def test_two_kill_conditions(model):
    conditions = model.kill_conditions
    assert len(conditions) == 2
    assert {c.label for c in conditions} == {"cathedral", "self_authorization"}
    for condition in conditions:
        assert isinstance(condition.attrs["when"], str) and condition.attrs["when"]
        assert isinstance(condition.attrs["then"], str) and condition.attrs["then"]


def test_amendment_hard_rules(model):
    rules = model.amendment_hard_rules
    assert rules["no_silent_amendment"] is True
    assert rules["no_agent_amendment"] is True
    assert rules["no_retroactive_amendment"] is True
    assert rules["amendment_is_public_to_organs"] is True


def test_from_documents_matches_from_directory(constitution_documents, make_model):
    model = make_model()
    from_docs = Constitution.from_documents(constitution_documents)
    assert from_docs.to_canonical() == model.to_canonical()


def test_canonical_dump_excludes_current_state(make_model):
    normal = make_model(current_state="normal")
    quarantined = make_model(current_state="quarantined")
    assert quarantined.current_state == "quarantined"
    # Runtime posture must never change the content-addressed policy version.
    assert normal.to_canonical() == quarantined.to_canonical()


# ------------------------------------------------------------------ validation

_CONSTITUTION_MIN = """
constitution "uniimente" {
    version = "1.0.0"
    status = "unratified"
    ratified_by = null
    doctrine { humans_authorize = true }
    permanent_prohibitions { non_delegable = ["constitutional_amendment"] }
    failure_posture {
        fails_toward = ["silence"]
        never_fails_toward = "uncontrolled_external_action"
    }
}
"""

_REST_MIN = """
participant_rights "uniimente" {
    right "safety" { rule = "no harm" enforcement = "hard_refusal" }
}
safety_states "ladder" {
    state { name = "normal" external_effects = "permitted_under_grants" }
    state { name = "shutdown" external_effects = "none" }
}
shutdown_rule "authority" {
    may_never_block_or_delay = ["any_agent"]
}
sovereignty_hierarchy "uniimente" {
    level { rank = 1 name = "law_safety_rights" owner = "external" }
}
kill_condition "cathedral" { when = "w" then = "t" }
amendment_rule "constitutional_amendment" {
    hard_rules { no_agent_amendment = true }
}
"""


def _minimal_documents():
    return [parse(_CONSTITUTION_MIN), parse(_REST_MIN)]


def test_minimal_valid_constitution_builds():
    model = Constitution.from_documents(_minimal_documents())
    assert model.version == "1.0.0"
    assert model.permanent_prohibitions == frozenset({"constitutional_amendment"})
    assert list(model.safety_states) == ["normal", "shutdown"]


def test_missing_constitution_block_fails_closed():
    with pytest.raises(UCLError, match="exactly one constitution block"):
        Constitution.from_documents([parse(_REST_MIN)])


def test_duplicate_constitution_block_fails_closed():
    docs = _minimal_documents() + [parse(_CONSTITUTION_MIN)]
    with pytest.raises(UCLError, match="exactly one constitution block"):
        Constitution.from_documents(docs)


def test_missing_doctrine_fails_closed():
    bad = parse(
        """
        constitution "uniimente" {
            version = "1.0.0" status = "unratified" ratified_by = null
            permanent_prohibitions { non_delegable = ["x"] }
            failure_posture { fails_toward = ["silence"] never_fails_toward = "y" }
        }
        """
    )
    with pytest.raises(UCLError, match="doctrine"):
        Constitution.from_documents([bad, parse(_REST_MIN)])


def test_humans_authorize_must_be_bool():
    bad = parse(
        """
        constitution "uniimente" {
            version = "1.0.0" status = "unratified" ratified_by = null
            doctrine { humans_authorize = "yes" }
            permanent_prohibitions { non_delegable = ["x"] }
            failure_posture { fails_toward = ["silence"] never_fails_toward = "y" }
        }
        """
    )
    with pytest.raises(UCLError, match="humans_authorize"):
        Constitution.from_documents([bad, parse(_REST_MIN)])


def test_missing_safety_states_fails_closed():
    docs = [parse(_CONSTITUTION_MIN)] + [
        doc for doc in _minimal_documents()[1:]
    ]
    # remove the safety_states block from the second document
    docs[1].blocks = [b for b in docs[1].blocks if b.kind != "safety_states"]
    with pytest.raises(UCLError, match="safety_states"):
        Constitution.from_documents(docs)


def test_ladder_without_normal_state_fails_closed():
    bad = parse(
        """
        participant_rights "uniimente" {
            right "safety" { rule = "no harm" enforcement = "hard_refusal" }
        }
        safety_states "ladder" {
            state { name = "shutdown" external_effects = "none" }
        }
        shutdown_rule "authority" { may_never_block_or_delay = ["any_agent"] }
        sovereignty_hierarchy "uniimente" {
            level { rank = 1 name = "law_safety_rights" owner = "external" }
        }
        kill_condition "cathedral" { when = "w" then = "t" }
        amendment_rule "constitutional_amendment" {
            hard_rules { no_agent_amendment = true }
        }
        """
    )
    with pytest.raises(UCLError, match="normal"):
        Constitution.from_documents([parse(_CONSTITUTION_MIN), bad])


def test_duplicate_sovereignty_rank_fails_closed():
    bad = parse(
        """
        participant_rights "uniimente" {
            right "safety" { rule = "no harm" enforcement = "hard_refusal" }
        }
        safety_states "ladder" {
            state { name = "normal" external_effects = "permitted_under_grants" }
        }
        shutdown_rule "authority" { may_never_block_or_delay = ["any_agent"] }
        sovereignty_hierarchy "uniimente" {
            level { rank = 1 name = "a" owner = "x" }
            level { rank = 1 name = "b" owner = "y" }
        }
        kill_condition "cathedral" { when = "w" then = "t" }
        amendment_rule "constitutional_amendment" {
            hard_rules { no_agent_amendment = true }
        }
        """
    )
    with pytest.raises(UCLError, match="duplicate ranks"):
        Constitution.from_documents([parse(_CONSTITUTION_MIN), bad])


def test_unknown_current_state_fails_closed(make_model):
    with pytest.raises(UCLError, match="not on the safety_states ladder"):
        make_model(current_state="bogus_state")


def test_from_directory_missing_dir_fails_closed(tmp_path):
    with pytest.raises(UCLError, match="not found"):
        Constitution.from_directory(tmp_path / "no-such-dir")
