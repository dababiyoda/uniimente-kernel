"""Global workspace (Layer 5): salience-gated selective broadcast among specialists on a narrow shared bus.

The 2026-10-21 coverage record (``docs/collaboration/MIND-COVERAGE-2026-10-21.md``, section 31 item 1) lists
"global workspace" as a directive-named family with no executor, and ``greg/cognition/reserved.py`` reserves
``cortex.meta.global_workspace`` ("no module competition or selective broadcast exists"). Effect, not metaphor
(INTENT-0030): Baars' and Dehaene's global workspace is compiled to an engineering effect with no claim about
consciousness. Several specialist modules each hold part of the evidence; each proposes partial results with a
salience; a capacity-limited workspace admits the most salient few per round and broadcasts them to every specialist;
the specialists update and propose again. The claim under test is efficiency under limited communication bandwidth,
so every arm is charged for every bit it puts on the shared channel, under one declared budget. Scope: the reserved
record's own falsifier ("beat simple orchestration on a frozen mixed suite" of GREG's methods) is NOT tested here;
this genome executes competition and selective broadcast among block specialists of one problem, and no workspace
arbitrates among GREG's intelligences.

* ``meta_global_workspace`` (``global_workspace_broadcast``, Layer 5). Native geometry (synthetic): distributed MAP
  inference in a pairwise binary factor graph (an Ising spin glass with fields),

      E(x) = sum_v h_v s_v + sum_(u,w) J_uw s_u s_w,     s_v = 2 x_v - 1,  x in {0,1}^n,

  whose variables are partitioned among K specialists. A specialist owns a block of at most 10 variables and only
  its own factors: the fields and couplings inside its block and the couplings crossing out of it (both ends of a
  crossing coupling know it). The request carries the whole graph so a run is recomputable, but each specialist's
  computation reads only its own factors; nothing in the communication model lets factors themselves be shipped.
  The specialists share one broadcast bus of ``bits_per_round`` bits for at most ``rounds`` synchronous rounds.

  Mechanism (the candidate). Each round, from the workspace contents W at the round's start (the last broadcast
  value of each broadcast variable), every specialist computes its block's exact MAP with the crossing couplings to
  broadcast variables clamped and those to unbroadcast variables ignored. It proposes each owned boundary variable
  whose MAP value differs from W (or is absent from W) and whose decision is not indifferent, with salience

      salience_v = gap_v * reach_v,   gap_v = min E_block(x_v flipped) - min E_block,  reach_v = sum |J_vw| (crossing)

  (confidence in the decision times the coupling mass it moves in other specialists). Access is priority
  arbitration on the bus, as on a CAN bus: each frame carries an 8-bit priority ``floor(64 log2(1 + salience))``
  (capped at 255), the highest priority wins the slot (ties to the lower variable id) and losing frames cost no bus
  time, so a frame costs its own bits only: 8 priority + ceil(log2 n) id + 1 value bits. The workspace admits
  ``floor(bits_per_round / frame_bits)`` frames per round and broadcasts them to all. The run stops at quiescence (no
  proposals) or when the rounds are spent. Readout (free and identical for every arm): each specialist reports its
  block's MAP given the final W.

  Verifier (``ws_verify``, independent: ``itertools`` enumeration over dict-based energies, never the solver's
  tables): recounts every frame's bits against the declared formats, the per-round budget and the round limit;
  replays the workspace round by round and checks every admitted frame is a proposal of its owner at the round's
  snapshot (block-optimal value, different from W, priority equal to the recomputed level), that the admitted set is
  the top-capacity set under arbitration, that the run stopped exactly when it was quiescent or out of rounds, that
  every block of the final assignment attains its block minimum given the final W, and that the claimed energy is
  the energy of the assignment.

  Truth: the exact global minimum energy by enumeration of all 2^n assignments (numpy, n <= 20), an evaluation-side
  method independent of every arm. Score: minus the energy gap to that minimum. An arm whose trace exceeds the bus
  budget or the round limit is scored ``wrong`` (its bandwidth claim is false), whatever its assignment.

  Baseline: independent specialists without communication (each block's MAP with every crossing coupling ignored),
  merged by concatenation. Zero bits.

  Competitor, the strongest bandwidth-matched alternative. Before any arm ran, the rule declared here was: three
  non-workspace schemes are implemented on the same bus, charged by the same frame accounting, and the competitor is
  the one with the highest mean development-seed quality (seeds 0-9). The three:

  1. ``bp_priority`` - belief-broadcast block min-sum belief propagation with residual scheduling (Elidan, McGraw
     and Koller 2006) by the same priority arbitration: each specialist computes the min-marginal difference D_v of
     each boundary variable with every message received so far as unary terms, and proposes it when its 8-bit
     quantisation (clip to +-4 * coupling_bound) moved; priority is the residual in levels. A broadcast belief lets
     every crossing neighbour compute its exact min-sum message, because a unary term on v shifts v's min-marginal
     pointwise: m_{v->w}(x_w) = min_{x_v} [J s_v s_w + D_v x_v - m_{w->v}(x_v)] (both ends keep the edge's two
     messages from the public broadcasts). Frame: 8 priority + id + 8 value bits. This is soft information (BP) with
     the workspace's own broadcast reach and access discipline.
  2. ``bp_round_robin`` - the same belief propagation without priority bits: the bus passes round-robin among the
     specialists (starting at round mod K); each sends its largest residuals while bits remain, a specialist with
     nothing to send passes the turn for 1 bit. Frame: id + 8 bits.
  3. ``blackboard_round_robin`` - unprioritised sharing of hard decisions (the workspace minus its competition):
     the same proposals as the candidate, from the round's snapshot, sent in variable-id order on the round-robin
     bus with no priority field. Frame: id + 1 bits, so it moves about twice as many decisions per bit.

  Disclosure (a post-development change): on seeds 0-9 the rule chose ``bp_priority`` (mean quality -2.251; the
  candidate -0.167). Looking at that result showed that the declared set left out the obvious sequential form of
  scheme 3, so a fourth scheme was added after the development run and, being the strongest, made the competitor:

  4. ``token_ring`` (``ws_token_ring``, THE COMPETITOR) - the same unprioritised decisions on a token ring, but
     sequential: the token holder recomputes its block MAP from the latest board, including frames sent earlier in
     the same round (distributed block coordinate descent, Gauss-Seidel). Frame: id + 1 bits, pass 1 bit.

  A second development finding, recorded without changing the candidate: on a 4000-bit, 50-round bus the
  synchronous workspace admits every proposal at once and oscillates on 8 of the 10 development instances (it ends
  no better than no communication), while the token ring settles in one or two rounds. The workspace works here
  only because the capacity limit serialises the updates.

  Development means (seeds 0-9, quality = minus the energy gap): candidate -0.167, token_ring -0.089, bp_priority
  -2.251, bp_round_robin -2.349, blackboard_round_robin -3.591, baseline -5.986. The token ring beats the candidate
  3-1 with 6 ties on development seeds. The change strengthens the competitor against the candidate; nothing in the
  candidate, generator, score, salience, priority, budget or baseline was changed after any development result.
  The candidate itself is synchronous (every specialist proposes from the round's snapshot); a sequential workspace
  (re-arbitration after every admitted frame) is the natural next candidate, and it is NOT built here, because a
  candidate change after seeing it lose is not allowed in this run.

  Full unlimited sharing (every specialist broadcasting every change every round) is not a separate arm: under the
  shared budget it is scheme 3 or 4 truncated to the bus, so it is charged the same bandwidth. A central exact
  solver is not a competitor: it needs every factor in one place, which the communication model forbids; it
  supplies the truth instead.

  Sanity check of the BP competitors (development only, recorded for honesty): on 200 random trees with one
  variable per specialist and an ample bus, both BP arms are exact with unquantised beliefs, and miss the minimum on
  8 of 200 trees at 8-bit beliefs, where near-degenerate min-marginals (weak fields, near spin-flip symmetry) round
  to the wrong sign. 12- and 16-bit beliefs did not improve their development means (fewer frames fit the bus).

Everything is read-only computation; no output of any method here creates authority. Development seeds 0-9 only.
"""
from __future__ import annotations

