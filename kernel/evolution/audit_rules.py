"""Automated SpiderWeb audit rules (WP-06, SPEC-WP06 3.3).

``RuleBasedAuditor`` applies the five shipped deterministic rules to every
generated branch draft and returns ``(draft, findings)`` pairs whose findings
feed straight into the SpiderWebAudit contract (the contract's own validator
derives ``overall`` — a single failed finding kills the branch).

The rules are SYNTACTIC, not semantic (honest limitation, SPEC-WP06 7): they
audit the variant's self-declared config, which the BranchGenerator embeds in
the draft hypothesis as a canonical-JSON ``variant_config`` block (the frozen
WP-05 StrategyBranch shape is never edited). A draft whose config block is
missing or unparseable fails every declaration-dependent rule — ambiguity
fails closed (Hard Rule 4).

The pre-registered WP-06 cycle kill: ``no_commit_stream`` declares
``commit_strategy="commit_never`` (TransactionSemanticsRule fail,
regression_risk: dangling transactions) and ``reversibility=0.4``
(DeclaredReversibilityRule fail) — a real, mechanically generated audit kill.
"""
from __future__ import annotations

import json
from typing import Any, Protocol, runtime_checkable

from ..contracts.evolution import AuditFinding, StrategyBranch
from .generate import CONFIG_MARKER

# WP-01..WP-04 verified spine surface: a candidate variant must never name
# any of these methods in its ``touches`` declaration (sandbox-first, ADR-2).
FROZEN_SURFACE = frozenset({"append", "get", "iter", "verify_chain", "append_record"})

MIN_REVERSIBILITY = 0.8
COMMIT_REQUIRED = "commit_after"


def parse_variant_config(draft: StrategyBranch) -> dict[str, Any] | None:
    """Parse the embedded ``variant_config`` block; None if absent/malformed.

    The block is the canonical-JSON suffix introduced by CONFIG_MARKER in the
    draft hypothesis. Any parse failure returns None; the rules treat None as
    an unverifiable declaration and fail closed.
    """
    hypothesis = getattr(draft, "hypothesis", None)
    if not isinstance(hypothesis, str) or CONFIG_MARKER not in hypothesis:
        return None
    _, _, raw = hypothesis.rpartition(CONFIG_MARKER)
    try:
        config = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(config, dict) or not isinstance(config.get("variant_id"), str):
        return None
    return config


@runtime_checkable
class AuditRule(Protocol):
    """One deterministic audit rule: ``check(draft) -> AuditFinding``."""

    name: str

    def check(self, draft: StrategyBranch) -> AuditFinding: ...


class ReadPathOnlyRule:
    """The variant must declare ``modifies=[]`` (no production method edits)."""

    name = "read_path_only"

    def check(self, draft: StrategyBranch) -> AuditFinding:
        attack = "variant config must declare modifies=[] (sandbox incubation)"
        config = parse_variant_config(draft)
        if config is None:
            return AuditFinding(
                dimension="correctness_risk",
                attack=attack,
                result="fail",
                note="variant config missing or unparseable; fail closed",
            )
        modifies = config.get("modifies")
        if modifies != []:
            return AuditFinding(
                dimension="correctness_risk",
                attack=attack,
                result="fail",
                note=f"declared modifies={modifies!r}: candidates never edit "
                "production methods",
            )
        return AuditFinding(dimension="correctness_risk", attack=attack, result="pass")


class NoFrozenSurfaceRule:
    """The variant must not name any WP-01..WP-04 verified method in touches."""

    name = "no_frozen_surface"

    def check(self, draft: StrategyBranch) -> AuditFinding:
        attack = "variant must not touch the verified WP-01..WP-04 method surface"
        config = parse_variant_config(draft)
        if config is None:
            return AuditFinding(
                dimension="governance_risk",
                attack=attack,
                result="fail",
                note="variant config missing or unparseable; fail closed",
            )
        touches = config.get("touches")
        if not isinstance(touches, list):
            return AuditFinding(
                dimension="governance_risk",
                attack=attack,
                result="fail",
                note="touches declaration missing or not a list; fail closed",
            )
        hits = sorted(FROZEN_SURFACE.intersection(touches))
        if hits:
            return AuditFinding(
                dimension="governance_risk",
                attack=attack,
                result="fail",
                note=f"touches frozen verified methods {hits}",
            )
        return AuditFinding(dimension="governance_risk", attack=attack, result="pass")


