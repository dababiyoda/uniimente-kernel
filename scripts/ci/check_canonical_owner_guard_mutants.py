"""Each safeguard of the canonical-owner registry (directive section 52) must fail its test when defeated.

The registry is ``function_owner_records`` in docs/collaboration/ARCHITECTURE-OWNERSHIP-MAP.yaml; the guards are
tests/unit/test_canonical_owner_guard.py. A mutant here is a change a contributor could make: drop a record, an
entry or a field, import a historical alternate from greg/, add a re-implementation or a copy, add a second owner,
resolve a founder decision alone, narrow the markers, rename what the registry names, or weaken a guard. Each names
the test that must fail on it. The mutants added after the 2026-10-30 review of 77deac50 name the finding they
replay (F1-F8, MUH-F1-MUH-F5); those added when #196 was merged in on 2026-11-04 are marked MERGE-196; those for
guard 4 (copies of a registered body), the exact candidate pin and the history guard (2026-11-21) are marked MW-C,
and those for the review of 7c2b39e5 (2026-11-22) are marked MW-C round 4 with the finding they replay (N1-N7);
those for the review of 79ef5742 (2026-11-22) are marked MW-C round 6 with the item they close (B1-B4).
A ``copy_body`` edit writes a disguised copy of a registered function at run time (every name and literal changed),
so the mutant follows the function as it is today instead of a frozen text that would stop being a copy.

Every mutant runs in one scratch copy of the repository with ``python -B`` and PYTHONDONTWRITEBYTECODE=1, after every
``__pycache__`` in the copy is purged, and the copy is restored after each. The unmutated copy must pass the whole
test file first; each mutant then runs the test it names. A mutant whose text no longer occurs exactly once, or whose
new file already exists, is STALE.
"""
from pathlib import Path
import ast
import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
TESTS = "tests/unit/test_canonical_owner_guard.py"
MAP = "docs/collaboration/ARCHITECTURE-OWNERSHIP-MAP.yaml"
SHAPE = "test_registry_names_an_owner_status_alternates_and_conditions_for_every_required_function"
PINS = "test_the_registry_keeps_every_pinned_record_entry_and_founder_decision"
MARKERS = "test_every_record_catches_the_names_it_must_and_exempts_only_common_names"
EXISTS = "test_every_registered_module_and_qualname_exists"
IMPORTS = "test_no_greg_module_imports_a_retired_or_historical_alternate"
DYNAMIC = "test_every_dynamic_import_in_greg_resolves_or_is_allowlisted"
DEFINES = "test_no_unrecorded_reimplementation_of_a_registered_function"
VACUOUS = "test_the_registry_has_at_least_one_alternate_the_import_guard_applies_to"
AUTONOMY_B = "test_the_adopted_autonomy_ladder_is_candidate_side_b_and_only_a_founder_ruling_promotes_it"
BODIES = "test_no_copy_of_a_registered_function_body_outside_its_record"
DISTINCT = "test_no_distinct_entry_names_a_module_that_holds_a_copy_of_a_registered_body"
HISTORY = "test_every_historical_or_retired_alternate_still_in_the_tree_says_what_keeps_it"
CATCHES = "test_the_body_guard_catches_renamed_nested_relocated_and_one_line_copies"
FRESH = "test_the_fingerprint_erases_a_fresh_copy_once_and_leaves_the_parsed_tree_alone"
VOUCH = "test_a_distinct_entry_cannot_vouch_for_a_module_that_holds_a_copy"
UNDECIDED = "test_an_undecided_record_takes_no_new_candidate_without_a_pin_change"
UNDECIDED_ALTERNATE = "test_an_undecided_record_takes_no_new_alternate_without_a_pin_change"
OWN_LOCATION = "test_a_registered_body_is_exempt_only_at_its_own_location"
TWINS = "test_two_registered_locations_with_one_body_fail"
KEPT_RULES = "test_kept_for_names_the_alternates_own_open_record_and_a_consumer_outside_tests_and_tools"
EXEMPT = "test_a_pinned_exemption_clears_exactly_one_location_and_a_stale_one_fails"
QUIET = "test_a_file_with_an_invalid_escape_parses_without_a_warning_on_any_python"
ONE_NODE = "test_the_body_guard_ignores_one_node_edits_pass_no_op_constants_annotations_and_import_aliases"
SEALED = "test_the_body_scan_reads_cortex_evaluation_except_the_files_a_freeze_manifest_seals"
LINKS = "test_the_body_scan_reads_bom_files_follows_links_inside_the_repository_only_and_sees_pycache"
UNDECIDED_ROLES = "test_an_undecided_record_takes_no_new_or_changed_entry_of_any_role_without_a_pin_change"
DISTINCT_SHAPE = "test_guard_3_reports_a_structural_copy_even_where_a_distinct_entry_names_it"
SEALS_ONLY = "test_a_freeze_manifest_seals_only_the_files_and_bytes_the_test_pins"
LAST_BINDING = "test_a_registered_qualname_names_its_last_binding_as_python_does"
COMPARED_PIN = "test_the_set_of_compared_registered_bodies_is_pinned"
SHADOW = "test_a_package_shadows_a_module_of_the_same_name_and_no_two_files_share_a_module_name"
ONCE = "test_the_walk_reads_each_real_file_once_and_follows_file_links_anywhere"
ONE_BINDING = "test_every_registered_qualname_has_one_binding_and_its_module_no_computed_binding"
DECOYS = "test_a_decoy_rebinding_or_star_import_of_a_registered_qualname_fails"
NEW_RECORD = "test_a_new_record_fails_until_it_is_pinned"
# A new CANONICAL record that names candidate side A of the undecided goal runtime as its owner and side B as its
# ALTERNATE (round 5's X1), with no ruling and no change to the test.
ADOPTED_RECORD = ("  - record_id: OWN-FN-GOAL-RUNTIME-ADOPTED\n    function: the goal runtime, adopted\n"
                  "    effect: one goal runtime\n    owner_status: CANONICAL\n    canonical:\n"
                  "      - module: greg.goal_gravity\n        qualnames: [tick]\n"
                  "    evidence: [\"adopted by an agent\"]\n    alternates:\n      - module: greg.gravity\n"
                  "        qualnames: [select, step]\n        status: ALTERNATE\n        reason: the rival\n"
                  "        retirement_condition: never\n    migration_path: none\n    markers:\n"
                  "      - 'GoalRuntimeAdopted'\n\n")
INBOX_RECORD_START = "  - record_id: OWN-FN-INBOX-TRANSPORT\n"
CLASS_WHOLE = "test_a_registered_class_body_is_compared_whole_at_its_own_location_and_for_twins"
COMMERCIAL_ALTERNATE = "      - module: business.commercial_loop\n        qualnames: [CommercialLoop, STAGES]\n"
SEALED_SHADOW = "test_a_package_beside_a_sealed_file_fails_the_module_name_rule"
REMOTE_SIG = "def handle(home: Path, method: str, path: str, headers, body: bytes, *, now: datetime | None = None):\n"
REALITY_KEPT = "        kept_for: {consumer: acceptance.claims.crosswalk_problems}\n"
# A copy of greg.organs.exchange recorded as 'distinct' in the organ-exchange record.
DISTINCT_COPY = [("copy_body", "greg/organs.py", "exchange", "greg/organ_relay2.py", "function"),
                 ("replace", MAP, "    migration_path: >-\n      the organ-exchange template signs organ.exchange;",
                  "      - module: greg.organ_relay2\n        qualnames: [exchange_copy]\n"
                  "        why: \"a different exchange\"\n"
                  "    migration_path: >-\n      the organ-exchange template signs organ.exchange;")]
REHEARSAL = ("        status: ALTERNATE\n        reason: >-\n"
             "          a FIXTURE rehearsal of the Foundry company loop")
