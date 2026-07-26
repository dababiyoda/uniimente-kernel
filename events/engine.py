"""The governed workflow-engine seam.

Package 4, founder decision 1. This opens ONE narrow seam: which class the
canonical construction sites instantiate when they build a durable workflow. It
does not redesign the Event Spine, the Evidence Ledger, the Kernel registry, the
Loom, authority, or shutdown.

INVARIANTS, ENFORCED HERE RATHER THAN PROMISED

  - The original `DurableWorkflow` is the default. `_ACTIVE is None` means "the
    original", so the default is not a stored choice that could drift — it is
    the absence of a choice.
  - Module state is process-local and never persisted. **After any process
    restart the original is the provider again**, because there is nothing on
    disk for a replacement to be restored from.
  - Activation is a context manager only. There is deliberately no
    `set_default()`, so no replacement can make itself the permanent default.
  - Activation is allowlisted per workflow id. A workflow outside the allowlist
    gets the original even while a replacement is active.
  - A replacement is handed a GUARDED ledger. There is no unguarded append path,
    so pre-append validation cannot be skipped by a candidate that would rather
    not be validated.

WHY THE GUARD LIVES AT THE SEAM. The founder's correction is that a malformed
checkpoint must be refused before it is appended, not detected afterwards. If
validation lived inside a candidate it would be the candidate's choice; if it
lived in a checker run after the fact the bad record would already be in the
chain. Putting it in the seam makes it the price of admission.

This module knows there may be a validator. It does not know the rules — those
are Package 4's, in `evolution/migration/`. Dependency direction stays clean:
the canonical runtime never imports the experiment.
"""
from __future__ import annotations

import contextlib
from dataclasses import dataclass, field


class EngineRefused(RuntimeError):
    """A checkpoint failed pre-append validation. The record was NOT appended."""


class ActivationRefused(ValueError):
    """A replacement may not be activated as requested. Fails closed."""


# --------------------------------------------------------------------------
# Process-local activation state. Never persisted; the default is the original.
# --------------------------------------------------------------------------

_ACTIVE = None            # engine class, or None meaning "the original"
_ACTIVE_ID: str | None = None
_ALLOWLIST: frozenset[str] = frozenset()
_VALIDATOR = None         # callable(payload, context) -> list[str] problems
_ACTIVATED_BY: str | None = None


def original_engine():
    """The default provider. Imported lazily so this module stays importable
    from inside `events.spine` without a cycle."""
    from events.spine import DurableWorkflow

    return DurableWorkflow


def is_active() -> bool:
    return _ACTIVE is not None


def active_provider_id() -> str | None:
    return _ACTIVE_ID


def allowlist() -> frozenset[str]:
    return _ALLOWLIST


# --------------------------------------------------------------------------
# The guarded ledger — the only ledger a replacement ever sees
# --------------------------------------------------------------------------

@dataclass
class GuardedLedger:
    """Wraps a ledger and validates `workflow` checkpoints BEFORE append.

    Everything that is not a workflow checkpoint passes straight through: the
    seam governs the engine, not the ledger's other users.

    On a validation failure the malformed payload is dropped, a valid rejection
    event is appended in its place, and `EngineRefused` is raised. The prior
    valid checkpoint is untouched by construction — this never mutates or
    removes anything, it only declines to add.
    """
    inner: object
    validator: object
    context: dict
    refusals: list = field(default_factory=list)

    def append(self, record_type: str, payload: dict, **kw):
        if record_type != "workflow":
            return self.inner.append(record_type, payload, **kw)

        problems = list(self.validator(payload, self.context) or ())
        if problems:
            refusal = {
                "type": "workflow.checkpoint_refused",
                "workflow_id": payload.get("workflow_id"),
                "provider_id": self.context.get("provider_id"),
                "problems": problems,
                # The offending payload's KEYS are recorded, not its values: the
                # point is an audit trail of the refusal, not a second copy of
                # the malformed record inside the chain.
                "rejected_payload_keys": sorted(str(k) for k in payload),
                "prior_checkpoint_untouched": True,
            }
            self.refusals.append(refusal)
            self.inner.append("event", refusal)
            raise EngineRefused(
                f"checkpoint refused before append: {problems}")

        return self.inner.append(record_type, payload, **kw)

    # -- transparent delegation for every other ledger use ------------------
    def __getattr__(self, name):
        return getattr(self.inner, name)


