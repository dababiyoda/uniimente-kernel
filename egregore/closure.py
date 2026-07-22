"""Five-closure verification for the standing-cognition module."""
from __future__ import annotations

from closure.framework import ModuleClosures

from .resources import ResourceGovernor, ResourceMode
from .runtime import StandingCognitionRuntime


def standing_cognition_closures() -> ModuleClosures:
    def technical() -> tuple[bool, str]:
        required = {"ingest", "tick", "suspend", "resume", "propose_change"}
        present = {name for name in required if callable(getattr(StandingCognitionRuntime, name, None))}
        return present == required, "restartable tick and lifecycle contracts are present"

    def authority() -> tuple[bool, str]:
        forbidden = {"execute", "publish", "post", "trade", "transfer", "sign", "apply_change"}
        exposed = [name for name in forbidden if hasattr(StandingCognitionRuntime, name)]
        return not exposed, "runtime exposes proposal authority only" if not exposed else f"forbidden methods: {exposed}"

    def evidence() -> tuple[bool, str]:
        fields = {"SIGNAL_RECORD", "SIGNAL_CONFLICT_RECORD", "CYCLE_RECORD", "CYCLE_CONFLICT_RECORD"}
        ok = all(hasattr(StandingCognitionRuntime, name) for name in fields)
        return ok, "positive, negative, and contradictory evidence have ledger record types"

    def economic() -> tuple[bool, str]:
        governor = ResourceGovernor(max_model_calls=0, max_estimated_cost_usd=1.0)
        return governor.mode == ResourceMode.HIBERNATE, "hard ceilings force zero-cost hibernation"

    def regenerative() -> tuple[bool, str]:
        governor = ResourceGovernor(max_model_calls=2, max_estimated_cost_usd=1.0)
        before = governor.snapshot(attention_telemetry=0).to_dict()
        after = governor.snapshot(attention_telemetry=10**9).to_dict()
        stable = (
            before["max_model_calls"] == after["max_model_calls"]
            and before["max_estimated_cost_usd"] == after["max_estimated_cost_usd"]
            and not after["attention_confers_authority"]
        )
        return stable, "attention cannot widen authority or resource ceilings"

    return ModuleClosures(
        module="egregore-standing-cognition",
        checks={
            "technical": technical,
            "authority": authority,
            "evidence": evidence,
            "economic": economic,
            "regenerative": regenerative,
        },
    )
