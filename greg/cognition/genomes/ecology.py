"""Layer 2 collective intelligence: ecology bidding for a compute budget among solver species.

The 2026-10-21 coverage record (``docs/collaboration/MIND-COVERAGE-2026-10-21.md``, section 31 item 1 and the
L2.ecological row) says "methods do not bid; no ecology executor". ``collective_auction`` (``collective_b``) is a
priced task market over *known* values; it does not answer the open question GREG's own evidence raised. In
antifragility v3b (``tests/evidence/antifragility-v3b-2026-10-22/README.md``) learned per-cell routing between two
methods lost to spending the same compute on four restarts of the incumbent (131 against 174 of 200), and best-of-both
at twice the compute scored 180. The question here: given a batch of heterogeneous tasks and a fixed total compute
budget, how should runs be allocated among several solver species (and restarts of one species) whose per-context
competence is uncertain and is learned only from outcomes?

Effect, not metaphor: "ecology bidding" is translated as *methods compete for compute through bids grounded in their
own scored track record, a reputation built from a proper scoring rule keeps those bids honest, and a budgeted
auction allocates runs*. Nothing here is a simulated organism.

* ``collective_ecology_bidding`` (``allocate_compute_by_ecology``). Tasks arrive in a declared order; before each task
  the allocator commits a bundle of runs (how many runs of each species, restarts included) and then sees those runs'
  outcomes. Mechanism, per task:

  1. each species m holds a Beta track record per context (warm-up history plus every outcome so far) and *claims*
     a success probability for the task's context: its posterior mean plus ``EC_Z`` posterior standard deviations
     (a self-interested, optimistic claim: species want work);
  2. the market discounts each claim by the species' reputation w_m in [0, 1]: the effective probability is
     mean + w_m (claim - mean). Reputation is a proper-scoring account: each executed run scores the species' claim
     and its own posterior mean by the Brier rule against the outcome, and w_m = min(1, exp(-``EC_ETA`` x cumulative
     excess Brier of claim over mean)). A species whose optimism is not borne out (overclaiming) loses its bonus;
     one whose optimism is borne out (an under-explored good species) keeps it;
  3. a budgeted auction over the current and every remaining task: each (task, species) pair bids its marginal
     expected value per budget unit, value x P(task still unsolved | runs already awarded) x effective probability /
     cost; the highest bid that fits the remaining budget wins one run, the task's later bids fall (diminishing
     returns), and the auction repeats until no affordable bid remains (greedy by bid per cost). Only the current
     task's awards are committed (receding horizon); the reserved budget is re-auctioned at the next task. The bid
     per cost of the last award is recorded as the clearing price of a budget unit;
  4. the committed runs execute, their outcomes are revealed, track records and reputations update online.

  Restarts are native: a second run of the same species on a task is just another bid.

Native geometry (declared in ``greg/cognition/worlds.py``; synthetic, a *simulated world*): 3-5 species with integer
costs 1-3; 3-6 task contexts; 24-36 tasks with integer values 1-20; a total budget of 1.2-3.5 units per task. Each run
of species m on a task of context c succeeds independently with probability p[m][c], hidden from every allocator.
Four regimes by seed mod 4: specialists (each species good on its own contexts), dominant (one species good
everywhere: the restart regime of antifragility v3b), mixed (additive logit competence, stronger species cost more)
and stale history (the warm-up record was produced by a context-shuffled competence table, so it misleads). The
warm-up history gives 0..d observations per (species, context) cell, d drawn from {1, 3, 8}.

Replay environment: the request carries each (task, species) outcome tape (the outcomes its 1st, 2nd, ... run would
have). A tape is the declared, seeded randomness of the world, so every arm faces the same outcomes (common random
numbers); an allocator may read tape i only after committing task i's bundle, and only the prefix it bought. This is
the standard replay evaluation of online allocators; non-anticipation of every arm here is checked by unit tests
(changing any unrevealed tape entry never changes an earlier decision), not by the verifier, which cannot see a
policy's reasoning.

Truth and score: because a task's bundle is committed before its own outcomes are seen, the expected value of task i
given its bundle x_i is exactly v_i (1 - prod_m (1 - p[m][c_i])^x_im). The oracle knows p and solves the static
problem exactly: a bounded knapsack per task (maximise sum_m x_m (-log(1 - p_m)) under each budget level) and a group
knapsack across tasks. No non-anticipating policy can exceed that oracle value E* in expectation or for its realised
bundles, so quality = (exact expected value of the arm's committed bundles) / E*, in [0, 1].

Arms:
* baseline: static allocation. The whole budget goes to the single species with the best pooled warm-up success
  rate per unit cost (Laplace-smoothed), split evenly across tasks (leftover runs to the earliest tasks). No learning.
* competitor: the certainty-equivalent online allocator: the same receding-horizon budgeted greedy planner fed the
  (species, context) Beta posterior means from the same warm-up history, updated online from the same revealed
  outcomes (greedy / certainty equivalence, the standard exploit-only rule for allocation under learned rates). Why
  the strongest honest choice: on development seeds 0-9 it was the strongest of the three standard online
  allocators measured with the candidate's planner and information (mean quality: certainty equivalent 0.797,
  UCB-style optimism with every claim at full weight 0.789, contextual Thompson sampling 0.735; the candidate 0.792),
  and it shares the candidate's planner, so the comparison isolates the ecology's mechanism (optimistic claims
  disciplined by a shared proper-scoring reputation). Thompson sampling (Thompson 1933; Agrawal and Goyal 2012) was
  the pre-registered competitor; it is kept as ``ecology_thompson`` and reported in ``notes``, not used by the rule.
  The certainty-equivalent rule is the candidate with every reputation at 0, so the candidate wins only where its
  reputation-kept optimism pays.

Verification (independent of every solver code path): the output's bundles are re-parsed and their budget feasibility
(integer counts, at most the tape length, total cost within budget) recomputed; the declared realised outcomes are
recomputed from the outcome tapes (a task is solved when any bought run's tape entry is 1); the declared spend, solved
flags and realised value must equal the recomputation; the certificate's reputations and clearing prices must be
well-formed. The verifier cannot recompute the expected value (p is hidden from requests); ``score`` does, from the
generator's truth.

Disclosure (directive requirement 4): the constants ``EC_Z`` = 1.0 and ``EC_ETA`` = 10.0, the regimes, the generator,
the baseline and the candidate were fixed before any development run and were not changed after one. One change was
made after seeing development results, and it makes the candidate's comparison harder, not easier: the
pre-registered competitor was contextual Thompson sampling (mean quality 0.735 on seeds 0-9, below the candidate's
0.792, 7-3 for the candidate). A diagnostic on the same seeds (no generator, constant or candidate change) found the
certainty-equivalent allocator stronger (0.797; 6-4 against the candidate), so it replaced Thompson sampling as the
competitor (requirement 2: the strongest appropriate method). On those seeds the candidate's reputations fell to
near 0 for most species, so it behaves mostly like the certainty-equivalent rule; ``EC_ETA`` was not retuned.

Everything is read-only computation: no files, network, subprocesses or environment access, and no output creates
authority. Development seeds 0-9 only.
"""
from __future__ import annotations

