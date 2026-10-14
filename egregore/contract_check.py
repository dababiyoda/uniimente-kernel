"""Enforce the Goal Gravity contracts on persisted records.

The pinned boundary package (`adapters/contract_validation.py`) keeps its own
allowlist of cross-organ contracts; changing it is a shared-contract decision
outside this extension. Goal Gravity records are kernel-internal, so this
module enforces them with the same strictness (Draft 2020-12, every declared
format must have an implementation, NaN refused) without touching the
boundary allowlist. When the founder adopts these contracts for organs, the
allowlist is the place to add them.
"""
from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files

from jsonschema import Draft202012Validator, FormatChecker

GOAL_GRAVITY_CONTRACTS = ("goal-record", "goal-state", "experience-event", "capability-deficit")


class ContractViolation(ValueError):
    """A record does not satisfy its contract; it is not persisted."""


@lru_cache
def validator(name: str) -> Draft202012Validator:
    if name not in GOAL_GRAVITY_CONTRACTS:
        raise ContractViolation(f"unregistered goal-gravity contract {name!r}")
    schema = json.loads(files("contracts").joinpath(name + ".schema.json").read_bytes())
    Draft202012Validator.check_schema(schema)
    checker = FormatChecker()

    def formats(node):
        if isinstance(node, dict):
            if "format" in node:
                yield node["format"]
            for value in node.values():
                yield from formats(value)
        elif isinstance(node, list):
            for value in node:
                yield from formats(value)

    missing = set(formats(schema)) - checker.checkers.keys()
    if missing:
        raise ContractViolation("required schema format implementation unavailable: " + ", ".join(sorted(missing)))
    return Draft202012Validator(schema, format_checker=checker)


def validate_record(payload, name: str):
    json.dumps(payload, allow_nan=False)
    errors = sorted(validator(name).iter_errors(payload), key=lambda e: str(list(e.path)))
    if errors:
        raise ContractViolation(f"{name}: {errors[0].message}")
    return payload
