"""Each safeguard of the intent-record contract, the section 8 horizon fields and the continuity guard must fail
its test when defeated (directive 2026-10-28 sections 8, 11 and 54).

The safeguards are contracts/intent-record.schema.json with the normalized docs/intent records
(tests/unit/test_intent_record_schema.py), greg.path's section 8 validation and greg/path.json's recorded entries
(tests/unit/test_horizon_section_8.py), and scripts/ci/check_intent_continuity.py with its pinned snapshot
(tests/unit/test_intent_continuity.py). A mutant is a change a contributor could make: thin the contract, drop or
relabel a record's field, paraphrase a recorded value, delete an intent or a horizon, or weaken a check. Each names
the test that must fail on it.

Every mutant runs in one scratch copy of the repository with ``python -B`` and PYTHONDONTWRITEBYTECODE=1, after every
``__pycache__`` in the copy is purged, and the copy is restored after each. The unmutated copy must pass all three
test files first. A mutant whose text no longer occurs exactly once, or whose new file already exists, is STALE.
"""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_TESTS = "tests/unit/test_intent_record_schema.py"
HORIZON_TESTS = "tests/unit/test_horizon_section_8.py"
CONTINUITY_TESTS = "tests/unit/test_intent_continuity.py"
TESTS = (SCHEMA_TESTS, HORIZON_TESTS, CONTINUITY_TESTS)
SCHEMA = "contracts/intent-record.schema.json"
PATH_JSON = "greg/path.json"
PATH_PY = "greg/path.py"
CHECK = "scripts/ci/check_intent_continuity.py"
SNAPSHOT = "docs/collaboration/INTENT-CONTINUITY-SNAPSHOT-2026-10-30.json"
FOUNDRY = "docs/intent/INTENT-2026-09-27-FOUNDRY-55.json"
FIRST_BODY = "docs/intent/INTENT-2026-09-22-FIRST-BODY.json"
FULL_MACHINE = "docs/intent/INTENT-20261001-FULL-MACHINE-COMPLETION.json"
METABOLISM = "docs/intent/INTENT-2026-09-26-REAL-PRODUCT-METABOLISM.json"
S11 = "not recorded in this record; directive 2026-10-28 section 11 lists this field"


def s(test: str) -> str:
    return f"{SCHEMA_TESTS}::{test}"


def h(test: str) -> str:
    return f"{HORIZON_TESTS}::{test}"


def c(test: str) -> str:
    return f"{CONTINUITY_TESTS}::{test}"


CONTRACT = s("test_the_contract_is_2020_12_and_requires_the_ledger_and_section_11_fields")
CLASSIFY = s("test_every_docs_intent_json_file_is_an_intent_record_or_listed_as_not_one")
UNIQUE = s("test_intent_ids_are_unique_and_name_their_file")
VALIDATES = s("test_every_intent_record_validates_against_the_contract")
COPIED = s("test_a_copied_field_repeats_the_records_own_words")
ALIASES = s("test_names_for_the_same_field_agree_wherever_both_are_present")
GAPS = s("test_unrecorded_fields_are_counted_and_never_hide_an_identity_field")
MISSING = s("test_a_record_missing_a_required_field_fails")
REFUSES = s("test_the_contract_refuses_a_thinned_or_relabelled_record")
CARRIES = h("test_every_horizon_not_currently_buildable_carries_section_8")
VERBATIM = h("test_every_copied_value_is_verbatim_in_its_source")
REPORT = h("test_the_section_8_gap_is_reported_on_greg_path")
H_MISSING = h("test_a_distant_horizon_missing_a_section_8_field_fails_validate")
H_REFUSES = h("test_validate_refuses_an_invented_or_empty_section_8_entry")
H_WHERE = h("test_feasibility_and_frontier_are_read_where_the_path_already_records_them")
HEAD = c("test_no_id_in_the_pinned_snapshot_is_missing_at_head")
PINNED = c("test_the_snapshot_is_pinned_and_covers_every_kind")
DELETED = c("test_deleting_an_intent_record_fails")
NOT_SUCCESSION = c("test_a_mention_outside_supersedes_is_not_succession")
PREFIX = c("test_a_prefix_of_an_id_is_not_succession")
MARKDOWN = c("test_deleting_a_markdown_intent_record_fails")
LEDGER = c("test_scrubbing_a_ledger_only_intent_fails")
HORIZON = c("test_deleting_a_horizon_fails_unless_a_horizon_supersedes_it")
BACKCAST = c("test_deleting_a_frontier_backcast_fails")

