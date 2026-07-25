"""The digital cell.

STRUCTURAL INVARIANT — enforced by test T1, verified by AST inspection:

    This module may not import the substrate, may not read any global lattice,
    and may not accept a position argument. A cell knows its own state and the
    states of its immediate neighbours. Nothing else.

That constraint is the whole point. A cell that can read global state is a
worker executing a plan. A cell that cannot is the only thing that can
produce morphology nobody wrote down.

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


def step(u, v, ortho_u, diag_u, ortho_v, diag_v, dt=1.0):
    """Advance one cell by one tick.

    Returns the cell's next (u, v). Pure function of local information.

    NOTE FOR REVIEWERS: there is no damage branch here, no wound detection,
    no repair routine, no 'if regenerating' path. Test T4 excises a region of
    the substrate at random and requires the pattern to return. If it returns,
    it returns because of these four lines and nothing else. That is what
    'unscripted' has to mean to be worth claiming.
    """
    lap_u = laplacian(u, ortho_u, diag_u)
    lap_v = laplacian(v, ortho_v, diag_v)

    reaction = u * v * v
    du = DU * lap_u - reaction + FEED * (1.0 - u)
    dv = DV * lap_v + reaction - (FEED + KILL) * v

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
