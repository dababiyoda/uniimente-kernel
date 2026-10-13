"""Typed failure reasons for standing cognition.

A failure is classified by *what raised it*, never by words in its message. A
transport error that says "connection refused" is transient infrastructure; a
constitutional refusal is a policy decision and must be raised as
``DoctrinalRefusal`` (or recorded with an explicit class) to count as one.

Classes are the evolution package's vocabulary so capsules, failure analysis and
genesis dossiers share one set of names.
"""
from __future__ import annotations

import socket
import urllib.error
from typing import Any, Mapping

from evolution.failure_analysis import FAILURE_CLASSES

from .contracts import ContractError
from .resources import ResourceExhausted


class DoctrinalRefusal(ContractError):
    """Raised only when the constitution, policy or Gate refused the attempt."""


class CapabilityMissing(ContractError):
    """Raised when a required capability, grant or permission is absent."""


_TRANSIENT = (ConnectionError, TimeoutError, socket.timeout, urllib.error.URLError, OSError)

# Exception class names, for records hydrated from the ledger where only the
# name survives. Order matters: subclasses before their parents.
_BY_NAME = (
    ("DoctrinalRefusal", "doctrinal_refusal"),
    ("CapabilityMissing", "capability_missing"),
    ("ResourceExhausted", "budget_exceeded"),
    ("ConnectionRefusedError", "transient"),
    ("ConnectionResetError", "transient"),
    ("ConnectionError", "transient"),
    ("TimeoutError", "transient"),
    ("timeout", "transient"),
    ("URLError", "transient"),
    ("HTTPError", "transient"),
    ("OSError", "transient"),
)


def classify_exception(exc: BaseException) -> str:
    """Map an exception to a failure class by type."""
    if isinstance(exc, DoctrinalRefusal):
        return "doctrinal_refusal"
    if isinstance(exc, CapabilityMissing):
        return "capability_missing"
    if isinstance(exc, ResourceExhausted):
        return "budget_exceeded"
    if isinstance(exc, _TRANSIENT):
        return "transient"
    return "executor_error"


def classify_record(failure: Mapping[str, Any]) -> str:
    """Classify a recorded failure: explicit class first, then exception type name.

    The message is never consulted.
    """
    explicit = failure.get("failure_class")
    if explicit in FAILURE_CLASSES:
        return explicit
    name = str(failure.get("error_type", ""))
    for suffix, klass in _BY_NAME:
        if name == suffix or name.endswith("." + suffix):
            return klass
    return "executor_error"


def failure_record(exc: BaseException, **extra: Any) -> dict[str, Any]:
    """A ledger-ready failure with its typed class attached."""
    return {
        "error_type": type(exc).__name__,
        "error": str(exc),
        "failure_class": classify_exception(exc),
        **extra,
    }