import itertools
import math
import random

from .contract import Executable, GenomeError, IntelligenceGenome, answer

LINEAGE = ("INTENT-20261007-POLYINTELLIGENCE-MIND-CONTINUATION", "INTENT-20261007-VERIFIED-POLYINTELLIGENCE-LIFT",
           "INTENT-20261021-MIND-MAXIMUM-CONTINUATION",
           "MIND-COVERAGE-2026-10-21 section 31 item 1: global workspace has no executor",
           "reserved cortex.meta.global_workspace: module competition and selective broadcast")

WS_MAX_N, WS_MAX_BLOCK, WS_MAX_BLOCKS, WS_MAX_EDGES = 60, 10, 12, 2000
WS_MAX_BITS, WS_MAX_ROUNDS = 4096, 50
WS_TRUTH_MAX_N = 20                  # evaluation-side enumeration limit (instances never exceed it)
PRIORITY_BITS, BELIEF_BITS = 8, 8
GAP_EPS = 1e-9                       # a decision whose flip costs no more than this is indifferent: never proposed
BELIEF_LEVELS = 127                  # signed 8-bit belief quantisation: level in [-127, 127]


def _num(v):
    return type(v) in (int, float) and math.isfinite(v)


def id_bits(n: int) -> int:
    return max(1, math.ceil(math.log2(n)))


def frame_bits(kind: str, n: int) -> int:
    """The declared bus frame formats (a protocol table shared by every arm, the score and the verifier)."""
    table = {"decision_priority": PRIORITY_BITS + id_bits(n) + 1, "decision": id_bits(n) + 1,
             "belief_priority": PRIORITY_BITS + id_bits(n) + BELIEF_BITS, "belief": id_bits(n) + BELIEF_BITS,
             "pass": 1}
    if kind not in table:
        raise GenomeError(f"unknown frame kind {kind!r}")
    return table[kind]


def priority_level(salience: float) -> int:
    return min(255, int(64 * math.log2(1.0 + salience)))


