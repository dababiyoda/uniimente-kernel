"""One canonical owner per important function (directive 2026-10-28 sections 3, 52 and 76), as a test.

"For every major mechanism identify: CANONICAL IMPLEMENTATION, ALTERNATIVES, SHIMS, EXPERIMENTS, BENCHMARKS,
HISTORICAL IMPLEMENTATIONS, MIGRATION PATH, RETIREMENT CONDITION. Do not allow architectural generations to remain
equally canonical forever. Preserving history does not require preserving active ambiguity." (section 52)

The registry is ``function_owner_records`` in docs/collaboration/ARCHITECTURE-OWNERSHIP-MAP.yaml. Three guards:

1. every module and qualname the registry names exists (read from the source with ``ast``; nothing is imported);
2. no module under greg/ imports an alternate whose status is RETIRED or HISTORICAL: ``import``, ``from ... import``
   (relative ones too), ``as`` aliases, attribute access through an aliased module, function-level imports,
   ``importlib.import_module`` / ``__import__`` with a constant name and a capability bound with
   ``_lazy("<module>", "<function>")`` (greg/capabilities.py);
3. a module-level definition in greg/, foundry/, egregore/, omnimorph/, autonomy/ or governance/ whose name matches a
   record's markers, outside that record's canonical, candidate and alternate modules and its ``distinct`` names,
   fails with the record to add. This is a NAME HEURISTIC: a re-implementation under a name no marker matches, a
   method inside a class, or code outside those six packages passes it.

The test reads code and data. It grants, attaches, activates and retires nothing.
"""
from __future__ import annotations

import ast
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
# The functions the 2026-10-28 program duplicates or proposes to duplicate (critic units MU-H and MW-C).
REQUIRED = {"OWN-FN-TEMPORARY-TEAMS", "OWN-FN-COMMERCE-CLOSURE", "OWN-FN-GOAL-RUNTIME",
            "OWN-FN-STATUS-EVIDENCE-LADDER", "OWN-FN-AUTONOMY-LEVELS", "OWN-FN-REGRESSION-CLOSING"}
FIX = ("If it re-implements that function, add an alternate or shim record for it (status ALTERNATE, HISTORICAL, "
       "RESEARCH or RETIRED, with its retirement or revival condition) to {record} in "
       "docs/collaboration/ARCHITECTURE-OWNERSHIP-MAP.yaml; if it is a different function, add a 'distinct' entry "
       "saying why.")


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


def _bodies(node) -> list:
    """Blocks that still run at the enclosing level: if/else, with, try/except/else/finally."""
    if isinstance(node, ast.If):
        return [node.body, node.orelse]
    if isinstance(node, (ast.With, ast.AsyncWith)):
        return [node.body]
    if isinstance(node, (ast.Try, getattr(ast, "TryStar", ast.Try))):
        return [node.body, *(h.body for h in node.handlers), node.orelse, node.finalbody]
    return []


def statements(body):
    for node in body:
        yield node
        for block in _bodies(node):
            yield from statements(block)


def bound_names(node) -> list[str]:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return [node.name]
    if isinstance(node, ast.Assign):
        targets = node.targets
    elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
        targets = [node.target]
    else:
        return []
    return [n.id for t in targets for n in ast.walk(t) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)]


def definitions(tree: ast.Module) -> dict[str, int]:
    """Every module-level definition (def, class, assignment target) -> its first line."""
    out: dict[str, int] = {}
    for node in statements(tree.body):
        for name in bound_names(node):
            out.setdefault(name, node.lineno)
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


def entries(record: dict):
    """(role, entry) for every implementation or distinct definition a record names."""
    for role, key in (("canonical", "canonical"), ("candidate", "candidates"), ("alternate", "alternates"),
                      ("distinct", "distinct")):
        for entry in record.get(key) or []:
            yield role, entry


def owned_modules(record: dict) -> set[str]:
    return {e["module"] for role, e in entries(record) if role != "distinct"}


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
        for key in ("function", "effect", "owner_status", "markers"):
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
            if not r.get("decision_needed") or not r.get("safe_default"):
                problems.append(f"{rid}: NEEDS_FOUNDER_DECISION states the decision needed and the safe default")
            problems += [f"{rid}: candidate {c.get('module')} has no evidence or side" for c in r.get("candidates") or []
                         if not c.get("evidence") or not c.get("side")]
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


def _resolve(node: ast.ImportFrom, module: str, is_package: bool) -> str:
    if not node.level:
        return node.module or ""
    package = module.split(".") if is_package else module.split(".")[:-1]
    base = package[:len(package) - (node.level - 1)]
    return ".".join(base + ([node.module] if node.module else []))


