"""Orthogonal closure tests: the five-closure standard itself."""
from closure.framework import ClosureRegistry, ModuleClosures, CLOSURE_NAMES
from closure.kernel_registry import build_registry


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
    reg.register(ModuleClosures("demo", {n: (explode if n == "technical" else (lambda: (True, "ok")))
                                         for n in CLOSURE_NAMES}))
    ok, reports = reg.verify()
    assert not ok
    assert any("raised" in c.detail for c in reports[0].closures if c.closure == "technical")


def test_kernel_modules_close_all_five():
    """The Stage A modules must pass every orthogonal closure."""
    reg = build_registry()
    ok, reports = reg.verify()
    failed = {r.module: r.open_closures for r in reports if not r.complete}
    assert ok, f"open closures: {failed}"
    assert set(reg.modules()) == {"compiler", "identity", "consequence_gate", "evidence_ledger"}
