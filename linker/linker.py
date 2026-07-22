"""The Institutional Linker: resolves typed edges between organs.

Doctrine (LINKER): organs are connected through named contracts, never
through each other's private state. An edge exists only when a producer's
contract name matches a consumer's contract name AND a schema file for
that contract exists in contracts/. Anything the graph cannot prove is
reported as disconnected or unresolved — the linker never invents an
edge, an identity, or an authority.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from linker.manifest import OrganManifest, ManifestError

KERNEL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTRACTS_DIR = os.path.join(KERNEL_ROOT, "contracts")


class LinkerError(ValueError):
    """Link resolution failed. Fails closed."""


@dataclass
class Edge:
    """One resolved typed connection: producer organ -> contract -> consumer organ."""
    producer: str          # organ_id
    consumer: str          # organ_id
    contract: str          # contract name (schema file stem)
    schema_path: str


@dataclass
class LinkReport:
    edges: list[Edge] = field(default_factory=list)
    unconsumed: list[tuple[str, str]] = field(default_factory=list)   # (organ_id, contract)
    unproduced: list[tuple[str, str]] = field(default_factory=list)   # (organ_id, contract)
    untyped: list[tuple[str, str]] = field(default_factory=list)      # contract named but no schema file
    unresolved: list[tuple[str, str]] = field(default_factory=list)   # (organ_id, open question)
    overlapping_authority: list[tuple[str, str]] = field(default_factory=list)  # (organ_id, capability_id)

    @property
    def fully_connected(self) -> bool:
        return not self.unproduced and not self.untyped


def known_contracts(contracts_dir: str = CONTRACTS_DIR) -> dict[str, str]:
    """Contract name -> schema path, from the contracts directory itself.
    The filesystem is the registry; no second list to drift."""
    out = {}
    for name in sorted(os.listdir(contracts_dir)):
        if name.endswith(".schema.json"):
            out[name[: -len(".schema.json")]] = os.path.join(contracts_dir, name)
    return out


class InstitutionalLinker:
    def __init__(self, manifests: list[OrganManifest], contracts_dir: str = CONTRACTS_DIR):
        if not manifests:
            raise LinkerError("no manifests to link")
        ids = [m.organ_id for m in manifests]
        if len(ids) != len(set(ids)):
            raise LinkerError(f"duplicate organ identities: {ids}")
        self.manifests = manifests
        self.contracts = known_contracts(contracts_dir)

    def link(self) -> LinkReport:
        report = LinkReport()
        producers: dict[str, list[str]] = {}   # contract -> [organ_id]
        consumers: dict[str, list[str]] = {}

        for m in self.manifests:
            for c in m.produces:
                producers.setdefault(c, []).append(m.organ_id)
            for c in m.consumes:
                consumers.setdefault(c, []).append(m.organ_id)
            for q in m.unresolved:
                report.unresolved.append((m.organ_id, q))
            for cap in m.capabilities:
                if cap["lifecycle"] == "SPECIALIZED":
                    # Organ-local implementation of something the kernel owns
                    # canonically. Preserved, never deleted — but flagged so
                    # overlapping authority stays visible and governed.
                    report.overlapping_authority.append((m.organ_id, cap["capability_id"]))

        named = set(producers) | set(consumers)
        for contract in sorted(named):
            if contract not in self.contracts:
                for organ in producers.get(contract, []) + consumers.get(contract, []):
                    report.untyped.append((organ, contract))
                continue
            for p in producers.get(contract, []):
                for c in consumers.get(contract, []):
                    if p != c:
                        report.edges.append(Edge(
                            producer=p, consumer=c, contract=contract,
                            schema_path=self.contracts[contract]))
            if contract not in consumers:
                for p in producers[contract]:
                    report.unconsumed.append((p, contract))
            if contract not in producers:
                for c in consumers[contract]:
                    report.unproduced.append((c, contract))
        return report

    def edges_between(self, producer_id: str, consumer_id: str) -> list[Edge]:
        return [e for e in self.link().edges
                if e.producer == producer_id and e.consumer == consumer_id]
