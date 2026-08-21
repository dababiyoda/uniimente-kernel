"""Explicit runtime bindings — the half of the seam a LinkReport cannot supply.

A ``LinkReport`` proves that organ A produces contract C and organ B consumes
it. It says nothing about *which function* receives C at runtime. Deriving that
from string similarity — ``wire-opportunity-packet`` therefore
``wire.opportunity_packet`` therefore some handler — would be exactly the
fabrication the build order forbids.

So the mapping is written by hand, once, with provenance, and every field is
checked against reality at resolution time:

* the module must import,
* the resolved file must live under the declared repository root (otherwise
  another repository's same-named package shadowed it and the binding is
  resolving something other than what it claims),
* the attribute chain must exist and be callable,
* no declared bypass may be loaded.

A binding that cannot satisfy all four does not resolve. It raises.
"""
from __future__ import annotations

import importlib
import os
import sys
from dataclasses import dataclass, field


class BindingError(RuntimeError):
    """A binding could not be resolved, or resolved to the wrong thing.

    Fails closed. A binding that half-resolves is more dangerous than one that
    does not resolve at all, because the episode would keep running against
    something nobody declared.
    """


@dataclass(frozen=True)
class ResolvedEntryPoint:
    """A callable plus the evidence of where it actually came from."""

    call: object
    module_name: str
    module_file: str
    qualname: str
    repository_root: str

    def describe(self) -> dict:
        return {
            "module": self.module_name,
            "module_file": self.module_file,
            "qualname": self.qualname,
            "repository_root": self.repository_root,
        }


@dataclass(frozen=True)
class OrganEntryPoint:
    """Where an organ's code lives and which symbol the seam may call.

    ``repository_root`` is load-bearing, not documentation. DALEOBANKS and
    WealthMachineIntelligence are separate repositories checked out side by
    side; both are importable in one process, and the kernel has packages of
    its own. Verifying the resolved ``__file__`` against the declared root is
    what makes "we called WMI's intake" a measurement rather than a hope.
    """

    organ_id: str
    repository_root: str
    module: str
    attribute: str            # dotted: "OpportunityIntakeService.evaluate_packet"
    #: Path fragments that must NOT appear among loaded modules or executed
    #: files. Declared per binding so each binding names the bypass it knows
    #: about instead of relying on a global blocklist nobody maintains.
    forbidden_fragments: tuple[str, ...] = ()

    def available(self) -> bool:
        return os.path.isdir(self.repository_root)

    def resolve(self) -> ResolvedEntryPoint:
        if not self.available():
            raise BindingError(
                f"repository root {self.repository_root!r} for organ "
                f"{self.organ_id!r} does not exist; binding cannot resolve"
            )
        root = os.path.abspath(self.repository_root)
        # Appended, never inserted at position 0: the kernel's own packages
        # must keep priority so an organ can never shadow kernel code. The
        # module-file check below catches the opposite mistake.
        if root not in sys.path:
            sys.path.append(root)
        # Importing an organ must not modify it. Measured, not assumed: the
        # first run of this seam rewrote nineteen tracked .pyc files inside
        # WealthMachineIntelligence, which is a declared read-only repository.
        # A byte written into a read-only organ is a write, whatever its
        # contents.
        previously_wrote_bytecode = sys.dont_write_bytecode
        sys.dont_write_bytecode = True
        try:
            mod = importlib.import_module(self.module)
        except Exception as exc:
            raise BindingError(
                f"module {self.module!r} for organ {self.organ_id!r} did not "
                f"import: {type(exc).__name__}: {exc}"
            ) from exc
        finally:
            sys.dont_write_bytecode = previously_wrote_bytecode

        module_file = os.path.abspath(getattr(mod, "__file__", "") or "")
        if not module_file.startswith(root + os.sep):
            raise BindingError(
                f"module {self.module!r} resolved to {module_file!r}, which is "
                f"outside the declared repository {root!r} — another package "
                f"shadowed it and this binding is not what it claims to be"
            )

        target = mod
        walked = [self.module]
        for part in self.attribute.split("."):
            if not hasattr(target, part):
                raise BindingError(
                    f"{'.'.join(walked)} has no attribute {part!r}; the declared "
                    f"entry point {self.module}:{self.attribute} does not exist"
                )
            target = getattr(target, part)
            walked.append(part)
        if not callable(target):
            raise BindingError(
                f"{self.module}:{self.attribute} resolved to a non-callable "
                f"{type(target).__name__}"
            )

        return ResolvedEntryPoint(
            call=target,
            module_name=self.module,
            module_file=module_file,
            qualname=getattr(target, "__qualname__", self.attribute),
            repository_root=root,
        )

    # -- bypass reporting ---------------------------------------------------
    def loaded_bypasses(self) -> list[str]:
        """Which forbidden implementations are currently *importable* in-process.

        Context only — never a failure condition, and the distinction cost a
        run to learn. An earlier version refused any binding while a forbidden
        module sat in ``sys.modules``, which had two defects: DALEOBANKS is
        checked out beside the kernel, so its client is permanently importable
        and the seam could never route at all; and the bypass negative control
        imports the client by design, so running the control poisoned every
        state after it. Importable is not used.

        The load-bearing check is execution, in ``router._ExecutionWitness``:
        a file that never ran cannot have produced the result.
        """
        hits = []
        for name, mod in list(sys.modules.items()):
            path = getattr(mod, "__file__", None)
            if not path:
                continue
            if any(frag in path for frag in self.forbidden_fragments):
                hits.append(f"{name} -> {path}")
        return sorted(hits)


