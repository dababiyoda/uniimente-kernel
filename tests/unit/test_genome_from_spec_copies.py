"""A genome built from a module's GENOME_SPEC owns its lists and dicts (review of #286).

``genome_from_spec`` copied only the top level, so a caller that edited a genome's ``failure_modes`` or
``acceptance_tests`` edited the module's spec and every genome built after it. Before #286, ``capability_genome()``
built fresh lists on every call; this keeps that property.
"""
from __future__ import annotations

import copy

from capabilities.specs import genome_from_spec
from provenance import witness


def test_editing_a_built_genome_leaves_the_spec_and_later_genomes_alone():
    held = copy.deepcopy(witness.GENOME_SPEC)
    g = genome_from_spec(witness.GENOME_SPEC)
    g.failure_modes.clear()
    g.acceptance_tests.append("x")
    assert witness.GENOME_SPEC == held
    assert witness.capability_genome().validate() == []


def test_every_mutable_field_is_a_fresh_object():
    a, b = genome_from_spec(witness.GENOME_SPEC), genome_from_spec(witness.GENOME_SPEC)
    for name, value in witness.GENOME_SPEC.items():
        if isinstance(value, (list, dict)) and name != "authority":
            assert getattr(a, name) is not value and getattr(a, name) is not getattr(b, name), name