# =================================================================== input
def _problem(data):
    if not isinstance(data, dict):
        raise GenomeError("data must be a JSON object")
    n, owner, unary, edges = data.get("n"), data.get("owner"), data.get("unary"), data.get("edges")
    bound, bus = data.get("coupling_bound"), data.get("bus")
    if type(n) is not int or not 2 <= n <= WS_MAX_N:
        raise GenomeError(f"n: integer in [2, {WS_MAX_N}]")
    if not isinstance(owner, list) or len(owner) != n or not all(type(b) is int and b >= 0 for b in owner):
        raise GenomeError("owner: one block index per variable")
    k = max(owner) + 1
    blocks = [[v for v in range(n) if owner[v] == b] for b in range(k)]
    if not 2 <= k <= WS_MAX_BLOCKS or any(not 1 <= len(b) <= WS_MAX_BLOCK for b in blocks):
        raise GenomeError(f"2-{WS_MAX_BLOCKS} specialists, each owning 1-{WS_MAX_BLOCK} variables, indices 0..K-1")
    if not _num(bound) or not 0 < bound <= 1e3:
        raise GenomeError("coupling_bound: a number in (0, 1000]")
    if not isinstance(unary, list) or len(unary) != n or not all(_num(h) and abs(h) <= 1e3 for h in unary):
        raise GenomeError("unary: n finite fields, |h| <= 1000")
    if not isinstance(edges, list) or len(edges) > WS_MAX_EDGES:
        raise GenomeError(f"edges: a list of at most {WS_MAX_EDGES} [u, w, J]")
    seen = set()
    for e in edges:
        if (not isinstance(e, list) or len(e) != 3 or type(e[0]) is not int or type(e[1]) is not int
                or not 0 <= e[0] < n or not 0 <= e[1] < n or e[0] == e[1] or not _num(e[2])
                or abs(e[2]) > bound):
            raise GenomeError("each edge is [u, w, J] with distinct variables in range and |J| <= coupling_bound")
        key = (min(e[0], e[1]), max(e[0], e[1]))
        if key in seen:
            raise GenomeError("duplicate edge")
        seen.add(key)
    if (not isinstance(bus, dict) or set(bus) != {"bits_per_round", "rounds"}
            or type(bus["bits_per_round"]) is not int or not 1 <= bus["bits_per_round"] <= WS_MAX_BITS
            or type(bus["rounds"]) is not int or not 0 <= bus["rounds"] <= WS_MAX_ROUNDS):
        raise GenomeError(f"bus: {{bits_per_round: 1-{WS_MAX_BITS}, rounds: 0-{WS_MAX_ROUNDS}}}")
    pos = {}
    for b, vs in enumerate(blocks):
        for j, v in enumerate(vs):
            pos[v] = (b, j)
    inner = [[] for _ in range(k)]           # per block: (local i, local j, J)
    cross = {v: [] for v in range(n)}        # v -> [(w, J)] crossing couplings
    for u, w, j in edges:
        if owner[u] == owner[w]:
            inner[owner[u]].append((pos[u][1], pos[w][1], float(j)))
        else:
            cross[u].append((w, float(j)))
            cross[w].append((u, float(j)))
    tables = []
    for b, vs in enumerate(blocks):
        spins, base = [], []
        for state in range(1 << len(vs)):
            s = tuple(1 if state >> j & 1 else -1 for j in range(len(vs)))
            spins.append(s)
            base.append(sum(unary[v] * s[j] for j, v in enumerate(vs))
                        + sum(jj * s[a] * s[c] for a, c, jj in inner[b]))
        tables.append((spins, base))
    return {"n": n, "owner": owner, "blocks": blocks, "pos": pos, "cross": cross, "tables": tables,
            "bound": float(bound), "B": bus["bits_per_round"], "R": bus["rounds"],
            "boundary": {v for v in range(n) if cross[v]}}


def _minima(P, b, coef):
    """Block b's exact minimum with linear terms coef[j] * s_j added: (best state, best E, min E with s_j = +1,
    min E with s_j = -1) for every local j."""
    spins, base = P["tables"][b]
    size = len(P["blocks"][b])
    best, best_e = 0, math.inf
    plus, minus = [math.inf] * size, [math.inf] * size
    for state, (s, e0) in enumerate(zip(spins, base)):
        e = e0
        for j in range(size):
            e += coef[j] * s[j]
        if e < best_e:
            best, best_e = state, e
        for j in range(size):
            if s[j] > 0:
                if e < plus[j]:
                    plus[j] = e
            elif e < minus[j]:
                minus[j] = e
    return best, best_e, plus, minus


def _decision_coef(P, b, W):
    return [sum(jj * (2 * W[w] - 1) for w, jj in P["cross"][v] if w in W) for v in P["blocks"][b]]


def _readout(P, coef_of):
    x = [0] * P["n"]
    for b, vs in enumerate(P["blocks"]):
        best = _minima(P, b, coef_of(b))[0]
        for j, v in enumerate(vs):
            x[v] = best >> j & 1
    return x


