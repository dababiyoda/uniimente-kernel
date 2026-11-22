"""One canonical owner per important function (directive 2026-10-28 sections 3, 52 and 76), as a test.

"For every major mechanism identify: CANONICAL IMPLEMENTATION, ALTERNATIVES, SHIMS, EXPERIMENTS, BENCHMARKS,
HISTORICAL IMPLEMENTATIONS, MIGRATION PATH, RETIREMENT CONDITION. Do not allow architectural generations to remain
equally canonical forever. Preserving history does not require preserving active ambiguity." (section 52)

The registry is ``function_owner_records`` in docs/collaboration/ARCHITECTURE-OWNERSHIP-MAP.yaml. Three guards:

1. every module and qualname the registry names exists (read from the source with ``ast``; nothing is imported). A
   dotted qualname resolves, part by part, to the LAST statement that binds it in source order (``binding``), and a
   module to its package before a module file of the same name, both present failing (``module_file``). Since round 6
   every canonical, candidate and alternate qualname has exactly ONE binding at its level, dead branches and
   ``TYPE_CHECKING`` blocks included, and its module no star import and no namespace write with a computed name
   (``binding_problems``), so the statement the guards read is the one Python binds, for ordinary code;
2. no module under greg/ reaches an alternate whose status is RETIRED or HISTORICAL: ``import``, ``from ... import``
   (relative ones too), ``as`` aliases, attribute chains through any of them, names assigned from them,
   ``getattr``/``vars``/``sys.modules`` with a constant name, ``importlib.import_module`` and ``__import__`` (with
   ``name=``/``package=``, relative names, ``fromlist``, and a module name taken from a module-level string table
   such as greg/appraisal.py ``DELIVERING``) and a capability bound with ``_lazy("<module>", "<function>")``
   (greg/capabilities.py). A dynamic import whose module name it cannot resolve fails unless ``ALLOWED_DYNAMIC``
   below says why it is safe;
3. a module-level binding in greg/, foundry/, egregore/, omnimorph/, autonomy/ or governance/ (def, class,
   assignment, for/with/except/match target, walrus, import alias, ``globals()`` key) outside a record's canonical,
   candidate and alternate modules fails when its name matches the record's markers or reuses the exact name of a
   registered implementation (except the record's ``generic_names``), unless a ``distinct`` entry names it; and when
   it is a structural copy of a registered function or class under any name, whatever a ``distinct`` entry says
   (test_guard_3_reports_a_structural_copy_even_where_a_distinct_entry_names_it). Names are a HEURISTIC: a rewritten
   re-implementation under an unmarked, unregistered name, a method inside a class, or code outside those six
   packages passes;
4. (MW-C, 2026-11-21) the body of every canonical, candidate and alternate FUNCTION a record names (a dotted
   qualname may name a method), and since round 6 the whole body of every such CLASS (compared with classes only,
   ``body_shape``), with every name and every constant erased, ``pass`` and no-op constant statements
   dropped, an annotated assignment read as the plain one and every import alias erased (``fingerprint``, from a
   fresh copy) and at least ``MIN_COPY_NODES`` nodes, is compared with every function and method at any depth of every
   runtime file the filesystem lists (``runtime_files``). The bodies compared are exactly ``COMPARED`` (by location,
   not by content)
   (test_the_set_of_compared_registered_bodies_is_pinned). The files are every .py file under the repository root,
   each real file once (``_once``), except tests/, docs/, top-level hidden entries and the ``SEALED`` files whose
   bytes still match the digest pinned there and a cortex/evaluation/freeze-*.json manifest; directory links are
   followed only inside the repository, file links wherever they point. A copy anywhere but the body's own
   registered module and qualname fails, inside its record or outside it, whatever it is called; two registered
   locations with one body fail (``registered_twin_problems``); two runtime files with one module name fail
   (``module_name_problems``); a ``distinct`` entry exempts none (``distinct_copy_problems``: and may not name a
   module that holds one); only a ``BODY_EXEMPTIONS`` entry clears a reviewed false positive. Stated limits, missed:
   a rewrite that changes structure (a statement reordered or added, such as ``_unused = 0``, a body wrapped in
   ``if True:``, split into two functions or with a helper inlined); an attribute or call-keyword rename
   (``row['x']`` to ``row.x``); code outside a def (at module level, in a class body or a ``__main__`` block) and
   code run by ``exec`` of a string; the fork pattern (the owner edited in the same diff that keeps its old body as a
   copy, which then matches nothing registered); the methods of a registered CLASS (not compared: four real
   duplicates already in the tree would fail, see the README); the 3 registered functions below ``MIN_COPY_NODES``
   (acceptance.rank, greg.improvement.attention_close_condition and claim_close_condition); and any function the
   registry does not record. tests/ is never scanned: fixtures may copy a body on purpose.

The registry itself is pinned (``PINNED``, ``UNDECIDED_ENTRIES``, ``FOUNDER_DECISIONS``, ``MUST_FLAG``): removing a
record or an entry, adding a record PINNED does not hold (round 6), adding a second canonical module, adding, removing
or changing any entry of a record that is still NEEDS_FOUNDER_DECISION (candidates, alternates with their status,
distinct entries, every field of each; the record's other fields are not pinned), resolving a founder decision without
a ruling record, or narrowing a record's markers below the names it must catch fails until this file changes in the
same reviewed diff, or, for a founder decision, until a ruling record is cited. ``kept_for_problems`` is a forward guard for section 76: a
HISTORICAL or RETIRED alternate still in the tree names what keeps it (a consumer outside greg/, tests/, docs/,
scripts/ci/ and any conftest.py, or its own record's open decision).

The test reads code and data. It grants, attaches, activates and retires nothing.
"""
from __future__ import annotations

import ast
import copy
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import re
from typing import NamedTuple
import warnings

import yaml

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "docs/collaboration/ARCHITECTURE-OWNERSHIP-MAP.yaml"
GUARDED = ("greg", "foundry", "egregore", "omnimorph", "autonomy", "governance")
OWNER_STATUSES = ("CANONICAL", "NEEDS_FOUNDER_DECISION")
ALTERNATE_STATUSES = ("ALTERNATE", "HISTORICAL", "RESEARCH", "RETIRED")
NOT_IMPORTABLE = ("HISTORICAL", "RETIRED")
# What each alternate status must say: when it leaves (a live alternate) or when it may come back (the rest).
CONDITION = {"ALTERNATE": "retirement_condition", "RESEARCH": "revival_condition",
             "HISTORICAL": "revival_condition", "RETIRED": "revival_condition"}
ROLES = (("canonical", "canonical"), ("candidates", "candidates"), ("alternates", "alternates"), ("distinct", "distinct"))

# -- frozen at this commit (review findings F4, F5, F6, MUH-F1 on 77deac50) --------------------------------------
# Every record and every (module, qualname) it names. Removing one fails: an implementation leaves a record by a
# status change (RETIRED, HISTORICAL), never by deletion. The canonical module set is exact: a second canonical module
# is two owners (section 52) and must be recorded as an ALTERNATE instead. The entries of a record that is still
# NEEDS_FOUNDER_DECISION (every entry of every role, and every field of each entry; not the record's own fields such as
# decision_needed or safe_default) are pinned by UNDECIDED_ENTRIES below. Since round 6 every record must be here: a
# record PINNED does not hold fails (test_a_new_record_fails_until_it_is_pinned). Adding an alternate or a distinct
# entry to a decided record needs no change here; changing this literal is a reviewed change to the guard itself.
PINNED = {
    "OWN-FN-TEMPORARY-TEAMS": {
        "canonical": {"foundry.systems.teams": ("form", "act", "dissolve", "report")},
        "candidates": {},
        "alternates": {"omnimorph.engine": ("OmnimorphEngine", "OrganManifest")},
        "distinct": {"greg.mcp_tools": ("act",)},
    },
    "OWN-FN-COMMERCE-CLOSURE": {
        "canonical": {"greg.business_loop": ("reconcile",), "greg.templates": ("business_case", "business_loop_amount"),
                      "greg.path": ("business_loop_closed",)},
        "candidates": {},
        "alternates": {"greg.venture_rehearsal": ("venture_rehearsal", "plan"),
                       "business.commercial_loop": ("CommercialLoop", "STAGES")},
        "distinct": {"business.commercial_loop": ("ACCEPTED_VERIFICATIONS", "OBSERVED", "CustomerCase",
                                                  "observation_problems"),
                     "foundry.systems.media_company": ("assemble", "reconcile"), "foundry.systems.offers": ("fulfill",),
                     "greg.cognition.settlement": ("reconcile",), "greg.metrics": ("STAGES",),
                     "foundry.systems.promotion": ("STAGES",)},
    },
    "OWN-FN-GOAL-RUNTIME": {
        "canonical": {},
        "candidates": {"greg.goal_gravity": ("tick",), "egregore.gravity": ("GoalGravityLoop",),
                       "egregore.goals": ("GoalRegistry", "GoalSpec"), "greg.gravity": ("select", "step")},
        "alternates": {"egregore.goal_chase": ("GoalChase",)},
        "distinct": {"greg.missions": ("MissionEngine",), "egregore.local_mission": ("run_once",)},
    },
    "OWN-FN-STATUS-EVIDENCE-LADDER": {
        "canonical": {},
        "candidates": {"foundry.completion": ("EVIDENCE_TIERS",), "acceptance": ("STATUSES", "LADDER", "TEST_TIERS", "rank"),
                       "greg.path": ("EVIDENCE_STATUS",)},
        "alternates": {"greg.mission_control": ("REALITY",)},
        "distinct": {"greg.metrics": ("FOUNDER_TIER", "STRUCTURAL_CANDIDATE", "founder_tier"),
                     "egregore.experience": ("TRUST_LEVELS",), "scripts.mind_status": ("LABELS",),
                     "greg.institution": ("SCORING_MODEL",), "evolution.capsule": ("VERIFIER_LEVELS",),
                     "scripts.build_mind_coverage_record": ("STATUSES",), "greg.cognition.genome_library": ("STATUSES",),
                     "egregore.brief_learning": ("rank",),
                     "greg.path": ("STRUCTURALLY_BUILT", "BUILD_OPEN", "NO_PREDICATE", "ACCEPTANCE_STATUS",
                                   "build_status")},
    },
    "OWN-FN-AUTONOMY-LEVELS": {
        "canonical": {},
        # side B: #235's ladder, adopted into #196 at 6fc4b22b. Pinned so that it cannot leave silently, and so that
        # the founder's ruling may make it canonical (a ruling promotes only a pinned candidate).
        "candidates": {"autonomy.levels": ("LEVELS", "AutonomyTuple", "AutonomyAuthority", "PROMOTION_CRITERIA"),
                       "greg.autonomy": ("LEVELS", "EARNED_CEILING", "earned_level", "report", "regress")},
        "alternates": {},
        "distinct": {"greg.missions": ("pre_approved",), "greg.cognition.genomes.forecasting": ("LEVELS",)},
    },
    "OWN-FN-REGRESSION-CLOSING": {
        "canonical": {"greg.improvement": ("_close_regressions", "_reopen_regressions", "founder_revert",
                                           "attention_close_condition", "claim_close_condition")},
        "candidates": {},
        "alternates": {},
        "distinct": {"greg.tribunal": ("critique",), "greg.goal_gravity": ("_reopen",),
                     "autonomy.levels": ("AutonomyAuthority.regress",), "foundry.systems.repair": ("regression_test",),
                     "greg.autonomy": ("regress",)},
    },
    "OWN-FN-ORGAN-EXCHANGE": {
        "canonical": {"greg.organs": ("exchange", "status")},
        "candidates": {},
        "alternates": {"greg.organ_exchange": ("exchange", "status", "verify_delivery")},
        "distinct": {"greg.templates": ("organ_exchange",), "greg.briefs": ("verify_delivery",),
                     "greg.ventures": ("verify_delivery",)},
    },
    "OWN-FN-INBOX-TRANSPORT": {
        "canonical": {"greg.body": ("send_signed",), "greg.remote": ("handle", "make_server")},
        "candidates": {},
        "alternates": {},
        "distinct": {},
    },
}
# The functions the 2026-10-28 program duplicates or proposes to duplicate (critic units MU-H and MW-C).
REQUIRED = frozenset(PINNED)
# Records whose owner is the founder's to decide. One leaves NEEDS_FOUNDER_DECISION only by citing a founder_ruling:
# a decision or intent record in the repository that names the record and is accepted or active.
FOUNDER_DECISIONS = frozenset({"OWN-FN-GOAL-RUNTIME", "OWN-FN-STATUS-EVIDENCE-LADDER", "OWN-FN-AUTONOMY-LEVELS"})
# Round 4 (2026-11-22, N1 and N2): the WHOLE entry set of every NEEDS_FOUNDER_DECISION record, exactly as it stands in
# the registry: canonical, candidates, alternates (status, reason, conditions and kept_for included) and distinct
# entries, every field. While the founder has not ruled, every entry of such a record is part of the question (a
# candidate is a competing owner, a live alternate one more competing implementation, a distinct entry a claim that
# something is not one), so any entry or field added, removed, changed or reordered fails (``undecided_problems``,
# tested by test_an_undecided_record_takes_no_new_or_changed_entry_of_any_role_without_a_pin_change) until this literal
# changes in the same reviewed diff. A record that is NEEDS_FOUNDER_DECISION and absent from it fails too. A ruled
# record (owner_status CANONICAL with its founder_ruling) leaves this pin and is checked by ``pin_problems``.
UNDECIDED_ENTRIES = {
    "OWN-FN-GOAL-RUNTIME": {
        "canonical": [],
        "candidates": [
            {
                "side": "A",
                "module": "greg.goal_gravity",
                "qualnames": ["tick"],
                "evidence": [
                    "Body.tick calls goal_gravity.tick before the mission engine on every tick (greg/body.py)",
                    "ADR-GOAL-GRAVITY-002 (status proposed) names it 'one canonical persistent operating path'",
                ],
            },
            {
                "side": "A",
                "module": "egregore.gravity",
                "qualnames": ["GoalGravityLoop"],
                "evidence": [
                    "greg/goal_gravity.py runs GoalGravityLoop.turn in body mode (no gate, executor or grant)",
                    ("its standalone gate and executor mode stays for non-body ledgers; ADR-GOAL-GRAVITY-002 graft "
                     "9 keeps both lineages"),
                ],
            },
            {
                "side": "A",
                "module": "egregore.goals",
                "qualnames": ["GoalRegistry", "GoalSpec"],
                "evidence": [
                    ("the goal store side A runs on: greg/goal_gravity.py imports GoalRegistry and GoalSpec, and "
                     "greg/cli.py _goal_id resolves a goal-id prefix through GoalRegistry"),
                ],
            },
            {
                "side": "B",
                "module": "greg.gravity",
                "qualnames": ["select", "step"],
                "evidence": [
                    ("Body._gravity_order is the mission engine's selector: gravity.select orders the signed "
                     "missions every tick and records gravity.ranked (#178)"),
                    "`greg gravity --situation` runs gravity.step, a one-turn read-only analysis (#158)",
                    ("select's docstring reserves for a founder ruling (ADR-GOAL-GRAVITY-001) the choice between "
                     "this path and egregore.GoalGravityLoop"),
                ],
            },
        ],
        "alternates": [
            {
                "module": "egregore.goal_chase",
                "qualnames": ["GoalChase"],
                "status": "RESEARCH",
                "reason": ("the Infinite Goal Chase engine (#93/#97/#109): a sandbox-only composition over the "
                           "Kernel spine, gate and causal memory, run from egregore/goal_chase_sandbox.py and "
                           "goal_chase_host.py. No module under greg/ imports it. "
                           'docs/collaboration/GREG-BODY-DECISION-2026-09-25.md: "GoalChase retained as sealed '
                           'experiment/benchmark; not unsealed"; goal-gravity-completeness-critique-2026-10-13 '
                           "counts it among four goal/mission engines"),
                "revival_condition": ("the founder unseals it (GREG-BODY-DECISION-2026-09-25), and on the same "
                                      "signed goals it closes a goal the canonical runtime does not, or with fewer "
                                      "founder asks; until then it serves only as a sealed benchmark"),
            },
        ],
        "distinct": [
            {
                "module": "greg.missions",
                "qualnames": ["MissionEngine"],
                "why": ("the mission engine: runs one signed mission's actions. Both candidates order or prepare "
                        "its missions and neither replaces it (GREG-BODY-DECISION-2026-09-25: greg/missions.py is "
                        "the product's goal pursuit)"),
            },
            {
                "module": "egregore.local_mission",
                "qualnames": ["run_once"],
                "why": ("one bounded local repository-audit proof; by its own docstring not a general scheduler or "
                        "goal engine"),
            },
        ],
    },
    "OWN-FN-STATUS-EVIDENCE-LADDER": {
        "canonical": [],
        "candidates": [
            {
                "side": "A",
                "module": "foundry.completion",
                "qualnames": ["EVIDENCE_TIERS"],
                "evidence": [
                    ("audit() refuses a Foundry row whose evidence_tier is not in it; `greg foundry status|run` "
                     "(greg/cli.py) imports the module, but only audit() reads the tuple"),
                ],
            },
            {
                "side": "B",
                "module": "acceptance",
                "qualnames": ["STATUSES", "LADDER", "TEST_TIERS", "rank"],
                "evidence": [
                    ("ranks every requirement, trace link and mission of the full-machine acceptance harness "
                     "(`python -m acceptance`, tests/unit/test_acceptance_harness.py); no module under greg/ "
                     "imports it"),
                    ("the same twelve names as EVIDENCE_TIERS; neither imports the other, and neither is section "
                     "56's seventeen-level list"),
                    ("TEST_TIERS is B's own slice (UNIT_VERIFIED, SANDBOX_VERIFIED, BODY_VERIFIED): the highest "
                     "status any test can establish"),
                ],
            },
            {
                "side": "C",
                "module": "greg.path",
                "qualnames": ["EVIDENCE_STATUS"],
                "evidence": [
                    ("on the mission path: greg/path.py load() validates every greg/path.json node and refuses one "
                     "whose evidence_status is not verified_by_execution, verified_by_inspection, asserted or "
                     "unresolved; the body, the CLI, goal_gravity, gravity and the tribunal read the path through "
                     "it"),
                    ("a four-value vocabulary for the evidence behind each path node's status claim; it shares no "
                     "name with A or B"),
                ],
            },
        ],
        "alternates": [
            {
                "module": "greg.mission_control",
                "qualnames": ["REALITY"],
                "status": "HISTORICAL",
                "reason": ("a six-level reality tuple defined in greg/mission_control.py. No module under greg/ "
                           "reads it (guard 2); acceptance/claims.py imports it (line 80) and crosswalk_problems "
                           "checks that its REALITY_CROSSWALK maps every one of the six labels onto "
                           "acceptance.LADDER, so the reality-claim guard still reads it. Corrected 2026-11-21 "
                           '(MW-C): this said "read by nothing in the repository"'),
                "revival_condition": ("only if the founder picks these six levels as the ladder; otherwise Mission "
                                      "Control imports whichever tuple the decision above makes canonical"),
                "kept_for": {"consumer": 'acceptance.claims.crosswalk_problems'},
            },
        ],
        "distinct": [
            {
                "module": "greg.metrics",
                "qualnames": ["FOUNDER_TIER", "STRUCTURAL_CANDIDATE", "founder_tier"],
                "why": ("the per-closure tier that decides whether a closure moves greg path (greg/path.py "
                        "_at_founder_tier); a different question from a claim's evidence level"),
            },
            {
                "module": "egregore.experience",
                "qualnames": ["TRUST_LEVELS"],
                "why": "the trust of an incoming signal",
            },
            {
                "module": "scripts.mind_status",
                "qualnames": ["LABELS"],
                "why": "the support label of one cognition mechanism",
            },
            {
                "module": "greg.institution",
                "qualnames": ["SCORING_MODEL"],
                "why": "a leverage prior that reads reality strings: a consumer, not a ladder",
            },
            {
                "module": "evolution.capsule",
                "qualnames": ["VERIFIER_LEVELS"],
                "why": ("ranks who or what verified an evolution capsule (formal proof down to intrinsic "
                        "confidence): the verifier's strength, not how far a claim reached in reality"),
            },
            {
                "module": "scripts.build_mind_coverage_record",
                "qualnames": ["STATUSES"],
                "why": ("the build stage of one cognition mechanism in the mind coverage record (absent to "
                        "exercised), the same kind of label as scripts/mind_status.py LABELS; whether section 56 "
                        "absorbs it is part of the decision above"),
            },
            {
                "module": "greg.cognition.genome_library",
                "qualnames": ["STATUSES"],
                "why": ("a genome's role in the library (default for a geometry, niche, experimental, "
                        "superseded...), not a claim's evidence"),
            },
            {
                "module": "egregore.brief_learning",
                "qualnames": ["rank"],
                "why": "orders brief findings by kind",
            },
            {
                "module": "greg.path",
                "qualnames": ["STRUCTURALLY_BUILT", "BUILD_OPEN", "NO_PREDICATE", "ACCEPTANCE_STATUS", "build_status"],
                "why": ("#236's build frontier, adopted into #196 at 2161dbe2: whether a path node's ledger "
                        "predicate is structurally met on this ledger, and what its founder acceptance waits for; a "
                        "node's build state, not a claim's evidence level (EVIDENCE_STATUS, side C, stays the "
                        "path's evidence vocabulary)"),
            },
        ],
    },
    "OWN-FN-AUTONOMY-LEVELS": {
        "canonical": [],
        "candidates": [
            {
                "side": "A",
                "module": "autonomy.levels",
                "qualnames": ["LEVELS", "AutonomyTuple", "AutonomyAuthority", "PROMOTION_CRITERIA"],
                "evidence": [
                    ("the A0-A9 ladder with ten promotion criteria and a named human authorizer; imported by "
                     "closure/kernel_registry.py and tests only, by no module under greg/"),
                ],
            },
            {
                "side": "B",
                "module": "greg.autonomy",
                "qualnames": ["LEVELS", "EARNED_CEILING", "earned_level", "report", "regress"],
                "evidence": [
                    ("#235, adopted into #196 at 6fc4b22b: LEVELS is section 59's five names, SHADOW to "
                     "MANAGE_BY_EXCEPTION; earned_level names SHADOW, RECOMMENDER or SUPERVISED_CANARY "
                     "(EARNED_CEILING) from verified runs since the latest failure, and nothing above it"),
                    ("on the mission path: Body.tick (greg/body.py) calls regress first, which withdraws a standing "
                     "approval when failure evidence names a run it allowed; `greg autonomy` (greg/cli.py) prints "
                     "report, a read-only fold per (capability, action class, target pattern, budget band)"),
                    "imports neither side A nor anything under autonomy/; neither side imports the other",
                ],
            },
        ],
        "alternates": [],
        "distinct": [
            {
                "module": "greg.missions",
                "qualnames": ["pre_approved"],
                "why": ("the mission path's exact-scope pre-approval inside a signed mission: an authority "
                        "envelope, not a level"),
            },
            {
                "module": "greg.cognition.genomes.forecasting",
                "qualnames": ["LEVELS"],
                "why": "forecast quantile levels",
            },
        ],
    },
}
RULING_DIRS = ("docs/decisions/", "docs/intent/")
RULING_STATUS = re.compile(r'(?im)^\W*(status|state)\W*:\W*(accepted|active)\b|"(state|status)"\s*:\s*"(accepted|active|implemented)"')
# Names each record's markers must catch: the shapes the program's open units and PRs use (#235's LEVELS,
# EARNED_CEILING and earned_level; WU-03's form_team; WU-13's REALITY_LADDER; WU-12's close_regression). Narrowing
# the markers below these fails.
MUST_FLAG = {
    "OWN-FN-TEMPORARY-TEAMS": ("TeamError", "form_team", "MAX_TEAM_SIZE", "TemporaryTeam", "dissolve_team",
                               "OmnimorphEngine"),
    "OWN-FN-COMMERCE-CLOSURE": ("business_case", "business_loop_closed", "venture_rehearsal", "CommercialLoop",
                                "commercial_case"),
    "OWN-FN-GOAL-RUNTIME": ("GoalGravityLoop", "GoalRuntime", "GoalChase", "gravity_tick", "goal_runtime", "goal_chase"),
    "OWN-FN-STATUS-EVIDENCE-LADDER": ("REALITY", "REALITY_LADDER", "EVIDENCE_TIERS", "EVIDENCE_LEVELS", "EVIDENCE_STATUS",
                                      "VERIFIER_LEVELS", "RealityLadder", "evidence_levels"),
    "OWN-FN-AUTONOMY-LEVELS": ("LEVELS", "EARNED_CEILING", "earned_level", "AutonomyLadder", "PROMOTION_CRITERIA",
                               "autonomy_level"),
    "OWN-FN-REGRESSION-CLOSING": ("close_regression", "reopen_regressions", "regression_closed", "RegressionLedger"),
    "OWN-FN-ORGAN-EXCHANGE": ("organ_exchange", "OrganExchange", "signed_exchange"),
    "OWN-FN-INBOX-TRANSPORT": ("send_signed", "send_signed_envelope", "drop_to_inbox", "InboxRelay", "inbox_write"),
}
# A registered name may be exempt from the exact-name check only when at least this many other guarded modules
# already define it at module level (report, status); otherwise generic_names would be a way around the guard.
GENERIC_MIN = 3
# The structural copy check compares functions and classes of at least this many AST nodes (smaller ones collide).
MIN_COPY_NODES = 25
# Dynamic imports in greg/ whose module name is not a constant or a module-level string table, by (file, scope).
ALLOWED_DYNAMIC = {
    ("greg/capabilities.py", "_lazy.adapter"):
        "imports the module a _lazy(...) call names; guard 2 follows every _lazy call site instead",
    ("greg/cognition/genomes/library.py", "_import"):
        "imports each name of the module-level tuple MODULES, every one a greg.cognition.genomes module",
    ("greg/cognition/evolution_sandbox.py", "main"):
        "imports the modules a TARGETS row names (greg.cognition.genomes modules and numpy), unpacked from a tuple",
}
FIX = ("If it re-implements that function, add an alternate or shim record for it (status ALTERNATE, HISTORICAL, "
       "RESEARCH or RETIRED, with its retirement or revival condition) to {record} in "
       "docs/collaboration/ARCHITECTURE-OWNERSHIP-MAP.yaml; if it is a different function, add a 'distinct' entry "
       "saying why.")
FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef)
DEFS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
TRY = (ast.Try, getattr(ast, "TryStar", ast.Try))


def load(path: Path = REGISTRY) -> dict:
    return yaml.safe_load(Path(path).read_text())


class AmbiguousModule(ValueError):
    """A module that is both ``<name>.py`` and ``<name>/__init__.py``: Python imports the package, so the module file
    is dead code that a guard must not read as the module."""


def module_file(module: str, root: Path = ROOT) -> Path | None:
    """The file ``import <module>`` loads: the package ``<name>/__init__.py`` first, as Python's FileFinder does, then
    ``<name>.py``. Both present raises AmbiguousModule (round 4, N5;
    test_a_package_shadows_a_module_of_the_same_name_and_no_two_files_share_a_module_name)."""
    base = Path(root, *module.split("."))
    package, plain = base / "__init__.py", base.with_suffix(".py")
    if package.is_file() and plain.is_file():
        raise AmbiguousModule(f"{module} is both {plain.relative_to(root).as_posix()} and "
                              f"{package.relative_to(root).as_posix()}: Python imports the package, so the module file "
                              f"is dead code; remove one of them")
    return package if package.is_file() else plain if plain.is_file() else None


def module_name(path: Path, root: Path = ROOT) -> str:
    """The dotted name a file is read under. Not injective on its own (``a/b.py``, ``a/b/__init__.py`` and a file named
    ``a.b.py`` are all ``a.b``): guard 4 fails on any two runtime files that share one (``module_name_problems``)."""
    relative = Path(path).relative_to(root).with_suffix("")
    return ".".join(relative.parts[:-1] if relative.name == "__init__" else relative.parts)


def module_name_problems(paths: list[Path], root: Path = ROOT) -> list[str]:
    """Every module name two or more of ``paths`` share: guard 4 compares a body with its own location by module
    name, so a second file under the owner's name would count as the owner."""
    names: dict[str, list[str]] = {}
    for path in paths:
        names.setdefault(module_name(path, root), []).append(Path(path).relative_to(root).as_posix())
    return [f"{' and '.join(sorted(files))} are one module name ({name}), so guard 4 cannot tell which is the "
            f"registered module; rename or remove one" for name, files in sorted(names.items()) if len(files) > 1]


# An invalid escape in a string is a SyntaxWarning on Python 3.12 and later and a DeprecationWarning on 3.11 (CI's
# version); tracked scripts that have one still parse, and neither may leak into the test summary.
QUIET = (SyntaxWarning, DeprecationWarning)


@lru_cache(maxsize=None)
def _parse(path: Path, stamp: float) -> ast.Module:
    with warnings.catch_warnings():
        for category in QUIET:
            warnings.simplefilter("ignore", category)
        return ast.parse(path.read_bytes(), str(path))        # bytes: a UTF-8 BOM or a coding line decodes as Python does


def parse(path: Path) -> ast.Module:
    path = Path(path)
    return _parse(path, path.stat().st_mtime_ns)


def _walk(directory: Path, root: Path, skip=lambda path: False, _on_path: frozenset = frozenset()):
    """Every .py file under ``directory``, in name order, at every path it is reachable by (``_once`` keeps one). A
    DIRECTORY symlink is followed only when its target resolves inside ``root`` and is not already on the walk's own
    path (a loop ends there); a directory link that leaves the repository (a venv/ pointing at site-packages) is never
    followed. A FILE symlink ending in .py is listed wherever it points, out of the repository too, so the scan reads
    more, not less (test_the_walk_reads_each_real_file_once_and_follows_file_links_anywhere). ``Path.rglob`` would
    follow a link only at the directory it starts from and never below it, on 3.11 and 3.13 alike: a top-level venv/
    link was walked in full and greg/vendor -> docs/vendor was not. Nothing is skipped by name: a .py file under
    __pycache__/ is importable."""
    inside, real = Path(root).resolve(), Path(directory).resolve()
    if not real.is_relative_to(inside) or real in _on_path:
        return
    on_path = _on_path | {real}
    try:
        with os.scandir(directory) as listing:
            listed = sorted(listing, key=lambda entry: entry.name)
    except OSError:
        return
    for entry in listed:
        path = Path(directory, entry.name)
        if entry.is_dir():
            if not skip(path):
                yield from _walk(path, root, skip, on_path)
        elif entry.name.endswith(".py") and entry.is_file():
            yield path


def _once(paths, root: Path, scanned=lambda path: True) -> list[Path]:
    """Each real file of ``paths`` once (round 4, N6): at its real path when the walk listed it there and
    ``scanned`` keeps it, otherwise at one link path ``scanned`` keeps (the one through the fewest links, then the
    first by name), which is when the target is not read where it lies (docs/, tests/, a sealed file, a package the
    scan does not cover, or outside the repository for a file link). A sibling directory link to scanned code adds
    nothing, so a registered body is never a copy of itself
    (test_the_walk_reads_each_real_file_once_and_follows_file_links_anywhere). A hard link is two files."""
    by_real: dict[Path, list[Path]] = {}
    for path in paths:
        by_real.setdefault(Path(path).resolve(), []).append(Path(path))

    def links(path: Path) -> int:
        parts = path.relative_to(root).parts
        return sum(Path(root, *parts[:i]).is_symlink() for i in range(1, len(parts) + 1))

    out = []
    for listed in by_real.values():
        kept = sorted((p for p in listed if scanned(p)), key=lambda p: (links(p), p.relative_to(root).as_posix()))
        out += kept[:1]
    return sorted(out, key=lambda p: p.relative_to(root).as_posix())


def python_files(root: Path, *packages: str) -> list[Path]:
    """Every .py file under the given packages, each real file once (``_once``): a link from one listed package to
    another is read where it lies, a link to anywhere else at the link path."""
    return _once([path for package in packages for path in _walk(Path(root, package), root)], root)


# -- module-level bindings (guards 1 and 3) ----------------------------------------------------------------------

def _bodies(node) -> list:
    """Blocks that still run at the enclosing level: if, for, while, with, try and match blocks."""
    if isinstance(node, (ast.If, ast.For, ast.AsyncFor, ast.While)):
        return [node.body, node.orelse]
    if isinstance(node, (ast.With, ast.AsyncWith)):
        return [node.body]
    if isinstance(node, TRY):
        return [node.body, *(h.body for h in node.handlers), node.orelse, node.finalbody]
    if isinstance(node, ast.Match):
        return [case.body for case in node.cases]
    return []


def statements(body):
    for node in body:
        yield node
        for block in _bodies(node):
            yield from statements(block)


def _headers(node) -> list:
    """The expressions a statement evaluates at its own level (where a walrus binds a module-level name)."""
    if isinstance(node, DEFS):
        return []
    if isinstance(node, (ast.If, ast.While)):
        return [node.test]
    if isinstance(node, (ast.For, ast.AsyncFor)):
        return [node.iter]
    if isinstance(node, (ast.With, ast.AsyncWith)):
        return [item.context_expr for item in node.items]
    if isinstance(node, ast.Match):
        return [node.subject]
    if isinstance(node, TRY):
        return [h.type for h in node.handlers if h.type is not None]
    return [node]


def _walrus(expressions) -> list[str]:
    out, stack = [], list(expressions)
    while stack:
        node = stack.pop()
        if isinstance(node, ast.NamedExpr) and isinstance(node.target, ast.Name):
            out.append(node.target.id)
        if not isinstance(node, (ast.Lambda, *DEFS)):          # a lambda's or def's walrus binds in its own scope
            stack.extend(ast.iter_child_nodes(node))
    return out


def _is_globals(node) -> bool:
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "globals"


def _globals_keys(node) -> list[str]:
    """Names a statement binds through ``globals()``: ``globals()["X"] = ...``, ``globals().update(X=...)`` or
    ``.update({"X": ...})`` and ``globals().setdefault("X", ...)``."""
    out = []
    targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(
        node, (ast.AnnAssign, ast.AugAssign)) else []
    for target in targets:
        if isinstance(target, ast.Subscript) and _is_globals(target.value) and isinstance(target.slice, ast.Constant):
            out.append(str(target.slice.value))
    call = node.value if isinstance(node, ast.Expr) else None
    if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) and _is_globals(call.func.value):
        if call.func.attr == "update":
            out += [k.arg for k in call.keywords if k.arg]
            out += [str(k.value) for a in call.args if isinstance(a, ast.Dict) for k in a.keys
                    if isinstance(k, ast.Constant)]
        elif call.func.attr == "setdefault" and call.args and isinstance(call.args[0], ast.Constant):
            out.append(str(call.args[0].value))
    return out


def bound_names(node) -> list[str]:
    """Every name one module-level statement binds at that level (not inside the blocks ``_bodies`` yields)."""
    if isinstance(node, DEFS):
        return [node.name]
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return [a.asname or a.name.split(".")[0] for a in node.names if a.name != "*"]
    if isinstance(node, ast.Assign):
        targets = node.targets
    elif isinstance(node, (ast.AnnAssign, ast.AugAssign, ast.For, ast.AsyncFor)):
        targets = [node.target]
    elif isinstance(node, (ast.With, ast.AsyncWith)):
        targets = [item.optional_vars for item in node.items if item.optional_vars is not None]
    else:
        targets = []
    names = [n.id for t in targets for n in ast.walk(t) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)]
    if isinstance(node, TRY):
        names += [h.name for h in node.handlers if h.name]
    if isinstance(node, ast.Match):
        for case in node.cases:
            for p in ast.walk(case.pattern):
                if isinstance(p, (ast.MatchAs, ast.MatchStar)) and p.name:
                    names.append(p.name)
                elif isinstance(p, ast.MatchMapping) and p.rest:
                    names.append(p.rest)
    return names + _walrus(_headers(node)) + _globals_keys(node)


def _resolve(node: ast.ImportFrom, module: str, is_package: bool) -> str:
    if not node.level:
        return node.module or ""
    package = module.split(".") if is_package else module.split(".")[:-1]
    base = package[:len(package) - (node.level - 1)]
    return ".".join(base + ([node.module] if node.module else []))


def definitions(tree: ast.Module, module: str = "", is_package: bool = False) -> dict[str, tuple[int, str | None]]:
    """Every module-level binding -> (first line, the dotted name it imports, or None for a definition)."""
    out: dict[str, tuple[int, str | None]] = {}
    for node in statements(tree.body):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            base = _resolve(node, module, is_package) if isinstance(node, ast.ImportFrom) else ""
            for alias in node.names:
                if alias.name == "*":
                    continue
                if isinstance(node, ast.Import):
                    name, source = alias.asname or alias.name.split(".")[0], alias.name
                else:
                    name, source = alias.asname or alias.name, f"{base}.{alias.name}" if base else alias.name
                out.setdefault(name, (node.lineno, source))
            continue
        for name in bound_names(node):
            if name not in out or out[name][1] is not None:          # a definition outranks an import of the name
                out[name] = (node.lineno, None)
    return out


def binding(module: str, qualname: str, root: Path = ROOT):
    """The statement that binds a dotted qualname: for each part, the LAST statement at that level that binds the
    name in SOURCE order (``statements``, ``bound_names``), descending only through a class. Python keeps the last
    binding that runs, so ``@overload`` stubs before a def, or a def rebound by a later assignment or import, resolve
    to what runs (round 4, N4; test_a_registered_qualname_names_its_last_binding_as_python_does); a later binding in
    a branch that never runs (``if False:``, ``if TYPE_CHECKING:``) does not, which is why a registered qualname must
    have exactly one binding (round 6, ``binding_problems``). None when a part is unbound or a dotted part's parent is
    not a class."""
    path = module_file(module, root)
    if path is None:
        return None
    body, node = parse(path).body, None
    for part in qualname.split("."):
        if node is not None:
            if not isinstance(node, ast.ClassDef):
                return None
            body = node.body
        node = None
        for statement in statements(body):
            if part in bound_names(statement):
                node = statement
        if node is None:
            return None
    return node


def has_qualname(module: str, qualname: str, root: Path = ROOT) -> bool:
    return binding(module, qualname, root) is not None


def definition_node(module: str, name: str, root: Path = ROOT):
    """The def or class a top-level name is last bound to, or None when its last binding is anything else."""
    node = binding(module, name, root)
    return node if isinstance(node, DEFS) else None


def _dotted(node) -> str | None:
    """``A.b.c`` for an attribute chain on a plain name, else None."""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    return ".".join([node.id, *reversed(parts)]) if isinstance(node, ast.Name) else None


def _module_namespace_calls(tree: ast.Module) -> set[int]:
    """The ids of every call that returns the module's namespace: ``globals()`` anywhere, and ``locals()`` or
    ``vars()`` with no argument outside a def, lambda or class body (inside one they are that scope's own)."""
    found: set[int] = set()

    def visit(node, nested: bool):
        for child in ast.iter_child_nodes(node):
            if (isinstance(child, ast.Call) and isinstance(child.func, ast.Name) and not child.args
                    and not child.keywords and (child.func.id == "globals"
                                                or (child.func.id in ("locals", "vars") and not nested))):
                found.add(id(child))
            visit(child, nested or isinstance(child, (*DEFS, ast.Lambda)))
    visit(tree, False)
    return found


def _computed_namespace_writes(tree: ast.Module) -> list[tuple[int, str]]:
    """(line, what) for every star import, and every write to the module namespace (``globals()``, or ``locals()``
    and ``vars()`` at module level) whose names are not literals: ``.update(<not a dict literal of constant keys>)``
    or ``**kwargs``, ``.setdefault(<not a constant>, ...)`` and ``[<not a constant>] = ...``. Literal ones are
    bindings (``_globals_keys``) and count there."""
    namespace = _module_namespace_calls(tree)

    def _namespace_call(node) -> bool:
        return id(node) in namespace

    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and any(alias.name == "*" for alias in node.names):
            out.append((node.lineno, f"from {'.' * node.level}{node.module or ''} import *"))
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and _namespace_call(node.func.value):
            literal = (node.func.attr == "update" and all(k.arg for k in node.keywords) and all(
                isinstance(a, ast.Dict) and all(isinstance(k, ast.Constant) for k in a.keys) for a in node.args)) or (
                node.func.attr == "setdefault" and node.args and isinstance(node.args[0], ast.Constant))
            if node.func.attr in ("update", "setdefault") and not literal:
                out.append((node.lineno, ast.unparse(node)[:80]))
        elif isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            for target in node.targets if isinstance(node, ast.Assign) else [node.target]:
                if (isinstance(target, ast.Subscript) and _namespace_call(target.value)
                        and not isinstance(target.slice, ast.Constant)):
                    out.append((node.lineno, ast.unparse(target)[:80]))
    return sorted(set(out))


def binding_problems(records: list[dict], root: Path = ROOT) -> list[str]:
    """Round 6, B1. Every canonical, candidate and alternate qualname a record names has exactly ONE binding at its
    level in its module: one def or class statement (or, for a constant, one assignment), and no other def, class,
    assignment, import, loop, with, except or match target, walrus, ``globals()`` key, ``global`` declaration or (for
    a dotted part) ``Class.attr = ...`` binding that name, anywhere in the module: dead branches (``if False:``,
    ``if TYPE_CHECKING:``, ``try: ... except ImportError:``) included, because the guards resolve a name statically.
    A module that holds a registered qualname also has no star import and no write to its namespace with a computed
    name (``_computed_namespace_writes``), either of which could replace the registered object at run time while the
    guards read the def. So the def guard 4 fingerprints is the object Python binds, for ordinary code
    (test_every_registered_qualname_has_one_binding_and_its_module_no_computed_binding,
    test_a_decoy_rebinding_or_star_import_of_a_registered_qualname_fails)."""
    out = []
    names: dict[str, set[str]] = {}
    for r in records:
        for role, e in entries(r):
            if role != "distinct":
                names.setdefault(e["module"], set()).update(e.get("qualnames") or [])
    for module in sorted(names):
        path = module_file(module, root)
        if path is None:
            continue                                   # guard 1 (``missing``) reports it
        tree, where = parse(path), path.relative_to(root).as_posix()
        declared: dict[str, list[int]] = {}
        attributes: dict[str, list[int]] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Global):
                for name in node.names:
                    declared.setdefault(name, []).append(node.lineno)
            elif isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
                for target in node.targets if isinstance(node, ast.Assign) else [node.target]:
                    for item in ast.walk(target):
                        dotted = _dotted(item) if isinstance(item, ast.Attribute) else None
                        if dotted:
                            attributes.setdefault(dotted, []).append(node.lineno)
        for qualname in sorted(names[module]):
            body, node, parts = tree.body, None, qualname.split(".")
            for depth, part in enumerate(parts):
                if node is not None:
                    if not isinstance(node, ast.ClassDef):
                        break                          # guard 1 reports a dotted part under a non-class
                    body = node.body
                hits = [s for s in statements(body) if part in bound_names(s)]
                lines = [s.lineno for s in hits] + (declared.get(part, []) if depth == 0 else
                                                    attributes.get(".".join(parts[:depth + 1]), []))
                if len(lines) > 1:
                    out.append(f"{where}: {module}.{'.'.join(parts[:depth + 1])} is bound {len(lines)} times at its "
                               f"level (lines {', '.join(map(str, sorted(lines)))}); a registered qualname has exactly "
                               f"one binding, dead branches, TYPE_CHECKING blocks and rebindings included, so that "
                               f"the def the guards read is the one Python runs. Remove the other bindings, or rename "
                               f"them and record them in the same reviewed diff")
                node = hits[-1] if hits else None
                if node is None:
                    break                              # guard 1 reports a missing name
        out += [f"{where}:{line}: {what} in {module}, which holds registered qualnames "
                f"({', '.join(sorted(names[module]))}); a star import or a namespace write with a computed name can "
                f"replace a registered object at run time while the guards read its def. Import the names "
                f"explicitly, or move it to a module the registry does not name"
                for line, what in _computed_namespace_writes(tree)]
    return out


# -- the registry ------------------------------------------------------------------------------------------------

def entries(record: dict):
    """(role, entry) for every implementation or distinct definition a record names."""
    for role, key in (("canonical", "canonical"), ("candidate", "candidates"), ("alternate", "alternates"),
                      ("distinct", "distinct")):
        for entry in record.get(key) or []:
            yield role, entry


def owned_modules(record: dict) -> set[str]:
    return {e["module"] for role, e in entries(record) if role != "distinct"}


def registered_names(record: dict) -> dict[str, str]:
    """Top-level name -> module, for every canonical, candidate and alternate qualname of a record."""
    out: dict[str, str] = {}
    for role, e in entries(record):
        if role != "distinct":
            for q in e.get("qualnames") or []:
                out.setdefault(q.split(".")[0], e["module"])
    return out