def references(tree: ast.Module, module: str, is_package: bool) -> list[tuple[int, str]]:
    """Every dotted name the file imports or reaches through an imported name, with its line."""
    bound: dict[str, str] = {}
    out: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.append((node.lineno, alias.name))
                if alias.asname:
                    bound[alias.asname] = alias.name
                else:
                    head = alias.name.split(".")[0]
                    bound[head] = head
        elif isinstance(node, ast.ImportFrom):
            source = _resolve(node, module, is_package)
            for alias in node.names:
                full = f"{source}.{alias.name}" if source else alias.name
                out.append((node.lineno, full))
                if alias.name != "*":
                    bound[alias.asname or alias.name] = full
        elif isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else ""
            consts = [a.value if isinstance(a, ast.Constant) and isinstance(a.value, str) else None
                      for a in node.args[:2]]
            if name in ("import_module", "__import__") and consts and consts[0]:
                out.append((node.lineno, consts[0]))
            elif name == "_lazy" and consts and consts[0]:
                # greg/capabilities.py binds a capability to "<module>", "<function>" and imports it on first call
                out.append((node.lineno, consts[0] + (f".{consts[1]}" if len(consts) > 1 and consts[1] else "")))
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            chain, value = [node.attr], node.value
            while isinstance(value, ast.Attribute):
                chain.append(value.attr)
                value = value.value
            if isinstance(value, ast.Name) and value.id in bound:
                out.append((node.lineno, ".".join([bound[value.id], *reversed(chain)])))
    return out


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
    for path in sorted(Path(root, package).rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        module = module_name(path, root)
        refs = references(parse(path), module, path.name == "__init__.py")
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


def unrecorded(records: list[dict], root: Path = ROOT, packages=GUARDED) -> list[str]:
    compiled = [(r, [re.compile(m) for m in r["markers"]], owned_modules(r),
                 {(e["module"], q) for role, e in entries(r) if role == "distinct" for q in e["qualnames"]})
                for r in records]
    out = []
    for package in packages:
        for path in sorted(Path(root, package).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            module = module_name(path, root)
            for name, line in definitions(parse(path)).items():
                for r, patterns, modules, distinct in compiled:
                    marker = next((p.pattern for p in patterns if p.fullmatch(name)), None)
                    if marker is None or module in modules or (module, name) in distinct:
                        continue
                    out.append(f"{path.relative_to(root)}:{line} defines {name!r}, which matches the marker "
                               f"{marker!r} of {r['record_id']} ({r['function']}); its owner is {owner(r)}. "
                               + FIX.format(record=r["record_id"]))
    return out


# -- the registry ------------------------------------------------------------------------------------------------

def test_registry_names_an_owner_status_alternates_and_conditions_for_every_required_function():
    assert shape_problems(load()) == []


def test_every_registered_module_and_qualname_exists():
    assert missing(load()["function_owner_records"]) == []


def test_no_greg_module_imports_a_retired_or_historical_alternate():
    assert retired_imports(load()["function_owner_records"]) == []


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
        "greg/wired_fine.py": "def _lazy(m, n): pass\nB = {'x': _lazy('greg.old', 'keep')}\n",
        "greg/sub/__init__.py": "from ..old import LADDER\n",
        "greg/fine.py": "from greg.old import keep\nimport greg.owner\n",
    })
    found = retired_imports(HISTORICAL, root)
    for name in ("direct", "aliased", "module_alias", "parent_alias", "dotted", "relative", "relative_module", "lazy",
                 "star", "whole_module", "dynamic", "wired", "wired_module"):
        assert any(line.startswith(f"greg/{name}.py:") for line in found), name
    assert any(line.startswith("greg/sub/__init__.py:") for line in found)
    assert not any(line.startswith(("greg/fine.py:", "greg/old.py:", "greg/wired_fine.py:")) for line in found)


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


def test_a_stale_qualname_or_module_is_reported(tmp_path):
    root = _tree(tmp_path, {"greg/__init__.py": "", "greg/owner.py": "class A:\n    def b(self): pass\n"})
    record = {"record_id": "OWN-FN-X", "canonical": [{"module": "greg.owner", "qualnames": ["A.b", "A.c", "run"]}],
              "alternates": [{"module": "greg.moved", "qualnames": ["x"], "status": "ALTERNATE"}]}
    found = missing([record], root)
    assert any("greg.owner.A.c does not exist" in line for line in found)
    assert any("greg.owner.run does not exist" in line for line in found)
    assert any("module greg.moved does not exist" in line for line in found)
    assert not any("A.b" in line for line in found)
