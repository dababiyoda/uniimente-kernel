"""The one-time additive normalization of docs/intent/*.json against contracts/intent-record.schema.json (2026-10-30).

Run once, from the repository root, at the commit before it landed: ``python -B <this file>``. For every intent
record missing a required field it appends, after the record's last field and without touching a byte before it:

* the field, copied verbatim from the name this same record already states it under (``COPIES``), or
* ``{"unrecorded": "<reason>"}`` when the record does not state it;
* ``normalization_2026_10_30``: the contract, the rule and which fields were copied from which.

It refuses a record it has already normalized, and checks after each write that deleting the inserted text gives
back the original file byte for byte and that every original field parses to the same value. It invents nothing:
a value is either the record's own words or the marker. Kept as evidence of how the records were changed.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path.cwd()
CONTRACT = "contracts/intent-record.schema.json"
BLOCK = "normalization_2026_10_30"
LEDGER = ("intent_id", "statement", "source_refs", "owner", "state", "binding_scope", "constitutional_constraints",
          "success_evidence", "failure_evidence", "dependencies", "conflicts", "next_review_trigger", "supersedes",
          "superseded_by", "implementation_refs")
SECTION_11 = ("intended_effect", "affected_systems", "authority_level", "consequence_class", "unresolved_questions")
# Canonical field -> names under which a record already states the same thing (first present wins). A list
# canonical copied from a single text becomes a one-item list of that text.
COPIES = {"state": ("status", "lifecycle_state"),
          "intended_effect": ("intended_outcome", "intended_observable_effect"),
          "statement": ("exact_source_excerpt",),
          "source_refs": ("source_location",),
          "next_review_trigger": ("review_trigger",),
          "constitutional_constraints": ("constraints",)}
LIST_FIELDS = {"source_refs"}
RULE = ("Additive: the fields named in copied repeat this record's own words under their canonical names, and a "
        "field this record's source does not supply carries an unrecorded marker; no recorded statement, state or "
        "meaning was changed.")


def reason(field: str, record: dict) -> str:
    base = ("not recorded in this record; the Founder Intent Ledger's Required Intent Record lists this field"
            if field in LEDGER else "not recorded in this record; directive 2026-10-28 section 11 lists this field")
    notes = []
    if field == "authority_level":
        notes += [f"{name} is kept as written and is not an authority level"
                  for name in ("authority_delta", "authority_scope") if name in record]
    if field == "binding_scope" and "authority_scope" in record:
        notes.append("authority_scope is kept as written and is not relabelled as binding scope")
    if field in ("success_evidence", "failure_evidence") and "evidence_refs" in record:
        notes.append("evidence_refs is kept as written and does not separate success from failure evidence")
    if field == "failure_evidence" and "failure_condition" in record:
        notes.append("failure_condition states a falsifier, not observed failure evidence")
    return "; ".join([base] + notes)


def additions(record: dict) -> tuple[dict, dict]:
    added, copied = {}, {}
    for field in LEDGER + SECTION_11:
        if field in record:
            continue
        alias = next((a for a in COPIES.get(field, ()) if a in record), None)
        if alias is not None:
            value = record[alias]
            added[field] = [value] if field in LIST_FIELDS and isinstance(value, str) else value
            copied[field] = alias
        else:
            added[field] = {"unrecorded": reason(field, record)}
    added[BLOCK] = {"contract": CONTRACT, "rule": RULE, "copied": copied}
    return added, copied


def style(text: str) -> tuple[int, bool]:
    """The file's indent unit and whether it escapes non-ASCII."""
    for line in text.splitlines()[1:]:
        if line.strip():
            unit = len(line) - len(line.lstrip(" "))
            break
    return unit, not any(ord(c) > 127 for c in text)


def insert(text: str, added: dict, nested: bool) -> tuple[str, str]:
    unit, ascii_only = style(text)
    body = text.rstrip()
    close = body.rfind("}", 0, body.rfind("]")) if nested else len(body) - 1
    end = len(body[:close].rstrip())
    indent = " " * (unit * (3 if nested else 1))
    lines = []
    for key, value in added.items():
        rendered = json.dumps(value, indent=unit, ensure_ascii=ascii_only).replace("\n", "\n" + indent)
        lines.append(f"{indent}{json.dumps(key)}: {rendered}")
    chunk = ",\n" + ",\n".join(lines)
    return text[:end] + chunk + text[end:], chunk


def main() -> int:
    changed = 0
    for path in sorted((ROOT / "docs/intent").glob("*.json")):
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
        nested = "intents" in data
        if nested and len(data["intents"]) != 1:
            raise SystemExit(f"{path.name}: one record per list file is all this script handles")
        record = data["intents"][0] if nested else data
        if BLOCK in record:
            raise SystemExit(f"{path.name}: already normalized")
        added, _ = additions(record)
        new, chunk = insert(text, added, nested)
        assert new.replace(chunk, "", 1) == text, path.name
        after = json.loads(new)
        after_record = after["intents"][0] if nested else after
        assert {k: after_record[k] for k in record} == record, path.name
        assert list(after_record)[:len(record)] == list(record), path.name
        path.write_text(new, encoding="utf-8")
        changed += 1
        print(path.name, "copied", sorted(added[BLOCK]["copied"].items()),
              "unrecorded", sorted(k for k, v in added.items() if isinstance(v, dict) and "unrecorded" in v))
    print(f"{changed} records normalized")
    return 0


if __name__ == "__main__":
    sys.exit(main())
