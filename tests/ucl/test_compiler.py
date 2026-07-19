"""Compiler tests: golden intents through the compiled constitution.

Per SPEC-WP02 "Compiled policy_fn semantics" and "Tests":
C1 PERMIT, C2 REQUIRE_HUMAN, C5 DENY, reserved-matter intent
(action_type="constitutional_amendment") DENY, participant_harm intent DENY,
shutdown-state intents (read_only C1 PERMIT / C2 DENY, manual_approval_only
C2 REQUIRE_HUMAN), and determinism (same intent compiled twice -> identical
trace). The compiler never emits PERMIT for classes >= C2.
"""
import pytest

from kernel.gate.fingerprint import intent_fingerprint
from kernel.ucl import UCLError, compile_policy_fn
from kernel.ucl.version import policy_version

from .conftest import evaluate, make_intent

ALL_CLASSES = ("C0", "C1", "C2", "C3", "C4", "C5")

# ------------------------------------------------------- consequence defaults


@pytest.mark.parametrize("cls", ["C0", "C1"])
def test_internal_classes_permit(policy_fn, versions, cls):
    decision = evaluate(policy_fn, make_intent(consequence_class=cls), versions)
    assert decision.effect == "PERMIT"
    assert decision.governing_clauses == [f"consequence_default:{cls}:PERMIT"]


def test_c2_requires_human(policy_fn, versions):
    decision = evaluate(policy_fn, make_intent(consequence_class="C2"), versions)
    assert decision.effect == "REQUIRE_HUMAN"
    assert decision.governing_clauses == ["consequence_default:C2:REQUIRE_HUMAN"]


@pytest.mark.parametrize("cls", ["C3", "C4"])
def test_c3_c4_require_human_not_denied(policy_fn, versions, cls):
    # ADR: the compiled constitution is STRICTER than the WP-01 default
    # evaluator here — WP-01 DENIED C3+, the constitution requires a human.
    decision = evaluate(policy_fn, make_intent(consequence_class=cls), versions)
    assert decision.effect == "REQUIRE_HUMAN"
    assert decision.governing_clauses == [f"consequence_default:{cls}:REQUIRE_HUMAN"]


def test_c5_denied(policy_fn, versions):
    decision = evaluate(policy_fn, make_intent(consequence_class="C5"), versions)
    assert decision.effect == "DENY"
    assert decision.governing_clauses == ["consequence_default:C5:DENY"]


@pytest.mark.parametrize("cls", ALL_CLASSES)
def test_compiler_never_permits_c2_or_above(policy_fn, versions, cls):
    decision = evaluate(policy_fn, make_intent(consequence_class=cls), versions)
    if cls in ("C2", "C3", "C4", "C5"):
        assert decision.effect != "PERMIT"


def test_trace_records_all_four_steps(policy_fn, versions):
    decision = evaluate(policy_fn, make_intent(), versions)
    text = "\n".join(decision.decision_trace)
    assert "ucl:shutdown_state" in text
    assert "ucl:permanent_prohibitions" in text
    assert "ucl:participant_rights" in text
    assert "ucl:consequence_default" in text
    assert "ucl:final" in text


def test_decision_echoes_versions_and_fingerprint(policy_fn, versions):
    intent = make_intent()
    fingerprint = intent_fingerprint(intent, versions["policy_version"])
    decision = policy_fn(
        intent,
        intent_fingerprint=fingerprint,
        policy_version=versions["policy_version"],
        constitution_version=versions["constitution_version"],
        trace=[],
    )
    assert decision.intent_fingerprint == fingerprint
    assert decision.policy_version == versions["policy_version"]
    assert decision.constitution_version == versions["constitution_version"]


# ------------------------------------------------------ permanent prohibitions


def test_constitutional_amendment_always_denied(policy_fn, versions):
    intent = make_intent(
        action_type="constitutional_amendment",
        objective="Amend the constitution to grant more autonomy",
        consequence_class="C2",
    )
    decision = evaluate(policy_fn, intent, versions)
    assert decision.effect == "DENY"
    assert decision.governing_clauses == ["permanent_prohibitions:constitutional_amendment"]
    text = "\n".join(decision.decision_trace)
    assert "ucl:permanent_prohibitions matched=constitutional_amendment" in text


@pytest.mark.parametrize("matter", ["material_debt", "equity_issuance", "shutdown_override"])
def test_reserved_matter_exact_match_denied(policy_fn, versions, matter):
    intent = make_intent(payload={"reserved_matter": matter})
    decision = evaluate(policy_fn, intent, versions)
    assert decision.effect == "DENY"
    assert decision.governing_clauses == [f"permanent_prohibitions:{matter}"]


def test_objective_keyword_match_denied(policy_fn, versions):
    intent = make_intent(objective="Approve the merger or acquisition approval paperwork")
    decision = evaluate(policy_fn, intent, versions)
    assert decision.effect == "DENY"
    assert decision.governing_clauses == [
        "permanent_prohibitions:merger_or_acquisition_approval"
    ]


def test_action_type_paraphrase_keyword_match_denied(policy_fn, versions):
    intent = make_intent(action_type="Shutdown Override")  # normalized keyword match
    decision = evaluate(policy_fn, intent, versions)
    assert decision.effect == "DENY"
    assert decision.governing_clauses == ["permanent_prohibitions:shutdown_override"]


def test_benign_research_intent_matches_nothing(policy_fn, versions):
    decision = evaluate(policy_fn, make_intent(), versions)
    assert "ucl:permanent_prohibitions matched=none" in "\n".join(decision.decision_trace)


def test_non_string_reserved_matter_fails_closed(policy_fn, versions):
    intent = make_intent(payload={"reserved_matter": ["material_debt"]})
    with pytest.raises(UCLError, match="reserved_matter"):
        evaluate(policy_fn, intent, versions)