# (name, edits, test that must fail). An edit is ("replace", path, old, new), ("cut", path, start, end): remove from
# the unique ``start`` up to the next ``end``, ("create", path, text) or ("delete", path).
MUTANTS = [
    # -- the contract ---------------------------------------------------------------------------------------------
    ("superseded_by dropped from the contract's required fields",
     [("replace", SCHEMA, '    "supersedes",\n    "superseded_by",\n', '    "supersedes",\n')], MISSING),
    ("affected_systems (a section 11 addition) dropped from the required fields",
     [("replace", SCHEMA, '    "affected_systems",\n', "")], MISSING),
    ("the lifecycle widened with OUTDATED",
     [("replace", SCHEMA, '        "exploratory"\n      ]', '        "exploratory",\n        "outdated"\n      ]')],
     REFUSES),
    ("the statement allowed to be unrecorded",
     [("replace", SCHEMA, '"statement": {\n      "$ref": "#/$defs/text",',
       '"statement": {\n      "$ref": "#/$defs/text_or_unrecorded",')], REFUSES),
    ("an unrecorded marker allowed without a reason",
     [("replace", SCHEMA, '"unrecorded": {\n          "$ref": "#/$defs/text"\n        }',
       '"unrecorded": {\n          "type": "string"\n        }')], REFUSES),
    ("an unrecorded marker allowed to carry a value as well",
     [("replace", SCHEMA, '"additionalProperties": false,\n      "required": [\n        "unrecorded"',
       '"additionalProperties": true,\n      "required": [\n        "unrecorded"')], REFUSES),
    ("a superseded record no longer has to name its successor",
     [("cut", SCHEMA, '  "allOf": [\n', '  "$defs": {\n')], REFUSES),
    # -- the records ----------------------------------------------------------------------------------------------
    ("a record loses a required field (FOUNDRY-55 unresolved_questions)",
     [("replace", FOUNDRY, f'  "unresolved_questions": {{\n    "unrecorded": "{S11}"\n  }},\n', "")], VALIDATES),
    ("an unrecorded marker emptied to a blank reason",
     [("replace", FOUNDRY, f'  "affected_systems": {{\n    "unrecorded": "{S11}"\n  }}',
       '  "affected_systems": {\n    "unrecorded": " "\n  }')], VALIDATES),
    ("a copied state relabelled while the record's status stays active (FIRST-BODY)",
     [("replace", FIRST_BODY, '  "state": "active",\n  "binding_scope": {',
       '  "state": "implemented",\n  "binding_scope": {')], COPIED),
    ("a copied founder statement edited (FULL-MACHINE)",
     [("replace", FULL_MACHINE, '"statement": "UNIIMENTE \\u2014 FULL-MACHINE COMPLETION CORRECTION',
       '"statement": "UNIIMENTE \\u2014 FULL MACHINE COMPLETION CORRECTION')], COPIED),
    ("a recorded field silently turned into a gap past the ratchet (REAL-PRODUCT binding_scope)",
     [("replace", METABOLISM, '  "binding_scope": "Repository interpretation, prioritization, reversible '
       'implementation, testing and draft review. It creates no merge, deployment, credential, spending, publishing, '
       'customer-contact, or external-consequence authority.",', '  "binding_scope": {"unrecorded": "dropped"},')],
     GAPS),
    ("a map that is not an intent record added to docs/intent",
     [("create", "docs/intent/HORIZON-MAP.json", '{"horizons": []}\n')], CLASSIFY),
    ("a second record claims an existing intent id",
     [("create", "docs/intent/INTENT-DUPLICATE.json", '{"intent_id": "INTENT-20261014-ONE-MACHINE"}\n')], UNIQUE),
    # -- greg.path section 8 --------------------------------------------------------------------------------------
    ("validate checks section 8 only where a field is present",
     [("replace", PATH_PY, '            if field in horizon or horizon["feasibility"] != "CURRENTLY_BUILDABLE":',
       "            if field in horizon:")], H_MISSING),
    ("an unrecorded entry accepted without a reason",
     [("replace", PATH_PY, '        return None if _texts(value["unrecorded"]) else "unrecorded needs a reason"',
       "        return None")], H_REFUSES),
    ("a path-sourced value no longer checked against its source",
     [("replace", PATH_PY, "                if not any(item in text for text in texts):", "                if False:")],
     H_REFUSES),
    ("a recorded_as pointer allowed to name any field (an id satisfies a falsifier)",
     [("replace", PATH_PY, '                if not isinstance(ref, str) or ref.rsplit("/", 1)[-1] not in '
       'SECTION_8_POINTERS[field]:', "                if not isinstance(ref, str):")], H_REFUSES),
    ("an unrecorded marker accepted inside a list of recorded entries",
     [("replace", PATH_PY, '        if "unrecorded" in entry:\n            return "unrecorded stands alone, not in a list"\n',
       "")], H_REFUSES),
    ("the section 8 gap report dropped from greg path",
     [("replace", PATH_PY, '"section_8_unrecorded": section_8_gaps(data)}', '"section_8_unrecorded": {}}')], REPORT),
    # -- greg/path.json --------------------------------------------------------------------------------------------
    ("a horizon's recorded falsifier emptied (immune_function)",
     [("replace", PATH_JSON, '"value": "a replayed incident is missed, or legitimate novelty is quarantined",',
       '"value": "",')], CARRIES),
    ("a horizon's enabling interfaces deleted (mac_support)",
     [("replace", PATH_JSON, '      "enabling_interfaces": {\n        "value": [\n          "launchd plist",',
       '      "enabling_interfaces_dropped": {\n        "value": [\n          "launchd plist",')], H_WHERE),
    ("a directive interface paraphrased (computer_use)",
     [("replace", PATH_JSON, '"keyboard input",', '"keyboard and voice input",')], VERBATIM),
    ("a copied falsifier cut short (continuity)",
     [("replace", PATH_JSON, '"value": "a restore drill loses founder intent, ledger history or the ability to swap '
       'the model",', '"value": "a restore drill loses founder intent",')], VERBATIM),
    # -- the continuity guard --------------------------------------------------------------------------------------
    ("an intent record deleted in cleanup",
     [("delete", "docs/intent/INTENT-20260930-open-source-first.json")], HEAD),
    ("a horizon renamed away (voice)",
     [("replace", PATH_JSON, '"id": "voice",', '"id": "voice_and_speech",')], HEAD),
    ("an id dropped from the pinned snapshot",
     [("replace", SNAPSHOT, '   "INTENT-20260930-open-source-first",\n', "")], PINNED),
    ("the check stops reading horizons",
     [("replace", CHECK, '"horizons": lambda i: i in now["horizons"],', '"horizons": lambda i: True,')], HORIZON),
    ("the check stops reading frontier backcasts",
     [("replace", CHECK, '"frontier_backcasts": lambda i: i in now["frontier_backcasts"]}',
       '"frontier_backcasts": lambda i: True}')], BACKCAST),
    ("the check stops reading markdown records",
     [("replace", CHECK, '"intent_documents": lambda i: i in declared,', '"intent_documents": lambda i: True,')],
     MARKDOWN),
    ("the check stops reading the ledger",
     [("replace", CHECK, '"ledger_records": lambda i: i in declared or bool(_token(i).search(ledger)),',
       '"ledger_records": lambda i: True,')], LEDGER),
    ("succession read from any mention in a record",
     [("replace", CHECK, '        named = row.get("supersedes")', '        named = [json.dumps(row)]')], NOT_SUCCESSION),
    ("an id matched as a prefix of a longer one",
     [("replace", CHECK, '    return re.compile(rf"(?<![\\w/-]){re.escape(identifier)}(?![\\w-])")',
       "    return re.compile(re.escape(identifier))")], PREFIX),
    ("records held in a list file ignored",
     [("replace", CHECK, '        rows = data.get("intents") if isinstance(data, dict) and "intents" in data else [data]',
       "        rows = [data]")], HEAD),
    ("the CLI exits 0 on a missing id",
     [("replace", CHECK, "    return int(bool(gone))", "    return 0")], DELETED),
]


