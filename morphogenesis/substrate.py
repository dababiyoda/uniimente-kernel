"""The lattice the cells sit on.

The substrate's only job is topology and scheduling: it knows who is adjacent
to whom, and it hands each cell its neighbours' values. It does not decide
anything. It contains no pattern, no target morphology, and no repair logic.

Topology is the open research question for this track (see
docs/DEVELOPMENTAL_TRACK.md). A 2-D torus is used here because it is the
substrate on which reaction-diffusion is best understood, which makes Stage 1
falsifiable. It is NOT a claim that institutional cells are spatially
arranged. Stage 4 is where a non-spatial topology has to be earned.
"""

import random

from . import cell


class Substrate:
    """A toroidal lattice of identical cells."""

    def __init__(self, width, height, seed=None):
        self.width = width
        self.height = height
        self.n = width * height
        self.rng = random.Random(seed)

        # Flat arrays: cache-friendlier and much faster than nested lists in
        # pure Python, which matters because the tests run thousands of ticks.
        self.u = [1.0] * self.n
        self.v = [0.0] * self.n

        self._ortho = self._build_ortho()
        self._diag = self._build_diag()

    # -- topology -----------------------------------------------------------

    def _build_ortho(self):
        w, h = self.width, self.height
        out = []
        for idx in range(self.n):
            x, y = idx % w, idx // w
            out.append((
                ((x - 1) % w) + y * w,
                ((x + 1) % w) + y * w,
                x + ((y - 1) % h) * w,
                x + ((y + 1) % h) * w,
            ))
        return out

    def _build_diag(self):
        w, h = self.width, self.height
        out = []
        for idx in range(self.n):
            x, y = idx % w, idx // w
            xm, xp = (x - 1) % w, (x + 1) % w
            ym, yp = (y - 1) % h, (y + 1) % h
            out.append((
                xm + ym * w,
                xp + ym * w,
                xm + yp * w,
                xp + yp * w,
            ))
        return out

    # -- initial conditions -------------------------------------------------

    def seed_uniform_with_noise(self, amplitude=0.25, fraction=0.08):
        """Uniform state plus undirected noise.

        This is the honest starting condition for a morphogenesis claim: the
        substrate is homogeneous, and the only asymmetry is noise. Noise is
        not a pattern. Anything structured that appears later was not put
        here.
        """
        self.u = [1.0] * self.n
        self.v = [0.0] * self.n
        for idx in range(self.n):
            if self.rng.random() < fraction:
                self.v[idx] = amplitude * self.rng.random()
                self.u[idx] = 1.0 - self.v[idx]

    # -- dynamics -----------------------------------------------------------

    def tick(self, dt=1.0):
        """One synchronous update of every cell, using only local rules."""
        u, v = self.u, self.v
        ortho, diag = self._ortho, self._diag
        step = cell.step

        nu = [0.0] * self.n
        nv = [0.0] * self.n

        for idx in range(self.n):
            o = ortho[idx]
            d = diag[idx]
            nu[idx], nv[idx] = step(
                u[idx], v[idx],
                (u[o[0]], u[o[1]], u[o[2]], u[o[3]]),
                (u[d[0]], u[d[1]], u[d[2]], u[d[3]]),
                (v[o[0]], v[o[1]], v[o[2]], v[o[3]]),
                (v[d[0]], v[d[1]], v[d[2]], v[d[3]]),
                dt,
            )

        self.u, self.v = nu, nv

    def run(self, steps, dt=1.0):
        for _ in range(steps):
            self.tick(dt)

    # -- injury -------------------------------------------------------------

    def excise(self, x0, y0, w, h):
        """Return a rectangular region to the naive uniform state.

        This is damage, not a repair hook. The substrate offers no way to
        record that damage occurred, and the cells have no way to learn of it
        except through their neighbours' concentrations.
        """
        for dy in range(h):
            for dx in range(w):
                idx = ((x0 + dx) % self.width) + ((y0 + dy) % self.height) * self.width
                self.u[idx] = 1.0
                self.v[idx] = 0.0

    # -- observation --------------------------------------------------------

    def expressed_fraction(self, region=None):
        """Fraction of cells expressing the activator phenotype."""
        indices = self._region_indices(region)
        if not indices:
            return 0.0
        hits = sum(1 for i in indices if cell.is_expressed(self.v[i]))
        return hits / len(indices)

    def interface_density(self, region=None):
        """Fraction of orthogonal neighbour pairs that straddle a phenotype
        boundary.

        This is a coarse proxy for characteristic length scale. A uniform
        field scores ~0 regardless of its value; a field with structure at the
        Turing wavelength scores well above 0. Using it alongside
        expressed_fraction distinguishes 'came back to the right density' from
        'came back with the right texture'.
        """
        indices = self._region_indices(region)
        if not indices:
            return 0.0
        boundary = 0
        total = 0
        for i in indices:
            here = cell.is_expressed(self.v[i])
            for j in self._ortho[i]:
                total += 1
                if here != cell.is_expressed(self.v[j]):
                    boundary += 1
        return boundary / total if total else 0.0

    def _region_indices(self, region):
        if region is None:
            return range(self.n)
        x0, y0, w, h = region
        return [
            ((x0 + dx) % self.width) + ((y0 + dy) % self.height) * self.width
            for dy in range(h)
            for dx in range(w)
        ]
