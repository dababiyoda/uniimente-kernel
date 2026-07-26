"""Pre-append checkpoint validation. The founder's correction, as code.

A defective replacement must not be able to append a malformed checkpoint and
have it merely detected afterwards. This module supplies the validator that
`events/engine.py` installs on the guarded ledger, so a replacement engine has
no unguarded path to append through.

The nine rules are frozen in `spec.PRE_APPEND_VALIDATION_RULES`; this is their
implementation, and a test asserts every frozen rule has a check here.

FAIL CLOSED. Any problem returns a non-empty list, the seam drops the payload,
appends a rejection event, and raises. Nothing here mutates or removes anything,
so the prior valid checkpoint is untouched by construction rather than by
promise.
"""
from __future__ import annotations

import jsonschema

from evolution.migration.spec import (
    LEGAL_STATUS_TRANSITIONS, TERMINAL_STATUSES, W0_STATE_SCHEMA, W2_STATE_SCHEMA,
)

SCHEMAS = {"W0": W0_STATE_SCHEMA, "W2": W2_STATE_SCHEMA}

#: Which schema each engine writes. Frozen alongside the candidates.
ENGINE_SCHEMA = {
    "W0-original": "W0",
    "W1-projection": "W0",     # same shape; the difference is how it is READ
    "W2-token": "W2",          # the schema-changing candidate
    "W3-journal": "W0",        # W0 shape plus an undo stack inside `state`
}


def schema_for(provider_id: str | None) -> dict:
    return SCHEMAS[ENGINE_SCHEMA.get(provider_id or "W0-original", "W0")]


def _position_problems(payload: dict, context: dict) -> list[str]:
    """Rule 5: position must resolve. An index outside the step list, or a name
    that is not a declared step, is a corrupt checkpoint whichever schema it is
    written in."""
    step_names = list(context.get("step_names") or ())
    problems = []

    if "cursor" in payload:
        cursor = payload["cursor"]
        if step_names and not (0 <= cursor <= len(step_names)):
            problems.append(
                f"cursor {cursor} outside [0, {len(step_names)}]")
    if "next_step" in payload:
        nxt = payload["next_step"]
        if nxt is not None and step_names and nxt not in step_names:
            problems.append(f"next_step {nxt!r} is not a declared step")
        completed = payload.get("completed_steps") or []
        unknown = [s for s in completed if step_names and s not in step_names]
        if unknown:
            problems.append(f"completed_steps names not declared: {unknown}")
        if len(set(completed)) != len(completed):
            problems.append(
                f"completed_steps contains duplicates: {completed} — a step "
                "recorded twice is duplicated work, not a checkpoint")
    return problems


def _transition_problems(payload: dict, context: dict) -> list[str]:
    """Rules 6 and 7: legal transitions only, and terminal means terminal."""
    prior = context.get("prior_status")
    status = payload.get("status")
    if prior is None or status is None:
        return []
    if prior in TERMINAL_STATUSES:
        return [f"{prior!r} is terminal; no successor status is legal "
                f"(attempted {status!r})"]
    allowed = LEGAL_STATUS_TRANSITIONS.get(prior, ())
    if status not in allowed:
        return [f"illegal status transition {prior!r} -> {status!r}"]
    return []


def validate_checkpoint(payload: dict, context: dict) -> list[str]:
    """Return every problem with this checkpoint. Empty list means appendable.

    `context` carries what the payload alone cannot prove: which provider is
    writing, which workflow the seam resolved, the declared step names, and the
    prior status.
    """
    problems: list[str] = []

    if not isinstance(payload, dict):
        return ["checkpoint payload is not an object"]

    # Rule 1 — declared schema for the active engine.
    schema = schema_for(context.get("provider_id"))
    for err in jsonschema.Draft202012Validator(schema).iter_errors(payload):
        path = "/".join(str(p) for p in err.path) or "<root>"
        problems.append(f"schema[{schema['title']}] {path}: {err.message}")

    # Rule 2 — workflow identity matches the workflow the seam resolved.
    expected_id = context.get("workflow_id")
    actual_id = payload.get("workflow_id")
    if expected_id and actual_id != expected_id:
        problems.append(
            f"workflow identity mismatch: seam resolved {expected_id!r}, "
            f"checkpoint claims {actual_id!r}")

    # Rule 3 — actor and legal principal present.
    if not payload.get("actor"):
        problems.append("checkpoint carries no actor")
    principal = payload.get("legal_principal")
    if not principal:
        problems.append("checkpoint carries no legal principal")

    # Rule 4 — UNIIMENTE is never a legal principal.
    if principal == "UNIIMENTE":
        problems.append("UNIIMENTE is never a legal principal")

    # Rules 5-7 — position and status transitions.
    problems.extend(_position_problems(payload, context))
    problems.extend(_transition_problems(payload, context))

    # Rules 8-9 — migration integrity, when the seam is carrying one.
    migration = context.get("migration")
    if migration is not None:
        if migration.get("ambiguous"):
            problems.append(
                f"ambiguous migration refused: {migration.get('reason')}")
        lost = migration.get("lost_keys") or []
        if lost:
            problems.append(f"migration lost required state keys: {sorted(lost)}")

    return problems


def make_validator(*, step_names, prior_status_fn, migration=None):
    """Bind a validator to one workflow's declared steps and status history.

    `prior_status_fn()` is read at append time rather than captured, so the
    transition check sees the status as of this append, not as of activation.
    """
    def _validator(payload: dict, context: dict) -> list[str]:
        ctx = dict(context)
        ctx["step_names"] = step_names
        ctx["prior_status"] = prior_status_fn()
        if migration is not None:
            ctx["migration"] = migration
        return validate_checkpoint(payload, ctx)

    return _validator
