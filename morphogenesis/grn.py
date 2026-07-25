"""Differentiation as a dynamical attractor, not an enum.

The claim this module has to make good on:

    A cell type is a stable fixed point of a gene regulatory network, reached
    by local dynamics from an undifferentiated state. It is not a field
    someone sets.

The difference is testable and it matters. If a cell type is an enum, then
every type that exists is a type someone anticipated, and the system can only
produce the organs its author imagined. If a cell type is an attractor, the
state space decides what is stable, and the set of viable types is a property
of the regulatory topology rather than of anyone's foresight.

Implemented as Hopfield-style associative dynamics because the attractor
structure is analytically understood, which makes the tests falsifiable
rather than decorative.
"""

import random


class RegulatoryNetwork:
    """A symmetric regulatory network with imprinted stable states."""

    def __init__(self, n_genes, n_types, seed=None):
        self.n = n_genes
        self.rng = random.Random(seed)

        # Loading ratio. Hopfield capacity degrades badly past ~0.138; staying
        # well under it keeps spurious attractors rare enough to measure.
        self.types = [
            [1 if self.rng.random() < 0.5 else -1 for _ in range(n_genes)]
            for _ in range(n_types)
        ]

        self.w = [[0.0] * n_genes for _ in range(n_genes)]
        for pattern in self.types:
            for i in range(n_genes):
                pi = pattern[i]
                row = self.w[i]
                for j in range(n_genes):
                    if i != j:
                        row[j] += pi * pattern[j] / n_genes

    def relax(self, state, max_sweeps=60):
        """Run local regulatory dynamics to a fixed point.

        Asynchronous update in random order — the biologically honest choice,
        and the one that guarantees convergence for a symmetric network.
        """
        state = list(state)
        order = list(range(self.n))
        for _ in range(max_sweeps):
            self.rng.shuffle(order)
            changed = False
            for i in order:
                row = self.w[i]
                total = 0.0
                for j in range(self.n):
                    total += row[j] * state[j]
                new = 1 if total >= 0.0 else -1
                if new != state[i]:
                    state[i] = new
                    changed = True
            if not changed:
                return state, True
        return state, False

    def identify(self, state):
        """Which cell type this state is, or None if it is a spurious
        attractor.

        Spurious attractors are not a bug to be hidden. They are the failure
        mode with a real biological counterpart — a stable cell state that is
        not any intended tissue — and the tests measure their rate rather than
        assuming it away.
        """
        for index, pattern in enumerate(self.types):
            if state == pattern:
                return index
            if all(s == -p for s, p in zip(state, pattern)):
                # The inverse of an imprinted state is always an attractor in
                # this formulation. Counted as its own type, not as spurious.
                return index
        return None

    def perturb(self, state, n_flips):
        """Flip n_flips genes at random. Damage to expression, not to code."""
        state = list(state)
        sites = self.rng.sample(range(self.n), n_flips)
        for i in sites:
            state[i] = -state[i]
        return state

    def naive_state(self):
        """An undifferentiated cell: expression is unbiased noise."""
        return [1 if self.rng.random() < 0.5 else -1 for _ in range(self.n)]
