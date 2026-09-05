"""Validate record-only source evidence. Validation confers no authority."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from omnimorph.organization_compiler import content_digest

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "contracts/manual-founder-direction.schema.json"


def validate_direction_record(record: dict) -> dict:
    with SCHEMA_PATH.open(encoding="utf-8") as handle:
        schema = json.load(handle)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(record)
    if record["digest"] != content_digest(record, excluding=("digest",)):
        raise ValueError("manual source record content digest mismatch")
    return copy.deepcopy(record)