import heapq
import math
import random

from .contract import Executable, GenomeError, IntelligenceGenome, answer, bounded_int

LINEAGE = ("INTENT-20261007-POLYINTELLIGENCE-MIND-CONTINUATION", "INTENT-20261007-VERIFIED-POLYINTELLIGENCE-LIFT",
           "INTENT-20261021-MIND-MAXIMUM-CONTINUATION section 4 (restore the full five-layer scope)",
           "docs/collaboration/MIND-COVERAGE-2026-10-21.md (section 31 item 1: ecology bidding has no executor)",
           "tests/evidence/antifragility-v3b-2026-10-22 (compute-matched restarts beat learned routing)")

EC_Z = 1.0                 # a species' claim: posterior mean + EC_Z posterior standard deviations
EC_ETA = 10.0              # reputation: w = min(1, exp(-EC_ETA x cumulative excess Brier of claim over mean))
EC_MAX_SPECIES, EC_MAX_CONTEXTS, EC_MAX_TASKS = 8, 16, 80
EC_MAX_COST, EC_MAX_VALUE, EC_MAX_BUDGET, EC_MAX_TAPE = 10, 1000, 1000, 20
EC_MAX_TRIALS = 10_000
EC_MAX_WORK = 200_000      # tasks x budget x species: above it the planner abstains (UNKNOWN)
EC_P_CLIP = (1e-3, 0.999)
EC_REGIMES = ("specialists", "dominant", "mixed", "stale_history")
EC_TAPE = 10
_DEV = "seeds 0-9 dev, held-out seeds fixed by the admission freeze"


