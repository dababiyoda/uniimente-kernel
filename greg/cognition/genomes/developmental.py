"""Layer 4 developmental / morphogenetic intelligence, compiled to computational mechanisms.

Founder rule (INTENT-0030, INTENT-20261007-POLYINTELLIGENCE-MIND-CONTINUATION): preserve the effect, do not
literalize the metaphor. "Developmental" labels two computational effects below; nothing here claims
biological equivalence, life, consciousness or general intelligence, and nothing carries authority.

Core question: can a higher-order target state stay stable while the lower-level structure is damaged and
reorganises, measured against STRONG conventional baselines?

* ``develop_repair`` (operation ``target_state_repair``): locally-competent units on a 4-neighbour lattice
  hold a transport target (every functioning source unit forwards to the sink region) through region
  removal, unit failures, link blocking and lossy neighbour messages. Each unit keeps only soft local state
  (sequence number, potential, feasibility distance, neighbour cache), senses its own links and talks only
  to neighbours: the sink region emits a sequence-numbered potential wave every ``WAVE_PERIOD`` steps
  (destination-sequenced distance vector, DSDV), routes are accepted only under the Babel feasibility
  condition (loop-free at every step), broken routes are retracted, and a unit vouches for its source route
  only while it was refreshed by a sink wave within an expiry window. The world script (damage, mid-repair
  failures, message loss) is a sandboxed simulation; the rules never read it ahead of time.
  Baseline: no repair. Competitor: an adaptive centralized replanner (global BFS rebuild of every forwarding
  pointer on its topology view, reliable pushes). Predeclared seeded conditions make that controller
  reliable or unreliable (crash mid-repair with probability q = 0.5, else a stale view); expected and
  reported: the reliable controller wins (exact repair, far fewer messages).
* ``develop_constraint_release`` (operation ``release_recombine_pipeline``): validated small heuristic
  operators for single-machine total weighted tardiness (dispatch rules EDD / WSPT / slack / WMDD / ATC(k);
  swap and insert improvement passes with adjacent / windowed / full neighbourhoods and first / best
  acceptance) are released from their fixed pipeline order and recombined by a bounded seeded (mu + lambda)
  evolutionary search on the instance's training split; the best candidates are measured on the
  validation split and retained only if they beat the original pipeline there, otherwise they go extinct
  and the original is kept. Output: the retained configuration plus its lineage (parents, mutations).
  Scored on held-out cases against the exact optimum (subset dynamic programming). No configuration gets
  authority. Baseline: the original fixed pipeline. Competitor: random-restart configuration search with
  the same evaluation budget and the same retain rule.

The sealed MICA/CDPE laboratory (``developmental/``) is imported lazily and never modified: its
TARGET_FORM_001 lattice, tissue layout (sensor tissue = sources, actuator tissue = sinks) and route-blocking
perturbation build the repair benchmark, and its centralized potential propagation cross-checks the
benchmark truth. Nothing here writes files, opens sockets, spawns processes or touches the environment.

Frontier, stated plainly: robust unscripted organ formation, generalized repair across domains and
cross-substrate developmental compilation are NOT achieved by anything in this module.
"""
from __future__ import annotations

from collections import deque
import hashlib
import json
import math
import random

from .contract import Executable, GenomeError, IntelligenceGenome, answer, bounded_int, finite

LINEAGE = ("INTENT-20261007-POLYINTELLIGENCE-MIND-CONTINUATION", "INTENT-20261007-VERIFIED-POLYINTELLIGENCE-LIFT",
           "INTENT-0030 effect-not-metaphor",
           "developmental/ MICA/CDPE TARGET_FORM_001 laboratory (sealed; imported, never modified)")
SEED_MAX = 2 ** 31 - 1


def _require_dict(data):
    if not isinstance(data, dict):
        raise GenomeError("data must be an object")
    return data


# ============================================================================ 1. target-state repair
REPAIR_MAX_UNITS = 200
REPAIR_MAX_STEPS = 400
REPAIR_MAX_EVENTS = 20
WAVE_PERIOD = 8            # sink region emits a new sequence number every WAVE_PERIOD steps
EXPIRY_WAVES = 2           # a route not refreshed within this many wave periods (+ its travel time) is unvouched
REPEATS = 5                # a changed route is re-broadcast until every live neighbour echoes it (implicit ack),
RETRACT_REPEATS = 3        # at most REPEATS times; a retraction is broadcast RETRACT_REPEATS times
MAX_LOSS = 0.5             # validated message-loss range of the local protocol
ACTION_COST = 0.05         # quality lost by an arm performing one unit-action per unit per step
WRONG_PENALTY = 1.5        # a false restoration claim is strictly worse than abstaining
BENCH_STEPS = 120
CONTROLLER_MODES = ("reliable", "crash", "stale")


def _key(idx, height):
    return f"{idx // height},{idx % height}"


def _parse_key(key, width, height):
    """'x,y' -> index, or None when malformed / off the lattice."""
    if not isinstance(key, str) or key.count(",") != 1:
        return None
    a, b = key.split(",")
    if not (a.isdigit() and b.isdigit()) or len(a) > 3 or len(b) > 3:
        return None
    x, y = int(a), int(b)
    if not (0 <= x < width and 0 <= y < height):
        return None
    return x * height + y


def _cell_list(value, width, height, name, low, high):
    if not isinstance(value, list) or not low <= len(value) <= high:
        raise GenomeError(f"{name}: list of {low}-{high} [x, y] cells required")
    out = []
    for c in value:
        if (not isinstance(c, list) or len(c) != 2 or any(type(v) is not int for v in c)
                or not (0 <= c[0] < width and 0 <= c[1] < height)):
            raise GenomeError(f"{name}: every cell is [x, y] on the {width}x{height} lattice")
        out.append(c[0] * height + c[1])
    if len(set(out)) != len(out):
        raise GenomeError(f"{name}: cells must be distinct")
    return out