def owner(record: dict) -> str:
    if record["owner_status"] == "CANONICAL":
        return "the canonical owner " + ", ".join(e["module"] for e in record["canonical"])
    return ("not yet decided (NEEDS_FOUNDER_DECISION between " + ", ".join(
        f"{e['side']}: {e['module']}" for e in record["candidates"]) + ")")


def shape_problems(data: dict) -> list[str]:
    problems = []
    records = data.get("function_owner_records") or []
    ids = [r.get("record_id") for r in records]
    concerns = {r["record_id"] for r in data.get("architecture_ownership_records") or []}
    problems += [f"duplicate record {i}" for i in sorted({i for i in ids if ids.count(i) > 1})]
    problems += [f"no record for {i}: the function it names keeps its owner record" for i in sorted(REQUIRED - set(ids))]
    for r in records:
        rid = r.get("record_id")
        for key in ("function", "effect", "owner_status", "markers", "migration_path"):
            if not r.get(key):
                problems.append(f"{rid}: {key} is required")
        problems += [f"{rid}: refines {c}, which is not a concern record" for c in r.get("refines") or []
                     if c not in concerns]
        status = r.get("owner_status")
        if status not in OWNER_STATUSES:
            problems.append(f"{rid}: owner_status {status!r} is not one of {OWNER_STATUSES}")
        elif status == "CANONICAL":
            if not r.get("canonical") or r.get("candidates") or not r.get("evidence"):
                problems.append(f"{rid}: a CANONICAL record names its canonical modules and evidence and no candidates")
        else:
            if r.get("canonical") or len(r.get("candidates") or []) < 1:
                problems.append(f"{rid}: NEEDS_FOUNDER_DECISION names candidates and no canonical module")
            for key in ("decision_needed", "safe_default", "review_trigger"):
                if not r.get(key):
                    problems.append(f"{rid}: NEEDS_FOUNDER_DECISION states its {key}")
            problems += [f"{rid}: candidate {c.get('module')} has no evidence or side" for c in r.get("candidates") or []
                         if not c.get("evidence") or not c.get("side")]
        if not isinstance(r.get("generic_names") or [], list):
            problems.append(f"{rid}: generic_names is a list of names")
        for role, e in entries(r):
            if not e.get("module"):
                problems.append(f"{rid}: a {role} entry has no module")
            if role != "alternate" and not e.get("qualnames"):
                problems.append(f"{rid}: {role} {e.get('module')} names no qualname")
            if role == "distinct" and not e.get("why"):
                problems.append(f"{rid}: distinct {e.get('module')} must say why it is a different function")
            if role == "alternate":
                alt = e.get("status")
                if alt not in ALTERNATE_STATUSES:
                    problems.append(f"{rid}: alternate {e.get('module')} status {alt!r} is not one of {ALTERNATE_STATUSES}")
                elif not str(e.get(CONDITION[alt]) or "").strip():
                    problems.append(f"{rid}: {alt} alternate {e.get('module')} needs a {CONDITION[alt]}")
                if not e.get("reason"):
                    problems.append(f"{rid}: alternate {e.get('module')} needs a reason")
        overlap = {e["module"] for role, e in entries(r) if role in ("canonical", "candidate")} & {
            e["module"] for role, e in entries(r) if role == "alternate"}
        problems += [f"{rid}: {m} is both an owner and an alternate" for m in sorted(overlap)]
        for marker in r.get("markers") or []:
            try:
                re.compile(marker)
            except re.error as exc:
                problems.append(f"{rid}: marker {marker!r} does not compile: {exc}")
    return problems


def ruling_problems(record: dict, root: Path = ROOT) -> list[str]:
    """A founder decision is resolved only by a ruling record in the repository that names it and is in force."""
    rid, ref = record.get("record_id"), str(record.get("founder_ruling") or "")
    if not ref:
        return [f"{rid}: is a founder decision and left NEEDS_FOUNDER_DECISION without a founder_ruling (the accepted "
                f"decision or active intent record, under {' or '.join(RULING_DIRS)}, that rules on {rid})"]
    path = Path(root, ref)
    if not ref.startswith(RULING_DIRS) or ".." in Path(ref).parts or not path.is_file():
        return [f"{rid}: founder_ruling {ref} is not a decision or intent record under {' or '.join(RULING_DIRS)}"]
    text = path.read_text(errors="replace")
    if rid not in text:
        return [f"{rid}: founder_ruling {ref} does not name {rid}"]
    if not RULING_STATUS.search(text):
        return [f"{rid}: founder_ruling {ref} is not accepted or active"]
    return []


def _have(record: dict, key: str) -> dict[str, set[str] | None]:
    """module -> qualnames for one role (None: an alternate that names its whole module)."""
    out: dict[str, set[str] | None] = {}
    for e in record.get(key) or []:
        names = e.get("qualnames") or []
        if key == "alternates" and not names:
            out[e["module"]] = None
        elif out.get(e["module"], set()) is not None:
            out[e["module"]] = out.get(e["module"], set()) | set(names)
    return out


def pin_problems(data: dict, root: Path = ROOT, pinned: dict = PINNED,
                 founder_decisions: frozenset = FOUNDER_DECISIONS, undecided: dict = UNDECIDED_ENTRIES) -> list[str]:
    records = {r.get("record_id"): r for r in data.get("function_owner_records") or []}
    # Round 6, B2: every record is pinned. A record that is not in PINNED (a new CANONICAL record naming an undecided
    # record's candidate as its owner and the rival as its ALTERNATE, say) fails until PINNED changes in the same
    # reviewed diff (test_a_new_record_fails_until_it_is_pinned).
    problems = [f"{rid}: the record is not pinned in tests/unit/test_canonical_owner_guard.py (PINNED); a record joins "
                f"the registry only in a reviewed change that adds it to PINNED, so that no record can name another's "
                f"implementation as its owner or alternate unseen" for rid in sorted(set(records) - set(pinned),
                                                                                         key=str)]
    for rid, pin in pinned.items():
        r = records.get(rid)
        if r is None:
            problems.append(f"{rid}: the record is pinned in tests/unit/test_canonical_owner_guard.py and was removed; "
                            f"a record leaves the registry only in a reviewed change to the pin")
            continue
        have = {role: _have(r, key) for role, key in ROLES}
        decision = rid in founder_decisions
        ruled = decision and r.get("owner_status") != "NEEDS_FOUNDER_DECISION"
        if ruled:
            problems += ruling_problems(r, root)
            if not set(have["canonical"]) <= set(pin["candidates"]):
                problems.append(f"{rid}: a founder ruling makes canonical only a module that was a candidate, not "
                                f"{sorted(set(have['canonical']) - set(pin['candidates']))}")
        elif set(have["canonical"]) != set(pin["canonical"]):
            problems.append(f"{rid}: canonical modules {sorted(have['canonical'])} differ from the pinned "
                            f"{sorted(pin['canonical'])}. A second canonical module makes two owners (section 52): "
                            f"record it as an ALTERNATE with its retirement condition"
                            + (", or cite the founder's ruling" if decision else "")
                            + "; a canonical module leaves only in a reviewed change to the pin")
        for role, modules in pin.items():
            for module, names in modules.items():
                where = [have[role]] + ([have["canonical"], have["alternates"]] if ruled and role == "candidates" else [])
                for name in names:
                    if not any(module in h and (h[module] is None or name in h[module]) for h in where):
                        problems.append(f"{rid}: {role} {module}.{name} is pinned and was removed; an implementation "
                                        f"leaves the record by a status change (RETIRED, HISTORICAL), not by deletion")
    return problems + undecided_problems(data, undecided)


UNDECIDED_KEYS = ("canonical", "candidates", "alternates", "distinct")
ENTRY_WORD = {"canonical": "canonical entry", "candidates": "candidate", "alternates": "alternate",
              "distinct": "distinct entry"}


def _label(entry) -> str:
    names = entry.get("qualnames") or []
    return (f"{entry.get('module')} " + (f"[{', '.join(map(str, names))}]" if names else "(whole module)")
            + (f" {entry['status']}" if entry.get("status") else ""))


def undecided_problems(data: dict, undecided: dict = UNDECIDED_ENTRIES) -> list[str]:
    """Every NEEDS_FOUNDER_DECISION record's canonical, candidate, alternate and distinct entries equal its
    UNDECIDED_ENTRIES literal, field for field and in order; a record that is undecided and not in it fails."""
    problems = []
    for r in data.get("function_owner_records") or []:
        if r.get("owner_status") != "NEEDS_FOUNDER_DECISION":
            continue
        rid, pin = r.get("record_id"), undecided.get(r.get("record_id"))
        if pin is None:
            problems.append(f"{rid}: is NEEDS_FOUNDER_DECISION and its entries are not pinned: add its canonical, "
                            f"candidate, alternate and distinct entries, as they stand, to UNDECIDED_ENTRIES in "
                            f"tests/unit/test_canonical_owner_guard.py in the same reviewed diff")
            continue
        for key in UNDECIDED_KEYS:
            have, want = list(r.get(key) or []), list(pin.get(key) or [])
            if have == want:
                continue
            added, gone = [e for e in have if e not in want], [e for e in want if e not in have]
            problems += [f"{rid}: {ENTRY_WORD[key]} {_label(e)} is not pinned as it stands. Until the founder rules, "
                         f"every entry of a NEEDS_FOUNDER_DECISION record (a competing owner, a competing "
                         f"implementation, or a claim that something is not one) changes only in a reviewed change "
                         f"to UNDECIDED_ENTRIES in tests/unit/test_canonical_owner_guard.py, never by a registry "
                         f"edit alone" for e in added]
            problems += [f"{rid}: pinned {ENTRY_WORD[key]} {_label(e)} is not in the registry as pinned (removed or "
                         f"changed); change UNDECIDED_ENTRIES in the same reviewed diff" for e in gone]
            if not added and not gone:
                problems.append(f"{rid}: its {key} entries are reordered or repeated against UNDECIDED_ENTRIES")
    return problems


def _guarded_index(root: Path, packages=GUARDED) -> dict[str, set[str]]:
    """Module-level name -> the guarded modules that define it (imports excluded)."""
    index: dict[str, set[str]] = {}
    for path in python_files(root, *packages):
        module = module_name(path, root)
        for name, (_, source) in definitions(parse(path), module, path.name == "__init__.py").items():
            if source is None:
                index.setdefault(name, set()).add(module)
    return index


def marker_problems(records: list[dict], root: Path = ROOT, must_flag: dict = MUST_FLAG) -> list[str]:
    by_id = {r["record_id"]: r for r in records}
    problems = []
    for rid, names in must_flag.items():
        r = by_id.get(rid)
        if r is None:
            continue
        patterns = [re.compile(m) for m in r.get("markers") or []]
        problems += [f"{rid}: no marker matches {name!r}, a name this record must catch (MUST_FLAG)"
                     for name in names if not any(p.fullmatch(name) for p in patterns)]
    index = _guarded_index(root) if any(r.get("generic_names") for r in records) else {}
    for r in records:
        registered, owned = registered_names(r), owned_modules(r)
        for name in r.get("generic_names") or []:
            if name not in registered:
                problems.append(f"{r['record_id']}: generic name {name!r} is not a registered qualname of the record")
                continue
            others = index.get(name, set()) - owned
            if len(others) < GENERIC_MIN:
                problems.append(f"{r['record_id']}: generic name {name!r} is defined in only {len(others)} other guarded "
                                f"modules (fewer than {GENERIC_MIN}); check it by name and record those as distinct")
    return problems


def missing(records: list[dict], root: Path = ROOT) -> list[str]:
    out = []
    for r in records:
        for role, e in entries(r):
            if module_file(e["module"], root) is None:
                out.append(f"{r['record_id']}: {role} module {e['module']} does not exist (moved or renamed? "
                           f"update the record)")
                continue
            out += [f"{r['record_id']}: {role} {e['module']}.{q} does not exist (stale qualname: update the record)"
                    for q in e.get("qualnames") or [] if not has_qualname(e["module"], q, root)]
    return out


# -- guard 2: what a greg module reaches -------------------------------------------------------------------------

DYNAMIC = ("import_module", "__import__")


def _call_name(func) -> str:
    return func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else ""


def _arg(call: ast.Call, index: int, keyword: str):
    if len(call.args) > index:
        return call.args[index]
    return next((k.value for k in call.keywords if k.arg == keyword), None)


def _str(node) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _scopes(tree: ast.Module) -> list[tuple[int, int, str]]:
    out = []

    def visit(node, prefix):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, DEFS):
                name = f"{prefix}.{child.name}" if prefix else child.name
                out.append((child.lineno, child.end_lineno or child.lineno, name))
                visit(child, name)
            else:
                visit(child, prefix)
    visit(tree, "")
    return out


class Reach:
    """Every dotted name one file imports or reaches through an imported name, statically, with its line.

    Names bound from a module expression (``m = importlib.import_module("x")``, ``o = greg.old``) are followed per
    file, not per scope, so a name rebound to something unrelated elsewhere in the file can be a false positive. The
    reviewed resolver for the same forms is greg/cognition/code_binding.py ``_dynamic_module``; it returns file paths
    through a tree reader and is private, so this follows its rules instead of importing it."""

    def __init__(self, tree: ast.Module, module: str, is_package: bool):
        self.tree, self.module, self.is_package = tree, module, is_package
        self.package = module if is_package else module.rpartition(".")[0]
        self.tables = self._tables(tree)
        self.bound: dict[str, set[str]] = {}
        self.unresolved: dict[tuple[int, int], int] = {}
        self.refs: list[tuple[int, str]] = []
        self._bind()
        self._collect()

    @staticmethod
    def _tables(tree) -> dict[str, tuple[list[str], dict]]:
        """Module-level names bound to a string, or to a dict, tuple, list or set literal of strings."""
        out = {}
        for node in statements(tree.body):
            if not (isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)):
                continue
            value = node.value
            if _str(value) is not None:
                out[node.targets[0].id] = ([value.value], {})
            elif isinstance(value, ast.Dict) and value.values and all(_str(v) is not None for v in value.values):
                out[node.targets[0].id] = ([v.value for v in value.values],
                                           {k.value: v.value for k, v in zip(value.keys, value.values)
                                            if isinstance(k, ast.Constant)})
            elif isinstance(value, (ast.Tuple, ast.List, ast.Set)) and value.elts and all(
                    _str(v) is not None for v in value.elts):
                out[node.targets[0].id] = ([v.value for v in value.elts], {})
        return out

    def names(self, node) -> set[str] | None:
        """The strings a module-name argument can be; None when it is not a constant or a module-level table."""
        if node is None:
            return None
        if _str(node) is not None:
            return {node.value}
        if isinstance(node, ast.Name) and node.id in self.tables:
            return set(self.tables[node.id][0])
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id in self.tables:
            values, keyed = self.tables[node.value.id]
            key = node.slice.value if isinstance(node.slice, ast.Constant) else object()
            return {keyed[key]} if key in keyed else set(values)
        return None

    def absolute(self, name: str, package: str | None = None) -> str:
        if not name.startswith("."):
            return name
        level = len(name) - len(name.lstrip("."))
        base = (package or self.package).split(".")
        base = base[:len(base) - (level - 1)]
        rest = name[level:]
        return ".".join([*base, rest] if rest else base)

    def imported(self, call: ast.Call) -> tuple[set[str], set[str]] | None:
        """(modules a dynamic import loads, what the call evaluates to); None when the call is not one."""
        kind = _call_name(call.func)
        if kind not in DYNAMIC:
            return None
        names = self.names(_arg(call, 0, "name"))
        if names is None:
            self.unresolved.setdefault((call.lineno, call.col_offset), call.lineno)
            return set(), set()
        if kind == "import_module":
            package = _arg(call, 1, "package")
            packages = self.names(package) if package is not None else {None}
            loaded = {self.absolute(n, p) for n in names for p in (packages or {None})}
            return loaded, loaded
        level = _arg(call, 4, "level")
        depth = level.value if isinstance(level, ast.Constant) and isinstance(level.value, int) else 0
        loaded = {self.absolute("." * depth + n) if depth else n for n in names}
        fromlist = _arg(call, 3, "fromlist")
        named = fromlist is not None and not (isinstance(fromlist, (ast.List, ast.Tuple)) and not fromlist.elts) and not (
            isinstance(fromlist, ast.Constant) and not fromlist.value)
        return loaded, loaded if named else {m.split(".")[0] for m in loaded}   # no fromlist: the top package

    def targets(self, node) -> set[str]:
        """The dotted names an expression can evaluate to (a module, or a name in one); empty when unknown.
        ``module.*`` stands for a name the code computes at run time."""
        if isinstance(node, ast.Name):
            return set(self.bound.get(node.id, ()))
        if isinstance(node, ast.Attribute):
            return {f"{t}.{node.attr}" for t in self.targets(node.value)}
        if isinstance(node, ast.Call):
            got = self.imported(node)
            if got is not None:
                return got[1]
            if isinstance(node.func, ast.Name) and node.func.id == "getattr" and len(node.args) >= 2:
                attr = _str(node.args[1])
                return {f"{t}.{attr or '*'}" for t in self.targets(node.args[0])}
            return set()
        if isinstance(node, ast.Subscript):
            key, value = _str(node.slice), node.value
            if isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id == "vars" and value.args:
                return {f"{t}.{key or '*'}" for t in self.targets(value.args[0])}
            if isinstance(value, ast.Attribute) and value.attr == "__dict__":
                return {f"{t}.{key or '*'}" for t in self.targets(value.value)}
            if key and "sys.modules" in self.targets(value):
                return {key}
        return set()

    def _bind(self):
        assigns = []
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.asname or alias.name.split(".")[0]
                    self.bound.setdefault(name, set()).add(alias.name if alias.asname else name)
            elif isinstance(node, ast.ImportFrom):
                source = _resolve(node, self.module, self.is_package)
                for alias in node.names:
                    if alias.name != "*":
                        self.bound.setdefault(alias.asname or alias.name, set()).add(
                            f"{source}.{alias.name}" if source else alias.name)
            elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.NamedExpr)) and node.value is not None:
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                names = [t.id for t in targets if isinstance(t, ast.Name)]
                if names:
                    assigns.append((names, node.value))
        for _ in range(8):                                   # follow chains of assignments to a fixed point
            changed = False
            for names, value in assigns:
                found = self.targets(value)
                for name in names:
                    if found - self.bound.get(name, set()):
                        self.bound.setdefault(name, set()).update(found)
                        changed = True
            if not changed:
                break

    def _collect(self):
        refs = self.refs
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                refs += [(node.lineno, alias.name) for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                source = _resolve(node, self.module, self.is_package)
                refs += [(node.lineno, f"{source}.{alias.name}" if source else alias.name) for alias in node.names]
            elif isinstance(node, ast.Call):
                got = self.imported(node)
                if got is not None:
                    refs += [(node.lineno, name) for name in got[0] | got[1]]
                elif _call_name(node.func) == "_lazy":
                    # greg/capabilities.py binds a capability to "<module>", "<function>" and imports it on first call
                    attr = _str(_arg(node, 1, "name"))
                    refs += [(node.lineno, f"{m}.{attr or '*'}") for m in self.names(_arg(node, 0, "module")) or ()]
                else:
                    refs += [(node.lineno, name) for name in self.targets(node)]
            elif isinstance(node, (ast.Attribute, ast.Subscript)):
                refs += [(node.lineno, name) for name in self.targets(node)]

    def unresolved_scopes(self) -> list[tuple[int, str]]:
        scopes = _scopes(self.tree)
        out = []
        for line in sorted(set(self.unresolved.values())):
            inside = [s for s in scopes if s[0] <= line <= s[1]]
            out.append((line, max(inside)[2] if inside else ""))
        return out


def reach(path: Path, root: Path = ROOT) -> Reach:
    return Reach(parse(path), module_name(path, root), path.name == "__init__.py")


def _hits(reference: str, module: str, qualnames: list[str]) -> bool:
    if not qualnames:
        return reference == module or reference.startswith(module + ".")
    if reference == module + ".*":
        return True
    return any(reference == f"{module}.{q.split('.')[0]}" or reference.startswith(f"{module}.{q.split('.')[0]}.")
               for q in qualnames)


def retired_imports(records: list[dict], root: Path = ROOT, package: str = "greg") -> list[str]:
    banned = [(r["record_id"], e) for r in records for e in r.get("alternates") or []
              if e.get("status") in NOT_IMPORTABLE]
    out = []
    for path in python_files(root, package):
        module = module_name(path, root)
        refs = reach(path, root).refs
        for rid, e in banned:
            if module == e["module"]:
                continue
            for line, ref in refs:
                if _hits(ref, e["module"], e.get("qualnames") or []):
                    what = e["module"] + (f" ({', '.join(e['qualnames'])})" if e.get("qualnames") else "")
                    out.append(f"{path.relative_to(root)}:{line} reaches {ref}, a {e['status']} alternate of "
                               f"{rid} ({what}); import the record's owner instead, or revive the alternate in "
                               f"the record first (its revival condition: {e.get('revival_condition')})")
    return sorted(set(out))


def unresolved_imports(root: Path = ROOT, package: str = "greg", allowed: dict = ALLOWED_DYNAMIC) -> list[str]:
    out, seen = [], set()
    for path in python_files(root, package):
        relative = str(path.relative_to(root))
        for line, scope in reach(path, root).unresolved_scopes():
            seen.add((relative, scope))
            if (relative, scope) not in allowed:
                out.append(f"{relative}:{line} ({scope or 'module level'}) imports a module whose name guard 2 cannot "
                           f"resolve, so it cannot tell whether a retired or historical alternate is reached; use a "
                           f"constant or a module-level table of names, or add ({relative!r}, {scope!r}) to "
                           f"ALLOWED_DYNAMIC with the reason it is safe")
    out += [f"ALLOWED_DYNAMIC {key} no longer matches an unresolved import: remove it" for key in allowed
            if key not in seen and Path(root, key[0]).is_relative_to(Path(root, package))]
    return out


# -- guard 3: unrecorded re-implementations ----------------------------------------------------------------------

def _shape(node) -> tuple[int, str]:
    """(node count, AST dump) of a def or class with its own name and docstring removed."""
    clone = copy.deepcopy(node)
    clone.name = "_"
    first = clone.body[0] if clone.body else None
    if isinstance(first, ast.Expr) and _str(first.value) is not None:
        clone.body = clone.body[1:] or [ast.Pass()]
    return sum(1 for _ in ast.walk(clone)), ast.dump(clone, include_attributes=False)


def origin(dotted: str, root: Path = ROOT, depth: int = 4) -> str:
    """Where an imported name is defined, following re-exports (``from .engine import X`` in a package)."""
    for _ in range(depth):
        module, _, name = dotted.rpartition(".")
        path = module_file(module, root) if module else None
        if path is None:
            break
        source = definitions(parse(path), module, path.name == "__init__.py").get(name, (0, None))[1]
        if source is None:
            break
        dotted = source
    return dotted


def unrecorded(records: list[dict], root: Path = ROOT, packages=GUARDED) -> list[str]:
    compiled = []
    for r in records:
        exact = {n: m for n, m in registered_names(r).items() if n not in set(r.get("generic_names") or [])}
        shapes = {}
        for name, module in registered_names(r).items():
            node = definition_node(module, name, root)
            if node is not None:
                size, dump = _shape(node)
                if size >= MIN_COPY_NODES:
                    shapes.setdefault((size, dump), f"{module}.{name}")
        compiled.append((r, [re.compile(m) for m in r["markers"]], owned_modules(r),
                         {(e["module"], q) for role, e in entries(r) if role == "distinct" for q in e["qualnames"]},
                         exact, shapes))
    sizes = {size for *_, shapes in compiled for size, _ in shapes}
    out = []
    for path in python_files(root, *packages):
        module, tree = module_name(path, root), parse(path)
        here = definitions(tree, module, path.name == "__init__.py")
        copies = {}
        for node in statements(tree.body):
            if isinstance(node, DEFS):
                raw = sum(1 for _ in ast.walk(node))          # a docstring adds two nodes to a shape's size
                if any(size <= raw <= size + 2 for size in sizes):
                    copies[node.name] = (node.lineno, _shape(node))
        for r, patterns, modules, distinct, exact, shapes in compiled:
            if module in modules:
                continue
            for name, (line, source) in here.items():
                if (module, name) in distinct:
                    continue
                if source is not None:
                    source = origin(source, root)
                    if (source.rpartition(".")[0] in modules or source in modules
                            or tuple(source.rsplit(".", 1)) in distinct):
                        continue                      # importing the owner's (or a distinct) name is a use
                marker = next((p.pattern for p in patterns if p.fullmatch(name)), None)
                if marker is not None:
                    why = f"matches the marker {marker!r} of {r['record_id']}"
                elif name in exact:
                    why = f"reuses the name of {exact[name]}.{name}, registered in {r['record_id']}"
                else:
                    continue
                out.append(f"{path.relative_to(root)}:{line} defines {name!r}, which {why} ({r['function']}); "
                           f"its owner is {owner(r)}. " + FIX.format(record=r["record_id"]))
            for name, (line, shape) in copies.items():
                if shape in shapes:                   # a distinct entry exempts names, never a copy
                    out.append(f"{path.relative_to(root)}:{line} defines {name!r}, a structural copy of "
                               f"{shapes[shape]} registered in {r['record_id']} ({r['function']}); its owner is "
                               f"{owner(r)}. " + FIX.format(record=r["record_id"]))
    return sorted(set(out))


# -- guard 4: a registered function's body anywhere in the runtime tree (MW-C, 2026-11-21) --------------------------

# Not runtime code: tests (fixtures may copy a body on purpose) and documents, by full top-level path prefix, never by
# a path segment, so a copy cannot hide in a new directory that shares one of these names. SEALED_UNDER: the only
# other files not scanned are the frozen instruments there (``sealed_files``); every other file under it (new files,
# edited ones, subdirectories) is scanned, because GREG imports from it (cortex.evaluation.closure).
NOT_RUNTIME = ("tests/", "docs/")
SEALED_UNDER = "cortex/evaluation/"
MANIFESTS = "freeze-*.json"
# Round 4 (2026-11-22, N3): the frozen instruments guard 4 skips, by path and the sha256 of the bytes it skips. A file
# is skipped only when it is here, its current bytes hash to this digest and a SEALED_UNDER/freeze-*.json manifest
# records that digest for it: a manifest added in a diff seals nothing, and a file edited after its freeze is scanned
# (test_a_freeze_manifest_seals_only_the_files_and_bytes_the_test_pins). An entry that seals nothing on the tree fails
# (``sealed_problems``, test_no_copy_of_a_registered_function_body_outside_its_record). These are the 9 files the
# manifests sealed on 2026-11-22; sealing another is a reviewed change to this literal.
SEALED = {
    "cortex/evaluation/__init__.py": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "cortex/evaluation/arms.py": "sha256:3142bff2aa8d5f316ea419e42afe5077e365a5c6939885454b3c080d2fbe614f",
    "cortex/evaluation/build_suites.py": "sha256:8115c7feae736c8878e56d4c1879fe7974b06f9a87768973cb57ff6f805b9187",
    "cortex/evaluation/crossgeo_arms.py": "sha256:d06cbf804594c5788ae4c5d154d720c1aa3e219eb293457485e24fdd314e38c8",
    "cortex/evaluation/crossgeo_loss.py": "sha256:c36be46479a16d29a9cc929d2d07a687e9d43db93ff8c8625026e1e94c9d0457",
    "cortex/evaluation/crossgeo_suite.py": "sha256:b5b464a62182d4dded70d9352165334cf1eeb86db2e7329f3c8206981ac85699",
    "cortex/evaluation/generators.py": "sha256:2b302d0d01b8051eae604dec7214726c53fe6bce7deb90d4e55b5cdcc544c362",
    "cortex/evaluation/run.py": "sha256:42460d4f95ab8c86f3be6081ba2fc8555c8a319ceebfa2d02b34bd3e88a82cdc",
    "cortex/evaluation/scoring.py": "sha256:8cbb90aade8d73da67d3c14d673408edaf45cbc65ddf6ebe7a27bea7ed6610d7",
}
ERASED = "_"                     # every name and every constant of a fingerprinted body becomes this one sentinel
# Guard 4's reviewed escape hatch for a false positive: a different function whose erased body happens to equal a
# registered one (small registered bodies have generic shapes). (module, qualname) of the location -> (the registered
# "module.qualname" it resembles, the reason it is a different function). An entry clears exactly that location for
# exactly that body; an entry that no longer matches a copy, or gives no reason, fails. Empty on 2026-11-21; adding one
# is a reviewed change to this file.
BODY_EXEMPTIONS: dict[tuple[str, str], tuple[str, str]] = {}
# Round 4 (2026-11-22, N4): the registered bodies guard 4 compares, by (module, qualname). Exact: one that leaves the
# comparison (its last binding no longer a def or class, a body shrunk below MIN_COPY_NODES, the record no longer
# naming it) or joins it fails until this literal changes in the same reviewed diff (``compared_problems``,
# test_the_set_of_compared_registered_bodies_is_pinned). It pins WHERE the compared bodies are, not what they hold: a
# wrapper of at least MIN_COPY_NODES nodes that calls a new helper holding the old logic stays compared, and the
# helper is not (the fork pattern, a stated limit; round 6, B5). Round 6 (B3): the 9 registered classes, compared
# whole, are the last 9 entries.
COMPARED = frozenset({
    ("foundry.systems.teams", "act"), ("foundry.systems.teams", "dissolve"), ("foundry.systems.teams", "form"),
    ("foundry.systems.teams", "report"), ("greg.autonomy", "earned_level"), ("greg.autonomy", "regress"),
    ("greg.autonomy", "report"), ("greg.body", "send_signed"), ("greg.business_loop", "reconcile"),
    ("greg.goal_gravity", "tick"), ("greg.gravity", "select"), ("greg.gravity", "step"),
    ("greg.improvement", "_close_regressions"), ("greg.improvement", "_reopen_regressions"),
    ("greg.improvement", "founder_revert"), ("greg.organ_exchange", "exchange"), ("greg.organ_exchange", "status"),
    ("greg.organ_exchange", "verify_delivery"), ("greg.organs", "exchange"), ("greg.organs", "status"),
    ("greg.path", "business_loop_closed"), ("greg.remote", "handle"), ("greg.remote", "make_server"),
    ("greg.templates", "business_case"), ("greg.templates", "business_loop_amount"), ("greg.venture_rehearsal", "plan"),
    ("greg.venture_rehearsal", "venture_rehearsal"),
    ("autonomy.levels", "AutonomyAuthority"), ("autonomy.levels", "AutonomyTuple"),
    ("business.commercial_loop", "CommercialLoop"), ("egregore.goal_chase", "GoalChase"),
    ("egregore.goals", "GoalRegistry"), ("egregore.goals", "GoalSpec"), ("egregore.gravity", "GoalGravityLoop"),
    ("omnimorph.engine", "OmnimorphEngine"), ("omnimorph.engine", "OrganManifest"),
})
FIX_COPY = ("Import the owner's function instead and remove the copy. Recording it does not exempt it: a body is "
            "exempt only at its own registered location, a 'distinct' entry exempts nothing, and two registered "
            "locations with one body fail (registered_twin_problems); {record} is in "
            "docs/collaboration/ARCHITECTURE-OWNERSHIP-MAP.yaml.")


def _inert(node) -> bool:
    """A statement the fingerprint drops: ``pass``, a no-op constant (a string, ``...``) and a bare annotation."""
    return (isinstance(node, ast.Pass) or (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant))
            or (isinstance(node, ast.AnnAssign) and node.value is None))


