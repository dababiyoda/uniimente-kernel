"""Directive ask S65.A1: every deliberation record passes the founder's two-pass protocol validator.

The validator is the founder-installed skill's own, vendored unchanged under tools/collaboration_protocol/
(PROVENANCE.json pins its bytes). A record is any tracked JSON file named deliberation* (any case), or any JSON
file whose top level carries both "pass_1" and "pass_2".

Records written before this check that it refuses are listed below with the reason. The list only shrinks: a new
record that fails, a listed record that now passes, and a listed record that is gone all fail this file. The
records themselves are not rewritten here; each belongs to its author.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "collaboration_protocol"
VALIDATOR = TOOL / "scripts" / "validate_deliberation.py"
SCHEMA = TOOL / "references" / "deliberation-schema.json"

# path -> why it is refused. Shrink-only.
KEPT_INVALID = {
    "docs/collaboration/deliberation-kimi-2026-08-22.json":
        "older record shape: it passed this validator off-repo on 2026-08-21 (verifier/README.md, run family "
        "collab-protocol-skill-v1); the skill's validator has since required decision_id, problem, "
        "founder_intent_refs, baseline, do_nothing_option, pass_1, pass_2 and more, which it lacks",
    "docs/collaboration/deliberation-foundry-09-oci-completion-20261026.json":
        "a different record shape (no title, problem, baseline, do_nothing_option, pass_1 or pass_2 fields)",
    "docs/collaboration/deliberation-revoked-device-authority-20261111.json":
        "alternatives lack description, advantages, disadvantages and revival_evidence; its unit was marked work in "
        "progress by its author (#96 comment 6799013915)",
}

MIN_RECORDS = 55  # measured on #196 f383fd26: 54 named deliberation*, plus docs/decisions/SR001-COMPAT-01.json


def _validator():
    spec = importlib.util.spec_from_file_location("validate_deliberation", VALIDATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", "node_modules", ".venv", "venv"}


def _json_files() -> list[str]:
    # A walk, not `git ls-files`: the mutation gates run this file in a copy without .git.
    out = []
    for path in ROOT.rglob("*.json"):
        rel = path.relative_to(ROOT)
        if SKIP_DIRS.intersection(rel.parts[:-1]):
            continue
        out.append(rel.as_posix())
    return out


def deliberation_records() -> list[str]:
    found = []
    for rel in _json_files():
        if rel.startswith("tools/collaboration_protocol/"):
            continue
        if Path(rel).name.lower().startswith("deliberation"):
            found.append(rel)
            continue
        try:
            text = (ROOT / rel).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if '"pass_1"' not in text or '"pass_2"' not in text:
            continue
        try:
            data = json.loads(text)
        except ValueError:
            continue
        if isinstance(data, dict) and "pass_1" in data and "pass_2" in data:
            found.append(rel)
    return sorted(found)


def errors_of(rel: str) -> list[str]:
    module = _validator()
    schema = module.load_json(SCHEMA)
    return module.validate_record(module.load_json(ROOT / rel), schema)


def test_the_vendored_validator_is_the_founders_bytes():
    pinned = json.loads((TOOL / "PROVENANCE.json").read_text())["files"]
    for rel, digest in pinned.items():
        assert hashlib.sha256((TOOL / rel).read_bytes()).hexdigest() == digest, rel


def test_every_record_is_found():
    records = deliberation_records()
    assert len(records) >= MIN_RECORDS, records
    assert "docs/decisions/SR001-COMPAT-01.json" in records


def test_every_deliberation_record_passes_the_two_pass_protocol():
    refused = {rel: errors_of(rel) for rel in deliberation_records()}
    refused = {rel: errs for rel, errs in refused.items() if errs}
    new = {rel: errs[:5] for rel, errs in refused.items() if rel not in KEPT_INVALID}
    assert not new, f"deliberation records the two-pass protocol refuses: {new}"


def test_the_kept_list_only_shrinks():
    records = set(deliberation_records())
    gone = sorted(set(KEPT_INVALID) - records)
    assert not gone, f"listed records no longer in the tree; remove them from KEPT_INVALID: {gone}"
    now_valid = sorted(rel for rel in KEPT_INVALID if not errors_of(rel))
    assert not now_valid, f"listed records now pass; remove them from KEPT_INVALID: {now_valid}"


# The validator, run on a record that passes, refuses each defect S65.A1 names. These keep the check honest if the
# vendored copy is ever swapped for a weaker one.
BASE = "docs/collaboration/deliberation-node-revoke-20261030.json"


def _base():
    module = _validator()
    return module, module.load_json(SCHEMA), module.load_json(ROOT / BASE)


def test_the_base_record_passes():
    module, schema, record = _base()
    assert module.validate_record(record, schema) == []


@pytest.mark.parametrize("defect", ["four_roles", "one_pass", "three_passes", "two_decisions", "no_do_nothing", "dissent_erased",
                                    "disposition_omitted"])
def test_each_named_defect_is_refused(defect):
    module, schema, record = _base()
    bad = copy.deepcopy(record)
    if defect == "four_roles":
        # Five entries, one of them a role the protocol does not require: only the missing-role check can see it.
        bad["roles"][-1] = dict(bad["roles"][-1], role="Product Owner")
    elif defect == "one_pass":
        del bad["pass_2"]
    elif defect == "two_decisions":
        bad["decision"] = "RETAIN and KILL"
    elif defect == "no_do_nothing":
        del bad["do_nothing_option"]
    elif defect == "three_passes":
        bad["pass_3"] = copy.deepcopy(bad["pass_2"])
    elif defect == "disposition_omitted":
        bad["pass_2"]["pass_1_disadvantage_dispositions"] = bad["pass_2"]["pass_1_disadvantage_dispositions"][1:]
    elif defect == "dissent_erased":
        # Declared dissent whose entries were dropped: the form of manufactured consensus the validator can see.
        # A record that never declares dissent and lists none passes; whether that is honest is for review.
        bad["dissent"]["entries"] = []
    assert module.validate_record(bad, schema), defect