ORGAN_ALT = "        status: ALTERNATE\n        reason: >-\n          the organs.exchange capability"
RETIRED_ORGAN_ALT = ("        status: RETIRED\n        revival_condition: none\n        reason: >-\n"
                     "          the organs.exchange capability")
# The goal runtime made CANONICAL by an agent, side B owner and side A alternates, with no founder ruling (F6).
GOAL_UNDECIDED = ("    refines: [OWN-0008]\n    owner_status: NEEDS_FOUNDER_DECISION\n    canonical: []\n"
                  "    candidates:\n      - side: A\n        module: greg.goal_gravity\n")
GOAL_FLIPPED = ("    refines: [OWN-0008]\n    owner_status: CANONICAL\n    canonical:\n      - module: greg.gravity\n"
                "        qualnames: [select, step]\n    evidence: [\"flipped by an agent\"]\n{ruling}"
                "    candidates:\n      - side: A\n        module: greg.goal_gravity\n")
GOAL_ALTERNATES = "    alternates:\n      - module: egregore.goal_chase\n"
GOAL_FLIPPED_ALTERNATES = "    alternates:\n" + "".join(
    f"      - module: {m}\n        qualnames: [{q}]\n        status: ALTERNATE\n        reason: flipped\n"
    f"        retirement_condition: flipped\n" for m, q in (("greg.goal_gravity", "tick"),
                                                           ("egregore.gravity", "GoalGravityLoop"),
                                                           ("egregore.goals", "GoalRegistry, GoalSpec"))
) + "      - module: egregore.goal_chase\n"


def _flip(ruling: str = "") -> list:
    return [("replace", MAP, GOAL_UNDECIDED, GOAL_FLIPPED.format(ruling=ruling)),
            ("cut", MAP, "    candidates:\n      - side: A\n        module: greg.goal_gravity\n",
             "    review_trigger: >-\n      the founder's ruling on the canonical Goal Gravity runtime"),
            ("replace", MAP, GOAL_ALTERNATES, GOAL_FLIPPED_ALTERNATES)]