class _GuardedSpine:
    """A spine whose `.ledger` is guarded. Everything else delegates.

    The engine only ever reaches the ledger through `spine.ledger`, so swapping
    that one attribute is enough to make validation unavoidable — without
    touching `EventSpine` itself.
    """

    __slots__ = ("_inner", "ledger")

    def __init__(self, inner, ledger):
        object.__setattr__(self, "_inner", inner)
        object.__setattr__(self, "ledger", ledger)

    def __getattr__(self, name):
        return getattr(self._inner, name)


# --------------------------------------------------------------------------
# Resolution — what the canonical construction sites call
# --------------------------------------------------------------------------

def resolve(spine, workflow_id: str):
    """(engine_class, spine) for this workflow.

    Returns the original and the untouched spine unless a replacement is active
    AND this workflow id is allowlisted. The inactive path allocates nothing and
    changes no behaviour, which is what makes the default genuinely the default.
    """
    if _ACTIVE is None or workflow_id not in _ALLOWLIST:
        return original_engine(), spine

    guarded = GuardedLedger(
        inner=spine.ledger, validator=_VALIDATOR,
        context={"workflow_id": workflow_id, "provider_id": _ACTIVE_ID,
                 "activated_by": _ACTIVATED_BY})
    return _ACTIVE, _GuardedSpine(spine, guarded)


@contextlib.contextmanager
def activate(engine, *, provider_id: str, workflow_ids, activated_by: str,
             validator, ledger=None):
    """Scoped, temporary, allowlisted, reversible activation.

    A context manager and nothing else. Leaving the block restores the original,
    and so does an exception, and so does a process restart.
    """
    global _ACTIVE, _ACTIVE_ID, _ALLOWLIST, _VALIDATOR, _ACTIVATED_BY

    if _ACTIVE is not None:
        raise ActivationRefused(
            f"{_ACTIVE_ID} is already active; nested activation is refused "
            "because it would make the restore target ambiguous")
    if engine is original_engine():
        raise ActivationRefused(
            "the original is the default and is never 'activated'; that would "
            "turn the absence of a choice into a stored one")
    if not provider_id or not activated_by:
        raise ActivationRefused("activation must name the provider and the "
                                "principal activating it")
    if activated_by == provider_id:
        raise ActivationRefused(
            f"{provider_id} named itself as its own activating principal; no "
            "component may authorize its own promotion")
    ids = frozenset(workflow_ids)
    if not ids:
        raise ActivationRefused("activation requires a non-empty workflow-id "
                                "allowlist; unbounded activation is not scoped")
    if validator is None:
        raise ActivationRefused(
            "a replacement may not run without pre-append validation")

    _ACTIVE, _ACTIVE_ID, _ALLOWLIST = engine, provider_id, ids
    _VALIDATOR, _ACTIVATED_BY = validator, activated_by
    if ledger is not None:
        ledger.append("event", {"type": "workflow.provider_activated",
                                "provider_id": provider_id,
                                "activated_by": activated_by,
                                "workflow_ids": sorted(ids),
                                "scope": "temporary, context-bound"})
    try:
        yield
    finally:
        _ACTIVE = _ACTIVE_ID = _VALIDATOR = _ACTIVATED_BY = None
        _ALLOWLIST = frozenset()
        if ledger is not None:
            ledger.append("event", {"type": "workflow.provider_restored",
                                    "provider_id": "W0-original",
                                    "reason": "activation scope exited"})


def assert_default_is_original() -> bool:
    """True when the provider is the original. Used to prove restoration after
    an activation scope, and after a simulated process restart."""
    return _ACTIVE is None and _ALLOWLIST == frozenset()
