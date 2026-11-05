"""No new copy of a function body anywhere in the runtime tree, under any name.

``test_provenance_digests`` guards the private digest/timestamp helpers by name, so a copy under a new
name, or with its variables renamed, passed it. This test compares structure instead: two functions in
different files whose bodies (docstring dropped, at least five lines) are the same once every variable,
argument and annotation is renamed away are one copy. ``KEPT`` lists the copies that must stay, each
with its reason. A new copy fails the first test; a kept group that has gone fails the second, so the
list can only shrink. Every name is renamed away, including the exception class a body catches and
the function it calls: eleven Foundry refusal probes that differed only in their exception class were
one copy. Constants and attribute names still count, so a different cut-off (``[:70]`` against
``[:80]``) or a different method called is a different function.

Round 3 of the consolidation record (``docs/collaboration/DIGEST-RULE-CONSOLIDATION-2026-10-30.md``).
"""
from __future__ import annotations

import ast
import collections
import hashlib
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIN_BODY_LINES = 5
# Tests and docs are not runtime; frozen evaluation runners are instruments that must stay as written.
SKIP = ("tests/", "docs/")
SKIP_PART = "/evaluation/"

PINNED = "PINNED: a freeze or evidence record holds this file's hash; adopt one copy at its next re-freeze"
KEPT = {
    frozenset({"adapters/contract_validation.py::validate_contract", "egregore/contract_check.py::validate_record"}):
        PINNED + " (both files are pinned; the boundary module is also the organs' installed contract package)",
    frozenset({"adapters/contract_validation.py::formats", "egregore/contract_check.py::formats"}):
        PINNED + " (both files are pinned)",
    frozenset({"cortex/contracts.py::canonical_json", "egregore/contracts.py::canonical_json",
               "governance/integrity/__init__.py::canonical_json"}):
        "INDEPENDENT on purpose: the integrity check must not import what it guards and the cortex seed is a "
        "separable package (round 1 record); the rule is tested equal in place",
    frozenset({"foundry/systems/segmentation.py::_load_filter", "greg/capabilities.py::_network_filter"}):
        PINNED + " (segmentation.py); both load the seccomp filter into the parent before any child runs",
    frozenset({"greg/cognition/genomes/flow.py::compile_score", "greg/cognition/genomes/forecasting.py::newsvendor_score"}):
        PINNED + " (greg/cognition/genomes is pinned by the admission freezes)",
    frozenset({"greg/cognition/genomes/solvers_c.py::timed_check", "greg/cognition/genomes/strategic.py::timed_check"}):
        PINNED + " (greg/cognition/genomes is pinned by the admission freezes)",
    frozenset({"scripts/p8_immune8_pilot.py::items", "scripts/p8_immune_pilot.py::items"}):
        "FROZEN INSTRUMENT: each P8 pilot script reproduces a recorded pilot decision as written",
    frozenset({"scripts/p8_immune8_pilot.py::choose", "scripts/p8_repair1_pilot.py::choose"}):
        "FROZEN INSTRUMENT: each P8 pilot script reproduces a recorded pilot decision as written",
}


class _Anonymize(ast.NodeTransformer):
    def visit_Name(self, node):
        node.id = "_"
        return node

    def visit_arg(self, node):
        node.arg, node.annotation = "_", None
        return node

    # Names bound as plain strings rather than Name nodes: ``except E as x``, ``import m as x``, nested ``def x``
    # and ``class x``, ``global x``/``nonlocal x``. The imported module itself still counts.
    def visit_ExceptHandler(self, node):
        self.generic_visit(node)
        if node.name is not None:
            node.name = "_"
        return node

    def visit_alias(self, node):
        if node.asname is not None:
            node.asname = "_"
        return node

    def visit_FunctionDef(self, node):
        self.generic_visit(node)
        node.name, node.returns = "_", None
        return node

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node):
        self.generic_visit(node)
        node.name = "_"
        return node

    def visit_Global(self, node):
        node.names = ["_"] * len(node.names)
        return node

    visit_Nonlocal = visit_Global


def _body(fn):
    body = fn.body
    if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
            and isinstance(body[0].value.value, str):
        body = body[1:]
    return body


def fingerprints(path: str, source: str):
    """(fingerprint, "path::name") for every function in ``source`` with a body of at least MIN_BODY_LINES."""
    tree = ast.parse(source)
    functions = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    sized = []
    for fn in functions:  # measured before anonymizing, which mutates the tree
        body = _body(fn)
        if body and body[-1].end_lineno - body[0].lineno + 1 >= MIN_BODY_LINES:
            sized.append((fn, fn.name, len(fn.body) - len(body)))
    out = []
    for fn, name, skip in sized:  # the name is read first: anonymizing an outer body renames nested defs
        module = _Anonymize().visit(ast.Module(body=fn.body[skip:], type_ignores=[]))
        out.append((hashlib.sha1(ast.dump(module).encode()).hexdigest(), f"{path}::{name}"))
    return out


