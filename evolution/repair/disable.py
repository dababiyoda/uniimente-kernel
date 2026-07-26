"""Adapter 1 of 4 — runtime component disable.

The removal has to be real. A stub that returns the right answer would make the
whole experiment theatre, so this makes the target package genuinely
unreachable: a `sys.meta_path` finder refuses to locate it, and any already
imported submodules are evicted from `sys.modules`. Every import path — plain
`import`, `importlib`, a transitive import from a third module — fails.

Nothing is deleted from disk. Disable is a runtime condition, which is exactly
why rollback is one step: lift the finder and the original path works again.

This is generic over package name. It knows nothing about the linker.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from importlib.abc import MetaPathFinder


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class ComponentUnavailable(ModuleNotFoundError):
    """Raised on any attempt to import a disabled component.

    Subclasses ModuleNotFoundError so callers that already handle a missing
    dependency degrade the way they would in production, rather than taking a
    special path that only exists during the experiment.
    """


class _RefusingFinder(MetaPathFinder):
    """Refuses to find one package and its submodules. Ignores everything else."""

    def __init__(self, package: str):
        self.package = package
        self._prefix = package + "."
        self.attempts: list[str] = []

    def find_module(self, fullname, path=None):        # pragma: no cover - legacy
        self.find_spec(fullname, path)
        return None

    def find_spec(self, fullname, path=None, target=None):
        if fullname == self.package or fullname.startswith(self._prefix):
            self.attempts.append(fullname)
            raise ComponentUnavailable(
                f"component {self.package!r} is disabled at runtime",
                name=fullname)
        return None


@dataclass
class DisableEvent:
    """The recorded fact that a component was removed, and when."""
    package: str
    evicted_modules: tuple[str, ...]
    disabled_at: str = field(default_factory=_now)
    lifted_at: str | None = None
    import_attempts: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {"type": "repair.component_disabled", "package": self.package,
                "evicted_modules": list(self.evicted_modules),
                "disabled_at": self.disabled_at, "lifted_at": self.lifted_at,
                "import_attempts": list(self.import_attempts)}


class ComponentDisabled:
    """Context manager making `package` unimportable for the duration.

        with ComponentDisabled("linker", ledger=ledger) as disabled:
            ...                      # the component is genuinely gone
        # ... and genuinely back

    Reentrant-safe only in the sense that nesting the same package twice is
    refused: silently tolerating it would make the lift ambiguous.
    """

    _active: set[str] = set()

    def __init__(self, package: str, *, ledger=None):
        if not package:
            raise ValueError("package name required")
        self.package = package
        self.ledger = ledger
        self.finder: _RefusingFinder | None = None
        self.event: DisableEvent | None = None
        self._saved: dict[str, object] = {}

    # -- lifecycle ---------------------------------------------------------

    def __enter__(self) -> DisableEvent:
        if self.package in ComponentDisabled._active:
            raise RuntimeError(f"{self.package} is already disabled")

        prefix = self.package + "."
        self._saved = {name: mod for name, mod in sys.modules.items()
                       if name == self.package or name.startswith(prefix)}
        for name in self._saved:
            del sys.modules[name]

        self.finder = _RefusingFinder(self.package)
        sys.meta_path.insert(0, self.finder)
        ComponentDisabled._active.add(self.package)

        self.event = DisableEvent(package=self.package,
                                  evicted_modules=tuple(sorted(self._saved)))
        if self.ledger is not None:
            self.ledger.append("event", self.event.to_dict())
        return self.event

    def __exit__(self, *exc) -> None:
        self.lift()
        return None

    def lift(self) -> DisableEvent | None:
        """Restore the original import path. One step, by construction."""
        if self.finder is not None and self.finder in sys.meta_path:
            sys.meta_path.remove(self.finder)
        ComponentDisabled._active.discard(self.package)

        # Put back exactly the module objects that were evicted, so any object
        # holding a reference from before the disable stays consistent with a
        # fresh import afterwards.
        for name, mod in self._saved.items():
            sys.modules.setdefault(name, mod)

        if self.event is not None:
            self.event.lifted_at = _now()
            if self.finder is not None:
                self.event.import_attempts = tuple(self.finder.attempts)
            if self.ledger is not None:
                self.ledger.append("event", {**self.event.to_dict(),
                                             "type": "repair.component_restored"})
        self._saved = {}
        self.finder = None
        return self.event


def is_disabled(package: str) -> bool:
    return package in ComponentDisabled._active
