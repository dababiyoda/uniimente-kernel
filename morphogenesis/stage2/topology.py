"""Candidate adjacency graphs for institutional tissue.

Stage 2 exists because reaction-diffusion needs a neighbourhood metric and
institutions do not obviously have one. Three candidates, each a different
theory of what adjacency means between institutional cells:

  lattice     regular degree. The Stage 1 topology, carried forward as a
              control so that a Stage 2 failure can be attributed to
              topology rather than to the change of task.

  smallworld  mostly-local ties with a few long-range ones (Watts-Strogatz).
              The work-handoff graph of an organisation: teams hand off to
              adjacent teams, with occasional cross-org shortcuts.

  scalefree   preferential attachment (Barabási-Albert). Hub-heavy, which is
              what real counterparty and capital-flow graphs actually look
              like. This is the case most likely to break local patterning,
              because Turing-type instability is sensitive to degree
              heterogeneity — so it is the case that decides the stage.

If differentiation works on lattice and small-world but fails on scale-free,
that is a real and reportable result, not a bug to tune away.
"""

import random


def lattice(n_side, seed=None):
    """Regular 4-neighbour torus. n = n_side^2."""
    n = n_side * n_side
    adj = [[] for _ in range(n)]
    for idx in range(n):
        x, y = idx % n_side, idx // n_side
        for nb in (
            ((x - 1) % n_side) + y * n_side,
            ((x + 1) % n_side) + y * n_side,
            x + ((y - 1) % n_side) * n_side,
            x + ((y + 1) % n_side) * n_side,
        ):
            if nb not in adj[idx]:
                adj[idx].append(nb)
    return adj


def smallworld(n, k=4, rewire=0.1, seed=None):
    """Watts-Strogatz ring lattice with rewiring."""
    rng = random.Random(seed)
    adj = [set() for _ in range(n)]
    half = max(1, k // 2)
    for i in range(n):
        for d in range(1, half + 1):
            j = (i + d) % n
            adj[i].add(j)
            adj[j].add(i)
    for i in range(n):
        for j in list(adj[i]):
            if rng.random() < rewire:
                new = rng.randrange(n)
                if new != i and new not in adj[i]:
                    adj[i].discard(j)
                    adj[j].discard(i)
                    adj[i].add(new)
                    adj[new].add(i)
    return [sorted(s) for s in adj]


def scalefree(n, m=2, seed=None):
    """Barabási-Albert preferential attachment. Hub-heavy by construction."""
    rng = random.Random(seed)
    adj = [set() for _ in range(n)]
    targets = list(range(m + 1))
    for i in range(m + 1):
        for j in range(m + 1):
            if i != j:
                adj[i].add(j)

    repeated = []
    for i in range(m + 1):
        repeated.extend([i] * m)

    for new in range(m + 1, n):
        chosen = set()
        while len(chosen) < m:
            chosen.add(repeated[rng.randrange(len(repeated))])
        for t in chosen:
            adj[new].add(t)
            adj[t].add(new)
        repeated.extend(chosen)
        repeated.extend([new] * m)

    return [sorted(s) for s in adj]


def degree_stats(adj):
    degrees = [len(a) for a in adj]
    mean = sum(degrees) / len(degrees)
    variance = sum((d - mean) ** 2 for d in degrees) / len(degrees)
    return {
        "mean": mean,
        "max": max(degrees),
        "min": min(degrees),
        # Heterogeneity index. Near 0 for a lattice, large for scale-free.
        # This is the quantity that predicts whether local patterning holds.
        "cv": (variance ** 0.5) / mean if mean else 0.0,
    }


BUILDERS = {
    "lattice": lambda seed: lattice(14, seed=seed),
    "smallworld": lambda seed: smallworld(196, k=4, rewire=0.12, seed=seed),
    "scalefree": lambda seed: scalefree(196, m=2, seed=seed),
}