def energy(data, x) -> float:
    s = [2 * v - 1 for v in x]
    return (math.fsum(h * s[v] for v, h in enumerate(data["unary"]))
            + math.fsum(j * s[u] * s[w] for u, w, j in data["edges"]))


def _decision_proposals(P, W, *, salience=True, only=None):
    """Every owned boundary variable whose block-MAP value differs from W: [(priority or 0, var, value, block)]
    (of block ``only`` when given)."""
    out = []
    for b, vs in enumerate(P["blocks"]):
        if only is not None and b != only:
            continue
        best, best_e, plus, minus = _minima(P, b, _decision_coef(P, b, W))
        for j, v in enumerate(vs):
            if v not in P["boundary"]:
                continue
            x = best >> j & 1
            gap = (minus[j] if x else plus[j]) - best_e
            if W.get(v) == x or gap <= GAP_EPS:
                continue
            reach = sum(abs(jj) for _, jj in P["cross"][v])
            out.append((priority_level(gap * reach) if salience else 0, v, x, b))
    return out


def _budget_abstain(P, budget, bits):
    cost = P["R"] * sum(1 << len(vs) for vs in P["blocks"])
    if int(budget.get("compute", 10 ** 9)) < cost:
        return ["compute budget below rounds x sum over specialists of 2^block_size"]
    if P["R"] > 0 and P["B"] < bits:
        return [f"the bus ({P['B']} bits per round) is too narrow for one {bits}-bit frame"]
    return None


# =================================================================== candidate: the global workspace
def ws_solve(data, budget):
    P = _problem(data)
    bits = frame_bits("decision_priority", P["n"])
    missing = _budget_abstain(P, budget, bits)
    if missing:
        return answer(None, {"frame_bits": bits}, status="ABSTAIN", missing=missing)
    capacity = P["B"] // bits
    W, trace, quiescent = {}, [], False
    for _ in range(P["R"]):
        proposals = _decision_proposals(P, W)
        if not proposals:
            quiescent = True
            break
        admitted = sorted(proposals, key=lambda p: (-p[0], p[1]))[:capacity]
        trace.append([{"kind": "decision_priority", "var": v, "value": x, "priority": p} for p, v, x, _ in admitted])
        for _, v, x, _ in admitted:
            W[v] = x
    else:
        quiescent = not _decision_proposals(P, W)
    x = _readout(P, lambda b: _decision_coef(P, b, W))
    used = sum(frame_bits(f["kind"], P["n"]) for r in trace for f in r)
    return answer({"assignment": x, "energy": energy(data, x), "trace": trace, "bits_used": used,
                   "rounds_used": len(trace), "quiescent": quiescent},
                  {"method": "global workspace: block-exact specialists propose boundary decisions with salience "
                             "gap x crossing-coupling mass; priority arbitration admits the top frames per round; "
                             "broadcast to all; repeat to quiescence or the round limit",
                   "frame_bits": bits, "frames_per_round": capacity, "priority": "floor(64 log2(1 + salience)), "
                   "cap 255, ties to the lower variable id", "bus": {"bits_per_round": P["B"], "rounds": P["R"]},
                   "frames_sent": sum(len(r) for r in trace), "broadcast_variables": len(W),
                   "boundary_variables": len(P["boundary"])})


# =================================================================== baseline and competitors
def ws_independent(data):
    """Baseline: every specialist's block MAP ignoring every crossing coupling, merged; no bits on the bus."""
    P = _problem(data)
    return {"assignment": _readout(P, lambda b: [0.0] * len(P["blocks"][b])), "trace": []}


def _round_robin(P, r, pending, kind):
    """One round of the round-robin bus: pending[b] is block b's ordered frames; returns the frames sent."""
    budget, sent = P["B"], []
    k = len(P["blocks"])
    size = frame_bits(kind, P["n"])
    for t in range(k):
        b = (r + t) % k
        if not pending[b]:
            if budget < 1:
                break
            sent.append({"kind": "pass", "block": b})
            budget -= 1
            continue
        stop = False
        for frame in pending[b]:
            if budget < size:
                stop = True
                break
            sent.append(frame)
            budget -= size
        if stop:
            break
    return sent


def ws_blackboard(data):
    """Competitor candidate 3: the same decisions without competition, in variable-id order on a round-robin bus."""
    P = _problem(data)
    W, trace = {}, []
    for r in range(P["R"]):
        proposals = _decision_proposals(P, W, salience=False)
        if not proposals:
            break
        pending = [[{"kind": "decision", "var": v, "value": x} for _, v, x, bb in sorted(proposals, key=lambda p: p[1])
                    if bb == b] for b in range(len(P["blocks"]))]
        sent = _round_robin(P, r, pending, "decision")
        trace.append(sent)
        for f in sent:
            if f["kind"] == "decision":
                W[f["var"]] = f["value"]
    return {"assignment": _readout(P, lambda b: _decision_coef(P, b, W)), "trace": trace}


