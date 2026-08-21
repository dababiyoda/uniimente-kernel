"""Deficit detection wired to the real FunctionLossDetector's symptom model.

The detector observes and names SYMPTOMS. It never names a cure. This module
reuses `evolution.repair.detector.Symptom` rather than inventing a parallel
vocabulary, which is what "wire it in" has to mean if it means anything.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from evolution.repair.detector import Symptom      # the existing vocabulary


@dataclass(frozen=True)
class FunctionalDeficit:
    """What was observed. Deliberately contains no replacement information."""
    function_contract_id: str
    symptoms: tuple[Symptom, ...]
    severity: float
    confidence: float
    affected_obligations: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    observation_window: str
    unmet_roles: tuple[str, ...]      # WHICH duty is unmet, not who should fill it

    def leaks_a_solution(self) -> bool:
        """True if this deficit names any part of a cure. Must always be False."""
        banned = ("capability", "topology", "candidate", "replacement",
                  "organ", "cell_id", "attach")
        blob = " ".join([self.function_contract_id, *[s.kind for s in self.symptoms],
                         *[s.detail for s in self.symptoms],
                         *self.unmet_roles]).lower()
        return any(b in blob for b in banned)


class DeficitObserver:
    """Infers a deficit from OBSERVATIONS. Does not read the tissue's plan."""

    def observe(self, *, contract_id: str, required_roles: Iterable[str],
                produced_outputs: int, expected_outputs: int,
                filled_roles: Iterable[str],
                open_obligations: Iterable[str],
                window: str = "1 cycle") -> FunctionalDeficit | None:
        required = tuple(required_roles)
        filled = set(filled_roles)
        unmet = tuple(r for r in required if r not in filled)
        symptoms: list[Symptom] = []
        if produced_outputs < expected_outputs:
            # Uses the EXISTING vocabulary. SYMPTOM_KINDS is validated at
            # construction, so a parallel vocabulary is impossible by design -
            # which is exactly why wiring in beats reinventing.
            symptoms.append(Symptom("missing_edges",
                                    f"produced {produced_outputs} of {expected_outputs} required outputs"))
        if unmet:
            symptoms.append(Symptom("provider_unavailable",
                                    f"{len(unmet)} required duty/duties unanswered"))
        if not symptoms:
            return None
        severity = len(unmet) / max(1, len(required))
        return FunctionalDeficit(
            function_contract_id=contract_id, symptoms=tuple(symptoms),
            severity=severity, confidence=0.9 if unmet else 0.6,
            affected_obligations=tuple(open_obligations),
            evidence_refs=(f"observation:{window}",),
            observation_window=window, unmet_roles=unmet)
