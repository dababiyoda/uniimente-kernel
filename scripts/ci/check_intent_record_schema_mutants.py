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
GRAVITY = "docs/intent/INTENT-20261013-GOAL-GRAVITY.json"
LEDGER_FILE = "docs/FOUNDER_INTENT_LEDGER.md"
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
LIFECYCLE_AGREE = s("test_the_contract_holds_the_older_lifecycle_names_to_state")
DOC_COPY = s("test_a_field_copied_from_the_companion_document_repeats_its_row")
DOC_GAP = s("test_no_field_is_marked_unrecorded_where_the_records_own_document_states_it")
CARRIES = h("test_every_horizon_not_currently_buildable_carries_section_8")
VERBATIM = h("test_every_copied_value_is_verbatim_in_its_source")
REPORT = h("test_the_section_8_gap_is_reported_on_greg_path")
H_MISSING = h("test_a_distant_horizon_missing_a_section_8_field_fails_validate")
H_REFUSES = h("test_validate_refuses_an_invented_or_empty_section_8_entry")
H_WHERE = h("test_feasibility_and_frontier_are_read_where_the_path_already_records_them")
H_EMPTY = h("test_an_empty_pointer_list_records_nothing")
H_BORROWED = h("test_validate_refuses_text_that_belongs_elsewhere_or_is_cut")
HEAD = c("test_no_id_in_the_pinned_snapshot_is_missing_at_head")
PINNED = c("test_the_snapshot_is_pinned_and_covers_every_kind")
DELETED = c("test_deleting_an_intent_record_fails")
NOT_SUCCESSION = c("test_a_mention_outside_supersedes_is_not_succession")
PREFIX = c("test_a_prefix_of_an_id_is_not_succession")
MARKDOWN = c("test_deleting_a_markdown_intent_record_fails")
LEDGER = c("test_scrubbing_a_ledger_only_intent_fails")
HORIZON = c("test_deleting_a_horizon_fails_unless_a_horizon_supersedes_it")
BACKCAST = c("test_deleting_a_frontier_backcast_fails")
MENTION = c("test_an_intent_the_ledger_only_mentions_is_pinned")
TREE = c("test_head_ids_are_read_from_the_tree_alone")
LONGER = c("test_a_longer_id_in_the_ledger_does_not_keep_a_shorter_one")
PROSE = c("test_prose_that_mentions_an_id_is_not_succession")
KINDED = c("test_an_intent_record_cannot_supersede_a_horizon")
REPIN = c("test_a_repin_refuses_a_deletion_and_only_adds")
WRITE = c("test_write_snapshot_keeps_the_pinned_ids_and_refuses_a_deletion")
LAWFUL = c("test_every_lawful_path_passes_the_check_and_the_cli")