# (name, edits, test that must fail). An edit is ("replace", path, old, new), ("cut", path, start, end): remove from
# the unique ``start`` up to the next ``end`` (None: to the end of the file), ("append", path, text),
# ("create", path, text), ("copy_def", path, name, new_name, new_path): a top-level def copied under a new name, or
# ("copy_body", path, name, new_path, form): a top-level def copied with every name and literal changed, as a
# function, a method ("method") or a nested def ("nested") (``_copy_body``), ("append_body", path, name,
# existing_path, form): the same copy appended to a file that exists, ("seal", manifest_path, path): a new freeze
# manifest that hashes the current bytes of ``path``, or ("copy_class", path, name, new_name, new_path) and
# ("append_class", path, name, new_name, existing_path): a verbatim copy of a top-level class under a new name, in a
# new file or appended to one that exists.
MUTANTS = [
    ("a registry entry removed: temporary teams",
     [("cut", MAP, "  - record_id: OWN-FN-TEMPORARY-TEAMS\n", "  - record_id: OWN-FN-COMMERCE-CLOSURE\n")], SHAPE),
    ("a registry entry removed: goal runtime",
     [("cut", MAP, "  - record_id: OWN-FN-GOAL-RUNTIME\n", "  - record_id: OWN-FN-STATUS-EVIDENCE-LADDER\n")], SHAPE),
    ("an alternate removed: the venture rehearsal",
     [("cut", MAP, "      - module: greg.venture_rehearsal\n", "      - module: business.commercial_loop\n")], DEFINES),
    ("a distinct entry removed: forecast quantile LEVELS",
     [("replace", MAP, '      - module: greg.cognition.genomes.forecasting\n        qualnames: [LEVELS]\n'
                       '        why: "forecast quantile levels"\n', "")], DEFINES),
    ("a historical alternate imported from greg/, inside a function",
     [("append", "greg/console.py", "\n\ndef _mutant_ladder():\n    from greg.mission_control import REALITY\n"
                                    "    return REALITY\n")], IMPORTS),
    ("a historical alternate reached through a module alias",
     [("append", "greg/briefs.py", "\nfrom greg import mission_control as _mc\n_MUTANT = _mc.REALITY\n")], IMPORTS),
    ("a historical alternate imported relatively under another name",
     [("append", "greg/metrics.py", "\nfrom .mission_control import REALITY as _LADDER\n")], IMPORTS),
    ("the venture rehearsal retired while greg still imports it",
     [("replace", MAP, REHEARSAL, REHEARSAL.replace("status: ALTERNATE", "status: RETIRED\n        revival_condition: "
                                                    "none"))], IMPORTS),
    ("the organ-exchange alternate retired while a capability still binds it with _lazy",
     [("replace", MAP, ORGAN_ALT, RETIRED_ORGAN_ALT)], IMPORTS),
    ("a re-implementation of temporary teams added (greg/team_forming.py)",
     [("create", "greg/team_forming.py", "class TeamError(RuntimeError):\n    pass\n\n\n"
                                  "def form_team(members, grant):\n    return {'members': members}\n")], DEFINES),
    ("a third evidence ladder added (governance/reality_ladder.py)",
     [("create", "governance/reality_ladder.py", "REALITY_LADDER = ('ASPIRATIONAL', 'PROPOSED', 'DOCUMENTED')\n")],
     DEFINES),
    ("a second regression closer added (greg/regressions.py)",
     [("create", "greg/regressions.py", "def close_regression(journal, regression_id):\n    return None\n")], DEFINES),
    ("a second autonomy ladder added in #235's shape",
     [("create", "greg/earned.py", "LEVELS = ('SHADOW', 'RECOMMENDER')\nEARNED_CEILING = 'RECOMMENDER'\n")], DEFINES),
    ("a second goal loop added (egregore/pursuit.py)",
     [("create", "egregore/pursuit.py", "class GoalRuntime:\n    pass\n")], DEFINES),
    ("a stale qualname: the canonical regression closer renamed",
     [("replace", "greg/improvement.py", "def _close_regressions(", "def _close_regressions_v2(")], EXISTS),
    ("a stale module: the team owner's path mistyped",
     [("replace", MAP, "      - module: foundry.systems.teams\n", "      - module: foundry.systems.team\n")], EXISTS),
    ("a stale qualname in the registry",
     [("replace", MAP, "qualnames: [_close_regressions, _reopen_regressions",
       "qualnames: [_close_regression, _reopen_regressions")], EXISTS),
    ("an undecided owner declared canonical without its evidence",
     [("replace", MAP, GOAL_UNDECIDED, GOAL_UNDECIDED.replace("NEEDS_FOUNDER_DECISION", "CANONICAL"))], SHAPE),
    ("an alternate left without its retirement condition",
     [("replace", MAP, "        retirement_condition: >-\n          a founder-tier business case closes",
       "        note: >-\n          a founder-tier business case closes")], SHAPE),
    ("the only historical alternate relabelled, leaving the import guard vacuous",
     [("replace", MAP, "        status: HISTORICAL\n", "        status: ALTERNATE\n        retirement_condition: none\n")],
     VACUOUS),
    # -- F1: constant-name dynamic imports and attribute chains on them ------------------------------------------
    ("F1: __import__(..., fromlist).REALITY in greg/console.py",
     [("append", "greg/console.py", "\n\ndef _probe_ladder():\n"
                                    "    return __import__('greg.mission_control', fromlist=['REALITY']).REALITY\n")],
     IMPORTS),
    ("F1: import_module bound to a name, then .REALITY (greg/briefs.py)",
     [("append", "greg/briefs.py", "\n\ndef _probe_ladder():\n    import importlib\n"
                                   "    m = importlib.import_module('greg.mission_control')\n    return m.REALITY\n")],
     IMPORTS),
    ("F1: getattr(module, 'REALITY') (greg/metrics.py)",
     [("append", "greg/metrics.py", "\nfrom greg import mission_control as _mc\n_X = getattr(_mc, 'REALITY')\n")],
     IMPORTS),
    # -- F2: a module name from a table, and a name guard 2 cannot resolve ---------------------------------------
    ("F2: the organ-exchange alternate retired while only appraisal's DELIVERING still reaches it",
     [("replace", MAP, ORGAN_ALT, RETIRED_ORGAN_ALT),
      ("replace", "greg/capabilities.py", '_lazy("greg.organ_exchange", "exchange")', '_lazy("greg.organs", "exchange")'),
      ("replace", "greg/capabilities.py", '_lazy("greg.organ_exchange", "status")', '_lazy("greg.organs", "status")')],
     IMPORTS),
    ("F2: an unresolvable dynamic import added to greg/console.py",
     [("append", "greg/console.py", "\n\ndef _probe_load(name):\n    import importlib\n"
                                    "    return importlib.import_module(name)\n")], DYNAMIC),
    ("F2: the evolution sandbox's allowlist entry removed from the guard",
     [("replace", TESTS, '    ("greg/cognition/evolution_sandbox.py", "main"):\n'
                         '        "imports the modules a TARGETS row names (greg.cognition.genomes modules and numpy), '
                         'unpacked from a tuple",\n', "")], DYNAMIC),
    # -- F3: a re-implementation under a registered name, or a renamed copy --------------------------------------
    ("F3: send_signed re-implemented under its own name (greg/nodes.py)",
     [("create", "greg/nodes.py", "def send_signed(home, key, kind, body):\n    return None\n")], DEFINES),
    ("F3: exchange re-implemented under its own name (greg/organ_relay.py)",
     [("create", "greg/organ_relay.py", "def exchange(params, ctx):\n    return {}\n")], DEFINES),
    ("F3: form, act and dissolve re-implemented (foundry/systems/crew.py)",
     [("create", "foundry/systems/crew.py", "def form(store, spec):\n    pass\n\n\ndef act(store, spec):\n    pass\n\n\n"
                                            "def dissolve(store, spec):\n    pass\n")], DEFINES),
    ("F3: tick and select re-implemented (egregore/pursuit_runtime.py)",
     [("create", "egregore/pursuit_runtime.py", "def tick(body):\n    pass\n\n\ndef select(missions):\n"
                                                "    return missions\n")], DEFINES),
    ("F3: a renamed verbatim copy of greg.organs.exchange (greg/organ_relay.py)",
     [("copy_def", "greg/organs.py", "exchange", "relay_exchange", "greg/organ_relay.py")], DEFINES),
    # -- F4: the markers narrowed or neutralized; a rare name exempted -------------------------------------------
    ("F4: the autonomy markers neutralized",
     [("cut", MAP, "      - '_?([A-Z][A-Za-z0-9]*)?Autonomy([A-Z][A-Za-z0-9]*)?'\n", "\n  - record_id: OWN-FN-REGRESSION"),
      ("replace", MAP, "\n  - record_id: OWN-FN-REGRESSION", "      - '(?!)'\n\n  - record_id: OWN-FN-REGRESSION")],
     MARKERS),
    ("F4: one autonomy marker dropped (_?LEVELS)",
     [("replace", MAP, "      - '_?LEVELS'\n", "")], MARKERS),
    ("F4: a rare registered name declared generic (send_signed)",
     [("replace", MAP, "    markers:\n      - '_?([a-z0-9]+_)*send_signed(_[a-z0-9]+)*'\n",
       "    generic_names: [send_signed]\n    markers:\n      - '_?([a-z0-9]+_)*send_signed(_[a-z0-9]+)*'\n")], MARKERS),
    # -- F5: a second canonical owner ------------------------------------------------------------------------------
    ("F5: a second canonical module added to temporary teams",
     [("replace", MAP, "        qualnames: [form, act, dissolve, report]\n",
       "        qualnames: [form, act, dissolve, report]\n      - module: greg.team_forming\n        qualnames: [form_team]\n"),
      ("create", "greg/team_forming.py", "def form_team(members, grant):\n    return {'members': members}\n")], PINS),
    # -- F6: a founder decision resolved by an agent ---------------------------------------------------------------
    ("F6: the goal runtime made canonical with no founder ruling", _flip(), PINS),
    ("F6: the same, citing a ruling file that does not exist",
     _flip("    founder_ruling: docs/decisions/ADR-GOAL-GRAVITY-RULING.md\n"), PINS),
    ("F6: the same, citing a proposed ADR that does not rule on the record",
     _flip("    founder_ruling: docs/decisions/ADR-GOAL-GRAVITY-002-greg-binding.md\n"), PINS),
    # -- MUH-F1: a record or an entry removed ------------------------------------------------------------------------
    ("MUH-F1: the inbox-transport record removed",
     [("cut", MAP, "  - record_id: OWN-FN-INBOX-TRANSPORT\n", None)], SHAPE),
    ("MUH-F1: the organ-exchange record removed",
     [("cut", MAP, "  - record_id: OWN-FN-ORGAN-EXCHANGE\n", "  - record_id: OWN-FN-INBOX-TRANSPORT\n")], PINS),
    ("MUH-F1: the greg.organ_exchange alternate removed",
     [("cut", MAP, "      - module: greg.organ_exchange\n", "    distinct:\n")], PINS),
    ("MUH-F1: the business.commercial_loop alternate removed",
     [("cut", MAP, "      - module: business.commercial_loop\n        qualnames: [CommercialLoop, STAGES]\n",
       "    distinct:\n")], PINS),
    ("MUH-F1: candidate B (acceptance) of the evidence ladder removed",
     [("cut", MAP, "      - side: B\n        module: acceptance\n", "      - side: C\n")], PINS),
    ("MUH-F1: the egregore.local_mission distinct entry removed",
     [("cut", MAP, "      - module: egregore.local_mission\n", "    migration_path: >-\n      the founder's ruling makes")],
     PINS),
    ("MUH-F1: a canonical qualname dropped (founder_revert)",
     [("replace", MAP, "_reopen_regressions, founder_revert, attention_close_condition",
       "_reopen_regressions, attention_close_condition")], PINS),
    # -- MUH-F2: GoalChase -------------------------------------------------------------------------------------------
    ("MUH-F2: the GoalChase alternate removed",
     [("cut", MAP, "      - module: egregore.goal_chase\n", "    distinct:\n")], PINS),
    ("MUH-F2: a second goal-chase engine added (egregore/chase_runtime.py)",
     [("create", "egregore/chase_runtime.py", "class GoalChaseRuntime:\n    pass\n")], DEFINES),
    # -- MUH-F5: migration path and review trigger -------------------------------------------------------------------
    ("MUH-F5: the organ-exchange migration_path removed",
     [("replace", MAP, "    migration_path: >-\n      the organ-exchange template signs organ.exchange;",
       "    note: >-\n      the organ-exchange template signs organ.exchange;")], SHAPE),
    ("MUH-F5: the autonomy review_trigger removed",
     [("replace", MAP, "    review_trigger: >-\n      the founder's ruling on section 59's five levels",
       "    note: >-\n      the founder's ruling on section 59's five levels")], SHAPE),
    # -- MERGE-196: entries for what #196 adopted after b1950be2 (#235 at 6fc4b22b, #236 at 2161dbe2) -------------
    ("MERGE-196: #235's ladder, candidate side B (greg.autonomy), removed from the record",
     [("cut", MAP, "      - side: B\n        module: greg.autonomy\n",
       "    decision_needed: >-\n      whether autonomy/levels.py")], DEFINES),
    ("MERGE-196: one side-B qualname dropped (regress)",
     [("replace", MAP, "qualnames: [LEVELS, EARNED_CEILING, earned_level, report, regress]",
       "qualnames: [LEVELS, EARNED_CEILING, earned_level, report]")], PINS),
    ("MERGE-196: side B made canonical by an agent, with no founder ruling",
     [("replace", MAP, "    owner_status: NEEDS_FOUNDER_DECISION\n    canonical: []\n    candidates:\n"
                       "      - side: A\n        module: autonomy.levels\n",
       "    owner_status: CANONICAL\n    canonical:\n      - module: greg.autonomy\n"
       "        qualnames: [LEVELS, EARNED_CEILING, earned_level, report, regress]\n"
       "    evidence: [\"flipped by an agent\"]\n    candidates:\n      - side: A\n        module: autonomy.levels\n")],
     PINS),
    ("MERGE-196: greg.autonomy unpinned, so a founder ruling could not promote it",
     [("replace", TESTS, ',\n                       "greg.autonomy": ("LEVELS", "EARNED_CEILING", "earned_level", "report", '
                         '"regress")},', "},")], AUTONOMY_B),
    ("MERGE-196: the greg.autonomy regress distinct entry removed (regression closing)",
     [("cut", MAP, "      - module: greg.autonomy\n        qualnames: [regress]\n",
       "      - module: foundry.systems.repair\n")], PINS),
    ("MERGE-196: #236's greg.path build-state distinct entry removed (evidence ladder)",
     [("cut", MAP, "      - module: greg.path\n        qualnames: [STRUCTURALLY_BUILT",
       "    migration_path: >-\n      the founder's ruling names the canonical tuple")], PINS),
    # -- F8: module-level bindings the definition scan did not see ---------------------------------------------------
    ("F8: a ladder bound by a module-level for loop (governance/reality_loop.py)",
     [("create", "governance/reality_loop.py", "for REALITY_LADDER in [('ASPIRATIONAL', 'PROPOSED')]:\n    pass\n")],
     DEFINES),
    ("F8: an autonomy ladder bound through globals() (greg/earned_globals.py)",
     [("create", "greg/earned_globals.py", "globals()['EARNED_CEILING'] = 'RECOMMENDER'\n")], DEFINES),
    ("F8: a ladder bound by a walrus in a module-level if (greg/earned_walrus.py)",
     [("create", "greg/earned_walrus.py", "if (LEVELS := ('SHADOW', 'RECOMMENDER')):\n    pass\n")], DEFINES),
    ("F8: a ladder imported under a marked alias (greg/earned_alias.py)",
     [("create", "greg/earned_alias.py", "from json import loads as EARNED_CEILING\n")], DEFINES),
    # -- MW-C: guard 4, copies of a registered body anywhere in the runtime tree ------------------------------------
    ("MW-C: a method copy of greg.business_loop.reconcile in business/ (names and literals changed)",
     [("copy_body", "greg/business_loop.py", "reconcile", "business/case_copy.py", "method")], BODIES),
    ("MW-C: a copy of foundry.systems.teams.form in its own directory (foundry/systems/team_copy.py)",
     [("copy_body", "foundry/systems/teams.py", "form", "foundry/systems/team_copy.py", "function")], BODIES),
    ("MW-C: a nested-def copy of greg.body.send_signed outside the six packages (acceptance/relay_copy.py)",
     [("copy_body", "greg/body.py", "send_signed", "acceptance/relay_copy.py", "nested")], BODIES),
    ("MW-C: a copy of greg.remote.handle in scripts/ (scripts/remote_copy.py)",
     [("copy_body", "greg/remote.py", "handle", "scripts/remote_copy.py", "function")], BODIES),
    ("MW-C: a copy of greg.organs.exchange recorded as distinct", DISTINCT_COPY, DISTINCT),
    ("MW-C: guard 4 exempts a record's distinct modules",
     [("replace", TESTS, "                if (module, name) != (body.module, body.qualname):\n",
       "                if (module, name) != (body.module, body.qualname) and module not in "
       "{e['module'] for e in body.record.get('distinct') or []}:\n")],
     VOUCH),
    ("MW-C: constant erasure removed from the anonymiser",
     [("replace", TESTS, "        node.value, node.kind = ERASED, None\n", "        node.kind = None\n")], CATCHES),
    ("MW-C: the fingerprint erases the parsed tree in place (no fresh copy)",
     [("replace", TESTS, "_Erase().visit(ast.Module(body=copy.deepcopy(_function_body(fn)), type_ignores=[]))",
       "_Erase().visit(ast.Module(body=_function_body(fn), type_ignores=[]))")], FRESH),
    ("MW-C: methods and nested defs no longer scanned",
     [("replace", TESTS, "                    out.append((name, child))\n                visit(child, name)\n",
       "                    out.append((name, child))\n")], CATCHES),
    ("MW-C: the scan narrowed to the six guarded packages",
     [("replace", TESTS, '(relative.name.startswith(".") or f"{relative.name}/" in NOT_RUNTIME)\n',
       '(relative.name.startswith(".") or f"{relative.name}/" in NOT_RUNTIME\n'
       '                                         or relative.name not in GUARDED)\n')],
     CATCHES),
    ("MW-C: files skipped by a path segment (any evaluation/ directory) instead of the sealed set",
     [("replace", TESTS, 'return not relative.startswith(".") and relative not in sealed\n',
       'return not relative.startswith(".") and "/evaluation/" not in "/" + relative\n')], CATCHES),
    # -- MW-C: the candidates of an undecided record are pinned exactly ---------------------------------------------
    ("MW-C: a third candidate added to the undecided goal runtime (side C)",
     [("replace", MAP, "      - side: B\n        module: greg.gravity\n",
       "      - side: C\n        module: egregore.local_mission\n        qualnames: [run_once]\n"
       "        evidence: [\"added by an agent\"]\n      - side: B\n        module: greg.gravity\n")], PINS),
    ("MW-C: a qualname added to an undecided record's candidate (greg.gravity rederive)",
     [("replace", MAP, "qualnames: [select, step]", "qualnames: [select, step, rederive]")], PINS),
    # -- MW-C round 3 (skeptic regression 1): a copy joins an undecided record as a live ALTERNATE ----------------
    ("MW-C: a disguised copy of greg.gravity.step recorded as a live ALTERNATE of the undecided goal runtime",
     [("copy_body", "greg/gravity.py", "step", "egregore/goal_engine2.py", "function"),
      ("replace", MAP, "    alternates:\n      - module: egregore.goal_chase\n",
       "    alternates:\n      - module: egregore.goal_engine2\n        qualnames: [step_copy]\n"
       "        status: ALTERNATE\n        reason: a third goal runtime\n"
       "        retirement_condition: when the founder rules on the goal runtime\n"
       "      - module: egregore.goal_chase\n")], PINS),
    ("MW-C: the same, its body caught by guard 4 as a twin of greg.gravity.step",
     [("copy_body", "greg/gravity.py", "step", "egregore/goal_engine2.py", "function"),
      ("replace", MAP, "    alternates:\n      - module: egregore.goal_chase\n",
       "    alternates:\n      - module: egregore.goal_engine2\n        qualnames: [step_copy]\n"
       "        status: ALTERNATE\n        reason: a third goal runtime\n"
       "        retirement_condition: when the founder rules on the goal runtime\n"
       "      - module: egregore.goal_chase\n")], BODIES),
    ("MW-C: a disguised copy of reconcile appended to an existing ALTERNATE module (no registry edit)",
     [("append_body", "greg/business_loop.py", "reconcile", "business/commercial_loop.py", "function")], BODIES),
    ("MW-C: the exact pin covers candidates only, not an undecided record's alternates",
     [("replace", TESTS, 'UNDECIDED_KEYS = ("canonical", "candidates", "alternates", "distinct")\n',
       'UNDECIDED_KEYS = ("canonical", "candidates")\n')], UNDECIDED_ALTERNATE),
    ("MW-C: guard 4 exempts every canonical, candidate and alternate module of the record again",
     [("replace", TESTS, "                if (module, name) != (body.module, body.qualname):\n",
       "                if module not in owned_modules(body.record):\n")], OWN_LOCATION),
    ("MW-C: two registered locations with one body pass",
     [("replace", TESTS, "        if len({registered for registered, _, _ in locations}) > 1:\n",
       "        if False:\n")], TWINS),
    ("MW-C: the exact candidate pin removed from pin_problems",
     [("replace", TESTS, "    return problems + undecided_problems(data, undecided)\n", "    return problems\n")],
     UNDECIDED),
    # -- MW-C: history kept only with a live reason (section 76) ----------------------------------------------------
    ("MW-C: REALITY's kept_for deleted", [("replace", MAP, REALITY_KEPT, "")], HISTORY),
    ("MW-C: REALITY kept for a consumer that does not read it (acceptance.claims.directive_levels)",
     [("replace", MAP, REALITY_KEPT, REALITY_KEPT.replace("crosswalk_problems", "directive_levels"))], HISTORY),
    ("MW-C: REALITY kept for a consumer under greg/ (greg.console.main)",
     [("replace", MAP, REALITY_KEPT, REALITY_KEPT.replace("acceptance.claims.crosswalk_problems", "greg.console.main"))],
     HISTORY),
    # -- MW-C round 3 (verifier's surviving code mutants): each part of the scan and the eraser has a positive control
    ("MW-C: async defs no longer scanned",
     [("replace", TESTS, "                if isinstance(child, kinds):\n                    out.append((name, child))\n",
       "                if isinstance(child, kinds) and not isinstance(child, ast.AsyncFunctionDef):\n"
       "                    out.append((name, child))\n")],
     CATCHES),
    ("MW-C: top-level .py files no longer scanned",
     [("replace", TESTS, 'return not relative.startswith(".") and relative not in sealed\n',
       'return not relative.startswith(".") and relative not in sealed and "/" in relative\n')], CATCHES),
    ("MW-C: all of cortex/ skipped",
     [("replace", TESTS, 'return not relative.startswith(".") and relative not in sealed\n',
       'return not relative.startswith(".") and not relative.startswith("cortex/")\n')], CATCHES),
    ("MW-C: except-as names no longer erased",
     [("replace", TESTS, "        self.generic_visit(node)\n        if node.name is not None:\n            node.name = ERASED\n"
                         "        return node\n\n    def visit_alias",
       "        self.generic_visit(node)\n        return node\n\n    def visit_alias")], CATCHES),
    ("MW-C: import aliases no longer erased",
     [("replace", TESTS, "    def visit_alias(self, node):\n        node.asname = ERASED\n",
       "    def visit_alias(self, node):\n")], CATCHES),
    ("MW-C: nested def names no longer erased",
     [("replace", TESTS, "        node.name, node.returns, node.type_comment = ERASED, None, None\n",
       "        node.returns, node.type_comment = None, None\n")], CATCHES),
    ("MW-C: an unparseable file dropped silently",
     [("replace", TESTS, "    return sorted(set(out)) + unreadable + stale\n", "    return sorted(set(out)) + stale\n")],
     CATCHES),
    ("MW-C: the distinct check sees only the copies of its own record's bodies",
     [("replace", TESTS, '            for c in holding.get(e.get("module"), []):\n',
       "            for c in [x for x in holding.get(e.get(\"module\"), []) if x['record'] is r]:\n")], VOUCH),
    # -- MW-C round 3: parse warnings hidden on every Python (3.11 reports an invalid escape as a DeprecationWarning)
    ("MW-C: the parse hides only SyntaxWarning",
     [("replace", TESTS, "QUIET = (SyntaxWarning, DeprecationWarning)\n", "QUIET = (SyntaxWarning,)\n")], QUIET),
    ("MW-C: the parse hides only DeprecationWarning",
     [("replace", TESTS, "QUIET = (SyntaxWarning, DeprecationWarning)\n", "QUIET = (DeprecationWarning,)\n")], QUIET),
    # -- MW-C round 3: what the filesystem walk reads and follows ---------------------------------------------------
    ("MW-C: the parse reads decoded text again (a UTF-8 BOM file is unparseable)",
     [("replace", TESTS, "ast.parse(path.read_bytes(), str(path))", "ast.parse(path.read_text(), str(path))")], LINKS),
    ("MW-C: a directory symlink followed out of the repository",
     [("replace", TESTS, "    if not real.is_relative_to(inside) or real in _on_path:\n",
       "    if real in _on_path:\n")], LINKS),
    ("MW-C: the symlink loop check removed",
     [("replace", TESTS, "    if not real.is_relative_to(inside) or real in _on_path:\n",
       "    if not real.is_relative_to(inside):\n")], LINKS),
    ("MW-C: directory symlinks never followed",
     [("replace", TESTS, "        if entry.is_dir():\n            if not skip(path):\n",
       "        if entry.is_dir(follow_symlinks=False):\n            if not skip(path):\n")], LINKS),
    ("MW-C: __pycache__ skipped by path segment",
     [("replace", TESTS, '        elif entry.name.endswith(".py") and entry.is_file():\n',
       '        elif entry.name.endswith(".py") and entry.is_file() and "__pycache__" not in path.parts:\n')], LINKS),
    # -- MW-C round 3 (skeptic regression 5): what may keep a HISTORICAL or RETIRED alternate -----------------------
    ("MW-C: REALITY kept for an unrelated open decision (OWN-FN-AUTONOMY-LEVELS)",
     [("replace", MAP, REALITY_KEPT, "        kept_for: {open_decision: OWN-FN-AUTONOMY-LEVELS}\n")], HISTORY),
    ("MW-C: REALITY kept for a helper appended to scripts/ci/ (a function that reads it, in tooling)",
     [("append", "scripts/ci/check_canonical_owner_guard_mutants.py",
       "\n\ndef _keep_reality():\n    from greg.mission_control import REALITY\n    return REALITY\n"),
      ("replace", MAP, REALITY_KEPT, REALITY_KEPT.replace("acceptance.claims.crosswalk_problems",
                                                         "scripts.ci.check_canonical_owner_guard_mutants._keep_reality"))],
     HISTORY),
    ("MW-C: open_decision may name another undecided record",
     [("replace", TESTS, '                if kept["open_decision"] != rid:\n', "                if False:\n")], KEPT_RULES),
    ("MW-C: open_decision accepted on the alternate's own decided record",
     [("replace", TESTS, '                elif by_id.get(rid, {}).get("owner_status") != "NEEDS_FOUNDER_DECISION":\n',
       "                elif False:\n")], KEPT_RULES),
    ("MW-C: a consumer under docs/ or scripts/ci/ accepted",
     [("replace", TESTS, 'NOT_CONSUMERS = ("greg", "tests", "docs", "scripts.ci")\n', 'NOT_CONSUMERS = ("greg", "tests")\n')],
     KEPT_RULES),
    ("MW-C: a consumer in a conftest.py accepted",
     [("replace", TESTS, 'NOT_CONSUMER_NAMES = ("conftest",)\n', "NOT_CONSUMER_NAMES = ()\n")], KEPT_RULES),
    # -- MW-C round 3 (skeptic regression 6): the reviewed exemption for a false positive ----------------------------
    ("MW-C: an exemption clears every copy in its module",
     [("replace", TESTS, '        key = (c["module"], c["name"])\n',
       '        key = next((k for k in exemptions if k[0] == c["module"]), (c["module"], c["name"]))\n')], EXEMPT),
    ("MW-C: an exemption clears a copy of any registered body",
     [("replace", TESTS, 'if key in exemptions and exemptions[key][0] == c["registered"] and ',
       "if key in exemptions and ")], EXEMPT),
    ("MW-C: a stale exemption passes",
     [("replace", TESTS, "if key not in used and str(reason).strip()]\n", "if False]\n")], EXEMPT),
    ("MW-C: an exemption with no reason clears its copy",
     [("replace", TESTS, ' and str(exemptions[key][1]).strip():\n', ":\n"),
      ("replace", TESTS, "for key, (resembles, reason) in exemptions.items() if not str(reason).strip()]\n",
       "for key, (resembles, reason) in exemptions.items() if False]\n")], EXEMPT),
    ("MW-C: the distinct check ignores the exemptions",
     [("replace", TESTS, "    for c in exempted(body_copies(records, root)[0], exemptions)[0]:\n",
       "    for c in body_copies(records, root)[0]:\n")], EXEMPT),
    # -- MW-C round 3: cortex/evaluation/ is scanned except the files a freeze manifest seals ----------------------
    ("MW-C: cortex/evaluation/ skipped wholesale again",
     [("replace", TESTS, 'return not relative.startswith(".") and relative not in sealed\n',
       'return not relative.startswith(".") and not relative.startswith(SEALED_UNDER)\n')], SEALED),
    ("MW-C: a manifest seals a file by name, whatever its bytes",
     [("replace", TESTS, '                f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}" == pinned):\n',
       "                True):\n")], SEALED),
    ("MW-C: a manifest seals files outside cortex/evaluation/",
     [("replace", TESTS, "        if relative.startswith(SEALED_UNDER) and path.is_file() and pinned in ",
       "        if path.is_file() and pinned in ")], SEALED),
    # -- MW-C round 3: one-node edits normalised before fingerprinting ---------------------------------------------
    ("MW-C: pass statements kept in the fingerprint",
     [("replace", TESTS, "    return (isinstance(node, ast.Pass) or (isinstance(node, ast.Expr)",
       "    return (False or (isinstance(node, ast.Expr)")], ONE_NODE),
    ("MW-C: no-op constant statements kept in the fingerprint",
     [("replace", TESTS, " or (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant))\n",
       " or False\n")], ONE_NODE),
    ("MW-C: an annotated assignment kept as written",
     [("replace", TESTS, "        return ast.Assign(targets=[node.target], value=node.value, type_comment=None)\n",
       "        return node\n"), ("replace", TESTS, '            ast.AnnAssign: "annotation"}\n', "}\n")], ONE_NODE),
    ("MW-C: an import alias erased only when one is written",
     [("replace", TESTS, "    def visit_alias(self, node):\n        node.asname = ERASED\n",
       "    def visit_alias(self, node):\n        if node.asname is not None:\n            node.asname = ERASED\n")],
     ONE_NODE),
    # -- MW-C round 4 (N1, N2): an undecided record is pinned whole; guard 3 never lets a distinct entry hide a copy
    ("MW-C round 4: WU-13's REALITY_LADDER joins the undecided evidence ladder as a distinct entry",
     [("create", "governance/reality_ladder.py", "REALITY_LADDER = ('PROPOSED', 'DESIGNED', 'IMPLEMENTED')\n"),
      ("replace", MAP, "      - module: greg.path\n        qualnames: [STRUCTURALLY_BUILT",
       "      - module: governance.reality_ladder\n        qualnames: [REALITY_LADDER]\n"
       "        why: \"the governance ladder of section 56 for policy claims\"\n"
       "      - module: greg.path\n        qualnames: [STRUCTURALLY_BUILT")], PINS),
    ("MW-C round 4: GoalChase revived from RESEARCH to a live ALTERNATE of the undecided goal runtime",
     [("replace", MAP, "        qualnames: [GoalChase]\n        status: RESEARCH\n",
       "        qualnames: [GoalChase]\n        status: ALTERNATE\n"
       "        retirement_condition: when the founder rules on the goal runtime\n")], PINS),
    ("MW-C round 4: the evidence of an undecided record's candidate edited",
     [("replace", MAP, "the A0-A9 ladder with ten promotion criteria", "the A0-A9 ladder with nine promotion criteria")],
     PINS),
    ("MW-C round 4: an undecided record's distinct entries left unpinned",
     [("replace", TESTS, 'UNDECIDED_KEYS = ("canonical", "candidates", "alternates", "distinct")\n',
       'UNDECIDED_KEYS = ("canonical", "candidates", "alternates")\n')], UNDECIDED_ROLES),
    ("MW-C round 4: an undecided record's entries compared by module and qualnames only (status and prose ignored)",
     [("replace", TESTS, "            have, want = list(r.get(key) or []), list(pin.get(key) or [])\n",
       "            have, want = ([{k: e.get(k) for k in ('module', 'qualnames')} for e in r.get(key) or []],\n"
       "                          [{k: e.get(k) for k in ('module', 'qualnames')} for e in pin.get(key) or []])\n")],
     UNDECIDED_ROLES),
    ("MW-C round 4: an undecided record missing from UNDECIDED_ENTRIES passes",
     [("replace", TESTS, "        if pin is None:\n            problems.append(", "        if pin is None:\n"
       "            continue\n            problems.append(")], UNDECIDED_ROLES),
    ("MW-C round 4: guard 3's structural-copy check honours distinct entries again",
     [("replace", TESTS, "                if shape in shapes:                   # a distinct entry exempts names, "
                         "never a copy\n",
       "                if shape in shapes and (module, name) not in distinct:\n")], DISTINCT_SHAPE),
    # -- MW-C round 4 (N3): a freeze manifest seals only what the SEALED literal pins ---------------------------------
    ("MW-C round 4: a copy under cortex/evaluation/ hidden by a freeze manifest written in the same diff",
     [("copy_body", "greg/business_loop.py", "reconcile", "cortex/evaluation/settle.py", "function"),
      ("seal", "cortex/evaluation/freeze-settle-v0.1.json", "cortex/evaluation/settle.py"),
      ("create", "greg/settle_view.py", "from cortex.evaluation.settle import reconcile_copy\n")], BODIES),
    ("MW-C round 4: any file a freeze manifest hashes is sealed again (the SEALED literal ignored)",
     [("replace", TESTS, "    for relative, pinned in sealed.items():\n",
       "    for relative, pinned in {r: d for r, ds in digests.items() for d in ds}.items():\n")], SEALS_ONLY),
    ("MW-C round 4: a pinned file skipped although no freeze manifest records its bytes",
     [("replace", TESTS, " and path.is_file() and pinned in digests.get(relative, ()) and (\n",
       " and path.is_file() and (\n")], SEALED),
    ("MW-C round 4: a SEALED entry that seals nothing passes",
     [("replace", TESTS, 'f"change" for relative, digest in sealed.items() if relative not in live]\n',
       'f"change" for relative, digest in sealed.items() if False]\n')], SEALED),
    # -- MW-C round 4 (N4): a qualname names its last binding; the compared bodies are pinned --------------------------
    ("MW-C round 4: @overload stubs before greg.remote.handle, and a copy of its body in tools/",
     [("copy_body", "greg/remote.py", "handle", "tools/serve_copy.py", "function"),
      ("replace", "greg/remote.py", "from __future__ import annotations\n",
       "from __future__ import annotations\nfrom typing import overload\n"),
      ("replace", "greg/remote.py", REMOTE_SIG, "@overload\ndef handle(home, method, path, headers, body): ...\n\n\n"
                                                + REMOTE_SIG)], BODIES),
    ("MW-C round 4: greg.remote.handle's body moved to a helper it delegates to, and a copy of the body in tools/",
     [("copy_body", "greg/remote.py", "handle", "tools/serve_copy.py", "function"),
      ("replace", "greg/remote.py", REMOTE_SIG, "def handle(home, method, path, headers, body, *, now=None):\n"
       "    return _handle(home, method, path, headers, body, now=now)\n\n\n"
       + REMOTE_SIG.replace("def handle(", "def _handle("))], BODIES),
    ("MW-C round 4: a qualname resolves to its first binding again",
     [("replace", TESTS, "            if part in bound_names(statement):\n                node = statement\n",
       "            if part in bound_names(statement) and node is None:\n                node = statement\n")],
     LAST_BINDING),
    ("MW-C round 4: a pinned body that leaves guard 4's comparison passes",
     [("replace", TESTS, "           for m, q in sorted(compared - have)]\n",
       "           for m, q in sorted(compared - have) if False]\n")], COMPARED_PIN),
    ("MW-C round 4: a compared body missing from COMPARED passes",
     [("replace", TESTS, "            for m, q in sorted(have - compared)]\n",
       "            for m, q in sorted(have - compared) if False]\n")], COMPARED_PIN),
    # -- MW-C round 4 (N5): a package beside a module of its name fails; no two runtime files share a module name ------
    ("MW-C round 4: a package greg/business_loop/ beside greg/business_loop.py (Python imports the package)",
     [("copy_body", "greg/business_loop.py", "reconcile", "greg/business_loop/__init__.py", "function")], BODIES),
    ("MW-C round 4: a top-level file greg.business_loop.py, read as module greg.business_loop",
     [("copy_body", "greg/business_loop.py", "reconcile", "greg.business_loop.py", "function")], BODIES),
    ("MW-C round 4: the module file read although a package of its name exists",
     [("replace", TESTS, "    if package.is_file() and plain.is_file():\n        raise AmbiguousModule(",
       "    if False:\n        raise AmbiguousModule("),
      ("replace", TESTS, "    return package if package.is_file() else plain if plain.is_file() else None\n",
       "    return plain if plain.is_file() else package if package.is_file() else None\n")], SHADOW),
    ("MW-C round 4: two runtime files with one module name pass",
     [("replace", TESTS, "for name, files in sorted(names.items()) if len(files) > 1]\n",
       "for name, files in sorted(names.items()) if False]\n")], SHADOW),
    # -- MW-C round 4 (N6, N7): each real file read once; file links followed wherever they point ------------------
    ("MW-C round 4: a real file read at every path the walk lists (no de-duplication)",
     [("replace", TESTS, "        out += kept[:1]\n", "        out += kept\n")], ONCE),
    ("MW-C round 4: a link path preferred to the file's real path",
     [("replace", TESTS, "key=lambda p: (links(p), p.relative_to(root).as_posix()))\n",
       "key=lambda p: (-links(p), p.relative_to(root).as_posix()))\n")], ONCE),
    ("MW-C round 4: guard 3 lists each guarded package on its own again",
     [("replace", TESTS, "    for path in python_files(root, *packages):\n        module, tree = ",
       "    for path in [q for package in packages for q in python_files(root, package)]:\n        module, tree = ")],
     ONCE),
    ("MW-C round 4: file links no longer followed",
     [("replace", TESTS, '        elif entry.name.endswith(".py") and entry.is_file():\n',
       '        elif entry.name.endswith(".py") and entry.is_file(follow_symlinks=False):\n')], ONCE),
    # -- MW-C round 6 (B1): a registered qualname has one binding; its module no star import or computed write ---------
    ("MW-C round 6: a dead-branch decoy of greg.remote.handle after the real def, and a copy of the real body in tools/",
     [("copy_body", "greg/remote.py", "handle", "tools/serve_copy.py", "function"),
      ("append", "greg/remote.py", "\n\nif False:  # never runs\n    def handle(home, method, path, headers, body, *, "
                                   "now=None):\n        rows = [str(home), method, path]\n"
                                   "        for key in sorted(headers or {}):\n            rows.append(key.lower())\n"
                                   "        return 404, {'rows': rows, 'size': len(body)}\n")], ONE_BINDING),
    ("MW-C round 6: an if TYPE_CHECKING: re-def of greg.business_loop.reconcile after the real def",
     [("append", "greg/business_loop.py", "\n\nif TYPE_CHECKING:\n    def reconcile(params, ctx):\n"
                                          "        rows = [dict(r) for r in params.get('rows') or []]\n"
                                          "        return {'rows': rows, 'matched': bool(rows)}\n")], ONE_BINDING),
    ("MW-C round 6: the registered class GoalGravityLoop rebound after its class statement",
     [("append", "egregore/gravity.py", "\n\ndef _runtime(cls):\n    cls.runtime = True\n    return cls\n\n\n"
                                        "GoalGravityLoop = _runtime(GoalGravityLoop)\n")], ONE_BINDING),
    ("MW-C round 6: a star-import accelerator appended to greg/business_loop.py (business/reconcile_native.py)",
     [("create", "business/reconcile_native.py", "def reconcile(params, ctx):\n    return {'matched': True}\n"),
      ("append", "greg/business_loop.py", "\n\ntry:  # the native reader, where it is installed\n"
                                          "    from business.reconcile_native import *  # noqa: F401,F403\n"
                                          "except ImportError:\n    pass\n")], ONE_BINDING),
    ("MW-C round 6: globals().update(vars(module)) in greg/body.py",
     [("append", "greg/body.py", "\n\nimport greg.remote as _remote_names  # noqa: E402\n"
                                 "globals().update(vars(_remote_names))\n")], ONE_BINDING),
    ("MW-C round 6: a second binding of a registered qualname passes",
     [("replace", TESTS, "                if len(lines) > 1:\n", "                if False:\n")], DECOYS),
    ("MW-C round 6: only top-level statements counted (dead branches skipped)",
     [("replace", TESTS, "                hits = [s for s in statements(body) if part in bound_names(s)]\n",
       "                hits = [s for s in body if part in bound_names(s)]\n")], DECOYS),
    ("MW-C round 6: global declarations not counted",
     [("replace", TESTS, "lines = [s.lineno for s in hits] + (declared.get(part, []) if depth == 0 else",
       "lines = [s.lineno for s in hits] + ([] if depth == 0 else")], DECOYS),
    ("MW-C round 6: star imports and computed namespace writes pass",
     [("replace", TESTS, "                for line, what in _computed_namespace_writes(tree)]\n",
       "                for line, what in _computed_namespace_writes(tree) if False]\n")], DECOYS),
    # -- MW-C round 6 (B2): every record is pinned ------------------------------------------------------------------
    ("MW-C round 6: a new CANONICAL record adopts an undecided record's candidate and demotes its rival (X1)",
     [("replace", MAP, INBOX_RECORD_START, ADOPTED_RECORD + INBOX_RECORD_START)], PINS),
    ("MW-C round 6: a record that PINNED does not hold passes",
     [("replace", TESTS, "for rid in sorted(set(records) - set(pinned),", "for rid in sorted(set() - set(pinned),")],
     NEW_RECORD),
    # -- MW-C round 6 (B3): a registered class is compared whole -------------------------------------------------------
    ("MW-C round 6: a verbatim copy of class GoalGravityLoop appended to greg/gravity.py (side B's own module)",
     [("append_class", "egregore/gravity.py", "GoalGravityLoop", "PullLoop", "greg/gravity.py")], BODIES),
    ("MW-C round 6: a verbatim copy of CommercialLoop recorded as a new ALTERNATE of the decided commerce record",
     [("copy_class", "business/commercial_loop.py", "CommercialLoop", "CommerceRunner", "greg/commerce_runner.py"),
      ("replace", MAP, COMMERCIAL_ALTERNATE, "      - module: greg.commerce_runner\n        qualnames: [CommerceRunner]\n"
                                             "        status: ALTERNATE\n        reason: a runner\n"
                                             "        retirement_condition: never\n" + COMMERCIAL_ALTERNATE)], BODIES),
    ("MW-C round 6: registered classes no longer compared",
     [("replace", TESTS, '    """The def or class (round 6, B3) a registered qualname is last bound to, or None."""\n'
                         "    node = binding(module, qualname, root)\n    return node if isinstance(node, DEFS) else None\n",
       '    """The def or class (round 6, B3) a registered qualname is last bound to, or None."""\n'
       "    node = binding(module, qualname, root)\n    return node if isinstance(node, FUNCTIONS) else None\n")],
     CLASS_WHOLE),
    ("MW-C round 6: a class body keyed like a function body (the kind tag dropped)",
     [("replace", TESTS, "    return (size, CLASS_SHAPE + dump) if isinstance(node, ast.ClassDef) else (size, dump)\n",
       "    return (size, dump)\n")], CLASS_WHOLE),
    ("MW-C round 6: classes not listed by the scan",
     [("replace", TESTS, "for name, node in _functions(_parse(path, stamp), DEFS)",
       "for name, node in _functions(_parse(path, stamp))")], CLASS_WHOLE),
    # -- MW-C round 6 (B4): sealed files take part in the module-name rule ----------------------------------------------
    ("MW-C round 6: a package cortex/evaluation/scoring/ beside the sealed scoring.py",
     [("create", "cortex/evaluation/scoring/__init__.py", "def score(x):\n    return 1.0\n")], BODIES),
    ("MW-C round 6: sealed files left out of the module-name rule",
     [("replace", TESTS, "    named = files + [Path(root, relative) for relative in sorted(sealed_files(root, sealed))]\n",
       "    named = files\n")], SEALED_SHADOW),
]


