"""Layer 2 distributed / collective intelligence: practical mechanisms named after collective systems.

Founder rule (INTENT-0030, INTENT-20261007-POLYINTELLIGENCE-MIND-CONTINUATION): preserve the effect, do not
literalize the metaphor. Every name below labels a computational mechanism; nothing here claims biological
equivalence, life, consciousness or general intelligence, and nothing carries authority (read-only).

* ``collective_quorum`` (operation ``quorum_cross_inhibition``): correlated observers vote among alternatives.
  Each independence group contributes ONE log-likelihood term computed under its declared shared-noise
  mixture (a correlated faction counts roughly once, not once per member); alternatives cross-inhibit (each
  alternative's support is its accumulated evidence minus the log-sum of its competitors', the normalisation
  a leaky competing accumulator approaches at its optimal inhibition); the colony commits when the leader's
  support crosses the quorum, else abstains.
* ``collective_aco`` (operation ``ant_colony_tour``): MAX-MIN Ant System for the symmetric Euclidean TSP
  (<= 40 cities): probabilistic tour construction from pheromone x heuristic, evaporation, iteration-best /
  global-best reinforcement with trail limits, and 2-opt on the iteration-best ant (the standard hybrid).
* ``collective_physarum`` (operation ``conductance_network_design``): the Tero adaptive-network model
  (conductances reinforced by Kirchhoff flux, decaying otherwise) on a candidate graph; tube networks
  extracted at several feedback exponents and thresholds are repaired, pruned and scored on the
  predeclared cost + fault-tolerance objective.
* ``collective_immune`` (operation ``negative_selection_detect``): real-valued negative selection
  (V-detectors): candidate detectors (uniform in the modelled universe plus Gaussian draws around the self
  region) are censored against self (each covers up to its distance from self); the self radius is set by
  3-fold cross-fitted conformal calibration to 0.75 x the declared false-alarm tolerance. Every flag carries
  a self-tolerant witness detector. Its score is a covered lower bound on distance-to-self.
* ``collective_market`` (operation ``clock_auction_allocate``): ascending clock auction (tatonnement)
  with a reserve price and a capacity, price-taking agents that reveal only demand at a quoted price, and
  bisection refinement of the clearing bracket. The clearing price is a dual certificate: the verifier
  checks the competitive-equilibrium conditions from the agents' values.
* ``collective_flock`` (operation ``flock_navigate``): local rules (goal seeking, a clearance bubble around
  sensed neighbours, crowd avoidance and a shared right-hand convention) move discs to their goals in a
  bounded 2-D kinematic simulation; contact and non-arrival are audited in continuous time, never hidden.

Independent verification never reuses the solver's code path (recomputed lengths, union-find connectivity,
probability-space posteriors, equilibrium inequalities, witness-detector geometry, continuous-time kinematic
audit). Benchmark truth never runs a candidate's code (Held-Karp / a self-contained reference search, generator
ground truth, dynamic programming, analytic makespan bounds).
"""
from __future__ import annotations

from bisect import bisect_left
import heapq
import json
import math
import random
import statistics

from .contract import Executable, GenomeError, IntelligenceGenome, answer, bounded_int, finite

LINEAGE = ("INTENT-20261007-POLYINTELLIGENCE-MIND-CONTINUATION", "INTENT-20261007-VERIFIED-POLYINTELLIGENCE-LIFT",
           "INTENT-0030 effect-not-metaphor", "greg/cognition/solvers.py quorum (collective family, Layer 2 lineage)")
SEED_MAX = 2 ** 31 - 1


def _require_dict(data):
    if not isinstance(data, dict):
        raise GenomeError("data must be an object")
    return data


def _seed(data):
    return bounded_int(data.get("seed", 0), low=0, high=SEED_MAX, name="seed")


def _point(p, dim, name):
    if not isinstance(p, list) or len(p) != dim:
        raise GenomeError(f"{name}: list of {dim} finite numbers required")
    return tuple(finite(v, low=-1e6, high=1e6, name=name) for v in p)


# ============================================================================ 1. quorum + cross-inhibition
def _quorum_inputs(data):
    _require_dict(data)
    alts = data.get("alternatives")
    if (not isinstance(alts, list) or not 2 <= len(alts) <= 8
            or not all(isinstance(a, str) and 1 <= len(a) <= 64 for a in alts) or len(set(alts)) != len(alts)):
        raise GenomeError("2-8 distinct alternative labels required")
    observers = data.get("observers")
    if not isinstance(observers, list) or not 1 <= len(observers) <= 200:
        raise GenomeError("1-200 observers required")
    rows, seen = [], set()
    for o in observers:
        if not isinstance(o, dict):
            raise GenomeError("observer is {observer_id, group, accuracy, vote}")
        oid, group, vote = o.get("observer_id"), o.get("group"), o.get("vote")
        if not isinstance(oid, str) or not 1 <= len(oid) <= 64 or oid in seen:
            raise GenomeError("observer ids must be unique strings of 1-64 characters")
        if not isinstance(group, str) or not 1 <= len(group) <= 64:
            raise GenomeError("every observer declares an independence group (1-64 characters)")
        if vote not in alts:
            raise GenomeError("vote must be a declared alternative")
        rows.append((oid, group, finite(o.get("accuracy"), low=0.01, high=0.99, name="accuracy"), vote))
        seen.add(oid)
    groups = data.get("groups", {})
    if not isinstance(groups, dict) or len(groups) > 200:
        raise GenomeError("groups maps at most 200 groups -> {shared_noise}")
    rho = {}
    for g, spec in groups.items():
        if not isinstance(spec, dict):
            raise GenomeError("group declaration is {shared_noise}")
        rho[g] = finite(spec.get("shared_noise"), low=0.0, high=0.99, name="shared_noise")
    quorum = finite(data.get("quorum", 0.5), low=0.5, high=0.999, name="quorum")
    minimum = bounded_int(data.get("minimum_independent", 3), low=1, high=100, name="minimum_independent")
    return alts, rows, rho, quorum, minimum


def _groups_in_order(rows):
    order, members = [], {}
    for oid, g, acc, vote in rows:
        if g not in members:
            order.append(g)
            members[g] = []
        members[g].append((oid, acc, vote))
    return order, members


def _logsumexp(values):
    m = max(values)
    if m == -math.inf:
        return -math.inf
    return m + math.log(sum(math.exp(v - m) for v in values))


def _group_loglik(members, alts, rho):
    """log P(group's votes | truth = a) under the declared mixture: with probability rho the whole group
    copies one shared signal (correct with the members' mean accuracy), otherwise members vote independently."""
    k = len(alts)
    q = sum(acc for _, acc, _ in members) / len(members)
    votes = {v for *_, v in members}
    out = {}
    for a in alts:
        indep = sum(math.log(acc) if v == a else math.log((1 - acc) / (k - 1)) for _, acc, v in members)
        if len(members) == 1 or rho == 0.0:
            out[a] = indep
            continue
        terms = [math.log1p(-rho) + indep]
        if len(votes) == 1:
            shared = math.log(q) if a in votes else math.log((1 - q) / (k - 1))
            terms.append(math.log(rho) + shared)
        out[a] = _logsumexp(terms)
    return out


def quorum_solve(data, budget):
    alts, rows, rho, quorum, minimum = _quorum_inputs(data)
    order, members = _groups_in_order(rows)
    undeclared = sorted(g for g in order if len(members[g]) > 1 and g not in rho)
    if undeclared:
        return answer(None, {"undeclared_groups": undeclared}, status="ABSTAIN",
                      missing=[f"shared-noise level of multi-member group {g!r}" for g in undeclared[:20]])
    if len(order) < minimum:
        return answer(None, {"independent_groups": len(order), "minimum": minimum}, status="ABSTAIN",
                      missing=["fewer independent groups than the declared minimum"])
    k = len(alts)
    if all(acc <= 1.0 / k for _, _, acc, _ in rows):
        return answer(None, {"chance_level": 1.0 / k}, status="ABSTAIN",
                      missing=["no observer is declared better than chance"])
    threshold = math.log(quorum / (1 - quorum))
    acc = {a: 0.0 for a in alts}
    trace, first_cross, group_ll = [], None, {}
    for step, g in enumerate(order, 1):
        ll = _group_loglik(members[g], alts, rho.get(g, 0.0))
        if len(group_ll) < 60:                  # certificate size bound; the verifier recomputes every group
            group_ll[g] = {a: round(v, 9) for a, v in ll.items()}
        for a in alts:
            acc[a] += ll[a]
        # cross-inhibition: support(a) = E_a - log sum_{b != a} exp(E_b)  (log posterior odds a : rest)
        support = {a: acc[a] - _logsumexp([acc[b] for b in alts if b != a]) for a in alts}
        leader = max(alts, key=lambda a: (support[a], -alts.index(a)))
        if first_cross is None and support[leader] >= threshold:
            first_cross = step
        if len(trace) < 100:
            trace.append({"step": step, "group": g, "leader": leader, "support": round(support[leader], 9)})
    z = _logsumexp(list(acc.values()))
    posterior = {a: math.exp(acc[a] - z) for a in alts}
    support = {a: acc[a] - _logsumexp([acc[b] for b in alts if b != a]) for a in alts}
    leader = max(alts, key=lambda a: (support[a], -alts.index(a)))
    tied = sum(1 for a in alts if abs(support[a] - support[leader]) <= 1e-12) > 1
    certificate = {"groups": {g: sorted(o for o, *_ in members[g]) for g in order},
                   "group_log_likelihood": group_ll, "trace": trace, "first_quorum_step": first_cross,
                   "quorum": quorum, "model": "per-group mixture: shared signal (prob rho, accuracy = mean member "
                   "accuracy) or independent votes; symmetric errors; uniform prior over alternatives"}
    out = {"choice": leader, "posterior": {a: round(p, 12) for a, p in posterior.items()},
           "support_log_odds": {a: round(s, 9) for a, s in support.items()}, "independent_groups": len(order)}
    if tied or support[leader] < threshold:
        return answer(None, certificate, status="ABSTAIN",
                      missing=[f"no alternative reached quorum {quorum} (leader posterior "
                               f"{posterior[leader]:.3f})"])
    return answer(out, certificate)


def quorum_verify(data, output, certificate):
    """Probability-space recomputation from the raw observations (no accumulators, no solver helpers)."""
    alts, rows, rho, quorum, minimum = _quorum_inputs(data)
    members = {}
    for oid, g, acc, vote in rows:
        members.setdefault(g, []).append((oid, acc, vote))
    k = len(alts)
    logpost = {a: 0.0 for a in alts}
    declared = all(g in rho for g, ms in members.items() if len(ms) > 1)
    for g, ms in members.items():
        r = rho.get(g, 0.0) if len(ms) > 1 else 0.0
        q = math.fsum(acc for _, acc, _ in ms) / len(ms)
        common = {v for *_, v in ms}
        for a in alts:
            log_ind = math.fsum(math.log(acc if v == a else (1 - acc) / (k - 1)) for _, acc, v in ms)
            p_shared = (q if a in common else (1 - q) / (k - 1)) if len(common) == 1 else 0.0
            if r == 0.0 or p_shared == 0.0:
                like = math.log(1 - r) + log_ind
            else:
                big = max(math.log(1 - r) + log_ind, math.log(r * p_shared))
                like = big + math.log(math.exp(math.log(1 - r) + log_ind - big) + math.exp(math.log(r * p_shared) - big))
            logpost[a] += like
    top = max(logpost.values())
    norm = math.fsum(math.exp(v - top) for v in logpost.values())
    post = {a: math.exp(logpost[a] - top) / norm for a in alts}
    odds = {}
    for a in alts:                       # log posterior odds of a against the rest, from the log scale
        rest = [logpost[b] for b in alts if b != a]
        m = max(rest)
        odds[a] = logpost[a] - (m + math.log(math.fsum(math.exp(v - m) for v in rest)))
    output = output if isinstance(output, dict) else {}
    support = output.get("support_log_odds")
    support = support if isinstance(support, dict) else {}
    choice = output.get("choice")
    choice = choice if isinstance(choice, str) else None
    reported = output.get("posterior")
    reported = reported if isinstance(reported, dict) else {}
    raw_groups = certificate.get("groups") if isinstance(certificate, dict) else None
    cert_groups = ({g: sorted(v) for g, v in raw_groups.items()}
                   if isinstance(raw_groups, dict) and all(isinstance(v, list) and all(isinstance(o, str) for o in v)
                                                           for v in raw_groups.values()) else None)
    return {"observers_partitioned_once": cert_groups == {g: sorted(o for o, *_ in ms) for g, ms in members.items()},
            "correlation_declared": declared,
            "enough_independent_groups": len(members) >= minimum,
            "independent_groups_reported": output.get("independent_groups") == len(members),
            "choice_is_posterior_leader": choice in post and post[choice] >= max(post.values()) - 1e-9,
            "quorum_reached": choice in post and post[choice] >= quorum - 1e-9,
            "posterior_recomputed": all(type(reported.get(a)) in (int, float)
                                        and abs(reported[a] - post[a]) < 1e-6 for a in alts),
            "support_log_odds_recomputed": set(support) == set(alts) and all(
                type(support[a]) in (int, float) and math.isclose(support[a], odds[a], rel_tol=1e-7, abs_tol=1e-6)
                for a in alts)}


def _unique_max(scores):
    best = max(scores.values())
    leaders = [a for a, s in scores.items() if abs(s - best) <= 1e-12]
    return leaders[0] if len(leaders) == 1 else None


def quorum_majority(data):
    """Baseline: simple majority of all observers, each counted as independent; exact ties abstain."""
    alts, rows, *_ = _quorum_inputs(data)
    counts = {a: 0 for a in alts}
    for *_, vote in rows:
        counts[vote] += 1
    return {"choice": _unique_max(counts)}


def quorum_group_majority(data):
    """Competitor: one vote per declared independence group. Each group votes for its accuracy-weighted
    majority (a tie inside the group casts no vote) with the Nitzan-Paroush log-odds weight of the group's mean
    accuracy; the weighted majority over groups wins, exact ties abstain. It uses the declared grouping (as the
    candidate does) but no likelihood model and no quorum. Chosen as the strongest of four group-blind and
    group-aware alternatives on development seeds 0-9 (mean score 1.0 vs design-effect-weighted 0.8,
    accuracy-weighted 0.6, best single observer 0.4)."""
    alts, rows, *_ = _quorum_inputs(data)
    k = len(alts)
    groups = {}
    for _, g, acc, vote in rows:
        groups.setdefault(g, []).append((acc, vote))
    scores = {a: 0.0 for a in alts}
    for members in groups.values():
        inner = {}
        for acc, vote in members:
            inner[vote] = inner.get(vote, 0.0) + math.log(acc * (k - 1) / (1 - acc))
        lead = _unique_max(inner)
        if lead is None:
            continue
        q = statistics.fmean(acc for acc, _ in members)
        scores[lead] += math.log(q * (k - 1) / (1 - q))
    return {"choice": _unique_max(scores)}


