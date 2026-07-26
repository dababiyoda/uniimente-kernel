"""Candidate R1-contract-index — inverted index, then set algebra.

MATERIAL DIFFERENCE FROM THE ORIGINAL. The original walks the manifests, builds
producer/consumer maps as a side effect of that walk, then iterates the named
contracts and branches per contract, accumulating refusals with counters and
`continue`. R1 inverts the order of operations: one indexing pass builds
`contract -> (producers, consumers)` as frozensets, and then every output —
edges, untyped, unconsumed, unproduced — is a single set expression over those
indices. There is no per-contract branch and no accumulator.

The relation computed is identical; the way it is computed is not. That is the
distinction the experiment is testing, so it is stated plainly rather than
implied by a rename.

This module does not import the original. It is an independent implementation
of the declared contract, not a wrapper.
"""
from __future__ import annotations

import os
from itertools import product

from evolution.repair.candidate import FunctionOutput

#: Lift the runtime disable, withdraw R1 as provider, re-register the original.
ROLLBACK_STEPS = 3


def _typed_contracts(contracts_dir: str) -> frozenset[str]:
    """The contract registry is the filesystem, read once."""
    suffix = ".schema.json"
    return frozenset(
        name[: -len(suffix)] for name in os.listdir(contracts_dir)
        if name.endswith(suffix)
    )


class ContractIndexInversion:
    """Index-first resolver. Set algebra decides; nothing branches per contract."""

    candidate_id = "R1-contract-index"
    mechanism = "single inverted-index pass, then set algebra over the indices"

    def resolve(self, manifests: list, contracts_dir: str) -> FunctionOutput:
        typed = _typed_contracts(contracts_dir)

        # ---- one indexing pass -------------------------------------------
        produced_by: dict[str, set[str]] = {}
        consumed_by: dict[str, set[str]] = {}
        for manifest in manifests:
            for contract in manifest.produces:
                produced_by.setdefault(contract, set()).add(manifest.organ_id)
            for contract in manifest.consumes:
                consumed_by.setdefault(contract, set()).add(manifest.organ_id)

        producers = {k: frozenset(v) for k, v in produced_by.items()}
        consumers = {k: frozenset(v) for k, v in consumed_by.items()}

        # ---- set algebra -------------------------------------------------
        named = frozenset(producers) | frozenset(consumers)
        untyped_names = named - typed
        resolvable = named & typed

        empty: frozenset[str] = frozenset()

        untyped = {
            (organ, contract)
            for contract in untyped_names
            for organ in producers.get(contract, empty) | consumers.get(contract, empty)
        }

        edges = {
            (p, contract, q)
            for contract in resolvable
            for p, q in product(producers.get(contract, empty),
                                consumers.get(contract, empty))
            if p != q
        }

        # A typed contract nobody consumes; and a typed contract nobody
        # produces. Both fall out of the indices as set differences — the
        # original reaches the same two facts through per-contract membership
        # tests inside its scan loop.
        unconsumed = {
            (producer, contract)
            for contract in resolvable - frozenset(consumers)
            for producer in producers.get(contract, empty)
        }
        unproduced = {
            (consumer, contract)
            for contract in resolvable - frozenset(producers)
            for consumer in consumers.get(contract, empty)
        }

        unresolved = {(m.organ_id, question)
                      for m in manifests for question in m.unresolved}
        overlapping = {
            (m.organ_id, cap["capability_id"])
            for m in manifests for cap in m.capabilities
            if cap.get("lifecycle") == "SPECIALIZED"
        }

        return FunctionOutput.normalize(
            edges=edges, untyped=untyped, unconsumed=unconsumed,
            unproduced=unproduced, unresolved=unresolved,
            overlapping_authority=overlapping,
            diagnostics=(f"indexed {len(named)} named contracts, "
                         f"{len(resolvable)} resolvable, "
                         f"{len(untyped_names)} untyped",),
        )


def factory() -> ContractIndexInversion:
    return ContractIndexInversion()
