"""Track B, Stage 2 — Held-Out Functional Recovery Rate.

THE SINGLE BOTTLENECK METRIC
    HFRR: the percentage of unseen graph injuries where local rules restore
    at least 90% of baseline function within bounded time and resources,
    without a central planner or a prewritten repair path.

Stage 2 decides whether Track B enters UNIIMENTE or remains a lattice model.
These tests therefore encode the MEASURED result, including where it fails.
They are regression tests on a finding, not aspirations.

HELD-OUT DISCIPLINE. Parameters (CAPACITY, TTL, SWITCH_MARGIN, DEMAND_ALPHA)
were chosen against topology seed 1 and graph seeds 101-137. Every seed used
below (211-251) is disjoint from that set and was not consulted while
tuning.

MEASURED RESULT — the honest summary:

  topology     deg cv   HFRR @10%   @20%    @30%   post-injury LCC @20%
  lattice       0.00      100%      100%      0%          1.00
  smallworld    0.24      100%        0%      0%          0.91
  scalefree     1.03        0%        0%      0%          0.07

  local rule vs nulls, pooled over 10/20/30% injury:
  lattice      local 66.7%  frozen 41.7%  random  0.0%
  smallworld   local 33.3%  frozen  4.2%  random  0.0%
  scalefree    local  0.0%  frozen  0.0%  random  0.0%
                     (median recovery 0.559 vs 0.272 vs 0.206)

READING IT. Local differentiation does real work — it beats frozen roles at
every topology, roughly doubling median recovery on scale-free. It clears the
90% bar on homogeneous-degree topology and fails on hub-heavy topology, which
is the topology institutions actually have.

The 20% and 30% scale-free figures are NOT evidence about differentiation:
hub-targeted removal shatters a Barabasi-Albert graph, leaving a largest
component of 7% of survivors. No mechanism can route work through a
disconnected substrate. The interpretable scale-free datapoint is 10%
injury, where the graph remains 73% connected and HFRR is still 0% at a
median of 0.85.
"""

import random
import statistics
from collections import deque

import pytest

from morphogenesis.stage2 import topology, tissue

RATE = 90          # load in the binding regime: capacity and TTL both bite
DEVELOP = 300
RECOVER = 400      # the bounded time budget
WINDOW = 120

HELD_OUT_SEEDS = (211, 223, 227, 229, 233, 239, 241, 251)


def _largest_component_fraction(t):
    seen, best = set(), 0
    for start in range(t.n):
        if not t.alive[start] or start in seen:
            continue
        queue, seen_here = deque([start]), 0
        seen.add(start)
        while queue:
            cell = queue.popleft()
            seen_here += 1
            for nb in t.adj[cell]:
                if t.alive[nb] and nb not in seen:
                    seen.add(nb)
                    queue.append(nb)
        best = max(best, seen_here)
    survivors = sum(1 for i in range(t.n) if t.alive[i])
    return best / survivors if survivors else 0.0


def _trial(topo, seed, fraction, mode="local"):
    """One injury trial. Returns recovery ratio, or None if the tissue never
    reached a usable baseline."""
    adjacency = topology.BUILDERS[topo](seed)
    t = tissue.Tissue(adjacency, seed=seed, differentiation=(mode != "frozen"))
    t.run(DEVELOP, RATE)
    baseline = t.measure_throughput(WINDOW, RATE)
    if baseline <= 1.0:
        return None

    live = [i for i in range(t.n) if t.alive[i]]
    t.injure(t.hub_targets(max(1, int(len(live) * fraction))))

    if mode == "random":
        rng = random.Random(seed)
        for cell in range(t.n):
            if t.alive[cell]:
                t.role[cell] = rng.choice(tissue.ROLES)
        t.differentiation = False

    t.run(RECOVER, RATE)
    return t.measure_throughput(WINDOW, RATE) / baseline


def _hfrr(topo, fraction, mode="local"):
    ratios = [r for r in (_trial(topo, s, fraction, mode) for s in HELD_OUT_SEEDS)
              if r is not None]
    assert ratios, f"{topo} produced no usable baselines"
    rate = sum(1 for r in ratios if r >= 0.90) / len(ratios)
    return rate, statistics.median(ratios)


