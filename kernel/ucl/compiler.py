"""UCL compiler — turns the Constitution model into the gate's policy_fn.

``compile_policy_fn(model, *, policy_version, constitution_version)`` returns
a callable with EXACTLY the signature the WP-01 gate expects::

    policy_fn(intent, *, intent_fingerprint, policy_version, constitution_version, trace) -> PolicyDecision

Evaluation order (SPEC-WP02 "Compiled policy_fn semantics"); every step
appends its clause id and observed value to the decision trace, and a DENY
short-circuits (the constitution never asks "anything else?" after a refusal):

1. ``ucl:shutdown_state`` — safety_states ladder (shutdown-policy.ucl).
   "normal": no constraint. "manual_approval_only": force REQUIRE_HUMAN.
   Otherwise ("constrained", "read_only", "quarantined", "recovery",
   "archived", "shutdown"): DENY external effects (C2+); C0/C1 internal
   allowed.
2. ``ucl:permanent_prohibitions`` — constitution.ucl permanent_prohibitions.
   A hit on intent.action_type / intent.objective (normalized keyword match)
   or payload["reserved_matter"] (exact match) DENYs with
   governing_clauses=["permanent_prohibitions:<matter>"]. This is the
   self-amendment protection: action_type "constitutional_amendment" always
   DENYs, for any actor (amendment_rule "constitutional_amendment":
   may_never = any_agent / any_workflow / uniimente_itself).
3. ``ucl:participant_rights`` — participant-rights.ucl hard_refusal rights
   (rank 1 in the sovereignty hierarchy). payload["participant_harm"] truthy
   DENYs under right "safety"; payload["requires_unlawful_conduct"] truthy
   DENYs under right "lawful_treatment". Absence means not triggered
   (documented limitation: the flags are proposer assertions).
4. ``ucl:consequence_default`` — constitution.ucl doctrine.humans_authorize:
   C0/C1 PERMIT, C2/C3/C4 REQUIRE_HUMAN, C5 DENY (reserved/catastrophic
   class). ADR: stricter than the WP-01 default (which DENIED C3+); this
   mapping is the compiled constitution's own choice, recorded in the trace.
   The compiler NEVER emits PERMIT for classes >= C2; REQUIRE_HUMAN is
   unbypassable downstream (WP-01 Hard Rule 3).

Determinism (WP-01 Hard Rule 5): the trace contains no wall-time and no
randomness; same .ucl inputs + same intent produce a byte-identical
decision_trace. A policy_fn bound to the wrong versions raises UCLError —
fail closed on any ambiguity (kernel_invariant on_violation).
"""
from __future__ import annotations

from typing import Any, Callable

from ..contracts.action import ActionIntent, PolicyDecision
from .lexer import UCLError
from .model import Constitution

CONSEQUENCE_CLASSES = ("C0", "C1", "C2", "C3", "C4", "C5")
_INTERNAL_CLASSES = ("C0", "C1")
_FORCE_APPROVAL_STATE = "manual_approval_only"
_NORMAL_STATE = "normal"

# payload flag -> participant right whose enforcement is hard_refusal.
_HARM_FLAG_TO_RIGHT = (
    ("participant_harm", "safety"),
    ("requires_unlawful_conduct", "lawful_treatment"),
)


def _normalize(text: Any) -> str:
    """Lowercase, underscores -> spaces, collapsed whitespace (keyword match)."""
    return " ".join(str(text).lower().replace("_", " ").split())


def _match_prohibitions(
    model: Constitution, intent: ActionIntent
) -> list[tuple[str, str]]:
    """Non-delegable matters hit by this intent, sorted for determinism.

    reserved_matter: exact string match. action_type / objective: normalized
    keyword (substring) match — the constitution names effects, not syntax,
    so paraphrases like "shutdown override" still hit "shutdown_override".
    """
    reserved = intent.payload.get("reserved_matter")
    if reserved is not None and not isinstance(reserved, str):
        raise UCLError("payload.reserved_matter must be a string; ambiguity fails closed")
    action_type = _normalize(intent.action_type)
    objective = _normalize(intent.objective)
    found: list[tuple[str, str]] = []
    for matter in sorted(model.permanent_prohibitions):
        if reserved is not None and reserved == matter:
            found.append((matter, "reserved_matter"))
        elif _normalize(matter) in action_type:
            found.append((matter, "action_type"))
        elif _normalize(matter) in objective:
            found.append((matter, "objective"))
    return found


