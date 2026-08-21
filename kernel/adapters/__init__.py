"""Execution adapters — Hard Rule 1: adapters may only execute with a current,
verified CommitWitness. No witness, no execute. No exceptions.

Every BoundedAdapter re-verifies the witness itself (presence, type, signature
against the authority key, expiry, one-use) so that bypassing the gate still
fails closed.
"""
from .base import Adapter, BoundedAdapter
from .benchmark import BenchmarkAdapter
from .echo import EchoAdapter
from .http_research import FetchResult, HttpResearchAdapter

__all__ = [
    "Adapter",
    "BenchmarkAdapter",
    "BoundedAdapter",
    "EchoAdapter",
    "FetchResult",
    "HttpResearchAdapter",
]
