"""Orthogonal closure tests: the five-closure standard itself."""
from closure.framework import ClosureRegistry, ModuleClosures, CLOSURE_NAMES
from closure.integration_registry import build_registry


def test_five_closures_named_exactly():
    assert CLOSURE_NAMES == ("technical", "authority", "evidence", "economic", "regenerative")


def test_a_module_with_only_technical_closure_is_not_finished():
    registry = ClosureRegistry()
    registry.register(ModuleClosures("demo", {
        "technical": lambda: (True, "runs"),
        "authority": lambda: (False, "cannot prove authority"),
        "evidence": lambda: (True, "reconstructable"),
        "economic": lambda: (True, "saves cost"),
        "regenerative": lambda: (True, "no hidden harm"),
    }))
    ok, reports = registry.verify()
    assert not ok
    assert not reports[0].complete
    assert reports[0].open_closures == ["authority"]


def test_crashing_check_fails_closed():
    registry = ClosureRegistry()

    def explode():
        raise RuntimeError("boom")

    registry.register(ModuleClosures("demo", {
        name: (explode if name == "technical" else (lambda: (True, "ok")))
        for name in CLOSURE_NAMES
    }))
    ok, reports = registry.verify()
    assert not ok
    assert any("raised" in closure.detail for closure in reports[0].closures
               if closure.closure == "technical")


def test_integrated_modules_close_all_five():
    registry = build_registry()
    ok, reports = registry.verify()
    failed = {report.module: report.open_closures for report in reports if not report.complete}
    assert ok, f"open closures: {failed}"
    required = {
        "compiler", "identity", "consequence_gate", "evidence_ledger",
        "evolution", "events", "autonomy", "proof", "loom", "twins",
        "capabilities", "embassy", "memory", "linker",
        "foundry", "business", "treasury",
        "advantage_foundry", "omnimorph", "developmental_substrate",
    }
    assert required.issubset(set(registry.modules()))