def ws_token_ring(data):
    """Competitor (added after the development run; see the module disclosure): sequential sharing of hard decisions
    on a token ring. Each round the token visits every specialist once, starting at round mod K; the holder
    recomputes its block MAP from the latest board (including frames sent earlier in the same round), sends its
    changed boundary decisions in variable-id order while bits remain, and passes the token for 1 bit when it has
    none. No priority field: frame id + 1 bits. This is distributed block coordinate descent (Gauss-Seidel)."""
    P = _problem(data)
    k = len(P["blocks"])
    size = frame_bits("decision", P["n"])
    W, trace = {}, []
    for r in range(P["R"]):
        budget, sent, active = P["B"], [], False
        for t in range(k):
            b = (r + t) % k
            proposals = sorted(_decision_proposals(P, W, salience=False, only=b), key=lambda p: p[1])
            if not proposals:
                if budget < 1:
                    break
                sent.append({"kind": "pass", "block": b})
                budget -= 1
                continue
            active, full = True, False
            for _, v, x, _ in proposals:
                if budget < size:
                    full = True
                    break
                sent.append({"kind": "decision", "var": v, "value": x})
                budget -= size
                W[v] = x
            if full:
                break
        if not active:
            break
        trace.append(sent)
    return {"assignment": _readout(P, lambda b: _decision_coef(P, b, W)), "trace": trace}


def _bp_message(j, cavity):
    """min-sum message difference over x_w from a cavity difference D over x_v on coupling J s_v s_w."""
    return min(-j, j + cavity) - min(j, -j + cavity)


