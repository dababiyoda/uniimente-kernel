"""Phase 5 — Institutional Twins: read-only counterfactual forks.

Doctrine (TWINS): before the institution changes itself, a twin lives
the change in parallel. A twin is a hermetic fork of the compiled
constitution plus one proposed amendment; it evaluates proposals exactly
as the main institution would under that amendment — and it can never
touch the main state, the ledger, or the outside world. Twins think;
they do not act.

The fork is read-only by construction: it deep-copies everything it
might mutate and exposes only evaluation.
"""
from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass, field

from policy.engine import evaluate


@dataclass
class Amendment:
    """One declarative counterfactual change."""
    description: str
    evidence_thresholds: dict | None = None        # consequence_class -> new floor
    extra_dimensions: dict | None = None           # policy dimension overrides (future)


@dataclass
class InstitutionalTwin:
    main_compiled: object                          # the unmodified compiled constitution
    amendment: Amendment
    twin_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self):
        # hermetic copy: nothing the twin does can leak into main state
        self._compiled = copy.deepcopy(self.main_compiled)
        self._thresholds = dict(self.amendment.evidence_thresholds or {})

    def evaluate(self, proposal, *, identity_ok=True, grant=None, now=None):
        """Evaluate exactly as main would under the amendment."""
        return evaluate(self._compiled, proposal, identity_ok=identity_ok,
                        grant=grant, now=now, thresholds=self._thresholds or None)

    def diverges_from_main(self) -> bool:
        """Sanity: the amendment actually changes at least one parameter."""
        return bool(self._thresholds or self.amendment.extra_dimensions)
