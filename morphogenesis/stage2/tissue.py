"""Institutional tissue: cells that differentiate into roles to keep work
flowing, using local signals only.

DEFINITIONS — these are the Stage 2 commitments, stated so they can be
disputed rather than assumed.

WHAT AN INSTITUTIONAL CELL REPRESENTS
    A service instance holding exactly one role and processing work items.
    Chosen over "a venture" or "a commitment" because it is the smallest unit
    that can (a) exist in multiples, (b) change what it does, (c) be
    destroyed and replaced, and (d) have a function that is measurable
    without interpretation.

WHAT THE TISSUE'S FUNCTION IS
    Work items must traverse a required role sequence end to end:
    INTAKE -> VERIFY -> SETTLE. Function is completed items per tick. This is
    the shape of essentially every institutional pipeline — a claim is taken
    in, checked, and settled — and it fails in a way you can count.

WHAT DAMAGE MEANS
    Removal of a set of cells (a team leaves, a vendor fails, a region goes
    dark) and/or the edges between them. Injuries are drawn at evaluation
    time from a held-out generator, never from the set used to choose
    parameters.

WHAT SUCCESSFUL FUNCTIONAL RECOVERY MEANS
    Throughput returns to >= 90% of the pre-injury baseline within a bounded
    number of ticks and a bounded number of role switches, achieved only by
    cells changing their own role from local signals. No central planner. No
    prewritten repair path.

THE LOCAL RULE
    Delta-Notch-style lateral inhibition plus local demand sensing. A cell
    sees: work waiting in its own queue and its neighbours' queues, and the
    roles its neighbours currently express. It computes unmet local demand
    per role, discounted by how many neighbours already serve that role, and
    switches if another role beats its current one by a hysteresis margin.

    No cell can observe throughput, the global role census, the graph, or the
    injury. Enforced by the invariant checker, same as Stage 1.
"""

import random

INTAKE, VERIFY, SETTLE = 0, 1, 2
ROLES = (INTAKE, VERIFY, SETTLE)
ROLE_NAMES = {INTAKE: "INTAKE", VERIFY: "VERIFY", SETTLE: "SETTLE"}

# A cell must see a clear local advantage before switching. Without
# hysteresis the tissue oscillates: cells chase demand, overshoot, and
# thrash. This is the same reason TCP needs damping.
SWITCH_MARGIN = 2.0
INHIBITION = 1.0

# Cells integrate demand over time rather than reacting to the instantaneous
# queue. This is biologically motivated -- real cells integrate morphogen
# exposure, they do not chase instantaneous concentration -- and it is the
# fix for a measured pathology: with instantaneous sensing the tissue
# thrashed at ~0.3 switches per cell per tick and the role census collapsed
# (INTAKE fell to 1 of 196 under load). See docs/DEVELOPMENTAL_TRACK.md.
DEMAND_ALPHA = 0.08


def local_role_decision(own_role, own_queue, neighbour_queues, neighbour_roles):
    """Decide this cell's role from local information only.

    own_queue        counts of items at this cell awaiting each role
    neighbour_queues summed counts at adjacent cells awaiting each role
    neighbour_roles  counts of adjacent cells expressing each role

    Returns the role this cell should express. Pure function; no access to
    the graph, the tissue, throughput, or whether an injury occurred.
    """
    scores = []
    for role in ROLES:
        demand = own_queue[role] + 0.5 * neighbour_queues[role]  # integrated upstream
        # Lateral inhibition: a neighbour already serving this role reduces
        # the value of duplicating it. This is what prevents every cell
        # collapsing onto the same role, with no coordinator.
        supply = INHIBITION * neighbour_roles[role]
        scores.append(demand / (1.0 + supply))

    best = max(range(len(ROLES)), key=lambda r: scores[r])
    if best == own_role:
        return own_role
    if scores[best] > SWITCH_MARGIN * scores[own_role]:
        return best
    return own_role