def _bp(data, prioritised):
    P = _problem(data)
    n, k = P["n"], len(P["blocks"])
    clip = 4.0 * P["bound"]
    msg = {}                                  # (a, b) -> message difference over x_b, from a to b
    last = {v: 0 for v in P["boundary"]}      # last broadcast belief level (0: nothing heard)

    def coef(b):
        return [sum(msg.get((w, v), 0.0) for w, _ in P["cross"][v]) / 2.0 for v in P["blocks"][b]]
    kind = "belief_priority" if prioritised else "belief"
    size = frame_bits(kind, n)
    trace = []
    for r in range(P["R"]):
        pending = []
        for b, vs in enumerate(P["blocks"]):
            _, _, plus, minus = _minima(P, b, coef(b))
            for j, v in enumerate(vs):
                if v not in P["boundary"]:
                    continue
                d = max(-clip, min(clip, plus[j] - minus[j]))
                level = int(round(d / clip * BELIEF_LEVELS))
                if level != last[v]:
                    pending.append((abs(level - last[v]), v, level, b))
        if not pending:
            break
        if prioritised:
            chosen = sorted(pending, key=lambda p: (-min(255, p[0]), p[1]))[:P["B"] // size]
            sent = [{"kind": kind, "var": v, "level": q, "priority": min(255, res)} for res, v, q, _ in chosen]
        else:
            per = [[{"kind": kind, "var": v, "level": q} for _, v, q, bb in sorted(pending, key=lambda p: (-p[0], p[1]))
                    if bb == b] for b in range(k)]
            sent = _round_robin(P, r, per, kind)
        snapshot = dict(msg)
        for f in sent:
            if f["kind"] == "pass":
                continue
            v, q = f["var"], f["level"]
            belief = q / BELIEF_LEVELS * clip
            for w, jj in P["cross"][v]:
                msg[(v, w)] = _bp_message(jj, belief - snapshot.get((w, v), 0.0))
            last[v] = q
        trace.append(sent)
    return {"assignment": _readout(P, coef), "trace": trace}


def ws_bp_priority(data):
    """Competitor candidate 1: belief-broadcast block min-sum BP, residual-scheduled by priority arbitration."""
    return _bp(data, True)


def ws_bp_round_robin(data):
    """Competitor candidate 2: belief-broadcast block min-sum BP on the round-robin bus (no priority bits)."""
    return _bp(data, False)


# =================================================================== independent verifier
def _v_graph(data):
    n = data["n"]
    owner = data["owner"]
    nbr = {v: {} for v in range(n)}
    for u, w, j in data["edges"]:
        nbr[u][w] = j
        nbr[w][u] = j
    blocks = {}
    for v in range(n):
        blocks.setdefault(owner[v], []).append(v)
    return nbr, [blocks[b] for b in sorted(blocks)]


def _v_block(data, nbr, vs, known):
    """{assignment tuple: energy} over the block by itertools, crossing couplings to known variables clamped."""
    inside = set(vs)
    out = {}
    for xs in itertools.product((0, 1), repeat=len(vs)):
        x = dict(zip(vs, xs))
        e = 0.0
        for v in vs:
            sv = 1 if x[v] else -1
            e += data["unary"][v] * sv
            for w, j in nbr[v].items():
                if w in inside:
                    if w > v:
                        e += j * sv * (1 if x[w] else -1)
                elif w in known:
                    e += j * sv * (1 if known[w] else -1)
        out[xs] = e
    return out


def _v_proposals(data, nbr, blocks, known):
    """var -> (value, admissible priority levels) for every proposal at the snapshot ``known``."""
    out = {}
    for vs in blocks:
        table = _v_block(data, nbr, vs, known)
        low = min(table.values())
        for i, v in enumerate(vs):
            if not any(data["owner"][w] != data["owner"][v] for w in nbr[v]):
                continue
            best = {val: min(e for xs, e in table.items() if xs[i] == val) for val in (0, 1)}
            value = 0 if best[0] <= best[1] else 1
            gap = best[1 - value] - low
            if gap <= GAP_EPS or known.get(v) == value:
                continue
            reach = math.fsum(abs(j) for w, j in nbr[v].items() if data["owner"][w] != data["owner"][v])
            out[v] = (value, {priority_level(gap * reach * (1 - 1e-9)), priority_level(gap * reach * (1 + 1e-9))})
    return out


def ws_verify(data, output, certificate):
    P = _problem(data)
    n, B, R = P["n"], P["B"], P["R"]
    keys = {"assignment", "energy", "trace", "bits_used", "rounds_used", "quiescent"}
    if (not isinstance(output, dict) or set(output) != keys or not isinstance(output["assignment"], list)
            or len(output["assignment"]) != n or not all(type(x) is int and x in (0, 1) for x in output["assignment"])
            or not _num(output["energy"]) or not isinstance(output["trace"], list)
            or type(output["bits_used"]) is not int or type(output["rounds_used"]) is not int
            or type(output["quiescent"]) is not bool):
        return {"output_shape": False}
    nbr, blocks = _v_graph(data)
    size = PRIORITY_BITS + max(1, math.ceil(math.log2(n))) + 1
    capacity = B // size
    frames_ok, budget_ok, truthful, arbitration = True, True, True, True
    known, recount = {}, 0
    for frames in output["trace"]:
        if (not isinstance(frames, list) or not frames or not all(
                isinstance(f, dict) and set(f) == {"kind", "var", "value", "priority"} and f["kind"] == "decision_priority"
                and type(f["var"]) is int and 0 <= f["var"] < n and type(f["value"]) is int and f["value"] in (0, 1)
                and type(f["priority"]) is int and 0 <= f["priority"] <= 255 for f in frames)):
            frames_ok = False
            break
        bits = size * len(frames)
        recount += bits
        budget_ok &= bits <= B
        proposals = _v_proposals(data, nbr, blocks, known)
        sent = [f["var"] for f in frames]
        truthful &= len(set(sent)) == len(sent) and all(
            f["var"] in proposals and proposals[f["var"]][0] == f["value"] and f["priority"] in proposals[f["var"]][1]
            for f in frames)
        arbitration &= len(frames) == min(capacity, len(proposals))
        arbitration &= all(f["priority"] >= frames[i + 1]["priority"] for i, f in enumerate(frames[:-1]))
        for q, (_, levels) in proposals.items():
            if q in sent:
                continue
            for f in frames:            # refuted only if a dropped proposal certainly outranks an admitted frame
                if min(levels) > f["priority"] or (min(levels) == f["priority"] and q < f["var"]):
                    arbitration = False
        for f in frames:
            known[f["var"]] = f["value"]
    checks = {"output_shape": True, "frames_well_formed": frames_ok}
    if not frames_ok:
        return checks
    rounds = len(output["trace"])
    quiet = not _v_proposals(data, nbr, blocks, known)
    x = output["assignment"]
    optimal = True
    for vs in blocks:
        table = _v_block(data, nbr, vs, known)
        optimal &= table[tuple(x[v] for v in vs)] <= min(table.values()) + 1e-9 * (1 + abs(min(table.values())))
    s = [2 * v - 1 for v in x]
    e = sum(data["unary"][v] * s[v] for v in range(n)) + sum(j * s[u] * s[w] for u, w, j in data["edges"])
    checks.update({
        "bus_budget_recounted": budget_ok and rounds <= R and output["bits_used"] == recount
                                and output["rounds_used"] == rounds,
        "frames_are_owner_proposals_at_snapshot": truthful,
        "arbitration_admits_top_priority_up_to_capacity": arbitration,
        "stops_exactly_at_quiescence_or_round_limit": output["quiescent"] == quiet and (quiet or rounds == R),
        "readout_blocks_are_optimal_given_workspace": optimal,
        "energy_recomputed": abs(e - output["energy"]) <= 1e-7 * (1 + abs(e)),
    })
    return checks


# =================================================================== benchmark: synthetic distributed spin glasses
def ws_instance(seed):
    """Synthetic. n 12-20 variables in K 3-4 contiguous blocks (sizes within one of each other); inside couplings on
    each pair with probability 0.5, J ~ N(0, 1); crossing couplings with mean crossing degree d ~ U[0.8, 2.0],
    J ~ c N(0, 1) with c ~ U[0.5, 1.5]; every |J| clipped to the coupling bound 2.5; fields h ~ N(0, sigma_h),
    sigma_h ~ U[0.1, 0.8]; bus 24-64 bits per round for 3-8 rounds. Truth: exact minimum energy by enumeration."""
    r = random.Random(f"genome:meta_global_workspace:{seed}")
    n = r.randint(12, 20)
    k = r.randint(3, 4)
    sizes = [n // k + (1 if b < n % k else 0) for b in range(k)]
    owner = [b for b, s in enumerate(sizes) for _ in range(s)]
    bound = 2.5

    def coupling(scale):
        return round(max(-bound, min(bound, scale * r.gauss(0.0, 1.0))), 6)
    d, c = r.uniform(0.8, 2.0), r.uniform(0.5, 1.5)
    p_cross = d / (n - n / k)
    edges = []
    for u in range(n):
        for w in range(u + 1, n):
            if owner[u] == owner[w]:
                if r.random() < 0.5:
                    edges.append([u, w, coupling(1.0)])
            elif r.random() < p_cross:
                edges.append([u, w, coupling(c)])
    if not any(owner[u] != owner[w] for u, w, _ in edges):
        u = r.randrange(sizes[0])
        edges.append([u, n - 1, coupling(c)])
    sigma = r.uniform(0.1, 0.8)
    data = {"n": n, "owner": owner, "unary": [round(r.gauss(0.0, sigma), 6) for _ in range(n)], "edges": edges,
            "coupling_bound": bound, "bus": {"bits_per_round": r.randint(24, 64), "rounds": r.randint(3, 8)}}
    return data, {"min_energy": exact_minimum(data), "upper_bound": math.fsum(abs(h) for h in data["unary"])
                  + math.fsum(abs(j) for _, _, j in edges)}


def exact_minimum(data) -> float:
    """Evaluation side only (``instance``; never ``solve`` or ``verify``): the exact minimum by enumeration."""
    import numpy as np
    n = data["n"]
    if n > WS_TRUTH_MAX_N:
        raise GenomeError(f"truth enumeration limited to n <= {WS_TRUTH_MAX_N}")
    best = math.inf
    chunk = 1 << min(n, 16)
    shifts = np.arange(n, dtype=np.uint32)
    h = np.array(data["unary"], dtype=float)
    for start in range(0, 1 << n, chunk):
        states = np.arange(start, start + chunk, dtype=np.uint32)
        s = (((states[:, None] >> shifts) & 1).astype(np.int8) * 2 - 1).astype(float)
        e = s @ h
        for u, w, j in data["edges"]:
            e += j * s[:, u] * s[:, w]
        best = min(best, float(e.min()))
    return best


def ws_subregion(data):
    """From the data alone: is the bus narrower than one workspace frame per boundary variable over the run, and is
    the crossing coupling mass at least half the inside coupling mass."""
    P = _problem(data)
    frames = P["R"] * (P["B"] // frame_bits("decision_priority", P["n"]))
    owner = data["owner"]
    cross = math.fsum(abs(j) for u, w, j in data["edges"] if owner[u] != owner[w])
    inside = math.fsum(abs(j) for u, w, j in data["edges"] if owner[u] == owner[w])
    return (("narrow_bus" if frames < len(P["boundary"]) else "wide_bus")
            + ("_strong_cross" if cross >= 0.5 * inside else "_weak_cross"))


def ws_score(data, truth, output):
    """Quality: minus the energy gap to the exact minimum. Abstaining scores as the worst conceivable assignment (the
    sum of absolute factor weights); an over-budget or malformed answer is wrong, one unit below abstaining."""
    abstain = -(truth["upper_bound"] - truth["min_energy"])
    if output is None:
        return {"quality": abstain, "category": "abstain"}
    n = data["n"]
    x = output.get("assignment") if isinstance(output, dict) else None
    trace = output.get("trace") if isinstance(output, dict) else None
    if (not isinstance(x, list) or len(x) != n or not all(type(v) is int and v in (0, 1) for v in x)
            or not isinstance(trace, list) or len(trace) > data["bus"]["rounds"]):
        return {"quality": abstain - 1.0, "category": "wrong"}
    try:
        over = any(sum(frame_bits(f["kind"], n) for f in r) > data["bus"]["bits_per_round"] for r in trace)
    except (GenomeError, TypeError, KeyError):
        over = True
    if over:
        return {"quality": abstain - 1.0, "category": "wrong"}
    return {"quality": -(energy(data, x) - truth["min_energy"]), "category": "correct"}


# =================================================================== genome
_DEV = "seeds 0-9 dev, held-out seeds fixed by the admission freeze"

INTELLIGENCES = [
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="meta.workspace.salience_broadcast", version="1.0.0", family="meta_global_workspace",
            layer=5, operation="global_workspace_broadcast", epistemic_class="optimization",
            subgeometry="specialists each holding a block of a pairwise binary factor graph (fields, inside and "
                        "crossing couplings) jointly minimise its energy by exchanging decisions over one shared "
                        "broadcast bus of declared bits per round and rounds",
            source_provenance="Baars (1988) global workspace theory; Dehaene, Kerszberg and Changeux (1998) and "
                              "Dehaene and Naccache (2001) global neuronal workspace (competition, ignition, "
                              "broadcast); compiled to priority-arbitrated broadcast (CAN bus, ISO 11898) among "
                              "block-exact specialists; compared with belief propagation (Pearl 1988) under residual "
                              "scheduling (Elidan, McGraw and Koller 2006) and with distributed constraint "
                              "optimisation practice (Maheswaran, Pearce and Tambe 2004, MGM)",
            buildability="BUILDABLE_NOW",
            native_representation="n, owner [n] block per variable, unary [n], edges [[u, w, J]], coupling_bound, "
                                  "bus {bits_per_round, rounds}",
            required_inputs=("n", "owner", "unary", "edges", "coupling_bound", "bus"),
            output_contract={"assignment": "[n] in {0,1}", "energy": "E(assignment)",
                             "trace": "[rounds][frames] the bus record", "bits_used": "recounted bus bits",
                             "rounds_used": "rounds", "quiescent": "no proposal remained"},
            algorithm_or_runtime="per round: block-exact MAP per specialist given the workspace -> boundary "
                                 "proposals with salience gap x crossing mass -> 8-bit priority arbitration admits "
                                 "floor(B / frame) frames -> broadcast; stop at quiescence or the round limit; "
                                 "readout block MAPs",
            parameters={"priority_bits": PRIORITY_BITS, "priority": "floor(64 log2(1 + salience)), cap 255",
                        "salience": "decision gap x sum of |crossing couplings|", "max_block": WS_MAX_BLOCK},
            memory_model="the workspace (last broadcast value per variable), rebuilt each call",
            learning_rule="none: no state persists between calls",
            composition_inputs=("specialists' private factors", "a bandwidth budget"),
            composition_outputs=("a joint assignment", "the broadcast record"),
            evidence_type="collective_trace",
            verification_method="independent replay by itertools enumeration: bus bits recounted against the frame "
                                "formats, budget and round limit; every frame an owner proposal at its round's "
                                "snapshot with its recomputed priority; arbitration top-capacity; stop condition; "
                                "readout blocks optimal given the final workspace; energy recomputed",
            confidence_semantics="the energy of the returned assignment is exact; its gap to the global minimum is "
                                 "not certified (no lower bound is produced)",
            resource_profile="rounds x sum over specialists of 2^block_size x block_size arithmetic; pure Python",
            latency_profile="milliseconds",
            known_strengths=("one broadcast decision informs every crossing neighbour at once",
                             "the bus carries the most decisive and most coupled decisions first",
                             "the whole run is replayable and its bandwidth is recounted"),
            known_failure_modes=(
                "priority bits are bus cost: an 8-bit priority field roughly doubles a decision frame, so "
                "unprioritised sharing moves about twice as many decisions per bit",
                "synchronous updates from one snapshot oscillate on frustrated crossing couplings when many frames fit "
                "a round: on development seeds 0-9 with a 4000-bit bus, 8 of 10 runs flip until the round limit and "
                "score no better than no communication, while the token ring settles in 1-2 rounds; the mechanism is "
                "not monotone in bandwidth (found after the development run; recorded, the candidate unchanged)",
                "hard decisions discard the specialists' soft evidence",
                "a decision of zero gap is never broadcast, so neighbours never learn an indifferent variable",
                "no optimality certificate: the answer is a block-consistent local solution, not a global minimum"),
            counterindications=("all factors can be gathered in one place: solve the whole graph exactly instead",
                                "a bus wide enough to admit most proposals in one round (synchronous oscillation)",
                                "blocks larger than 10 variables", "a bus wide enough to ship every factor"),
            abstention_conditions=("a bus narrower than one workspace frame per round",
                                   "a compute budget below rounds x sum over specialists of 2^block_size"),
            benchmark_suite="synthetic distributed spin glasses: 12-20 variables in 3-4 specialists, inside "
                            "couplings N(0,1) on half the pairs, crossing couplings c N(0,1) with c ~ U[0.5, 1.5] and "
                            "mean crossing degree U[0.8, 2.0], |J| <= 2.5, fields N(0, U[0.1, 0.8]); bus 24-64 bits "
                            "per round for 3-8 rounds; quality minus the energy gap to the exact minimum (enumeration);"
                            " over-budget answers wrong; " + _DEV,
            baseline="independent specialists without communication, merged",
            competitor="sequential token-ring sharing of the same hard decisions without priority bits (distributed "
                       "block coordinate descent), on the same bus and budget",
            lineage=LINEAGE),
        solve=ws_solve, verify=ws_verify, instance=ws_instance, score=ws_score,
        baseline=ws_independent, competitor=ws_token_ring, subregion=ws_subregion, tolerance=1e-9,
        notes={"competitor": "ws_token_ring, added after the development run because it is stronger than the three "
                             "declared schemes (module docstring disclosure)",
               "alternative_competitors": "ws_bp_priority (the declared rule's pick), ws_bp_round_robin and "
                                          "ws_blackboard; reported on development seeds, not used by the rule",
               "bandwidth_matching": "every arm runs on the same bus: the same bits per round and rounds, every frame "
                                     "charged by the declared formats (frame_bits); losing arbitration frames cost "
                                     "nothing (CAN-style); the readout of each block's decision is free for every arm",
               "score": "minus the energy gap to the exact minimum (enumeration of 2^n, n <= 20); an over-budget "
                        "trace is wrong"}),
]
