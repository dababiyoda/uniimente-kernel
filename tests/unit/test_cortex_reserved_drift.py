"""Drift between the cortex's reserved families and what GREG can execute (directive 2026-10-07, section 31 item 17).

cortex/genome.py registers RESERVED_FAMILIES disabled, "no executor in the seed experiment". GREG's one cognition
path (greg/cognition/catalog.py, including the IntelligenceGenome library) has since gained executors for several
of their mechanisms. cortex/genome.py is frozen code of the cortex 0.2.1 seed freeze, so the reconciliation lives
beside it in greg/cognition/reserved.py; it is explicit, never inferred, and this test keeps it true:

* every reserved family is exactly one of: superseded by a cortex seed organ, EXECUTED_ON_GREG (named executors
  that exist and run), or RESERVED_WITHOUT_EXECUTOR (with the reason, partial precursors included);
* the record follows cortex/genome.py's own convention (SUPERSEDED lineage naming every executor, else SPECIFIED),
  keeps the frozen lineage, and flags exactly the families whose frozen cortex record is behind; the frozen
  registry itself is untouched (still disabled, still its frozen lifecycle);
* a genome or catalog family whose identity names a reserved family's mechanism (its leaf name or its
  failure-diversity key) must be reconciled with that family, so a new executor cannot silently leave a reserved
  family claiming that nothing executes it.

What is not verified: that an executor implements the reserved mechanism well (admission evidence decides that,
docs/evidence/greg-mind-evidence-index.json), or that the name heuristic finds every executor (it is a net; the
explicit tables are the record).
"""
from __future__ import annotations

import importlib
import re

import pytest

from cortex.genome import RESERVED_FAMILIES, SEED_ORGANS, seed_registry
from greg.cognition.catalog import FAMILIES
from greg.cognition.genomes import library
from greg.cognition.reserved import EXECUTED_ON_GREG, RESERVED_WITHOUT_EXECUTOR, reconciled
from greg.cognition.solvers import SOLVERS


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower())


def _resolve(ref: str):
    """An executor reference -> the object that executes it on GREG's path, or None."""
    if ref.startswith("cognition."):
        family = ref.removeprefix("cognition.")
        if family not in FAMILIES:
            return None
        return SOLVERS.get(family)
    module, _, symbol = ref.partition(":")
    if not symbol:
        return None
    try:
        return getattr(importlib.import_module(module), symbol, None)
    except ImportError:
        return None


def test_every_reserved_family_is_reconciled_exactly_once():
    seed = {n for n in RESERVED_FAMILIES if n in SEED_ORGANS}
    executed, without = set(EXECUTED_ON_GREG), set(RESERVED_WITHOUT_EXECUTOR)
    assert not (seed & executed) and not (seed & without) and not (executed & without)
    assert seed | executed | without == set(RESERVED_FAMILIES), {
        "unreconciled": sorted(set(RESERVED_FAMILIES) - seed - executed - without),
        "not reserved": sorted((executed | without) - set(RESERVED_FAMILIES))}
    for name, reason in RESERVED_WITHOUT_EXECUTOR.items():
        assert reason.strip(), name


def test_every_named_executor_exists_and_runs_on_the_cognition_path():
    genomes = library.executables()
    for name, (executors, coverage) in EXECUTED_ON_GREG.items():
        assert executors and coverage.strip(), name
        for ref in executors:
            target = _resolve(ref)
            assert target is not None and (callable(target) or len(target) > 0), (name, ref)
            family = ref.removeprefix("cognition.")
            if ref.startswith("cognition.") and family in genomes:
                # a genome executor is the library's own adapter, so the reserved family runs where GREG routes
                assert SOLVERS[family].__qualname__.startswith("_genome_solver"), (name, ref)


def test_the_record_follows_the_cortex_convention_and_leaves_the_frozen_registry_untouched():
    registry, record = seed_registry(), reconciled()
    assert set(record) == set(RESERVED_FAMILIES)
    for name, row in record.items():
        frozen = registry.get(f"{name}@0.1.0")
        assert frozen.profile.role == "reserved" and frozen.profile.enabled is False and not row["enabled_in_cortex"]
        # the reserved capability is still unimplemented inside the cortex; the record says where it runs
        assert list(frozen.capability.failure_modes) == ["not implemented"], name
        assert row["frozen_lifecycle"] == frozen.profile.lifecycle
        assert row["lineage"][:len(frozen.profile.lineage)] == list(frozen.profile.lineage), name   # history kept
        if name in SEED_ORGANS:
            assert row["status"] == frozen.profile.lifecycle == "SUPERSEDED" and not row["frozen_record_behind"]
        elif name in EXECUTED_ON_GREG:
            executors, coverage = EXECUTED_ON_GREG[name]
            assert row["status"] == "SUPERSEDED" and row["executors"] == list(executors), name
            assert all(ref in row["lineage"][-1] for ref in executors) and coverage in row["lineage"][-1], name
            assert frozen.profile.lifecycle == "SPECIFIED" and row["frozen_record_behind"], name
        else:
            assert row["status"] == "SPECIFIED" and not row["executors"] and row["no_executor_reason"], name
            assert not row["frozen_record_behind"], name


def test_an_executor_named_after_a_reserved_mechanism_cannot_leave_it_claiming_no_executor():
    """The net: a family or intelligence id containing a reserved leaf name or diversity key is reconciled."""
    genomes = library.executables()
    identities = {family: {_norm(family)} | ({_norm(genomes[family].genome.intelligence_id)} if family in genomes
                                             else set())
                  for family in FAMILIES}
    unreconciled = []
    for name, (_, _, _, diversity, _) in RESERVED_FAMILIES.items():
        if name in SEED_ORGANS:
            continue
        tokens = {_norm(name.rsplit(".", 1)[1]), _norm(diversity)}
        for family, names in identities.items():
            if not any(token in ident for token in tokens for ident in names):
                continue
            ref = f"cognition.{family}"
            if name in EXECUTED_ON_GREG and ref in EXECUTED_ON_GREG[name][0]:
                continue
            if name in RESERVED_WITHOUT_EXECUTOR and re.search(rf"{re.escape(ref)}\b", RESERVED_WITHOUT_EXECUTOR[name]):
                continue          # named as a partial or different precursor, with the reason
            unreconciled.append((name, ref))
    assert not unreconciled, unreconciled


def test_the_net_catches_a_new_genome_named_after_a_reserved_mechanism(monkeypatch):
    """Falsification of the net itself: a family called after 'swarm_pso' must force a decision."""
    monkeypatch.setitem(FAMILIES, "swarm_pso_probe", (2, ("swarm_probe",), ("optimization",), "collective_trace", None))
    with pytest.raises(AssertionError) as caught:
        test_an_executor_named_after_a_reserved_mechanism_cannot_leave_it_claiming_no_executor()
    assert "cortex.collective.swarm_pso" in str(caught.value) and "cognition.swarm_pso_probe" in str(caught.value)
