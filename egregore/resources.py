"""Hard resource bounds for continuous cognition.

Attention is observed telemetry, never fuel, money, permission, or a reason to
increase autonomy.  Only explicit operator-supplied call and cost ceilings can
authorize cognition spend.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from .contracts import ContractError


class ResourceMode(str, Enum):
    NORMAL = "normal"
    CONSERVE = "conserve"
    HIBERNATE = "hibernate"


class ResourceExhausted(RuntimeError):
    """The next cognition call would exceed a declared hard bound."""


@dataclass(frozen=True)
class ResourceSnapshot:
    max_model_calls: int
    used_model_calls: int
    max_estimated_cost_usd: float
    used_estimated_cost_usd: float
    mode: ResourceMode
    attention_telemetry: float | None

    def to_dict(self) -> dict:
        return {
            "max_model_calls": self.max_model_calls,
            "used_model_calls": self.used_model_calls,
            "max_estimated_cost_usd": self.max_estimated_cost_usd,
            "used_estimated_cost_usd": self.used_estimated_cost_usd,
            "mode": self.mode.value,
            "attention_telemetry": self.attention_telemetry,
            "attention_confers_authority": False,
        }


class ResourceGovernor:
    """Monotonic, non-replenishing budget for one or more cognition ticks."""

    def __init__(
        self,
        *,
        max_model_calls: int,
        max_estimated_cost_usd: float,
        conservation_threshold: float = 0.25,
    ):
        if not isinstance(max_model_calls, int) or isinstance(max_model_calls, bool) or max_model_calls < 0:
            raise ContractError("max_model_calls must be a non-negative integer")
        if not isinstance(max_estimated_cost_usd, (int, float)) or isinstance(max_estimated_cost_usd, bool):
            raise ContractError("max_estimated_cost_usd must be numeric")
        max_cost = float(max_estimated_cost_usd)
        if not math.isfinite(max_cost) or max_cost < 0:
            raise ContractError("max_estimated_cost_usd must be finite and non-negative")
        if not isinstance(conservation_threshold, (int, float)) or not 0 <= float(conservation_threshold) <= 1:
            raise ContractError("conservation_threshold must be between 0 and 1")
        self.max_model_calls = max_model_calls
        self.max_estimated_cost_usd = max_cost
        self.conservation_threshold = float(conservation_threshold)
        self.used_model_calls = 0
        self.used_estimated_cost_usd = 0.0

    def consume_call(self, *, component: str, estimated_cost_usd: float) -> None:
        if not component or not isinstance(component, str):
            raise ContractError("component must be a non-empty string")
        if not isinstance(estimated_cost_usd, (int, float)) or isinstance(estimated_cost_usd, bool):
            raise ContractError("estimated_cost_usd must be numeric")
        cost = float(estimated_cost_usd)
        if not math.isfinite(cost) or cost < 0:
            raise ContractError("estimated_cost_usd must be finite and non-negative")
        if self.used_model_calls + 1 > self.max_model_calls:
            raise ResourceExhausted(f"model-call ceiling reached before {component}")
        if self.used_estimated_cost_usd + cost > self.max_estimated_cost_usd + 1e-12:
            raise ResourceExhausted(f"cost ceiling reached before {component}")
        self.used_model_calls += 1
        self.used_estimated_cost_usd += cost

    @property
    def mode(self) -> ResourceMode:
        if self.max_model_calls == 0 or self.max_estimated_cost_usd == 0:
            return ResourceMode.HIBERNATE
        call_remaining = (self.max_model_calls - self.used_model_calls) / self.max_model_calls
        cost_remaining = (
            self.max_estimated_cost_usd - self.used_estimated_cost_usd
        ) / self.max_estimated_cost_usd
        remaining = min(call_remaining, cost_remaining)
        if remaining <= 0:
            return ResourceMode.HIBERNATE
        if remaining <= self.conservation_threshold:
            return ResourceMode.CONSERVE
        return ResourceMode.NORMAL

    def snapshot(self, *, attention_telemetry: float | None = None) -> ResourceSnapshot:
        if attention_telemetry is not None:
            if not isinstance(attention_telemetry, (int, float)) or isinstance(attention_telemetry, bool):
                raise ContractError("attention_telemetry must be numeric when supplied")
            attention_telemetry = float(attention_telemetry)
            if not math.isfinite(attention_telemetry):
                raise ContractError("attention_telemetry must be finite")
        return ResourceSnapshot(
            max_model_calls=self.max_model_calls,
            used_model_calls=self.used_model_calls,
            max_estimated_cost_usd=self.max_estimated_cost_usd,
            used_estimated_cost_usd=self.used_estimated_cost_usd,
            mode=self.mode,
            attention_telemetry=attention_telemetry,
        )
