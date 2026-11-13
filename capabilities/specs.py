"""Build Capability Genomes from plain data.

A package that must not import ``capabilities`` (the published boundary
distribution: adapters, contracts, events, provenance) declares its genome as a
``GENOME_SPEC`` dict; the kernel builds and validates it here. This lives in its
own module because ``capabilities/genome.py`` is pinned by digest in frozen
evaluations (``cortex/evaluation/**/freeze-*.json``) and is not edited for this.
"""
from __future__ import annotations
import copy

from capabilities.genome import AuthorityEnvelope, CapabilityGenome


def genome_from_spec(spec: dict) -> CapabilityGenome:
    """A CapabilityGenome from a module's ``GENOME_SPEC`` (its ``authority`` is a dict)."""
    data = copy.deepcopy(spec)            # the genome owns its lists and dicts; the module spec stays as written
    data["authority"] = AuthorityEnvelope(**data["authority"])
    return CapabilityGenome(**data)
