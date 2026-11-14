#!/usr/bin/env python3
"""Validate a two-pass founder-intent deliberation without external packages."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


DEFAULT_SCHEMA = (
    Path(__file__).resolve().parent.parent
    / "references"
    / "deliberation-schema.json"
)
REQUIRED_ROLES = {
    "founder-intent steward",
    "systems architect",
    "adversarial reviewer",
    "operator and maintainer",
    "evidence and welfare guardian",
}
DECISIONS = {
    "RETAIN",
    "REGRESS",
    "KILL",
    "DEFER",
    "EXPERIMENT",
    "NEEDS_FOUNDER_DECISION",
}
DISPOSITION_OUTCOMES = {
    "resolved",
    "accepted",
    "deferred",
    "prohibited",
    "experiment",
}
EVIDENCE_TIERS = {
    "readme_claim",
    "model_output",
    "deterministic_fixture",
    "unit_test",
    "sandbox_execution",
    "real_external_effect",
    "independently_verified_outcome",
    "commercial_result",
    "primary_source",
    "historical_artifact",
    "other",
}
SEVERITIES = {"low", "medium", "high", "critical"}
RESPONSE_TYPES = {
    "protective",
    "learning",
    "competitive",
    "modularity",
    "evidence",
    "governance",
    "do_not_proceed",
}
WEAKNESS_CATEGORIES = {
    "bureaucracy",
    "centralization",
    "fragility",
    "overfit",
    "expense",
    "comprehensibility",
    "reversibility",
    "gaming",
    "dependency",
    "other",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate one material deliberation with exactly two passes."
    )
    parser.add_argument("input", type=Path, help="Deliberation JSON file")
    parser.add_argument(
        "--schema",
        type=Path,
        default=DEFAULT_SCHEMA,
        help="Deliberation JSON Schema (default: bundled schema)",
    )
    parser.add_argument(
        "--json-report",
        action="store_true",
        help="Emit the validation report as JSON",
    )
    return parser.parse_args()


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"file not found: {path}") from exc
    except PermissionError as exc:
        raise ValueError(f"permission denied: {path}") from exc
    except UnicodeDecodeError as exc:
        raise ValueError(f"not valid UTF-8: {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"invalid JSON in {path} at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc


def nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def require_object(
    parent: dict[str, Any], field: str, path: str, errors: list[str]
) -> dict[str, Any] | None:
    value = parent.get(field)
    if not isinstance(value, dict):
        errors.append(f"{path}.{field}: must be an object")
        return None
    return value


def require_list(
    parent: dict[str, Any],
    field: str,
    path: str,
    errors: list[str],
    *,
    minimum: int = 0,
) -> list[Any] | None:
    value = parent.get(field)
    if not isinstance(value, list):
        errors.append(f"{path}.{field}: must be an array")
        return None
    if len(value) < minimum:
        errors.append(
            f"{path}.{field}: must contain at least {minimum} item(s)"
        )
    return value


def require_nonempty(
    parent: dict[str, Any], field: str, path: str, errors: list[str]
) -> None:
    if not nonempty(parent.get(field)):
        errors.append(f"{path}.{field}: must be a non-empty string")


def validate_nonempty_string_list(
    value: Any, path: str, errors: list[str], *, minimum: int = 0
) -> None:
    if not isinstance(value, list):
        errors.append(f"{path}: must be an array")
        return
    if len(value) < minimum:
        errors.append(f"{path}: must contain at least {minimum} item(s)")
    seen: set[str] = set()
    for index, item in enumerate(value):
        if not nonempty(item):
            errors.append(f"{path}[{index}]: must be a non-empty string")
            continue
        normalized = item.strip()
        if normalized in seen:
            errors.append(f"{path}[{index}]: duplicate value {normalized!r}")
        seen.add(normalized)


def validate_evidence(items: Any, path: str, errors: list[str]) -> None:
    if not isinstance(items, list):
        errors.append(f"{path}: must be an array")
        return
    for index, item in enumerate(items):
        item_path = f"{path}[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{item_path}: must be an object")
            continue
        for field in ("claim", "tier", "reference", "finding"):
            require_nonempty(item, field, item_path, errors)
        if item.get("tier") not in EVIDENCE_TIERS:
            errors.append(
                f"{item_path}.tier: must be one of "
                + ", ".join(sorted(EVIDENCE_TIERS))
            )


def validate_alternatives(record: dict[str, Any], errors: list[str]) -> None:
    alternatives = require_list(record, "alternatives", "$", errors, minimum=1)
    if alternatives is not None:
        for index, alternative in enumerate(alternatives):
            path = f"$.alternatives[{index}]"
            if not isinstance(alternative, dict):
                errors.append(f"{path}: must be an object")
                continue
            for field in ("name", "description", "revival_evidence"):
                require_nonempty(alternative, field, path, errors)
            validate_nonempty_string_list(
                alternative.get("advantages"), f"{path}.advantages", errors
            )
            validate_nonempty_string_list(
                alternative.get("disadvantages"), f"{path}.disadvantages", errors
            )

    do_nothing = require_object(record, "do_nothing_option", "$", errors)
    if do_nothing is not None:
        require_nonempty(do_nothing, "expected_outcome", "$.do_nothing_option", errors)
        validate_nonempty_string_list(
            do_nothing.get("advantages"),
            "$.do_nothing_option.advantages",
            errors,
        )
        validate_nonempty_string_list(
            do_nothing.get("disadvantages"),
            "$.do_nothing_option.disadvantages",
            errors,
        )


def validate_roles(record: dict[str, Any], errors: list[str]) -> None:
    roles = require_list(record, "roles", "$", errors, minimum=5)
    if roles is None:
        return
    seen: set[str] = set()
    for index, role_record in enumerate(roles):
        path = f"$.roles[{index}]"
        if not isinstance(role_record, dict):
            errors.append(f"{path}: must be an object")
            continue
        for field in ("role", "position"):
            require_nonempty(role_record, field, path, errors)
        role = role_record.get("role")
        if nonempty(role):
            normalized = role.strip().casefold()
            if normalized in seen:
                errors.append(f"{path}.role: duplicate role {role!r}")
            seen.add(normalized)
        validate_nonempty_string_list(
            role_record.get("material_concerns"),
            f"{path}.material_concerns",
            errors,
            minimum=1,
        )
        validate_nonempty_string_list(
            role_record.get("evidence_refs"), f"{path}.evidence_refs", errors
        )
        recommendation = role_record.get("recommendation")
        if recommendation not in DECISIONS:
            errors.append(
                f"{path}.recommendation: must be one of {', '.join(sorted(DECISIONS))}"
            )

    missing = sorted(REQUIRED_ROLES - seen)
    if missing:
        errors.append(
            "$.roles: missing required role(s): " + ", ".join(missing)
        )


def validate_passes(
    record: dict[str, Any], errors: list[str]
) -> tuple[set[str], set[str]]:
    numbered_passes = {
        key for key in record if re.fullmatch(r"pass_\d+", key)
    }
    if numbered_passes != {"pass_1", "pass_2"}:
        errors.append(
            "$: exactly pass_1 and pass_2 are allowed; found "
            + ", ".join(sorted(numbered_passes))
        )

    pass_1 = require_object(record, "pass_1", "$", errors)
    pass_2 = require_object(record, "pass_2", "$", errors)
    disadvantage_ids: set[str] = set()
    disposition_ids: set[str] = set()

    if pass_1 is not None:
        path = "$.pass_1"
        require_nonempty(pass_1, "intended_outcome", path, errors)
        advantages = require_list(pass_1, "advantages", path, errors, minimum=1)
        if advantages is not None:
            seen_advantages: set[str] = set()
            for index, item in enumerate(advantages):
                item_path = f"{path}.advantages[{index}]"
                if not isinstance(item, dict):
                    errors.append(f"{item_path}: must be an object")
                    continue
                for field in ("id", "statement", "amplified_value"):
                    require_nonempty(item, field, item_path, errors)
                item_id = item.get("id")
                if nonempty(item_id):
                    if item_id in seen_advantages:
                        errors.append(f"{item_path}.id: duplicate advantage ID")
                    seen_advantages.add(item_id)

        disadvantages = require_list(
            pass_1, "disadvantages", path, errors, minimum=1
        )
        if disadvantages is not None:
            for index, item in enumerate(disadvantages):
                item_path = f"{path}.disadvantages[{index}]"
                if not isinstance(item, dict):
                    errors.append(f"{item_path}: must be an object")
                    continue
                for field in (
                    "id",
                    "statement",
                    "severity",
                    "response_type",
                    "redesigned_response",
                ):
                    require_nonempty(item, field, item_path, errors)
                if item.get("severity") not in SEVERITIES:
                    errors.append(
                        f"{item_path}.severity: must be one of "
                        + ", ".join(sorted(SEVERITIES))
                    )
                if item.get("response_type") not in RESPONSE_TYPES:
                    errors.append(
                        f"{item_path}.response_type: must be one of "
                        + ", ".join(sorted(RESPONSE_TYPES))
                    )
                item_id = item.get("id")
                if nonempty(item_id):
                    if item_id in disadvantage_ids:
                        errors.append(f"{item_path}.id: duplicate disadvantage ID")
                    disadvantage_ids.add(item_id)

        comparisons = require_object(pass_1, "comparisons", path, errors)
        if comparisons is not None:
            for field in (
                "baseline",
                "do_nothing",
                "simplest_viable_alternative",
                "strongest_competing_architecture",
                "reversible_experiment",
            ):
                require_nonempty(
                    comparisons, field, f"{path}.comparisons", errors
                )

        rejected = require_list(pass_1, "rejected_alternatives", path, errors)
        if rejected is not None:
            for index, item in enumerate(rejected):
                item_path = f"{path}.rejected_alternatives[{index}]"
                if not isinstance(item, dict):
                    errors.append(f"{item_path}: must be an object")
                    continue
                for field in ("name", "rejection_reason", "revival_evidence"):
                    require_nonempty(item, field, item_path, errors)

    if pass_2 is not None:
        path = "$.pass_2"
        require_nonempty(pass_2, "attack_summary", path, errors)
        weaknesses = require_list(
            pass_2, "new_weaknesses", path, errors, minimum=1
        )
        if weaknesses is not None:
            seen_weaknesses: set[str] = set()
            for index, item in enumerate(weaknesses):
                item_path = f"{path}.new_weaknesses[{index}]"
                if not isinstance(item, dict):
                    errors.append(f"{item_path}: must be an object")
                    continue
                for field in (
                    "id",
                    "category",
                    "statement",
                    "strengthening_response",
                ):
                    require_nonempty(item, field, item_path, errors)
                if item.get("category") not in WEAKNESS_CATEGORIES:
                    errors.append(
                        f"{item_path}.category: must be one of "
                        + ", ".join(sorted(WEAKNESS_CATEGORIES))
                    )
                item_id = item.get("id")
                if nonempty(item_id):
                    if item_id in seen_weaknesses:
                        errors.append(f"{item_path}.id: duplicate weakness ID")
                    seen_weaknesses.add(item_id)

        dispositions = require_list(
            pass_2,
            "pass_1_disadvantage_dispositions",
            path,
            errors,
            minimum=1,
        )
        if dispositions is not None:
            for index, item in enumerate(dispositions):
                item_path = (
                    f"{path}.pass_1_disadvantage_dispositions[{index}]"
                )
                if not isinstance(item, dict):
                    errors.append(f"{item_path}: must be an object")
                    continue
                for field in (
                    "disadvantage_id",
                    "outcome",
                    "rationale",
                    "owner",
                    "review_trigger",
                ):
                    require_nonempty(item, field, item_path, errors)
                item_id = item.get("disadvantage_id")
                if nonempty(item_id):
                    if item_id in disposition_ids:
                        errors.append(
                            f"{item_path}.disadvantage_id: duplicate disposition"
                        )
                    disposition_ids.add(item_id)
                if item.get("outcome") not in DISPOSITION_OUTCOMES:
                    errors.append(
                        f"{item_path}.outcome: must be one of "
                        + ", ".join(sorted(DISPOSITION_OUTCOMES))
                    )

        require_nonempty(pass_2, "final_design", path, errors)
        residual = require_list(
            pass_2, "residual_risks", path, errors, minimum=1
        )
        if residual is not None:
            for index, item in enumerate(residual):
                item_path = f"{path}.residual_risks[{index}]"
                if not isinstance(item, dict):
                    errors.append(f"{item_path}: must be an object")
                    continue
                for field in ("risk", "mitigation", "owner", "review_trigger"):
                    require_nonempty(item, field, item_path, errors)
        recommendation = pass_2.get("recommendation")
        if recommendation not in DECISIONS:
            errors.append(
                f"{path}.recommendation: must be one of "
                + ", ".join(sorted(DECISIONS))
            )
        if recommendation != record.get("decision"):
            errors.append(
                f"{path}.recommendation: must match top-level decision"
            )

    missing_dispositions = sorted(disadvantage_ids - disposition_ids)
    unknown_dispositions = sorted(disposition_ids - disadvantage_ids)
    if missing_dispositions:
        errors.append(
            "$.pass_2.pass_1_disadvantage_dispositions: "
            "Pass-1 disadvantage(s) silently omitted: "
            + ", ".join(missing_dispositions)
        )
    if unknown_dispositions:
        errors.append(
            "$.pass_2.pass_1_disadvantage_dispositions: "
            "unknown Pass-1 disadvantage ID(s): "
            + ", ".join(unknown_dispositions)
        )
    return disadvantage_ids, disposition_ids


def validate_dissent(record: dict[str, Any], errors: list[str]) -> None:
    dissent = require_object(record, "dissent", "$", errors)
    if dissent is None:
        return
    path = "$.dissent"
    present = dissent.get("present")
    if not isinstance(present, bool):
        errors.append(f"{path}.present: must be a boolean")
    require_nonempty(dissent, "handling", path, errors)
    entries = require_list(dissent, "entries", path, errors)
    if entries is None:
        return
    if present is True and not entries:
        errors.append(f"{path}.entries: dissent is present but no dissent is preserved")
    if present is False and entries:
        errors.append(f"{path}: present is false but dissent entries exist")
    for index, item in enumerate(entries):
        item_path = f"{path}.entries[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{item_path}: must be an object")
            continue
        for field in (
            "role",
            "position",
            "rationale",
            "evidence_threshold",
            "owner",
            "review_trigger",
        ):
            require_nonempty(item, field, item_path, errors)


def validate_authority_and_rollback(
    record: dict[str, Any], errors: list[str]
) -> None:
    authority = require_object(record, "authority_impact", "$", errors)
    if authority is not None:
        path = "$.authority_impact"
        level = authority.get("level")
        if level not in {"lightweight", "standard", "constitutional"}:
            errors.append(
                f"{path}.level: must be lightweight, standard, or constitutional"
            )
        for field in ("changes_authority", "requires_authorized_human"):
            if not isinstance(authority.get(field), bool):
                errors.append(f"{path}.{field}: must be a boolean")
        approval = authority.get("approval_status")
        if approval not in {"not_required", "pending", "approved", "rejected"}:
            errors.append(f"{path}.approval_status: invalid approval state")
        requires_human = authority.get("requires_authorized_human")
        if (level == "constitutional" or authority.get("changes_authority") is True) and (
            requires_human is not True
        ):
            errors.append(
                f"{path}.requires_authorized_human: constitutional or authority-changing decisions require human approval"
            )
        decision = record.get("decision")
        approver = authority.get("approver")
        if requires_human is True:
            if decision == "NEEDS_FOUNDER_DECISION":
                if approval == "approved":
                    errors.append(
                        f"{path}: approved authority conflicts with NEEDS_FOUNDER_DECISION"
                    )
            elif approval != "approved":
                errors.append(
                    f"{path}.approval_status: consequential decision requires approved human authority"
                )
            if approval == "approved" and not nonempty(approver):
                errors.append(f"{path}.approver: approved authority requires an approver")
        elif approval != "not_required":
            errors.append(
                f"{path}.approval_status: use not_required when human approval is not required"
            )

    rollback = require_object(record, "rollback_plan", "$", errors)
    if rollback is not None:
        path = "$.rollback_plan"
        possible = rollback.get("possible")
        if not isinstance(possible, bool):
            errors.append(f"{path}.possible: must be a boolean")
        steps = rollback.get("steps")
        validate_nonempty_string_list(
            steps, f"{path}.steps", errors, minimum=1 if possible is True else 0
        )
        reason = rollback.get("reason_impossible")
        if possible is False and not nonempty(reason):
            errors.append(
                f"{path}.reason_impossible: required when rollback is impossible"
            )
        if possible is True and reason not in (None, ""):
            errors.append(
                f"{path}.reason_impossible: must be null or empty when rollback is possible"
            )


def validate_record(record: Any, schema: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["$: deliberation must be an object"]

    required = schema.get("required", [])
    properties = schema.get("properties", {})
    for field in required:
        if field not in record:
            errors.append(f"$.{field}: required field is missing")
    for field in sorted(set(record) - set(properties)):
        errors.append(f"$.{field}: unexpected field")

    for field in (
        "decision_id",
        "title",
        "problem",
        "baseline",
        "migration_plan",
        "decision_owner",
        "review_trigger",
    ):
        require_nonempty(record, field, "$", errors)

    validate_nonempty_string_list(
        record.get("founder_intent_refs"),
        "$.founder_intent_refs",
        errors,
        minimum=1,
    )
    validate_alternatives(record, errors)
    validate_roles(record, errors)
    validate_evidence(record.get("evidence"), "$.evidence", errors)
    validate_evidence(record.get("counterevidence"), "$.counterevidence", errors)
    validate_passes(record, errors)
    validate_dissent(record, errors)
    validate_authority_and_rollback(record, errors)

    validate_nonempty_string_list(
        record.get("kill_criteria"), "$.kill_criteria", errors, minimum=1
    )
    decision = record.get("decision")
    if decision not in DECISIONS:
        errors.append(
            "$.decision: must be one of " + ", ".join(sorted(DECISIONS))
        )
    return errors


def emit_report(report: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return
    if report["valid"]:
        print("VALID: deliberation contains five-role review and exactly two passes")
        return
    print(f"INVALID: {len(report['errors'])} error(s)")
    for error in report["errors"]:
        print(f"- {error}")


def main() -> int:
    args = parse_args()
    try:
        record = load_json(args.input)
        schema = load_json(args.schema)
        if not isinstance(schema, dict):
            raise ValueError("schema root must be an object")
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    errors = validate_record(record, schema)
    report = {
        "valid": not errors,
        "errors": errors,
        "input": str(args.input),
        "schema": str(args.schema),
    }
    emit_report(report, args.json_report)
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