class _Erase(ast.NodeTransformer):
    """Rewrite every name a body binds or reads, and every constant, to ERASED; structure, attribute names, keyword
    names and imported module names stay. Three one-node edits are normalised away and nothing more: ``_inert``
    statements are dropped, an annotated assignment is read as the plain assignment, and every import gets the
    ERASED alias (``import os`` and ``import os as system`` are one statement). It rewrites in place, so
    ``fingerprint`` gives it a fresh copy, and it is idempotent: an erased tree erases to itself."""

    def visit_Pass(self, node):
        return None

    def visit_Expr(self, node):
        return None if _inert(node) else self.generic_visit(node)

    def visit_AnnAssign(self, node):
        if _inert(node):
            return None
        self.generic_visit(node)
        return ast.Assign(targets=[node.target], value=node.value, type_comment=None)

    def visit_Name(self, node):
        node.id = ERASED
        return node

    def visit_arg(self, node):
        node.arg, node.annotation, node.type_comment = ERASED, None, None
        return node

    def visit_Constant(self, node):
        node.value, node.kind = ERASED, None
        return node

    def visit_ExceptHandler(self, node):
        self.generic_visit(node)
        if node.name is not None:
            node.name = ERASED
        return node

    def visit_alias(self, node):
        node.asname = ERASED
        return node

    def visit_FunctionDef(self, node):
        self.generic_visit(node)
        node.name, node.returns, node.type_comment = ERASED, None, None
        return node

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node):
        self.generic_visit(node)
        node.name = ERASED
        return node

    def visit_Global(self, node):
        node.names = [ERASED] * len(node.names)
        return node

    visit_Nonlocal = visit_Global

    def visit_MatchAs(self, node):
        self.generic_visit(node)
        if node.name is not None:
            node.name = ERASED
        return node

    def visit_MatchStar(self, node):
        if node.name is not None:
            node.name = ERASED
        return node

    def visit_MatchMapping(self, node):
        self.generic_visit(node)
        if node.rest is not None:
            node.rest = ERASED
        return node


def _function_body(fn) -> list:
    """A function's statements without its docstring."""
    body = fn.body
    if body and isinstance(body[0], ast.Expr) and _str(body[0].value) is not None:
        body = body[1:]
    return body


_DROPPED = {ast.arg: "annotation", ast.FunctionDef: "returns", ast.AsyncFunctionDef: "returns",
            ast.AnnAssign: "annotation"}


def _erased_size(fn) -> int:
    """The node count ``fingerprint`` reports, read without copying: the body's nodes minus the ``_inert``
    statements and the annotations _Erase drops (an annotated assignment counts as the plain one)."""
    stack, size = list(_function_body(fn)), 0
    while stack:
        node = stack.pop()
        if _inert(node):
            continue
        size += 1
        skip = _DROPPED.get(type(node))
        for field, value in ast.iter_fields(node):
            if field == skip:
                continue
            if isinstance(value, ast.AST):
                stack.append(value)
            elif isinstance(value, list):
                stack.extend(v for v in value if isinstance(v, ast.AST))
    return size


def fingerprint(fn) -> tuple[int, str]:
    """(node count, dump) of a function's body (docstring dropped) with every name and constant erased, taken from a
    fresh deep copy: the cached parse other guards read is never rewritten, and nothing is erased twice."""
    module = _Erase().visit(ast.Module(body=copy.deepcopy(_function_body(fn)), type_ignores=[]))
    return sum(1 for _ in ast.walk(module)) - 1, ast.dump(module)


def sealed_files(root: Path = ROOT, sealed: dict = SEALED) -> frozenset[str]:
    """The ``sealed`` paths (repository-relative, under SEALED_UNDER) whose current bytes hash to the pinned digest
    when a SEALED_UNDER/freeze-*.json manifest (``inputs.code``: path -> "sha256:<hex>") records that digest for the
    path. A manifest that does not parse seals nothing; neither does a manifest for a path or digest not pinned."""
    digests: dict[str, set[str]] = {}
    for manifest in sorted(Path(root, SEALED_UNDER).glob(MANIFESTS)):
        try:
            code = (json.loads(manifest.read_bytes()).get("inputs") or {}).get("code") or {}
        except (OSError, ValueError, AttributeError):
            continue
        for relative, digest in code.items() if isinstance(code, dict) else ():
            if isinstance(relative, str) and isinstance(digest, str):
                digests.setdefault(relative, set()).add(digest)
    out = set()
    for relative, pinned in sealed.items():
        path = Path(root, relative)
        if relative.startswith(SEALED_UNDER) and path.is_file() and pinned in digests.get(relative, ()) and (
                f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}" == pinned):
            out.add(relative)
    return frozenset(out)


def sealed_problems(root: Path = ROOT, sealed: dict = SEALED) -> list[str]:
    """A SEALED entry that seals nothing on this tree: the file moved, its bytes changed, or no manifest records them.
    It is scanned now, and the entry must go (or be re-pinned to the new freeze) in a reviewed change."""
    live = sealed_files(root, sealed)
    return [f"SEALED {relative} seals nothing on this tree (moved, edited since its freeze, or no freeze manifest "
            f"records {digest}): guard 4 scans it now; remove the entry, or pin the new freeze's digest in a reviewed "
            f"change" for relative, digest in sealed.items() if relative not in live]


def runtime_files(root: Path = ROOT, sealed: dict = SEALED):
    """Every runtime .py file as the filesystem lists it (no git: the mutant gate's copy of the tree has none), by
    guard 3's rule (``_walk``, then ``_once``: each real file once), without NOT_RUNTIME, the ``sealed_files`` and
    top-level hidden entries (.git, tool caches, an agent's worktree: none is tracked runtime code). A link into one
    of those places is read at the link path."""
    sealed = sealed_files(root, sealed)

    def skip(path: Path) -> bool:
        relative = path.relative_to(root)
        return len(relative.parts) == 1 and (relative.name.startswith(".") or f"{relative.name}/" in NOT_RUNTIME)

    def scanned(path: Path) -> bool:
        relative = path.relative_to(root).as_posix()
        return not relative.startswith(".") and relative not in sealed

    yield from _once(_walk(Path(root), root, skip), root, scanned)


def _functions(tree: ast.Module, kinds=FUNCTIONS):
    """(dotted scope name, node) for every function and method (or, with ``kinds=DEFS``, every class too) at any
    depth."""
    out = []

    def visit(node, prefix):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, DEFS):
                name = f"{prefix}.{child.name}" if prefix else child.name
                if isinstance(child, kinds):
                    out.append((name, child))
                visit(child, name)
            else:
                visit(child, prefix)
    visit(tree, "")
    return out


CLASS_SHAPE = "class "          # prefixes a class body's fingerprint dump: a class is compared with classes only


def body_shape(node) -> tuple[int, str]:
    """Guard 4's key for a def (``fingerprint``) or a whole class body (round 6, B3: its fingerprint, every method
    included, tagged CLASS_SHAPE so that a function body never matches a class body)."""
    size, dump = fingerprint(node)
    return (size, CLASS_SHAPE + dump) if isinstance(node, ast.ClassDef) else (size, dump)


def _function_node(module: str, qualname: str, root: Path = ROOT):
    """The def a registered (dotted) qualname is last bound to (``binding``), or None for a class, a constant, a
    missing name or a name whose last binding is not a def."""
    node = binding(module, qualname, root)
    return node if isinstance(node, FUNCTIONS) else None


def _compared_node(module: str, qualname: str, root: Path = ROOT):
    """The def or class (round 6, B3) a registered qualname is last bound to, or None."""
    node = binding(module, qualname, root)
    return node if isinstance(node, DEFS) else None


class Body(NamedTuple):
    """A registered function body: its record, its own location (module and dotted qualname) and its file:line."""
    record: dict
    module: str
    qualname: str
    where: str

    @property
    def registered(self) -> str:
        return f"{self.module}.{self.qualname}"


def registered_bodies(records: list[dict], root: Path = ROOT) -> dict[tuple[int, str], list[Body]]:
    """``body_shape`` -> [Body] for every canonical, candidate and alternate qualname that names a function, or
    (round 6, B3) a class whose whole body, at least MIN_COPY_NODES erased nodes. Constants are guard 3's."""
    out: dict[tuple[int, str], list[Body]] = {}
    for r in records:
        for role, e in entries(r):
            if role == "distinct":
                continue
            for q in e.get("qualnames") or []:
                node = _compared_node(e["module"], q, root)
                if node is None:
                    continue
                shape = body_shape(node)
                if shape[0] >= MIN_COPY_NODES:
                    where = f"{module_file(e['module'], root).relative_to(root).as_posix()}:{node.lineno}"
                    out.setdefault(shape, []).append(Body(r, e["module"], q, where))
    return out


def registered_twin_problems(records: list[dict], root: Path = ROOT) -> list[str]:
    """Two registered locations whose bodies share one fingerprint: one is a copy of the other, and recording a copy
    does not make it an owner (guard 4 exempts a body only at its own location). The same location named by two
    records is one location."""
    out = []
    for found in registered_bodies(records, root).values():
        locations = sorted({(b.registered, b.where, b.record.get("record_id")) for b in found})
        if len({registered for registered, _, _ in locations}) > 1:
            out.append("registered with one body: " + "; ".join(f"{name} ({where}, {rid})" for name, where, rid
                                                                in locations)
                       + ". One is a copy of the other: import the owner's function instead and remove the copy from "
                         "the tree and from the registry")
    return sorted(out)


def compared_problems(records: list[dict], root: Path = ROOT, compared: frozenset = None) -> list[str]:
    """The registered (module, qualname) locations guard 4 compares must equal COMPARED: a body that leaves the
    comparison (its last binding no longer a def or class, the body shrunk below MIN_COPY_NODES, a thin delegation
    left behind) or joins it fails until COMPARED changes in the same reviewed diff."""
    compared = COMPARED if compared is None else compared
    have = {(b.module, b.qualname) for found in registered_bodies(records, root).values() for b in found}
    out = [f"{m}.{q} is pinned in COMPARED and is no longer compared by guard 4: its last binding is not a def or class, or its "
           f"body is below MIN_COPY_NODES ({MIN_COPY_NODES} erased nodes), or the record no longer names it, so a "
           f"copy of it would pass. Restore it, or change COMPARED in the same reviewed diff and say why"
           for m, q in sorted(compared - have)]
    out += [f"{m}.{q} is compared and not pinned in COMPARED: add it in the same reviewed diff"
            for m, q in sorted(have - compared)]
    return out


@lru_cache(maxsize=None)
def _prints(path: Path, stamp: int, sizes: frozenset) -> tuple:
    """(scope name, line, ``body_shape``) for every function and class of one file whose erased size is one of
    ``sizes``; the rest are never copied."""
    return tuple((name, node.lineno, body_shape(node)) for name, node in _functions(_parse(path, stamp), DEFS)
                 if _erased_size(node) in sizes)


def body_copies(records: list[dict], root: Path = ROOT, sealed: dict = SEALED) -> tuple[list[dict], list[str]]:
    """(every function or method whose fingerprint is a registered body's, anywhere but that body's own registered
    module and qualname, inside its record or outside it; every runtime file that does not parse). Neither a
    'distinct' entry nor recording the module as a canonical, candidate or alternate module exempts a copy; only
    BODY_EXEMPTIONS does (``exempted``)."""
    bodies = registered_bodies(records, root)
    sizes = frozenset(size for size, _ in bodies)
    files = list(runtime_files(root, sealed))
    found, unreadable = [], module_name_problems(files, root)
    for path in files:
        relative = path.relative_to(root).as_posix()
        try:
            prints = _prints(path, path.stat().st_mtime_ns, sizes)
        except (SyntaxError, UnicodeDecodeError, ValueError, OSError) as exc:
            unreadable.append(f"{relative} cannot be parsed ({type(exc).__name__}), so guard 4 cannot show that it "
                              f"holds no copy of a registered function")
            continue
        module = module_name(path, root)
        for name, line, shape in prints:
            for body in bodies.get(shape, []):
                if (module, name) != (body.module, body.qualname):
                    found.append({"record": body.record, "registered": body.registered, "registered_at": body.where,
                                  "module": module, "at": f"{relative}:{line}", "name": name})
    return found, unreadable


def exempted(found: list[dict], exemptions: dict = BODY_EXEMPTIONS) -> tuple[list[dict], list[str]]:
    """(the copies no exemption clears; a problem for every exemption that clears nothing or gives no reason). An
    entry clears the copy at its own (module, qualname) of the registered body it names, and no other."""
    used, kept = set(), []
    for c in found:
        key = (c["module"], c["name"])
        if key in exemptions and exemptions[key][0] == c["registered"] and str(exemptions[key][1]).strip():
            used.add(key)
        else:
            kept.append(c)
    problems = [f"BODY_EXEMPTIONS {key} gives no reason: say why {key[0]}.{key[1]} is a different function from "
                f"{resembles}" for key, (resembles, reason) in exemptions.items() if not str(reason).strip()]
    problems += [f"BODY_EXEMPTIONS {key} no longer matches a copy of {resembles} at {key[0]}.{key[1]}: remove it"
                 for key, (resembles, reason) in exemptions.items() if key not in used and str(reason).strip()]
    return kept, sorted(problems)