def duplicate_groups(sources: dict[str, str]) -> set[frozenset]:
    """Groups of functions, in at least two different files, that share one fingerprint."""
    by_print = collections.defaultdict(set)
    for path, source in sources.items():
        for digest, name in fingerprints(path, source):
            by_print[digest].add(name)
    return {frozenset(names) for names in by_print.values() if len({n.split("::")[0] for n in names}) > 1}


def _runtime_sources() -> dict[str, str]:
    listed = subprocess.run(["git", "ls-files", "*.py"], cwd=ROOT, capture_output=True, text=True, check=True)
    sources = {}
    for path in listed.stdout.split():
        if path.startswith(SKIP) or SKIP_PART in path:
            continue
        try:
            sources[path] = (ROOT / path).read_text()
        except (OSError, UnicodeDecodeError):  # pragma: no cover - a tracked file removed in the worktree
            continue
    return sources


_GROUPS: set[frozenset] | None = None


def _groups() -> set[frozenset]:
    global _GROUPS
    if _GROUPS is None:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)  # tracked scripts with invalid escapes still parse
            _GROUPS = duplicate_groups(_runtime_sources())
    return _GROUPS


def test_no_new_structural_duplicate():
    new = [sorted(g) for g in _groups() if not any(g <= kept for kept in KEPT)]
    assert not new, ("a function body now exists in two files (variables renamed away); import one copy instead, "
                     f"or add the group to KEPT with the reason it must stay: {new}")


def test_kept_list_only_shrinks():
    gone = [sorted(kept) for kept in KEPT if not any(kept == g for g in _groups())]
    assert not gone, f"a kept duplicate group changed or is gone; update KEPT so it can only shrink: {gone}"


def test_the_scanner_sees_through_renamed_names_but_not_different_constants():
    a = "def f(label, fn):\n    try:\n        fn()\n        out[label] = None\n    except KeyError as exc:\n        out[label] = str(exc)[:80]\n"
    renamed = ("def g(key, call):\n    try:\n        call()\n        out[key] = None\n    except KeyError as err:\n"
               "        out[key] = str(err)[:80]\n")
    other_rule = a.replace("[:80]", "[:70]")
    other_error = a.replace("KeyError", "ValueError")
    other_method = a.replace("str(exc)[:80]", "exc.args[:80]")
    groups = duplicate_groups({"a.py": a, "b.py": renamed, "c.py": other_rule, "d.py": other_error,
                               "e.py": other_method})
    assert groups == {frozenset({"a.py::f", "b.py::g", "d.py::f"})}
    assert duplicate_groups({"a.py": a, "b.py": a.replace("def f", "def h")}) == {frozenset({"a.py::f", "b.py::h"})}
    loader = ("def f():\n    try:\n        module = sys.modules.get('m')\n        if module is None:\n"
              "            import m as module\n        return module.run\n    except Exception as exc:\n        return exc\n")
    aliased = ("def f():\n    try:\n        mod = sys.modules.get('m')\n        if mod is None:\n"
               "            import m as mod\n        return mod.run\n    except Exception as err:\n        return err\n")
    assert duplicate_groups({"a.py": loader, "b.py": aliased.replace("def f", "def g")}) == {
        frozenset({"a.py::f", "b.py::g"})}, "an import alias or handler name renamed away is still the same body"


def test_short_bodies_and_same_file_copies_are_not_counted():
    short = "def f(x):\n    \"\"\"A long docstring\n    that spans\n    several\n    lines.\"\"\"\n    return x[0]\n"
    assert duplicate_groups({"a.py": short, "b.py": short.replace("def f", "def g")}) == set()
    body = "def f(x):\n" + "".join(f"    x = x + {i}\n" for i in range(5))
    assert duplicate_groups({"a.py": body + body.replace("def f", "def g")}) == set()


def test_refusal_recorder_rules():
    from foundry.systems.refusals import refusal_recorder

    refusals, refused = refusal_recorder(KeyError, limit=3)
    refused("refused", lambda: {}["abcdef"])
    refused("went through", lambda: None)
    assert refusals == {"refused": "'ab", "went through": None}

    refusals, refused = refusal_recorder((KeyError, ValueError), accepted=False)
    refused("value", lambda: int("x"))
    refused("ok", lambda: 1)
    assert refusals["ok"] is False and refusals["value"].startswith("invalid literal")

    _, refused = refusal_recorder(KeyError)
    try:
        refused("unexpected", lambda: 1 / 0)
    except ZeroDivisionError:
        pass
    else:  # pragma: no cover - the defect this guards against
        raise AssertionError("an error the probe does not expect must propagate, not be recorded as a refusal")