def _evaluate(
    model: Constitution, intent: ActionIntent, trace: list[str]
) -> tuple[str, list[str], list[str]]:
    """Run the four constitutional steps. Returns (effect, clauses, trace)."""
    clauses: list[str] = []
    cls = intent.consequence_class
    if cls not in CONSEQUENCE_CLASSES:
        # The gate's CLASSIFY stage guards this too; defense in depth fails closed.
        raise UCLError(f"unknown consequence_class {cls!r}")

    # -- Step 1: ucl:shutdown_state (safety_states ladder, shutdown-policy.ucl)
    state = model.current_state
    floor: str | None = None
    if state == _NORMAL_STATE:
        trace.append("EVALUATE: ucl:shutdown_state state=normal constraint=none")
    elif state == _FORCE_APPROVAL_STATE:
        floor = "REQUIRE_HUMAN"
        clauses.append(f"ucl:shutdown_state:{state}")
        trace.append(
            f"EVALUATE: ucl:shutdown_state state={state} constraint=REQUIRE_HUMAN "
            f"external_effects={model.safety_states[state]}"
        )
    else:
        external_effects = model.safety_states[state]
        if cls in _INTERNAL_CLASSES:
            trace.append(
                f"EVALUATE: ucl:shutdown_state state={state} "
                f"external_effects={external_effects} class={cls} internal=allowed"
            )
        else:
            clauses.append(f"ucl:shutdown_state:{state}")
            trace.append(
                f"EVALUATE: ucl:shutdown_state state={state} "
                f"external_effects={external_effects} class={cls} effect=DENY"
            )
            return "DENY", clauses, trace

    # -- Step 2: ucl:permanent_prohibitions (constitution.ucl non_delegable)
    matches = _match_prohibitions(model, intent)
    if matches:
        matter, via = matches[0]
        clauses.append(f"permanent_prohibitions:{matter}")
        trace.append(
            f"EVALUATE: ucl:permanent_prohibitions matched={matter} via={via} effect=DENY"
        )
        return "DENY", clauses, trace
    trace.append("EVALUATE: ucl:permanent_prohibitions matched=none")

    # -- Step 3: ucl:participant_rights (hard_refusal rights, rank 1)
    triggered = [
        (flag, right) for flag, right in _HARM_FLAG_TO_RIGHT if intent.payload.get(flag)
    ]
    if triggered:
        for flag, right in triggered:
            clauses.append(f"participant_rights:{right}:hard_refusal")
            trace.append(
                f"EVALUATE: ucl:participant_rights flag={flag} right={right} "
                f"enforcement=hard_refusal effect=DENY"
            )
        return "DENY", clauses, trace
    trace.append("EVALUATE: ucl:participant_rights flags=none")

    # -- Step 4: ucl:consequence_default (doctrine.humans_authorize)
    if cls in _INTERNAL_CLASSES:
        default = "PERMIT"
    elif cls == "C5":
        default = "DENY"
    elif model.humans_authorize:
        default = "REQUIRE_HUMAN"
    else:  # humans cannot authorize: the only fail-closed option is refusal
        default = "DENY"
    clauses.append(f"consequence_default:{cls}:{default}")
    trace.append(
        f"EVALUATE: ucl:consequence_default humans_authorize={model.humans_authorize} "
        f"class={cls} effect={default}"
    )

    effect = default
    if floor == "REQUIRE_HUMAN" and effect == "PERMIT":
        effect = "REQUIRE_HUMAN"
    return effect, clauses, trace


def compile_policy_fn(
    model: Constitution, *, policy_version: str, constitution_version: str
) -> Callable[..., PolicyDecision]:
    """Compile the Constitution model into a gate-compatible policy_fn."""
    if not isinstance(model, Constitution):
        raise UCLError("compile_policy_fn requires a Constitution model")
    if not policy_version or not constitution_version:
        raise UCLError("policy_version and constitution_version are required")
    # A compiled policy_fn is only valid for exactly the constitution it was
    # compiled from; the closure binds those versions permanently.
    bound_policy_version = policy_version
    bound_constitution_version = constitution_version

    def policy_fn(
        intent: ActionIntent,
        *,
        intent_fingerprint: str,
        policy_version: str,
        constitution_version: str,
        trace: list[str],
    ) -> PolicyDecision:
        """Compiled constitution: evaluate ``intent`` per the four steps."""
        if policy_version != bound_policy_version:
            raise UCLError(
                f"policy_fn invoked with policy_version {policy_version!r}; "
                f"this policy_fn was compiled for {bound_policy_version!r}"
            )
        if constitution_version != bound_constitution_version:
            raise UCLError(
                f"policy_fn invoked with constitution_version {constitution_version!r}; "
                f"this policy_fn was compiled for {bound_constitution_version!r}"
            )
        decision_trace = list(trace)
        effect, clauses, decision_trace = _evaluate(model, intent, decision_trace)
        decision_trace.append(
            f"EVALUATE: ucl:final effect={effect} governing_clauses=[{', '.join(clauses)}]"
        )
        return PolicyDecision(
            intent_fingerprint=intent_fingerprint,
            effect=effect,
            governing_clauses=clauses,
            policy_version=policy_version,
            constitution_version=constitution_version,
            decision_trace=decision_trace,
        )

    return policy_fn
