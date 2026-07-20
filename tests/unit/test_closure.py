"""Orthogonal closure tests: the five-closure standard itself."""
import json

from closure.framework import ClosureRegistry, ModuleClosures, CLOSURE_NAMES
from closure.complete_registry import build_registry


def test_five_closures_named_exactly():
    assert CLOSURE_NAMES == ("technical", "authority", "evidence", "economic", "regenerative")


def test_a_module_with_only_technical_closure_is_not_finished():
    reg = ClosureRegistry()
    reg.register(ModuleClosures("demo", {
        "technical": lambda: (True, "runs"),
        "authority": lambda: (False, "cannot prove authority"),
        "evidence": lambda: (True, "reconstructable"),
        "economic": lambda: (True, "saves cost"),
        "regenerative": lambda: (True, "no hidden harm"),
    }))
    ok, reports = reg.verify()
    report = reports[0]
    assert not ok
    assert not report.complete
    assert report.open_closures == ["authority"]


def test_crashing_check_fails_closed():
    reg = ClosureRegistry()

    def explode():
        raise RuntimeError("boom")

    reg.register(ModuleClosures("demo", {
        name: (explode if name == "technical" else (lambda: (True, "ok")))
        for name in CLOSURE_NAMES
    }))
    ok, reports = reg.verify()
    assert not ok
    assert any(
        "raised" in closure.detail
        for closure in reports[0].closures
        if closure.closure == "technical"
    )


def test_all_canonical_modules_close_all_five():
    """Every canonical module, including Foundry and OMNIMORPH, must close."""
    registry = build_registry()
    ok, reports = registry.verify()
    failures = [report.to_dict() for report in reports if not report.complete]
    assert ok, json.dumps(failures, indent=2, sort_keys=True)
    assert len(reports) == 15
    assert set(registry.modules()) == {
        "compiler", "identity", "consequence_gate", "evidence_ledger",
        "evolution", "events", "autonomy", "proof", "loom", "twins",
        "capabilities", "embassy", "memory", "foundry", "omnimorph",
    }