# ------------------------------------------------------------------ input
def _input(data):
    """Validated request: costs[K], contexts[N], values[N], n_contexts, budget, hist s[K][C] and n[K][C],
    tapes[N][K] (strings), tape length R, rng seed."""
    if not isinstance(data, dict):
        raise GenomeError("data must be a JSON object")
    species, tasks = data.get("species"), data.get("tasks")
    if not isinstance(species, list) or not 1 <= len(species) <= EC_MAX_SPECIES:
        raise GenomeError(f"species: 1-{EC_MAX_SPECIES} objects with an integer cost")
    costs = []
    for s in species:
        if not isinstance(s, dict) or set(s) != {"name", "cost"} or not isinstance(s["name"], str):
            raise GenomeError("each species is {name, cost}")
        costs.append(bounded_int(s["cost"], low=1, high=EC_MAX_COST, name="species cost"))
    k = len(costs)
    n_ctx = bounded_int(data.get("contexts"), low=1, high=EC_MAX_CONTEXTS, name="contexts")
    if not isinstance(tasks, list) or not 1 <= len(tasks) <= EC_MAX_TASKS:
        raise GenomeError(f"tasks: 1-{EC_MAX_TASKS} objects {{context, value}}")
    ctx, vals = [], []
    for t in tasks:
        if not isinstance(t, dict) or set(t) != {"context", "value"}:
            raise GenomeError("each task is {context, value}")
        ctx.append(bounded_int(t["context"], low=0, high=n_ctx - 1, name="task context"))
        vals.append(bounded_int(t["value"], low=0, high=EC_MAX_VALUE, name="task value"))
    budget = bounded_int(data.get("budget"), low=0, high=EC_MAX_BUDGET, name="budget")
    hs = [[0] * n_ctx for _ in range(k)]
    hn = [[0] * n_ctx for _ in range(k)]
    history, seen = data.get("warmup_history"), set()
    if not isinstance(history, list) or len(history) > k * n_ctx:
        raise GenomeError("warmup_history: a list of [species, context, successes, trials], one per cell")
    for row in history:
        if not isinstance(row, list) or len(row) != 4:
            raise GenomeError("warmup_history rows are [species, context, successes, trials]")
        m = bounded_int(row[0], low=0, high=k - 1, name="history species")
        c = bounded_int(row[1], low=0, high=n_ctx - 1, name="history context")
        n = bounded_int(row[3], low=0, high=EC_MAX_TRIALS, name="history trials")
        s = bounded_int(row[2], low=0, high=n, name="history successes")
        if (m, c) in seen:
            raise GenomeError("warmup_history repeats a (species, context) cell")
        seen.add((m, c))
        hs[m][c], hn[m][c] = s, n
    tapes = data.get("outcome_tape")
    if not isinstance(tapes, list) or len(tapes) != len(tasks):
        raise GenomeError("outcome_tape: one row per task")
    length = None
    for row in tapes:
        if not isinstance(row, list) or len(row) != k:
            raise GenomeError("outcome_tape rows hold one string per species")
        for tape in row:
            if not isinstance(tape, str) or not 1 <= len(tape) <= EC_MAX_TAPE or set(tape) - {"0", "1"}:
                raise GenomeError(f"each outcome tape is a 1-{EC_MAX_TAPE} character string of 0 and 1")
            if length is None:
                length = len(tape)
            elif len(tape) != length:
                raise GenomeError("every outcome tape has the same length")
    seed = bounded_int(data.get("rng_seed"), low=0, high=2 ** 31 - 1, name="rng_seed")
    return costs, ctx, vals, n_ctx, budget, hs, hn, tapes, length, seed