def body_copy_problems(records: list[dict], root: Path = ROOT, exemptions: dict = BODY_EXEMPTIONS,
                       sealed: dict = SEALED) -> list[str]:
    found, unreadable = body_copies(records, root, sealed)
    found, stale = exempted(found, exemptions)
    out = [f"{c['at']} defines {c['name']!r}, a copy of the body of {c['registered']} ({c['registered_at']}), "
           f"registered in {c['record']['record_id']} ({c['record'].get('function')}); names and constants are erased "
           f"before comparing, so renamed variables or changed literals are still the same body. Its owner is "
           f"{owner(c['record'])}. " + FIX_COPY.format(record=c["record"]["record_id"]) for c in found]
    return sorted(set(out)) + unreadable + stale


def distinct_copy_problems(records: list[dict], root: Path = ROOT, exemptions: dict = BODY_EXEMPTIONS) -> list[str]:
    """A 'distinct' entry says a module holds a different function. It may not name a module that holds a copy of a
    registered body (guard 4) that BODY_EXEMPTIONS does not clear: a copy is never a different function."""
    holding: dict[str, list[dict]] = {}
    for c in exempted(body_copies(records, root)[0], exemptions)[0]:
        holding.setdefault(c["module"], []).append(c)
    out = []
    for r in records:
        for e in r.get("distinct") or []:
            for c in holding.get(e.get("module"), []):
                out.append(f"{r.get('record_id')}: distinct entry {e['module']} names a module that holds a copy of "
                           f"the body of {c['registered']} ({c['at']}, {c['name']!r}, registered in "
                           f"{c['record']['record_id']}); a copy is never a different function: record the module as "
                           f"an ALTERNATE of {c['record']['record_id']} with its retirement or revival condition, or "
                           f"import the owner")
    return sorted(set(out))


# -- history kept only with a live reason (section 76; MW-C, 2026-11-21) -------------------------------------------

KEPT_FOR = ("consumer", "open_decision")
# Not a consumer: greg/ (guard 2 forbids it to reach the alternate), tests/ (a test of the kept object is not a use),
# docs/ and scripts/ci/ (tooling, not use), and any conftest.py (test set-up), by dotted module prefix and name.
NOT_CONSUMERS = ("greg", "tests", "docs", "scripts.ci")
NOT_CONSUMER_NAMES = ("conftest",)


def _not_a_consumer(module: str) -> bool:
    return (any(module == p or module.startswith(p + ".") for p in NOT_CONSUMERS)
            or module.rpartition(".")[2] in NOT_CONSUMER_NAMES)


def _names_in(node) -> set[str]:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)} | {
        n.attr for n in ast.walk(node) if isinstance(n, ast.Attribute)}


def kept_for_problems(records: list[dict], root: Path = ROOT) -> list[str]:
    """Directive section 76: "Do not keep obsolete implementations merely to preserve history." A FORWARD GUARD over
    the registry: every alternate with status HISTORICAL or RETIRED whose module (or one of its qualnames) is still
    defined in the tree carries ``kept_for``, exactly one of

    - ``{consumer: <module>.<function>}``: a function outside ``NOT_CONSUMERS`` (greg/, tests/, docs/, scripts/ci/) and
      any conftest.py, and outside the alternate's own module, whose source names the kept object, in a module that
      imports it from the alternate's module; or
    - ``{open_decision: <record_id>}``: the alternate's OWN record, while it is still NEEDS_FOUNDER_DECISION (its
      ruling may revive the alternate; another record's open decision keeps nothing).

    An alternate gone from the tree needs none: git keeps its history. On 2026-11-21 this binds one entry
    (greg.mission_control REALITY, HISTORICAL). It binds only what the registry records: obsolete code that no record
    names is not seen. A STATED LIMIT: a consumer is checked by what its source names, not by whether anything calls
    it, so a dead two-line shim outside those places that imports and returns the object still passes."""
    by_id = {r.get("record_id"): r for r in records}
    out = []
    for r in records:
        rid = r.get("record_id")
        for e in r.get("alternates") or []:
            if e.get("status") not in NOT_IMPORTABLE:
                continue
            module, names = e["module"], list(e.get("qualnames") or [])
            if module_file(module, root) is None or (names and not any(has_qualname(module, q, root) for q in names)):
                continue
            what = f"{module}" + (f".{'/'.join(names)}" if names else "")
            kept = e.get("kept_for")
            if not (isinstance(kept, dict) and len(kept) == 1 and next(iter(kept)) in KEPT_FOR):
                out.append(f"{rid}: {e['status']} alternate {what} is still defined in the tree and does not say what "
                           f"keeps it: give it kept_for {{consumer: <module>.<function>}} (code outside greg/, tests/, "
                           f"docs/, scripts/ci/ and any conftest.py that still reads it) or {{open_decision: {rid}}} "
                           f"(while its own record is undecided), or remove it from the tree (git keeps its history)")
                continue
            if "open_decision" in kept:
                if kept["open_decision"] != rid:
                    out.append(f"{rid}: {what} is kept_for open_decision {kept['open_decision']}, which is not its own "
                               f"record {rid}; only the decision on the alternate's own record may revive it")
                elif by_id.get(rid, {}).get("owner_status") != "NEEDS_FOUNDER_DECISION":
                    out.append(f"{rid}: {what} is kept_for open_decision {rid}, which is not NEEDS_FOUNDER_DECISION; "
                               f"once the founder rules, the alternate leaves the tree, or names the consumer that "
                               f"still reads it")
                continue
            consumer = str(kept["consumer"])
            consumer_module, _, function = consumer.rpartition(".")
            if not consumer_module or _not_a_consumer(consumer_module) or consumer_module == module:
                out.append(f"{rid}: {what} is kept_for consumer {consumer}, which is not a consumer: a function "
                           f"outside greg/, tests/, docs/, scripts/ci/ and any conftest.py, and outside the "
                           f"alternate's own module")
                continue
            path, node = module_file(consumer_module, root), definition_node(consumer_module, function, root)
            if path is None or not isinstance(node, FUNCTIONS):
                out.append(f"{rid}: {what} is kept_for consumer {consumer}, which does not exist (moved or renamed? "
                           f"update kept_for, or remove the alternate from the tree)")
                continue
            kept_names = set(names) or {module.rpartition(".")[2]}
            refs = reach(path, root).refs
            if not (_names_in(node) & {n.split(".")[-1] for n in kept_names}
                    and any(_hits(ref, module, names) for _, ref in refs)):
                out.append(f"{rid}: {what} is kept_for consumer {consumer}, whose source does not name "
                           f"{module}.{'/'.join(names) or '*'} (imported from {module}); a consumer is code that still "
                           f"reads the kept object")
    return out


# -- the registry ------------------------------------------------------------------------------------------------

def test_registry_names_an_owner_status_alternates_and_conditions_for_every_required_function():
    assert shape_problems(load()) == []


def test_the_registry_keeps_every_pinned_record_entry_and_founder_decision():
    assert pin_problems(load()) == []


def test_every_record_catches_the_names_it_must_and_exempts_only_common_names():
    assert marker_problems(load()["function_owner_records"]) == []


def test_every_registered_module_and_qualname_exists():
    assert missing(load()["function_owner_records"]) == []


def test_no_greg_module_imports_a_retired_or_historical_alternate():
    assert retired_imports(load()["function_owner_records"]) == []


def test_every_dynamic_import_in_greg_resolves_or_is_allowlisted():
    assert unresolved_imports() == []


def test_no_unrecorded_reimplementation_of_a_registered_function():
    assert unrecorded(load()["function_owner_records"]) == []


def test_the_registry_has_at_least_one_alternate_the_import_guard_applies_to():
    # Without one, guard 2 would pass vacuously.
    statuses = [e["status"] for r in load()["function_owner_records"] for e in r.get("alternates") or []]
    assert set(statuses) & set(NOT_IMPORTABLE)


def test_the_adopted_autonomy_ladder_is_candidate_side_b_and_only_a_founder_ruling_promotes_it(tmp_path):
    # #235's greg/autonomy.py, adopted into #196 at 6fc4b22b, is a second autonomy ladder. It is recorded as
    # candidate side B of an undecided record, never as an owner, and without that entry guard 3 reports its names.
    data = load()
    record = next(r for r in data["function_owner_records"] if r["record_id"] == "OWN-FN-AUTONOMY-LEVELS")
    assert record["owner_status"] == "NEEDS_FOUNDER_DECISION" and not record.get("canonical")
    assert {c["side"]: c["module"] for c in record["candidates"]} == {"A": "autonomy.levels", "B": "greg.autonomy"}
    side_a, side_b = sorted(record["candidates"], key=lambda c: c["side"])
    without_b = {**record, "candidates": [side_a]}
    found = {(line.split(":")[0], line.split(" defines '")[1].split("'")[0])
             for line in unrecorded([without_b], packages=("greg",))}
    assert found == {("greg/autonomy.py", "LEVELS"), ("greg/autonomy.py", "EARNED_CEILING"),
                     ("greg/autonomy.py", "earned_level")}

    # Only the founder's ruling may make side B canonical, and it must keep side A as an alternate.
    root = _tree(tmp_path, {"docs/decisions/ADR-AUTONOMY.md":
                            "- Status: accepted\nOWN-FN-AUTONOMY-LEVELS: section 59's five levels are canonical.\n"})
    ruled = {**record, "owner_status": "CANONICAL", "candidates": [],
             "canonical": [{"module": "greg.autonomy", "qualnames": side_b["qualnames"]}],
             "alternates": [{"module": "autonomy.levels", "qualnames": side_a["qualnames"], "status": "ALTERNATE",
                             "reason": "ruled", "retirement_condition": "ruled"}]}

    def problems(replacement):
        changed = copy.deepcopy(data)
        changed["function_owner_records"] = [replacement if r["record_id"] == record["record_id"] else r
                                             for r in changed["function_owner_records"]]
        return [p for p in pin_problems(changed, root) if p.startswith(record["record_id"])]

    assert any("without a founder_ruling" in p for p in problems(ruled))
    assert problems({**ruled, "founder_ruling": "docs/decisions/ADR-AUTONOMY.md"}) == []
    assert any("only a module that was a candidate" in p for p in problems(
        {**ruled, "founder_ruling": "docs/decisions/ADR-AUTONOMY.md",
         "canonical": [{"module": "greg.earned", "qualnames": ["LEVELS"]}]}))
    assert any("candidates greg.autonomy.LEVELS is pinned" in p for p in problems(without_b))


# -- the guards themselves, on synthetic trees -------------------------------------------------------------------

def _tree(tmp_path: Path, files: dict[str, str]) -> Path:
    for relative, text in files.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return tmp_path


HISTORICAL = [{"record_id": "OWN-FN-X", "function": "x", "owner_status": "CANONICAL", "markers": ["X"],
               "canonical": [{"module": "greg.owner", "qualnames": ["run"]}],
               "alternates": [{"module": "greg.old", "qualnames": ["LADDER"], "status": "HISTORICAL",
                               "revival_condition": "never"},
                              {"module": "greg.gone", "qualnames": [], "status": "RETIRED",
                               "revival_condition": "never"}]}]


def test_the_import_guard_sees_aliases_attributes_relative_and_lazy_imports(tmp_path):
    root = _tree(tmp_path, {
        "greg/__init__.py": "", "greg/owner.py": "def run(): pass\n",
        "greg/old.py": "LADDER = ()\ndef keep(): pass\n", "greg/gone.py": "",
        "greg/direct.py": "from greg.old import LADDER\n",
        "greg/aliased.py": "from greg.old import LADDER as L\n",
        "greg/module_alias.py": "import greg.old as o\nX = o.LADDER\n",
        "greg/parent_alias.py": "from greg import old as o\nX = o.LADDER\n",
        "greg/dotted.py": "import greg.old\nX = greg.old.LADDER\n",
        "greg/relative.py": "from .old import LADDER\n",
        "greg/relative_module.py": "from . import old\nX = old.LADDER\n",
        "greg/lazy.py": "def f():\n    from greg.old import LADDER\n    return LADDER\n",
        "greg/star.py": "from greg.old import *\n",
        "greg/whole_module.py": "import greg.gone\n",
        "greg/dynamic.py": "import importlib\nM = importlib.import_module('greg.gone')\n",
        "greg/wired.py": "def _lazy(m, n): pass\nB = {'x': _lazy('greg.old', 'LADDER')}\n",
        "greg/wired_module.py": "def _lazy(m, n): pass\nB = {'x': _lazy('greg.gone', handler)}\n",
        "greg/wired_kw.py": "def _lazy(module, name): pass\nB = _lazy(module='greg.old', name='LADDER')\n",
        "greg/wired_fine.py": "def _lazy(m, n): pass\nB = {'x': _lazy('greg.old', 'keep')}\n",
        "greg/sub/__init__.py": "from ..old import LADDER\n",
        # review finding F1 on 77deac50: each of these got through
        "greg/dunder_attr.py": "X = __import__('greg.old', fromlist=['LADDER']).LADDER\n",
        "greg/dunder_top.py": "X = __import__('greg.old').old.LADDER\n",
        "greg/import_module_attr.py": "import importlib\nX = importlib.import_module('greg.old').LADDER\n",
        "greg/dynamic_alias.py": "import importlib\nm = importlib.import_module('greg.old')\nX = m.LADDER\n",
        "greg/dynamic_chain.py": "import importlib\nm = importlib.import_module('greg.old')\nn = m\nX = n.LADDER\n",
        "greg/getattr_const.py": "from greg import old as mc\nX = getattr(mc, 'LADDER')\n",
        "greg/getattr_computed.py": "from greg import old as mc\ndef f(name):\n    return getattr(mc, name)\n",
        "greg/vars_lookup.py": "from greg import old as mc\nX = vars(mc)['LADDER']\n",
        "greg/dict_lookup.py": "from greg import old as mc\nX = mc.__dict__['LADDER']\n",
        "greg/relative_dynamic.py": "import importlib\nM = importlib.import_module('.gone', 'greg')\n",
        "greg/keyword_dynamic.py": "import importlib\nM = importlib.import_module(name='greg.gone')\n",
        "greg/sys_modules.py": "import sys, greg.owner\nX = sys.modules['greg.old'].LADDER\n",
        "greg/walrus_alias.py": "import importlib\nif (m := importlib.import_module('greg.old')):\n    X = m.LADDER\n",
        "greg/fine.py": "from greg.old import keep\nimport greg.owner\nimport importlib\n"
                        "X = importlib.import_module('greg.old').keep\nY = getattr(greg.owner, 'run')\n",
    })
    found = retired_imports(HISTORICAL, root)
    for name in ("direct", "aliased", "module_alias", "parent_alias", "dotted", "relative", "relative_module", "lazy",
                 "star", "whole_module", "dynamic", "wired", "wired_module", "wired_kw", "dunder_attr", "dunder_top",
                 "import_module_attr", "dynamic_alias", "dynamic_chain", "getattr_const", "getattr_computed",
                 "vars_lookup", "dict_lookup", "relative_dynamic", "keyword_dynamic", "sys_modules", "walrus_alias"):
        assert any(line.startswith(f"greg/{name}.py:") for line in found), name
    assert any(line.startswith("greg/sub/__init__.py:") for line in found)
    assert not any(line.startswith(("greg/fine.py:", "greg/old.py:", "greg/wired_fine.py:")) for line in found)


def test_the_import_guard_follows_module_name_tables_and_reports_what_it_cannot_resolve(tmp_path):
    # review finding F2 on 77deac50: greg/appraisal.py reaches greg.organ_exchange through DELIVERING[...]
    root = _tree(tmp_path, {
        "greg/__init__.py": "", "greg/owner.py": "def run(): pass\n", "greg/old.py": "LADDER = ()\n",
        "greg/gone.py": "def verify_delivery(): pass\n", "greg/briefs.py": "def verify_delivery(): pass\n",
        "greg/table.py": ("import importlib\nDELIVERING = {'brief': 'greg.briefs', 'gone': 'greg.gone'}\n"
                          "def check(action):\n"
                          "    return importlib.import_module(DELIVERING[action]).verify_delivery\n"),
        "greg/keyed.py": "import importlib\nT = {'a': 'greg.gone', 'b': 'greg.briefs'}\nM = importlib.import_module(T['a'])\n",
        "greg/tuple_table.py": "import importlib\nMODS = ('greg.briefs', 'greg.gone')\nM = [importlib.import_module(MODS[0])]\n",
        "greg/computed.py": "import importlib\ndef load(name):\n    return importlib.import_module(name)\n",
        "greg/computed_ok.py": "import importlib\nclass A:\n    def load(self, name):\n        return importlib.import_module(name)\n",
        "greg/computed_dunder.py": "def f(x):\n    return __import__(x)\n",
        "greg/fine.py": "import importlib\nT = {'b': 'greg.briefs'}\nM = importlib.import_module(T['b'])\n",
    })
    found = retired_imports(HISTORICAL, root)
    for name in ("table", "keyed", "tuple_table"):
        assert any(line.startswith(f"greg/{name}.py:") for line in found), name
    assert not any(line.startswith("greg/fine.py:") for line in found)
    allowed = {("greg/computed_ok.py", "A.load"): "test", ("greg/gone_away.py", "f"): "stale"}
    unresolved = unresolved_imports(root, allowed=allowed)
    assert any(line.startswith("greg/computed.py:3 (load)") for line in unresolved)
    assert any(line.startswith("greg/computed_dunder.py:2 (f)") for line in unresolved)
    assert not any(line.startswith(("greg/computed_ok.py", "greg/table.py", "greg/keyed.py")) for line in unresolved)
    assert any("('greg/gone_away.py', 'f') no longer matches" in line for line in unresolved)


def test_the_definition_guard_sees_classes_constants_and_guarded_blocks(tmp_path):
    teams = next(r for r in load()["function_owner_records"] if r["record_id"] == "OWN-FN-TEMPORARY-TEAMS")
    root = _tree(tmp_path, {
        "greg/__init__.py": "",
        "greg/crew.py": ("class TeamError(RuntimeError):\n    pass\nMAX_TEAM_SIZE = 3\n"
                         "try:\n    import x\nexcept ImportError:\n    def form_team():\n        pass\n"
                         "def steamroll():\n    pass\nclass Holder:\n    def team(self):\n        pass\n"),
        "foundry/__init__.py": "", "foundry/systems/__init__.py": "",
        "foundry/systems/teams.py": "class TeamError(RuntimeError):\n    pass\n",
    })
    found = unrecorded([teams], root, packages=("greg", "foundry"))
    named = {line.split(" defines ")[1].split(",")[0] for line in found}
    assert named == {"'TeamError'", "'MAX_TEAM_SIZE'", "'form_team'"}
    assert all(line.startswith("greg/crew.py:") and "OWN-FN-TEMPORARY-TEAMS" in line and "alternate or shim" in line
               for line in found)


def test_the_definition_guard_sees_every_module_level_binding_shape(tmp_path):
    # review finding F8 on 77deac50: each of these bindings was invisible
    autonomy = next(r for r in load()["function_owner_records"] if r["record_id"] == "OWN-FN-AUTONOMY-LEVELS")
    shapes = {
        "for_block": "for LEVELS in [('A0',)]:\n    pass\n",
        "for_body": "for _ in range(1):\n    LEVELS = ('A0',)\n",
        "while_block": "while True:\n    LEVELS = ('A0',)\n    break\n",
        "match_block": "match 1:\n    case 1:\n        LEVELS = ('A0',)\n",
        "match_capture": "match ('A0',):\n    case LEVELS:\n        pass\n",
        "walrus": "if (LEVELS := ('A0',)):\n    pass\n",
        "walrus_expr": "print(LEVELS := ('A0',))\n",
        "import_as": "import json as LEVELS\n",
        "from_import_as": "from json import loads as EARNED_CEILING\n",
        "globals_set": "globals()['LEVELS'] = ('A0',)\n",
        "globals_update": "globals().update(LEVELS=('A0',))\n",
        "with_as": "import contextlib\nwith contextlib.nullcontext(('A0',)) as LEVELS:\n    pass\n",
        "except_as": "try:\n    pass\nexcept Exception as LEVELS:\n    pass\n",
    }
    root = _tree(tmp_path, {"greg/__init__.py": "", **{f"greg/{k}.py": v for k, v in shapes.items()},
                            "autonomy/__init__.py": "", "autonomy/levels.py": "LEVELS = ()\n",
                            "greg/consumer.py": "from autonomy.levels import LEVELS\nfrom autonomy import levels as L\n",
                            "greg/lambda_scope.py": "F = lambda: (LEVELS := 1)\ndef f():\n    LEVELS = 2\n"})
    found = unrecorded([autonomy], root, packages=("greg",))
    for name in shapes:
        assert any(line.startswith(f"greg/{name}.py:") for line in found), name
    assert not any(line.startswith(("greg/consumer.py:", "greg/lambda_scope.py:")) for line in found)


OWNER_BODY = ("def send_signed(home, key, kind, body):\n"
              "    \"\"\"Sign and drop.\"\"\"\n"
              "    envelope = {'kind': kind, 'body': body, 'key': key}\n"
              "    path = home / 'inbox' / (kind + '.json')\n"
              "    tmp = path.with_suffix('.tmp')\n"
              "    tmp.write_text(str(envelope))\n"
              "    tmp.replace(path)\n"
              "    return path\n")


def test_the_definition_guard_catches_a_registered_name_or_a_copy_outside_its_record(tmp_path):
    # review finding F3 on 77deac50: a copy of the canonical function under its own name passed
    record = {"record_id": "OWN-FN-X", "function": "x", "owner_status": "CANONICAL", "markers": ["Inbox"],
              "canonical": [{"module": "greg.body", "qualnames": ["send_signed", "status"]}],
              "generic_names": ["status"],
              "distinct": [{"module": "greg.audited", "qualnames": ["send_signed"], "why": "test"}]}
    root = _tree(tmp_path, {
        "greg/__init__.py": "", "greg/body.py": OWNER_BODY + "def status():\n    return {}\n",
        "greg/nodes.py": "def send_signed(home, key, kind, body):\n    return None\n",
        "greg/relay.py": OWNER_BODY.replace("def send_signed(", "def forward_envelope(").replace(
            "    \"\"\"Sign and drop.\"\"\"\n", ""),
        "greg/other.py": "def status():\n    return {'ok': True}\n",
        "greg/audited.py": "def send_signed():\n    return None\n",
        "greg/user.py": "from greg.body import send_signed\n",
    })
    found = unrecorded([record], root, packages=("greg",))
    assert any(line.startswith("greg/nodes.py:1 defines 'send_signed', which reuses the name") for line in found)
    assert any(line.startswith("greg/relay.py:1 defines 'forward_envelope', a structural copy of greg.body.send_signed")
               for line in found)
    assert not any(line.startswith(("greg/other.py", "greg/audited.py", "greg/user.py", "greg/body.py"))
                   for line in found)