class NoExternalDepsRule:
    """The variant must declare ``new_dependencies=[]`` (hermetic WP)."""

    name = "no_external_deps"

    def check(self, draft: StrategyBranch) -> AuditFinding:
        attack = "variant must declare new_dependencies=[] (hermetic build)"
        config = parse_variant_config(draft)
        if config is None:
            return AuditFinding(
                dimension="governance_risk",
                attack=attack,
                result="fail",
                note="variant config missing or unparseable; fail closed",
            )
        deps = config.get("new_dependencies")
        if deps != []:
            return AuditFinding(
                dimension="governance_risk",
                attack=attack,
                result="fail",
                note=f"declared new_dependencies={deps!r}",
            )
        return AuditFinding(dimension="governance_risk", attack=attack, result="pass")


class TransactionSemanticsRule:
    """The variant must keep commit semantics (``commit_strategy="commit_after"``).

    ``commit_never`` fails: a streaming read without the closing commit leaves
    a dangling transaction (regression_risk).
    """

    name = "transaction_semantics"

    def check(self, draft: StrategyBranch) -> AuditFinding:
        attack = "variant must keep commit semantics (commit_strategy='commit_after')"
        config = parse_variant_config(draft)
        if config is None:
            return AuditFinding(
                dimension="regression_risk",
                attack=attack,
                result="fail",
                note="variant config missing or unparseable; fail closed",
            )
        strategy = config.get("commit_strategy")
        if strategy != COMMIT_REQUIRED:
            return AuditFinding(
                dimension="regression_risk",
                attack=attack,
                result="fail",
                note=f"commit_strategy={strategy!r} leaves a dangling transaction",
            )
        return AuditFinding(dimension="regression_risk", attack=attack, result="pass")


class DeclaredReversibilityRule:
    """The pre-registered scores must declare reversibility >= 0.8."""

    name = "declared_reversibility"

    def check(self, draft: StrategyBranch) -> AuditFinding:
        attack = f"scores.reversibility must be >= {MIN_REVERSIBILITY}"
        reversibility = draft.scores.get("reversibility")
        if not isinstance(reversibility, (int, float)) or reversibility < MIN_REVERSIBILITY:
            return AuditFinding(
                dimension="reversibility",
                attack=attack,
                result="fail",
                note=f"declared reversibility={reversibility!r} < {MIN_REVERSIBILITY}",
            )
        return AuditFinding(dimension="reversibility", attack=attack, result="pass")


#: The five shipped deterministic rules, in audit order (SPEC-WP06 3.3).
SHIPPED_RULES: tuple[AuditRule, ...] = (
    ReadPathOnlyRule(),
    NoFrozenSurfaceRule(),
    NoExternalDepsRule(),
    TransactionSemanticsRule(),
    DeclaredReversibilityRule(),
)


class RuleBasedAuditor:
    """Applies every rule to every draft; mechanical audit content.

    ``audit(drafts) -> list[(draft, findings)]`` — the findings feed the
    SpiderWebAudit contract, whose own validator derives ``overall`` (any
    failed finding kills the branch).
    """

    def __init__(self, rules=SHIPPED_RULES):
        rules = tuple(rules)
        if not rules:
            raise ValueError("an auditor needs at least one rule (fail closed)")
        for rule in rules:
            if not isinstance(rule, AuditRule):
                raise ValueError(f"{rule!r} does not satisfy the AuditRule protocol")
        self._rules = rules

    @property
    def rules(self) -> tuple[AuditRule, ...]:
        return self._rules

    def audit(self, drafts) -> list[tuple[StrategyBranch, list[AuditFinding]]]:
        results: list[tuple[StrategyBranch, list[AuditFinding]]] = []
        for draft in drafts:
            if not isinstance(draft, StrategyBranch):
                raise ValueError("RuleBasedAuditor audits StrategyBranch drafts only")
            findings = [rule.check(draft) for rule in self._rules]
            results.append((draft, findings))
        return results