class _Disguise(ast.NodeTransformer):
    """What a copier changes to hide a copy: every variable and argument name, every string and number literal
    (inside an f-string only the names, so the copy still parses)."""

    def __init__(self):
        self.fstring = 0

    def visit_Name(self, node):
        node.id += "_v"
        return node

    def visit_arg(self, node):
        node.arg += "_v"
        return node

    def visit_JoinedStr(self, node):
        self.fstring += 1
        self.generic_visit(node)
        self.fstring -= 1
        return node

    def visit_Constant(self, node):
        if not self.fstring and isinstance(node.value, str):
            node.value += " (copy)"
        elif not self.fstring and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            node.value += 1
        return node


def _copy_body(text: str, name: str, form: str) -> str | None:
    """A disguised copy of the top-level def ``name`` as a function, a method of a class, or a def nested in one."""
    node = next((n for n in ast.parse(text).body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and n.name == name), None)
    if node is None:
        return None
    clone = copy.deepcopy(node)
    clone.name, clone.decorator_list = f"{name}_copy", []
    _Disguise().visit(clone)
    if form == "method":
        clone.args.args.insert(0, ast.arg("self"))
    ast.fix_missing_locations(clone)
    source = ast.unparse(clone)
    if form == "function":
        return source + "\n"
    indented = "".join(f"    {line}\n" for line in source.splitlines())
    return ("class CaseCopy:\n" + indented) if form == "method" else (
        "def outer_copy():\n" + indented + f"    return {name}_copy\n")