@dataclass(frozen=True)
class ConsumerBinding:
    """The runtime consumer of one contract, for one organ.

    Both halves of the founder's rule live here: ``organ_id`` and ``contract``
    must match a linker-proven edge, and ``entry_point`` must resolve to real
    code in the declared repository. Neither alone is sufficient.
    """

    organ_id: str
    contract: str
    entry_point: OrganEntryPoint
    declared_by: str
    reason: str
    #: When ``entry_point.attribute`` names a class, the seam constructs it with
    #: no arguments and calls ``method`` on the instance. Declared rather than
    #: guessed from whether the attribute happens to be a type.
    construct: bool = False
    method: str = ""

    def __post_init__(self) -> None:
        if self.organ_id != self.entry_point.organ_id:
            raise BindingError(
                f"binding organ {self.organ_id!r} disagrees with its entry "
                f"point organ {self.entry_point.organ_id!r}"
            )
        if self.construct and not self.method:
            raise BindingError(
                f"binding for {self.organ_id!r} constructs "
                f"{self.entry_point.attribute!r} but names no method to call"
            )

    def bind(self) -> tuple[object, ResolvedEntryPoint, dict]:
        """Resolve to the exact callable that will receive the contract.

        Returns the callable, the resolution evidence, and a description of the
        instance it is bound to (empty when the entry point is a plain
        function). Construction happens here, before any delivery, so a
        consumer that cannot even be built fails the route rather than the
        payload.
        """
        resolved = self.entry_point.resolve()
        if not self.construct:
            return resolved.call, resolved, {}
        try:
            instance = resolved.call()          # type: ignore[operator]
        except Exception as exc:
            raise BindingError(
                f"consumer {self.entry_point.module}:{self.entry_point.attribute} "
                f"could not be constructed: {type(exc).__name__}: {exc}"
            ) from exc
        if not hasattr(instance, self.method):
            raise BindingError(
                f"{type(instance).__name__} has no method {self.method!r}"
            )
        call = getattr(instance, self.method)
        if not callable(call):
            raise BindingError(f"{self.method!r} on {type(instance).__name__} is not callable")
        return call, resolved, {
            "instance_class": type(instance).__qualname__,
            "instance_module": type(instance).__module__,
            "method": self.method,
        }

    def describe(self) -> dict:
        return {
            "organ_id": self.organ_id,
            "contract": self.contract,
            "module": self.entry_point.module,
            "attribute": self.entry_point.attribute,
            "method": self.method,
            "declared_by": self.declared_by,
            "reason": self.reason,
            "forbidden_fragments": list(self.entry_point.forbidden_fragments),
        }


@dataclass(frozen=True)
class ProducerBinding:
    """The runtime producer of one contract.

    Declared symmetrically with the consumer so the episode never has to reach
    into an organ by hand. ``serializer`` is the organ's own canonical wire
    serialization — the seam does not invent a second one, because a bespoke
    serializer would make the delivery prove the seam's arithmetic instead of
    the organ's contract.
    """

    organ_id: str
    contract: str
    #: The organ's own input type (e.g. its ``Idea`` dataclass). Constructed
    #: from ``subject_kwargs`` so the episode feeds the real producer real
    #: input instead of hand-assembling something packet-shaped.
    subject: OrganEntryPoint
    subject_kwargs: dict
    entry_point: OrganEntryPoint
    method: str
    serializer: OrganEntryPoint
    declared_by: str
    reason: str
    extra_args: tuple = ()

    def produce(self) -> tuple[dict, dict]:
        """Run the organ's real producer and return (wire payload, evidence)."""
        subject_resolved = self.subject.resolve()
        producer_resolved = self.entry_point.resolve()
        serializer_resolved = self.serializer.resolve()

        subject = subject_resolved.call(**self.subject_kwargs)  # type: ignore[operator]
        producer = producer_resolved.call()                     # type: ignore[operator]
        if not hasattr(producer, self.method):
            raise BindingError(
                f"{type(producer).__name__} has no method {self.method!r}"
            )
        obj = getattr(producer, self.method)(subject, *self.extra_args)
        if obj is None:
            raise BindingError(
                f"{self.entry_point.module}:{self.entry_point.attribute}."
                f"{self.method} produced nothing for the declared subject; the "
                "episode has no packet to route and must not fabricate one"
            )
        wire = serializer_resolved.call(obj)                    # type: ignore[operator]
        return wire, {
            "subject": subject_resolved.describe(),
            "producer": producer_resolved.describe(),
            "producer_method": self.method,
            "serializer": serializer_resolved.describe(),
            "produced_type": type(obj).__qualname__,
        }

    def describe(self) -> dict:
        return {
            "organ_id": self.organ_id,
            "contract": self.contract,
            "subject": f"{self.subject.module}:{self.subject.attribute}",
            "producer": (
                f"{self.entry_point.module}:{self.entry_point.attribute}.{self.method}"
            ),
            "serializer": f"{self.serializer.module}:{self.serializer.attribute}",
            "declared_by": self.declared_by,
            "reason": self.reason,
        }
