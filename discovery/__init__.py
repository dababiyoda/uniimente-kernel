"""Capability Discovery (Foundry technology #27, FBO §4.10).

Discovery answers "who offers what, under which contract, at what authority
requirement, and is it healthy" — and nothing else. It is the read model the
Composer, the Router and any future module loader consult before proposing work.

    Discovery does not grant access.

That sentence is the whole security posture of this package, and it is asserted
by test rather than trusted: the service exposes no method that mints a grant,
opens the Consequence Gate, or widens a ceiling, and an AST check forbids it
from importing the gate at all.
"""
from discovery.service import (
    CapabilityAdvertisement,
    CapabilityDiscoveryService,
    DiscoveryError,
    DiscoveryQuery,
    OrganAdvertisement,
)

__all__ = [
    "CapabilityAdvertisement", "CapabilityDiscoveryService", "DiscoveryError",
    "DiscoveryQuery", "OrganAdvertisement",
]