def _purge(repo: Path) -> None:
    for cache in repo.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)


def _run(repo: Path, target: str) -> subprocess.CompletedProcess:
    _purge(repo)
    return subprocess.run([sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", target],
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
            missing = [d for d in reversed(path.parents) if not d.exists()]
            for directory in missing:                  # a new package directory is removed again on restore
                directory.mkdir()
                created.append(directory)
            created.append(path)
            path.write_text(args[0])
            continue
        if kind == "copy_def":
            name, new_name, new_relative = args
            target = repo / new_relative
            text = path.read_text()
            node = next((n for n in ast.parse(text).body if isinstance(n, (ast.FunctionDef, ast.ClassDef))
                         and n.name == name), None)
            if node is None or target.exists():
                return _restore(originals, created)
            created.append(target)
            target.write_text(ast.get_source_segment(text, node).replace(f"def {name}(", f"def {new_name}(", 1) + "\n")
            continue
        if kind == "copy_body":
            name, new_relative, form = args
            target = repo / new_relative
            body = _copy_body(path.read_text(), name, form) if path.is_file() else None
            if body is None or target.exists():
                return _restore(originals, created)
            created.append(target)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(body)
            continue
        if kind == "seal":
            # a new freeze manifest at ``relative`` that hashes the current bytes of the file ``args[0]``
            sealed = repo / args[0]
            if path.exists() or not sealed.is_file():
                return _restore(originals, created)
            created.append(path)
            path.write_text(json.dumps({"inputs": {"code": {
                args[0]: "sha256:" + hashlib.sha256(sealed.read_bytes()).hexdigest()}}}))
            continue
        if kind in ("copy_class", "append_class"):
            name, new_name, other = args
            target = repo / other
            text = path.read_text() if path.is_file() else ""
            node = next((n for n in ast.parse(text).body if isinstance(n, ast.ClassDef) and n.name == name), None)
            if node is None or (target.exists() if kind == "copy_class" else not target.is_file()):
                return _restore(originals, created)
            body = ast.get_source_segment(text, node).replace(f"class {name}", f"class {new_name}", 1) + "\n"
            if kind == "copy_class":
                created.append(target)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(body)
            else:
                originals.setdefault(target, target.read_text())
                target.write_text(target.read_text() + "\n\n" + body)
            continue
        if kind == "append_body":
            name, existing, form = args
            target = repo / existing
            body = _copy_body(path.read_text(), name, form) if path.is_file() else None
            if body is None or not target.is_file():
                return _restore(originals, created)
            originals.setdefault(target, target.read_text())
            target.write_text(target.read_text() + "\n\n" + body)
            continue
        if path not in originals:
            originals[path] = path.read_text()
        text = path.read_text()
        if kind == "append":
            path.write_text(text + args[0])
        elif kind == "replace":
            old, new = args
            if text.count(old) != 1:
                return _restore(originals, created)
            path.write_text(text.replace(old, new))
        elif kind == "cut":
            start, end = args
            if text.count(start) != 1:
                return _restore(originals, created)
            at = text.index(start)
            stop = len(text) if end is None else text.find(end, at + len(start))
            if stop < 0:
                return _restore(originals, created)
            path.write_text(text[:at] + text[stop:])
        else:
            raise ValueError(kind)
    return originals, created


def _restore(originals: dict, created: list[Path]) -> None:
    for path, text in originals.items():
        path.write_text(text)
    for path in reversed(created):
        if path.is_dir() and not path.is_symlink():
            path.rmdir()
        else:
            path.unlink(missing_ok=True)
    return None


def main() -> int:
    invalid = 0
    with tempfile.TemporaryDirectory(prefix="canonical-owner-guard-mutants-") as temp:
        repo = Path(temp) / "repo"
        shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
        baseline = _run(repo, TESTS)
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
            run = _run(repo, f"{TESTS}::{test}")
            caught = (run.returncode == 1 and f"FAILED {TESTS}::{test}" in run.stdout
                      and "ERROR collecting" not in run.stdout)
            print("CAUGHT" if caught else "SURVIVED_OR_INVALID", name, flush=True)
            if not caught:
                print(run.stdout[-2000:])
            invalid += not caught
            _restore(*applied)
    print(f"{len(MUTANTS) - invalid}/{len(MUTANTS)} caught")
    return int(bool(invalid))


if __name__ == "__main__":
    raise SystemExit(main())