class Tissue:
    # A cell serves at most this many items per tick. Without a capacity
    # bound, role allocation never binds: one INTAKE cell could serve the
    # whole tissue and differentiation would be decorative.
    CAPACITY = 2

    # Hop budget. An item that cannot find its required role within TTL hops
    # is lost. This is the correction that makes locality matter at all —
    # with unbounded hops, a connected graph is effectively fully connected
    # given enough time, so any random role assignment eventually works and
    # the measurement is vacuous. Measured negative result on the first
    # version of this file; see docs/DEVELOPMENTAL_TRACK.md.
    TTL = 10

    def __init__(self, adjacency, seed=None, differentiation=True):
        self.adj = [list(a) for a in adjacency]
        self.n = len(self.adj)
        self.rng = random.Random(seed)
        self.differentiation = differentiation

        self.alive = [True] * self.n
        self.role = [self.rng.choice(ROLES) for _ in range(self.n)]
        # queue[cell][stage] = list of remaining hop budgets, one per item
        self.queue = [[[], [], []] for _ in range(self.n)]
        # Per-cell integrated demand signal. Local state, local update.
        self.demand = [[0.0, 0.0, 0.0] for _ in range(self.n)]

        self.completed = 0
        self.lost = 0
        self.switches = 0
        self._injected = 0

    # -- dynamics -----------------------------------------------------------

    def _live_cells(self):
        return [i for i in range(self.n) if self.alive[i]]

    def _inject(self, rate):
        live = self._live_cells()
        if not live:
            return
        for _ in range(rate):
            self.queue[self.rng.choice(live)][INTAKE].append(self.TTL)
            self._injected += 1

    def _advance_work(self):
        """Items are served where their required role is expressed, otherwise
        they walk to a neighbour and spend a hop. Movement is local; nothing
        routes them, and nothing knows where the roles are."""
        moves = []
        for cell in range(self.n):
            if not self.alive[cell]:
                continue
            served = 0
            for stage in ROLES:
                items = self.queue[cell][stage]
                if not items:
                    continue
                keep = []
                for ttl in items:
                    if self.role[cell] == stage and served < self.CAPACITY:
                        served += 1
                        if stage == SETTLE:
                            self.completed += 1
                        else:
                            moves.append((cell, stage + 1, self.TTL))
                        continue
                    # Not served this tick: walk, spending a hop.
                    neighbours = [n for n in self.adj[cell] if self.alive[n]]
                    if ttl <= 1 or not neighbours:
                        self.lost += 1
                        continue
                    moves.append((self.rng.choice(neighbours), stage, ttl - 1))
                self.queue[cell][stage] = keep
        for cell, stage, ttl in moves:
            self.queue[cell][stage].append(ttl)

    def _queue_counts(self, cell):
        q = self.queue[cell]
        return [len(q[0]), len(q[1]), len(q[2])]

    def _differentiate(self):
        if not self.differentiation:
            return
        new_roles = list(self.role)
        for cell in range(self.n):
            if not self.alive[cell]:
                continue
            neighbours = [n for n in self.adj[cell] if self.alive[n]]
            own = self._queue_counts(cell)
            nq = [0, 0, 0]
            nr = [0, 0, 0]
            for nb in neighbours:
                counts = self._queue_counts(nb)
                for stage in ROLES:
                    nq[stage] += counts[stage]
                nr[self.role[nb]] += 1

            # Integrate, then decide on the integrated signal.
            d = self.demand[cell]
            for stage in ROLES:
                observed = own[stage] + 0.5 * nq[stage]
                d[stage] += DEMAND_ALPHA * (observed - d[stage])

            decided = local_role_decision(self.role[cell], d, [0.0, 0.0, 0.0], nr)
            if decided != self.role[cell]:
                new_roles[cell] = decided
                self.switches += 1
        self.role = new_roles

    def tick(self, rate=6):
        self._inject(rate)
        self._advance_work()
        self._differentiate()

    def run(self, ticks, rate=6):
        for _ in range(ticks):
            self.tick(rate)

    # -- measurement --------------------------------------------------------

    def measure_throughput(self, ticks=120, rate=6):
        """Completed items per tick over a measurement window."""
        before = self.completed
        self.run(ticks, rate)
        return (self.completed - before) / ticks

    # -- injury -------------------------------------------------------------

    def injure(self, cells):
        """Remove cells. No record is kept that an injury occurred, and no
        cell can query this."""
        for c in cells:
            self.alive[c] = False
            self.queue[c] = [[], [], []]

    def hub_targets(self, k):
        """The k highest-degree living cells.

        Targeted removal, not random. This is the realistic institutional
        failure -- the largest partner fails, the busiest team leaves -- and
        it is the case scale-free graphs are known to be fragile to. Random
        removal on a hub-heavy graph mostly deletes leaves and proves little.
        """
        live = [(len([n for n in self.adj[i] if self.alive[n]]), i)
                for i in range(self.n) if self.alive[i]]
        live.sort(reverse=True)
        return [i for _, i in live[:k]]

    def role_census(self):
        counts = {INTAKE: 0, VERIFY: 0, SETTLE: 0}
        for cell in range(self.n):
            if self.alive[cell]:
                counts[self.role[cell]] += 1
        return counts
