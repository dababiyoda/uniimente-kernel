"""Adapter 2 of 4 — blind function-loss detection.

WHAT THIS MODULE IS NOT TOLD. It does not know which module provides the
capability, that anything was removed, or which replacement ought to win. It
holds two things: a capability name and a declared output contract. It asks the
provider registry for whoever answers to that name and compares what comes back
against the contract.

Deliberate consequence: when the provider cannot be built, this records the
exception *type* and discards the exception *message*. The message would say
"No module named 'linker'" and hand the detector the identity of the failed
module — the exact knowledge it must not have. Losing that string costs real
diagnostic value, and it is the price of the blindness being genuine rather than
asserted. The module identity is still recoverable from the disable event, which
is recorded separately by whoever performed the removal.

Grep-checkable invariant, asserted by the test suite: no import of the subject
package appears here, and no report this module produces names a module path.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from evolution.repair.candidate import FunctionOutput

#: Symptoms are institutional, not implementational. Each says something about
#: a capability's observable behaviour, never about a file.
SYMPTOM_KINDS = (
    "provider_unavailable",   # nothing answers to the capability name
    "provider_failed",        # something answers but cannot be built or run
    "malformed_output",       # the output is not even the right shape
    "missing_edges",          # required relations absent
    "incorrect_edges",        # relations present that the contract does not allow
    "refusal_incorrect",      # the refusal behaviour changed
    "health_check_failed",    # the capability is not self-consistent
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class Symptom:
    kind: str
    detail: str

    def __post_init__(self):
        if self.kind not in SYMPTOM_KINDS:
            raise ValueError(f"unknown symptom kind {self.kind!r}")


@dataclass
class CapabilityLossReport:
    """A lost institutional function, named as a function.

    `lost` is the finding. `symptoms` is the evidence. Neither carries a module
    path, an import error string, or a file name.
    """
    capability: str
    lost: bool
    symptoms: tuple[Symptom, ...] = ()
    observed_edges: int = 0
    required_edges: int = 0
    corpus_id: str = "LIVE"
    detected_at: str = field(default_factory=_now)

    @property
    def function_fraction(self) -> float:
        """Fraction of required relations observed correctly. Reported for
        information; it is NOT the pass criterion — see `restored`."""
        if not self.required_edges:
            return 0.0
        return self.observed_edges / self.required_edges

    @property
    def restored(self) -> bool:
        """The function is restored only when nothing is wrong with it.

        Not `function_fraction >= threshold`. Three of four required edges is
        0.75, and a detector that called that a partial success would be exactly
        the false recovery report this experiment forbids. Any symptom at all
        means not restored.
        """
        return not self.lost and not self.symptoms

    def to_dict(self) -> dict:
        return {"type": "repair.capability_loss_detected" if self.lost
                        else "repair.capability_healthy",
                "capability": self.capability, "lost": self.lost,
                "corpus_id": self.corpus_id,
                "symptoms": [{"kind": s.kind, "detail": s.detail}
                             for s in self.symptoms],
                "observed_edges": self.observed_edges,
                "required_edges": self.required_edges,
                "function_fraction": self.function_fraction,
                "detected_at": self.detected_at}


@dataclass(frozen=True)
class DeclaredContract:
    """What the capability is obliged to produce. The detector's only knowledge.

    Expressed as expected relations, not as an implementation. Built from the
    frozen spec for the live corpus, and from the frozen held-out expectations
    for the synthetic ones.
    """
    capability: str
    corpus_id: str
    required_edges: tuple[tuple[str, str, str], ...]
    required_untyped: tuple[tuple[str, str], ...]
    required_unconsumed: tuple[tuple[str, str], ...]
    required_unproduced: tuple[tuple[str, str], ...]
    required_unresolved_count: int
    required_overlapping: tuple[tuple[str, str], ...]
    required_fully_connected: bool


class FunctionLossDetector:
    """Observes a capability and reports whether the institution still has it."""

    def __init__(self, registry, *, ledger=None):
        self.registry = registry
        self.ledger = ledger

    # -- observation -------------------------------------------------------

    def _observe(self, contract: DeclaredContract, manifests, contracts_dir):
        """Try to obtain the capability's output. Returns (output, symptoms)."""
        try:
            resolver = self.registry.instantiate(contract.capability)
        except LookupError:
            return None, (Symptom("provider_unavailable",
                                  f"nothing answers to {contract.capability}"),)
        except Exception as exc:
            # Type only. The message is discarded on purpose; see module docstring.
            return None, (Symptom("provider_failed",
                                  f"provider could not be built "
                                  f"({type(exc).__name__})"),)

        try:
            output = resolver.resolve(manifests, contracts_dir)
        except Exception as exc:
            return None, (Symptom("provider_failed",
                                  f"capability raised while resolving "
                                  f"({type(exc).__name__})"),)

        if not isinstance(output, FunctionOutput) or not output.is_wellformed():
            return None, (Symptom("malformed_output",
                                  "output is not a well-formed capability result"),)
        return output, ()

    # -- the check ---------------------------------------------------------

    def detect(self, contract: DeclaredContract, manifests, contracts_dir
               ) -> CapabilityLossReport:
        """Is the institution still able to do this?

        Fires on absence, on incorrectness, on wrong refusal behaviour, and on
        internal inconsistency. Stays silent when the capability is healthy.
        """
        output, symptoms = self._observe(contract, manifests, contracts_dir)
        required = len(contract.required_edges)

        if output is None:
            report = CapabilityLossReport(
                capability=contract.capability, lost=True, symptoms=symptoms,
                observed_edges=0, required_edges=required,
                corpus_id=contract.corpus_id)
            return self._record(report)

        found = list(symptoms)
        observed = set(output.edges)
        expected = set(contract.required_edges)

        missing = sorted(expected - observed)
        if missing:
            found.append(Symptom(
                "missing_edges",
                f"{len(missing)} of {required} required relations absent: "
                f"{missing}"))
        extra = sorted(observed - expected)
        if extra:
            found.append(Symptom(
                "incorrect_edges",
                f"{len(extra)} relations asserted that the contract does not "
                f"permit: {extra}"))

        for name, obs, req in (
                ("untyped", output.untyped, contract.required_untyped),
                ("unconsumed", output.unconsumed, contract.required_unconsumed),
                ("unproduced", output.unproduced, contract.required_unproduced),
                ("overlapping_authority", output.overlapping_authority,
                 contract.required_overlapping)):
            if tuple(sorted(obs)) != tuple(sorted(req)):
                found.append(Symptom(
                    "refusal_incorrect",
                    f"{name}: expected {sorted(req)}, observed {sorted(obs)}"))

        if len(output.unresolved) != contract.required_unresolved_count:
            found.append(Symptom(
                "refusal_incorrect",
                f"unresolved: expected {contract.required_unresolved_count} "
                f"carried questions, observed {len(output.unresolved)}"))

        # Health check: the capability must be internally consistent. A result
        # claiming full connection while reporting unproduced or untyped
        # relations contradicts itself, whatever the edges say.
        if output.fully_connected is not contract.required_fully_connected:
            found.append(Symptom(
                "health_check_failed",
                f"connectivity claim {output.fully_connected} contradicts the "
                f"declared contract {contract.required_fully_connected}"))

        report = CapabilityLossReport(
            capability=contract.capability, lost=bool(found),
            symptoms=tuple(found), observed_edges=len(observed & expected),
            required_edges=required, corpus_id=contract.corpus_id)
        return self._record(report)

    def verify_recovery(self, contract: DeclaredContract, manifests,
                        contracts_dir) -> CapabilityLossReport:
        """Post-install check. Recovery means `report.restored`, which requires
        zero symptoms — partial output can never be reported as recovered."""
        return self.detect(contract, manifests, contracts_dir)

    def _record(self, report: CapabilityLossReport) -> CapabilityLossReport:
        if self.ledger is not None:
            self.ledger.append("event", report.to_dict())
        return report
