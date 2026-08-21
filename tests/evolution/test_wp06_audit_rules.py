"""WP-06 audit-rule suite (SPEC-WP06 4.3).

Every shipped rule's pass AND fail path; the pre-registered no_commit_stream
kill carries exactly the expected dimensions (TransactionSemanticsRule +
DeclaredReversibilityRule); RuleBasedAuditor output feeds SpiderWebAudit
contracts without validator errors; a draft without a parseable
variant_config fails closed on every declaration-dependent rule.
"""
from __future__ import annotations

import pytest

from kernel.contracts.evolution import SpiderWebAudit, StrategyBranch
from kernel.evolution import (
    AuditRule,
    DeclaredReversibilityRule,
    NoExternalDepsRule,
    NoFrozenSurfaceRule,
    ReadPathOnlyRule,
    RuleBasedAuditor,
    SHIPPED_RULES,
    TransactionSemanticsRule,
)
from kernel.evolution.audit_rules import parse_variant_config
from kernel.evolution.generate import BranchGenerator

from scripts.run_fast_cycle import DECLARATIONS, SCORING, make_generator, make_space


def drafts_by_variant():
    drafts = make_generator().generate(make_space())
    return {parse_variant_config(d)["variant_id"]: d for d in drafts}


def _custom_draft(declaration_overrides, score_overrides=None) -> StrategyBranch:
    scoring = {"v": dict(SCORING["stream"])}
    if score_overrides:
        scoring["v"].update(score_overrides)
    declaration = dict(DECLARATIONS["stream"])
    declaration.update(declaration_overrides)
    generator = BranchGenerator(scoring, declarations={"v": declaration})
    space_space = make_space().model_copy(
        update={"axes": {"fetch_strategy": ["fetchall", "v"]}}
    )
    (draft,) = generator.generate(space_space)
    return draft


def test_shipped_rules_satisfy_the_audit_rule_protocol():
    assert len(SHIPPED_RULES) == 5
    for rule in SHIPPED_RULES:
        assert isinstance(rule, AuditRule)
        assert isinstance(rule.name, str) and rule.name


def test_all_five_rules_pass_on_a_clean_variant():
    draft = drafts_by_variant()["stream"]
    for rule in SHIPPED_RULES:
        finding = rule.check(draft)
        assert finding.result == "pass", rule.name
        assert finding.dimension


def test_read_path_only_rule_fail_path():
    draft = _custom_draft({"modifies": ["verify_chain"]})
    finding = ReadPathOnlyRule().check(draft)
    assert finding.result == "fail"
    assert finding.dimension == "correctness_risk"


def test_no_frozen_surface_rule_fail_path():
    draft = _custom_draft({"touches": ["verify_chain"]})
    finding = NoFrozenSurfaceRule().check(draft)
    assert finding.result == "fail"
    assert finding.dimension == "governance_risk"
    assert "verify_chain" in finding.note
    # Harness-local touches are fine.
    ok = _custom_draft({"touches": ["scripts/wp06_bench.py::verify_stream"]})
    assert NoFrozenSurfaceRule().check(ok).result == "pass"


def test_no_external_deps_rule_fail_path():
    draft = _custom_draft({"new_dependencies": ["numpy"]})
    finding = NoExternalDepsRule().check(draft)
    assert finding.result == "fail"
    assert finding.dimension == "governance_risk"


def test_transaction_semantics_rule_fail_path():
    draft = _custom_draft({"commit_strategy": "commit_never"})
    finding = TransactionSemanticsRule().check(draft)
    assert finding.result == "fail"
    assert finding.dimension == "regression_risk"
    assert "commit_never" in finding.note


def test_declared_reversibility_rule_fail_path():
    draft = _custom_draft({}, {"reversibility": 0.4})
    finding = DeclaredReversibilityRule().check(draft)
    assert finding.result == "fail"
    assert finding.dimension == "reversibility"
    # The boundary itself passes.
    edge = _custom_draft({}, {"reversibility": 0.8})
    assert DeclaredReversibilityRule().check(edge).result == "pass"


def test_no_commit_stream_killed_with_expected_dimensions():
    draft = drafts_by_variant()["no_commit_stream"]
    auditor = RuleBasedAuditor()
    [(audited, findings)] = [
        (d, f) for d, f in auditor.audit([draft]) if d.id == draft.id
    ]
    failed = {f.dimension for f in findings if f.result == "fail"}
    passed = {f.dimension for f in findings if f.result == "pass"}
    assert failed == {"regression_risk", "reversibility"}
    assert passed == {"correctness_risk", "governance_risk"}
    assert len(findings) == 5


def test_auditor_output_feeds_spiderweb_audit_contracts_cleanly():
    drafts = make_generator().generate(make_space())
    auditor = RuleBasedAuditor()
    for draft, findings in auditor.audit(drafts):
        overall = "fail" if any(f.result == "fail" for f in findings) else "pass"
        audit = SpiderWebAudit(
            branch_id=draft.id,
            auditor_id="rule-based-auditor",
            findings=findings,
            overall=overall,
        )
        variant = parse_variant_config(draft)["variant_id"]
        expected = "fail" if variant == "no_commit_stream" else "pass"
        assert audit.overall == expected  # the contract validator agrees


def test_unparseable_config_fails_closed_on_declaration_rules():
    draft = StrategyBranch(
        title="hand-authored",
        hypothesis="no config block here",
        metric_id="m",
        expected_delta=-0.1,
        scores={"expected_value": 0.5, "risk": 0.1, "reversibility": 1.0, "cost": 0.2},
    )
    assert parse_variant_config(draft) is None
    for rule in (
        ReadPathOnlyRule(),
        NoFrozenSurfaceRule(),
        NoExternalDepsRule(),
        TransactionSemanticsRule(),
    ):
        finding = rule.check(draft)
        assert finding.result == "fail", rule.name
        assert "fail closed" in finding.note
    # The scores-based rule still reads the declared scores honestly.
    assert DeclaredReversibilityRule().check(draft).result == "pass"


def test_auditor_requires_rules_and_branch_drafts():
    with pytest.raises(ValueError, match="at least one rule"):
        RuleBasedAuditor(())
    with pytest.raises(ValueError, match="AuditRule protocol"):
        RuleBasedAuditor((object(),))
    with pytest.raises(ValueError, match="StrategyBranch"):
        RuleBasedAuditor().audit([{"not": "a branch"}])
