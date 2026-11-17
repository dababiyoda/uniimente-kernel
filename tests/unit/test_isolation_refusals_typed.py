"""Isolation the host cannot provide is the host's: every capability refusal raised for it is typed ``transient``.

``CapabilityError``'s docstring names ``transient`` as the class for "the host or infrastructure: a timeout,
unavailable isolation", and ``run_isolated`` types unavailable network isolation so. Before 2026-11-13, eight
routes that need bubblewrap namespaces (browser.render, browser.session, the DALEOBANKS bridge, the organ exchange,
venture appraisal and three MCP routes) raised the refusal untyped. Since #196's ``f383fd26`` the ordinary sensor
path holds a transient sensor failure unmeasured, so untyped, a check read through one of those routes on a host
without namespaces recorded a measured failure where nothing was measured (#311's review, M2; its boundary item 8
listed the other routes). This test reads the source, so a route added later is held to the same rule.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _isolation_refusals() -> list[tuple[str, int, str | None]]:
    """(file, line, failure_class) of every ``raise CapabilityError(...)`` inside ``except WorkerIsolationError``."""
    found = []
    for path in sorted((ROOT / "greg").rglob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        for handler in ast.walk(tree):
            if not (isinstance(handler, ast.ExceptHandler) and handler.type is not None
                    and "WorkerIsolationError" in ast.unparse(handler.type)):
                continue
            for node in ast.walk(handler):
                if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call) \
                        and ast.unparse(node.exc.func).endswith("CapabilityError"):
                    kind = next((k.value.value for k in node.exc.keywords
                                 if k.arg == "failure_class" and isinstance(k.value, ast.Constant)), None)
                    found.append((str(path.relative_to(ROOT)), node.lineno, kind))
    return found


def test_every_refusal_for_missing_isolation_is_typed_transient():
    refusals = _isolation_refusals()
    assert len(refusals) >= 8, refusals        # the rule is checked where it applies, not vacuously
    untyped = [(f, line) for f, line, kind in refusals if kind != "transient"]
    assert not untyped, f"refusals for missing isolation must carry failure_class='transient': {untyped}"


def test_the_routes_named_by_the_review_are_among_those_checked():
    files = {f for f, _, _ in _isolation_refusals()}
    assert {"greg/capabilities.py", "greg/computer.py", "greg/daleobanks_bridge.py", "greg/organ_exchange.py",
            "greg/ventures.py", "greg/mcp_tools.py"} <= files
