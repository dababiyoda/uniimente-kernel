"""One canonical owner per important function (directive 2026-10-28 sections 3, 52 and 76), as a test.

"For every major mechanism identify: CANONICAL IMPLEMENTATION, ALTERNATIVES, SHIMS, EXPERIMENTS, BENCHMARKS,
HISTORICAL IMPLEMENTATIONS, MIGRATION PATH, RETIREMENT CONDITION. Do not allow architectural generations to remain
equally canonical forever. Preserving history does not require preserving active ambiguity." (section 52)

The registry is ``function_owner_records`` in docs/collaboration/ARCHITECTURE-OWNERSHIP-MAP.yaml. Three guards:

1. every module and qualname the registry names exists (read from the source with ``ast``; nothing is imported);
2. no module under greg/ reaches an alternate whose status is RETIRED or HISTORICAL: ``import``, ``from ... import``
   (relative ones too), ``as`` aliases, attribute chains through any of them, names assigned from them,
   ``getattr``/``vars``/``sys.modules`` with a constant name, ``importlib.import_module`` and ``__import__`` (with
   ``name=``/``package=``, relative names, ``fromlist``, and a module name taken from a module-level string table
   such as greg/appraisal.py ``DELIVERING``) and a capability bound with ``_lazy("<module>", "<function>")``
   (greg/capabilities.py). A dynamic import whose module name it cannot resolve fails unless ``ALLOWED_DYNAMIC``
   below says why it is safe;
3. a module-level binding in greg/, foundry/, egregore/, omnimorph/, autonomy/ or governance/ (def, class,
   assignment, for/with/except/match target, walrus, import alias, ``globals()`` key) outside a record's canonical,
   candidate and alternate modules and its ``distinct`` names fails when its name matches the record's markers, when
   it reuses the exact name of a registered implementation (except the record's ``generic_names``), or when it is a
   structural copy of a registered function or class under any name. Names are a HEURISTIC: a rewritten
   re-implementation under an unmarked, unregistered name, a method inside a class, or code outside those six
   packages passes;
4. (MW-C, 2026-11-21) the body of every canonical, candidate and alternate FUNCTION a record names, with every name
   and every constant erased (``fingerprint``, from a fresh copy) and at least ``MIN_COPY_NODES`` nodes, is compared
   with every function and method at any depth of every runtime file the filesystem lists (``runtime_files``: every
   .py file under the repository root, directory links followed only inside it, except tests/, docs/, top-level
   hidden entries and the cortex/evaluation/ files whose bytes a freeze manifest there hashes). A copy outside the
   record's canonical, candidate and alternate modules fails, wherever it is and whatever it is called; a
   ``distinct`` entry never exempts one (``distinct_copy_problems``: and may not name a module that holds one). It
   still misses a rewrite that changes structure, an attribute rename (``row['x']`` to ``row.x``) and a function the
   registry does not record.

The registry itself is pinned (``PINNED``, ``FOUNDER_DECISIONS``, ``MUST_FLAG``): removing a record or an entry,
adding a second canonical module, adding a candidate to a record that is still NEEDS_FOUNDER_DECISION, resolving a
founder decision without a ruling record, or narrowing a record's markers below the names it must catch fails until
this file changes in the same reviewed diff. ``kept_for_problems`` is a forward guard for section 76: a HISTORICAL or
RETIRED alternate still in the tree names what keeps it (a consumer outside greg/ and tests/, or an open decision).

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
# is two owners (section 52) and must be recorded as an ALTERNATE instead. The candidate set of a record that is still
# NEEDS_FOUNDER_DECISION is exact too (MW-C, 2026-11-21): its candidates are competing owners, so adding one fails
# until it is pinned here. Adding an alternate or a distinct entry needs no change here; changing this literal is a
# reviewed change to the guard itself.
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


def module_file(module: str, root: Path = ROOT) -> Path | None:
    base = Path(root, *module.split("."))
    for candidate in (base.with_suffix(".py"), base / "__init__.py"):
        if candidate.is_file():
            return candidate
    return None


def module_name(path: Path, root: Path = ROOT) -> str:
    relative = Path(path).relative_to(root).with_suffix("")
    return ".".join(relative.parts[:-1] if relative.name == "__init__" else relative.parts)


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
    """Every .py file under ``directory``, in name order. A directory symlink is followed only when its target
    resolves inside ``root`` and is not already on the walk's own path (a loop ends there); a link that leaves the
    repository (a venv/ pointing at site-packages) is never followed. ``Path.rglob`` would follow a link only at the
    directory it starts from and never below it, on 3.11 and 3.13 alike: a top-level venv/ link was walked in full
    and greg/vendor -> docs/vendor was not. Nothing is skipped by name: a .py file under __pycache__/ is importable."""
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


def python_files(root: Path, package: str):
    yield from _walk(Path(root, package), root)


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


def has_qualname(module: str, qualname: str, root: Path = ROOT) -> bool:
    path = module_file(module, root)
    if path is None:
        return False
    body = parse(path).body
    for part in qualname.split("."):
        found = next((n for n in statements(body) if part in bound_names(n)), None)
        if found is None:
            return False
        body = found.body if isinstance(found, ast.ClassDef) else []
    return True


def definition_node(module: str, name: str, root: Path = ROOT):
    path = module_file(module, root)
    if path is None:
        return None
    return next((n for n in statements(parse(path).body) if isinstance(n, DEFS) and n.name == name), None)


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
                 founder_decisions: frozenset = FOUNDER_DECISIONS) -> list[str]:
    records = {r.get("record_id"): r for r in data.get("function_owner_records") or []}
    problems = []
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
        if r.get("owner_status") == "NEEDS_FOUNDER_DECISION":
            # An undecided record's candidates are its competing owners until the founder rules: the set is exact.
            added = sorted(f"{module}.{name}" if name else module for module, names in have["candidates"].items()
                           for name in (sorted(names or ()) or [""])
                           if module not in pin["candidates"] or (name and name not in pin["candidates"][module]))
            problems += [f"{rid}: candidate {name} is not pinned. The candidates of a NEEDS_FOUNDER_DECISION record are "
                         f"its competing owners until the founder rules, so a new one joins only in a reviewed change "
                         f"to PINNED in tests/unit/test_canonical_owner_guard.py, never by a registry edit alone"
                         for name in added]
    return problems


def _guarded_index(root: Path, packages=GUARDED) -> dict[str, set[str]]:
    """Module-level name -> the guarded modules that define it (imports excluded)."""
    index: dict[str, set[str]] = {}
    for package in packages:
        for path in python_files(root, package):
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
    for package in packages:
        for path in python_files(root, package):
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
                    if shape in shapes and (module, name) not in distinct:
                        out.append(f"{path.relative_to(root)}:{line} defines {name!r}, a structural copy of "
                                   f"{shapes[shape]} registered in {r['record_id']} ({r['function']}); its owner is "
                                   f"{owner(r)}. " + FIX.format(record=r["record_id"]))
    return sorted(set(out))


# -- guard 4: a registered function's body anywhere in the runtime tree (MW-C, 2026-11-21) --------------------------

# Not runtime code: tests (fixtures may copy a body on purpose) and documents, by full top-level path prefix, never by
# a path segment, so a copy cannot hide in a new directory that shares one of these names. SEALED_UNDER: the only
# other files not scanned are the frozen instruments there, each a file whose current bytes a ``MANIFESTS`` file hashes
# (``sealed_files``); every other file under it (new files, edited ones, subdirectories) is scanned, because GREG
# imports from it (cortex.evaluation.closure).
NOT_RUNTIME = ("tests/", "docs/")
SEALED_UNDER = "cortex/evaluation/"
MANIFESTS = "freeze-*.json"
ERASED = "_"                     # every name and every constant of a fingerprinted body becomes this one sentinel
FIX_COPY = ("Import the owner's function instead. If this copy must stay, record its module in {record} in "
            "docs/collaboration/ARCHITECTURE-OWNERSHIP-MAP.yaml as an ALTERNATE (with its status and its retirement "
            "or revival condition); a 'distinct' entry does not exempt a copy.")


class _Erase(ast.NodeTransformer):
    """Rewrite every name a body binds or reads, and every constant, to ERASED; structure, attribute names, keyword
    names and imported module names stay. It rewrites in place, so ``fingerprint`` gives it a fresh copy, and it is
    idempotent: an erased tree erases to itself."""

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
        if node.asname is not None:
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


_DROPPED = {ast.arg: "annotation", ast.FunctionDef: "returns", ast.AsyncFunctionDef: "returns"}


def _erased_size(fn) -> int:
    """The node count ``fingerprint`` reports, read without copying: the body's nodes minus the annotations _Erase
    drops."""
    stack, size = list(_function_body(fn)), 0
    while stack:
        node = stack.pop()
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


def sealed_files(root: Path = ROOT) -> frozenset[str]:
    """The files under SEALED_UNDER that a SEALED_UNDER/freeze-*.json manifest hashes (``inputs.code``: path ->
    "sha256:<hex>"), as repository-relative paths, when the file's bytes still have a hash some manifest records for
    it. A manifest that does not parse seals nothing."""
    digests: dict[str, set[str]] = {}
    for manifest in sorted(Path(root, SEALED_UNDER).glob(MANIFESTS)):
        try:
            code = (json.loads(manifest.read_bytes()).get("inputs") or {}).get("code") or {}
        except (OSError, ValueError, AttributeError):
            continue
        for relative, digest in code.items() if isinstance(code, dict) else ():
            if isinstance(relative, str) and isinstance(digest, str) and relative.startswith(SEALED_UNDER):
                digests.setdefault(relative, set()).add(digest)
    sealed = set()
    for relative, recorded in digests.items():
        path = Path(root, relative)
        if path.is_file() and f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}" in recorded:
            sealed.add(relative)
    return frozenset(sealed)


def runtime_files(root: Path = ROOT):
    """Every runtime .py file as the filesystem lists it (no git: the mutant gate's copy of the tree has none), by
    guard 3's rule (``_walk``: directory symlinks followed only inside the repository), without NOT_RUNTIME, the
    sealed files under SEALED_UNDER and top-level hidden entries (.git, tool caches, an agent's worktree: none is
    tracked runtime code)."""
    sealed = sealed_files(root)

    def skip(path: Path) -> bool:
        relative = path.relative_to(root)
        return len(relative.parts) == 1 and (relative.name.startswith(".") or f"{relative.name}/" in NOT_RUNTIME)

    for path in _walk(Path(root), root, skip):
        relative = path.relative_to(root).as_posix()
        if not relative.startswith(".") and relative not in sealed:
            yield path


def _functions(tree: ast.Module):
    """(dotted scope name, node) for every function and method at any depth."""
    out = []

    def visit(node, prefix):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, DEFS):
                name = f"{prefix}.{child.name}" if prefix else child.name
                if isinstance(child, FUNCTIONS):
                    out.append((name, child))
                visit(child, name)
            else:
                visit(child, prefix)
    visit(tree, "")
    return out


def _function_node(module: str, qualname: str, root: Path = ROOT):
    """The def a registered (dotted) qualname names, or None for a class, a constant or a missing name."""
    node, path = None, module_file(module, root)
    body = parse(path).body if path is not None else []
    for part in qualname.split("."):
        node = next((n for n in statements(body) if isinstance(n, DEFS) and n.name == part), None)
        if node is None:
            return None
        body = node.body
    return node if isinstance(node, FUNCTIONS) else None


def registered_bodies(records: list[dict], root: Path = ROOT) -> dict[tuple[int, str], list[tuple[dict, str, str]]]:
    """fingerprint -> [(record, "module.qualname", "path:line")] for every canonical, candidate and alternate
    qualname that names a function of at least MIN_COPY_NODES erased nodes. Classes and constants are guard 3's."""
    out: dict[tuple[int, str], list[tuple[dict, str, str]]] = {}
    for r in records:
        for role, e in entries(r):
            if role == "distinct":
                continue
            for q in e.get("qualnames") or []:
                node = _function_node(e["module"], q, root)
                if node is None:
                    continue
                shape = fingerprint(node)
                if shape[0] >= MIN_COPY_NODES:
                    where = f"{module_file(e['module'], root).relative_to(root).as_posix()}:{node.lineno}"
                    out.setdefault(shape, []).append((r, f"{e['module']}.{q}", where))
    return out


@lru_cache(maxsize=None)
def _prints(path: Path, stamp: int, sizes: frozenset) -> tuple:
    """(scope name, line, fingerprint) for every function of one file whose erased size is one of ``sizes``; the
    rest are never copied."""
    return tuple((name, node.lineno, fingerprint(node)) for name, node in _functions(_parse(path, stamp))
                 if _erased_size(node) in sizes)


def body_copies(records: list[dict], root: Path = ROOT) -> tuple[list[dict], list[str]]:
    """(every function or method whose fingerprint is a registered body's, outside that record's canonical,
    candidate and alternate modules; every runtime file that does not parse). A 'distinct' entry never exempts."""
    bodies = registered_bodies(records, root)
    sizes = frozenset(size for size, _ in bodies)
    found, unreadable = [], []
    for path in runtime_files(root):
        relative = path.relative_to(root).as_posix()
        try:
            prints = _prints(path, path.stat().st_mtime_ns, sizes)
        except (SyntaxError, UnicodeDecodeError, ValueError) as exc:
            unreadable.append(f"{relative} cannot be parsed ({type(exc).__name__}), so guard 4 cannot show that it "
                              f"holds no copy of a registered function")
            continue
        module = module_name(path, root)
        for name, line, shape in prints:
            for r, registered, where in bodies.get(shape, []):
                if module not in owned_modules(r):
                    found.append({"record": r, "registered": registered, "registered_at": where, "module": module,
                                  "at": f"{relative}:{line}", "name": name})
    return found, unreadable


def body_copy_problems(records: list[dict], root: Path = ROOT) -> list[str]:
    found, unreadable = body_copies(records, root)
    out = [f"{c['at']} defines {c['name']!r}, a copy of the body of {c['registered']} ({c['registered_at']}), "
           f"registered in {c['record']['record_id']} ({c['record'].get('function')}); names and constants are erased "
           f"before comparing, so renamed variables or changed literals are still the same body. Its owner is "
           f"{owner(c['record'])}. " + FIX_COPY.format(record=c["record"]["record_id"]) for c in found]
    return sorted(set(out)) + unreadable


def distinct_copy_problems(records: list[dict], root: Path = ROOT) -> list[str]:
    """A 'distinct' entry says a module holds a different function. It may not name a module that holds a copy of a
    registered body (guard 4): a copy is an alternate, recorded with its status and condition."""
    holding: dict[str, list[dict]] = {}
    for c in body_copies(records, root)[0]:
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
NOT_CONSUMERS = ("greg", "tests")


def _names_in(node) -> set[str]:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)} | {
        n.attr for n in ast.walk(node) if isinstance(n, ast.Attribute)}