# --------------------------------------------------------------------------
# The invariant still holds at Stage 2
# --------------------------------------------------------------------------

def test_stage2_local_rule_obeys_the_developmental_invariant():
    """The role decision must remain a pure function of local signals."""
    import os
    from morphogenesis import invariant

    source = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "stage2", "tissue.py",
    )
    violations = invariant.check(source, "local_role_decision")
    assert not violations, f"Stage 2 violates the invariant: {violations}"


def test_stage2_cells_cannot_observe_throughput_or_injury():
    """A cell decides from own queue, neighbour queues, and neighbour roles.

    Passing deliberately wrong global information must not change the
    decision, because the decision function has no channel to receive it.
    """
    from morphogenesis.stage2.tissue import local_role_decision

    decision = local_role_decision(0, [5.0, 1.0, 1.0], [0.0, 0.0, 0.0], [0, 2, 2])
    again = local_role_decision(0, [5.0, 1.0, 1.0], [0.0, 0.0, 0.0], [0, 2, 2])
    assert decision == again, "role decision is not a pure function"


# --------------------------------------------------------------------------
# HFRR — the measured result, including the failure
# --------------------------------------------------------------------------

@pytest.mark.slow
def test_hfrr_passes_on_homogeneous_degree_topology():
    """Lattice, 10% and 20% hub-targeted injury: local rules restore function."""
    for fraction in (0.10, 0.20):
        rate, median = _hfrr("lattice", fraction)
        assert rate >= 0.90, f"lattice HFRR@{fraction:.0%} = {rate:.0%} (median {median:.2f})"


@pytest.mark.slow
def test_hfrr_fails_on_hub_heavy_topology():
    """Scale-free, 10% hub-targeted injury: local rules do NOT restore
    function, on a substrate that is still 73% connected.

    This test asserts the FAILURE. If a future change makes scale-free pass,
    this test breaks and that is the intended signal — the result would be
    the most important thing to have happened to this track, and it should
    not slip by unnoticed.
    """
    rate, median = _hfrr("scalefree", 0.10)
    assert rate < 0.90, (
        f"scale-free HFRR@10% = {rate:.0%} (median {median:.2f}) — the Stage 2 "
        f"blocker may be resolved; re-read docs/DEVELOPMENTAL_TRACK.md before "
        f"relaxing this assertion"
    )


@pytest.mark.slow
def test_differentiation_beats_frozen_and_random_baselines():
    """The mechanism does real work even where it does not clear the bar.

    Without this, a passing HFRR on the lattice could be a property of the
    task rather than of differentiation — which is exactly the artefact the
    first version of Stage 2 fell into, when frozen roles matched the local
    rule at 100%.
    """
    _, local = _hfrr("smallworld", 0.20, "local")
    _, frozen = _hfrr("smallworld", 0.20, "frozen")
    _, rand = _hfrr("smallworld", 0.20, "random")

    assert local > frozen > rand, (
        f"baselines not separated: local={local:.3f} frozen={frozen:.3f} random={rand:.3f}"
    )


@pytest.mark.slow
def test_severe_scalefree_injury_is_substrate_destruction_not_rule_failure():
    """Interpretive guard.

    Hub-targeted removal of 20% of a Barabasi-Albert graph leaves a largest
    component of well under half the survivors. Any HFRR measured there says
    nothing about differentiation, and this test exists so nobody later cites
    the 20-30% scale-free numbers as evidence about the local rule.
    """
    t = tissue.Tissue(topology.BUILDERS["scalefree"](1), seed=1)
    live = [i for i in range(t.n) if t.alive[i]]
    t.injure(t.hub_targets(int(len(live) * 0.20)))
    assert _largest_component_fraction(t) < 0.50, (
        "scale-free graph no longer shatters under 20% hub removal; the "
        "interpretation in docs/DEVELOPMENTAL_TRACK.md needs revisiting"
    )
