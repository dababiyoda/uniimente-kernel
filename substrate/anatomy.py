"""Mechanism-level anatomy for UNIIMENTE's developmental substrate.

The registry records reusable mechanisms extracted from educational technologies.
It does not vendor or reproduce tutorial products. Every mutation remains bounded,
traceable, and incapable of increasing execution authority.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class AnatomyError(ValueError):
    """Raised when a primitive or mutation is incomplete or unsafe.""