def quorum_weighted_majority(data):
    """Alternative competitor (group-blind): accuracy-weighted majority (Nitzan-Paroush log-odds weights,
    optimal for INDEPENDENT voters with symmetric errors) over all observers (mean score 0.6 on dev seeds 0-9)."""
    alts, rows, *_ = _quorum_inputs(data)
    k = len(alts)
    scores = {a: 0.0 for a in alts}
    for _, _, acc, vote in rows:
        scores[vote] += math.log(acc * (k - 1) / (1 - acc))
    return {"choice": _unique_max(scores)}


def quorum_best_single(data):
    """Alternative competitor (kept for comparison): follow the single most accurate observer."""
    alts, rows, *_ = _quorum_inputs(data)
    best = max(rows, key=lambda r: (r[2], -rows.index(r)))
    return {"choice": best[3]}


def quorum_instance(seed):
    r = random.Random(7_100_000 + seed)
    k = r.choice((2, 3, 3, 4))
    alts = list("ABCD"[:k])
    truth = r.choice(alts)
    observers, groups = [], {}
    total = 0
    for gi in range(r.randint(4, 9)):
        size = 1 if r.random() < 0.5 else r.randint(2, 9)
        size = min(size, 40 - total)
        if size <= 0:
            break
        rho = 0.0 if size == 1 else r.uniform(0.3, 0.95)
        accs = [r.uniform(1 / k + 0.08, min(0.92, 1 / k + 0.5)) for _ in range(size)]
        q = sum(accs) / size
        shared = size > 1 and r.random() < rho
        signal = truth if r.random() < q else r.choice([a for a in alts if a != truth])
        g = f"g{gi}"
        for j, acc in enumerate(accs):
            if shared:
                vote = signal
            else:
                vote = truth if r.random() < acc else r.choice([a for a in alts if a != truth])
            history = sum(r.random() < acc for _ in range(40))          # accuracy is ESTIMATED, not known
            observers.append({"observer_id": f"o{gi}_{j}", "group": g, "accuracy": round((history + 1) / 42, 4),
                              "vote": vote})
        groups[g] = {"shared_noise": 0.0 if size == 1 else round(min(0.95, max(0.0, rho + r.gauss(0, 0.08))), 4)}
        total += size
    r.shuffle(observers)
    return ({"alternatives": alts, "observers": observers, "groups": groups, "quorum": 0.55,
             "minimum_independent": 3}, {"truth": truth})


def quorum_score(data, truth, output):
    choice = output.get("choice") if isinstance(output, dict) else None
    if choice is None:
        return {"quality": 0.0, "category": "abstain"}
    if choice == truth["truth"]:
        return {"quality": 1.0, "category": "correct"}
    return {"quality": -1.0, "category": "wrong"}


def quorum_subregion(data):
    """dominant_faction: one group with shared noise >= 0.5 holds >= 30% of all observers."""
    sizes = {}
    for o in data["observers"]:
        sizes[o["group"]] = sizes.get(o["group"], 0) + 1
    total = len(data["observers"])
    dominant = any(n / total >= 0.3 and data["groups"].get(g, {}).get("shared_noise", 0) >= 0.5
                   for g, n in sizes.items())
    return "dominant_faction" if dominant else "spread_factions"


# ============================================================================ 2. ant colony (MMAS) for the TSP
ACO_MAX_NATIVE = 40


def _cities(data):
    _require_dict(data)
    pts = data.get("cities")
    if not isinstance(pts, list) or not 4 <= len(pts) <= 1000:
        raise GenomeError("4-1000 cities [[x, y], ...] required")
    return [_point(p, 2, "city") for p in pts]


def _distances(pts):
    import numpy as np
    a = np.array(pts, dtype=float)
    return np.sqrt(((a[:, None, :] - a[None, :, :]) ** 2).sum(-1))


def _tour_len_np(tour, dmat):
    import numpy as np
    t = np.asarray(tour)
    return float(dmat[t, np.roll(t, -1)].sum())


def _two_opt(tour, dmat):
    """Best-improvement 2-opt to a local optimum (vectorised move evaluation)."""
    import numpy as np
    t = np.array(tour, dtype=int)
    n = len(t)
    if n < 4:
        return t.tolist()
    ii, jj = np.triu_indices(n, k=2)
    keep = ~((ii == 0) & (jj == n - 1))
    ii, jj = ii[keep], jj[keep]
    for _ in range(20 * n * n):
        a, b, c, d = t[ii], t[ii + 1], t[jj], t[(jj + 1) % n]
        delta = dmat[a, c] + dmat[b, d] - dmat[a, b] - dmat[c, d]
        k = int(np.argmin(delta))
        if delta[k] >= -1e-9:
            break
        i, j = int(ii[k]), int(jj[k])
        t[i + 1:j + 1] = t[i + 1:j + 1][::-1].copy()
    return t.tolist()


def _nearest_neighbour(dmat, start=0):
    n = len(dmat)
    tour, seen = [start], {start}
    while len(tour) < n:
        row = dmat[tour[-1]]
        nxt = min((j for j in range(n) if j not in seen), key=lambda j: (row[j], j))
        tour.append(nxt)
        seen.add(nxt)
    return tour