# --------------------------------------------------------- participant rights


def test_participant_harm_denied(policy_fn, versions):
    intent = make_intent(payload={"participant_harm": True})
    decision = evaluate(policy_fn, intent, versions)
    assert decision.effect == "DENY"
    assert decision.governing_clauses == ["participant_rights:safety:hard_refusal"]


def test_requires_unlawful_conduct_denied(policy_fn, versions):
    intent = make_intent(payload={"requires_unlawful_conduct": True})
    decision = evaluate(policy_fn, intent, versions)
    assert decision.effect == "DENY"
    assert decision.governing_clauses == [
        "participant_rights:lawful_treatment:hard_refusal"
    ]


def test_absent_flags_do_not_trigger(policy_fn, versions):
    intent = make_intent(payload={"participant_harm": False})
    decision = evaluate(policy_fn, intent, versions)
    assert decision.effect == "REQUIRE_HUMAN"  # plain C2 default; no right fired
    assert "ucl:participant_rights flags=none" in "\n".join(decision.decision_trace)


# ------------------------------------------------------------- safety states


def test_read_only_allows_internal_c1(make_model, make_policy_fn, versions):
    policy_fn = make_policy_fn(make_model(current_state="read_only"))
    decision = evaluate(policy_fn, make_intent(consequence_class="C1"), versions)
    assert decision.effect == "PERMIT"
    text = "\n".join(decision.decision_trace)
    assert "ucl:shutdown_state state=read_only" in text and "internal=allowed" in text


def test_read_only_denies_external_c2(make_model, make_policy_fn, versions):
    policy_fn = make_policy_fn(make_model(current_state="read_only"))
    decision = evaluate(policy_fn, make_intent(consequence_class="C2"), versions)
    assert decision.effect == "DENY"
    assert decision.governing_clauses == ["ucl:shutdown_state:read_only"]


@pytest.mark.parametrize(
    "state", ["constrained", "quarantined", "recovery", "archived", "shutdown"]
)
def test_non_normal_states_deny_external_effects(make_model, make_policy_fn, versions, state):
    policy_fn = make_policy_fn(make_model(current_state=state))
    decision = evaluate(policy_fn, make_intent(consequence_class="C3"), versions)
    assert decision.effect == "DENY"
    assert decision.governing_clauses == [f"ucl:shutdown_state:{state}"]


def test_manual_approval_only_forces_require_human(make_model, make_policy_fn, versions):
    policy_fn = make_policy_fn(make_model(current_state="manual_approval_only"))
    decision = evaluate(policy_fn, make_intent(consequence_class="C2"), versions)
    assert decision.effect == "REQUIRE_HUMAN"
    assert "ucl:shutdown_state:manual_approval_only" in decision.governing_clauses


def test_manual_approval_only_forces_human_even_for_c0(make_model, make_policy_fn, versions):
    policy_fn = make_policy_fn(make_model(current_state="manual_approval_only"))
    decision = evaluate(policy_fn, make_intent(consequence_class="C0"), versions)
    assert decision.effect == "REQUIRE_HUMAN"


def test_manual_approval_only_still_denies_c5(make_model, make_policy_fn, versions):
    policy_fn = make_policy_fn(make_model(current_state="manual_approval_only"))
    decision = evaluate(policy_fn, make_intent(consequence_class="C5"), versions)
    assert decision.effect == "DENY"


def test_shutdown_state_deny_short_circuits_prohibitions(make_model, make_policy_fn, versions):
    # In a deny-state, external effects are refused before any other clause.
    policy_fn = make_policy_fn(make_model(current_state="quarantined"))
    intent = make_intent(action_type="constitutional_amendment", consequence_class="C2")
    decision = evaluate(policy_fn, intent, versions)
    assert decision.effect == "DENY"
    assert decision.governing_clauses == ["ucl:shutdown_state:quarantined"]


# ---------------------------------------------------------------- determinism


def test_same_intent_compiled_twice_identical_trace(make_model, versions):
    intent = make_intent()
    policy_a = compile_policy_fn(make_model(), **versions)
    policy_b = compile_policy_fn(make_model(), **versions)
    decision_a = evaluate(policy_a, intent, versions, trace=["PROPOSE: fingerprint=x"])
    decision_b = evaluate(policy_b, intent, versions, trace=["PROPOSE: fingerprint=x"])
    assert decision_a.decision_trace == decision_b.decision_trace
    assert decision_a.governing_clauses == decision_b.governing_clauses
    assert decision_a.effect == decision_b.effect


def test_content_addressed_versions_are_stable(make_model, constitution_dir):
    from kernel.ucl.version import constitution_version_from_dir

    model_a, model_b = make_model(), make_model()
    assert policy_version(model_a) == policy_version(model_b)
    assert constitution_version_from_dir(constitution_dir) == constitution_version_from_dir(
        constitution_dir
    )
    assert policy_version(model_a).startswith("policy-")
    assert constitution_version_from_dir(constitution_dir).startswith("ucl-")


def test_policy_fn_rejects_foreign_versions(policy_fn, versions):
    intent = make_intent()
    with pytest.raises(UCLError, match="policy_version"):
        policy_fn(
            intent,
            intent_fingerprint="x",
            policy_version="policy-0000000000000000",
            constitution_version=versions["constitution_version"],
            trace=[],
        )
    with pytest.raises(UCLError, match="constitution_version"):
        policy_fn(
            intent,
            intent_fingerprint="x",
            policy_version=versions["policy_version"],
            constitution_version="ucl-0000000000000000",
            trace=[],
        )


def test_compile_requires_model_and_versions():
    with pytest.raises(UCLError):
        compile_policy_fn(object(), policy_version="p", constitution_version="c")