def kept_for_problems(records: list[dict], root: Path = ROOT) -> list[str]:
    """Directive section 76: "Do not keep obsolete implementations merely to preserve history." A FORWARD GUARD over
    the registry: every alternate with status HISTORICAL or RETIRED whose module (or one of its qualnames) is still
    defined in the tree carries ``kept_for``, exactly one of

    - ``{consumer: <module>.<function>}``: a function outside greg/ (which guard 2 forbids to reach it) and tests/ (a
      test of the kept object is not a use) whose source names the kept object, in a module that imports it from the
      alternate's module; or
    - ``{open_decision: <record_id>}``: a record still NEEDS_FOUNDER_DECISION whose ruling may revive it.

    An alternate gone from the tree needs none: git keeps its history. On 2026-11-21 this binds one entry
    (greg.mission_control REALITY, HISTORICAL). It binds only what the registry records: obsolete code that no record
    names is not seen."""
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
                           f"keeps it: give it kept_for {{consumer: <module>.<function>}} (code outside greg/ and "
                           f"tests/ that still reads it) or {{open_decision: <record_id>}} (an undecided record whose "
                           f"ruling may revive it), or remove it from the tree (git keeps its history)")
                continue
            if "open_decision" in kept:
                target = by_id.get(kept["open_decision"])
                if target is None or target.get("owner_status") != "NEEDS_FOUNDER_DECISION":
                    out.append(f"{rid}: {what} is kept_for open_decision {kept['open_decision']}, which is not a "
                               f"NEEDS_FOUNDER_DECISION record of the registry; once the founder rules, the alternate "
                               f"leaves the tree, or names the consumer that still reads it")
                continue
            consumer = str(kept["consumer"])
            consumer_module, _, function = consumer.rpartition(".")
            if not consumer_module or consumer_module.split(".")[0] in NOT_CONSUMERS or consumer_module == module:
                out.append(f"{rid}: {what} is kept_for consumer {consumer}, which is not a function outside greg/ "
                           f"and tests/ and outside the alternate's own module")
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
    check = lambda d: pin_problems(d, root, pinned, frozenset({"OWN-FN-D"}))  # noqa: E731
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
    # not vacuous: 27 registered function bodies of at least MIN_COPY_NODES erased nodes on 2026-11-21, compared with
    # every function and method of about 500 runtime files
    assert sum(len(found) for found in registered_bodies(records).values()) >= 20
    assert len(list(runtime_files())) > 400
    assert body_copy_problems(records) == []


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
    })
    found = body_copy_problems([commerce, teams, inbox], root)
    expected = {"business/case_copy.py": ("'Case.settle'", "greg.business_loop.reconcile (greg/business_loop.py:"),
                "greg/wrapped.py": ("'outer.inner'", "greg.business_loop.reconcile (greg/business_loop.py:"),
                "closure/settle_copy.py": ("'settle_case'", "greg.business_loop.reconcile (greg/business_loop.py:"),
                "foundry/systems/team_copy.py": ("'convene'", "foundry.systems.teams.form (foundry/systems/teams.py:"),
                "greg/evaluation/team_copy.py": ("'convene'", "foundry.systems.teams.form (foundry/systems/teams.py:"),
                "greg/oneline.py": ("'relay'", "greg.body.send_signed (greg/body.py:1)")}
    for path, (copied, registered) in expected.items():
        assert any(line.startswith(f"{path}:") and copied in line and registered in line for line in found), path
    assert len(found) == len(expected), found
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