def _repair_inputs(data):
    _require_dict(data)
    width = bounded_int(data.get("width"), low=3, high=60, name="width")
    height = bounded_int(data.get("height"), low=3, high=60, name="height")
    if width * height > REPAIR_MAX_UNITS:
        raise GenomeError(f"at most {REPAIR_MAX_UNITS} lattice units")
    sources = _cell_list(data.get("sources"), width, height, "sources", 1, 60)
    sinks = _cell_list(data.get("sinks"), width, height, "sinks", 1, 60)
    if set(sources) & set(sinks):
        raise GenomeError("sources and sinks must be disjoint")
    removed = _cell_list(data.get("removed", []), width, height, "removed", 0, REPAIR_MAX_UNITS)
    blocked_raw = data.get("blocked", [])
    if not isinstance(blocked_raw, list) or len(blocked_raw) > 2 * REPAIR_MAX_UNITS:
        raise GenomeError("blocked: list of [[x, y], [x, y]] lattice edges")
    blocked = set()
    for edge in blocked_raw:
        if not isinstance(edge, list) or len(edge) != 2:
            raise GenomeError("blocked: every edge is [[x, y], [x, y]]")
        a, b = _cell_list(edge, width, height, "blocked edge", 2, 2)
        if abs(a // height - b // height) + abs(a % height - b % height) != 1:
            raise GenomeError("blocked: an edge joins two 4-neighbours")
        blocked.add((min(a, b), max(a, b)))
    steps = bounded_int(data.get("steps"), low=1, high=REPAIR_MAX_STEPS, name="steps")
    events_raw = data.get("events", [])
    if not isinstance(events_raw, list) or len(events_raw) > REPAIR_MAX_EVENTS:
        raise GenomeError(f"events: at most {REPAIR_MAX_EVENTS} scheduled failure events")
    events, total = {}, 0
    for ev in events_raw:
        if not isinstance(ev, dict) or set(ev) != {"step", "fail"}:
            raise GenomeError("event is {step, fail}")
        step = bounded_int(ev["step"], low=1, high=max(1, steps - 1), name="event step")
        cells = _cell_list(ev["fail"], width, height, "event fail", 1, REPAIR_MAX_UNITS)
        total += len(cells)
        events.setdefault(step, []).extend(cells)
    if total > REPAIR_MAX_UNITS:
        raise GenomeError("at most 200 scheduled unit failures")
    loss = finite(data.get("message_loss", 0.0), low=0.0, high=0.95, name="message_loss")
    seed = bounded_int(data.get("seed", 0), low=0, high=SEED_MAX, name="seed")
    cost = finite(data.get("action_cost", ACTION_COST), low=0.0, high=1.0, name="action_cost")
    controller = data.get("controller", {"mode": "reliable", "view_lag": 0, "crash_at": None})
    if not isinstance(controller, dict) or set(controller) != {"mode", "view_lag", "crash_at"}:
        raise GenomeError("controller is {mode, view_lag, crash_at}")
    if controller["mode"] not in CONTROLLER_MODES:
        raise GenomeError(f"controller mode is one of {CONTROLLER_MODES}")
    lag = bounded_int(controller["view_lag"], low=0, high=REPAIR_MAX_STEPS, name="view_lag")
    crash = controller["crash_at"]
    if crash is not None:
        crash = bounded_int(crash, low=0, high=REPAIR_MAX_STEPS, name="crash_at")
    return {"W": width, "H": height, "N": width * height, "sources": sources, "sinks": sinks,
            "removed": removed, "blocked": blocked, "steps": steps, "events": events, "loss": loss,
            "seed": seed, "cost": cost, "mode": controller["mode"], "lag": lag, "crash_at": crash}


def _lattice(width, height):
    """index (x * height + y) -> 4-neighbour indices in ascending (x, y) order."""
    adj = []
    for x in range(width):
        for y in range(height):
            nb = []
            for dx, dy in ((-1, 0), (0, -1), (0, 1), (1, 0)):
                if 0 <= x + dx < width and 0 <= y + dy < height:
                    nb.append((x + dx) * height + (y + dy))
            adj.append(sorted(nb))
    return adj


def _bfs_pointers(adj, dead, blocked, roots):
    """Multi-root BFS -> (dist, next-hop) with the MICA tie-break (lowest potential, then lowest (x, y))."""
    n = len(adj)
    dist = [None] * n
    queue = deque()
    for r in sorted(roots):
        if not dead[r]:
            dist[r] = 0
            queue.append(r)
    while queue:
        u = queue.popleft()
        for v in adj[u]:
            if dist[v] is None and not dead[v] and (min(u, v), max(u, v)) not in blocked:
                dist[v] = dist[u] + 1
                queue.append(v)
    nh = [None] * n
    for u in range(n):
        if dist[u] and not dead[u]:
            nh[u] = min((v for v in adj[u] if dist[v] == dist[u] - 1 and (min(u, v), max(u, v)) not in blocked))
    return dist, nh


def _settle_steps(width, height):
    return (EXPIRY_WAVES + 1) * WAVE_PERIOD + 2 * (width + height)


def _local_repair(inp):
    """Run the local rules inside the declared world script. Returns (state, statistics)."""
    W, H, N, T = inp["W"], inp["H"], inp["N"], inp["steps"]
    adj = _lattice(W, H)
    sinks = set(inp["sinks"])
    rng = random.Random(inp["seed"])
    loss = inp["loss"]
    dead = [False] * N
    blocked = set()
    phi, nh0 = _bfs_pointers(adj, dead, blocked, sinks)            # converged pre-damage state (sequence 0)
    phi = list(phi)
    nh = list(nh0)
    seq = [0] * N
    fd = [(0, phi[u]) for u in range(N)]                            # feasibility distance (seq, metric)
    cache = [{v: (0, phi[v]) for v in adj[u]} for u in range(N)]    # last (seq, metric) heard from each neighbour
    tx = [0] * N
    stats = {"adoptions": 0, "retractions": 0, "link_losses": 0, "messages_per_step": []}

    def links(u):
        return [v for v in adj[u] if not dead[v] and (min(u, v), max(u, v)) not in blocked]

    def update(u, live):
        old = (seq[u], phi[u])
        cur = nh[u]
        ent = cache[u].get(cur) if cur is not None and cur in live else None
        cur_ok = ent is not None and ent[1] is not None and ent[0] == seq[u] and phi[u] is not None
        fs, fm = fd[u]
        best = None
        for v in live:
            e = cache[u].get(v)
            if e is None or e[1] is None:
                continue
            s, m = e
            if not (s > fs or (s == fs and fm is not None and m < fm)):
                continue                                           # Babel feasibility: loop-free at every step
            if best is None or s > best[0] or (s == best[0] and m < best[1]):
                best = (s, m, v)
        if best is not None and (not cur_ok or best[0] > seq[u] or best[1] + 1 < phi[u]):
            s, m, v = best
            seq[u], phi[u], nh[u] = s, m + 1, v
            fd[u] = (s, m + 1) if s > fs else (fs, min(fm, m + 1))
            stats["adoptions"] += 1
        elif not cur_ok and phi[u] is not None:
            phi[u], nh[u] = None, None                             # retract: no feasible route under this seq
            stats["retractions"] += 1
        if (seq[u], phi[u]) != old:
            tx[u] = REPEATS if phi[u] is not None else RETRACT_REPEATS
            changed.add(u)

    changed = set()
    for t in range(T):
        touched = set()
        changed.clear()
        if t == 0:
            for u in inp["removed"]:
                dead[u] = True
                touched.update(adj[u])
            for a, b in inp["blocked"]:
                blocked.add((a, b))
                touched.update((a, b))
        for u in inp["events"].get(t, ()):
            if not dead[u]:
                dead[u] = True
                touched.update(adj[u])
        pending = set()
        for u in sorted(touched):                                   # local link sensing, nothing global
            if dead[u]:
                continue
            live = set(links(u))
            for v in [v for v in cache[u] if v not in live]:
                del cache[u][v]
                stats["link_losses"] += 1
            if nh[u] is not None and nh[u] not in live:
                pending.add(u)
        if t % WAVE_PERIOD == 0:
            for z in sinks:
                if not dead[z]:
                    seq[z], phi[z], nh[z] = t // WAVE_PERIOD + 1, 0, None
                    tx[z] = REPEATS
                    changed.add(z)
        for u in sorted(pending):
            if u not in sinks:
                update(u, set(links(u)))
        inbox = {}
        sent = 0
        senders = []
        for u in range(N):
            if dead[u] or tx[u] <= 0:
                continue
            for v in links(u):
                sent += 1
                if loss == 0.0 or rng.random() >= loss:
                    inbox.setdefault(v, []).append((u, seq[u], phi[u]))
            tx[u] -= 1
            senders.append(u)
        for v in sorted(inbox):
            for u, s, m in inbox[v]:
                cache[v][u] = (s, m)
            if v not in sinks:
                update(v, set(links(v)))
        for u in senders:                                           # implicit ack: every live neighbour echoed
            if tx[u] > 0 and u not in changed and phi[u] is not None and all(
                    v in cache[u] and cache[u][v][0] >= seq[u] for v in links(u)):
                tx[u] = 0
        stats["messages_per_step"].append(sent)
    return {"dead": dead, "phi": phi, "nh": nh, "seq": seq}, stats


def _vouched(state, u, steps, width, height):
    """A unit vouches for its route only while a sink wave refreshed it within the expiry window."""
    phi = state["phi"][u]
    if state["dead"][u] or phi is None or phi > 2 * (width + height):
        return False
    emitted = (state["seq"][u] - 1) * WAVE_PERIOD                    # sequence 0 = the pre-damage wave at -period
    return steps - emitted <= EXPIRY_WAVES * WAVE_PERIOD + phi


def repair_solve(data, budget):
    inp = _repair_inputs(data)
    W, H, N, T = inp["W"], inp["H"], inp["N"], inp["steps"]
    removed = set(inp["removed"])
    if inp["loss"] > MAX_LOSS:
        return answer(None, {"message_loss": inp["loss"], "validated_max": MAX_LOSS}, status="ABSTAIN",
                      missing=["message loss above the local protocol's validated range"])
    if T < _settle_steps(W, H):
        return answer(None, {"steps": T, "settle_steps": _settle_steps(W, H)}, status="ABSTAIN",
                      missing=["step budget shorter than the protocol's settle time"])
    if all(z in removed for z in inp["sinks"]) or all(s in removed for s in inp["sources"]):
        return answer(None, {"functioning_sinks": sum(z not in removed for z in inp["sinks"])}, status="ABSTAIN",
                      missing=["no functioning source or sink region: no target state to hold"])
    state, stats = _local_repair(inp)
    next_hop = {_key(u, H): _key(state["nh"][u], H) for u in range(N)
                if not state["dead"][u] and state["nh"][u] is not None}
    claimed = sorted(_key(u, H) for u in inp["sources"] if _vouched(state, u, T, W, H))
    actions = sum(stats["messages_per_step"])
    digest = hashlib.sha256(json.dumps(next_hop, sort_keys=True).encode()).hexdigest()
    certificate = {
        "mechanism": "destination-sequenced potential waves from the sink region, Babel feasibility condition, "
                     "local link sensing, retraction on loss, expiry-bounded vouching",
        "seed": inp["seed"], "message_loss": inp["loss"], "steps": T, "wave_period": WAVE_PERIOD,
        "expiry_waves": EXPIRY_WAVES, "repeats": REPEATS, "messages_per_step": stats["messages_per_step"],
        "adoptions": stats["adoptions"], "retractions": stats["retractions"],
        "link_losses_sensed": stats["link_losses"], "final_wave": T // WAVE_PERIOD + (1 if T % WAVE_PERIOD else 0),
        "source_route_seq": {_key(u, H): state["seq"][u] for u in inp["sources"] if not state["dead"][u]},
        "vouched_sources": len(claimed), "field_digest": "sha256:" + digest,
        "exact_restoration_attempts": 0, "external_effects": 0,
        "authorization_state": "SIMULATED_NOT_AUTHORIZED",
        "limits": "simulation of the declared world script; a claim is a refreshed local route, not a probe"}
    return answer({"next_hop": next_hop, "claimed": claimed, "actions": actions, "steps": T}, certificate)


def _realized(inp):
    """The world's final topology, rebuilt from the script (evaluation side; not the solver's state)."""
    dead = set(inp["removed"])
    for cells in inp["events"].values():
        dead.update(cells)
    return dead, set(inp["blocked"])


def _follow(start, next_hop, inp, dead, blocked):
    """Hops from ``start`` to the sink region along the returned pointers on the realized topology, or None."""
    W, H = inp["W"], inp["H"]
    sinks = set(inp["sinks"])
    cur, hops, seen = start, 0, {start}
    if cur in dead:
        return None
    while cur not in sinks:
        nxt = _parse_key(next_hop.get(_key(cur, H)), W, H)
        if nxt is None or nxt in dead or nxt in seen:
            return None
        if abs(cur // H - nxt // H) + abs(cur % H - nxt % H) != 1 or (min(cur, nxt), max(cur, nxt)) in blocked:
            return None
        cur, hops = nxt, hops + 1
        seen.add(cur)
        if hops > inp["N"]:
            return None
    return hops


def repair_verify(data, output, certificate):
    inp = _repair_inputs(data)
    W, H = inp["W"], inp["H"]
    dead, blocked = _realized(inp)
    hop = output.get("next_hop") if isinstance(output, dict) else None
    claimed = output.get("claimed") if isinstance(output, dict) else None
    if not isinstance(hop, dict) or not isinstance(claimed, list):
        return {"output_shape": False}
    parsed = [(_parse_key(k, W, H), _parse_key(v, W, H)) for k, v in hop.items()]
    lattice_ok = all(a is not None and b is not None and abs(a // H - b // H) + abs(a % H - b % H) == 1
                     for a, b in parsed)
    pointers_ok = lattice_ok and all(a not in dead and b not in dead and (min(a, b), max(a, b)) not in blocked
                                     for a, b in parsed)
    source_keys = {_key(s, H) for s in inp["sources"]}
    claims_are_sources = all(isinstance(k, str) and k in source_keys for k in claimed) and len(set(claimed)) == len(
        claimed)
    claims_deliver = claims_are_sources and all(
        _follow(_parse_key(k, W, H), hop, inp, dead, blocked) is not None for k in claimed)
    trace = certificate.get("messages_per_step") if isinstance(certificate, dict) else None
    actions_ok = (isinstance(trace, list) and len(trace) == inp["steps"] and type(output.get("actions")) is int
                  and all(type(m) is int and m >= 0 for m in trace) and sum(trace) == output["actions"])
    return {"pointers_are_lattice_edges": lattice_ok,
            "no_pointer_into_removed_unit_or_blocked_link": pointers_ok,
            "claims_are_distinct_sources": claims_are_sources,
            "every_claimed_source_delivers_on_realized_topology": claims_deliver,
            "actions_match_trace": actions_ok,
            "seed_bound": isinstance(certificate, dict) and certificate.get("seed") == inp["seed"],
            "no_external_effect": isinstance(certificate, dict) and certificate.get("external_effects") == 0}


def _reference_distances(width, height, dead_xy, blocked_xy, roots_xy):
    """Coordinate BFS (independent of the solver's index arithmetic): (x, y) -> hops to the nearest root."""
    dist = {r: 0 for r in roots_xy if r not in dead_xy}
    frontier = list(dist)
    while frontier:
        nxt = []
        for x, y in frontier:
            for c in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if not (0 <= c[0] < width and 0 <= c[1] < height) or c in dead_xy or c in dist:
                    continue
                if frozenset(((x, y), c)) in blocked_xy:
                    continue
                dist[c] = dist[(x, y)] + 1
                nxt.append(c)
        frontier = nxt
    return dist


def repair_score(data, truth, output):
    if not isinstance(output, dict) or not isinstance(output.get("next_hop"), dict):
        return {"quality": 0.0, "category": "abstain"}
    inp = _repair_inputs(data)
    W, H = inp["W"], inp["H"]
    dead, blocked = _realized(inp)
    hop = output["next_hop"]
    restored = []
    for key, d in truth["distances"].items():
        hops = _follow(_parse_key(key, W, H), hop, inp, dead, blocked)
        restored.append(0.0 if hops is None else d / hops if hops else 1.0)
    function = sum(restored) / len(restored)
    wrong = False
    claimed = output.get("claimed")
    source_keys = {_key(s, H) for s in inp["sources"]}
    if not isinstance(claimed, list) or len(set(map(str, claimed))) != len(claimed):
        wrong = True
    else:
        for key in claimed:                                       # collapse claimed as restored = a false answer
            if (not isinstance(key, str) or key not in source_keys
                    or _follow(_parse_key(key, W, H), hop, inp, dead, blocked) is None):
                wrong = True
    actions = output.get("actions")
    if type(actions) is not int or actions < 0:
        wrong, actions = True, 0
    quality = function - inp["cost"] * actions / (inp["N"] * inp["steps"])
    if wrong:
        return {"quality": quality - WRONG_PENALTY, "category": "wrong"}
    return {"quality": quality, "category": "correct"}


def repair_no_repair(data):
    """Baseline: keep the pre-damage forwarding field, perform no action, claim nothing."""
    inp = _repair_inputs(data)
    _, nh = _bfs_pointers(_lattice(inp["W"], inp["H"]), [False] * inp["N"], set(), set(inp["sinks"]))
    H = inp["H"]
    return {"next_hop": {_key(u, H): _key(v, H) for u, v in enumerate(nh) if v is not None},
            "claimed": [], "actions": 0, "steps": inp["steps"]}


def repair_central_replanner(data):
    """Competitor: adaptive centralized replanner.

    At every step it is running it rebuilds the global shortest-path forwarding field (BFS from the sink
    region, MICA tie-break) on its topology view whenever the view changed and pushes the changed pointers
    over a reliable management channel. Unit-actions: pushed pointers plus one telemetry report per unit
    sensing a link loss. Reliable: fresh view, never crashes. Unreliable (predeclared per seed): crashes at
    ``crash_at`` (a liveness monitor then voids its claims), or its view lags reality by ``view_lag`` steps.
    It claims every source its view shows connected.
    """
    inp = _repair_inputs(data)
    W, H, N, T = inp["W"], inp["H"], inp["N"], inp["steps"]
    adj = _lattice(W, H)
    sinks = set(inp["sinks"])
    no_dead = [False] * N
    _, table = _bfs_pointers(adj, no_dead, set(), sinks)
    table = list(table)
    history = {0: list(inp["removed"])}
    for step, cells in inp["events"].items():
        history.setdefault(step, []).extend(cells)

    def topology(t):
        if t < 0:
            return frozenset(), frozenset()
        return frozenset(u for s, cells in history.items() if s <= t for u in cells), frozenset(inp["blocked"])

    real_dead = set()
    planned = topology(-1)
    claims = [_key(s, H) for s in inp["sources"]]
    actions = 0
    alive_controller = True
    for t in range(T):
        if inp["crash_at"] is not None and t >= inp["crash_at"]:
            alive_controller = False
            break
        failed = history.get(t, ())
        if failed or (t == 0 and inp["blocked"]):
            new_dead = set(failed) - real_dead
            real_dead |= new_dead
            sensing = {v for u in new_dead for v in adj[u] if v not in real_dead}
            if t == 0:
                sensing |= {u for e in inp["blocked"] for u in e if u not in real_dead}
            actions += len(sensing)                                   # telemetry reports
        view = topology(t - inp["lag"])
        if view != planned:
            vdead = [False] * N
            for u in view[0]:
                vdead[u] = True
            dist, nh = _bfs_pointers(adj, vdead, set(view[1]), sinks)
            for u in range(N):
                if not vdead[u] and nh[u] != table[u]:
                    actions += 1                                      # pushed pointer (lost if the unit is gone)
                    if u not in real_dead:
                        table[u] = nh[u]
            claims = [_key(s, H) for s in inp["sources"] if not vdead[s] and dist[s] is not None]
            planned = view
    if not alive_controller:
        claims = []
    return {"next_hop": {_key(u, H): _key(v, H) for u, v in enumerate(table) if v is not None},
            "claimed": sorted(claims), "actions": actions, "steps": T}


def repair_subregion(data):
    controller = data.get("controller", {}) if isinstance(data, dict) else {}
    return "reliable_controller" if controller.get("mode", "reliable") == "reliable" else "unreliable_controller"


def _load_bearing(width, height, dead_xy, blocked_xy, sources_xy, sinks_xy):
    """Cells on the converged forwarding chains of connected sources (the generator's own BFS)."""
    dist = _reference_distances(width, height, dead_xy, blocked_xy, sinks_xy)
    used = set()
    for s in sources_xy:
        cur = s
        if cur not in dist:
            continue
        while dist[cur] > 0:
            x, y = cur
            options = sorted(c for c in ((x - 1, y), (x, y - 1), (x, y + 1), (x + 1, y))
                             if dist.get(c) == dist[cur] - 1 and frozenset((cur, c)) not in blocked_xy)
            cur = options[0]
            used.add(cur)
    return used


def repair_instance(seed):
    """TARGET_FORM_001 lattice (sealed MICA) + seeded region removal, scattered failures, the MICA route-blocking
    perturbation, mid-repair failures (half aimed at load-bearing units), message loss and a predeclared
    controller condition: even seeds reliable; odd seeds unreliable (crash with q = 0.5, else a stale view).
    Truth: coordinate BFS on the realized final topology, cross-checked against MICA's own propagation."""
    from developmental.contracts import TissueType
    from developmental.mica import MICAField

    rng = random.Random(f"genome:develop_repair:{seed}")
    T = BENCH_STEPS
    for _ in range(200):
        W, H = rng.choice((12, 14, 16)), rng.choice((10, 12))
        field = MICAField(width=W, height=H)
        field.propagate_target_field()
        original = field.local_route()
        damaged = field.clone()
        damaged.block_route(original)                                 # TARGET_FORM_001: every original edge blocked
        protected = {field.source_id, field.sink_id}

        def cid(c):
            return MICAField.cell_id(c[0], c[1])

        def tissue(kind):
            return sorted((c.x, c.y) for c in field.cells.values() if c.tissue is kind)

        transport, sensors, actuators = (tissue(TissueType.TRANSPORT), tissue(TissueType.SENSOR),
                                         tissue(TissueType.ACTUATOR))
        rw, rh = rng.randint(2, 4), rng.randint(3, H - 3)
        x0, y0 = rng.randint(2, W - 2 - rw), rng.randint(0, H - rh)
        region = {(x, y) for x in range(x0, x0 + rw) for y in range(y0, y0 + rh)}
        scattered = set(rng.sample(transport, rng.randint(3, 8)))
        sensor_loss = set(rng.sample([s for s in sensors if cid(s) not in protected], rng.randint(0, 2)))
        initial = sorted(region | scattered | sensor_loss)
        damaged.remove_cells(cid(c) for c in initial)
        blocked_xy = {frozenset(((damaged.cells[a].x, damaged.cells[a].y), (damaged.cells[b].x, damaged.cells[b].y)))
                      for a, b in damaged.blocked_edges}
        dead_xy = set(initial)
        times = sorted(rng.sample(range(round(0.15 * T), round(0.55 * T) + 1), rng.randint(1, 3)))
        events = []
        for step in times:
            live_transport = [c for c in transport if c not in dead_xy and cid(c) not in protected]
            bearing = sorted(_load_bearing(W, H, dead_xy, blocked_xy, sensors, actuators)
                             & set(live_transport))
            k = rng.randint(2, 5)
            aimed = rng.sample(bearing, min(len(bearing), (k + 1) // 2))
            rest = [c for c in live_transport if c not in aimed]
            fail = sorted(set(aimed) | set(rng.sample(rest, min(len(rest), k - len(aimed)))))
            if fail:
                events.append({"step": step, "fail": [list(c) for c in fail]})
                dead_xy |= set(fail)
        dist = _reference_distances(W, H, dead_xy, blocked_xy, actuators)
        connected = {s: dist[s] for s in sensors if s in dist}
        if connected:
            break
    else:                                                             # pragma: no cover - generator guard
        raise GenomeError("could not generate a connected repair instance")
    final = damaged.clone()
    final.remove_cells(cid(c) for c in sorted(dead_xy - set(initial)))
    final.propagate_target_field()
    mica_sink = (final.cells[final.sink_id].x, final.cells[final.sink_id].y)
    ref = _reference_distances(W, H, dead_xy, blocked_xy, [mica_sink])
    for c in final.cells.values():                                    # independent cross-check against MICA
        mine = ref.get((c.x, c.y))
        if (mine is None) != (c.potential == math.inf) or (mine is not None and mine != c.potential):
            raise GenomeError("benchmark truth disagrees with the sealed MICA propagation")
    if seed % 2 == 0:
        controller = {"mode": "reliable", "view_lag": 0, "crash_at": None}
    elif rng.random() < 0.5:
        controller = {"mode": "crash", "view_lag": 0, "crash_at": rng.randint(round(0.1 * T), round(0.5 * T))}
    else:
        controller = {"mode": "stale", "view_lag": rng.randint(round(0.3 * T), round(0.7 * T)), "crash_at": None}
    data = {"width": W, "height": H, "sources": [list(s) for s in sensors], "sinks": [list(z) for z in actuators],
            "removed": [list(c) for c in initial],
            "blocked": sorted([sorted([list(c) for c in e]) for e in blocked_xy]),
            "events": events, "steps": T, "message_loss": rng.choice((0.0, 0.1, 0.2, 0.3)),
            "seed": rng.randrange(SEED_MAX), "controller": controller, "action_cost": ACTION_COST}
    truth = {"distances": {f"{x},{y}": d for (x, y), d in sorted(connected.items())},
             "unreachable_sources": sorted(f"{x},{y}" for x, y in sensors if (x, y) not in connected),
             "method": "coordinate BFS from the sink region on the realized final topology; MICA propagation "
                       "cross-check passed"}
    return data, truth


# ============================================================================ 2. constraint-release recombination
CONSTRUCTORS = ("edd", "wspt", "slack", "wmdd", "atc:0.5", "atc:1", "atc:2", "atc:4")
IMPROVERS = tuple(f"swap:{nbr}:{acc}" for nbr in ("adj", "any") for acc in ("first", "best")) + tuple(
    f"insert:{nbr}:{acc}" for nbr in ("2", "4", "all") for acc in ("first", "best"))
ORIGINAL_PIPELINE = ("atc:2", "swap:adj:first", "insert:2:first")
MAX_PIPELINE = 5
MU, LAMBDA = 4, 4
TOP_VALIDATED = 3
RETAIN_MARGIN = 0.001          # retained only if validation utility beats the original by > 0.1% (relative)
CR_MAX_JOBS = 30
CR_NATIVE_JOBS = 12
CR_MAX_CASES = 40
CR_MAX_BUDGET = 200
CR_BENCH_BUDGET = 36


def _cases(value, name):
    if not isinstance(value, list) or not 1 <= len(value) <= CR_MAX_CASES:
        raise GenomeError(f"{name}: list of 1-{CR_MAX_CASES} cases required")
    out = []
    for case in value:
        if not isinstance(case, dict) or set(case) != {"p", "w", "d"}:
            raise GenomeError(f"{name}: a case is {{p, w, d}}")
        p, w, d = case["p"], case["w"], case["d"]
        if not all(isinstance(v, list) for v in (p, w, d)) or not 2 <= len(p) <= CR_MAX_JOBS \
                or not len(p) == len(w) == len(d):
            raise GenomeError(f"{name}: p, w, d are equal-length lists of 2-{CR_MAX_JOBS} jobs")
        out.append((tuple(bounded_int(v, low=1, high=10_000, name="p") for v in p),
                    tuple(bounded_int(v, low=1, high=1_000, name="w") for v in w),
                    tuple(bounded_int(v, low=0, high=10 ** 6, name="d") for v in d)))
    return out


def _check_config(config):
    if (not isinstance(config, (list, tuple)) or not 1 <= len(config) <= MAX_PIPELINE
            or config[0] not in CONSTRUCTORS or any(op not in IMPROVERS for op in config[1:])):
        raise GenomeError(f"configuration is [constructor] + up to {MAX_PIPELINE - 1} improvers from the "
                          "declared operator library")
    return tuple(config)


def _cr_inputs(data):
    _require_dict(data)
    train = _cases(data.get("train"), "train")
    validation = _cases(data.get("validation"), "validation")
    budget = bounded_int(data.get("budget", CR_BENCH_BUDGET), low=1, high=CR_MAX_BUDGET, name="budget")
    seed = bounded_int(data.get("seed", 0), low=0, high=SEED_MAX, name="seed")
    original = _check_config(data.get("pipeline", list(ORIGINAL_PIPELINE)))
    return train, validation, budget, seed, original


def _twt(seq, case):
    p, w, d = case
    t = total = 0
    for j in seq:
        t += p[j]
        if t > d[j]:
            total += w[j] * (t - d[j])
    return total


def _construct(rule, case):
    p, w, d = case
    jobs = range(len(p))
    if rule == "edd":
        return sorted(jobs, key=lambda j: (d[j], j))
    if rule == "wspt":
        return sorted(jobs, key=lambda j: (p[j] / w[j], j))
    if rule == "slack":
        return sorted(jobs, key=lambda j: (d[j] - p[j], j))
    rest, seq, t = list(jobs), [], 0
    if rule == "wmdd":                                            # Kanet & Li (2004) weighted modified due date
        while rest:
            j = min(rest, key=lambda j: (max(p[j], d[j] - t) / w[j], j))
            rest.remove(j)
            seq.append(j)
            t += p[j]
        return seq
    k = float(rule.split(":")[1])                                  # ATC: Vepsalainen & Morton (1987)
    pbar = sum(p) / len(p)
    while rest:
        j = max(rest, key=lambda j: ((w[j] / p[j]) * math.exp(-max(d[j] - p[j] - t, 0) / (k * pbar)), -j))
        rest.remove(j)
        seq.append(j)
        t += p[j]
    return seq


def _moves(kind, nbr, n):
    if kind == "swap":
        return [(i, i + 1) for i in range(n - 1)] if nbr == "adj" else [
            (i, j) for i in range(n) for j in range(i + 1, n)]
    window = n if nbr == "all" else int(nbr)
    return [(i, j) for i in range(n) for j in range(n) if i != j and abs(i - j) <= window]


def _apply(kind, seq, i, j):
    s = list(seq)
    if kind == "swap":
        s[i], s[j] = s[j], s[i]
    else:
        s.insert(j, s.pop(i))
    return s


def _improve(op, seq, case):
    kind, nbr, acc = op.split(":")
    cur, cost = list(seq), _twt(seq, case)
    if acc == "first":                                            # one sweep, accept every improving move
        for i, j in _moves(kind, nbr, len(cur)):
            cand = _apply(kind, cur, i, j)
            c = _twt(cand, case)
            if c < cost:
                cur, cost = cand, c
        return cur
    best, best_cost = None, cost                                   # one sweep, apply the single best move
    for i, j in _moves(kind, nbr, len(cur)):
        cand = _apply(kind, cur, i, j)
        c = _twt(cand, case)
        if c < best_cost:
            best, best_cost = cand, c
    return best if best is not None else cur


def run_pipeline(config, case):
    """Execute a configuration (constructor, then improvers in order) on one case -> job sequence."""
    seq = _construct(config[0], case)
    for op in config[1:]:
        seq = _improve(op, seq, case)
    return seq


def _utility(config, cases):
    """Mean weighted tardiness normalised by sum(w * p) per case (lower is better)."""
    return sum(_twt(run_pipeline(config, c), c) / sum(pi * wi for pi, wi in zip(c[0], c[1])) for c in cases) / len(
        cases)


class _Search:
    """Bounded evaluation accounting shared by the candidate and the random-restart competitor."""

    def __init__(self, train, budget):
        self.train, self.budget, self.cache, self.order = train, budget, {}, []

    def evaluate(self, config):
        if config in self.cache:
            return self.cache[config]
        if len(self.cache) >= self.budget:
            return None
        self.cache[config] = _utility(config, self.train)
        self.order.append(config)
        return self.cache[config]


def _mutate(config, rng):
    head, imps = config[0], list(config[1:])
    kinds = ["constructor"]
    if len(imps) >= 2:
        kinds.append("reorder")
    if imps:
        kinds += ["drop", "rule"]
    if len(imps) < MAX_PIPELINE - 1:
        kinds.append("add")
        if imps:
            kinds.append("duplicate")
    kind = rng.choice(kinds)
    if kind == "reorder":
        i, j = rng.sample(range(len(imps)), 2)
        imps[i], imps[j] = imps[j], imps[i]
        note = f"reorder({i},{j})"
    elif kind == "drop":
        i = rng.randrange(len(imps))
        note = f"drop({imps.pop(i)})"
    elif kind == "add":
        i, op = rng.randrange(len(imps) + 1), rng.choice(IMPROVERS)
        imps.insert(i, op)
        note = f"add({op}@{i})"
    elif kind == "duplicate":
        i = rng.randrange(len(imps))
        imps.insert(i, imps[i])
        note = f"duplicate({imps[i]})"
    elif kind == "rule":                                           # alter one operator's neighbour / acceptance rule
        i = rng.randrange(len(imps))
        fam, nbr, acc = imps[i].split(":")
        variants = [op for op in IMPROVERS if op != imps[i] and (op.split(":")[0] == fam or op.split(":")[2] == acc)]
        new = rng.choice(variants)
        note = f"rule({imps[i]}->{new})"
        imps[i] = new
    else:
        new = rng.choice([c for c in CONSTRUCTORS if c != head])
        note = f"constructor({head}->{new})"
        head = new
    return (head,) + tuple(imps), note


def _recombine(a, b, rng):
    ia, ib = list(a[1:]), list(b[1:])
    cut_a, cut_b = rng.randint(0, len(ia)), rng.randint(0, len(ib))
    imps = (ia[:cut_a] + ib[cut_b:])[:MAX_PIPELINE - 1]
    head = rng.choice((a[0], b[0]))
    return (head,) + tuple(imps), f"recombine(a[:{cut_a}]+b[{cut_b}:])"


def _validate_and_retain(search, validation, original):
    """Top candidates by training utility are measured on validation; retain only a strict improvement."""
    ranked = sorted((c for c in search.cache if c != original), key=lambda c: (search.cache[c], len(c), c))
    shortlist = ranked[:TOP_VALIDATED]
    orig_val = _utility(original, validation)
    measured = [(c, _utility(c, validation)) for c in shortlist]
    best = min(measured, key=lambda cv: (cv[1], len(cv[0]), cv[0]), default=None)
    retained = best is not None and best[1] < orig_val * (1 - RETAIN_MARGIN)
    return (best[0] if retained else original), retained, orig_val, (best[1] if retained else orig_val), measured


def _cr_output(config, retained, val_u, orig_val_u, lineage, evaluations):
    return {"configuration": list(config), "retained": retained, "validation_utility": val_u,
            "original_validation_utility": orig_val_u, "lineage": lineage, "evaluations": evaluations,
            "authority": "none: a configuration is a proposal, never an installed or activated capability"}


def constraint_release_solve(data, budget):
    train, validation, eval_budget, seed, original = _cr_inputs(data)
    n_max = max(len(c[0]) for c in train + validation)
    if len(train) < 4 or len(validation) < 4:
        return answer(None, {"train": len(train), "validation": len(validation)}, status="ABSTAIN",
                      missing=["at least 4 training and 4 validation cases are needed to select without "
                               "overfitting"])
    if eval_budget < MU + LAMBDA:
        return answer(None, {"budget": eval_budget}, status="ABSTAIN",
                      missing=[f"evaluation budget below one generation ({MU + LAMBDA})"])
    if n_max > CR_NATIVE_JOBS:
        return answer(None, {"jobs": n_max}, status="ABSTAIN",
                      missing=[f"more than {CR_NATIVE_JOBS} jobs per case: outside the validated toy size"])
    rng = random.Random(f"constraint_release:{seed}")
    search = _Search(train, eval_budget)
    individuals = {original: {"id": 0, "parents": [], "mutations": ["original pipeline (validated, fixed order)"]}}
    search.evaluate(original)
    population = [original]
    generations, stall = [], 0
    while len(search.cache) < eval_budget and stall < 50:
        offspring = []
        for _ in range(LAMBDA):
            def pick():
                a, b = rng.choice(population), rng.choice(population)
                return min((a, b), key=lambda c: (search.cache[c], len(c), c))
            if len(population) >= 2 and rng.random() < 0.3:
                pa, pb = pick(), pick()
                child, note = _recombine(pa, pb, rng)
                parents = [pa, pb]
                notes = [note]
                if rng.random() < 0.5:
                    child, extra = _mutate(child, rng)
                    notes.append(extra)
            else:
                pa = pick()
                child, note = _mutate(pa, rng)
                parents, notes = [pa], [note]
                if rng.random() < 0.3:
                    child, extra = _mutate(child, rng)
                    notes.append(extra)
            if child in search.cache or len(search.cache) >= eval_budget:
                stall += 1
                continue
            search.evaluate(child)
            individuals[child] = {"id": len(individuals), "parents": [individuals[p]["id"] for p in parents],
                                  "mutations": notes}
            offspring.append(child)
            stall = 0
        population = sorted(set(population) | set(offspring), key=lambda c: (search.cache[c], len(c), c))[:MU]
        if offspring:
            generations.append({"generation": len(generations) + 1, "evaluations": len(search.cache),
                                "best_train_utility": round(search.cache[population[0]], 12)})
    config, retained, orig_val, val_u, measured = _validate_and_retain(search, validation, original)
    by_id = {v["id"]: (c, v) for c, v in individuals.items()}
    wanted, frontier = set(), [individuals[config]["id"]]
    while frontier:
        i = frontier.pop()
        if i not in wanted:
            wanted.add(i)
            frontier.extend(by_id[i][1]["parents"])
    # The full ancestor closure (<= budget <= 200 entries): truncating it would drop the root and parents and
    # make the independent verifier refute a valid answer.
    lineage = [{"id": i, "config": list(by_id[i][0]), "parents": by_id[i][1]["parents"],
                "mutations": by_id[i][1]["mutations"], "train_utility": search.cache[by_id[i][0]]}
               for i in sorted(wanted)]
    certificate = {
        "mechanism": "(mu + lambda) evolutionary recombination of released pipeline operators; retain-or-extinct "
                     "against the original on the validation split",
        "seed": seed, "budget": eval_budget, "evaluations": len(search.cache), "mu": MU, "lambda": LAMBDA,
        "retain_margin": RETAIN_MARGIN, "generations": generations[:200],
        "original": {"config": list(original), "train_utility": search.cache[original],
                     "validation_utility": orig_val},
        "validated": [{"config": list(c), "train_utility": search.cache[c], "validation_utility": v}
                      for c, v in measured],
        "extinct": len(search.cache) - (2 if retained else 1),
        "validation_schedules": [run_pipeline(config, c) for c in validation],
        "authority": "none"}
    return answer(_cr_output(config, retained, val_u, orig_val, lineage, len(search.cache)), certificate)


def _tardiness_check(seq, case):
    """Verifier's own objective: completion times by prefix sums, then weighted lateness clipped at zero."""
    p, w, d = case
    completion, acc = {}, 0
    for j in seq:
        acc += p[j]
        completion[j] = acc
    return sum(w[j] * max(0, completion[j] - d[j]) for j in completion)


def _is_permutation(seq, n):
    return isinstance(seq, list) and sorted(seq) == list(range(n)) and all(type(j) is int for j in seq)


def constraint_release_verify(data, output, certificate):
    train, validation, _, _, original = _cr_inputs(data)
    if not isinstance(output, dict):
        return {"output_shape": False}
    try:
        config = _check_config(output.get("configuration"))
    except GenomeError:
        return {"configuration_well_formed": False}
    schedules = [run_pipeline(config, c) for c in validation]       # replay the returned configuration
    perms = all(_is_permutation(s, len(c[0])) for s, c in zip(schedules, validation))

    def util(scheds):
        return sum(_tardiness_check(s, c) / sum(a * b for a, b in zip(c[0], c[1]))
                   for s, c in zip(scheds, validation)) / len(validation)

    val_u = util(schedules)
    orig_u = util([run_pipeline(original, c) for c in validation])
    claimed_v, claimed_o = output.get("validation_utility"), output.get("original_validation_utility")
    claims_ok = (isinstance(claimed_v, (int, float)) and isinstance(claimed_o, (int, float))
                 and math.isclose(claimed_v, val_u, rel_tol=1e-9, abs_tol=1e-12)
                 and math.isclose(claimed_o, orig_u, rel_tol=1e-9, abs_tol=1e-12))
    retained = output.get("retained")
    rule_ok = retained is (val_u < orig_u * (1 - RETAIN_MARGIN)) and (retained or config == original)
    lineage = output.get("lineage")
    lineage_ok = isinstance(lineage, list) and bool(lineage)
    if lineage_ok:
        ids = set()
        for entry in lineage:
            if (not isinstance(entry, dict) or type(entry.get("id")) is not int
                    or not isinstance(entry.get("parents"), list)
                    or any(type(p) is not int or p not in ids for p in entry["parents"])):
                lineage_ok = False
                break
            ids.add(entry["id"])
        lineage_ok = (lineage_ok and lineage[0].get("parents") == [] and lineage[0].get("config") == list(original)
                      and lineage[-1].get("config") == list(config))
    cert_scheds = certificate.get("validation_schedules") if isinstance(certificate, dict) else None
    cert_ok = (isinstance(cert_scheds, list) and len(cert_scheds) == len(validation)
               and all(_is_permutation(s, len(c[0])) for s, c in zip(cert_scheds, validation))
               and math.isclose(util(cert_scheds), val_u, rel_tol=1e-9, abs_tol=1e-12))
    return {"configuration_well_formed": True, "schedules_are_permutations": perms,
            "validation_claims_recomputed": claims_ok, "retain_or_extinct_rule_obeyed": rule_ok,
            "lineage_roots_at_original_and_ends_at_output": lineage_ok,
            "certificate_schedules_match_objective": cert_ok,
            "no_authority_claimed": isinstance(output.get("authority"), str)
            and output["authority"].startswith("none")}


def _twt_optimum(case):
    """Exact minimum total weighted tardiness by dynamic programming over job subsets (n <= 12)."""
    p, w, d = case
    n = len(p)
    size = 1 << n
    load = [0] * size
    for s in range(1, size):
        low = s & -s
        load[s] = load[s ^ low] + p[low.bit_length() - 1]
    best = [0] * size
    for s in range(1, size):
        t, value, rest = load[s], None, s
        while rest:
            low = rest & -rest
            j = low.bit_length() - 1
            v = best[s ^ low] + w[j] * max(0, t - d[j])
            if value is None or v < value:
                value = v
            rest ^= low
        best[s] = value
    return best[size - 1]


def constraint_release_score(data, truth, output):
    if not isinstance(output, dict) or "configuration" not in output:
        return {"quality": -1.0, "category": "abstain"}
    train, validation, _, _, original = _cr_inputs(data)
    try:
        config = _check_config(output["configuration"])
    except GenomeError:
        return {"quality": -2.0, "category": "wrong"}
    gaps = []
    for case, opt in zip(truth["test"], truth["optimum"]):
        c = (tuple(case["p"]), tuple(case["w"]), tuple(case["d"]))
        cost = _tardiness_check(run_pipeline(config, c), c)
        norm = sum(a * b for a, b in zip(c[0], c[1])) / len(c[0])
        gaps.append((cost - opt) / (opt + norm))
    quality = -sum(gaps) / len(gaps)
    # a false answer: claims the validation split does not support, or a retention the rule forbids
    val_u = _utility(config, validation)
    orig_u = _utility(original, validation)
    claims_ok = (isinstance(output.get("validation_utility"), (int, float))
                 and math.isclose(output["validation_utility"], val_u, rel_tol=1e-9, abs_tol=1e-12)
                 and output.get("retained") is (val_u < orig_u * (1 - RETAIN_MARGIN))
                 and (output.get("retained") or config == original))
    if not claims_ok:                     # quality <= 0, so a false claim is always strictly below abstaining (-1)
        return {"quality": quality - 1.5, "category": "wrong"}
    return {"quality": quality, "category": "correct"}


def constraint_release_original(data):
    """Baseline: the original fixed pipeline, unchanged."""
    train, validation, _, _, original = _cr_inputs(data)
    u = _utility(original, validation)
    root = [{"id": 0, "config": list(original), "parents": [], "mutations": ["original pipeline"],
             "train_utility": _utility(original, train)}]
    return _cr_output(original, False, u, u, root, 1)


def constraint_release_random_restart(data):
    """Competitor: random-restart configuration search, same evaluation budget and retain rule."""
    train, validation, eval_budget, seed, original = _cr_inputs(data)
    rng = random.Random(f"random_restart:{seed}")
    search = _Search(train, eval_budget)
    search.evaluate(original)
    tries = 0
    while len(search.cache) < eval_budget and tries < 20 * eval_budget:
        tries += 1
        config = (rng.choice(CONSTRUCTORS),) + tuple(rng.choice(IMPROVERS)
                                                      for _ in range(rng.randint(0, MAX_PIPELINE - 1)))
        search.evaluate(config)
    config, retained, orig_val, val_u, _ = _validate_and_retain(search, validation, original)
    lineage = [{"id": 0, "config": list(original), "parents": [], "mutations": ["original pipeline"],
                "train_utility": search.cache[original]}]
    if retained:
        lineage.append({"id": search.order.index(config), "config": list(config), "parents": [],
                        "mutations": ["random restart"], "train_utility": search.cache[config]})
    return _cr_output(config, retained, val_u, orig_val, lineage, len(search.cache))


def constraint_release_subregion(data):
    """tight_due_dates: mean training tardiness factor 1 - mean(d)/sum(p) >= 0.5."""
    cases = data.get("train", []) if isinstance(data, dict) else []
    factors = [1 - (sum(c["d"]) / len(c["d"])) / sum(c["p"]) for c in cases if c.get("p")]
    tau = sum(factors) / len(factors) if factors else 0.0
    return "tight_due_dates" if tau >= 0.5 else "loose_due_dates"


def constraint_release_instance(seed):
    """Seeded instance family (Potts & Van Wassenhove due-date generator, tardiness factor tau and range R;
    uniform or bimodal processing times): 10 training, 10 validation and 16 held-out test cases of 10 jobs.
    Truth: exact optimum of every test case by subset dynamic programming."""
    rng = random.Random(f"genome:develop_constraint_release:{seed}")
    tau, spread = rng.choice((0.2, 0.4, 0.6, 0.8)), rng.choice((0.2, 0.6, 1.0))
    shape = rng.choice(("uniform", "bimodal"))
    n = 10

    def case():
        if shape == "uniform":
            p = [rng.randint(1, 100) for _ in range(n)]
        else:
            p = [rng.randint(1, 20) if rng.random() < 0.7 else rng.randint(60, 100) for _ in range(n)]
        w = [rng.randint(1, 10) for _ in range(n)]
        total = sum(p)
        lo, hi = total * (1 - tau - spread / 2), total * (1 - tau + spread / 2)
        d = [max(0, round(rng.uniform(lo, hi))) for _ in range(n)]
        return {"p": p, "w": w, "d": d}

    train = [case() for _ in range(10)]
    validation = [case() for _ in range(10)]
    test = [case() for _ in range(16)]
    data = {"train": train, "validation": validation, "budget": CR_BENCH_BUDGET,
            "seed": rng.randrange(SEED_MAX), "pipeline": list(ORIGINAL_PIPELINE)}
    truth = {"test": test, "optimum": [_twt_optimum((tuple(c["p"]), tuple(c["w"]), tuple(c["d"]))) for c in test],
             "family": {"tau": tau, "R": spread, "processing_times": shape},
             "method": "exact subset dynamic programming per held-out case"}
    return data, truth


# ============================================================================ genomes
def _genome(**kw):
    return IntelligenceGenome(layer=4, buildability="BUILDABLE_NOW", lineage=LINEAGE, version="1.0.0", **kw)


FRONTIER = ("frontier NOT achieved: robust unscripted organ formation",
            "frontier NOT achieved: generalized repair across domains",
            "frontier NOT achieved: cross-substrate developmental compilation")

INTELLIGENCES = [
    Executable(
        genome=_genome(
            intelligence_id="developmental.repair.sequenced_local_gradient", family="develop_repair",
            operation="target_state_repair",
            # physical, not optimization: the answer is the state a damaged distributed substrate reaches under a
            # disturbance process, judged against the realized world, not the optimum of a declared objective.
            epistemic_class="physical",
            subgeometry="hold a source-region -> sink-region transport target on a damaged 4-neighbour lattice "
                        "under region removal, unit failures, link blocking, mid-repair failures and lossy "
                        "neighbour messages, within a step budget",
            source_provenance="sealed MICA/CDPE TARGET_FORM_001 laboratory (developmental/, imported unmodified); "
                              "DSDV (Perkins & Bhagwat 1994); Babel feasibility condition (RFC 8966); gradient "
                              "self-repair in amorphous computing (Nagpal; Beal & Bachrach)",
            native_representation="lattice width/height + source and sink cells + removed cells + blocked edges "
                                  "+ scheduled failure events + step budget + message loss + seed",
            required_inputs=("width", "height", "sources", "sinks", "removed", "blocked", "events", "steps",
                             "message_loss", "seed"),
            output_contract={"next_hop": "{'x,y': 'x,y'} forwarding pointer of every functioning unit",
                             "claimed": "[source keys the local rules vouch for]",
                             "actions": "int unit-actions (messages sent)", "steps": "int"},
            algorithm_or_runtime="sandboxed step simulation of per-unit local rules: sequence-numbered potential "
                                 "waves from the sink region, feasibility-guarded adoption, retraction on link "
                                 "loss, repeated broadcast of changes, expiry-bounded vouching",
            parameters={"wave_period": WAVE_PERIOD, "expiry_waves": EXPIRY_WAVES, "repeats": REPEATS,
                        "max_message_loss": MAX_LOSS, "action_cost": ACTION_COST, "wrong_penalty": WRONG_PENALTY},
            memory_model="per-unit soft state (sequence, potential, feasibility distance, neighbour cache) inside "
                         "one call; nothing persists",
            learning_rule="none; competence settles per geometry from receipts",
            composition_inputs=("damaged_topology", "disturbance_schedule"),
            composition_outputs=("forwarding_field", "restoration_claims"),
            evidence_type="developmental_trace",
            verification_method="independent: rebuild the realized final topology from the world script, check "
                                "every pointer is a lattice edge between functioning units over an unblocked "
                                "link, follow every claimed source's chain to the sink region without loops, "
                                "match the action count to the per-step trace",
            confidence_semantics="a claim means a sink wave refreshed that source's route within the expiry window "
                                 "of the declared simulation; it is not a physical probe",
            resource_profile="O(steps x units x 4) pure Python; <= 200 units, <= 400 steps",
            latency_profile="tens of milliseconds",
            known_strengths=("no coordinator to crash or go stale: repair continues under controller failure",
                             "loop-free forwarding at every step (feasibility condition)",
                             "honest vouching: unrefreshed routes are not claimed",
                             "zero false restoration claims on the development benchmark"),
            known_failure_modes=("a reliable, fresh central replanner restores exactly with far fewer messages "
                                 "and beats it on every reliable-controller instance",
                                 "claims can be false if a failure lands inside the final expiry window",
                                 "lossy waves can settle on longer-than-shortest routes",
                                 "message cost scales with the wave rate even when nothing is damaged",
                                 "a hybrid (central plan plus this local fallback) is the obvious stronger "
                                 "design and is not evaluated here") + FRONTIER,
            counterindications=("a reliable, fresh central controller is available (use it)",
                                "message loss above 0.5", "failures expected inside the final expiry window",
                                "substrates without local link sensing or neighbour-only messaging") + FRONTIER,
            abstention_conditions=("step budget below (expiry_waves + 1) x wave_period + 2 x (width + height)",
                                   "message loss above 0.5", "no functioning source or sink at the start"),
            benchmark_suite="TARGET_FORM_001 lattices 12-16 x 10-12 (sealed MICA): seeded region removal, scattered "
                            "failures, route blocking, 1-3 mid-repair failure events (half aimed at load-bearing "
                            "units) in steps 18-66 of 120, message loss 0-0.3; even seeds reliable controller, odd "
                            "seeds unreliable (crash q = 0.5, else 36-84-step stale view); quality = efficiency-"
                            "weighted restored fraction - action cost, false claim -1.5; dev 0-9, held-out "
                            "1000-1029",
            baseline="no repair: keep the pre-damage forwarding field, act never, claim nothing",
            competitor="adaptive centralized replanner: global BFS shortest-path rebuild on its view at every "
                       "change, reliable pushes; reliable or predeclared-unreliable (crash / stale view)"),
        solve=repair_solve, verify=repair_verify, instance=repair_instance, score=repair_score,
        baseline=repair_no_repair, competitor=repair_central_replanner, subregion=repair_subregion, tolerance=1e-9,
        notes={"expected": "the reliable centralized replanner wins every reliable_controller instance (exact "
                           "repair, fewer unit-actions); the local rules only earn a place where the controller "
                           "is unreliable, and only if they never claim a collapsed route",
               "mica_reuse": "MICAField builds the lattice, tissues and the route-blocking perturbation and "
                             "cross-checks the truth; developmental/ is never modified"}),
    Executable(
        genome=_genome(
            intelligence_id="developmental.release.recombine_pipeline", family="develop_constraint_release",
            operation="release_recombine_pipeline", epistemic_class="optimization",
            subgeometry="re-order, re-wire and recombine validated heuristic operators of a fixed pipeline for an "
                        "instance family of single-machine total-weighted-tardiness cases (<= 12 jobs)",
            source_provenance="ATC (Vepsalainen & Morton 1987); WMDD (Kanet & Li 2004); pairwise interchange and "
                              "insertion local search; Potts & Van Wassenhove (1985) due-date generator; "
                              "(mu + lambda) evolution strategies; hyper-heuristic pipeline search",
            native_representation="training and validation cases {p, w, d} + evaluation budget + seed + the "
                                  "original validated pipeline",
            required_inputs=("train", "validation", "budget", "seed"),
            output_contract={"configuration": "[constructor, improver...]", "retained": "bool",
                             "validation_utility": "float", "original_validation_utility": "float",
                             "lineage": "[{id, config, parents, mutations, train_utility}]",
                             "evaluations": "int", "authority": "str (none)"},
            algorithm_or_runtime="seeded (mu=4 + lambda=4) evolution over pipelines with release mutations "
                                 "(reorder, drop, add, duplicate, neighbour/acceptance rule change, constructor "
                                 "change) and cut-and-splice recombination; top 3 by training utility measured "
                                 "on validation; retain only a > 0.1% validation improvement over the original",
            parameters={"mu": MU, "lambda": LAMBDA, "top_validated": TOP_VALIDATED, "retain_margin": RETAIN_MARGIN,
                        "max_pipeline": MAX_PIPELINE, "benchmark_budget": CR_BENCH_BUDGET},
            memory_model="evaluation cache and lineage inside one call; nothing persists",
            learning_rule="selection on training utility, retention on validation utility",
            composition_inputs=("operator_library", "instance_family_sample"),
            composition_outputs=("retained_configuration", "lineage"),
            evidence_type="heuristic_trace",
            verification_method="independent: replay the returned configuration and the original on the "
                                "validation split, recompute weighted tardiness with separate objective code, "
                                "check the retain-or-extinct rule and that the lineage roots at the original and "
                                "ends at the output; the search itself is never re-run",
            confidence_semantics="a retained configuration beat the original on this instance's validation split; "
                                 "it is a heuristic, not an optimality proof",
            resource_profile="budget x training cases x pipeline sweeps of O(n^2) moves x O(n) objective",
            latency_profile="tens of milliseconds at the benchmark budget (36 evaluations, 10 cases of 10 jobs); "
                            "about 2 s at the input ceiling (200 evaluations, 40 cases of 12 jobs)",
            known_strengths=("never worse than the original on validation by construction (extinct otherwise)",
                             "lineage makes every retained change auditable",
                             "adapts operator order to the instance family's due-date tightness"),
            known_failure_modes=("overfitting: a configuration can win validation and lose on held-out cases",
                                 "random restart with the same budget can match or beat it in this small space",
                                 "improvements are often just 'more local search', not new structure",
                                 "toy scale only (<= 12 jobs)") + FRONTIER,
            counterindications=("problems with an exact polynomial algorithm (use it)",
                                "fewer than 4 training or validation cases", "more than 12 jobs per case") + FRONTIER,
            abstention_conditions=("fewer than 4 training or 4 validation cases",
                                   "evaluation budget below one generation (8)",
                                   "more than 12 jobs per case"),
            benchmark_suite="seeded tardiness families (tau 0.2-0.8, R 0.2-1.0, uniform or bimodal p), 10 train / "
                            "10 validation / 16 held-out cases of 10 jobs, budget 36 evaluations; quality = - mean "
                            "normalised gap to the exact DP optimum, abstain -1, false validation/retention claim "
                            "-1.5; dev 0-9, held-out 1000-1029",
            baseline="the original fixed pipeline ATC(k=2) -> adjacent swap -> insert(window 2)",
            competitor="random-restart configuration search with the same evaluation budget and retain rule"),
        solve=constraint_release_solve, verify=constraint_release_verify, instance=constraint_release_instance,
        score=constraint_release_score, baseline=constraint_release_original,
        competitor=constraint_release_random_restart, subregion=constraint_release_subregion, tolerance=1e-9,
        notes={"authority": "a retained configuration is a proposal only; building != installation != activation"}),
]