# (name, edits, test that must fail). An edit is ("replace", path, old, new), ("cut", path, start, end): remove from
# the unique ``start`` up to the next ``end``, ("create", path, text) or ("delete", path).
MUTANTS = [
    # -- the contract ---------------------------------------------------------------------------------------------
    ("superseded_by dropped from the contract's required fields",
     [("replace", SCHEMA, '    "supersedes",\n    "superseded_by",\n', '    "supersedes",\n')], MISSING),
    ("affected_systems (a section 11 addition) dropped from the required fields",
     [("replace", SCHEMA, '    "affected_systems",\n', "")], MISSING),
    # Since $defs/agreeing_lifecycle, a widened enum alone is still refused for a record; the contract test is what
    # holds the enum to the ledger's six states.
    ("the lifecycle widened with OUTDATED",
     [("replace", SCHEMA, '        "exploratory"\n      ]', '        "exploratory",\n        "outdated"\n      ]')],
     CONTRACT),
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
    ("status and lifecycle_state no longer held to state (review MUF-S1)",
     [("replace", SCHEMA, ',\n    {\n      "$ref": "#/$defs/agreeing_lifecycle"\n    }\n  ],', "\n  ],")],
     LIFECYCLE_AGREE),
    ("a zero-width text accepted as recorded (review MUF-S1)",
     [("replace", SCHEMA, '"pattern": "[^\\\\s\\\\u00ad\\\\u200b-\\\\u200f\\\\u2060-\\\\u2064\\\\ufeff]"',
       '"pattern": "\\\\S"')], REFUSES),
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
    ("a GOAL-GRAVITY field its own document states turned back into a gap (review MUF-N1)",
     [("replace", GRAVITY, '"binding_scope": "uniimente-kernel canonical runtime (`egregore/`); organs consume through '
       'existing adapters/contracts; the dated id avoids the numeric `INTENT-00NN` series that is contended across '
       'unmerged branches (0029\\u20130037 allocated in drafts)",',
       '"binding_scope": {"unrecorded": "not recorded"},')],
     DOC_GAP),
    ("a field copied from GOAL-GRAVITY's document paraphrased",
     [("replace", GRAVITY, 'or \\"creates coincidences\\" resting on this code alone"',
       'or \\"creates coincidences\\" resting on this code"')], DOC_COPY),
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
     [("replace", PATH_PY, "            if not any(_phrase(item, text) for text in texts):", "            if False:")],
     H_REFUSES),
    ("an empty pointer list accepted (review MUF-A1)",
     [("replace", PATH_PY, '            if not refs:\n                return "recorded_as names no field '
       '(an empty list records nothing)"\n', "")], H_EMPTY),
    ("a frontier backcast pointer allowed to belong to another horizon (review MUF-A2, MUF-R1)",
     [("replace", PATH_PY, '        return None if owner == horizon["id"] else f"belongs to horizon {owner!r}"',
       "        return None")], H_BORROWED),
    ("any cognition P-node accepted, named by the horizon or not (review MUF-R1)",
     [("replace", PATH_PY, '        if re.search(rf"(?<![\\w-]){re.escape(parts[3])}(?![\\w-])", named):',
       "        if True:")], H_BORROWED),
    ("any path accepted, another horizon's fields included (review MUF-A2, MUF-R1)",
     [("replace", PATH_PY,
       '    return "is not this horizon\'s field, one of its frontier backcasts or a node it names"', "    return None")],
     H_BORROWED),
    ("a path-sourced value matched as a bare substring (review MUF-A2, MUF-R1)",
     [("replace", PATH_PY, '    if not re.search(rf"(?<![\\w./-]){re.escape(item)}(?![\\w/-]|\\.\\w)", text):',
       "    if item not in text:")], H_BORROWED),
    ("a lone common word or letter accepted as a name (review MUF-R1)",
     [("replace", PATH_PY, '    return len(item.split()) > 1 or (len(item) > 1 and re.search(r"[A-Z0-9_./-]", item) is '
       'not None)', "    return True")], H_BORROWED),
    ("a value citing path fields and files at once accepted (review MUF-R2)",
     [("replace", PATH_PY, "        if inside and len(inside) != len(sources):", "        if False:")], H_BORROWED),
    ("a zero-width reason accepted as recorded text",
     [("replace", PATH_PY, 'VISIBLE = re.compile(r"[^\\s\\u00ad\\u200b-\\u200f\\u2060-\\u2064\\ufeff]")',
       'VISIBLE = re.compile(r"\\S")')], H_REFUSES),
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
    ("a directive interface cited from another section (computer_use under section 39)",
     [("replace", PATH_JSON, '-source.md#31-computer-use"', '-source.md#39-organizational-morphogenesis"')], VERBATIM),
    ("developmental_research's inferred P10 falsifier restored (review MUF-R1)",
     [("replace", PATH_JSON, '"recorded_as": "frontier_backcasts/substrate_independent_developmental_intelligence/'
       'nearest_falsifiable_experiment"\n        }\n      ]',
       '"recorded_as": "frontier_backcasts/substrate_independent_developmental_intelligence/'
       'nearest_falsifiable_experiment"\n        },\n        {\n          "recorded_as": '
       '"workstreams/cognition_cortex/nodes/P10/falsification"\n        }\n      ]')], CARRIES),
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
    ("an id the ledger only mentions dropped from the pinned snapshot",
     [("replace", SNAPSHOT, '   "INTENT-20261001-open-source-mechanism-harvest",\n', "")], MENTION),
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
    ("ledger ids read from headings only, so an id the ledger only mentions is never pinned",
     [("replace", CHECK, '    return re.findall(rf"(?<![\\w/-])({ID})(?![\\w-])", text)',
       '    return re.findall(rf"^#+ ({ID})\\b", text, re.M)')], MENTION),
    ("a ledger id read as present while the ledger names only a longer id",
     [("replace", CHECK, '"ledger_records": lambda i: i in declared or bool(_token(i).search(ledger)),',
       '"ledger_records": lambda i: i in declared or i in ledger,')], LONGER),
    ("succession read from every field of a record (superseded_by and conflicts included), not its supersedes",
     [("replace", CHECK, '        named = row.get("supersedes")',
       '        named = [e for v in row.values() for e in (v if isinstance(v, list) else [v])]')], NOT_SUCCESSION),
    ("succession read from any whole-word mention inside a supersedes entry (review MUF-C2, MUF-R3)",
     [("replace", CHECK, "        out |= {entry.strip() for entry in entries if isinstance(entry, str)}",
       '        out |= set(re.findall(r"[\\w-]+", " ".join(e for e in entries if isinstance(e, str))))')], PROSE),
    ("succession pooled across intent records, horizons and backcasts (review MUF-C2, MUF-R3)",
     [("replace", CHECK, "            if present[kind](identifier) or identifier in named[SUCCESSOR[kind]]:",
       "            if present[kind](identifier) or identifier in set().union(*named.values()):")], KINDED),
    ("a markdown record turned JSON no longer counts (the documented lawful path)",
     [("replace", CHECK, '"intent_documents": lambda i: i in declared,',
       '"intent_documents": lambda i: i in now["intent_documents"],')], LAWFUL),
    ("a re-pin no longer refuses a deletion (review MUF-C1)",
     [("replace", CHECK, "    gone = missing(snapshot, root)\n    if gone:", "    gone = []\n    if gone:")], REPIN),
    ("a re-pin rewrites the pinned commit's ids (review MUF-C1)",
     [("replace", CHECK, "    out = copy.deepcopy(snapshot)\n", "    out = dict(copy.deepcopy(snapshot), ids=ids)\n")],
     REPIN),
    ("write_snapshot ignores the committed snapshot and pins afresh (review MUF-C1)",
     [("replace", CHECK, '    old = json.loads(target.read_text(encoding="utf-8")) if target.exists() else None',
       "    old = None")], WRITE),
    ("an id and its only ledger mention dropped together, the snapshot thinned to match (review MUF-R4)",
     [("replace", SNAPSHOT, '   "INTENT-20261021-COMPLETE-COLLABORATION",\n', ""),
      ("replace", LEDGER_FILE, "INTENT-20261021-COMPLETE-COLLABORATION", "the collaboration intent")], PINNED),
    ("an id matched as a prefix of a longer one",
     [("replace", CHECK, '    return re.compile(rf"(?<![\\w/-]){re.escape(identifier)}(?![\\w-])")',
       "    return re.compile(re.escape(identifier))")], LONGER),
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