def aco_solve(data, budget):
    import numpy as np
    pts = _cities(data)
    n = len(pts)
    seed = _seed(data)
    if n > ACO_MAX_NATIVE:
        return answer(None, {"cities": n, "native_max": ACO_MAX_NATIVE}, status="ABSTAIN",
                      missing=[f"{n} cities exceeds the colony's bounded native size ({ACO_MAX_NATIVE})"])
    iterations = bounded_int(data.get("iterations", 150), low=1, high=400, name="iterations")
    local_search = data.get("local_search", True)
    if type(local_search) is not bool:
        raise GenomeError("local_search is a boolean")
    dmat = _distances(pts)
    scale = float(dmat.max())
    if scale == 0.0:
        return answer({"tour": list(range(n)), "length": 0.0}, {"degenerate": "all cities coincide"})
    rng = np.random.default_rng(seed)
    alpha, beta, rho, p_best = 1.0, 3.0, 0.1, 0.05
    ants = min(n, 20)
    eta = 1.0 / (dmat + 1e-9 * scale)
    np.fill_diagonal(eta, 0.0)
    heur = eta ** beta
    nn_len = _tour_len_np(_nearest_neighbour(dmat), dmat)
    tau_max = 1.0 / (rho * nn_len)
    root = p_best ** (1.0 / n)

    def tau_min_of(tmax):
        return tmax * (1 - root) / ((n / 2 - 1) * root)

    tau = np.full((n, n), tau_max)
    best, best_len, history, last_gain, restarts = None, math.inf, [], 0, 0
    rows = np.arange(ants)
    for it in range(iterations):
        weight = (tau ** alpha) * heur
        visited = np.zeros((ants, n), dtype=bool)
        cur = rng.integers(0, n, size=ants)
        tours = np.empty((ants, n), dtype=int)
        tours[:, 0] = cur
        visited[rows, cur] = True
        for step in range(1, n):
            w = weight[cur] * ~visited
            cum = np.cumsum(w, axis=1)
            total = cum[:, -1]
            u = rng.random(ants) * total
            nxt = (cum < u[:, None]).sum(axis=1)
            dead = (total <= 0) | (nxt >= n) | visited[rows, np.minimum(nxt, n - 1)]
            if dead.any():                          # numerical underflow: take the first unvisited city
                nxt[dead] = np.argmax(~visited[dead], axis=1)
            tours[:, step] = nxt
            visited[rows, nxt] = True
            cur = nxt
        lengths = dmat[tours, np.roll(tours, -1, axis=1)].sum(axis=1)
        ib = tours[int(np.argmin(lengths))].tolist()
        if local_search:
            ib = _two_opt(ib, dmat)
        ib_len = _tour_len_np(ib, dmat)
        if ib_len < best_len - 1e-9:
            best, best_len, last_gain = ib, ib_len, it
        tau *= 1 - rho
        deposit = best if it % 5 == 4 else ib            # MMAS schedule: mostly iteration-best
        d_len = best_len if deposit is best else ib_len
        t = np.asarray(deposit)
        nxt_t = np.roll(t, -1)
        tau[t, nxt_t] += 1.0 / d_len
        tau[nxt_t, t] += 1.0 / d_len
        tau_max = 1.0 / (rho * best_len)
        tau = np.clip(tau, tau_min_of(tau_max), tau_max)
        if it - last_gain >= 40:                           # stagnation: re-initialise trails (MMAS restart)
            tau[:] = tau_max
            last_gain = it
            restarts += 1
        if it % max(1, iterations // 50) == 0 or it == iterations - 1:
            history.append([it, round(best_len, 9)])
    best = [int(c) for c in best]
    # bounded trace that always keeps the final entry (it must end at the reported length)
    trace = history if len(history) <= 60 else history[:59] + history[-1:]
    return answer({"tour": best, "length": round(best_len, 9)},
                  {"seed": seed, "iterations": iterations, "ants": ants, "restarts": restarts,
                   "parameters": {"alpha": alpha, "beta": beta, "evaporation": rho, "p_best": p_best,
                                  "local_search": "2-opt on the iteration-best ant" if local_search else "none"},
                   "best_length_by_iteration": trace,
                   "evidence": "heuristic colony trace; no optimality claim"})


def _verify_tour(data, output):
    pts = _cities(data)
    tour = output.get("tour") if isinstance(output, dict) else None
    perm = isinstance(tour, list) and all(type(c) is int for c in tour) and sorted(tour) == list(range(len(pts)))
    length = math.fsum(math.hypot(pts[a][0] - pts[b][0], pts[a][1] - pts[b][1])
                       for a, b in zip(tour, tour[1:] + tour[:1])) if perm else None
    return perm, length


def aco_verify(data, output, certificate):
    perm, length = _verify_tour(data, output)
    reported = output.get("length") if isinstance(output, dict) else None
    reported = reported if type(reported) in (int, float) and math.isfinite(reported) else None
    raw = certificate.get("best_length_by_iteration") if isinstance(certificate, dict) else None
    trace_ok = isinstance(raw, list) and all(isinstance(h, list) and len(h) == 2 and type(h[1]) in (int, float)
                                             and math.isfinite(h[1]) for h in raw)
    history = [h[1] for h in raw] if trace_ok else []
    return {"tour_is_permutation": perm,
            "length_recomputed": perm and reported is not None
            and math.isclose(length, reported, rel_tol=1e-7, abs_tol=1e-6),
            "trace_well_formed": trace_ok,
            "trace_monotone": all(b <= a + 1e-9 for a, b in zip(history, history[1:])),
            "trace_ends_at_reported": not history or (reported is not None
                                                      and math.isclose(history[-1], reported, rel_tol=1e-7,
                                                                       abs_tol=1e-6))}


def _held_karp(dist):
    """Exact TSP optimum by dynamic programming over subsets (truth for n <= 12)."""
    n = len(dist)
    full = 1 << (n - 1)
    inf = math.inf
    dp = [[inf] * (n - 1) for _ in range(full)]
    for k in range(n - 1):
        dp[1 << k][k] = dist[0][k + 1]
    for mask in range(1, full):
        row = dp[mask]
        for k in range(n - 1):
            v = row[k]
            if v == inf or not (mask >> k) & 1:
                continue
            dk = dist[k + 1]
            for j in range(n - 1):
                if (mask >> j) & 1:
                    continue
                w = v + dk[j + 1]
                nm = mask | (1 << j)
                if w < dp[nm][j]:
                    dp[nm][j] = w
    return min(dp[full - 1][k] + dist[k + 1][0] for k in range(n - 1))


def _or_opt(tour, dmat):
    """First-improvement Or-opt (move a segment of 1-3 cities, either orientation)."""
    import numpy as np
    t = list(tour)
    n = len(t)
    improved = True
    while improved:
        improved = False
        for seg in (1, 2, 3):
            for i in range(n - seg + 1):
                s = t[i:i + seg]
                prev, nxt = t[i - 1], t[(i + seg) % n]
                if prev in s or nxt in s:
                    continue
                gain = dmat[prev, s[0]] + dmat[s[-1], nxt] - dmat[prev, nxt]
                rest = np.array(t[:i] + t[i + seg:])
                r1 = np.concatenate((rest[1:], rest[:1]))
                base = dmat[rest, r1]
                fwd = dmat[rest, s[0]] + dmat[s[-1], r1] - base
                rev = dmat[rest, s[-1]] + dmat[s[0], r1] - base
                cost = np.minimum(fwd, rev)
                j = int(np.argmin(cost))
                if gain - cost[j] > 1e-9:
                    piece = s if fwd[j] <= rev[j] else s[::-1]
                    rest = rest.tolist()
                    t = rest[:j + 1] + piece + rest[j + 1:]
                    improved = True
                    break
            if improved:
                break
    return t


def _reference_two_opt(tour, dmat):
    """First-improvement 2-opt written for the reference only (the candidate's best-improvement ``_two_opt``
    is deliberately not reused, so benchmark truth does not run the candidate's code)."""
    import numpy as np
    arr = np.array(tour, dtype=int)
    n = len(arr)
    improved = True
    while improved:
        improved = False
        for i in range(n - 2):
            a, b = arr[i], arr[i + 1]
            if i == 0:                     # edge (t[n-1], t[0]) is adjacent to (t[0], t[1]): j <= n - 2
                c, d = arr[2:n - 1], arr[3:n]
            else:                          # j = i + 2 .. n - 1, the successor of t[n-1] is t[0]
                c, d = arr[i + 2:n], np.append(arr[i + 3:n], arr[0])
            if not c.size:
                continue
            delta = dmat[a, c] + dmat[b, d] - dmat[a, b] - dmat[c, d]
            hit = np.flatnonzero(delta < -1e-9)
            if hit.size:
                j = i + 2 + int(hit[0])
                arr[i + 1:j + 1] = arr[i + 1:j + 1][::-1].copy()
                improved = True
    return arr.tolist()


def _tsp_reference(pts, seed):
    """Long multi-start local search for n > 12: nearest-neighbour starts from every city plus 40 random
    permutations, each improved by first-improvement 2-opt and Or-opt alternated to a joint local optimum.
    Self-contained: shares no construction or improvement code with the candidate or the competitor."""
    import numpy as np
    a = np.array(pts, dtype=float)
    dmat = np.sqrt(((a[:, None, :] - a[None, :, :]) ** 2).sum(-1))
    n = len(pts)

    def length_of(tour):
        return math.fsum(float(dmat[tour[k], tour[(k + 1) % n]]) for k in range(n))
    r = random.Random(9_000_000 + seed)
    starts = []
    for s in range(n):
        tour, left = [s], set(range(n)) - {s}
        while left:
            nxt = min(left, key=lambda j: (dmat[tour[-1], j], j))
            tour.append(nxt)
            left.discard(nxt)
        starts.append(tour)
    for _ in range(40):
        perm = list(range(n))
        r.shuffle(perm)
        starts.append(perm)
    best = math.inf
    for tour in starts:
        length = length_of(tour)
        while True:
            tour = _or_opt(_reference_two_opt(tour, dmat), dmat)
            new = length_of(tour)
            if new >= length - 1e-9:
                break
            length = new
        best = min(best, length)
    return best


def aco_instance(seed):
    r = random.Random(7_200_000 + seed)
    n = r.randint(8, 12) if r.random() < 0.3 else r.randint(20, 40)
    if r.random() < 0.5:
        pts = [[round(r.uniform(0, 1000), 3), round(r.uniform(0, 1000), 3)] for _ in range(n)]
    else:
        centres = [(r.uniform(100, 900), r.uniform(100, 900)) for _ in range(r.randint(3, 6))]
        pts = []
        for _ in range(n):
            cx, cy = r.choice(centres)
            pts.append([round(cx + r.gauss(0, 60), 3), round(cy + r.gauss(0, 60), 3)])
    data = {"cities": pts, "seed": seed}
    if n <= 12:
        dist = [[math.hypot(a[0] - b[0], a[1] - b[1]) for b in pts] for a in pts]
        return data, {"length": _held_karp(dist), "method": "Held-Karp exact"}
    return data, {"length": _tsp_reference([tuple(p) for p in pts], seed),
                  "method": "multi-start 2-opt + Or-opt reference (not a proven optimum)"}


def aco_score(data, truth, output):
    if not isinstance(output, dict) or "tour" not in output:
        return {"quality": -10.0, "category": "abstain"}         # no tour: below any valid tour's gap
    perm, length = _verify_tour(data, output)
    if not perm:
        return {"quality": -11.0, "category": "wrong"}
    ref = truth["length"]
    return {"quality": -(length - ref) / ref if ref > 0 else -length, "category": "correct"}


def aco_nearest_neighbour(data):
    """Baseline: nearest-neighbour tour from city 0."""
    pts = _cities(data)
    return {"tour": _nearest_neighbour(_distances(pts))}


def aco_nn_two_opt(data):
    """Alternative competitor (the competitor before the 2026-10-09 review): nearest-neighbour tour improved by
    best-improvement 2-opt to a local optimum (a single descent, ~0.4 ms)."""
    pts = _cities(data)
    dmat = _distances(pts)
    return {"tour": [int(c) for c in _two_opt(_nearest_neighbour(dmat), dmat)]}


ACO_GLS_SOLUTIONS = 2000


def aco_ortools_gls(data):
    """Competitor: OR-Tools routing (the mature open-source solver) with path-cheapest-arc construction and
    guided local search. Arc costs are distances scaled so the longest arc is ~1e9 (integer rounding below
    ~1e-9 relative); the search is bounded by a solution count, not a wall-clock limit, so the result is
    deterministic. On dev seeds 0-9 a 2000-solution limit reached the reference length on every instance
    (1200 missed one), 0.7-2.5 s."""
    from ortools.constraint_solver import pywrapcp, routing_enums_pb2
    pts = _cities(data)
    n = len(pts)
    dist = [[math.hypot(a[0] - b[0], a[1] - b[1]) for b in pts] for a in pts]
    top = max(max(row) for row in dist)
    if top == 0.0:
        return {"tour": list(range(n))}
    scale = 1e9 / top
    matrix = [[int(round(v * scale)) for v in row] for row in dist]
    manager = pywrapcp.RoutingIndexManager(n, 1, 0)
    routing = pywrapcp.RoutingModel(manager)
    routing.SetArcCostEvaluatorOfAllVehicles(routing.RegisterTransitMatrix(matrix))
    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    params.solution_limit = ACO_GLS_SOLUTIONS
    solution = routing.SolveWithParameters(params)
    if solution is None:
        return None
    index, tour = routing.Start(0), []
    while not routing.IsEnd(index):
        tour.append(int(manager.IndexToNode(index)))
        index = solution.Value(routing.NextVar(index))
    return {"tour": tour}


def aco_subregion(data):
    return "exact_truth_n_le_12" if len(data["cities"]) <= 12 else "reference_truth_n_20_40"


# ============================================================================ 3. Physarum conductance network
def _network_inputs(data):
    _require_dict(data)
    nodes = data.get("nodes")
    if not isinstance(nodes, list) or not 2 <= len(nodes) <= 120:
        raise GenomeError("2-120 nodes [[x, y], ...] required")
    coords = [_point(p, 2, "node") for p in nodes]
    edges = data.get("edges")
    if not isinstance(edges, list) or not 1 <= len(edges) <= 400:
        raise GenomeError("1-400 candidate edges [[u, v], ...] required")
    pairs, seen = [], set()
    for e in edges:
        if not isinstance(e, list) or len(e) != 2:
            raise GenomeError("edge is [u, v]")
        u = bounded_int(e[0], low=0, high=len(coords) - 1, name="edge endpoint")
        v = bounded_int(e[1], low=0, high=len(coords) - 1, name="edge endpoint")
        key = (min(u, v), max(u, v))
        if u == v or key in seen:
            raise GenomeError("candidate edges must be distinct and loop-free")
        seen.add(key)
        pairs.append(key)
    lengths = [math.hypot(coords[u][0] - coords[v][0], coords[u][1] - coords[v][1]) for u, v in pairs]
    if min(lengths) <= 0:
        raise GenomeError("zero-length candidate edge")
    terms = data.get("terminals")
    if not isinstance(terms, list) or not 2 <= len(terms) <= 40:
        raise GenomeError("2-40 distinct terminal node indices required")
    terms = [bounded_int(t, low=0, high=len(coords) - 1, name="terminal") for t in terms]
    if len(set(terms)) != len(terms):
        raise GenomeError("2-40 distinct terminal node indices required")
    lam = finite(data.get("lambda"), low=0.0, high=1e9, name="lambda")
    return coords, pairs, lengths, terms, lam


def _adjacency(n, pairs, chosen):
    adj = [[] for _ in range(n)]
    for e in chosen:
        u, v = pairs[e]
        adj[u].append((v, e))
        adj[v].append((u, e))
    return adj


def _design_value(n, pairs, lengths, terms, lam, chosen):
    """(objective, length, bridge_disconnections, bridges) via one DFS with bridge detection; None if the
    design leaves a terminal disconnected. Objective = length + lam * E[disconnected terminal pairs] when one
    candidate edge, chosen uniformly, fails."""
    chosen = sorted(set(chosen))
    adj = _adjacency(n, pairs, chosen)
    is_term = [False] * n
    for t in terms:
        is_term[t] = True
    root = terms[0]
    disc, low, tsub = [-1] * n, [0] * n, [0] * n
    timer, bridges = 0, []
    disc[root] = low[root] = 0
    tsub[root] = 1 if is_term[root] else 0
    stack = [(root, -1, iter(adj[root]))]
    while stack:
        node, via, it = stack[-1]
        advanced = False
        for nb, e in it:
            if e == via:
                continue
            if disc[nb] == -1:
                timer += 1
                disc[nb] = low[nb] = timer
                tsub[nb] = 1 if is_term[nb] else 0
                stack.append((nb, e, iter(adj[nb])))
                advanced = True
                break
            low[node] = min(low[node], disc[nb])
        if advanced:
            continue
        stack.pop()
        if stack:
            parent = stack[-1][0]
            low[parent] = min(low[parent], low[node])
            tsub[parent] += tsub[node]
            if low[node] > disc[parent]:
                bridges.append((via, tsub[node]))
    if any(disc[t] == -1 for t in terms):
        return None
    total_terms = len(terms)
    split = sum(s * (total_terms - s) for _, s in bridges)
    length = math.fsum(lengths[e] for e in chosen)
    return (length + lam * split / len(pairs), length, split,
            [e for e, s in bridges if 0 < s < total_terms])


def _dijkstra(n, pairs, lengths, sources, free=frozenset(), banned=frozenset()):
    adj = [[] for _ in range(n)]
    for e, (u, v) in enumerate(pairs):
        if e in banned:
            continue
        w = 0.0 if e in free else lengths[e]
        adj[u].append((v, e, w))
        adj[v].append((u, e, w))
    dist, via = [math.inf] * n, [None] * n
    heap = []
    for s in sources:
        dist[s] = 0.0
        heap.append((0.0, s))
    heapq.heapify(heap)
    while heap:
        d, u = heapq.heappop(heap)
        if d > dist[u]:
            continue
        for v, e, w in adj[u]:
            if d + w < dist[v] - 1e-12:
                dist[v], via[v] = d + w, (u, e)
                heapq.heappush(heap, (d + w, v))
    return dist, via


def _path_edges(via, target):
    out = []
    while via[target] is not None:
        u, e = via[target]
        out.append(e)
        target = u
    return out


def _components(n, pairs, chosen):
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for e in chosen:
        a, b = find(pairs[e][0]), find(pairs[e][1])
        if a != b:
            parent[a] = b
    return find


def _repair_and_prune(n, pairs, lengths, terms, chosen):
    """Connect every terminal (cheapest added paths, existing tubes free), then drop tubes that serve no
    terminal: edges outside the terminal component and dangling non-terminal branches."""
    chosen = set(chosen)
    for _ in range(len(terms)):
        find = _components(n, pairs, chosen)
        main = find(terms[0])
        loose = [t for t in terms if find(t) != main]
        if not loose:
            break
        sources = [v for v in range(n) if find(v) == main]
        dist, via = _dijkstra(n, pairs, lengths, sources, free=frozenset(chosen))
        target = min(loose, key=lambda t: (dist[t], t))
        if dist[target] == math.inf:
            return None
        chosen |= set(_path_edges(via, target))
    find = _components(n, pairs, chosen)
    main = find(terms[0])
    chosen = {e for e in chosen if find(pairs[e][0]) == main}
    term_set = set(terms)
    while True:
        degree = [0] * n
        for e in chosen:
            degree[pairs[e][0]] += 1
            degree[pairs[e][1]] += 1
        drop = {e for e in chosen if any(degree[x] == 1 and x not in term_set for x in pairs[e])}
        if not drop:
            return chosen
        chosen -= drop


def _terminals_connected(n, pairs, terms):
    find = _components(n, pairs, range(len(pairs)))
    return len({find(t) for t in terms}) == 1


def physarum_solve(data, budget):
    import numpy as np
    coords, pairs, lengths, terms, lam = _network_inputs(data)
    seed = _seed(data)
    n, m = len(coords), len(pairs)
    if not _terminals_connected(n, pairs, terms):
        return answer(None, {"terminals": len(terms)}, status="ABSTAIN",
                      missing=["the candidate graph does not connect every terminal"])
    steps = bounded_int(data.get("steps", 250), low=10, high=1000, name="steps")
    u_idx = np.array([u for u, _ in pairs])
    v_idx = np.array([v for _, v in pairs])
    rel_len = np.array(lengths) / float(np.mean(lengths))
    rng = np.random.default_rng(seed)
    t_arr = np.array(terms)
    sinks_share = 1.0 / (len(terms) - 1)
    designs, runs = [], []
    for mu in (0.9, 1.3, 1.8):
        cond = np.ones(m)
        for _ in range(steps):
            src = int(t_arr[rng.integers(len(terms))])
            b = np.zeros(n)
            b[t_arr] = -sinks_share
            b[src] = 1.0
            g = cond / rel_len
            lap = np.zeros((n, n))
            np.add.at(lap, (u_idx, u_idx), g)
            np.add.at(lap, (v_idx, v_idx), g)
            np.add.at(lap, (u_idx, v_idx), -g)
            np.add.at(lap, (v_idx, u_idx), -g)
            ground = int(t_arr[0]) if src != int(t_arr[0]) else int(t_arr[1])
            keep = np.arange(n) != ground
            reduced = lap[np.ix_(keep, keep)] + 1e-10 * np.eye(n - 1)
            p = np.zeros(n)
            p[keep] = np.linalg.solve(reduced, b[keep])
            q = np.abs(g * (p[u_idx] - p[v_idx]))
            qm = q ** mu
            cond += 0.25 * (2.0 * qm / (1.0 + qm) - cond)
            np.maximum(cond, 1e-9, out=cond)
        runs.append({"mu": mu, "max_conductance": round(float(cond.max()), 6),
                     "tubes_above_0.1": int((cond >= 0.1 * cond.max()).sum())})
        for frac in (0.02, 0.05, 0.1, 0.2, 0.35, 0.5):
            chosen = _repair_and_prune(n, pairs, lengths, terms,
                                       [e for e in range(m) if cond[e] >= frac * cond.max()])
            if chosen is None:
                continue
            value = _design_value(n, pairs, lengths, terms, lam, chosen)
            if value is not None:
                designs.append((value[0], mu, frac, sorted(chosen), value))
    if not designs:
        return answer(None, {"runs": runs}, status="UNKNOWN", missing=["no connected tube network extracted"])
    designs.sort(key=lambda d: (d[0], d[1], d[2]))
    objective, mu, frac, chosen, (_, length, split, bridges) = designs[0]
    return answer({"edges": [list(pairs[e]) for e in chosen], "objective": round(objective, 9),
                   "length": round(length, 9), "expected_disconnected_pairs": round(split / m, 9)},
                  {"seed": seed, "steps_per_run": steps, "runs": runs, "selected": {"mu": mu, "threshold": frac},
                   "designs_evaluated": len(designs), "bridges": len(bridges),
                   "objective_definition": "length + lambda * sum_{design edges} disconnected terminal pairs "
                                           "/ number of candidate edges (one uniformly random candidate edge fails)",
                   "evidence": "heuristic conductance-model trace; no optimality claim"})


def _union_find_split(n, design, terms, skip):
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for i, (u, v) in enumerate(design):
        if i != skip:
            parent[find(u)] = find(v)
    sizes = {}
    for t in terms:
        sizes[find(t)] = sizes.get(find(t), 0) + 1
    total = len(terms)
    return (total * (total - 1) - sum(s * (s - 1) for s in sizes.values())) // 2


def network_evaluate(data, output):
    """Independent objective: coordinates -> lengths; union-find connectivity after every single failure."""
    coords, pairs, _, terms, lam = _network_inputs(data)
    edges = output.get("edges") if isinstance(output, dict) else None
    cand = set(pairs)
    if not isinstance(edges, list) or not edges:
        return None
    design = []
    for e in edges:
        if not isinstance(e, list) or len(e) != 2 or not all(type(x) is int for x in e):
            return None
        key = (min(e), max(e))
        if key not in cand or key in design:
            return None
        design.append(key)
    n = len(coords)
    if _union_find_split(n, design, terms, skip=-1) != 0:
        return None
    length = math.fsum(math.hypot(coords[u][0] - coords[v][0], coords[u][1] - coords[v][1]) for u, v in design)
    split = sum(_union_find_split(n, design, terms, skip=i) for i in range(len(design)))
    return {"objective": length + lam * split / len(pairs), "length": length, "split": split}


def physarum_verify(data, output, certificate):
    value = network_evaluate(data, output)
    ok = value is not None

    def reported(key):
        v = output.get(key) if ok else None
        return v if type(v) in (int, float) and math.isfinite(v) else None
    m = len(_network_inputs(data)[1])
    return {"candidate_edges_only_and_terminals_connected": ok,
            "length_recomputed": reported("length") is not None
            and math.isclose(value["length"], reported("length"), rel_tol=1e-7),
            "objective_recomputed": reported("objective") is not None
            and math.isclose(value["objective"], reported("objective"), rel_tol=1e-7, abs_tol=1e-7),
            "robustness_recomputed": reported("expected_disconnected_pairs") is not None
            and math.isclose(value["split"] / m, reported("expected_disconnected_pairs"), rel_tol=1e-7,
                             abs_tol=1e-8)}


def _kmb_tree(n, pairs, lengths, terms):
    """Kou-Markowsky-Berman: MST of the terminals' shortest-path metric, expanded, re-spanned and pruned."""
    trees = {t: _dijkstra(n, pairs, lengths, [t]) for t in terms}
    inside, edges = {terms[0]}, set()
    while len(inside) < len(terms):
        d, a, b = min((trees[a][0][b], a, b) for a in inside for b in terms if b not in inside)
        if d == math.inf:
            return None
        edges |= set(_path_edges(trees[a][1], b))
        inside.add(b)
    order = sorted(edges, key=lambda e: (lengths[e], e))
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    span = set()
    for e in order:
        a, b = find(pairs[e][0]), find(pairs[e][1])
        if a != b:
            parent[a] = b
            span.add(e)
    return _repair_and_prune(n, pairs, lengths, terms, span)


def _edges_out(pairs, chosen):
    return {"edges": [list(pairs[e]) for e in sorted(chosen)]}


def physarum_mst(data):
    """Baseline: minimum spanning (Steiner) tree - KMB metric-closure MST, expanded and pruned."""
    coords, pairs, lengths, terms, lam = _network_inputs(data)
    tree = _kmb_tree(len(coords), pairs, lengths, terms)
    return None if tree is None else _edges_out(pairs, tree)


def physarum_mst_augmented(data):
    """Alternative competitor (the competitor before the 2026-10-09 review; it inherits KMB's longer trees
    in the low-fault regime): the KMB tree plus greedy bridge-removal augmentation optimising the SAME predeclared
    objective: each round, for every bridge, add the cheapest path that bypasses it (existing edges free) and
    keep the single augmentation that lowers the objective most; stop when none helps or the added length
    would exceed the budget (= the tree's own length)."""
    coords, pairs, lengths, terms, lam = _network_inputs(data)
    n = len(coords)
    tree = _kmb_tree(n, pairs, lengths, terms)
    if tree is None:
        return None
    design = set(tree)
    value = _design_value(n, pairs, lengths, terms, lam, design)
    budget, spent = value[1], 0.0
    for _ in range(60):
        best = None
        for e in value[3]:
            u, v = pairs[e]
            dist, via = _dijkstra(n, pairs, lengths, [u], free=frozenset(design), banned=frozenset([e]))
            if dist[v] == math.inf:
                continue
            new = set(_path_edges(via, v)) - design
            added = math.fsum(lengths[x] for x in new)
            if not new or spent + added > budget:
                continue
            trial = _design_value(n, pairs, lengths, terms, lam, design | new)
            if trial[0] < value[0] - 1e-9 and (best is None or trial[0] < best[0][0]):
                best = (trial, new, added)
        if best is None:
            break
        value, new, added = best
        design |= new
        spent += added
    return _edges_out(pairs, design)


def _tm_tree(n, pairs, lengths, terms, root):
    """Takahashi-Matsuyama shortest-path heuristic: grow a tree from ``root`` by repeatedly attaching the
    nearest remaining terminal along a shortest path."""
    nodes, edges, left = {root}, set(), set(terms) - {root}
    while left:
        dist, via = _dijkstra(n, pairs, lengths, sorted(nodes))
        target = min(left, key=lambda t: (dist[t], t))
        if dist[target] == math.inf:
            return None
        path = _path_edges(via, target)
        edges |= set(path)
        for e in path:
            nodes |= set(pairs[e])
        left -= nodes
    return _repair_and_prune(n, pairs, lengths, terms, edges)


def _objective_local_search(n, pairs, lengths, terms, lam, design, rounds=100):
    """Best-improvement local search on the declared objective. Moves: add the cheapest bypass path of a bridge
    (existing design edges free), add one candidate edge, or drop one design edge (connectivity kept)."""
    design = set(design)
    value = _design_value(n, pairs, lengths, terms, lam, design)
    for _ in range(rounds):
        best = None
        for e in value[3]:
            u, v = pairs[e]
            dist, via = _dijkstra(n, pairs, lengths, [u], free=frozenset(design), banned=frozenset([e]))
            if dist[v] == math.inf:
                continue
            trial_set = design | set(_path_edges(via, v))
            if trial_set == design:
                continue
            trial = _design_value(n, pairs, lengths, terms, lam, trial_set)
            if trial[0] < value[0] - 1e-9 and (best is None or trial[0] < best[0][0] - 1e-12):
                best = (trial, trial_set)
        for e in range(len(pairs)):
            trial_set = design ^ {e}
            if not trial_set:
                continue
            trial = _design_value(n, pairs, lengths, terms, lam, trial_set)
            if trial is not None and trial[0] < value[0] - 1e-9 and (best is None or trial[0] < best[0][0] - 1e-12):
                best = (trial, trial_set)
        if best is None:
            break
        value, design = best
    return value[0], design


def physarum_multistart_search(data):
    """Competitor: classical Steiner heuristics + local search on the SAME predeclared objective. Start trees:
    Kou-Markowsky-Berman and Takahashi-Matsuyama grown from each terminal (at most 10 roots); each start is
    improved by best-improvement local search (bridge-bypass paths, single-edge additions and removals) and
    the design with the lowest objective is returned."""
    coords, pairs, lengths, terms, lam = _network_inputs(data)
    n = len(coords)
    starts = [_kmb_tree(n, pairs, lengths, terms)] + [_tm_tree(n, pairs, lengths, terms, r) for r in terms[:10]]
    best = None
    for tree in starts:
        if not tree:
            continue
        value, design = _objective_local_search(n, pairs, lengths, terms, lam, tree)
        if best is None or value < best[0] - 1e-12:
            best = (value, design)
    return None if best is None else _edges_out(pairs, best[1])


def physarum_instance(seed):
    r = random.Random(7_300_000 + seed)
    t = r.randint(5, 9)
    pts = [(r.uniform(0, 100), r.uniform(0, 100)) for _ in range(t)]
    for gx in range(5):
        for gy in range(5):
            pts.append((10 + 20 * gx + r.uniform(-5, 5), 10 + 20 * gy + r.uniform(-5, 5)))
    pts = [(round(x, 3), round(y, 3)) for x, y in pts]
    n = len(pts)
    d = [[math.hypot(a[0] - b[0], a[1] - b[1]) for b in pts] for a in pts]
    edges = set()
    for i in range(n):
        for j in sorted((j for j in range(n) if j != i), key=lambda j: d[i][j])[:4]:
            edges.add((min(i, j), max(i, j)))
    inside = {0}                                   # Prim over all nodes guarantees a connected candidate graph
    while len(inside) < n:
        _, i, j = min((d[i][j], i, j) for i in inside for j in range(n) if j not in inside)
        edges.add((min(i, j), max(i, j)))
        inside.add(j)
    edges = sorted(edges)
    # instance scale from straight-line geometry only (independent of every arm): Euclidean MST of terminals
    inside, scale, tree = {0}, 0.0, []
    while len(inside) < t:
        w, i, j = min((d[i][j], i, j) for i in inside for j in range(t) if j not in inside)
        scale += w
        tree.append((i, j))
        inside.add(j)
    split_est = 0
    for i, j in tree:                               # terminals on each side of each Euclidean-MST edge
        side, frontier = {j}, [j]
        while frontier:
            x = frontier.pop()
            for a, b in tree:
                for y, z in ((a, b), (b, a)):
                    if y == x and z != i and z not in side:
                        side.add(z)
                        frontier.append(z)
        split_est += len(side) * (t - len(side))
    ratio = math.exp(r.uniform(math.log(0.05), math.log(2.0)))
    lam = round(ratio * scale * len(edges) / (2.5 * split_est), 4)
    data = {"nodes": [list(p) for p in pts], "edges": [list(e) for e in edges], "terminals": list(range(t)),
            "lambda": lam, "seed": seed}
    return data, {"scale": scale, "ratio": ratio}


def physarum_score(data, truth, output):
    if not isinstance(output, dict) or "edges" not in output:
        return {"quality": -10.0, "category": "abstain"}
    value = network_evaluate(data, output)
    if value is None:
        return {"quality": -11.0, "category": "wrong"}
    return {"quality": -value["objective"] / truth["scale"], "category": "correct"}


def physarum_subregion(data):
    """high_fault_weight: one leaf link's expected penalty lambda * (T-1) / |candidates| exceeds 0.15 x the
    median candidate edge length (the population median of this statistic over generator seeds 100-299, which
    are neither development nor held-out seeds); low_fault_weight otherwise."""
    coords, pairs, lengths, terms, lam = _network_inputs(data)
    leaf_penalty = lam * (len(terms) - 1) / len(pairs)
    return "high_fault_weight" if leaf_penalty > 0.15 * statistics.median(lengths) else "low_fault_weight"


# ============================================================================ 4. negative selection detectors
IMMUNE_MAX_DIM = 8
IMMUNE_MAX_TEST = 300   # witness certificate stays < 64 KiB even if every point is flagged at d = 8
UNIVERSE = 6.0          # the modelled universe is the box [-6, 6]^d in self-standardised units
# A flag needs depth > self radius + margin; its witness radius keeps margin / 2 of slack on BOTH sides, so
# the 9-decimal rounding of witness centres (<= 1.5e-9 in distance at d = 8) and numpy-vs-math.dist rounding
# can never make the independent witness check refute a correct flag.
IMMUNE_MARGIN = 1e-7
IMMUNE_TARGET_FRACTION = 0.75   # calibrate to 0.75 x the declared false-alarm tolerance (a safety factor)
# P8 evolvable configuration (greg/cognition/evolution.py, target "immune_detect"). The genome runs
# IMMUNE_DEFAULT_CONFIG; a retained evolved configuration is only a proposal (building != activation).
IMMUNE_DEFAULT_CONFIG = {"detectors": 3000, "uniform_share": 0.5, "scale_set": [1.0, 2.0, 3.0],
                         "calibration_folds": 3, "alarm_fraction": IMMUNE_TARGET_FRACTION, "whitening": "diagonal"}
IMMUNE_CONFIG_SPACE = {"detectors": ("choice", [1000, 2000, 3000, 4000, 5000]),
                       "uniform_share": ("float", [0.1, 0.9]),
                       "scale_set": ("choice", [[1.0], [1.0, 2.0], [1.0, 2.0, 3.0], [0.5, 1.0, 2.0],
                                                [0.5, 1.0, 2.0, 3.0]]),
                       "calibration_folds": ("choice", [3, 5]),
                       "alarm_fraction": ("float", [0.4, 0.95]),
                       "whitening": ("choice", ["diagonal", "full"])}


def _immune_config(config):
    if not isinstance(config, dict) or set(config) != set(IMMUNE_CONFIG_SPACE):
        raise GenomeError(f"immune configuration must set exactly {sorted(IMMUNE_CONFIG_SPACE)}")
    for key, (kind, values) in IMMUNE_CONFIG_SPACE.items():
        value = config[key]
        if kind == "choice" and value not in values:
            raise GenomeError(f"{key}={value!r} is outside the declared space")
        if kind == "float" and (type(value) not in (int, float) or not values[0] <= value <= values[1]):
            raise GenomeError(f"{key}={value!r} is outside [{values[0]}, {values[1]}]")
    return config


def _immune_inputs(data):
    _require_dict(data)
    self_s, test = data.get("self_samples"), data.get("test_points")
    if not isinstance(self_s, list) or not 2 <= len(self_s) <= 2000:
        raise GenomeError("2-2000 self samples required")
    if not isinstance(test, list) or not 1 <= len(test) <= 1000:
        raise GenomeError("1-1000 test points required")
    if not isinstance(self_s[0], list) or not 1 <= len(self_s[0]) <= 20:
        raise GenomeError("feature vectors of dimension 1-20 required")
    dim = len(self_s[0])
    s = [_point(p, dim, "self sample") for p in self_s]
    x = [_point(p, dim, "test point") for p in test]
    tol = finite(data.get("max_false_alarm_rate"), low=0.001, high=0.5, name="max_false_alarm_rate")
    return s, x, tol, dim


def _standardiser(s):
    dim = len(s[0])
    mean = [statistics.fmean(p[k] for p in s) for k in range(dim)]
    sd = [statistics.pstdev([p[k] for p in s]) or 1.0 for k in range(dim)]
    return mean, sd


def immune_solve(data, budget):
    return immune_solve_with(IMMUNE_DEFAULT_CONFIG, data)


def immune_solve_with(config, data):
    import numpy as np
    config = _immune_config(config)
    s, x, tol, dim = _immune_inputs(data)
    seed = _seed(data)
    if dim > IMMUNE_MAX_DIM:
        return answer(None, {"dimension": dim}, status="ABSTAIN",
                      missing=[f"dimension {dim} > {IMMUNE_MAX_DIM}: detector coverage collapses"])
    if len(s) < 60:
        return answer(None, {"self_samples": len(s)}, status="ABSTAIN",
                      missing=["at least 60 self samples are needed to censor and calibrate detectors"])
    if len(x) > IMMUNE_MAX_TEST:
        return answer(None, {"test_points": len(x)}, status="ABSTAIN",
                      missing=[f"more than {IMMUNE_MAX_TEST} test points: split the batch (witness certificate "
                               "size bound)"])
    target = config["alarm_fraction"] * tol
    k = int(math.floor(target * (len(s) + 1))) - 1      # conformal: (k + 1) / (n + 1) <= target
    if k < 0:
        # even the largest held-back depth only bounds the false-alarm rate by 1 / (n + 1) > target
        need = math.ceil(1.0 / target) - 1
        return answer(None, {"self_samples": len(s), "target_rate": round(target, 9), "needed": need},
                      status="ABSTAIN",
                      missing=[f"{len(s)} self samples cannot calibrate a false-alarm target of {target:.6g}; "
                               f"at least {need} are needed"])
    if config["whitening"] == "full":
        # full whitening by the self covariance (numpy Cholesky); the verifier recomputes it independently
        a = np.array(s)
        mean = [float(v) for v in a.mean(0)]
        try:
            low = np.linalg.cholesky(np.atleast_2d(np.cov(a, rowvar=False, bias=True)))
        except np.linalg.LinAlgError:
            return answer(None, {"whitening": "full"}, status="ABSTAIN",
                          missing=["self covariance is not positive definite: full whitening is undefined"])
        zs = np.linalg.solve(low, (a - mean).T).T
        zx = np.linalg.solve(low, (np.array(x) - mean).T).T
        standardisation = {"kind": "full", "mean": mean, "cholesky": [[float(v) for v in r] for r in low]}
    else:
        mean, sd = _standardiser(s)
        zs = (np.array(s) - mean) / sd
        zx = (np.array(x) - mean) / sd
        standardisation = {"mean": mean, "sd": sd}
    rng = np.random.default_rng(seed)
    n_det = int(bounded_int(data.get("detectors", config["detectors"]), low=100, high=5000, name="detectors"))
    half = int(n_det * config["uniform_share"])
    # candidate detectors never depend on individual self samples (keeps calibration exchangeable):
    # a share uniform over the universe, the rest concentrated around the self region at several scales
    around = rng.normal(size=(n_det - half, dim)) * rng.choice(config["scale_set"], size=(n_det - half, 1))
    centres = np.clip(np.vstack([rng.uniform(-UNIVERSE, UNIVERSE, size=(half, dim)), around]), -UNIVERSE, UNIVERSE)

    def rows_per_chunk(width):                 # keep each pairwise block near 2e6 floats (~16 MB)
        return max(1, 2_000_000 // max(1, width * dim))

    def nearest(points, ref):
        out, step = np.empty(len(points)), rows_per_chunk(len(ref))
        for i in range(0, len(points), step):
            chunk = points[i:i + step]
            out[i:i + step] = np.sqrt(((chunk[:, None, :] - ref[None, :, :]) ** 2).sum(-1)).min(1)
        return out

    def depth(points, reach):                  # max_j (reach_j - ||p - c_j||): how deep inside coverage
        out, arg, step = np.empty(len(points)), np.empty(len(points), dtype=int), rows_per_chunk(len(centres))
        for i in range(0, len(points), step):
            v = reach[None, :] - np.sqrt(((points[i:i + step][:, None, :] - centres[None, :, :]) ** 2).sum(-1))
            arg[i:i + step] = v.argmax(1)
            out[i:i + step] = v.max(1)
        return out, arg
    folds = config["calibration_folds"]        # cross-fitted calibration: every self sample is held back once
    fold_of = rng.permutation(len(zs)) % folds
    cal_depth = np.empty(len(zs))
    for f in range(folds):
        reach_f = nearest(centres, zs[fold_of != f])
        cal_depth[fold_of == f] = depth(zs[fold_of == f], reach_f)[0]
    reach = nearest(centres, zs)               # final detectors censored on ALL self: depths only shrink
    ranked = np.sort(cal_depth)[::-1]
    r_self = max(0.0, float(ranked[k]))
    test_depth, which = depth(zx, reach)
    outside = np.abs(zx).max(1) > UNIVERSE + 1e-9      # slack so the verifier's own z agrees at the edge
    flagged = sorted(int(i) for i in np.nonzero((test_depth > r_self + IMMUNE_MARGIN) | outside)[0])
    witnesses = {}
    for i in flagged:
        if outside[i]:
            witnesses[str(i)] = {"outside_universe": True}
        else:
            j = int(which[i])
            witnesses[str(i)] = {"centre": [round(float(c), 9) for c in centres[j]],
                                 "radius": float(reach[j] - r_self) - IMMUNE_MARGIN / 2}
    return answer({"flagged": flagged, "self_radius": round(r_self, 12)},
                  {"seed": seed, "standardisation": standardisation, "self_radius": r_self,
                   "censored_against": "every self sample", "witnesses": witnesses, "detectors_generated": n_det,
                   "detectors_self_tolerant": int((reach > r_self).sum()),
                   "calibration": {"method": f"{folds}-fold cross-fitted conformal quantile of self depth",
                                   "target_rate": round(target, 9), "allowed_exceedances": k,
                                   **({} if config["alarm_fraction"] == IMMUNE_TARGET_FRACTION
                                      else {"alarm_fraction": config["alarm_fraction"]}),
                                   "held_back_self": len(zs),
                                   "held_back_flagged": int((cal_depth > r_self + IMMUNE_MARGIN).sum())},
                   "universe": f"[-{UNIVERSE}, {UNIVERSE}]^d standardised; outside it is non-self",
                   "evidence": "calibrated statistical detector; each flag has a self-tolerant witness detector"})


def immune_verify(data, output, certificate):
    """Witness geometry in pure Python: each flag is outside the universe or covered by a detector whose
    radius plus the self radius does not reach any self sample."""
    s, x, tol, dim = _immune_inputs(data)
    n = len(s)
    # standardisation recomputed here (fsum-based), not through the solver's ``_standardiser``
    mean = [math.fsum(p[k] for p in s) / n for k in range(dim)]
    sd = [math.sqrt(math.fsum((p[k] - mean[k]) ** 2 for p in s) / n) for k in range(dim)]
    sd = [v if v > 0 else 1.0 for v in sd]
    certificate = certificate if isinstance(certificate, dict) else {}

    def numbers(v, size):
        return (isinstance(v, list) and len(v) == size
                and all(type(a) in (int, float) and math.isfinite(a) for a in v))
    cert_std = certificate.get("standardisation")
    cert_std = cert_std if isinstance(cert_std, dict) else {}
    close = lambda a, b: math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)   # noqa: E731
    if cert_std.get("kind") == "full":
        # covariance (fsum) and a pure-Python Cholesky here, independent of the solver's numpy factor
        cov = [[math.fsum((p[i] - mean[i]) * (p[j] - mean[j]) for p in s) / n for j in range(dim)]
               for i in range(dim)]
        low = _verify_cholesky(cov)
        claimed = cert_std.get("cholesky")
        std_ok = (low is not None and numbers(cert_std.get("mean"), dim) and isinstance(claimed, list)
                  and len(claimed) == dim and all(numbers(r, dim) for r in claimed)
                  and all(close(a, b) for a, b in zip(cert_std["mean"], mean))
                  and all(close(a, b) for r, q in zip(claimed, low) for a, b in zip(r, q)))
        if std_ok:
            mean, low = cert_std["mean"], claimed            # agrees to 1e-9; use the solver's exact frame

        def frame(p):                                        # forward substitution: z = L^-1 (p - mean)
            if low is None:
                return None
            z = []
            for i in range(dim):
                z.append(((p[i] - mean[i]) - math.fsum(low[i][j] * z[j] for j in range(i))) / low[i][i])
            return z
    else:
        std_ok = (numbers(cert_std.get("mean"), dim) and numbers(cert_std.get("sd"), dim)
                  and all(close(a, b) for a, b in zip(cert_std["mean"], mean))
                  and all(close(a, b) for a, b in zip(cert_std["sd"], sd)))
        if std_ok:
            mean, sd = cert_std["mean"], cert_std["sd"]      # agrees to 1e-9; use the solver's exact frame

        def frame(p):
            return [(p[k] - mean[k]) / sd[k] for k in range(dim)]
    # calibration arithmetic: the declared target, the conformal rank and the held-back count must be the
    # ones the declared tolerance and sample size imply (the detector depths themselves are not recomputed)
    cal = certificate.get("calibration")
    cal = cal if isinstance(cal, dict) else {}
    fraction = cal.get("alarm_fraction", IMMUNE_TARGET_FRACTION)
    low_f, high_f = IMMUNE_CONFIG_SPACE["alarm_fraction"][1]
    fraction_ok = type(fraction) in (int, float) and low_f <= fraction <= high_f
    target = (fraction if fraction_ok else IMMUNE_TARGET_FRACTION) * tol
    k = cal.get("allowed_exceedances")
    flagged_back = cal.get("held_back_flagged")
    calibration_ok = (fraction_ok and type(cal.get("target_rate")) in (int, float)
                      and math.isclose(cal["target_rate"], target, rel_tol=1e-6)
                      and type(k) is int and k >= 0 and (k + 1) / (n + 1) <= target + 1e-12
                      and cal.get("held_back_self") == n
                      and type(flagged_back) is int and 0 <= flagged_back <= k)
    r_self = certificate.get("self_radius")
    output = output if isinstance(output, dict) else {}
    flagged = output.get("flagged")
    idx_ok = (isinstance(flagged, list) and all(type(i) is int and 0 <= i < len(x) for i in flagged)
              and len(set(flagged)) == len(flagged))
    radius_ok = (type(r_self) in (int, float) and math.isfinite(r_self) and r_self >= 0
                 and type(output.get("self_radius")) in (int, float)
                 and math.isclose(output["self_radius"], r_self, rel_tol=1e-9, abs_tol=1e-12))
    witnessed = idx_ok and radius_ok and frame(s[0]) is not None
    witnesses = certificate.get("witnesses")
    witnesses = witnesses if isinstance(witnesses, dict) else {}
    if witnessed:
        selfz = [frame(p) for p in s]
        for i in flagged:
            z = frame(x[i])
            w = witnesses.get(str(i))
            if not isinstance(w, dict):
                witnessed = False
            elif w.get("outside_universe") is True:
                witnessed = max(abs(v) for v in z) > UNIVERSE
            else:
                c, rad = w.get("centre"), w.get("radius")
                witnessed = (numbers(c, dim) and type(rad) in (int, float) and math.isfinite(rad) and rad > 0
                             and math.dist(z, c) < rad                                   # the detector covers it
                             and min(math.dist(c, t) for t in selfz) >= rad + r_self)    # and tolerates self
            if not witnessed:
                break
    return {"flag_indices_valid": idx_ok, "standardisation_recomputed": std_ok,
            "calibration_arithmetic": calibration_ok,
            "self_radius_consistent": radius_ok, "every_flag_witnessed": witnessed}


def _verify_cholesky(a):
    """Verifier-only pure-Python Cholesky factor; None when the matrix is not positive definite."""
    dim = len(a)
    low = [[0.0] * dim for _ in range(dim)]
    for i in range(dim):
        for j in range(i + 1):
            acc = a[i][j] - math.fsum(low[i][m] * low[j][m] for m in range(j))
            if i == j:
                if acc <= 1e-12 * max(1.0, abs(a[i][i])):
                    return None
                low[i][i] = math.sqrt(acc)
            else:
                low[i][j] = acc / low[j][j]
    return low


def _binom_upper(n, p, level=0.95):
    """Smallest k with P(Bin(n, p) <= k) >= level."""
    total, k = 0.0, 0
    while k <= n:
        total += math.comb(n, k) * p ** k * (1 - p) ** (n - k)
        if total >= level:
            return k
        k += 1
    return n


def immune_score(data, truth, output):
    if not isinstance(output, dict) or "flagged" not in output:
        return {"quality": 0.0, "category": "abstain"}
    labels = truth["labels"]
    flagged = output["flagged"]
    if (not isinstance(flagged, list) or not all(type(i) is int and 0 <= i < len(labels) for i in flagged)
            or len(set(flagged)) != len(flagged)):
        return {"quality": -1.0, "category": "wrong"}
    hits = set(flagged)
    tp = sum(1 for i in hits if labels[i] == 1)
    fp = len(hits) - tp
    fn = sum(labels) - tp
    n_self = len(labels) - sum(labels)
    if fp > _binom_upper(n_self, data["max_false_alarm_rate"]):     # autoimmunity beyond tolerance
        return {"quality": -1.0, "category": "wrong"}
    return {"quality": 2 * tp / (2 * tp + fp + fn) if tp else 0.0, "category": "correct"}


def immune_zscore(data):
    """Baseline: per-feature z-score with a Bonferroni threshold z > Phi^-1(1 - tol / (2d))."""
    s, x, tol, dim = _immune_inputs(data)
    mean, sd = _standardiser(s)
    cut = statistics.NormalDist().inv_cdf(1 - tol / (2 * dim))
    return {"flagged": [i for i, p in enumerate(x) if max(abs((p[k] - mean[k]) / sd[k]) for k in range(dim)) > cut]}


def immune_mahalanobis(data):
    """Alternative competitor (the competitor before the 2026-10-09 review): Mahalanobis distance with the
    asymptotic chi-square(d) 1 - tol quantile. It ignores that the mean and covariance are estimated and targets
    the full tolerance, so it overshoots the false-alarm limit (1 wrong answer on dev seeds 0-9)."""
    import numpy as np
    from scipy.stats import chi2
    s, x, tol, dim = _immune_inputs(data)
    a = np.array(s)
    mu = a.mean(0)
    cov = np.atleast_2d(np.cov(a, rowvar=False))
    inv = np.linalg.pinv(cov)
    diff = np.array(x) - mu
    d2 = np.einsum("ij,jk,ik->i", diff, inv, diff)
    return {"flagged": [int(i) for i in np.nonzero(d2 > chi2.ppf(1 - tol, dim))[0]]}


def immune_prediction_region(data):
    """Competitor: the exact Gaussian prediction ellipsoid for a new observation (Hotelling): flag x when
    (x - mean)' S^-1 (x - mean) > d (n - 1)(n + 1) / (n (n - d)) F^-1_{d, n-d}(1 - target), with the sample mean
    and covariance and the SAME false-alarm target as the candidate (0.75 x tolerance). scipy for the quantile."""
    import numpy as np
    from scipy.stats import f as f_dist
    s, x, tol, dim = _immune_inputs(data)
    n = len(s)
    if n <= dim + 1:
        return None
    a = np.array(s)
    mu = a.mean(0)
    inv = np.linalg.pinv(np.atleast_2d(np.cov(a, rowvar=False)))
    diff = np.array(x) - mu
    d2 = np.einsum("ij,jk,ik->i", diff, inv, diff)
    cut = dim * (n - 1) * (n + 1) / (n * (n - dim)) * f_dist.ppf(1 - IMMUNE_TARGET_FRACTION * tol, dim, n - dim)
    return {"flagged": [int(i) for i in np.nonzero(d2 > cut)[0]]}


def immune_instance(seed):
    import numpy as np
    r = random.Random(7_400_000 + seed)
    g = np.random.default_rng(7_400_000 + seed)
    dim = r.randint(2, 6)
    q, _ = np.linalg.qr(g.normal(size=(dim, dim)))
    cov = q @ np.diag(g.uniform(0.05, 3.0, dim)) @ q.T
    mu = g.uniform(-5, 5, dim)
    chol = np.linalg.cholesky(cov)
    self_s = g.multivariate_normal(mu, cov, r.randint(300, 500))
    normal = g.multivariate_normal(mu, cov, 200)
    n_anom = r.randint(20, 40)
    kinds = [r.choice(("correlation_break", "shift", "inflated")) for _ in range(n_anom)]
    anomalies = []
    for kind in kinds:
        if kind == "correlation_break":            # same marginals, correlations removed
            anomalies.append(g.normal(mu, np.sqrt(np.diag(cov))))
        elif kind == "shift":
            u = g.normal(size=dim)
            u /= np.linalg.norm(u)
            anomalies.append(mu + chol @ (u * r.uniform(3.0, 5.0) + 0.3 * g.normal(size=dim)))
        else:
            anomalies.append(mu + 2.0 * chol @ g.normal(size=dim))
    points = [(p, 0) for p in normal] + [(p, 1) for p in anomalies]
    r.shuffle(points)
    data = {"self_samples": [[round(float(v), 6) for v in p] for p in self_s],
            "test_points": [[round(float(v), 6) for v in p] for p, _ in points],
            "max_false_alarm_rate": r.choice((0.01, 0.02, 0.05)), "seed": seed}
    return data, {"labels": [lab for _, lab in points], "kinds": kinds}


def immune_subregion(data):
    return "low_dim_2_3" if len(data["self_samples"][0]) <= 3 else "mid_dim_4_6"


# ============================================================================ 5. ascending clock auction
def _market_inputs(data):
    _require_dict(data)
    cap = bounded_int(data.get("capacity"), low=0, high=100_000, name="capacity")
    reserve = finite(data.get("reserve", 0.0), low=0.0, high=1e9, name="reserve")
    inc = finite(data.get("increment", 1.0), low=1e-6, high=1e9, name="increment")
    tasks = data.get("tasks")
    if not isinstance(tasks, list) or not 1 <= len(tasks) <= 200:
        raise GenomeError("1-200 tasks required")
    out, ids, units = [], set(), 0
    for t in tasks:
        if not isinstance(t, dict):
            raise GenomeError("task is {task_id, marginal_values}")
        tid, vals = t.get("task_id"), t.get("marginal_values")
        if not isinstance(tid, str) or not 1 <= len(tid) <= 64 or tid in ids:
            raise GenomeError("task ids must be unique strings of 1-64 characters")
        if not isinstance(vals, list) or not 1 <= len(vals) <= 100:
            raise GenomeError("1-100 marginal values per task required")
        out.append((tid, [finite(v, low=0.0, high=1e9, name="marginal value") for v in vals]))
        ids.add(tid)
        units += len(vals)
    if units > 20_000:
        raise GenomeError("at most 20000 requested units")
    max_rounds = bounded_int(data.get("max_rounds", 5000), low=1, high=100_000, name="max_rounds")
    return cap, reserve, inc, out, max_rounds


class _Bidder:
    """A price-taking agent. The auctioneer sees only ``demand(price)``, never the values."""

    def __init__(self, values):
        self._ascending = sorted(values)

    def demand(self, price):
        return len(self._ascending) - bisect_left(self._ascending, price)


def market_solve(data, budget):
    cap, reserve, inc, tasks, max_rounds = _market_inputs(data)
    for tid, vals in tasks:
        if any(b > a + 1e-12 for a, b in zip(vals, vals[1:])):
            return answer(None, {"task": tid}, status="ABSTAIN",
                          missing=[f"task {tid!r} has increasing marginal values (complementarity): a clearing "
                                   "price need not exist"])
    bidders = [(tid, _Bidder(vals)) for tid, vals in tasks]

    def total(price):
        return sum(b.demand(price) for _, b in bidders)
    trace, rounds = [], 0
    lo = hi = reserve
    d_hi = total(reserve)
    trace.append([round(reserve, 9), d_hi])
    if d_hi > cap:
        step = inc
        while True:
            rounds += 1
            hi = lo + step
            d_hi = total(hi)
            if len(trace) < 150:
                trace.append([round(hi, 9), d_hi])
            if d_hi <= cap:
                break
            lo = hi
            if rounds % 50 == 0:
                step *= 2.0                          # bounded rounds: the clock accelerates
            if rounds > max_rounds:
                return answer(None, {"rounds": rounds, "trace": trace[:150]}, status="UNKNOWN",
                              missing=["the clock did not clear within max_rounds"])
        for _ in range(80):                          # refine the clearing bracket by bisection
            if hi - lo <= 1e-9 * max(1.0, hi):
                break
            mid = (lo + hi) / 2
            rounds += 1
            if total(mid) <= cap:
                hi = mid
            else:
                lo = mid
        d_hi = total(hi)
    allocation = {tid: b.demand(hi) for tid, b in bidders}
    left = cap - sum(allocation.values())
    rationed = 0
    if hi > lo and left > 0:
        for tid, b in bidders:                       # units valued inside the bracket are tied up to its width
            extra = min(left, b.demand(lo) - b.demand(hi))
            allocation[tid] += extra
            left -= extra
            rationed += extra
    price = lo if rationed else hi
    return answer({"allocation": allocation, "clearing_price": round(price, 12),
                   "payments": {tid: round(price * x, 9) for tid, x in allocation.items()}, "rounds": rounds},
                  {"bracket": [round(lo, 12), round(hi, 12)], "demand_at_bracket": [total(lo), total(hi)],
                   "rationed_units_in_bracket": rationed, "capacity": cap, "reserve": reserve,
                   "price_trace": trace[:150],
                   "certificate": "uniform clearing price = dual variable of capacity; competitive equilibrium "
                                  "(each agent's allocation is its demand at the price, up to the bracket width) "
                                  "implies welfare optimality for non-increasing marginal values"})


def _feasible_allocation(data, output):
    cap, reserve, inc, tasks, _ = _market_inputs(data)
    alloc = output.get("allocation") if isinstance(output, dict) else None
    if not isinstance(alloc, dict) or set(alloc) - {tid for tid, _ in tasks}:
        return None
    x = {tid: alloc.get(tid, 0) for tid, _ in tasks}
    if not all(type(v) is int and 0 <= v <= len(vals) for (tid, vals), v in zip(tasks, x.values())):
        return None
    if sum(x.values()) > cap:
        return None
    return x


def market_verify(data, output, certificate):
    """Competitive-equilibrium inequalities checked directly against the agents' values."""
    cap, reserve, inc, tasks, _ = _market_inputs(data)
    x = _feasible_allocation(data, output)
    price = output.get("clearing_price") if isinstance(output, dict) else None
    eps = 1e-6 * max(1.0, abs(price)) if isinstance(price, (int, float)) else 0.0   # never read from the certificate
    ok_price = isinstance(price, (int, float)) and price >= reserve - 1e-12
    allocated_ok = unallocated_ok = slack_ok = payments_ok = False
    if x is not None and ok_price:
        allocated_ok = all(vals[k] >= price - eps for tid, vals in tasks for k in range(x[tid]))
        unallocated_ok = all(vals[k] <= price + eps for tid, vals in tasks for k in range(x[tid], len(vals)))
        slack_ok = price <= reserve + eps or sum(x.values()) == cap
        pay = output.get("payments")
        payments_ok = isinstance(pay, dict) and all(
            type(pay.get(tid)) in (int, float) and math.isclose(pay[tid], price * x[tid], rel_tol=1e-7, abs_tol=1e-7)
            for tid in x)
    return {"capacity_and_requests_respected": x is not None, "price_at_least_reserve": ok_price,
            "allocated_units_worth_the_price": allocated_ok, "unallocated_units_not_worth_the_price": unallocated_ok,
            "positive_price_only_if_capacity_binds": slack_ok, "payments_are_price_times_units": payments_ok}


def _optimal_welfare(cap, reserve, tasks):
    """Exact optimum by dynamic programming over capacity (independent of greedy sorting)."""
    best = [0.0] * (cap + 1)
    for _, vals in tasks:
        gains = [0.0]
        for v in vals:
            gains.append(gains[-1] + v - reserve)
        new = best[:]
        for c in range(cap + 1):
            for k in range(1, min(len(vals), c) + 1):
                cand = best[c - k] + gains[k]
                if cand > new[c]:
                    new[c] = cand
        best = new
    return max(best)


def market_instance(seed):
    r = random.Random(7_500_000 + seed)
    tasks = []
    for i in range(r.randint(5, 25)):
        v, vals = math.exp(r.gauss(2.0, 0.8)), []
        for _ in range(r.randint(1, 8)):
            vals.append(round(v, 2))
            v *= r.uniform(0.4, 0.95)
        tasks.append({"task_id": f"t{i}", "marginal_values": vals})
    every = sorted(v for t in tasks for v in t["marginal_values"])
    reserve = round(every[int(len(every) * r.uniform(0.1, 0.4))] * r.uniform(0.5, 1.0), 2)
    demand = sum(1 for v in every if v >= reserve)
    cap = max(1, int(demand * r.uniform(0.3, 1.1)))
    data = {"capacity": cap, "reserve": reserve, "increment": round(r.uniform(0.05, 0.5), 3), "tasks": tasks}
    parsed = _market_inputs(data)
    return data, {"optimal_welfare": _optimal_welfare(cap, reserve, parsed[3])}


def market_score(data, truth, output):
    if not isinstance(output, dict) or "allocation" not in output:
        return {"quality": 0.0, "category": "abstain"}
    x = _feasible_allocation(data, output)
    if x is None:
        return {"quality": -1.0, "category": "wrong"}               # capacity or request violated
    cap, reserve, inc, tasks, _ = _market_inputs(data)
    welfare = math.fsum(vals[k] - reserve for tid, vals in tasks for k in range(x[tid]))
    best = truth["optimal_welfare"]
    return {"quality": welfare / best if best > 1e-12 else (1.0 if welfare >= -1e-12 else -1.0),
            "category": "correct"}


def market_proportional(data):
    """Baseline: posted reserve price + pro-rata rationing. Each task requests the units it values at least
    the reserve; if oversubscribed, capacity is split in proportion to requests (largest remainder)."""
    cap, reserve, inc, tasks, _ = _market_inputs(data)
    req = {tid: sum(1 for v in vals if v >= reserve) for tid, vals in tasks}
    total = sum(req.values())
    if total <= cap:
        return {"allocation": req}
    share = {tid: cap * q / total for tid, q in req.items()}
    alloc = {tid: int(math.floor(s)) for tid, s in share.items()}
    left = cap - sum(alloc.values())
    for tid in sorted(share, key=lambda t: (-(share[t] - alloc[t]), t))[:left]:
        alloc[tid] += 1
    return {"allocation": alloc}


def market_central_optimum(data):
    """Competitor: centralized optimum with FULL knowledge of every private value (an upper bound the
    market cannot use): allocate the highest-value units above the reserve until capacity is exhausted."""
    cap, reserve, inc, tasks, _ = _market_inputs(data)
    units = sorted(((v, tid) for tid, vals in tasks for v in vals if v > reserve), key=lambda u: -u[0])[:cap]
    alloc = {tid: 0 for tid, _ in tasks}
    for _, tid in units:
        alloc[tid] += 1
    return {"allocation": alloc}


def market_subregion(data):
    cap, reserve, inc, tasks, _ = _market_inputs(data)
    demand = sum(1 for _, vals in tasks for v in vals if v >= reserve)
    return "oversubscribed" if demand > cap else "slack"


# ============================================================================ 6. flocking (local rules)
FLOCK_R, FLOCK_SPEED, FLOCK_DT = 0.5, 1.0, 0.25          # disc radius, max speed, time step
FLOCK_STEP = FLOCK_SPEED * FLOCK_DT
FLOCK_MARGIN = 0.06       # endpoint clearance 2R + margin keeps continuous clearance >= 2R for steps <= 0.25
FLOCK_SENSE = 3.0         # local rules see only neighbours inside this radius
FLOCK_MAX_AGENTS, FLOCK_MAX_STEPS = 10, 300
FLOCK_MAX_OUTPUT_BYTES = 60_000   # stays under the 64 KiB result contract with room for the envelope


def _flock_inputs(data):
    _require_dict(data)
    starts, goals = data.get("starts"), data.get("goals")
    if (not isinstance(starts, list) or not 2 <= len(starts) <= FLOCK_MAX_AGENTS or not isinstance(goals, list)
            or len(goals) != len(starts)):
        raise GenomeError(f"2-{FLOCK_MAX_AGENTS} starts and as many goals required")
    s = [_point(p, 2, "start") for p in starts]
    g = [_point(p, 2, "goal") for p in goals]
    steps = bounded_int(data.get("steps", FLOCK_MAX_STEPS), low=10, high=FLOCK_MAX_STEPS, name="steps")
    for group in (s, g):
        for i in range(len(group)):
            for j in range(i):
                if math.dist(group[i], group[j]) < 2 * FLOCK_R + 0.2:
                    raise GenomeError("starts (and goals) must be at least 2 radii + 0.2 apart")
    return s, g, steps


def _flock_output(paths, rule):
    makespan = max(len(p) - 1 for p in paths)
    return {"trajectories": [[round(c, 5) for pt in p for c in pt] for p in paths],
            "arrival_steps": [len(p) - 1 for p in paths], "makespan": makespan, "rule": rule}


def _local_step(i, pos, goal, parked):
    """One agent's local rule: sample 16 headings x 2 speeds + stop; keep only moves that stay clear of every
    moving neighbour's CURRENT position by 2R + one neighbour step + margin (safe whatever the neighbour does;
    a parked neighbour needs only 2R + margin; ``parked`` marks agents that have arrived);
    score = progress to goal - crowding near neighbours + a shared right-hand bias when crowded."""
    p = pos[i]
    gx, gy = goal[0] - p[0], goal[1] - p[1]
    dist = math.hypot(gx, gy)
    if dist <= FLOCK_STEP + 1e-12:
        candidates = [(goal[0], goal[1])]
    else:
        candidates = [(p[0], p[1])]
        for k in range(16):
            a = k * math.pi / 8
            for frac in (1.0, 0.5):
                candidates.append((p[0] + math.cos(a) * FLOCK_STEP * frac, p[1] + math.sin(a) * FLOCK_STEP * frac))
    near = [(pos[j], 2 * FLOCK_R + FLOCK_MARGIN + (0.0 if parked[j] else FLOCK_STEP))
            for j in range(len(pos)) if j != i and math.dist(p, pos[j]) < FLOCK_SENSE]
    right = (gy / dist, -gx / dist) if dist > 0 else (0.0, 0.0)
    best, best_score = (p[0], p[1]), -math.inf
    for q in candidates:
        if q != (p[0], p[1]) and any(math.dist(q, n) < bubble for n, bubble in near):
            continue
        progress = dist - math.dist(q, goal)
        crowd = sum(0.02 / max(math.dist(q, n) - 2 * FLOCK_R, 0.05) for n, _ in near)
        side = 0.3 * ((q[0] - p[0]) * right[0] + (q[1] - p[1]) * right[1]) if near else 0.0
        score = progress - crowd + side
        if score > best_score + 1e-12:
            best, best_score = q, score
    return best


def flock_solve(data, budget):
    s, g, steps = _flock_inputs(data)
    pos = [tuple(p) for p in s]
    paths = [[p] for p in pos]
    done = [math.dist(pos[i], g[i]) <= 1e-9 for i in range(len(pos))]
    for _ in range(steps):
        if all(done):
            break
        nxt = [pos[i] if done[i] else _local_step(i, pos, g[i], done) for i in range(len(pos))]
        for i, q in enumerate(nxt):
            if not done[i]:
                paths[i].append(q)
                done[i] = math.dist(q, g[i]) <= 1e-9
        pos = nxt
    cert = {"rules": "16 headings x {1, 0.5} step + stop; clearance bubble from neighbours' current positions; "
                     "progress - crowding + right-hand bias", "sensing_radius": FLOCK_SENSE, "dt": FLOCK_DT,
            "max_speed": FLOCK_SPEED, "radius": FLOCK_R, "steps_budget": steps,
            "evidence": "deterministic simulation; the verifier re-checks every step in continuous time"}
    if not all(done):
        stuck = [i for i, d in enumerate(done) if not d]
        return answer(None, cert | {"unarrived": stuck}, status="ABSTAIN",
                      missing=[f"local rules left {len(stuck)} agent(s) short of their goals within {steps} steps"])
    output = _flock_output(paths, "local_rules")
    size = len(json.dumps(output))
    if size > FLOCK_MAX_OUTPUT_BYTES:
        # the verifier needs every position; long trips at large coordinates exceed the result-size contract
        return answer(None, cert | {"output_bytes": size}, status="ABSTAIN",
                      missing=[f"trajectories need {size} bytes > {FLOCK_MAX_OUTPUT_BYTES}: shorten the trip or "
                               "translate coordinates toward the origin"])
    return answer(output, cert)


def _closest_approach(a0, a1, b0, b1):
    """Minimum distance between two points moving linearly over one step (exact)."""
    dx, dy = a0[0] - b0[0], a0[1] - b0[1]
    vx, vy = (a1[0] - a0[0]) - (b1[0] - b0[0]), (a1[1] - a0[1]) - (b1[1] - b0[1])
    vv = vx * vx + vy * vy
    t = 0.0 if vv == 0 else min(1.0, max(0.0, -(dx * vx + dy * vy) / vv))
    return math.hypot(dx + vx * t, dy + vy * t)


def flock_audit(data, output):
    """Independent kinematic audit of any arm's trajectories: starts, goals, speed limit, continuous-time
    pairwise clearance (agents hold their goals after arrival)."""
    s, g, steps = _flock_inputs(data)
    traj = output.get("trajectories") if isinstance(output, dict) else None
    if not isinstance(traj, list) or len(traj) != len(s):
        return None
    paths = []
    for flat in traj:
        if (not isinstance(flat, list) or len(flat) < 2 or len(flat) % 2
                or not all(type(v) in (int, float) and math.isfinite(v) for v in flat)):
            return None
        paths.append([(flat[k], flat[k + 1]) for k in range(0, len(flat), 2)])
    horizon = max(len(p) for p in paths)
    padded = [p + [p[-1]] * (horizon - len(p)) for p in paths]
    starts_ok = all(math.dist(p[0], s[i]) <= 1e-3 for i, p in enumerate(paths))      # 5-decimal rounding
    goals_ok = all(math.dist(p[-1], g[i]) <= 1e-3 for i, p in enumerate(paths))
    speed_ok = all(math.dist(a, b) <= FLOCK_STEP + 1e-3 for p in paths for a, b in zip(p, p[1:]))
    min_sep = math.inf
    for t in range(horizon - 1):
        for i in range(len(padded)):
            for j in range(i):
                min_sep = min(min_sep, _closest_approach(padded[i][t], padded[i][t + 1], padded[j][t], padded[j][t + 1]))
    return {"starts": starts_ok, "goals": goals_ok, "speed": speed_ok, "within_budget": horizon - 1 <= steps,
            "min_separation": min_sep, "clear": min_sep >= 2 * FLOCK_R - 1e-3, "makespan": horizon - 1}


def flock_verify(data, output, certificate):
    audit = flock_audit(data, output)
    if audit is None:
        return {"trajectories_well_formed": False}
    arrivals = output.get("arrival_steps")
    return {"trajectories_well_formed": True, "starts_match": audit["starts"], "goals_reached": audit["goals"],
            "speed_limit_respected": audit["speed"], "within_step_budget": audit["within_budget"],
            "continuous_clearance": audit["clear"],
            "makespan_reported": type(output.get("makespan")) is int and output["makespan"] == audit["makespan"],
            "arrival_steps_reported": isinstance(arrivals, list) and arrivals == [
                len(flat) // 2 - 1 for flat in output["trajectories"]]}


def flock_straight(data):
    """Baseline: every agent drives straight to its goal at full speed, ignoring the others."""
    s, g, steps = _flock_inputs(data)
    paths = []
    for a, b in zip(s, g):
        n = max(1, math.ceil(math.dist(a, b) / FLOCK_STEP - 1e-9))
        paths.append([(a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n) for k in range(n + 1)])
    return _flock_output(paths, "straight")


def flock_prioritized(data):
    """Competitor: centralized prioritized planning (Erdmann & Lozano-Perez 1987). Agents are planned one at
    a time, longest trip first, by space-time A* (16 headings + wait, the same step limit) that keeps 2R +
    margin from every earlier agent's planned position at each step (held at its goal after arrival) and
    from every not-yet-planned agent's start during the first second (states deduplicated on a 0.1 x 0.1 x
    step lattice); abstains if any agent cannot be planned within 60000 expansions."""
    s, g, steps = _flock_inputs(data)
    order = sorted(range(len(s)), key=lambda i: (-math.dist(s[i], g[i]), i))
    planned = {}
    for i in order:
        reserved = [planned[j] for j in planned]
        waiting = [s[j] for j in range(len(s)) if j != i and j not in planned]
        path = _space_time_astar(s[i], g[i], reserved, waiting, steps)
        if path is None:
            return None
        planned[i] = path
    return _flock_output([planned[i] for i in range(len(s))], "prioritized")


def _space_time_astar(start, goal, reserved, waiting, steps, max_expansions=60000):
    clearance = 2 * FLOCK_R + FLOCK_MARGIN
    horizon = max((len(p) for p in reserved), default=1)
    blocked_cache = {}

    def blocked(t):                     # obstacles at step t: reserved agents (held at goal) + early waiters
        if t not in blocked_cache:
            pts = [path[min(t, len(path) - 1)] for path in reserved]
            blocked_cache[t] = (pts, waiting if t <= 4 else [])
        return blocked_cache[t]

    def free(q, t):
        pts, early = blocked(t)
        # a not-yet-planned agent is still at its start for the first second; afterwards it plans around us
        return (all(math.dist(q, x) >= clearance for x in pts)
                and all(math.dist(q, w) >= clearance + FLOCK_STEP for w in early))

    def cell(q, t):
        return (round(q[0] / 0.1), round(q[1] / 0.1), t)
    moves = [(0.0, 0.0)] + [(math.cos(k * math.pi / 8) * FLOCK_STEP, math.sin(k * math.pi / 8) * FLOCK_STEP)
                            for k in range(16)]
    start = tuple(start)
    goal = tuple(goal)
    heap = [(math.dist(start, goal) / FLOCK_STEP, 0, 0, start)]       # ties on f break toward deeper nodes
    parent, pushed, counter, expansions = {(start, 0): None}, {cell(start, 0)}, 0, 0
    while heap and expansions < max_expansions:
        _, neg_t, _, p = heapq.heappop(heap)
        t = -neg_t
        expansions += 1
        if p == goal:
            if all(free(goal, tt) for tt in range(t, max(horizon, t + 1))):   # goal stays clear afterwards
                path, node = [], (p, t)
                while node is not None:
                    path.append(node[0])
                    node = parent[node]
                return path[::-1]
            continue
        if t + 1 > steps:
            continue
        options = [goal] if math.dist(p, goal) <= FLOCK_STEP + 1e-12 else []
        options += [(p[0] + dx, p[1] + dy) for dx, dy in moves]
        for q in options:
            key = cell(q, t + 1)
            if key in pushed or not free(q, t + 1):
                continue
            pushed.add(key)
            parent[(q, t + 1)] = (p, t)
            counter += 1
            heapq.heappush(heap, (t + 1 + math.dist(q, goal) / FLOCK_STEP, -(t + 1), counter, q))
    return None


def flock_instance(seed):
    """Antipodal swap on a ring (the classic hardest symmetric crossing), lightly perturbed."""
    r = random.Random(7_600_000 + seed)
    for attempt in range(100):
        n = r.randint(4, 8)
        radius = 4.0 + 0.6 * n
        angles = [2 * math.pi * k / n + r.uniform(-0.2, 0.2) for k in range(n)]
        starts = [[round(radius * math.cos(a), 4), round(radius * math.sin(a), 4)] for a in angles]
        goals = [[round(radius * math.cos(a + math.pi + r.uniform(-0.25, 0.25)), 4),
                  round(radius * math.sin(a + math.pi + r.uniform(-0.25, 0.25)), 4)] for a in angles]
        data = {"starts": starts, "goals": goals}
        try:
            _flock_inputs(data)
        except GenomeError:
            continue
        lower = max(math.ceil(math.dist(a, b) / FLOCK_STEP - 1e-9) for a, b in zip(starts, goals))
        return data, {"makespan_lower_bound": lower}
    raise GenomeError("could not generate a valid flock instance")


def flock_score(data, truth, output):
    if output is None:
        return {"quality": 0.0, "category": "abstain"}
    audit = flock_audit(data, output)
    if audit is None or not all(audit[k] for k in ("starts", "goals", "speed", "within_budget", "clear")):
        return {"quality": -1.0, "category": "wrong"}         # a collision, teleport or unreached goal
    return {"quality": truth["makespan_lower_bound"] / max(1, audit["makespan"]), "category": "correct"}


def flock_subregion(data):
    return "four_to_five_agents" if len(data["starts"]) <= 5 else "six_to_eight_agents"


# ============================================================================ genomes
def _common(**kw):
    base = dict(buildability="BUILDABLE_NOW", memory_model="stateless (every call starts from the data)",
                learning_rule="none inside a call; competence settles per geometry through GREG outcomes",
                lineage=LINEAGE)
    base.update(kw)
    return base


INTELLIGENCES = [
    Executable(
        genome=IntelligenceGenome(**_common(
            intelligence_id="collective.quorum.cross_inhibition", version="1.0.1", family="collective_quorum",
            layer=2, operation="quorum_cross_inhibition", epistemic_class="prediction",
            subgeometry="choose among 2-8 alternatives from correlated observers with declared independence groups",
            source_provenance="Condorcet/Nitzan-Paroush weighted voting; design-effect / shared-signal mixture for "
                              "correlated groups; Seeley et al. (2012) cross-inhibition; Bogacz et al. (2006) "
                              "accumulator-to-SPRT reduction",
            native_representation="observers {id, independence group, estimated accuracy, vote} + per-group "
                                  "shared-noise level",
            required_inputs=("alternatives", "observers", "groups"),
            output_contract={"choice": "alternative", "posterior": "{alternative: p}",
                             "support_log_odds": "{alternative: float}", "independent_groups": "int"},
            algorithm_or_runtime="per-group mixture log-likelihood, accumulated in arrival order; support = "
                                 "E_a - logsumexp(E_others); commit when the leader's support >= logit(quorum)",
            parameters={"quorum": "posterior threshold (benchmark 0.55: score break-even 0.5 + 0.05 margin)",
                        "minimum_independent": 3},
            composition_inputs=("observations",), composition_outputs=("choice", "posterior"),
            evidence_type="posterior",
            verification_method="probability-space recomputation from raw votes; partition of observers into "
                                "groups checked; leader and quorum re-derived",
            confidence_semantics="posterior under the declared accuracy and shared-noise model; mis-estimated "
                                 "accuracies or correlations make it miscalibrated",
            resource_profile="O(observers x alternatives), pure Python", latency_profile="sub-millisecond",
            known_strengths=("a correlated faction counts about once, not once per member",
                             "abstains instead of guessing when no alternative reaches quorum"),
            known_failure_modes=("hidden correlation across declared-independent groups",
                                 "accuracies estimated from short histories",
                                 "asymmetric error structure is not modelled"),
            counterindications=("undeclared independence structure", "observers no better than chance",
                                "strategic voters"),
            abstention_conditions=("multi-member group without a shared-noise declaration",
                                   "fewer independent groups than minimum_independent",
                                   "no alternative reaches quorum"),
            benchmark_suite="seeded panels: 4-9 groups (half singletons, factions of 2-9 with shared noise "
                            "0.3-0.95), accuracies estimated from 40-trial histories; dev 0-9 / held-out 1000-1029",
            baseline="simple majority of all observers (each counted as independent; ties abstain)",
            competitor="one vote per declared independence group (the group's accuracy-weighted majority, "
                       "weighted by the log-odds of its mean accuracy); uses the same grouping and accuracies, "
                       "no likelihood model")),
        solve=quorum_solve, verify=quorum_verify, instance=quorum_instance, score=quorum_score,
        baseline=quorum_majority, competitor=quorum_group_majority, subregion=quorum_subregion, tolerance=1e-9,
        notes={"alternative_competitors": "quorum_weighted_majority (group-blind log-odds weights; the competitor "
                                          "before the 2026-10-09 review, mean 0.6 on dev), quorum_best_single (0.4); a "
                                          "design-effect-weighted vote scored 0.8; the group-majority competitor 1.0 "
                                          "(ties the candidate on every dev seed)",
               "score": "+1 correct, -1 wrong, 0 abstain; a single decision per seed"}),
    Executable(
        genome=IntelligenceGenome(**_common(
            intelligence_id="collective.ant_colony.tsp_mmas", version="1.0.1", family="collective_aco",
            layer=2, operation="ant_colony_tour", epistemic_class="optimization",
            subgeometry="symmetric Euclidean TSP, 4-40 cities",
            source_provenance="Dorigo & Gambardella (1997) ACS; Stutzle & Hoos (2000) MAX-MIN Ant System with "
                              "local search; Croes (1958) 2-opt",
            native_representation="city coordinates",
            required_inputs=("cities",),
            output_contract={"tour": "[city index]", "length": "float"},
            algorithm_or_runtime="MMAS (alpha 1, beta 3, evaporation 0.1, p_best 0.05, min(n,20) ants, 150 "
                                 "iterations, restart after 40 stagnant iterations) + 2-opt on the iteration-best ant",
            parameters={"iterations": 150, "ants": "min(n, 20)", "seed": "from data"},
            composition_inputs=("cities",), composition_outputs=("tour", "length"),
            evidence_type="collective_trace",
            verification_method="tour is a permutation; length recomputed with math.hypot; best-length trace "
                                "monotone and ending at the reported length",
            confidence_semantics="a feasible tour and its exact length; no optimality claim",
            resource_profile="numpy; O(iterations x ants x n^2)", latency_profile="0.1-1 s at n <= 40",
            known_strengths=("finds near-reference tours where a single 2-opt descent stalls",
                             "matched OR-Tools guided local search (2000 solutions) on every dev seed at ~1/10 of "
                             "its median latency"),
            known_failure_modes=("stochastic: quality varies with the seed", "slower than one local search",
                                 "no optimality certificate"),
            counterindications=("more than 40 cities (outside the bounded native size)",
                                "asymmetric or non-metric costs (not modelled)", "a certified optimum is required"),
            abstention_conditions=("more than 40 cities",),
            benchmark_suite="30% n=8-12 (Held-Karp exact truth), 70% n=20-40 (multi-start 2-opt + Or-opt reference); "
                            "uniform and clustered; dev 0-9 / held-out 1000-1029",
            baseline="nearest-neighbour tour from city 0",
            competitor="OR-Tools routing: path-cheapest-arc + guided local search, 2000-solution limit "
                       "(deterministic; ortools is a competitor-only dependency)", dependency=None)),
        solve=aco_solve, verify=aco_verify, instance=aco_instance, score=aco_score,
        baseline=aco_nearest_neighbour, competitor=aco_ortools_gls, subregion=aco_subregion, tolerance=1e-7,
        notes={"score": "-(length - reference) / reference; reference is exact (Held-Karp) for n <= 12, a long "
                        "self-contained multi-start 2-opt + Or-opt tour otherwise (can be beaten); arms are ranked by "
                        "tour length either way",
               "alternative_competitor": "aco_nn_two_opt (NN + one 2-opt descent), the competitor before the "
                                         "2026-10-09 review; against it the colony won 7, lost 0, tied 3 on dev",
               "ablation_dev": "without 2-opt (local_search=false) the colony still averaged a 0.69% gap vs 1.66% "
                               "for NN + 2-opt on dev seeds 0-9 (5 wins, 2 losses, 3 ties); the hybrid had a 0.00% "
                               "gap (7 wins, 3 ties)"}),
    Executable(
        genome=IntelligenceGenome(**_common(
            intelligence_id="collective.physarum.conductance_network", version="1.0.1",
            family="collective_physarum", layer=2, operation="conductance_network_design",
            epistemic_class="optimization",
            subgeometry="connect terminals on a candidate graph trading length against single-failure robustness",
            source_provenance="Tero et al. (2007) J. Theor. Biol.; Tero et al. (2010) Science (adaptive network "
                              "model); Kou-Markowsky-Berman (1981) Steiner heuristic for repair comparison",
            native_representation="node coordinates + candidate edges + terminals + lambda",
            required_inputs=("nodes", "edges", "terminals", "lambda"),
            output_contract={"edges": "[[u, v]]", "objective": "float", "length": "float",
                             "expected_disconnected_pairs": "float"},
            algorithm_or_runtime="Kirchhoff flux with one random terminal source and the other terminals as sinks; "
                                 "dD/dt = 2|Q|^mu/(1+|Q|^mu) - D for mu in {0.9, 1.3, 1.8}, 250 steps each; tubes "
                                 "above 6 relative thresholds, repaired to connect terminals and pruned; best "
                                 "objective kept",
            parameters={"mu": [0.9, 1.3, 1.8], "steps": 250, "thresholds": [0.02, 0.05, 0.1, 0.2, 0.35, 0.5]},
            composition_inputs=("network",), composition_outputs=("edges",),
            evidence_type="heuristic_trace",
            verification_method="design edges are candidates; union-find connectivity of all terminals; length "
                                "from coordinates; brute-force single-failure disconnections recomputed",
            confidence_semantics="exact objective of the returned design; no optimality claim",
            resource_profile="numpy dense Laplacian solves (n <= 120)",
            latency_profile="~40-100 ms on the 30-34-node benchmark graphs; ~1 s at 120 nodes with 1000 steps",
            known_strengths=("produces loops when the fault-tolerance weight is high, trees when it is low",),
            known_failure_modes=("conductance dynamics do not optimise the declared objective directly",
                                 "threshold extraction can keep redundant tubes"),
            counterindications=("directed or capacitated networks", "objectives other than length + "
                                "single-failure disconnection"),
            abstention_conditions=("candidate graph does not connect the terminals",),
            benchmark_suite="5-9 terminals + 25 jittered junctions, k=4 nearest-neighbour candidate graph, lambda "
                            "log-uniform over tree-to-redundancy regimes; dev 0-9 / held-out 1000-1029",
            baseline="minimum spanning Steiner tree (KMB metric-closure MST, expanded and pruned)",
            competitor="multi-start Steiner heuristics (KMB + Takahashi-Matsuyama from each terminal) each improved "
                       "by best-improvement local search on the same objective (bridge-bypass paths, single-edge "
                       "additions and removals)")),
        solve=physarum_solve, verify=physarum_verify, instance=physarum_instance, score=physarum_score,
        baseline=physarum_mst, competitor=physarum_multistart_search, subregion=physarum_subregion, tolerance=1e-7,
        notes={"score": "-(length + lambda * E[disconnected terminal pairs | one uniformly random candidate edge "
                        "fails]) / Euclidean terminal-MST length",
               "alternative_competitor": "physarum_mst_augmented (KMB + greedy bridge bypass), the competitor before "
                                         "the 2026-10-09 review: dev 4 wins, 3 losses, 3 ties for the candidate; "
                                         "its KMB trees lost to the candidate's in the low-fault regime"}),
    Executable(
        genome=IntelligenceGenome(**_common(
            intelligence_id="collective.immune.negative_selection", version="1.0.1", family="collective_immune",
            layer=2, operation="negative_selection_detect", epistemic_class="prediction",
            subgeometry="flag non-self points given only self samples, under a false-alarm tolerance",
            source_provenance="Forrest et al. (1994) negative selection; Ji & Dasgupta (2004) V-detector",
            native_representation="self samples + test points (d <= 8) + max_false_alarm_rate",
            required_inputs=("self_samples", "test_points", "max_false_alarm_rate"),
            output_contract={"flagged": "[test index]", "self_radius": "float"},
            algorithm_or_runtime="standardise on self; 3000 candidate detectors (half uniform in [-6,6]^d, half "
                                 "N(0, s^2 I) around the self centroid, s in {1,2,3}); reach = distance to nearest "
                                 "self; self radius = 3-fold cross-fitted conformal quantile of self depth at "
                                 "0.75 x tolerance; final detectors censored on all self (conservative)",
            parameters={"detectors": 3000, "calibration": "3-fold cross-fitted conformal", "target": "0.75 x tol",
                        "universe": UNIVERSE},
            composition_inputs=("self_samples", "test_points"), composition_outputs=("flagged",),
            evidence_type="statistical_estimate",
            verification_method="pure-Python witness geometry: each flag lies inside a detector whose radius plus "
                                "the self radius stays clear of every training self sample (or outside the "
                                "universe); standardisation recomputed; calibration arithmetic (target, conformal "
                                "rank, held-back count) checked against the declared tolerance. The held-back "
                                "detector depths that set the self radius are NOT recomputed, so an under-stated "
                                "self radius is not refutable by the verifier, and an omitted flag (a subset of the "
                                "flag set) is not detected",
            confidence_semantics="the false-alarm rate is a calibrated estimate on held-back self, not a guarantee",
            resource_profile="numpy; O(detectors x (self + test) x d)",
            latency_profile="~0.2-0.3 s on the benchmark (300-500 self samples, 220-240 test points)",
            known_strengths=("needs no non-self examples", "every alarm has a geometric witness"),
            known_failure_modes=("its score is only a covered lower bound on distance to self: coverage holes miss "
                                 "anomalies near self", "weak in higher dimension",
                                 "loses to a covariance model when self is Gaussian (lost every dev seed to the "
                                 "exact Gaussian prediction region)"),
            counterindications=("dimension above 8", "fewer than 60 self samples", "self data known to be Gaussian"),
            abstention_conditions=("dimension above 8", "fewer than 60 self samples",
                                   "more than 300 test points in one call (split the batch)",
                                   "too few self samples for the tolerance: (n + 1) x 0.75 x tolerance < 1"),
            benchmark_suite="multivariate-normal self (d 2-6, random covariance), anomalies: correlation breaks, "
                            "shifts of 3-5 Mahalanobis units, inflated variance; tolerance 0.01-0.05; dev 0-9 / "
                            "held-out 1000-1029",
            baseline="per-feature z-score, Bonferroni threshold",
            competitor="exact Gaussian prediction ellipsoid (Hotelling: sample mean/covariance, F quantile) at the "
                       "same 0.75 x tolerance target (scipy for the quantile)")),
        solve=immune_solve, verify=immune_verify, instance=immune_instance, score=immune_score,
        baseline=immune_zscore, competitor=immune_prediction_region, subregion=immune_subregion, tolerance=1e-9,
        notes={"score": "F1 on the non-self class; false alarms above the 95% binomial bound of the tolerance = "
                        "wrong (-1); abstain 0",
               "alternative_competitor": "immune_mahalanobis (asymptotic chi-square at the full tolerance), the "
                                         "competitor before the 2026-10-09 review; it ignored estimation error and "
                                         "the candidate's 0.75 safety factor and produced 1 wrong answer on dev, "
                                         "which is why the candidate's mean once looked higher"}),
    Executable(
        genome=IntelligenceGenome(**_common(
            intelligence_id="collective.market.clock_auction", version="1.0.0", family="collective_market",
            layer=2, operation="clock_auction_allocate", epistemic_class="optimization",
            subgeometry="allocate a divisible-in-units compute/attention capacity across tasks with private, "
                        "non-increasing marginal values",
            source_provenance="Walras tatonnement; Ausubel (2004) ascending clock auctions; first welfare theorem "
                              "for concave valuations (LP duality)",
            native_representation="capacity + reserve price + per-task marginal values (queried only as demand)",
            required_inputs=("capacity", "reserve", "tasks"),
            output_contract={"allocation": "{task: units}", "clearing_price": "float", "payments": "{task: float}",
                             "rounds": "int"},
            algorithm_or_runtime="ascending price clock from the reserve (accelerating every 50 rounds), bisection "
                                 "of the final bracket, tie-band rationing at the lower bracket price",
            parameters={"increment": "from data", "max_rounds": 5000},
            composition_inputs=("tasks", "capacity"), composition_outputs=("allocation", "clearing_price"),
            evidence_type="optimality_certificate",
            verification_method="competitive-equilibrium inequalities against the agents' values: allocated units "
                                "worth >= price, unallocated <= price, positive price only with binding capacity, "
                                "price >= reserve, payments = price x units",
            confidence_semantics="welfare-optimal up to (bracket width x units) when agents report demand "
                                 "truthfully as price takers",
            resource_profile="O(rounds x tasks x log units)", latency_profile="milliseconds",
            known_strengths=("needs only demand queries, never the private values",
                             "the clearing price certifies optimality"),
            known_failure_modes=("strategic demand reduction by large bidders is not modelled",
                                 "complementarities (increasing marginal values) break equilibrium existence"),
            counterindications=("increasing marginal values / bundles", "strategic bidders with market power"),
            abstention_conditions=("any task with increasing marginal values",),
            benchmark_suite="5-25 tasks with 1-8 lognormal, geometrically decreasing unit values, reserve near a "
                            "low value quantile, capacity 30-110% of demand; dev 0-9 / held-out 1000-1029",
            baseline="posted reserve price + pro-rata rationing by request",
            competitor="centralized optimum with full knowledge of every private value (an upper bound that uses "
                       "information the market never sees)")),
        solve=market_solve, verify=market_verify, instance=market_instance, score=market_score,
        baseline=market_proportional, competitor=market_central_optimum, subregion=market_subregion,
        tolerance=1e-6,
        notes={"score": "realized welfare above the reserve / DP optimum; capacity or request violation = wrong (-1)",
               "information_asymmetry": "the competitor reads private values; the market only queries demand"}),
    Executable(
        genome=IntelligenceGenome(**_common(
            intelligence_id="collective.flock.local_rules", version="1.0.1", family="collective_flock",
            layer=2, operation="flock_navigate", epistemic_class="physical",
            subgeometry="2-10 discs (radius 0.5, speed <= 1) move to goals in the open plane without contact",
            source_provenance="Reynolds (1987) boids (separation + goal seeking); social-force / sampled-velocity "
                              "local planners; right-hand convention for symmetric crossings",
            native_representation="start and goal points per agent",
            required_inputs=("starts", "goals"),
            output_contract={"trajectories": "[[x0, y0, x1, y1, ...] per agent]", "arrival_steps": "[int]",
                             "makespan": "int", "rule": "str"},
            algorithm_or_runtime="synchronous steps (dt 0.25): each agent samples 33 moves, keeps those clear of "
                                 "neighbours (sensing radius 3) by 2R + one step + margin, maximises progress - "
                                 "crowding + right-hand bias",
            parameters={"sensing_radius": FLOCK_SENSE, "dt": FLOCK_DT, "max_speed": FLOCK_SPEED,
                        "radius": FLOCK_R, "steps": FLOCK_MAX_STEPS},
            composition_inputs=("starts", "goals"), composition_outputs=("trajectories",),
            evidence_type="simulation",
            verification_method="independent kinematic audit: starts, goals, per-step speed, exact continuous-time "
                                "closest approach of every pair on every step",
            confidence_semantics="contact-free by construction of the clearance bubble inside the modelled "
                                 "kinematics; says nothing about real robots, sensing noise or delays",
            resource_profile="O(steps x agents^2 x 33), pure Python", latency_profile="~10-30 ms",
            known_strengths=("decentralised: each agent uses only neighbours within 3 units",
                             "never collides in the model; ~35x lower median latency than centralized planning "
                             "on dev seeds 0-9"),
            known_failure_modes=("deadlock or livelock in dense symmetric crowds (then abstains)",
                                 "longer makespan than centralized planning"),
            counterindications=("obstacle-filled maps (no static obstacles modelled)", "more than 10 agents",
                                "safety-critical physical deployment"),
            abstention_conditions=("any agent short of its goal within the step budget",
                                   "trajectories larger than 60000 bytes (result-size contract)"),
            benchmark_suite="4-8 agents in perturbed antipodal swaps on a ring; dev 0-9 / held-out 1000-1029",
            baseline="straight-to-goal at full speed (ignores the others)",
            competitor="centralized prioritized planning: space-time A* per agent (longest trip first) around "
                       "earlier agents' reserved trajectories")),
        solve=flock_solve, verify=flock_verify, instance=flock_instance, score=flock_score,
        baseline=flock_straight, competitor=flock_prioritized, subregion=flock_subregion, tolerance=1e-9,
        notes={"score": "makespan lower bound / makespan; any contact, speed violation or unreached goal = wrong "
                        "(-1); abstain 0"}),
]
