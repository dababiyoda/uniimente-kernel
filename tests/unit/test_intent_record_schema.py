"""Directive 2026-10-28 section 11, as a contract: every founder intent record carries the ledger's fields.

``contracts/intent-record.schema.json`` holds the fifteen fields of the Founder Intent Ledger's Required Intent
Record and the five that section 11 adds (intended observable effect, affected systems, authority level,
consequence class, unresolved questions), with the six lifecycle states the ledger allows. The records under
docs/intent were normalized additively on 2026-10-30: a field a record already states under another name was
copied from that name, and a field its source does not supply carries ``{"unrecorded": "<reason>"}``, which these
tests count and never treat as recorded. No recorded statement, state or meaning was changed.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import re

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "contracts" / "intent-record.schema.json"
INTENT_DIR = ROOT / "docs" / "intent"
LEDGER = ROOT / "docs" / "FOUNDER_INTENT_LEDGER.md"
DIRECTIVE = INTENT_DIR / "sources" / "OPUS-MAXIMUS-MASTER-BUILD-DIRECTIVE-2026-10-28-source.md"
NORMALIZATION = "normalization_2026_10_30"

LEDGER_FIELDS = ("intent_id", "statement", "source_refs", "owner", "state", "binding_scope",
                 "constitutional_constraints", "success_evidence", "failure_evidence", "dependencies", "conflicts",
                 "next_review_trigger", "supersedes", "superseded_by", "implementation_refs")
SECTION_11_FIELDS = ("intended_effect", "affected_systems", "authority_level", "consequence_class",
                     "unresolved_questions")
LIFECYCLE = ("active", "implemented", "deferred", "superseded", "prohibited", "exploratory")
# Section 11's list, in the directive's words, and the field that carries each item.
SECTION_11 = {"unique ID": ("intent_id",), "faithful statement": ("statement",), "source lineage": ("source_refs",),
              "intended observable effect": ("intended_effect",), "affected systems": ("affected_systems",),
              "lifecycle state": ("state",), "authority level": ("authority_level",),
              "consequence class": ("consequence_class",), "implementation references": ("implementation_refs",),
              "evidence": ("success_evidence", "failure_evidence"), "conflicts": ("conflicts",),
              "owner": ("owner",), "review trigger": ("next_review_trigger",),
              "unresolved questions": ("unresolved_questions",)}
# What a record identifies itself by can never be unrecorded.
IDENTITY = ("intent_id", "statement", "source_refs", "owner", "state")
# Names the records already use for the same field; wherever two are present they must agree.
ALIASES = {"state": ("status", "lifecycle_state"),
           "intended_effect": ("intended_outcome", "intended_observable_effect")}
# docs/intent/*.json files that hold no intent record (a manifest, a map), by name, with what they are.
NOT_INTENT_RECORDS: dict[str, str] = {}
# The unrecorded markers at normalization (2026-10-30). A later record may close a gap; it may not add one silently.
MAX_UNRECORDED = 129


def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def validator() -> jsonschema.Draft202012Validator:
    document = schema()
    jsonschema.Draft202012Validator.check_schema(document)
    return jsonschema.Draft202012Validator(document)


def records() -> list[tuple[str, dict]]:
    """Every intent record under docs/intent, as (file name, record); a file may hold a list under ``intents``."""
    out = []
    for path in sorted(INTENT_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if path.name in NOT_INTENT_RECORDS:
            continue
        out += [(path.name, r) for r in (data["intents"] if "intents" in data else [data])]
    return out


def unrecorded(value) -> bool:
    return isinstance(value, dict) and set(value) == {"unrecorded"}


def gap_report() -> dict:
    """Field -> the intent ids whose record leaves it unrecorded."""
    report: dict[str, list[str]] = {}
    for _, record in records():
        for field in LEDGER_FIELDS + SECTION_11_FIELDS:
            if unrecorded(record.get(field)):
                report.setdefault(field, []).append(record["intent_id"])
    return report


def test_the_contract_is_2020_12_and_requires_the_ledger_and_section_11_fields():
    document = schema()
    jsonschema.Draft202012Validator.check_schema(document)
    assert document["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert document["$id"].endswith("/contracts/intent-record.schema.json")
    assert list(document["required"]) == list(LEDGER_FIELDS + SECTION_11_FIELDS)
    assert document["properties"]["state"] == {"$ref": "#/$defs/lifecycle"}
    assert document["$defs"]["lifecycle"]["enum"] == list(LIFECYCLE)
    # The ledger's Required Intent Record, read from the ledger itself (never edited here).
    text = LEDGER.read_text(encoding="utf-8")
    block = text[text.index("## Required Intent Record"):].split("\n## ", 1)[0]
    assert tuple(re.findall(r"^\d+\. `([a-z_]+)`$", block, re.M)) == LEDGER_FIELDS
    states = re.findall(r"^- `([a-z]+)`: ", text, re.M)
    assert tuple(states) == LIFECYCLE
    # Directive section 11's list, read from the verbatim source.
    lines = DIRECTIVE.read_text(encoding="utf-8").splitlines()
    start = lines.index("11. FOUNDER INTENT LEDGER")
    section = lines[start:lines.index("12. FOUNDER CORRECTION SEMANTICS", start)]
    items = [line[2:].rstrip(";.") for line in section if line.startswith("* ")]
    assert items == list(SECTION_11)
    for fields in SECTION_11.values():
        assert set(fields) <= set(document["required"])


def test_every_docs_intent_json_file_is_an_intent_record_or_listed_as_not_one():
    for path in sorted(INTENT_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        assert "intent_id" in data or "intents" in data or path.name in NOT_INTENT_RECORDS, path.name


def test_intent_ids_are_unique_and_name_their_file():
    ids = [r["intent_id"] for _, r in records()]
    assert len(ids) == len(set(ids)) and len(ids) >= 26
    for name, record in records():
        assert name == f"{record['intent_id']}.json", (name, record["intent_id"])


def test_every_intent_record_validates_against_the_contract():
    check = validator()
    failures = {r["intent_id"]: [f"{'/'.join(map(str, e.absolute_path))}: {e.message[:120]}"
                                 for e in check.iter_errors(r)] for _, r in records()}
    assert {k: v for k, v in failures.items() if v} == {}


def test_a_copied_field_repeats_the_records_own_words():
    copies = 0
    for _, record in records():
        for field, alias in (record.get(NORMALIZATION) or {}).get("copied", {}).items():
            assert alias in record and field in record, (record["intent_id"], field, alias)
            original = record[alias]
            expected = [original] if isinstance(record[field], list) and isinstance(original, str) else original
            assert record[field] == expected, (record["intent_id"], field)
            copies += 1
    assert copies > 0


def test_names_for_the_same_field_agree_wherever_both_are_present():
    for _, record in records():
        for field, aliases in ALIASES.items():
            for alias in aliases:
                if alias in record and field in record:
                    assert record[alias] == record[field], (record["intent_id"], field, alias)


def test_unrecorded_fields_are_counted_and_never_hide_an_identity_field():
    report = gap_report()
    total = sum(len(ids) for ids in report.values())
    assert 0 < total <= MAX_UNRECORDED, report
    assert not set(report) & set(IDENTITY), report
    for _, record in records():
        for field in LEDGER_FIELDS + SECTION_11_FIELDS:
            if unrecorded(record[field]):
                assert record[field]["unrecorded"].strip(), (record["intent_id"], field)


def _record(intent_id: str = "INTENT-2026-09-25-EGREGORE-ECOLOGY") -> dict:
    return copy.deepcopy(next(r for _, r in records() if r["intent_id"] == intent_id))


@pytest.mark.parametrize("field", LEDGER_FIELDS + SECTION_11_FIELDS)
def test_a_record_missing_a_required_field_fails(field):
    check = validator()
    record = _record()
    assert check.is_valid(record)
    record.pop(field)
    assert not check.is_valid(record), field


@pytest.mark.parametrize("change", [
    pytest.param(lambda r: r.update(state="outdated"), id="state outside the ledger's six"),
    pytest.param(lambda r: r.update(statement={"unrecorded": "lost"}), id="statement unrecorded"),
    pytest.param(lambda r: r.update(source_refs=[]), id="no source lineage"),
    pytest.param(lambda r: r.update(state={"unrecorded": "unknown"}), id="state unrecorded"),
    pytest.param(lambda r: r.update(owner={"unrecorded": "unknown"}), id="owner unrecorded"),
    pytest.param(lambda r: r.update(binding_scope={"unrecorded": ""}), id="unrecorded without a reason"),
    pytest.param(lambda r: r.update(binding_scope={"unrecorded": "x", "value": "y"}), id="marker with a value"),
    pytest.param(lambda r: r.update(binding_scope=""), id="empty text"),
    pytest.param(lambda r: r.update(state="superseded"), id="superseded with no successor"),
    pytest.param(lambda r: r.update(state="superseded", superseded_by={"unrecorded": "x"}),
                 id="superseded with an unrecorded successor"),
    pytest.param(lambda r: r.update(intent_id="GOAL-1"), id="id outside the INTENT- namespace"),
    pytest.param(lambda r: r.update(status="outdated"), id="an alias state outside the six"),
])
def test_the_contract_refuses_a_thinned_or_relabelled_record(change):
    check = validator()
    record = _record()
    change(record)
    assert not check.is_valid(record)


def test_a_superseded_record_names_its_successor():
    check = validator()
    record = _record()
    record.update(state="superseded", status="superseded", superseded_by=["INTENT-20261030-BUILD-BEFORE-DEVICE-RUN"])
    assert check.is_valid(record)