def test_an_undecided_record_takes_no_new_candidate_without_a_pin_change():
    # The adversary's candidate game (scratchpad mwc/attack/candidate_game.py), first half: a third competing owner
    # added to an undecided record passed every check.
    data = load()
    assert pin_problems(data) == []

    def changed(record_id: str, edit) -> list[str]:
        out = copy.deepcopy(data)
        edit(next(r for r in out["function_owner_records"] if r["record_id"] == record_id))
        return [p for p in pin_problems(out) if p.startswith(record_id)]

    new_module = changed("OWN-FN-GOAL-RUNTIME", lambda r: r["candidates"].append(
        {"module": "greg.goal_engine2", "qualnames": ["run"], "side": "C", "evidence": ["new"]}))
    assert any("candidate greg.goal_engine2.run is not pinned" in p for p in new_module), new_module
    new_name = changed("OWN-FN-GOAL-RUNTIME", lambda r: next(
        c for c in r["candidates"] if c["module"] == "greg.gravity")["qualnames"].append("rederive"))
    assert any("candidate greg.gravity.rederive is not pinned" in p for p in new_name), new_name
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

    def problems(kept_for=None, status="HISTORICAL", module="greg.ladder", decided="NEEDS_FOUNDER_DECISION"):
        alternate = {"module": module, "qualnames": ["REALITY"], "status": status, "reason": "r",
                     "revival_condition": "c", **({"kept_for": kept_for} if kept_for is not None else {})}
        records = [{"record_id": "OWN-FN-L", "owner_status": "CANONICAL", "alternates": [alternate]},
                   {"record_id": "OWN-FN-OPEN", "owner_status": decided}]
        return kept_for_problems(records, root)

    assert problems({"consumer": "acceptance.claims.crosswalk"}) == []
    assert problems({"open_decision": "OWN-FN-OPEN"}) == []
    assert problems(status="RETIRED", kept_for={"consumer": "acceptance.claims.crosswalk"}) == []
    assert problems(module="greg.gone") == []                       # gone from the tree: git keeps its history
    assert problems(status="ALTERNATE") == []                       # a live alternate states a retirement condition
    for kept_for, said in ((None, "does not say what keeps it"),
                           ({}, "does not say what keeps it"),
                           ({"consumer": "acceptance.claims.crosswalk", "open_decision": "OWN-FN-OPEN"},
                            "does not say what keeps it"),
                           ({"consumer": "greg.console.show"}, "outside greg/ and tests/"),
                           ({"consumer": "tests.test_ladder.test_x"}, "outside greg/ and tests/"),
                           ({"consumer": "acceptance.claims.other"}, "does not name greg.ladder.REALITY"),
                           ({"consumer": "acceptance.unrelated.crosswalk"}, "does not name greg.ladder.REALITY"),
                           ({"consumer": "acceptance.claims.missing"}, "does not exist"),
                           ({"open_decision": "OWN-FN-NONE"}, "not a NEEDS_FOUNDER_DECISION record")):
        found = problems(kept_for)
        assert len(found) == 1 and said in found[0], (kept_for, found)
    assert "not a NEEDS_FOUNDER_DECISION record" in problems({"open_decision": "OWN-FN-OPEN"}, decided="CANONICAL")[0]


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
    found = body_copy_problems([teams], root)
    assert sorted(line.split(":")[0] for line in found) == [
        "cortex/evaluation/edited.py", "cortex/evaluation/settle.py", "cortex/evaluation/suites/runner.py",
        "cortex/other.py", "foundry/systems/team_copy.py"], found
    assert sealed_files(root) == {"cortex/evaluation/sealed.py"}
