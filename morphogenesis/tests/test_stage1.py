"""Track B, Stage 1 — falsifiable tests for the morphogenetic runtime.

Each test corresponds to one property that separates morphogenesis from
configuration. A property that cannot fail here is not being claimed.

T1  locality        a cell cannot read global state (static, by AST)
T2  emergence       pattern arises from a uniform substrate + noise
T3  differentiation cell types are attractors, not assignments
T4  regeneration    unanticipated damage is repaired by unmodified local rules

T4 is the decisive one. Everything above it has been done many times; a
system that only recovers from damage its author anticipated is a supervision
tree wearing a biology costume.
"""

import ast
import os
import random

import pytest

from morphogenesis import grn
from morphogenesis.substrate import Substrate

CELL_SOURCE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cell.py")


# --------------------------------------------------------------------------
# T1 — locality, enforced statically
# --------------------------------------------------------------------------

def test_t1_cell_cannot_reach_global_state():
    """The cell module may not import the substrate or any Kernel module.

    Checked by parsing, not by convention. If a cell can obtain a reference to
    the lattice, it can read global state, and every emergence claim below
    collapses into 'a central planner with extra steps'.
    """
    with open(CELL_SOURCE) as handle:
        tree = ast.parse(handle.read())

    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.add(node.module.split(".")[0])
            if node.level:  # relative import
                for alias in node.names:
                    imported.add(alias.name.split(".")[0])

    forbidden = {"substrate", "policy", "authority", "capital", "provenance", "constitution"}
    assert not (imported & forbidden), f"cell.py reached for {imported & forbidden}"


def test_t1_cell_step_takes_no_position_argument():
    """A cell that knows where it is can compute a body plan from coordinates.

    Positional information in real morphogenesis is *derived* from local
    signalling, never handed to the cell. If `step` accepted x/y/index, the
    system could cheat by making pattern a function of address.
    """
    with open(CELL_SOURCE) as handle:
        tree = ast.parse(handle.read())

    step_fn = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "step"
    )
    names = {arg.arg for arg in step_fn.args.args}
    banned = {"x", "y", "idx", "index", "position", "pos", "coord", "coords", "grid", "lattice"}
    assert not (names & banned), f"step() accepts positional/global args: {names & banned}"


# --------------------------------------------------------------------------
# T2 — emergence from a uniform substrate
# --------------------------------------------------------------------------

@pytest.mark.slow
def test_t2_pattern_emerges_from_uniform_state():
    """Structure must appear where none was placed.

    Initial condition is homogeneous plus undirected noise. Noise has no
    characteristic length scale; a Turing pattern does. If interface density
    climbs from ~0 to a sustained non-trivial value, the substrate produced
    spatial organisation that nobody encoded.
    """
    sub = Substrate(48, 48, seed=7)
    sub.seed_uniform_with_noise()

    start_interface = sub.interface_density()
    sub.run(4000)
    end_interface = sub.interface_density()
    end_expressed = sub.expressed_fraction()

    # Pattern, not saturation: a field that simply flipped everywhere on would
    # have near-zero interface density too.
    assert end_interface > 0.10, f"no structure emerged (interface={end_interface:.3f})"
    assert 0.05 < end_expressed < 0.95, f"field saturated (expressed={end_expressed:.3f})"
    assert end_interface > start_interface


# --------------------------------------------------------------------------
# T3 — differentiation as attractor dynamics
# --------------------------------------------------------------------------

def test_t3_cell_types_are_attractors_not_assignments():
    """An imprinted type must be a fixed point of the regulatory dynamics."""
    net = grn.RegulatoryNetwork(n_genes=64, n_types=4, seed=11)
    for index, pattern in enumerate(net.types):
        settled, converged = net.relax(pattern)
        assert converged
        assert settled == pattern, f"type {index} is not a fixed point"


def test_t3_small_perturbation_returns_to_same_type():
    """Robustness: a differentiated cell resists small expression noise."""
    net = grn.RegulatoryNetwork(n_genes=64, n_types=4, seed=11)
    for index, pattern in enumerate(net.types):
        for _ in range(10):
            disturbed = net.perturb(pattern, n_flips=4)
            settled, converged = net.relax(disturbed)
            assert converged
            assert net.identify(settled) == index


def test_t3_naive_cells_differentiate_into_valid_types():
    """An undifferentiated cell must reach *some* viable type, and mostly a
    real one.

    Spurious attractors are reported rather than assumed away — they are the
    honest analogue of a stable cell state that is no intended tissue. The
    bound is what is being asserted, not their absence.
    """
    net = grn.RegulatoryNetwork(n_genes=64, n_types=4, seed=11)
    rng = random.Random(3)

    identified = 0
    trials = 200
    for _ in range(trials):
        net.rng = random.Random(rng.randrange(1 << 30))
        settled, converged = net.relax(net.naive_state())
        assert converged, "regulatory dynamics failed to reach a fixed point"
        if net.identify(settled) is not None:
            identified += 1

    rate = identified / trials
    assert rate > 0.60, f"spurious attractor rate too high (valid={rate:.2f})"


# --------------------------------------------------------------------------
# T4 — unscripted regeneration (the decisive test)
# --------------------------------------------------------------------------

def test_t4_no_repair_logic_exists_anywhere():
    """Structural precondition for the regeneration claim.

    If any module contains wound detection or a recovery branch, T4 proves
    nothing. Checked before the dynamics are allowed to make the claim.
    """
    package = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    banned = ("wound", "repair", "regenerate", "restore", "heal", "damaged")
    for name in ("cell.py", "substrate.py", "grn.py"):
        with open(os.path.join(package, name)) as handle:
            tree = ast.parse(handle.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                assert not any(b in node.name.lower() for b in banned), \
                    f"{name} defines recovery routine {node.name}()"


@pytest.mark.slow
def test_t4_unscripted_regeneration():
    """Excise a region the system was never designed to lose, and require the
    tissue to come back with the right texture.

    The wound's position and size are drawn at random at test time. No code
    path anywhere handles damage. If the region recovers, it recovers because
    identical local rules ran in every cell, including the ones at the wound
    margin — which is the definition this track has to meet.
    """
    sub = Substrate(48, 48, seed=7)
    sub.seed_uniform_with_noise()
    sub.run(4000)

    baseline_interface = sub.interface_density()
    baseline_expressed = sub.expressed_fraction()

    rng = random.Random(99)
    w = h = rng.randint(12, 18)
    x0, y0 = rng.randrange(48), rng.randrange(48)
    wound = (x0, y0, w, h)

    sub.excise(*wound)

    wounded_interface = sub.interface_density(wound)
    assert wounded_interface < 0.02, "excision did not actually clear the region"

    sub.run(4000)

    healed_interface = sub.interface_density(wound)
    healed_expressed = sub.expressed_fraction(wound)

    # Texture must return, not merely density: a wound that refilled uniformly
    # would score on expressed_fraction and fail here.
    assert healed_interface > 0.6 * baseline_interface, (
        f"texture did not return (healed={healed_interface:.3f}, "
        f"baseline={baseline_interface:.3f})"
    )
    assert abs(healed_expressed - baseline_expressed) < 0.25, (
        f"density did not return (healed={healed_expressed:.3f}, "
        f"baseline={baseline_expressed:.3f})"
    )
