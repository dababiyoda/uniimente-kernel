"""Bounded semantic drift measurement.

Cosine distance from a historical centroid is useful telemetry, but it is not
Shannon entropy and is therefore named explicitly rather than overstated.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from .contracts import ContractError


@dataclass(frozen=True)
class DriftReport:
    mean_cosine_distance: float
    sample_size: int
    dimension: int
    metric: str = "semantic_centroid_drift"

    def to_dict(self) -> dict:
        return {
            "metric": self.metric,
            "mean_cosine_distance": self.mean_cosine_distance,
            "sample_size": self.sample_size,
            "dimension": self.dimension,
            "is_entropy": False,
        }


def _vector(value: Sequence[float], *, name: str) -> tuple[float, ...]:
    if isinstance(value, (str, bytes)) or not value:
        raise ContractError(f"{name} must be a non-empty numeric vector")
    result = []
    for item in value:
        if not isinstance(item, (int, float)) or isinstance(item, bool):
            raise ContractError(f"{name} must contain only numbers")
        number = float(item)
        if not math.isfinite(number):
            raise ContractError(f"{name} must contain only finite numbers")
        result.append(number)
    if math.sqrt(sum(item * item for item in result)) == 0:
        raise ContractError(f"{name} must not be a zero vector")
    return tuple(result)


def semantic_centroid_drift(
    current_vectors: Sequence[Sequence[float]],
    historical_centroid: Sequence[float],
) -> DriftReport:
    """Return mean cosine distance in [0, 2] for equally-sized vectors."""
    if isinstance(current_vectors, (str, bytes)) or not current_vectors:
        raise ContractError("current_vectors must contain at least one vector")
    centroid = _vector(historical_centroid, name="historical_centroid")
    centroid_norm = math.sqrt(sum(item * item for item in centroid))
    distances: list[float] = []
    for index, raw in enumerate(current_vectors):
        vector = _vector(raw, name=f"current_vectors[{index}]")
        if len(vector) != len(centroid):
            raise ContractError("all vectors must have the same dimension")
        norm = math.sqrt(sum(item * item for item in vector))
        similarity = sum(a * b for a, b in zip(vector, centroid)) / (norm * centroid_norm)
        similarity = max(-1.0, min(1.0, similarity))
        distances.append(1.0 - similarity)
    return DriftReport(
        mean_cosine_distance=sum(distances) / len(distances),
        sample_size=len(distances),
        dimension=len(centroid),
    )
