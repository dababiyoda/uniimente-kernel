"""Orthogonal loop closure: the exact standard the builder must use.

Doctrine (the attached specification, section 6):

    A module is complete only when it passes five orthogonal closures.

    Technical closure    - it executes, survives failure, passes its tests.
    Authority closure    - no action occurs without current identity,
                           policy and permission.
    Evidence closure     - the result can be independently reconstructed
                           and verified.
    Economic closure     - the component reduces cost, produces revenue,
                           protects capital or creates a durable asset.
    Regenerative closure - the gain does not depend on hidden harm,
                           transferred burden or depleted institutional
                           capacity.

    A module passing only technical tests is not finished.
    A system that works but cannot prove authority is not finished.
    A business that earns revenue but destroys founder attention is not
    finished. An automation that saves time but creates unreconciled risk
    is not finished.

This module is the loop: register modules, run closures, report. The
recursive build loop runs until every module closes all five.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from typing import Callable

CLOSURE_NAMES = ("technical", "authority", "evidence", "economic", "regenerative")


@dataclass
class ClosureResult:
    closure: str
    ok: bool
    detail: str
    elapsed_ms: float = 0.0


@dataclass
class ModuleReport:
    module: str
    closures: list[ClosureResult] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return len(self.closures) == len(CLOSURE_NAMES) and all(c.ok for c in self.closures)

    @property
    def open_closures(self) -> list[str]:
        done = {c.closure for c in self.closures if c.ok}
        return [c for c in CLOSURE_NAMES if c not in done]

    def to_dict(self) -> dict:
        return {"module": self.module, "complete": self.complete,
                "open_closures": self.open_closures,
                "closures": [asdict(c) for c in self.closures]}


Check = Callable[[], tuple[bool, str]]


@dataclass
class ModuleClosures:
    """Five checks, one per orthogonal closure, for one module."""
    module: str
    checks: dict[str, Check]          # closure name -> check

    def run(self) -> ModuleReport:
        report = ModuleReport(module=self.module)
        for name in CLOSURE_NAMES:
            check = self.checks.get(name)
            if check is None:
                report.closures.append(ClosureResult(name, False, "no check registered"))
                continue
            start = time.perf_counter()
            try:
                ok, detail = check()
            except Exception as e:  # a crashing check fails closed
                ok, detail = False, f"check raised {type(e).__name__}: {e}"
            elapsed = (time.perf_counter() - start) * 1000
            report.closures.append(ClosureResult(name, bool(ok), str(detail), elapsed))
        return report


class ClosureRegistry:
    """All modules under closure. The build is done when verify() is green."""

    def __init__(self):
        self._modules: dict[str, ModuleClosures] = {}

    def register(self, module: ModuleClosures) -> None:
        self._modules[module.module] = module

    def modules(self) -> list[str]:
        return sorted(self._modules)

    def verify(self) -> tuple[bool, list[ModuleReport]]:
        reports = [self._modules[m].run() for m in self.modules()]
        return all(r.complete for r in reports), reports

    def verify_module(self, name: str) -> ModuleReport:
        return self._modules[name].run()
