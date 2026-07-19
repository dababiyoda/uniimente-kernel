"""KernelModel base — enforces Hard Rule 5 (determinism) and Hard Rule 4
(fail closed): every contract is frozen (immutable after creation) and forbids
extra fields, so ambiguity can never be silently absorbed.

Common base fields on every contract: schema_version, id (uuid4 hex),
created_at (UTC, timezone-aware).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _uuid4_hex() -> str:
    return uuid.uuid4().hex


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class KernelModel(BaseModel):
    """Base for all 20 constitutional contracts: frozen, extra-forbid."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = "0.1.0"
    id: str = Field(default_factory=_uuid4_hex)
    created_at: datetime = Field(default_factory=_utcnow)

    @field_validator("*", mode="after")
    @classmethod
    def _require_tz_aware_datetimes(cls, v):
        # Naive datetimes are ambiguous; ambiguity fails closed (Hard Rule 4).
        if isinstance(v, datetime) and (v.tzinfo is None or v.tzinfo.utcoffset(v) is None):
            raise ValueError("datetime fields must be timezone-aware (UTC)")
        return v