def test_a_founder_decision_resolves_only_through_a_ruling_record_that_names_it(tmp_path):
    # review findings F5 and F6 on 77deac50: a second canonical module and a unilateral flip both passed
    pinned = {"OWN-FN-D": {"canonical": {}, "candidates": {"greg.a": ("run",), "greg.b": ("run",)}, "alternates": {},
                           "distinct": {}},
              "OWN-FN-C": {"canonical": {"greg.a": ("run",)}, "candidates": {}, "alternates": {"greg.b": ("run",)},
                           "distinct": {}}}
    root = _tree(tmp_path, {
        "docs/decisions/ADR-OK.md": "# Ruling\n- Status: accepted\nOWN-FN-D: side A is canonical.\n",
        "docs/decisions/ADR-PROPOSED.md": "# Ruling\n- Status: proposed\nOWN-FN-D: side A.\n",
        "docs/decisions/ADR-OTHER.md": "# Ruling\n- Status: accepted\nAbout something else.\n",
        "docs/elsewhere/RULING.md": "- Status: accepted\nOWN-FN-D\n"})

    def data(d_record, c_canonical=("greg.a",)):
        return {"function_owner_records": [
            {"record_id": "OWN-FN-D", **d_record},
            {"record_id": "OWN-FN-C", "owner_status": "CANONICAL",
             "canonical": [{"module": m, "qualnames": ["run"]} for m in c_canonical],
             "alternates": [{"module": "greg.b", "qualnames": ["run"], "status": "ALTERNATE"}]}]}

    undecided = {"owner_status": "NEEDS_FOUNDER_DECISION", "candidates": [{"module": "greg.a", "qualnames": ["run"]},
                                                                           {"module": "greg.b", "qualnames": ["run"]}]}
    ruled = {"owner_status": "CANONICAL", "canonical": [{"module": "greg.a", "qualnames": ["run"]}],
             "alternates": [{"module": "greg.b", "qualnames": ["run"], "status": "ALTERNATE"}]}
    entries = {"OWN-FN-D": {"canonical": [], "candidates": undecided["candidates"], "alternates": [], "distinct": []}}
    check = lambda d: pin_problems(d, root, pinned, frozenset({"OWN-FN-D"}), entries)  # noqa: E731
    assert check(data(undecided)) == []
    assert any("without a founder_ruling" in p for p in check(data(ruled)))
    for ref, said in (("docs/decisions/ADR-PROPOSED.md", "is not accepted or active"),
                      ("docs/decisions/ADR-OTHER.md", "does not name OWN-FN-D"),
                      ("docs/elsewhere/RULING.md", "is not a decision or intent record"),
                      ("docs/decisions/ADR-MISSING.md", "is not a decision or intent record")):
        assert any(said in p for p in check(data({**ruled, "founder_ruling": ref}))), ref
    assert check(data({**ruled, "founder_ruling": "docs/decisions/ADR-OK.md"})) == []
    # a ruling cannot make a non-candidate canonical, nor drop a candidate
    assert any("only a module that was a candidate" in p for p in check(data(
        {**ruled, "founder_ruling": "docs/decisions/ADR-OK.md",
         "canonical": [{"module": "greg.z", "qualnames": ["run"]}]})))
    assert any("candidates greg.b.run is pinned" in p for p in check(data(
        {"owner_status": "CANONICAL", "founder_ruling": "docs/decisions/ADR-OK.md",
         "canonical": [{"module": "greg.a", "qualnames": ["run"]}]})))
    # a second canonical module on an ordinary record, or a dropped alternate, fails
    assert any("A second canonical module makes two owners" in p
               for p in check(data(undecided, c_canonical=("greg.a", "greg.teams"))))
    no_alternate = data(undecided)
    no_alternate["function_owner_records"][1]["alternates"] = []
    assert any("alternates greg.b.run is pinned" in p for p in check(no_alternate))


def test_a_stale_qualname_or_module_is_reported(tmp_path):
    root = _tree(tmp_path, {"greg/__init__.py": "", "greg/owner.py": "class A:\n    def b(self): pass\n"})
    record = {"record_id": "OWN-FN-X", "canonical": [{"module": "greg.owner", "qualnames": ["A.b", "A.c", "run"]}],
              "alternates": [{"module": "greg.moved", "qualnames": ["x"], "status": "ALTERNATE"}]}
    found = missing([record], root)
    assert any("greg.owner.A.c does not exist" in line for line in found)
    assert any("greg.owner.run does not exist" in line for line in found)
    assert any("module greg.moved does not exist" in line for line in found)
    assert not any("A.b" in line for line in found)


# -- guard 4, the exact candidate pin and the history guard (MW-C, 2026-11-21) ------------------------------------

def test_no_copy_of_a_registered_function_body_outside_its_record():
    records = load()["function_owner_records"]
    # not vacuous: the 36 registered bodies COMPARED pins (compared_problems: 27 functions and, since round 6, the 9
    # registered classes whole), compared with every function, method and class of about 550 runtime files; each is
    # exempt only at its own location
    assert compared_problems(records) == [] and len(COMPARED) == 36
    assert len(list(runtime_files())) > 400
    assert body_copy_problems(records) == []
    assert registered_twin_problems(records) == []
    assert sealed_problems() == [] and sealed_files() == frozenset(SEALED)


def test_no_distinct_entry_names_a_module_that_holds_a_copy_of_a_registered_body():
    assert distinct_copy_problems(load()["function_owner_records"]) == []


def test_every_historical_or_retired_alternate_still_in_the_tree_says_what_keeps_it():
    records = load()["function_owner_records"]
    kept = [e for r in records for e in r.get("alternates") or [] if e.get("status") in NOT_IMPORTABLE
            and module_file(e["module"]) is not None]
    assert kept, "no HISTORICAL or RETIRED alternate is still in the tree: the guard would pass vacuously"
    assert kept_for_problems(records) == []