# ------------------------------------------------------------------ shared planner (candidate and competitor)
def _plan(p, costs, ctx, vals, start, budget, cap):
    """Receding-horizon budgeted greedy auction over tasks start..N-1 with success probabilities p[m][c]: repeatedly
    award one run to the highest marginal expected value per budget unit that still fits. Returns (bundle of task
    ``start``, clearing price = bid per cost of the last award, or 0.0)."""
    k, n = len(costs), len(ctx)
    fail = [1.0] * n
    count = [[0] * k for _ in range(n)]
    version = [0] * n
    heap = []

    def push(j):
        for m in range(k):
            if count[j][m] < cap:
                bid = vals[j] * fail[j] * p[m][ctx[j]] / costs[m]
                if bid > 0:
                    heapq.heappush(heap, (-bid, j, m, version[j]))
    for j in range(start, n):
        push(j)
    price = 0.0
    while heap:
        neg, j, m, ver = heapq.heappop(heap)
        if ver != version[j] or costs[m] > budget or count[j][m] >= cap:
            continue
        budget -= costs[m]
        count[j][m] += 1
        fail[j] *= 1.0 - p[m][ctx[j]]
        version[j] += 1
        price = -neg
        push(j)
    return count[start], price


def _reveal(tapes, i, bundle):
    """The outcomes an allocator may read after committing task i's bundle: the bought prefix of each tape."""
    return [tapes[i][m][:x] for m, x in enumerate(bundle)]


def _finish(costs, vals, tapes, bundles):
    spend = sum(costs[m] * x for b in bundles for m, x in enumerate(b))
    solved = [any("1" in tapes[i][m][:x] for m, x in enumerate(b)) for i, b in enumerate(bundles)]
    return {"bundles": bundles, "spend": spend, "solved": solved,
            "realised_value": sum(v for v, s in zip(vals, solved) if s)}


def _clip(x):
    return min(EC_P_CLIP[1], max(EC_P_CLIP[0], x))


# ------------------------------------------------------------------ candidate: ecology bidding
def ecology_solve(data, budget=None):
    costs, ctx, vals, n_ctx, total, hs, hn, tapes, cap, _ = _input(data)
    k, n = len(costs), len(ctx)
    if n * max(total, 1) * k > EC_MAX_WORK:
        return answer(None, {}, status="UNKNOWN",
                      missing=[f"planning work tasks x budget x species above {EC_MAX_WORK}"])
    s = [row[:] for row in hs]
    t = [row[:] for row in hn]
    excess = [0.0] * k
    reputation = [1.0] * k
    remaining, bundles, prices, scored = total, [], [], 0
    for i in range(n):
        mean = [[(s[m][c] + 1) / (t[m][c] + 2) for c in range(n_ctx)] for m in range(k)]
        claim = [[_clip(mean[m][c] + EC_Z * math.sqrt(mean[m][c] * (1 - mean[m][c]) / (t[m][c] + 3)))
                  for c in range(n_ctx)] for m in range(k)]
        eff = [[_clip(mean[m][c] + reputation[m] * (claim[m][c] - mean[m][c])) for c in range(n_ctx)]
               for m in range(k)]
        bundle, price = _plan(eff, costs, ctx, vals, i, remaining, cap)
        remaining -= sum(costs[m] * x for m, x in enumerate(bundle))
        bundles.append(list(bundle))
        prices.append(round(price, 9))
        c = ctx[i]
        for m, seen in enumerate(_reveal(tapes, i, bundle)):
            for ch in seen:
                y = 1.0 if ch == "1" else 0.0
                excess[m] += (claim[m][c] - y) ** 2 - (mean[m][c] - y) ** 2     # Brier: claim against own mean
                scored += 1
            s[m][c] += seen.count("1")
            t[m][c] += len(seen)
            reputation[m] = min(1.0, math.exp(-EC_ETA * excess[m]))
    certificate = {"mechanism": "optimistic species claims x proper-scoring reputation -> budgeted greedy auction, "
                                "receding horizon",
                   "reputation": [round(w, 9) for w in reputation], "clearing_prices": prices,
                   "claims_scored": scored, "z": EC_Z, "eta": EC_ETA}
    return answer(_finish(costs, vals, tapes, bundles), certificate)


