"""Strict Draft 2020-12 validation of cortex contracts (repository convention).

Reuses the Kernel's strict JSON reader and refuses to run with a missing format
implementation, exactly like adapters.contract_validation. The cortex contracts
are deliberately *not* added to that module's shared-boundary allowlist.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from adapters.contract_validation import strict_json

CONTRACTS = Path(__file__).resolve().parents[1] / "contracts"
NAMES = ("cortex-problem-geometry", "cortex-intelligence-genome", "cortex-proof-artifact",
         "cortex-receipt", "cortex-routing-memory")


@lru_cache
def validator(name: str) -> Draft202012Validator:
    if name not in NAMES:
        raise ValueError(f"unregistered cortex contract {name!r}")
    schema = strict_json((CONTRACTS / f"{name}.schema.json").read_bytes())
    Draft202012Validator.check_schema(schema)
    checker = FormatChecker()
    if "date-time" not in checker.checkers:
        raise ValueError("required schema format implementation unavailable: date-time")
    return Draft202012Validator(schema, format_checker=checker)


def validate(payload, name: str):
    json.dumps(payload, allow_nan=False)
    errors = sorted(validator(name).iter_errors(payload), key=lambda e: str(list(e.path)))
    if errors:
        raise ValueError(f"{name}: {errors[0].message} at {list(errors[0].path)}")
    return payload