class _Disguise(ast.NodeTransformer):
    """What a copier changes to hide a copy: every variable and argument name, and every string and number literal
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
        if self.fstring:
            return node
        if isinstance(node.value, str):
            node.value += " (copy)"
        elif isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            node.value += 1
        return node


def _disguised(module: str, name: str, new_name: str, method: bool = False, indent: str = "") -> str:
    """A renamed copy of a registered function from this repository, every name and literal changed."""
    node = copy.deepcopy(definition_node(module, name))
    node.name, node.decorator_list = new_name, []
    _Disguise().visit(node)
    if method:
        node.args.args.insert(0, ast.arg("self"))
    ast.fix_missing_locations(node)
    return "".join(indent + line + "\n" for line in ast.unparse(node).splitlines())


def _real(*modules: str) -> dict[str, str]:
    return {str(module_file(m).relative_to(ROOT)): module_file(m).read_text() for m in modules}


def test_the_body_guard_catches_renamed_nested_relocated_and_one_line_copies(tmp_path):
    data = {r["record_id"]: r for r in load()["function_owner_records"]}
    commerce, teams = data["OWN-FN-COMMERCE-CLOSURE"], data["OWN-FN-TEMPORARY-TEAMS"]
    inbox = {"record_id": "OWN-FN-X", "function": "x", "owner_status": "CANONICAL", "markers": ["Inbox"],
             "canonical": [{"module": "greg.body", "qualnames": ["send_signed"]}]}
    # every statement of OWNER_BODY on one line: no line-count threshold would see it
    one_line = ("def relay(h, k, t, b): e = {'t': t, 'b': b, 'k': k}; p = h / 'box' / (t + '.j'); "
                "s = p.with_suffix('.x'); s.write_text(str(e)); s.replace(p); return p\n")
    different = ("def read_inbox(home, kind):\n    path = home / 'inbox' / (kind + '.json')\n"
                 "    if not path.exists():\n        return None\n    data = json.loads(path.read_text())\n"
                 "    for key in ('body', 'kind'):\n        data.setdefault(key, None)\n"
                 "    return data.get('body')\n")
    root = _tree(tmp_path, {
        **_real("greg.business_loop", "foundry.systems.teams"),
        "greg/body.py": OWNER_BODY,
        # a method in business/, outside the six guarded packages, every local renamed and every literal changed
        "business/case_copy.py": "class Case:\n" + _disguised("greg.business_loop", "reconcile", "settle",
                                                               method=True, indent="    "),
        # a nested def
        "greg/wrapped.py": "def outer():\n" + _disguised("greg.business_loop", "reconcile", "inner", indent="    ")
                           + "    return inner\n",
        # top level, outside the six packages
        "closure/settle_copy.py": _disguised("greg.business_loop", "reconcile", "settle_case"),
        # in the owner's own directory, under another name
        "foundry/systems/team_copy.py": _disguised("foundry.systems.teams", "form", "convene"),
        "greg/oneline.py": one_line,
        "greg/reader.py": different,
        # a directory named evaluation is not skipped (cortex/evaluation/: the next test but one)
        "greg/evaluation/team_copy.py": _disguised("foundry.systems.teams", "form", "convene"),
        # positive controls for each part of the scan and of the eraser (verifier, MW-C review 2026-11-21: a code
        # mutant that drops any one of them survived this file): an async def, a top-level file, cortex/ outside
        # the sealed instruments, and copies of DEEP_BODY with only an except-as name, an import alias or a nested
        # def's name renamed; an unparseable file is reported, never dropped
        "acceptance/async_copy.py": _disguised("foundry.systems.teams", "form", "convene").replace(
            "def convene(", "async def convene(", 1),
        "toplevel_copy.py": _disguised("greg.business_loop", "reconcile", "settle_case"),
        "cortex/other_copy.py": _disguised("foundry.systems.teams", "form", "convene"),
        "greg/collect.py": DEEP_BODY,
        "greg/except_renamed.py": _variant(("as error:", "as failure:"), ("str(error)", "str(failure)")),
        "greg/alias_renamed.py": _variant(("import json as codec", "import json as parser"),
                                          ("codec.loads", "parser.loads")),
        "greg/nested_renamed.py": _variant(("    def load(name):", "    def fetch(name):"),
                                           ("= load(name)", "= fetch(name)")),
        "greg/broken.py": "def settle(:\n",
    })
    found = body_copy_problems([commerce, teams, inbox, DEEP_RECORD], root)
    expected = {"business/case_copy.py": ("'Case.settle'", "greg.business_loop.reconcile (greg/business_loop.py:"),
                "greg/wrapped.py": ("'outer.inner'", "greg.business_loop.reconcile (greg/business_loop.py:"),
                "closure/settle_copy.py": ("'settle_case'", "greg.business_loop.reconcile (greg/business_loop.py:"),
                "foundry/systems/team_copy.py": ("'convene'", "foundry.systems.teams.form (foundry/systems/teams.py:"),
                "greg/evaluation/team_copy.py": ("'convene'", "foundry.systems.teams.form (foundry/systems/teams.py:"),
                "greg/oneline.py": ("'relay'", "greg.body.send_signed (greg/body.py:1)"),
                "acceptance/async_copy.py": ("'convene'", "foundry.systems.teams.form (foundry/systems/teams.py:"),
                "toplevel_copy.py": ("'settle_case'", "greg.business_loop.reconcile (greg/business_loop.py:"),
                "cortex/other_copy.py": ("'convene'", "foundry.systems.teams.form (foundry/systems/teams.py:"),
                "greg/except_renamed.py": ("'gather'", "greg.collect.collect (greg/collect.py:1)"),
                "greg/alias_renamed.py": ("'gather'", "greg.collect.collect (greg/collect.py:1)"),
                "greg/nested_renamed.py": ("'gather'", "greg.collect.collect (greg/collect.py:1)")}
    for path, (copied, registered) in expected.items():
        assert any(line.startswith(f"{path}:") and copied in line and registered in line for line in found), path
    assert "greg/broken.py cannot be parsed (SyntaxError)" in " ".join(found), found
    assert len(found) == len(expected) + 1, found
    # the control: a genuinely different function of similar size (within a fifth of the registered body's)
    size, registered_size = _erased_size(ast.parse(different).body[0]), fingerprint(ast.parse(OWNER_BODY).body[0])[0]
    assert abs(size - registered_size) <= registered_size / 5
    assert not any(line.startswith("greg/reader.py") for line in found)
    # the owners' own modules hold the originals, not copies
    assert not any(line.startswith(("greg/business_loop.py", "foundry/systems/teams.py", "greg/body.py"))
                   for line in found)


def test_the_body_guard_does_not_see_an_attribute_rename(tmp_path):
    # A STATED LIMIT, recorded as passing. Attribute names and subscript-versus-attribute access are structure the
    # fingerprint keeps, so a copy that changes one attribute name (write_text to write_bytes) or reads a field as
    # an attribute instead of a key (envelope['kind'] to envelope.kind) is not detected. A later change that claims
    # this coverage must change these assertions.
    record = {"record_id": "OWN-FN-X", "function": "x", "owner_status": "CANONICAL", "markers": ["Inbox"],
              "canonical": [{"module": "greg.body", "qualnames": ["send_signed"]}]}
    keyed = OWNER_BODY.replace("    path = home / 'inbox' / (kind + '.json')\n",
                               "    path = home / 'inbox' / (envelope['kind'] + '.json')\n")
    root = _tree(tmp_path, {
        "greg/body.py": keyed,
        "greg/renamed_attribute.py": keyed.replace("def send_signed(", "def relay(").replace("write_text", "write_bytes"),
        "greg/attribute_access.py": keyed.replace("def send_signed(", "def relay(").replace("envelope['kind']",
                                                                                           "envelope.kind"),
        "greg/exact.py": keyed.replace("def send_signed(", "def relay("),
    })
    found = body_copy_problems([record], root)
    assert [line.split(":")[0] for line in found] == ["greg/exact.py"]    # the guard runs on this tree


def test_the_fingerprint_erases_a_fresh_copy_once_and_leaves_the_parsed_tree_alone(tmp_path):
    # A nested def is fingerprinted from its own fresh copy, never from a tree an outer erase already rewrote, and
    # the cached parse other guards read stays as it was.
    nested = ("def outer(q: int) -> int:\n    def g(c: int, d: float) -> bool:\n        x = c + 1\n"
              "        y = d * 2.5\n        if x > y:\n            return None\n        return f'{x:>4}' == 'a'\n"
              "    return g(q, q)\n")
    top = ("def h(a, b):\n    x = a + 7\n    y = b * 9.0\n    if x > y:\n        return None\n"
           "    return f'{x:>4}' == 'b'\n")
    root = _tree(tmp_path, {"m.py": nested})
    tree = parse(root / "m.py")
    before = ast.dump(tree, include_attributes=True)
    outer, inner = tree.body[0], tree.body[0].body[0]
    first = fingerprint(outer), fingerprint(inner)
    assert (fingerprint(outer), fingerprint(inner)) == first
    assert ast.dump(parse(root / "m.py"), include_attributes=True) == before
    assert fingerprint(inner) == fingerprint(ast.parse(top).body[0])
    for fn in (outer, inner, ast.parse(top).body[0]):
        erased = ast.Module(body=copy.deepcopy(_function_body(fn)), type_ignores=[])
        once = ast.dump(_Erase().visit(erased))
        assert ast.dump(_Erase().visit(erased)) == once                     # erasing is idempotent
        assert _erased_size(fn) == fingerprint(fn)[0]


def test_a_distinct_entry_cannot_vouch_for_a_module_that_holds_a_copy(tmp_path):
    # The adversary's candidate game, second half: a structural copy recorded as 'distinct'.
    record = copy.deepcopy(next(r for r in load()["function_owner_records"]
                                if r["record_id"] == "OWN-FN-ORGAN-EXCHANGE"))
    record["distinct"].append({"module": "greg.organs2", "qualnames": ["exchange"], "why": "different"})
    record["distinct"].append({"module": "greg.briefs", "qualnames": ["verify_delivery"], "why": "different"})
    root = _tree(tmp_path, {**_real("greg.organs"),
                            "greg/organs2.py": _disguised("greg.organs", "exchange", "exchange"),
                            "greg/briefs.py": "def verify_delivery(action):\n    return None\n"})
    found = distinct_copy_problems([record], root)
    assert len(found) == 1 and found[0].startswith("OWN-FN-ORGAN-EXCHANGE: distinct entry greg.organs2 ")
    assert "greg.organs.exchange" in found[0] and "greg/organs2.py:1" in found[0]
    # a distinct entry exempts nothing: the copy itself is still reported
    assert [line.split(":")[0] for line in body_copy_problems([record], root)] == ["greg/organs2.py"]
    # across records too: another record's distinct entry may not name a module that holds this record's copy
    other = {"record_id": "OWN-FN-OTHER", "function": "o", "owner_status": "CANONICAL", "markers": ["Other"],
             "canonical": [{"module": "greg.body", "qualnames": ["send_signed"]}],
             "distinct": [{"module": "greg.organs2", "qualnames": ["exchange"], "why": "a different exchange"}]}
    plain = {**record, "distinct": [e for e in record["distinct"] if e["module"] != "greg.organs2"]}
    found = distinct_copy_problems([plain, other], root)
    assert len(found) == 1 and found[0].startswith("OWN-FN-OTHER: distinct entry greg.organs2 "), found
    assert "registered in OWN-FN-ORGAN-EXCHANGE" in found[0]


def test_an_undecided_record_takes_no_new_candidate_without_a_pin_change():
    # The adversary's candidate game, first half: a third competing owner added as a candidate of an undecided
    # record passed every check (the alternate half: test_an_undecided_record_takes_no_new_alternate_without_a_pin_change).
    data = load()
    assert pin_problems(data) == []

    def changed(record_id: str, edit) -> list[str]:
        out = copy.deepcopy(data)
        edit(next(r for r in out["function_owner_records"] if r["record_id"] == record_id))
        return [p for p in pin_problems(out) if p.startswith(record_id)]

    new_module = changed("OWN-FN-GOAL-RUNTIME", lambda r: r["candidates"].append(
        {"module": "greg.goal_engine2", "qualnames": ["run"], "side": "C", "evidence": ["new"]}))
    assert any("candidate greg.goal_engine2 [run] is not pinned" in p for p in new_module), new_module
    new_name = changed("OWN-FN-GOAL-RUNTIME", lambda r: next(
        c for c in r["candidates"] if c["module"] == "greg.gravity")["qualnames"].append("rederive"))
    assert any("candidate greg.gravity [select, step, rederive] is not pinned" in p for p in new_name), new_name
    for record_id in FOUNDER_DECISIONS:
        assert changed(record_id, lambda r: r["candidates"].append(
            {"module": "greg.extra", "qualnames": ["x"], "side": "Z", "evidence": ["new"]})), record_id
    # a decided record still takes a new alternate or distinct entry without a pin change
    assert changed("OWN-FN-TEMPORARY-TEAMS", lambda r: r["alternates"].append(
        {"module": "greg.crew", "qualnames": ["form_team"], "status": "ALTERNATE", "reason": "r",
         "retirement_condition": "c"})) == []


def test_the_history_guard_refuses_a_kept_alternate_with_no_live_reason(tmp_path):
    root = _tree(tmp_path, {
        "greg/__init__.py": "", "greg/ladder.py": "REALITY = ('A', 'B')\n", "greg/console.py": (
            "from greg.ladder import REALITY\ndef show():\n    return REALITY\n"),
        "acceptance/__init__.py": "", "acceptance/claims.py": (
            "from greg.ladder import REALITY\ndef crosswalk():\n    return list(REALITY)\ndef other():\n    return 1\n"),
        "acceptance/unrelated.py": "REALITY = ()\ndef crosswalk():\n    return REALITY\n",
        "tests/__init__.py": "", "tests/test_ladder.py": "from greg.ladder import REALITY\ndef test_x():\n    REALITY\n",
    })

    def problems(kept_for=None, status="HISTORICAL", module="greg.ladder", own="CANONICAL"):
        alternate = {"module": module, "qualnames": ["REALITY"], "status": status, "reason": "r",
                     "revival_condition": "c", **({"kept_for": kept_for} if kept_for is not None else {})}
        records = [{"record_id": "OWN-FN-L", "owner_status": own, "alternates": [alternate]},
                   {"record_id": "OWN-FN-OPEN", "owner_status": "NEEDS_FOUNDER_DECISION"}]
        return kept_for_problems(records, root)

    assert problems({"consumer": "acceptance.claims.crosswalk"}) == []
    assert problems({"open_decision": "OWN-FN-L"}, own="NEEDS_FOUNDER_DECISION") == []
    assert problems(status="RETIRED", kept_for={"consumer": "acceptance.claims.crosswalk"}) == []
    assert problems(module="greg.gone") == []                       # gone from the tree: git keeps its history
    assert problems(status="ALTERNATE") == []                       # a live alternate states a retirement condition
    for kept_for, said in ((None, "does not say what keeps it"),
                           ({}, "does not say what keeps it"),
                           ({"consumer": "acceptance.claims.crosswalk", "open_decision": "OWN-FN-OPEN"},
                            "does not say what keeps it"),
                           ({"consumer": "greg.console.show"}, "not a consumer"),
                           ({"consumer": "tests.test_ladder.test_x"}, "not a consumer"),
                           ({"consumer": "acceptance.claims.other"}, "does not name greg.ladder.REALITY"),
                           ({"consumer": "acceptance.unrelated.crosswalk"}, "does not name greg.ladder.REALITY"),
                           ({"consumer": "acceptance.claims.missing"}, "does not exist"),
                           ({"open_decision": "OWN-FN-NONE"}, "not its own record")):
        found = problems(kept_for)
        assert len(found) == 1 and said in found[0], (kept_for, found)
    assert "is not NEEDS_FOUNDER_DECISION" in problems({"open_decision": "OWN-FN-L"})[0]


INBOX_RECORD = {"record_id": "OWN-FN-X", "function": "x", "owner_status": "CANONICAL", "markers": ["Inbox"],
                "canonical": [{"module": "greg.body", "qualnames": ["send_signed"]}]}


def test_a_file_with_an_invalid_escape_parses_without_a_warning_on_any_python(tmp_path, monkeypatch):
    # Python 3.12+ reports an invalid escape as a SyntaxWarning, 3.11 (CI's version) as a DeprecationWarning; the
    # guards parse tracked scripts that have one, and neither category may leak into the test summary.
    root = _tree(tmp_path, {"greg/body.py": OWNER_BODY, "scripts/escape.py": "PATTERN = '\\d+'\n",
                            "greg/escape.py": "PATTERN = '\\w+'\n", "tests/both.py": "X = 1\n"})

    def leaked() -> list[str]:
        return [str(w.message) for w in seen if issubclass(w.category, (SyntaxWarning, DeprecationWarning))]

    with warnings.catch_warnings(record=True) as seen:
        warnings.simplefilter("always")
        parse(root / "greg/escape.py")                             # the parse guards 1-3 read
        found = body_copy_problems([INBOX_RECORD], root)          # guard 4's scan
    assert found == [] and leaked() == []
    # whichever category this interpreter uses, the other one is hidden too
    real_parse = ast.parse

    def both_categories(source, *args, **kwargs):
        warnings.warn("invalid escape sequence (as 3.12+ reports it)", SyntaxWarning)
        warnings.warn("invalid escape sequence (as 3.11 reports it)", DeprecationWarning)
        return real_parse(source, *args, **kwargs)

    monkeypatch.setattr(ast, "parse", both_categories)
    with warnings.catch_warnings(record=True) as seen:
        warnings.simplefilter("always")
        parse(root / "tests/both.py")                              # not scanned by guard 4, so not yet parsed
    assert leaked() == []


def test_the_body_scan_reads_bom_files_follows_links_inside_the_repository_only_and_sees_pycache(tmp_path):
    # A UTF-8 BOM file imports fine, so it parses; a directory symlink is followed when it resolves inside the
    # repository (greg/vendor -> docs/vendor is importable as greg.vendor), never when it leaves it (a venv/ link to
    # an installed site-packages), and a symlink loop ends; a .py file under __pycache__/ is still a file Python can
    # import (pkg.__pycache__.m), so it is scanned like any other.
    copied = _disguised("greg.business_loop", "reconcile", "settle_case")
    outside = tmp_path / "site-packages"
    root = tmp_path / "repo"
    _tree(outside, {"pkg/settle.py": copied})
    _tree(root, {**_real("greg.business_loop"), "tools/win_helper.py": "﻿" + copied,
                 "docs/vendor/settle.py": copied, "pkg/__pycache__/m.py": copied})
    (root / "greg/vendor").symlink_to(root / "docs/vendor", target_is_directory=True)
    (root / "venv").symlink_to(outside, target_is_directory=True)
    (root / "greg/loop").symlink_to(root / "greg", target_is_directory=True)
    (root / "pkg/up").symlink_to(root, target_is_directory=True)
    commerce = next(r for r in load()["function_owner_records"] if r["record_id"] == "OWN-FN-COMMERCE-CLOSURE")
    found = body_copy_problems([commerce], root)
    assert sorted(line.split(":")[0] for line in found) == ["greg/vendor/settle.py", "pkg/__pycache__/m.py",
                                                            "tools/win_helper.py"], found
    listed = [p.relative_to(root).as_posix() for p in runtime_files(root)]
    assert not any(p.startswith(("venv/", "greg/loop/", "pkg/up/")) for p in listed), listed
    # guards 2 and 3 list their packages by the same rule
    assert "greg/vendor/settle.py" in [p.relative_to(root).as_posix() for p in python_files(root, "greg")]


def test_the_body_scan_reads_cortex_evaluation_except_the_files_a_freeze_manifest_seals(tmp_path):
    # GREG imports cortex.evaluation.closure, and new files there are sealed by nothing: only a file whose bytes a
    # cortex/evaluation/freeze-*.json manifest hashes (inputs.code) is a frozen instrument, and only under
    # cortex/evaluation/. A file the manifest names with another hash was edited after the freeze and is scanned.
    copied = _disguised("foundry.systems.teams", "form", "convene")
    sealed = _disguised("foundry.systems.teams", "form", "sealed_convene")

    def digest(text: str) -> str:
        return "sha256:" + hashlib.sha256(text.encode()).hexdigest()

    root = _tree(tmp_path, {
        **_real("foundry.systems.teams"),
        "cortex/evaluation/settle.py": copied,                 # new since every freeze
        "cortex/evaluation/sealed.py": sealed,                 # the bytes a manifest hashes
        "cortex/evaluation/edited.py": copied,                 # named by a manifest, hashed when it held other text
        "cortex/evaluation/suites/runner.py": copied,          # below it, named by no top-level manifest
        "cortex/other.py": copied,
        "foundry/systems/team_copy.py": copied,                # a manifest seals nothing outside cortex/evaluation/
        "cortex/evaluation/freeze-v9.json": json.dumps({"inputs": {"code": {
            "cortex/evaluation/sealed.py": digest(sealed), "cortex/evaluation/edited.py": digest("X = 1\n"),
            "foundry/systems/team_copy.py": digest(copied)}}}),
        "cortex/evaluation/freeze-broken.json": "{not json",
    })
    teams = next(r for r in load()["function_owner_records"] if r["record_id"] == "OWN-FN-TEMPORARY-TEAMS")
    # the test's own SEALED: each path with the digest a manifest records, as the literal pins the real ones
    pinned = {"cortex/evaluation/sealed.py": digest(sealed), "cortex/evaluation/edited.py": digest("X = 1\n"),
              "foundry/systems/team_copy.py": digest(copied)}
    found = body_copy_problems([teams], root, sealed=pinned)
    assert sorted(line.split(":")[0] for line in found) == [
        "cortex/evaluation/edited.py", "cortex/evaluation/settle.py", "cortex/evaluation/suites/runner.py",
        "cortex/other.py", "foundry/systems/team_copy.py"], found
    assert sealed_files(root, pinned) == {"cortex/evaluation/sealed.py"}
    stale = sealed_problems(root, pinned)
    assert sorted(line.split()[1] for line in stale) == ["cortex/evaluation/edited.py", "foundry/systems/team_copy.py"]
    # a pinned path is skipped only for the pinned bytes and only when a manifest records them
    assert sealed_files(root, {"cortex/evaluation/sealed.py": digest(copied)}) == frozenset()
    unrecorded_seal = _tree(tmp_path / "no-manifest", {"cortex/evaluation/sealed.py": sealed})
    assert sealed_files(unrecorded_seal, {"cortex/evaluation/sealed.py": digest(sealed)}) == frozenset()


# A registered body with a local import under an alias, a plain import, a nested def and an except-as name.
DEEP_BODY = ("def collect(home, names):\n"
             "    import json as codec\n"
             "    import os\n"
             "    found = {}\n"
             "    def load(name):\n"
             "        return codec.loads((home / name).read_text())\n"
             "    for name in names:\n"
             "        try:\n"
             "            found[name] = load(name)\n"
             "        except (OSError, ValueError) as error:\n"
             "            found[name] = {'error': str(error), 'pid': os.getpid()}\n"
             "    return found\n")
DEEP_RECORD = {"record_id": "OWN-FN-D", "function": "d", "owner_status": "CANONICAL", "markers": ["Collect"],
               "canonical": [{"module": "greg.collect", "qualnames": ["collect"]}]}


def _variant(*edits: tuple[str, str], name: str = "gather") -> str:
    text = DEEP_BODY.replace("def collect(", f"def {name}(")
    for old, new in edits:
        assert text.count(old) == 1, old
        text = text.replace(old, new)
    return text


def test_the_body_guard_ignores_one_node_edits_pass_no_op_constants_annotations_and_import_aliases(tmp_path):
    # Before comparing, the fingerprint drops `pass` and no-op constant statements, reads an annotated assignment as
    # the plain assignment (a bare annotation is dropped) and erases every import alias, added or renamed. Nothing
    # else is normalised: `_unused = 0`, a renamed call keyword or an `if True:` wrapper is still a different body.
    edits = {
        "with_pass": ("    found = {}\n", "    found = {}\n    pass\n"),
        "no_op_string": ("    found = {}\n", "    found = {}\n    'collected below'\n"),
        "no_op_ellipsis": ("    return found\n", "    ...\n    return found\n"),
        "annotated": ("    found = {}\n", "    found: dict = {}\n"),
        "bare_annotation": ("    found = {}\n", "    found = {}\n    total: int\n"),
        "alias_added": ("    import os\n", "    import os as system\n"),
    }
    root = _tree(tmp_path, {"greg/collect.py": DEEP_BODY,
                            **{f"greg/{key}.py": _variant(edit) for key, edit in edits.items()},
                            "greg/assigned.py": _variant(("    found = {}\n", "    found = {}\n    _unused = 0\n")),
                            "greg/wrapped_if.py": _variant(("    return found\n", "    if True:\n        return found\n"))})
    found = body_copy_problems([DEEP_RECORD], root)
    assert sorted(line.split(":")[0] for line in found) == sorted(f"greg/{key}.py" for key in edits), found
    for key in edits:
        fn = parse(root / f"greg/{key}.py").body[0]
        assert _erased_size(fn) == fingerprint(fn)[0] == fingerprint(parse(root / "greg/collect.py").body[0])[0], key


def test_an_undecided_record_takes_no_new_alternate_without_a_pin_change():
    # Skeptic regression 1 (MW-C review, 2026-11-21): a copy of an owner's body joined the undecided goal runtime as a
    # live ALTERNATE (egregore.goal_engine2 advance, a disguised greg.gravity.step) and every check passed. The
    # alternates of a NEEDS_FOUNDER_DECISION record are pinned exactly, as its candidates are.
    data = load()

    def changed(record_id: str, edit) -> list[str]:
        out = copy.deepcopy(data)
        edit(next(r for r in out["function_owner_records"] if r["record_id"] == record_id))
        return [p for p in pin_problems(out) if p.startswith(record_id)]

    engine = {"module": "egregore.goal_engine2", "qualnames": ["advance"], "status": "ALTERNATE",
              "reason": "a third goal runtime", "retirement_condition": "when the founder rules on the goal runtime"}
    new_module = changed("OWN-FN-GOAL-RUNTIME", lambda r: r["alternates"].append(engine))
    assert any("alternate egregore.goal_engine2 [advance] ALTERNATE is not pinned" in p for p in new_module), new_module
    new_name = changed("OWN-FN-GOAL-RUNTIME", lambda r: r["alternates"][0]["qualnames"].append("chase_v2"))
    assert any("alternate egregore.goal_chase [GoalChase, chase_v2] RESEARCH is not pinned" in p
               for p in new_name), new_name
    whole = changed("OWN-FN-STATUS-EVIDENCE-LADDER", lambda r: r["alternates"][0].update(qualnames=[]))
    assert any("alternate greg.mission_control (whole module) HISTORICAL is not pinned" in p for p in whole), whole
    for record_id in FOUNDER_DECISIONS:
        assert changed(record_id, lambda r: r.setdefault("alternates", []).append(
            {**engine, "module": "greg.extra", "qualnames": ["x"]})), record_id


def test_a_registered_body_is_exempt_only_at_its_own_location(tmp_path):
    # Skeptic regression 1, second half: guard 4 exempted every canonical, candidate and alternate module of a record
    # for any of the record's bodies, so a copy appended to an existing ALTERNATE module passed with no registry edit.
    # A body is exempt only at its own registered module and qualname: anywhere else, inside or outside the record,
    # it is a copy.
    data = {r["record_id"]: r for r in load()["function_owner_records"]}
    commerce, goal = data["OWN-FN-COMMERCE-CLOSURE"], data["OWN-FN-GOAL-RUNTIME"]
    real = _real("business.commercial_loop", "greg.business_loop", "greg.gravity", "egregore.goal_chase")
    root = _tree(tmp_path, {
        **real,
        # appended to an existing ALTERNATE module of the commerce record, no registry edit
        "business/commercial_loop.py": real["business/commercial_loop.py"] + "\n\n"
                                       + _disguised("greg.business_loop", "reconcile", "settle"),
        # beside the owner in its own canonical module
        "greg/business_loop.py": real["greg/business_loop.py"] + "\n\n"
                                 + _disguised("greg.business_loop", "reconcile", "reconcile_v1"),
        # in the undecided goal runtime's ALTERNATE module, a copy of its candidate greg.gravity.step
        "egregore/goal_chase.py": real["egregore/goal_chase.py"] + "\n\n"
                                  + _disguised("greg.gravity", "step", "advance"),
    })
    found = body_copy_problems([commerce, goal], root)
    where = {line.split(" defines ")[0].split(":")[0] + " " + line.split(" defines ")[1].split(",")[0]
             for line in found}
    assert where == {"business/commercial_loop.py 'settle'", "greg/business_loop.py 'reconcile_v1'",
                     "egregore/goal_chase.py 'advance'"}, found
    # the registered originals are never reported
    assert not any(" defines 'reconcile'," in line or " defines 'step'," in line for line in found)


def test_two_registered_locations_with_one_body_fail(tmp_path):
    # Registering a copy does not make it an owner: two registered entries whose bodies share one fingerprint fail,
    # so a copy can be neither left unrecorded nor recorded (the skeptic's egregore.goal_engine2 advance, recorded as
    # an ALTERNATE, is such a pair with greg.gravity.step). The same location named twice (by two records) is one.
    twin = OWNER_BODY.replace("def send_signed(", "def send_signed_twin(")
    records = [{**INBOX_RECORD, "canonical": [{"module": "greg.body", "qualnames": ["send_signed"]}]},
               {"record_id": "OWN-FN-Y", "function": "y", "owner_status": "CANONICAL", "markers": ["Y"],
                "canonical": [{"module": "greg.body", "qualnames": ["send_signed"]}],
                "alternates": [{"module": "greg.relay", "qualnames": ["send_signed_twin"], "status": "ALTERNATE",
                                "reason": "r", "retirement_condition": "c"}]}]
    root = _tree(tmp_path, {"greg/body.py": OWNER_BODY, "greg/relay.py": twin})
    found = registered_twin_problems(records, root)
    assert len(found) == 1 and "greg.body.send_signed" in found[0] and "greg.relay.send_signed_twin" in found[0], found
    assert registered_twin_problems(records[:1] + [{**records[1], "alternates": []}], root) == []


def test_a_pinned_exemption_clears_exactly_one_location_and_a_stale_one_fails(tmp_path):
    # Skeptic regression 6: a false positive of guard 4 (a different function whose erased body equals a small
    # registered one) had no reviewed escape hatch. BODY_EXEMPTIONS, a literal in this file and empty on 2026-11-21,
    # maps the location (module, qualname) to the registered body it resembles and the reason; an entry clears that
    # location for that body and nothing else, and one that no longer matches a copy fails.
    relay = OWNER_BODY.replace("def send_signed(", "def relay(")
    root = _tree(tmp_path, {"greg/body.py": OWNER_BODY, "greg/a.py": relay + "\n\n" + relay.replace(
        "def relay(", "def forward("), "greg/b.py": relay})
    exempt = {("greg.a", "relay"): ("greg.body.send_signed", "a different function: test fixture")}
    found = body_copy_problems([INBOX_RECORD], root, exemptions=exempt)
    assert sorted(line.split(" defines ")[0] for line in found) == ["greg/a.py:11", "greg/b.py:1"], found
    # an entry for another registered body clears nothing there, and says it is stale
    other = {("greg.a", "relay"): ("greg.remote.handle", "a different function")}
    found = body_copy_problems([INBOX_RECORD], root, exemptions=other)
    assert sum(line.startswith(("greg/a.py:", "greg/b.py:")) for line in found) == 3, found
    assert any("BODY_EXEMPTIONS ('greg.a', 'relay')" in line and "no longer matches" in line for line in found), found
    # a stale entry, or one without a reason, fails
    stale = body_copy_problems([INBOX_RECORD], root, exemptions={**exempt, ("greg.gone", "x"): (
        "greg.body.send_signed", "gone")})
    assert any("BODY_EXEMPTIONS ('greg.gone', 'x')" in line and "no longer matches" in line for line in stale), stale
    reasonless = body_copy_problems([INBOX_RECORD], root, exemptions={("greg.a", "relay"): ("greg.body.send_signed", "")})
    assert any("BODY_EXEMPTIONS ('greg.a', 'relay')" in line and "reason" in line for line in reasonless), reasonless
    # an exempted location is not a copy to the distinct check either
    vouched = {**INBOX_RECORD, "distinct": [{"module": "greg.a", "qualnames": ["relay"], "why": "different"}]}
    assert len(distinct_copy_problems([vouched], root, exemptions=exempt)) == 1        # forward is still a copy
    assert BODY_EXEMPTIONS == {} or all(reason for _, reason in BODY_EXEMPTIONS.values())


def test_kept_for_names_the_alternates_own_open_record_and_a_consumer_outside_tests_and_tools(tmp_path):
    # Skeptic regression 5: kept_for was satisfied by naming any of the three long-open founder decisions, or by a
    # consumer in docs/, scripts/ci/ or a conftest.py. open_decision must be the alternate's own record, still
    # undecided; a consumer may not sit under tests/, greg/, docs/ or scripts/ci/, or in any conftest.py. A STATED
    # LIMIT, recorded as passing: a dead two-line shim anywhere else that imports and names the object still passes.
    reads = "from greg.ladder import REALITY\ndef keep():\n    return REALITY\n"
    root = _tree(tmp_path, {
        "greg/__init__.py": "", "greg/ladder.py": "REALITY = ('A', 'B')\n",
        "docs/tools/keep.py": reads, "scripts/ci/keep.py": reads, "conftest.py": reads,
        "acceptance/conftest.py": reads, "scripts/keep_reality.py": reads,
    })

    def problems(kept_for, own="NEEDS_FOUNDER_DECISION"):
        alternate = {"module": "greg.ladder", "qualnames": ["REALITY"], "status": "HISTORICAL", "reason": "r",
                     "revival_condition": "c", "kept_for": kept_for}
        records = [{"record_id": "OWN-FN-L", "owner_status": own, "alternates": [alternate]},
                   {"record_id": "OWN-FN-OPEN", "owner_status": "NEEDS_FOUNDER_DECISION"}]
        return kept_for_problems(records, root)

    assert problems({"open_decision": "OWN-FN-L"}) == []
    for kept_for, own, said in (({"open_decision": "OWN-FN-OPEN"}, "NEEDS_FOUNDER_DECISION", "not its own record"),
                                ({"open_decision": "OWN-FN-OPEN"}, "CANONICAL", "not its own record"),
                                ({"open_decision": "OWN-FN-L"}, "CANONICAL", "is not NEEDS_FOUNDER_DECISION"),
                                ({"consumer": "docs.tools.keep.keep"}, "CANONICAL", "not a consumer"),
                                ({"consumer": "scripts.ci.keep.keep"}, "CANONICAL", "not a consumer"),
                                ({"consumer": "conftest.keep"}, "CANONICAL", "not a consumer"),
                                ({"consumer": "acceptance.conftest.keep"}, "CANONICAL", "not a consumer")):
        found = problems(kept_for, own)
        assert len(found) == 1 and said in found[0], (kept_for, own, found)
    assert problems({"consumer": "scripts.keep_reality.keep"}, "CANONICAL") == []      # the stated limit


# -- MW-C round 4: what the review of 7c2b39e5 found ---------------------------------------------------------------

WU13_LADDER = {"module": "governance.reality_ladder", "qualnames": ["REALITY_LADDER"],
               "why": "the governance ladder of section 56 for policy claims, not a status claim's evidence level"}


def test_an_undecided_record_takes_no_new_or_changed_entry_of_any_role_without_a_pin_change():
    # Round 4, N1 and N2: a competing owner joined an undecided record as a 'distinct' entry (WU-13's REALITY_LADDER on
    # the evidence ladder; a verbatim copy of the candidate class GoalGravityLoop as a third goal runtime), and an
    # alternate's status changed (GoalChase RESEARCH to a live ALTERNATE; REALITY revived from HISTORICAL), with no
    # pin change. The whole entry set of every NEEDS_FOUNDER_DECISION record is one literal, UNDECIDED_ENTRIES: any
    # entry or field added, removed or changed fails.
    data = load()
    assert pin_problems(data) == []

    def changed(record_id: str, edit) -> list[str]:
        out = copy.deepcopy(data)
        edit(next(r for r in out["function_owner_records"] if r["record_id"] == record_id))
        return [p for p in pin_problems(out) if p.startswith(record_id)]

    def alternate(r, module):
        return next(e for e in r["alternates"] if e["module"] == module)

    a1 = changed("OWN-FN-STATUS-EVIDENCE-LADDER", lambda r: r["distinct"].append(dict(WU13_LADDER)))
    assert any("distinct entry governance.reality_ladder [REALITY_LADDER] is not pinned" in p for p in a1), a1
    a2 = changed("OWN-FN-GOAL-RUNTIME", lambda r: r["distinct"].append(
        {"module": "egregore.goal_runtime", "qualnames": ["GoalRuntime"], "why": "a mission-scoped runtime"}))
    assert any("distinct entry egregore.goal_runtime [GoalRuntime] is not pinned" in p for p in a2), a2
    b1 = changed("OWN-FN-GOAL-RUNTIME", lambda r: alternate(r, "egregore.goal_chase").update(
        status="ALTERNATE", retirement_condition="when the founder rules on the goal runtime"))
    assert any("alternate egregore.goal_chase [GoalChase] ALTERNATE is not pinned" in p for p in b1), b1
    assert any("pinned alternate egregore.goal_chase [GoalChase] RESEARCH is not in the registry" in p for p in b1), b1
    b2 = changed("OWN-FN-STATUS-EVIDENCE-LADDER", lambda r: alternate(r, "greg.mission_control").update(
        status="ALTERNATE", retirement_condition="when the founder picks the ladder", kept_for=None))
    assert any("alternate greg.mission_control [REALITY] ALTERNATE is not pinned" in p for p in b2), b2
    # any other field, prose included, and an entry removed or reordered
    for record_id, edit, said in (
            ("OWN-FN-AUTONOMY-LEVELS", lambda r: r["distinct"][1].update(why="forecast levels"), "distinct entry"),
            ("OWN-FN-AUTONOMY-LEVELS", lambda r: r["candidates"][0]["evidence"].append("new"), "candidate"),
            ("OWN-FN-AUTONOMY-LEVELS", lambda r: r["candidates"][1].pop("side"), "candidate"),
            ("OWN-FN-GOAL-RUNTIME", lambda r: r["distinct"].pop(), "pinned distinct entry"),
            ("OWN-FN-GOAL-RUNTIME", lambda r: r["distinct"].reverse(), "reordered or repeated"),
            ("OWN-FN-STATUS-EVIDENCE-LADDER", lambda r: alternate(r, "greg.mission_control").update(
                kept_for={"open_decision": "OWN-FN-STATUS-EVIDENCE-LADDER"}), "alternate"),
            ("OWN-FN-STATUS-EVIDENCE-LADDER", lambda r: r["canonical"].append(
                {"module": "acceptance", "qualnames": ["LADDER"]}), "canonical entry")):
        found = changed(record_id, edit)
        assert any(said in p for p in found), (record_id, said, found)
    # a record that becomes undecided, or a new undecided record, is not pinned yet
    flipped = changed("OWN-FN-REGRESSION-CLOSING", lambda r: r.update(owner_status="NEEDS_FOUNDER_DECISION"))
    assert any("is NEEDS_FOUNDER_DECISION and its entries are not pinned" in p for p in flipped), flipped
    # a decided record still takes a new distinct entry or alternate without a pin change
    assert changed("OWN-FN-TEMPORARY-TEAMS", lambda r: r["distinct"].append(
        {"module": "greg.crew", "qualnames": ["act"], "why": "a different act"})) == []
    assert set(UNDECIDED_ENTRIES) == FOUNDER_DECISIONS


def test_guard_3_reports_a_structural_copy_even_where_a_distinct_entry_names_it(tmp_path):
    # Round 4, N1: guard 3 skipped every check, the structural-copy check included, for a (module, name) a distinct
    # entry named, so an exact copy of a registered class recorded as 'distinct' passed. A distinct entry still
    # exempts a name (the marker and exact-name checks: that is what it is for), never a structural copy.
    owner_class = ("class Relay:\n    def __init__(self, home, key):\n        self.home, self.key = home, key\n"
                   "    def send(self, kind, body):\n        path = self.home / 'inbox' / (kind + '.json')\n"
                   "        path.write_text(str({'kind': kind, 'body': body, 'key': self.key}))\n        return path\n")
    record = {"record_id": "OWN-FN-X", "function": "x", "owner_status": "CANONICAL", "markers": ["Inbox"],
              "canonical": [{"module": "greg.body", "qualnames": ["send_signed", "Relay"]}],
              "distinct": [{"module": "greg.vouched", "qualnames": ["forward_envelope", "InboxRelay"],
                            "why": "says it is different"},
                           {"module": "greg.named", "qualnames": ["InboxRelay"], "why": "a different relay"}]}
    root = _tree(tmp_path, {
        "greg/__init__.py": "", "greg/body.py": OWNER_BODY + owner_class,
        "greg/vouched.py": OWNER_BODY.replace("def send_signed(", "def forward_envelope(")
                           + owner_class.replace("class Relay:", "class InboxRelay:"),
        "greg/named.py": "class InboxRelay:\n    pass\n",
    })
    found = unrecorded([record], root, packages=("greg",))
    assert sorted(line.split(" defines ")[1].split(",")[0] for line in found) == ["'InboxRelay'", "'forward_envelope'"]
    assert all(line.startswith("greg/vouched.py:") and "a structural copy of greg.body." in line for line in found)


def _sha(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode()).hexdigest()


def test_a_freeze_manifest_seals_only_the_files_and_bytes_the_test_pins(tmp_path):
    # Round 4, N3: the seal was self-issued. Any new cortex/evaluation/freeze-*.json written in the same diff hid the
    # files whose bytes it hashed, a copy GREG imports included. A file is skipped only when SEALED (a literal here)
    # names it with its current sha256 and a manifest records that sha256 for it; a new manifest seals nothing, and a
    # pinned file edited and re-sealed by a new manifest is scanned.
    copied = _disguised("foundry.systems.teams", "form", "convene")
    root = _tree(tmp_path, {
        **_real("foundry.systems.teams"),
        "cortex/evaluation/planted.py": copied,                # new, sealed by a manifest written in the same diff
        "cortex/evaluation/arms.py": copied,                   # a SEALED path, edited, re-sealed by the same manifest
        "cortex/evaluation/freeze-v0.2.4.json": json.dumps({"inputs": {"code": {
            "cortex/evaluation/planted.py": _sha(copied), "cortex/evaluation/arms.py": _sha(copied)}}}),
        "greg/settle_view.py": "from cortex.evaluation.planted import convene\n",
    })
    teams = next(r for r in load()["function_owner_records"] if r["record_id"] == "OWN-FN-TEMPORARY-TEAMS")
    found = body_copy_problems([teams], root)
    assert sorted(line.split(":")[0] for line in found) == ["cortex/evaluation/arms.py",
                                                            "cortex/evaluation/planted.py"], found
    assert sealed_files(root) == frozenset()


def test_a_registered_qualname_names_its_last_binding_as_python_does(tmp_path):
    # Round 4, N4: _function_node took the FIRST def of a qualname. Two @overload stubs before greg.remote.handle made
    # guard 4 fingerprint a stub's empty body (Python binds the last def), so a copy of the real body passed. Every
    # resolver (guard 1's has_qualname, guard 3's definition_node, guard 4's _function_node) now takes the last
    # binding of each part; a name whose last binding is not a def (an assignment, an import) is not a def.
    real = OWNER_BODY
    stubs = ("from typing import overload\n\n\n@overload\ndef send_signed(home, key, kind, body): ...\n\n\n"
             "@overload\ndef send_signed(home, key, kind, body, extra): ...\n\n\n")
    root = _tree(tmp_path, {
        "greg/body.py": stubs + real,
        "greg/relay.py": real.replace("def send_signed(", "def relay("),
        "greg/rebound.py": "def relay():\n    return 0\n\n\nrelay = print\n"
                           + "class Box:\n    def open(self):\n        return 1\n    def open(self):\n        return 2\n",
    })
    found = body_copy_problems([INBOX_RECORD], root)
    assert [line.split(" defines ")[0] for line in found] == ["greg/relay.py:1"], found
    node = _function_node("greg.body", "send_signed", root)
    assert node is not None and fingerprint(node) == fingerprint(ast.parse(OWNER_BODY).body[0])
    assert _function_node("greg.rebound", "relay", root) is None and definition_node("greg.rebound", "relay", root) is None
    assert has_qualname("greg.rebound", "relay", root) and has_qualname("greg.rebound", "Box.open", root)
    assert _function_node("greg.rebound", "Box.open", root).body[0].value.value == 2


def test_the_set_of_compared_registered_bodies_is_pinned(tmp_path):
    # Round 4, N4: nothing pinned WHICH registered bodies guard 4 compares, only a floor of 20 of 27. Extracting a
    # helper (handle delegating to _handle) or adding overload stubs dropped greg.remote.handle out of the comparison
    # silently, and a copy of its body then passed. COMPARED is the exact set of (module, qualname) locations; one
    # leaving the comparison or joining it fails until COMPARED changes in the same reviewed diff.
    records = load()["function_owner_records"]
    assert compared_problems(records) == []
    delegated = OWNER_BODY.replace("def send_signed(home, key, kind, body):\n",
                                   "def send_signed(home, key, kind, body):\n    return _send(home, key, kind, body)\n\n\n"
                                   "def _send(home, key, kind, body):\n")
    root = _tree(tmp_path, {"greg/body.py": delegated, "greg/relay.py": OWNER_BODY.replace("def send_signed(", "def relay(")})
    gone = compared_problems([INBOX_RECORD], root, compared=frozenset({("greg.body", "send_signed")}))
    assert len(gone) == 1 and "greg.body.send_signed is pinned in COMPARED and is no longer compared" in gone[0], gone
    assert body_copy_problems([INBOX_RECORD], root) == []        # which is why the set is pinned: the copy passes
    joined = compared_problems([INBOX_RECORD], _tree(tmp_path / "plain", {"greg/body.py": OWNER_BODY}), compared=frozenset())
    assert len(joined) == 1 and "greg.body.send_signed is compared and not pinned in COMPARED" in joined[0], joined


def test_a_package_shadows_a_module_of_the_same_name_and_no_two_files_share_a_module_name(tmp_path):
    # Round 4, N5: module_file preferred greg/business_loop.py to greg/business_loop/__init__.py, the opposite of
    # Python, so with both present every guard read the shadowed dead file and a copy in the live package counted as
    # the body's own location. module_file now resolves the package first and fails when both exist; and two runtime
    # files with one module name (a top-level greg.business_loop.py beside greg/business_loop.py) fail guard 4.
    import pytest

    commerce = next(r for r in load()["function_owner_records"] if r["record_id"] == "OWN-FN-COMMERCE-CLOSURE")
    copied = _disguised("greg.business_loop", "reconcile", "reconcile")
    both = _tree(tmp_path / "both", {**_real("greg.business_loop"), "greg/__init__.py": "",
                                     "greg/business_loop/__init__.py": copied})
    with pytest.raises(AmbiguousModule, match="greg.business_loop is both greg/business_loop.py and "
                                              "greg/business_loop/__init__.py"):
        body_copy_problems([commerce], both)
    package = _tree(tmp_path / "package", {"greg/__init__.py": "", "greg/business_loop/__init__.py": copied})
    assert module_file("greg.business_loop", package) == package / "greg/business_loop/__init__.py"
    dotted = _tree(tmp_path / "dotted", {**_real("greg.business_loop"), "greg.business_loop.py": copied})
    found = body_copy_problems([commerce], dotted)
    assert len(found) == 1 and "greg.business_loop.py and greg/business_loop.py are one module name" in found[0], found
    assert module_name_problems(list(runtime_files())) == []


def test_the_walk_reads_each_real_file_once_and_follows_file_links_anywhere(tmp_path):
    # Round 4, N6: the walk followed in-repository directory links without de-duplicating by real path, so a sibling
    # link (examples/app/greg -> greg) made greg's own reconcile a copy of itself, and greg/foundry_compat -> foundry
    # made guard 3 report foundry.systems.teams' own definitions. Each real file is now read once: at its real path
    # when the scan lists it there, and at a link path only when the target is not scanned where it lies (docs/,
    # tests/, a sealed file, outside the packages a guard scans). N7, a stated behaviour: a FILE link is followed
    # wherever it points, out of the repository too, so the scan reads more, not less; two links to one file are
    # read once, at the first link path.
    recs = [next(r for r in load()["function_owner_records"] if r["record_id"] == rid)
            for rid in ("OWN-FN-COMMERCE-CLOSURE", "OWN-FN-TEMPORARY-TEAMS")]
    copied = _disguised("greg.business_loop", "reconcile", "settle_case")
    root, outside = tmp_path / "repo", tmp_path / "outside"
    _tree(root, {**_real("greg.business_loop", "foundry.systems.teams"), "greg/__init__.py": "",
                 "docs/vendor/settle.py": copied})
    _tree(outside, {"settle.py": copied, "broken.py": "def x(:\n"})
    (root / "examples/app").mkdir(parents=True)
    (root / "examples/app/greg").symlink_to("../../greg", target_is_directory=True)
    (root / "greg/foundry_compat").symlink_to("../foundry", target_is_directory=True)
    (root / "greg/vendor").symlink_to(root / "docs/vendor", target_is_directory=True)
    (root / "tools").mkdir()
    (root / "tools/settle.py").symlink_to(outside / "settle.py")
    (root / "tools/settle_again.py").symlink_to(outside / "settle.py")
    (root / "tools/broken.py").symlink_to(outside / "broken.py")
    found = body_copy_problems(recs, root)
    assert sorted(line.split(" ")[0].split(":")[0] for line in found) == ["greg/vendor/settle.py", "tools/broken.py",
                                                                         "tools/settle.py"], found
    listed = [p.relative_to(root).as_posix() for p in runtime_files(root)]
    assert not any(p.startswith(("examples/app/greg/", "greg/foundry_compat/")) for p in listed), listed
    assert "greg/business_loop.py" in listed and "foundry/systems/teams.py" in listed
    # guards 2 and 3 list their packages by the same rule: a link to a package the guard also scans is read there
    assert unrecorded(recs, root, packages=("greg", "foundry")) == []
    in_greg = [p.relative_to(root).as_posix() for p in python_files(root, "greg")]
    assert "greg/foundry_compat/systems/teams.py" in in_greg and "greg/vendor/settle.py" in in_greg
    assert not any(p.startswith("greg/foundry_compat/") for p in
                   (q.relative_to(root).as_posix() for q in python_files(root, "greg", "foundry")))


# -- MW-C round 6: what the review of 79ef5742 found ---------------------------------------------------------------

def test_every_registered_qualname_has_one_binding_and_its_module_no_computed_binding():
    # Round 6, B1, on today's tree: each of the 50 registered qualnames is bound once at its level, and no module that
    # holds one has a star import or a namespace write with a computed name.
    records = load()["function_owner_records"]
    registered = {(e["module"], q) for r in records for role, e in entries(r) if role != "distinct"
                  for q in e.get("qualnames") or []}
    assert len(registered) == 50
    assert binding_problems(records) == []


def test_a_decoy_rebinding_or_star_import_of_a_registered_qualname_fails(tmp_path):
    # Round 6, B1 (verifier N4/caseH3, skeptic r3_alias, r9_rebind and rstar): the guards resolve a name statically, to
    # its last binding, so a decoy def in a branch that never runs, placed after the real def, was what guard 4 read,
    # and a copy of the real body then passed; a registered class rebound after its class statement dropped out of
    # guard 3's comparison; a star import could replace the registered def at run time. Every one is now a second
    # binding, or a computed one, and fails.
    decoy = ("def send_signed(home, key, kind, body):\n    rows = [home, key, kind]\n"
             "    for row in body or ():\n        rows.append(str(row).lower())\n    return {'rows': rows}\n")
    indented = "".join("    " + line + "\n" for line in decoy.splitlines())
    variants = {
        "if_false": "if False:\n" + indented,
        "type_checking": "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n" + indented,
        "except_import": "try:\n    pass\nexcept ImportError:\n" + indented,
        "overload_stub": "from typing import overload\n@overload\ndef send_signed(home, key, kind, body): ...\n",
        "rebound": "def _wrap(f):\n    return f\nsend_signed = _wrap(send_signed)\n",
        "imported": "try:\n    from greg.native import send_signed\nexcept ImportError:\n    pass\n",
        "loop_target": "for send_signed in ():\n    pass\n",
        "global_declared": "def install(f):\n    global send_signed\n    send_signed = f\n",
        "star_import": "try:\n    from greg.native import *\nexcept ImportError:\n    pass\n",
        "globals_update": "import greg.native as _native\nglobals().update(vars(_native))\n",
        "globals_computed_key": "for _name in ('send_signed',):\n    globals()[_name] = print\n",
        "vars_update": "import greg.native as _native\nvars().update(_native.__dict__)\n",
    }
    method = ("class Relay:\n    def send(self, kind):\n        return kind\n"
              "    def send(self, kind, body):\n        return body\n")
    controls = {   # one binding each; computed namespace writes only in a function's own scope or with literal names
        "plain": OWNER_BODY,
        "decorated": "import functools\n" + OWNER_BODY.replace("def send_signed(", "@functools.lru_cache\ndef send_signed("),
        "local_namespace": OWNER_BODY + "def g(values):\n    locals().update(values)\n    vars().update(values)\n",
        "literal_globals": OWNER_BODY + "globals().update({'OTHER': 1}, MORE=2)\nglobals().setdefault('LAST', 3)\n",
    }
    root = _tree(tmp_path, {"greg/__init__.py": "", "greg/native.py": decoy, "greg/unnamed.py": "from greg.native import *\n",
                            **{f"greg/{key}.py": OWNER_BODY + "\n\n" + text for key, text in variants.items()},
                            **{f"greg/{key}.py": text for key, text in controls.items()},
                            "greg/methods.py": method, "greg/patched.py": method.split("    def send(self, kind, body")[0]
                            + "Relay.send = print\n"})

    def record(module, qualname="send_signed"):
        return {"record_id": f"OWN-FN-{module.upper()}", "canonical": [{"module": f"greg.{module}",
                                                                         "qualnames": [qualname]}]}

    for key in variants:
        found = binding_problems([record(key)], root)
        assert len(found) == 1, (key, found)
        said = ("star import or a namespace write" if key in ("star_import", "globals_update", "globals_computed_key",
                                                               "vars_update") else "is bound 2 times at its level")
        assert said in found[0] and found[0].startswith(f"greg/{key}.py"), (key, found)
    for key in controls:
        assert binding_problems([record(key)], root) == [], key
    assert "Relay.send is bound 2 times" in " ".join(binding_problems([record("methods", "Relay.send")], root))
    assert "Relay.send is bound 2 times" in " ".join(binding_problems([record("patched", "Relay.send")], root))
    assert binding_problems([record("native")], root) == []       # greg/unnamed.py's star import: not a registered module
    # why the rule is needed: guard 4 reads the dead-branch decoy, so a copy of the real body passes guard 4 alone
    copy_root = _tree(tmp_path / "copy", {"greg/body.py": OWNER_BODY + "\n\n" + variants["if_false"],
                                          "tools/relay.py": OWNER_BODY.replace("def send_signed(", "def relay(")})
    assert body_copy_problems([INBOX_RECORD], copy_root) == []
    assert binding_problems([INBOX_RECORD], copy_root) != []


def test_a_new_record_fails_until_it_is_pinned():
    # Round 6, B2 (verifier X1/X2, skeptic R4): a NEW decided record could name an undecided record's candidate as its
    # canonical owner and the rival candidate as its ALTERNATE, with no ruling and no test change, and every test
    # passed. Every record must now be in PINNED, so a new record is a reviewed change to this file.
    data = load()
    assert {r["record_id"] for r in data["function_owner_records"]} == set(PINNED)
    adopted = {"record_id": "OWN-FN-GOAL-RUNTIME-ADOPTED", "function": "the goal runtime, adopted",
               "effect": "one goal runtime", "owner_status": "CANONICAL", "markers": ["GoalRuntime"],
               "migration_path": "none", "evidence": ["adopted"],
               "canonical": [{"module": "greg.goal_gravity", "qualnames": ["tick"]}],
               "alternates": [{"module": "greg.gravity", "qualnames": ["select", "step"], "status": "ALTERNATE",
                               "reason": "the rival", "retirement_condition": "never"}]}
    changed = copy.deepcopy(data)
    changed["function_owner_records"].append(adopted)
    assert shape_problems(changed) == []                    # what passed before: the shape check is all it met
    found = pin_problems(changed)
    assert found == ["OWN-FN-GOAL-RUNTIME-ADOPTED: the record is not pinned in tests/unit/test_canonical_owner_guard.py "
                     "(PINNED); a record joins the registry only in a reviewed change that adds it to PINNED, so that "
                     "no record can name another's implementation as its owner or alternate unseen"], found
    pinned = {**PINNED, adopted["record_id"]: {"canonical": {"greg.goal_gravity": ("tick",)}, "candidates": {},
                                               "alternates": {"greg.gravity": ("select", "step")}, "distinct": {}}}
    assert pin_problems(changed, pinned=pinned) == []       # the reviewed change; review must then judge it


def _class_source(module: str, name: str, new_name: str) -> str:
    node = definition_node(module, name)
    text = module_file(module).read_text()
    return ast.get_source_segment(text, node).replace(f"class {name}", f"class {new_name}", 1) + "\n"


def test_a_registered_class_body_is_compared_whole_at_its_own_location_and_for_twins(tmp_path):
    # Round 6, B3 (skeptic R2a, R2b): guard 4 compared registered FUNCTIONS only, and guard 3 skips a record's own
    # modules, so a verbatim copy of a registered class in a module its record already names, or recorded as a new
    # alternate of a decided record, passed. A registered class is now compared whole (every method included in one
    # fingerprint, names and constants erased), with the own-location and twin rules of a function body. Its methods
    # are still not compared one by one (four real duplicates; see the README), so a copy of one method passes.
    data = {r["record_id"]: r for r in load()["function_owner_records"]}
    goal, commerce = data["OWN-FN-GOAL-RUNTIME"], copy.deepcopy(data["OWN-FN-COMMERCE-CLOSURE"])
    real = _real("egregore.gravity", "greg.gravity", "business.commercial_loop", "greg.business_loop")
    loop = definition_node("egregore.gravity", "GoalGravityLoop")
    one_method = copy.deepcopy(next(n for n in loop.body if isinstance(n, FUNCTIONS) and fingerprint(n)[0] >= 100))
    one_method.name, one_method.decorator_list = "lone_method", []
    disguised = copy.deepcopy(definition_node("business.commercial_loop", "CommercialLoop"))
    disguised.name, disguised.decorator_list = "Settlement", []
    _Disguise().visit(disguised)
    ast.fix_missing_locations(disguised)
    root = _tree(tmp_path, {
        **real,
        # R2a: a verbatim copy of candidate side A's class in side B's own module, no registry edit
        "greg/gravity.py": real["greg/gravity.py"] + "\n\n" + _class_source("egregore.gravity", "GoalGravityLoop",
                                                                             "PullLoop"),
        # R2b: a verbatim copy of an alternate's class, recorded as a new ALTERNATE of the decided commerce record
        "greg/commerce_runner.py": _class_source("business.commercial_loop", "CommercialLoop", "CommerceRunner"),
        # a disguised class copy (every name and literal changed) outside the six packages
        "tools/settlement.py": ast.unparse(disguised) + "\n",
        # one method of the class copied on its own: methods are not compared (stated limit)
        "tools/lone.py": ast.unparse(one_method) + "\n",
    })
    commerce["alternates"].append({"module": "greg.commerce_runner", "qualnames": ["CommerceRunner"],
                                   "status": "ALTERNATE", "reason": "r", "retirement_condition": "c"})
    found = body_copy_problems([goal, commerce], root)
    where = sorted({line.split(" defines ")[0].split(":")[0] + " " + line.split(" defines ")[1].split(",")[0]
                    for line in found})
    # the recorded copy and the original are each a copy of the other's registered body, as with a function twin
    assert where == ["business/commercial_loop.py 'CommercialLoop'", "greg/commerce_runner.py 'CommerceRunner'",
                     "greg/gravity.py 'PullLoop'", "tools/settlement.py 'Settlement'"], found
    assert any("egregore.gravity.GoalGravityLoop" in line for line in found if line.startswith("greg/gravity.py"))
    twins = registered_twin_problems([goal, commerce], root)
    assert len(twins) == 1 and "business.commercial_loop.CommercialLoop" in twins[0] and (
        "greg.commerce_runner.CommerceRunner" in twins[0]), twins
    # a class never matches a function: the kind is part of the key
    assert body_shape(loop)[1].startswith(CLASS_SHAPE) and not body_shape(one_method)[1].startswith(CLASS_SHAPE)
    assert {(m, q) for m, q in COMPARED if isinstance(_compared_node(m, q), ast.ClassDef)} == {
        (e["module"], q) for r in data.values() for role, e in entries(r) if role != "distinct"
        for q in e.get("qualnames") or [] if isinstance(binding(e["module"], q), ast.ClassDef)}
