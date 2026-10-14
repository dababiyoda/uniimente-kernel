"""The IntelligenceGenome library claims nothing that code and frozen evidence do not support."""
from dataclasses import replace

from greg.cognition import genome_library as lib


def test_inventory_covers_every_registered_source():
    from cortex.genome import seed_registry
    from greg import genesis
    from greg.cognition import catalog, composition
    ids = {e.genome_id for e in lib.inventory()}
    assert set(seed_registry().keys()) <= ids
    assert {f"cognition.{f}" for f in catalog.FAMILIES} <= ids
    assert {f"genesis.{g}" for g in genesis.CATALOG} <= ids
    assert {f"composition.{r}" for r in composition.RECIPES} <= ids


def test_library_is_consistent_with_code_and_evidence():
    assert lib.check() == []


def test_reserved_cortex_families_are_never_implemented():
    from cortex.genome import seed_registry
    registry = seed_registry()
    for e in lib.inventory():
        if e.source == "cortex_organ" and not registry.get(e.genome_id).profile.enabled:
            assert not e.implemented and not e.integrated
            assert e.admission in ("FRONTIER_HORIZON", "SUPERSEDED")


def test_every_founder_layer_is_present():
    assert set(lib.matrix()) == {1, 2, 3, 4, 5}


def test_check_refuses_inflated_claims():
    entries = lib.inventory()
    horizon = next(e for e in entries if e.admission == "FRONTIER_HORIZON")
    rejected = next(e for e in entries if e.genome_id == "cognition.pattern")
    forged = [replace(horizon, implemented=True), replace(rejected, admission="DEFAULT_FOR_GEOMETRY"),
              replace(rejected, evidence_refs=("docs/evidence/does-not-exist.json",)),
              replace(horizon, admission="DEFAULT_FOR_GEOMETRY", evidence_refs=()),
              replace(horizon, admission="PERFECT")]
    problems = lib.check(forged)
    assert any("frontier horizon cannot be implemented" in p for p in problems)
    assert any("disagrees with frozen admission REJECTED" in p for p in problems)
    assert any("missing evidence" in p for p in problems)
    assert any("without evidence" in p for p in problems)
    assert any("closed vocabulary" in p for p in problems)