def _purge(repo: Path) -> None:
    for cache in repo.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)


def _run(repo: Path, *targets: str) -> subprocess.CompletedProcess:
    _purge(repo)
    return subprocess.run([sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", *targets],
                          cwd=repo, env={**os.environ, "PYTHONPATH": str(repo), "PYTHONDONTWRITEBYTECODE": "1"},
                          capture_output=True, text=True, timeout=900)


def _apply(repo: Path, edits) -> tuple[dict, list[Path]] | None:
    """Apply every edit; None (nothing changed) when any edit is stale."""
    originals, created = {}, []
    for kind, relative, *args in edits:
        path = repo / relative
        if kind == "create":
            if path.exists():
                return _restore(originals, created)
            created.append(path)
            path.write_text(args[0])
            continue
        if not path.exists():
            return _restore(originals, created)
        if path not in originals:
            originals[path] = path.read_text(encoding="utf-8")
        text = path.read_text(encoding="utf-8")
        if kind == "delete":
            path.unlink()
        elif kind == "replace":
            old, new = args
            if text.count(old) != 1:
                return _restore(originals, created)
            path.write_text(text.replace(old, new), encoding="utf-8")
        elif kind == "cut":
            start, end = args
            if text.count(start) != 1:
                return _restore(originals, created)
            at = text.index(start)
            stop = text.find(end, at + len(start))
            if stop < 0:
                return _restore(originals, created)
            path.write_text(text[:at] + text[stop:], encoding="utf-8")
        else:
            raise ValueError(kind)
    return originals, created


def _restore(originals: dict, created: list[Path]) -> None:
    for path, text in originals.items():
        path.write_text(text, encoding="utf-8")
    for path in created:
        path.unlink(missing_ok=True)
    return None


def main() -> int:
    invalid = 0
    with tempfile.TemporaryDirectory(prefix="intent-record-schema-mutants-") as temp:
        repo = Path(temp) / "repo"
        shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
        baseline = _run(repo, *TESTS)
        if baseline.returncode != 0:
            print("BASELINE_FAILS")
            print(baseline.stdout[-3000:])
            return 1
        print("BASELINE_PASSES", baseline.stdout.strip().splitlines()[-1], flush=True)
        for name, edits, test in MUTANTS:
            applied = _apply(repo, edits)
            if applied is None:
                print("STALE", name, flush=True)
                invalid += 1
                continue
            run = _run(repo, test)
            caught = (run.returncode == 1 and f"FAILED {test}" in run.stdout and "ERROR collecting" not in run.stdout)
            print("CAUGHT" if caught else "SURVIVED_OR_INVALID", name, flush=True)
            if not caught:
                print(run.stdout[-2000:])
            invalid += not caught
            _restore(*applied)
    print(f"{len(MUTANTS) - invalid}/{len(MUTANTS)} caught")
    return int(bool(invalid))


if __name__ == "__main__":
    raise SystemExit(main())
