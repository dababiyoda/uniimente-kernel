"""Track B, Stage 1 — falsifiable tests for the morphogenetic runtime.

SCOPE, STATED HONESTLY. Stage 1 is a toy morphogenesis experiment on a
regular lattice. It establishes local pattern formation and local pattern
reconstitution after perturbation. It does NOT establish regeneration in the
biological sense: no identity is restored, no function is restored, and no
remembered target morphology is involved. Those claims belong to Stages 2-4
and are not made here.

T1a/b/c  invariant     the three clauses of the developmental invariant
T1d      permissive    long-range signalling is allowed, and demonstrated
T2       emergence     pattern arises from a uniform substrate + noise
T3       fates         cell types are attractors, not assignments
T4       reconstitution local pattern returns after perturbation — measured as
                       a distribution against null baselines, not one run
"""

import os
import random
import statistics

import pytest

from morphogenesis import grn, invariant
from morphogenesis.substrate import Substrate

PACKAGE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CELL_SOURCE = os.path.join(PACKAGE, "cell.py")


# --------------------------------------------------------------------------
# T1 — the developmental invariant, three clauses
# --------------------------------------------------------------------------

def test_t1a_no_access_to_complete_target_structure():
    violations = invariant.clause1_no_target_structure(CELL_SOURCE)
    assert not violations, f"clause 1 violated: {violations}"


def test_t1b_no_centrally_assigned_fate():
    for name in ("cell.py", "substrate.py", "grn.py"):
        violations = invariant.clause2_no_assigned_fate(os.path.join(PACKAGE, name))
        assert not violations, f"clause 2 violated in {name}: {violations}"


def test_t1c_no_privileged_omniscient_state():
    violations = invariant.clause3_no_omniscient_state(CELL_SOURCE, "step")
    assert not violations, f"clause 3 violated: {violations}"


def test_t1d_long_range_signalling_is_permitted_and_works():
    """The corrected invariant must PERMIT what biology actually does.

    A tissue-scale gradient from a boundary source, sampled by each cell at
    its own location, is legitimate positional information — the Bicoid case.
    If the invariant checker rejected this, it would be the old over-strict
    rule under a new name, so this test asserts the permission explicitly and
    then confirms the gradient measurably changes development.
    """
    assert not invariant.check(CELL_SOURCE, "step"), \
        "invariant must hold WITH morphogen sampling present in cell.step"

    plain = Substrate(40, 40, seed=5)
    plain.seed_uniform_with_noise()
    plain.run(2500)

    graded = Substrate(40, 40, seed=5)
    graded.seed_uniform_with_noise()
    graded.establish_morphogen_gradient()
    graded.run(2500)

    # The gradient must do something. If long-range signalling were inert,
    # permitting it would be a hollow concession.
    left = graded.expressed_fraction((0, 0, 10, 40))
    right = graded.expressed_fraction((20, 0, 10, 40))
    assert abs(left - right) > 0.02, (
        f"gradient produced no positional difference (left={left:.3f}, right={right:.3f})"
    )
    assert graded.expressed_fraction() != plain.expressed_fraction()


# --------------------------------------------------------------------------
# T2 — emergence, with null baselines
# --------------------------------------------------------------------------

@pytest.mark.slow
def test_t2_pattern_emerges_from_uniform_state():
    sub = Substrate(48, 48, seed=7)
    sub.seed_uniform_with_noise()
    start = sub.interface_density()
    sub.run(4000)

    interface = sub.interface_density()
    expressed = sub.expressed_fraction()

    assert interface > 0.10, f"no structure emerged (interface={interface:.3f})"
    assert 0.05 < expressed < 0.95, f"field saturated (expressed={expressed:.3f})"
    assert interface > start


@pytest.mark.slow
def test_t2_null_no_diffusion_produces_no_structure():
    """Reaction without transport cannot pattern. If it appears to, the metric
    is measuring noise rather than structure."""
    sub = Substrate(48, 48, seed=7)
    sub.seed_uniform_with_noise()
    sub.disable_diffusion()
    sub.run(4000)
    assert sub.interface_density() < 0.05, \
        f"reaction-only substrate patterned (interface={sub.interface_density():.3f})"


# --------------------------------------------------------------------------
# T3 — differentiation as attractor dynamics
# --------------------------------------------------------------------------

def test_t3_cell_types_are_attractors_not_assignments():
    net = grn.RegulatoryNetwork(n_genes=64, n_types=4, seed=11)
    for index, pattern in enumerate(net.types):
        settled, converged = net.relax(pattern)
        assert converged and settled == pattern, f"type {index} is not a fixed point"


def test_t3_small_perturbation_returns_to_same_type():
    net = grn.RegulatoryNetwork(n_genes=64, n_types=4, seed=11)
    for index, pattern in enumerate(net.types):
        for _ in range(10):
            settled, converged = net.relax(net.perturb(pattern, n_flips=4))
            assert converged and net.identify(settled) == index


