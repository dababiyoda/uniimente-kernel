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
   packages passes.

The registry itself is pinned (``PINNED``, ``FOUNDER_DECISIONS``, ``MUST_FLAG``): removing a record or an entry,
adding a second canonical module, resolving a founder decision without a ruling record, or narrowing a record's
markers below the names it must catch fails until this file changes in the same reviewed diff.

The test reads code and data. It grants, attaches, activates and retires nothing.
"""
from __future__ import annotations

import ast
import copy
from functools import lru_cache
from pathlib import Path
import re

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
# is two owners (section 52) and must be recorded as an ALTERNATE instead. Adding a candidate, an alternate or a
# distinct entry needs no change here; changing this literal is a reviewed change to the guard itself.
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
                     "egregore.brief_learning": ("rank",)},
    },
    "OWN-FN-AUTONOMY-LEVELS": {
        "canonical": {},
        "candidates": {"autonomy.levels": ("LEVELS", "AutonomyTuple", "AutonomyAuthority", "PROMOTION_CRITERIA")},
        "alternates": {},
        "distinct": {"greg.missions": ("pre_approved",), "greg.cognition.genomes.forecasting": ("LEVELS",)},
    },
    "OWN-FN-REGRESSION-CLOSING": {
        "canonical": {"greg.improvement": ("_close_regressions", "_reopen_regressions", "founder_revert",
                                           "attention_close_condition", "claim_close_condition")},
        "candidates": {},
        "alternates": {},
        "distinct": {"greg.tribunal": ("critique",), "greg.goal_gravity": ("_reopen",),
                     "autonomy.levels": ("AutonomyAuthority.regress",), "foundry.systems.repair": ("regression_test",)},
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


@lru_cache(maxsize=None)
def _parse(path: Path, stamp: float) -> ast.Module:
    return ast.parse(path.read_text(), str(path))


def parse(path: Path) -> ast.Module:
    path = Path(path)
    return _parse(path, path.stat().st_mtime_ns)


def python_files(root: Path, package: str):
    for path in sorted(Path(root, package).rglob("*.py")):
        if "__pycache__" not in path.parts:
            yield path


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
