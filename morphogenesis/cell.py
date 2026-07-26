"""The digital cell.

DEVELOPMENTAL INVARIANT — see invariant.py, enforced by tests T1a/T1b/T1c:

    No cell may access the complete target structure, receive a centrally
    assigned final fate, or use privileged omniscient state.

What that permits, and biology requires: local morphogen fields sampled at
the cell's own location, tissue-scale gradients from boundary sources,
accumulated signals, boundary cues, and long-range signalling. The Bicoid
gradient spans an entire Drosophila embryo and is not a violation — range is
not the issue. Omniscience and assignment are.

What it prohibits: reading a stored morphology, having a fate written from
outside, and unbounded input arity. A cell samples its surroundings; it is
never handed the tissue.

Absolute coordinates are treated as a violation by proxy: in a lattice of
known size, fate = f(x, y) is a blueprint lookup wearing different clothes.

Every cell in the substrate runs THIS code. There are no cell classes, no
subtypes, no role parameters. Differentiation is a dynamical outcome (see
grn.py), never a construction-time choice.
"""

# Gray-Scott reaction-diffusion coefficients.
#
# These are not a body plan. They are chemistry. The pattern that arises from
# them is not encoded anywhere in this file, which is the distinction between
# morphogenesis and configuration.
DU = 0.16          # diffusion rate, substrate morphogen
DV = 0.08          # diffusion rate, activator morphogen
FEED = 0.037       # replenishment of U
KILL = 0.063       # removal of V

# Laplacian stencil weights: orthogonal neighbours, then diagonal.
_W_ORTHO = 0.20
_W_DIAG = 0.05
_W_SELF = -1.0


def laplacian(own, ortho, diag):
    """Discrete Laplacian from local values only.

    `ortho` and `diag` are the neighbour values handed to the cell. The cell
    never fetches them; it is given them. It cannot reach past its neighbours
    because it has no reference through which to reach.
    """
    total = _W_SELF * own
    for value in ortho:
        total += _W_ORTHO * value
    for value in diag:
        total += _W_DIAG * value
    return total


def step(u, v, ortho_u, diag_u, ortho_v, diag_v, dt=1.0, morphogen=None):
    """Advance one cell by one tick.

    Returns the cell's next (u, v). Pure function of local information plus,
    optionally, a long-range morphogen concentration sampled AT THIS CELL'S
    OWN LOCATION.

    `morphogen` is the legitimate case the corrected invariant exists to
    permit. It is a tissue-scale field produced by diffusion from a boundary
    source. The cell reads one scalar — its own local concentration — and has
    no way to learn the field's shape, extent, or where it sits within it.
    That is positional information in Wolpert's sense, not omniscience.

    NOTE FOR REVIEWERS: there is no damage branch here, no wound detection,
    no repair routine, no 'if perturbed' path. The perturbation tests excise
    regions at random; if pattern returns, it returns from these lines alone.
    """
    lap_u = laplacian(u, ortho_u, diag_u)
    lap_v = laplacian(v, ortho_v, diag_v)

    feed = FEED if morphogen is None else FEED * (0.75 + 0.5 * morphogen)

    reaction = u * v * v
    du = DU * lap_u - reaction + feed * (1.0 - u)
    dv = DV * lap_v + reaction - (feed + KILL) * v

    next_u = u + dt * du
    next_v = v + dt * dv

    # Clamp to the physically meaningful range. Concentrations are not signed.
    if next_u < 0.0:
        next_u = 0.0
    elif next_u > 1.0:
        next_u = 1.0
    if next_v < 0.0:
        next_v = 0.0
    elif next_v > 1.0:
        next_v = 1.0

    return next_u, next_v


def is_expressed(v, threshold=0.20):
    """Whether this cell currently expresses the activator-driven phenotype.

    A local read of a local value. No cell is told what the tissue looks like.
    """
    return v > threshold