def test_t3_naive_cells_differentiate_into_valid_types():
    """Spurious attractors are measured and bounded, not assumed away."""
    net = grn.RegulatoryNetwork(n_genes=64, n_types=4, seed=11)
    rng = random.Random(3)
    identified = 0
    trials = 200
    for _ in range(trials):
        net.rng = random.Random(rng.randrange(1 << 30))
        settled, converged = net.relax(net.naive_state())
        assert converged
        if net.identify(settled) is not None:
            identified += 1
    assert identified / trials > 0.60, f"spurious rate too high (valid={identified/trials:.2f})"


# --------------------------------------------------------------------------
# T4 — LOCAL PATTERN RECONSTITUTION AFTER PERTURBATION
#
# Deliberately NOT called regeneration. Gray-Scott re-forms spatial texture
# under local rules; it does not restore identity, function, or a remembered
# target morphology. Naming it regeneration would claim Stage 4 results from
# a Stage 1 experiment.
# --------------------------------------------------------------------------

def test_t4_no_prewritten_repair_path_exists():
    """Structural precondition. Without this the reconstitution result is
    worthless, because recovery could be a coded response."""
    for name in ("cell.py", "substrate.py", "grn.py"):
        violations = invariant.clause2_no_assigned_fate(os.path.join(PACKAGE, name))
        assert not violations, f"{name}: {violations}"


def _reconstitution_trial(seed, wound_kind, feed_jitter=0.0, shuffled=False, no_diffusion=False):
    """One perturbation trial. Returns (texture_ratio, density_delta) or None
    if the substrate never patterned in the first place."""
    rng = random.Random(seed)

    sub = Substrate(40, 40, seed=seed)
    sub.seed_uniform_with_noise()
    if shuffled:
        sub.shuffle_topology()
    if no_diffusion:
        sub.disable_diffusion()

    if feed_jitter:
        import morphogenesis.cell as cellmod
        cellmod.FEED = 0.037 * (1.0 + feed_jitter)

    sub.run(3000)
    baseline_interface = sub.interface_density()
    baseline_expressed = sub.expressed_fraction()

    if baseline_interface < 0.05:
        return None  # never patterned; nothing to reconstitute

    if wound_kind == "square":
        w = h = rng.randint(10, 16)
    elif wound_kind == "strip":
        w, h = rng.randint(4, 7), rng.randint(24, 36)
    elif wound_kind == "wide":
        w, h = rng.randint(24, 36), rng.randint(4, 7)
    else:  # scatter — several small lesions
        w = h = rng.randint(4, 7)

    x0, y0 = rng.randrange(40), rng.randrange(40)
    wound = (x0, y0, w, h)
    sub.excise(*wound)
    if wound_kind == "scatter":
        for _ in range(4):
            sub.excise(rng.randrange(40), rng.randrange(40), w, h)

    sub.run(3000)

    healed_interface = sub.interface_density(wound)
    healed_expressed = sub.expressed_fraction(wound)
    return (
        healed_interface / baseline_interface if baseline_interface else 0.0,
        abs(healed_expressed - baseline_expressed),
    )


@pytest.mark.slow
def test_t4_reconstitution_distribution_across_seeds_and_wounds():
    """Many seeds, four wound geometries, parameter jitter — reported as a
    distribution. A single successful run is an anecdote."""
    import morphogenesis.cell as cellmod
    original_feed = cellmod.FEED
    try:
        ratios = []
        for seed in (3, 11, 19, 27, 35, 43):
            for kind in ("square", "strip", "wide", "scatter"):
                jitter = {"square": 0.0, "strip": 0.03, "wide": -0.03, "scatter": 0.0}[kind]
                result = _reconstitution_trial(seed, kind, feed_jitter=jitter)
                if result is not None:
                    ratios.append(result[0])
    finally:
        cellmod.FEED = original_feed

    assert len(ratios) >= 18, f"too few patterning trials to draw a distribution ({len(ratios)})"

    median = statistics.median(ratios)
    fraction_above_70 = sum(1 for r in ratios if r > 0.70) / len(ratios)

    assert median > 0.70, f"median texture recovery {median:.2f} (n={len(ratios)})"
    assert fraction_above_70 > 0.60, (
        f"only {fraction_above_70:.0%} of trials recovered >70% texture (n={len(ratios)})"
    )


@pytest.mark.slow
def test_t4_null_baselines_do_not_reconstitute():
    """The controls that make the result mean something.

    Shuffled neighbours preserve degree and destroy locality. No-diffusion
    preserves reaction and removes transport. If either reconstitutes as well
    as the intact substrate, Stage 1 is measuring an artefact.
    """
    import morphogenesis.cell as cellmod
    original_feed = cellmod.FEED
    try:
        shuffled = [_reconstitution_trial(s, "square", shuffled=True) for s in (3, 11, 19, 27)]
        nodiff = [_reconstitution_trial(s, "square", no_diffusion=True) for s in (3, 11, 19, 27)]
    finally:
        cellmod.FEED = original_feed

    # Both null models are expected to fail to pattern at all (None), or to
    # reconstitute far worse than the intact substrate.
    for label, results in (("shuffled", shuffled), ("no-diffusion", nodiff)):
        scored = [r[0] for r in results if r is not None]
        assert not scored or statistics.median(scored) < 0.70, (
            f"{label} null baseline reconstituted (median={statistics.median(scored):.2f}) "
            f"— intact-substrate result is not attributable to local spatial dynamics"
        )
