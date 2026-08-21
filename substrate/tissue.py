"""Tissue: the medium cells live in, and the readout that no cell can perform.

The tissue is a POSTMAN and a SUBSTRATE, not a planner. It:

  - delivers signals only along declared neighbour edges
  - hands each cell a view restricted to that cell's own neighbours
  - never inspects the function contract
  - never chooses a topology
  - never tells a cell what to become

The readout (`precipitate`) serializes whatever attachment structure exists so
that constitutional admission has something to inspect. It runs AFTER
formation, reads only committed state, and cannot influence it. That ordering
is the whole separation: the observer that describes the candidate had no part
in producing it.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

from .cell import Cell, Interface, Signal, Tri


@dataclass
class TissueStats:
    ticks: int = 0
    messages: int = 0
    differentiations: int = 0
    inhibitions_sent: int = 0
    redundant_attachments: int = 0


class Tissue:
    """A neighbourhood graph of cells. Holds no goal and no plan."""

    def __init__(self, cells: list[Cell], *, seed: int = 0):
        self.cells = {c.cell_id: c for c in cells}
        self.rng = random.Random(seed)
        self.stats = TissueStats()
        self.trace: list[dict] = []
        self.partitioned: set[tuple[str, str]] = set()

    # -- environment ------------------------------------------------------
    def connect(self, a: str, b: str) -> None:
        self.cells[a].neighbours.add(b)
        self.cells[b].neighbours.add(a)

    def partition(self, a: str, b: str) -> None:
        """Communication damage. The edge exists but carries nothing."""
        self.partitioned.add(tuple(sorted((a, b))))

    def _blocked(self, a: str, b: str) -> bool:
        return tuple(sorted((a, b))) in self.partitioned

    def _neighbour_interfaces(self, c: Cell) -> dict[str, Interface]:
        """ONLY this cell's neighbours. The restriction is enforced here."""
        return {n: self.cells[n].interface for n in c.neighbours
                if n in self.cells and not self.cells[n].dissolved}

    def _neighbour_roles(self, c: Cell) -> dict[str, Optional[str]]:
        return {n: self.cells[n].differentiated_role for n in c.neighbours
                if n in self.cells and not self.cells[n].dissolved}

    # -- the deficit enters at a boundary, not at a planner ---------------
    def inject(self, cell_id: str, signal: Signal) -> None:
        self.cells[cell_id].inbox.append(signal)

    # -- run --------------------------------------------------------------
    def develop(self, max_ticks: int = 40) -> TissueStats:
        for tick in range(max_ticks):
            active = [c for c in self.cells.values()
                      if c.inbox and not c.dissolved]
            if not active:
                break
            self.stats.ticks += 1
            order = sorted(active, key=lambda c: c.cell_id)
            self.rng.shuffle(order)
            for c in order:
                before = c.differentiated_role
                c.step(self._neighbour_interfaces(c), self._neighbour_roles(c))
                if before is None and c.differentiated_role is not None:
                    self.stats.differentiations += 1
                    self.trace.append({"tick": tick, "cell": c.cell_id,
                                       "became": c.differentiated_role,
                                       "attached_to": c.attached_to})
            # deliver
            for c in order:
                for dest, sig in c.outbox:
                    if dest not in self.cells or self._blocked(c.cell_id, dest):
                        continue
                    if self.cells[dest].dissolved:
                        continue
                    self.cells[dest].inbox.append(sig)
                    self.stats.messages += 1
                    if sig.sign is Tri.INHIBIT:
                        self.stats.inhibitions_sent += 1
                c.outbox.clear()

        roles: dict[str, int] = {}
        for c in self.cells.values():
            if c.differentiated_role and not c.dissolved:
                roles[c.differentiated_role] = roles.get(c.differentiated_role, 0) + 1
        self.stats.redundant_attachments = sum(n - 1 for n in roles.values() if n > 1)
        return self.stats

    # -- readout: runs after, reads committed state, changes nothing -------
    def precipitate(self) -> Optional[dict]:
        """Serialize whatever formed. Returns None if no viable tissue exists.

        This is the only place a whole-structure view exists, and it exists
        only AFTER development has finished.
        """
        formed = [c for c in self.cells.values()
                  if c.differentiated_role and not c.dissolved]
        if not formed:
            return None

        roles = sorted({c.differentiated_role for c in formed})
        caps = sorted(c.capability for c in formed)
        # control topology is READ from the attachment shape, not chosen
        depth = self._chain_depth(formed)
        fanout = max((sum(1 for x in formed if x.attached_to == c.cell_id)
                      for c in formed), default=0)
        if fanout >= 2:
            control = "fan_out_vote"
        elif depth >= len(roles) and len(roles) > 1:
            control = "pipeline"
        else:
            control = "supervised_pair"

        return {
            "capabilities": caps,
            "roles_filled": roles,
            "control_topology": control,
            "communication": "direct" if control == "pipeline" else "broadcast",
            "verification": ("dual_read" if fanout >= 2 else "readback"),
            "memory_distribution": ("replicated" if fanout >= 2 else "central"),
            "resource_allocation": ("elastic" if fanout >= 2 else "static"),
            "recovery_behaviour": ("reassign" if control != "pipeline" else "restart"),
            "attachments": sorted(
                (c.cell_id, c.attached_to) for c in formed if c.attached_to),
            "cells": sorted(c.cell_id for c in formed),
        }

    def _chain_depth(self, formed: list[Cell]) -> int:
        by_id = {c.cell_id: c for c in formed}
        best = 0
        for c in formed:
            d, cur, guard = 1, c, 0
            while cur.attached_to in by_id and guard < 50:
                cur = by_id[cur.attached_to]
                d += 1
                guard += 1
            best = max(best, d)
        return best

    def damage_capability(self, capability: str) -> list[str]:
        killed = [c.cell_id for c in self.cells.values()
                  if c.capability == capability and not c.dissolved]
        for cid in killed:
            self.cells[cid].dissolve("capability lost")
        return killed

    def degrade_resources(self, factor: float) -> None:
        for c in self.cells.values():
            c.resource *= factor