# ------------------------------------------------------------------ baseline and competitor
def ecology_baseline(data):
    """Static: the single species with the best pooled warm-up success rate per unit cost, budget split evenly."""
    costs, ctx, vals, n_ctx, total, hs, hn, tapes, cap, _ = _input(data)
    k, n = len(costs), len(ctx)
    rate = [(sum(hs[m]) + 1) / (sum(hn[m]) + 2) / costs[m] for m in range(k)]
    best = max(range(k), key=lambda m: (rate[m], -m))
    each = min(cap, total // (n * costs[best]))
    left = total - each * n * costs[best]
    bundles = []
    for i in range(n):
        x = each
        if x < cap and left >= costs[best]:
            x += 1
            left -= costs[best]
        bundles.append([x if m == best else 0 for m in range(k)])
    return _finish(costs, vals, tapes, bundles)


def ecology_thompson(data):
    """Contextual Thompson sampling over (species, context) Beta posteriors with the same planner and information."""
    costs, ctx, vals, n_ctx, total, hs, hn, tapes, cap, seed = _input(data)
    k, n = len(costs), len(ctx)
    if n * max(total, 1) * k > EC_MAX_WORK:
        return None
    rng = random.Random(seed)
    s = [row[:] for row in hs]
    t = [row[:] for row in hn]
    remaining, bundles = total, []
    for i in range(n):
        sample = [[_clip(rng.betavariate(s[m][c] + 1, t[m][c] - s[m][c] + 1)) for c in range(n_ctx)]
                  for m in range(k)]
        bundle, _ = _plan(sample, costs, ctx, vals, i, remaining, cap)
        remaining -= sum(costs[m] * x for m, x in enumerate(bundle))
        bundles.append(list(bundle))
        for m, seen in enumerate(_reveal(tapes, i, bundle)):
            s[m][ctx[i]] += seen.count("1")
            t[m][ctx[i]] += len(seen)
    return _finish(costs, vals, tapes, bundles)


def ecology_certainty_equivalent(data):
    """Certainty equivalence: the same planner and information, fed the Beta posterior means (exploit only)."""
    costs, ctx, vals, n_ctx, total, hs, hn, tapes, cap, _ = _input(data)
    k, n = len(costs), len(ctx)
    if n * max(total, 1) * k > EC_MAX_WORK:
        return None
    s = [row[:] for row in hs]
    t = [row[:] for row in hn]
    remaining, bundles = total, []
    for i in range(n):
        mean = [[_clip((s[m][c] + 1) / (t[m][c] + 2)) for c in range(n_ctx)] for m in range(k)]
        bundle, _ = _plan(mean, costs, ctx, vals, i, remaining, cap)
        remaining -= sum(costs[m] * x for m, x in enumerate(bundle))
        bundles.append(list(bundle))
        for m, seen in enumerate(_reveal(tapes, i, bundle)):
            s[m][ctx[i]] += seen.count("1")
            t[m][ctx[i]] += len(seen)
    return _finish(costs, vals, tapes, bundles)


# ------------------------------------------------------------------ independent verifier
def ecology_verify(data, output, certificate):
    """Recompute budget feasibility and realised outcomes from the request's tapes; never calls solver code."""
    checks = {"well_formed": False, "budget_feasible": False, "spend_recomputed": False,
              "outcomes_replayed": False, "realised_value_recomputed": False, "certificate_well_formed": False}
    try:
        species, tasks, tape = data["species"], data["tasks"], data["outcome_tape"]
        cost = [int(sp["cost"]) for sp in species]
        value = [int(tk["value"]) for tk in tasks]
        limit, width = int(data["budget"]), len(tape[0][0])
    except (KeyError, TypeError, ValueError, IndexError):
        return checks
    if not isinstance(output, dict) or set(output) != {"bundles", "spend", "solved", "realised_value"}:
        return checks
    bundles = output["bundles"]
    if (not isinstance(bundles, list) or len(bundles) != len(tasks)
            or not all(isinstance(b, list) and len(b) == len(cost) for b in bundles)
            or not all(type(x) is int and 0 <= x <= width for b in bundles for x in b)):
        return checks
    checks["well_formed"] = True
    spent = 0
    for b in bundles:
        for m in range(len(cost)):
            spent += cost[m] * b[m]
    checks["budget_feasible"] = spent <= limit
    checks["spend_recomputed"] = type(output["spend"]) is int and output["spend"] == spent
    solved = []
    for i, b in enumerate(bundles):
        hit = False
        for m in range(len(cost)):
            for r in range(b[m]):
                if tape[i][m][r] == "1":
                    hit = True
        solved.append(hit)
    checks["outcomes_replayed"] = (isinstance(output["solved"], list)
                                   and all(type(x) is bool for x in output["solved"]) and output["solved"] == solved)
    total = 0
    for i in range(len(tasks)):
        if solved[i]:
            total += value[i]
    checks["realised_value_recomputed"] = type(output["realised_value"]) is int and output["realised_value"] == total
    cert = certificate if isinstance(certificate, dict) else {}
    rep, prices = cert.get("reputation"), cert.get("clearing_prices")
    checks["certificate_well_formed"] = (
        isinstance(rep, list) and len(rep) == len(cost)
        and all(type(w) in (int, float) and math.isfinite(w) and 0 <= w <= 1 for w in rep)
        and isinstance(prices, list) and len(prices) == len(tasks)
        and all(type(x) in (int, float) and math.isfinite(x) and x >= 0 for x in prices))
    return checks


# ------------------------------------------------------------------ simulated world, oracle and score
def ecology_instance(seed):
    """A seeded simulated world (see the module docstring). Truth: the hidden competence table, the regime and the
    exact oracle value of the static problem under known probabilities."""
    r = random.Random(f"genome:collective_ecology_bidding:{seed}")
    regime = EC_REGIMES[seed % 4]
    k, n_ctx, n = r.randint(3, 5), r.randint(3, 6), r.randint(24, 36)
    costs = [r.randint(1, 3) for _ in range(k)]
    p = [[0.0] * n_ctx for _ in range(k)]
    if regime == "specialists":
        home = [set() for _ in range(k)]
        for c in range(n_ctx):
            home[r.randrange(k)].add(c)
        for m in range(k):
            if r.random() < 0.5:
                home[m].add(r.randrange(n_ctx))
            for c in range(n_ctx):
                p[m][c] = r.uniform(0.45, 0.85) if c in home[m] else r.uniform(0.03, 0.25)
    elif regime == "dominant":
        d = r.randrange(k)
        for m in range(k):
            for c in range(n_ctx):
                if m == d:
                    p[m][c] = r.uniform(0.35, 0.6)
                elif r.random() < 0.2:
                    p[m][c] = r.uniform(0.3, 0.7)
                else:
                    p[m][c] = r.uniform(0.03, 0.3)
    else:                                                  # mixed and stale_history: additive logit competence
        a = [r.gauss(-1.0, 0.8) + 0.5 * (costs[m] - 2) for m in range(k)]
        b = [r.gauss(0.0, 0.8) for _ in range(n_ctx)]
        for m in range(k):
            for c in range(n_ctx):
                p[m][c] = 1 / (1 + math.exp(-(a[m] + b[c] + r.gauss(0.0, 0.8))))
    p = [[min(0.95, max(0.02, x)) for x in row] for row in p]
    if regime == "stale_history":
        perm = list(range(n_ctx))
        r.shuffle(perm)
        p_hist = [[p[m][perm[c]] for c in range(n_ctx)] for m in range(k)]
    else:
        p_hist = p
    depth = r.choice((1, 3, 8))
    history = []
    for m in range(k):
        for c in range(n_ctx):
            trials = r.randint(0, depth)
            history.append([m, c, sum(r.random() < p_hist[m][c] for _ in range(trials)), trials])
    tasks = [{"context": r.randrange(n_ctx), "value": r.randint(1, 20)} for _ in range(n)]
    budget = round(n * r.uniform(1.2, 3.5))
    tape = [["".join("1" if r.random() < p[m][t["context"]] else "0" for _ in range(EC_TAPE)) for m in range(k)]
            for t in tasks]
    data = {"species": [{"name": f"species_{m}", "cost": costs[m]} for m in range(k)], "contexts": n_ctx,
            "tasks": tasks, "budget": budget, "warmup_history": history, "outcome_tape": tape,
            "rng_seed": r.randrange(2 ** 31)}
    oracle = oracle_value(p, costs, [t["context"] for t in tasks], [t["value"] for t in tasks], budget, EC_TAPE)
    return data, {"p": p, "regime": regime, "oracle_value": oracle, "history_depth": depth}


def oracle_value(p, costs, ctx, vals, budget, cap):
    """Exact optimum of sum_i v_i (1 - prod_m (1 - p[m][c_i])^x_im) over integer bundles with x_im <= cap and total
    cost <= budget: per task a bounded knapsack on -log(1 - p) (the value is increasing in it), then a group knapsack
    across tasks. Evaluation side only: never called by an allocator or the verifier."""
    k = len(costs)
    best = [0.0] * (budget + 1)
    for i in range(len(ctx)):
        weight = [-math.log(1.0 - p[m][ctx[i]]) for m in range(k)]
        logs = [0.0] * (budget + 1)                       # max sum x_m weight_m with cost <= b
        for m in range(k):
            for _ in range(cap):                          # bounded: cap copies of item m, 0/1 each
                for b in range(budget, costs[m] - 1, -1):
                    cand = logs[b - costs[m]] + weight[m]
                    if cand > logs[b]:
                        logs[b] = cand
        gain = [vals[i] * (1.0 - math.exp(-x)) for x in logs]
        nxt = [0.0] * (budget + 1)
        for b in range(budget + 1):
            nxt[b] = max(best[b - u] + gain[u] for u in range(b + 1))
        best = nxt
    return best[budget]


def expected_value(p, ctx, vals, bundles):
    total = 0.0
    for i, bundle in enumerate(bundles):
        fail = 1.0
        for m, x in enumerate(bundle):
            fail *= (1.0 - p[m][ctx[i]]) ** x
        total += vals[i] * (1.0 - fail)
    return total


def ecology_score(data, truth, output):
    if output is None:
        return {"quality": 0.0, "category": "abstain"}
    costs = [sp["cost"] for sp in data["species"]]
    width = len(data["outcome_tape"][0][0])
    bundles = output.get("bundles") if isinstance(output, dict) else None
    if (not isinstance(bundles, list) or len(bundles) != len(data["tasks"])
            or not all(isinstance(b, list) and len(b) == len(costs)
                       and all(type(x) is int and 0 <= x <= width for x in b) for b in bundles)
            or sum(c * x for b in bundles for c, x in zip(costs, b)) > data["budget"]):
        return {"quality": -1.0, "category": "wrong"}
    ev = expected_value(truth["p"], [t["context"] for t in data["tasks"]], [t["value"] for t in data["tasks"]],
                        bundles)
    oracle = truth["oracle_value"]
    return {"quality": ev / oracle if oracle > 0 else 1.0, "category": "correct"}


def ecology_subregion(data):
    """From the data alone: warm-up depth (mean trials per cell below 2 is sparse) and budget tightness (below 2 of
    the cheapest species' runs per task is tight)."""
    costs = [sp["cost"] for sp in data["species"]]
    cells = len(costs) * data["contexts"]
    depth = sum(row[3] for row in data["warmup_history"]) / cells
    runs = data["budget"] / (len(data["tasks"]) * min(costs))
    return f"{'sparse' if depth < 2 else 'deep'}_history/{'tight' if runs < 2 else 'loose'}_budget"


INTELLIGENCES = [
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="collective.ecology_bidding", version="1.0.0", family="collective_ecology_bidding",
            layer=2, operation="allocate_compute_by_ecology", epistemic_class="optimization",
            subgeometry="online allocation of a fixed compute budget among solver species (and restarts) over a "
                        "batch of heterogeneous tasks, with per-context success probabilities unknown and learned "
                        "from outcomes; each task's runs are committed before its outcomes are seen",
            source_provenance="ecology of methods competing for resources (directive L2.ecological); Brier (1950) "
                              "and Gneiting and Raftery (2007) proper scoring as reputation; optimism in the face of "
                              "uncertainty (Auer et al. 2002); greedy budgeted allocation by marginal value per cost "
                              "for monotone submodular objectives (Khuller, Moss and Naor 1999); Li et al. (2011) "
                              "replay evaluation of online allocators",
            buildability="BUILDABLE_NOW",
            native_representation="species [K] {name, cost}, contexts C, tasks [N] {context, value} in arrival "
                                  "order, budget, warmup_history [[species, context, successes, trials]], "
                                  "outcome_tape [N][K] strings, rng_seed",
            required_inputs=("species", "tasks", "warmup_history", "outcome_tape"),
            output_contract={"bundles": "[N][K] runs of each species committed per task",
                             "spend": "total cost of the bundles", "solved": "[N] task solved by a bought run",
                             "realised_value": "sum of solved tasks' values on the replayed tapes"},
            algorithm_or_runtime="per task: Beta track records -> optimistic claims (mean + z sd) -> reputation-"
                                 "discounted bids -> budgeted greedy auction over remaining tasks (receding horizon) "
                                 "-> commit current task -> reveal -> Brier-scored reputation update",
            parameters={"z": EC_Z, "eta": EC_ETA, "probability_clip": list(EC_P_CLIP), "max_work": EC_MAX_WORK},
            memory_model="stateless across calls; within a call, per-cell Beta counts and per-species reputation",
            learning_rule="online within the batch: counts from every revealed outcome; reputation from the "
                          "cumulative Brier excess of each species' claims over its own posterior means",
            composition_inputs=("solver species with costs and a track record", "a batch of tasks and a budget"),
            composition_outputs=("per-task run bundles (method choice and restarts)", "species reputations"),
            evidence_type="collective_trace",
            verification_method="independent recomputation of budget feasibility, spend, every replayed outcome and "
                                "the realised value from the request's tapes; certificate shape checks",
            confidence_semantics="no probability is asserted; reputations are scoring-rule weights, and quality is "
                                 "measured against the exact oracle of the declared world",
            resource_profile="O(N x budget x K log) heap operations; pure Python",
            latency_profile="tens to hundreds of milliseconds at native size",
            known_strengths=("bids from a scored track record let a strong species take restarts (the v3b lesson) "
                             "and specialists take their contexts",
                             "a proper-scoring reputation withdraws an overclaiming species' exploration bonus",
                             "budget reserved for later tasks by a receding-horizon auction"),
            known_failure_modes=(
                "reputation is per species, not per context: a species optimistic in one context and calibrated in "
                "another is judged on the mix",
                "deterministic optimism over-explores empty cells when the budget is tight",
                "greedy by bid per cost is not exactly optimal for knapsack-like budgets",
                "the planner trusts the arrival order and treats outcomes as independent across runs; correlated "
                "failures of restarts are not modelled",
                "measured only on a simulated world; real solver competence drifts and is not Bernoulli"),
            counterindications=("competence known in advance (use the exact oracle allocation)",
                                "runs whose outcomes are seen only after the whole batch is committed",
                                "correlated restarts (a deterministic solver gains nothing from a rerun)"),
            abstention_conditions=(f"planning work tasks x budget x species above {EC_MAX_WORK} (UNKNOWN)",
                                   "malformed request (refused with a GenomeError)"),
            benchmark_suite="simulated world (synthetic): 3-5 species with costs 1-3, 3-6 contexts, 24-36 tasks with "
                            "values 1-20, budget 1.2-3.5 units per task, Bernoulli runs from a hidden competence "
                            "table; regimes by seed mod 4: specialists, dominant (restarts win), mixed, stale "
                            "history; warm-up depth 1, 3 or 8 per cell; quality = exact expected value of the "
                            "committed bundles over the exact static oracle; " + _DEV,
            baseline="static: the best pooled warm-up species per unit cost, budget split evenly across tasks",
            competitor="certainty-equivalent online allocator: the same receding-horizon budgeted planner fed the "
                       "(species, context) Beta posterior means, updated online from the same outcomes",
            lineage=LINEAGE),
        solve=ecology_solve, verify=ecology_verify, instance=ecology_instance, score=ecology_score,
        baseline=ecology_baseline, competitor=ecology_certainty_equivalent, subregion=ecology_subregion, tolerance=1e-9,
        notes={"alternative_competitors": "ecology_thompson (contextual Thompson sampling, the pre-registered "
                                           "competitor; dev mean quality 0.735) and UCB-style full-weight optimism "
                                           "(0.789) were weaker than certainty equivalence (0.797) on seeds 0-9; "
                                           "reported, not used by the rule",
               "score": "exact expected value of the committed bundles under the hidden competence table, divided "
                        "by the exact static oracle; the realised value on the tapes is verified, not scored",
               "replay": "outcome tapes travel in the request; non-anticipation is a unit-tested property of every "
                         "arm, not something the verifier can check",
               "related": "collective_auction (collective_b) is a priced market over known values; this genome "
                          "bids under uncertain, learned competence"}),
]
