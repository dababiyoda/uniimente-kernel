"""Layer 5 intelligence: active inference for sequential fault diagnosis (``meta_active_inference``).

The 2026-10-21 coverage record (``docs/collaboration/MIND-COVERAGE-2026-10-21.md``, section 31 item 1) lists active
inference as a directive-named family with no executor (``greg/cognition/reserved.py``: "no generative-model policy
selection exists"). The directive's own condition (SOURCE_COVERAGE_LEDGER: "Compare active inference against simpler
control methods. Do not retain it if ... Bayesian decision theory ... perform[s] better") is the test this genome is
built to take. It runs on GREG's one cognition path (``greg.cognition.cortex.reason`` -> isolated worker ->
independent verifier -> CognitiveReceipt), registered and withheld like every non-seed family.

Native geometry: the question GREG faces when a mission fails and it must find which component broke. N fault
hypotheses (exactly one is true) with a declared prior; M tests, each with a cost and a likelihood table
P(outcome | hypothesis) over 2 or 3 outcomes (noisy; a third outcome is "inconclusive"); each test may be run at most
once; at any point the agent may stop and either declare one hypothesis (loss ``misdiagnosis_loss`` if it is wrong,
0 if right) or escalate (fixed ``escalation_cost``). Total loss = test costs paid + terminal loss.

Candidate (``active_infer_diagnose``): a receding-horizon active-inference agent. At each belief it selects the
action that minimises the expected free energy over a declared planning horizon H = 2:

    G_0(b)       = risk(b)
    G_h(b)       = min( risk(b),  min_j [ c_j / lam - IG_j(b) + sum_o P(o | b, j) G_{h-1}(b_jo) ] )
    risk(b)      = min( L (1 - max_h b_h),  E ) / lam          (pragmatic term: expected negative log-preference)
    IG_j(b)      = H[b] - sum_o P(o | b, j) H[b_jo]             (epistemic term: expected information gain, nats)

Preferences over outcomes are declared as a Boltzmann prior P~(outcome) proportional to exp(-loss / lam), so
expected negative log-preference is expected loss / lam (up to a constant). lam is fixed a priori, before any
development run, by one declared preference precision: a misdiagnosis is 100 times less preferred than a correct
diagnosis, lam = L / ln 100. Not tuned. When "stop" minimises G the agent declares the maximum-posterior hypothesis
(lowest index on ties) or escalates, whichever has the lower expected loss (declare on a tie). The policy is
expanded into a complete decision tree over every outcome with positive probability, and its exact expected loss is
computed along the tree.

Truth (``instance``): the Bayes-optimal expected loss by exact dynamic programming over every partial outcome
assignment (state = which tests were run and their outcomes), on unnormalised joint vectors (numpy), so no posterior
division is shared with the solver. Quality: minus the normalised regret, -(expected loss - optimum) / L, computed
by exact enumeration of the submitted policy's tree under the declared model.

Categories (score). A submitted policy is ``wrong`` when it is not a legal, internally consistent policy: an unknown
or repeated test, a branch list of the wrong length, a missing branch for an outcome of positive probability, a
subtree hung on an outcome of zero probability, a declaration of a hypothesis whose posterior is zero at that leaf
(a declaration contradicted by the evidence it observed), a malformed node, or a claimed ``expected_loss`` that
differs from the exact enumeration (relative 1e-7). Any legal, consistent policy is ``correct`` and its sub-
optimality is carried by its quality. Deviation from the lane brief, which suggested "correct when within a declared
regret tolerance": the admission rule reads ``wrong`` as a false answer (REJECTED/NICHE are decided on wrong counts),
and a legal policy that is merely suboptimal is not false; scoring it ``wrong`` would let regret enter the decision
twice. The regret tolerance is instead the tie tolerance (1e-9 of L) of the quality comparison.

Verifier (independent code path): numpy enumeration of the tree from the prior, the joint probability of every node
recomputed from scratch as prior * product of the likelihood columns along its path (no sequential normalised
updates, no shared helper with the solver); every action checked legal; every positive-probability branch present
and every zero-probability branch empty; every declaration checked to have positive joint mass; the claimed expected
loss checked against the enumeration; the declared planning parameters checked; and the root expected-free-energy
table recomputed by a separate vectorised evaluation and the root action checked to be its argmin.

Baseline: cheapest-first fixed test order (ties by index) until the maximum posterior reaches 0.9 or the tests run
out, then declare or escalate, whichever has the lower expected loss.

Competitor (chosen by a rule declared before any development run: of three standard Bayesian decision-theoretic
policies, the one with the lowest mean regret against the DP optimum on development seeds 0-9, measured on the
competitors alone and never against the candidate):
  * ``voi_myopic``: one-step myopic value of information with exact stopping (run the test with the largest positive
    expected reduction in terminal loss net of its cost, else stop optimally);
  * ``ig_per_cost``: greedy expected information gain per unit cost, stopping at maximum posterior 0.9 (the brief's
    named competitor; threshold fixed, not tuned);
  * ``bayes_lookahead2``: limited-lookahead Bayesian decision theory with the candidate's own horizon H = 2 and pure
    expected loss (no epistemic term): the exact ablation of active inference, i.e. the "Bayesian decision theory"
    the directive says active inference must beat.
Dev result (recorded after the run): mean regret / L on seeds 0-9 was baseline 0.0780, ig_per_cost 0.0724,
voi_myopic 0.0157, bayes_lookahead2 0.0028; ``bayes_lookahead2`` is the competitor. The candidate's dev regret was
0.0183: it beats the baseline 10-0, ig_per_cost 9-1 and voi_myopic 5-4 (diagnostic, not the rule), and loses to
``bayes_lookahead2`` 0-8 with 2 ties (status_if_heldout_matched SUPERSEDED). The epistemic term made it over-test.
Nothing was changed in response. Theory does not guarantee either direction between the candidate and this competitor: the
epistemic term double-counts information that the risk term already values when the horizon reaches a stop, and it
can also offset the myopia of a 2-step horizon when no single test is decisive.

Everything is read-only computation on a declared model: no output creates authority, and nothing here observes a
real system; the benchmark is synthetic. Development seeds 0-9 only.

Post-development changes (disclosure, directive requirement 4): none to the benchmark generator, the candidate's
parameters, the baseline or the score after the first development run; the competitor was selected by the rule
declared above. After the dev run, a unit test on a hand-built instance (escalation cheaper than any test) showed
the candidate testing where the DP and the competitor escalate; it was added to ``known_failure_modes`` as a
documentation change only, and the test pins it.
"""
from __future__ import annotations

import math
import random
import time

from .contract import Executable, GenomeError, IntelligenceGenome, answer, finite

LINEAGE = ("INTENT-20261007-POLYINTELLIGENCE-MIND-CONTINUATION", "INTENT-20261007-VERIFIED-POLYINTELLIGENCE-LIFT",
           "INTENT-20261021-MIND-MAXIMUM-CONTINUATION section 4 (restore the full five-layer scope)",
           "docs/collaboration/MIND-COVERAGE-2026-10-21.md section 31 item 1 (active inference: no executor)",
           "greg/cognition/reserved.py cortex.meta.active_inference ('no generative-model policy selection exists')")

MAX_HYPOTHESES, MAX_TESTS, MAX_OUTCOMES = 12, 7, 3
HORIZON = 2
PREFERENCE_RATIO = 100.0                 # a misdiagnosis is 100 times less preferred than a correct diagnosis
BASELINE_THRESHOLD = 0.9
CLAIM_RTOL = 1e-7
ZERO = 1e-15                             # probability mass at or below this is an impossible outcome
FAMILY = "meta_active_inference"


# =================================================================== input
def _model(data):
    """(prior [N], tests [(cost, lik[N][K])], L, E) after bound checks; raises GenomeError."""
    if not isinstance(data, dict):
        raise GenomeError("data must be a JSON object")
    prior, tests = data.get("fault_prior"), data.get("fault_tests")
    if not isinstance(prior, list) or not 2 <= len(prior) <= MAX_HYPOTHESES:
        raise GenomeError(f"fault_prior: 2-{MAX_HYPOTHESES} probabilities")
    prior = [finite(p, low=0.0, high=1.0, name="fault_prior") for p in prior]
    if abs(sum(prior) - 1.0) > 1e-9 or max(prior) <= 0:
        raise GenomeError("fault_prior must sum to 1")
    n = len(prior)
    if not isinstance(tests, list) or not 1 <= len(tests) <= MAX_TESTS:
        raise GenomeError(f"fault_tests: 1-{MAX_TESTS} tests")
    out = []
    for t in tests:
        if not isinstance(t, dict) or set(t) - {"cost", "likelihood", "name"}:
            raise GenomeError("a test is {cost, likelihood, name?}")
        cost = finite(t.get("cost"), low=0.0, high=1e6, name="cost")
        lik = t.get("likelihood")
        if not isinstance(lik, list) or len(lik) != n or not all(isinstance(r, list) for r in lik):
            raise GenomeError("likelihood: one row per hypothesis")
        k = len(lik[0])
        if not 2 <= k <= MAX_OUTCOMES or any(len(r) != k for r in lik):
            raise GenomeError(f"likelihood: 2-{MAX_OUTCOMES} outcomes, the same for every hypothesis")
        rows = [[finite(p, low=0.0, high=1.0, name="likelihood") for p in r] for r in lik]
        if any(abs(sum(r) - 1.0) > 1e-9 for r in rows):
            raise GenomeError("likelihood rows are distributions over outcomes")
        out.append((cost, rows))
    big_l = finite(data.get("misdiagnosis_loss"), low=1e-6, high=1e6, name="misdiagnosis_loss")
    big_e = finite(data.get("escalation_cost"), low=0.0, high=1e6, name="escalation_cost")
    return prior, out, big_l, big_e


# =================================================================== solver side (pure Python, normalised beliefs)
def _update(b, lik, o):
    w = [b[h] * lik[h][o] for h in range(len(b))]
    z = sum(w)
    return z, ([x / z for x in w] if z > ZERO else None)


def _entropy(b):
    return -sum(p * math.log(p) for p in b if p > 0)


def _stop(b, big_l, big_e):
    """(expected terminal loss, leaf) of the better of declaring the MAP hypothesis and escalating."""
    best = max(range(len(b)), key=lambda h: (b[h], -h))
    declare = big_l * (1.0 - b[best])
    if big_e < declare:
        return big_e, {"escalate": True}
    return declare, {"declare": best}


class _Clock:
    def __init__(self, seconds):
        self.deadline = time.perf_counter() + seconds

    def check(self):
        if time.perf_counter() > self.deadline:
            raise TimeoutError


def _efe(b, avail, tests, big_l, big_e, lam, h, epistemic, clock):
    """G_h(b): minimum expected free energy over the remaining horizon (epistemic=0 gives pure expected loss/lam)."""
    risk = _stop(b, big_l, big_e)[0] / lam
    if h == 0 or not avail:
        return risk
    best = risk
    for j in avail:
        g = _test_g(b, j, avail, tests, big_l, big_e, lam, h, epistemic, clock)
        best = min(best, g)
    return best


def _test_g(b, j, avail, tests, big_l, big_e, lam, h, epistemic, clock):
    clock.check()
    cost, lik = tests[j]
    rest = tuple(x for x in avail if x != j)
    g = cost / lam
    expected_h = 0.0
    for o in range(len(lik[0])):
        z, bo = _update(b, lik, o)
        if bo is None:
            continue
        expected_h += z * _entropy(bo)
        g += z * _efe(bo, rest, tests, big_l, big_e, lam, h - 1, epistemic, clock)
    return g - epistemic * (_entropy(b) - expected_h)


def _plan_action(b, avail, tests, big_l, big_e, lam, epistemic, clock, horizon=HORIZON):
    """(action, table): action 'stop' or a test index; table maps action name -> G (the root decision trace)."""
    table = {"stop": _stop(b, big_l, big_e)[0] / lam}
    for j in avail:
        table[f"test:{j}"] = _test_g(b, j, avail, tests, big_l, big_e, lam, horizon, epistemic, clock)
    best = min(table.values())
    if table["stop"] <= best:
        return "stop", table
    for j in avail:                              # lowest index among the minimisers
        if table[f"test:{j}"] <= best:
            return j, table
    return "stop", table


def _expand(prior, tests, big_l, big_e, policy, clock):
    """Expand ``policy(b, avail) -> 'stop' | j`` into a tree; returns (tree, expected loss) by sequential updates."""
    def go(b, avail):
        clock.check()
        action = policy(b, avail)
        if action == "stop":
            loss, leaf = _stop(b, big_l, big_e)
            return leaf, loss
        cost, lik = tests[action]
        rest = tuple(x for x in avail if x != action)
        branches, loss = [], cost
        for o in range(len(lik[0])):
            z, bo = _update(b, lik, o)
            if bo is None:
                branches.append(None)
                continue
            sub, sub_loss = go(bo, rest)
            branches.append(sub)
            loss += z * sub_loss
        return {"test": action, "branches": branches}, loss
    return go(list(prior), tuple(range(len(tests))))


def _lam(big_l):
    return big_l / math.log(PREFERENCE_RATIO)


def _count(tree):
    if tree is None:
        return 0
    return 1 + sum(_count(c) for c in tree.get("branches", ()))


def solve(data, budget):
    prior, tests, big_l, big_e = _model(data)
    lam = _lam(big_l)
    clock = _Clock(max(0.05, float(budget.get("latency_s", 5.0))))

    def policy(b, avail):
        return _plan_action(b, avail, tests, big_l, big_e, lam, 1.0, clock)[0]
    try:
        root_action, table = _plan_action(list(prior), tuple(range(len(tests))), tests, big_l, big_e, lam, 1.0,
                                          clock)
        tree, loss = _expand(prior, tests, big_l, big_e, policy, clock)
    except TimeoutError:
        return answer(None, {"reason": "planning exceeded the latency budget"}, status="UNKNOWN",
                      missing=["latency budget for receding-horizon planning over the full outcome tree"])
    return answer({"policy": tree, "expected_loss": loss},
                  {"method": "receding-horizon expected-free-energy minimisation (risk + epistemic), "
                             "expanded over every positive-probability outcome",
                   "horizon": HORIZON, "lambda": lam, "preference_ratio": PREFERENCE_RATIO,
                   "root_efe": table, "root_action": "stop" if root_action == "stop" else f"test:{root_action}",
                   "expected_loss": loss, "nodes": _count(tree),
                   "scope": "exact expected loss under the declared model only; the model is not checked against "
                            "the real system"})


# =================================================================== arms (deployable Bayesian policies)
def _arm(data, policy_factory):
    prior, tests, big_l, big_e = _model(data)
    clock = _Clock(120.0)
    tree, loss = _expand(prior, tests, big_l, big_e, policy_factory(tests, big_l, big_e, clock), clock)
    return {"policy": tree, "expected_loss": loss}


def baseline(data):
    """Cheapest-first fixed order until max posterior >= 0.9 or no tests remain; then the better terminal action."""
    def factory(tests, big_l, big_e, clock):
        def policy(b, avail):
            if not avail or max(b) >= BASELINE_THRESHOLD:
                return "stop"
            return min(avail, key=lambda j: (tests[j][0], j))
        return policy
    return _arm(data, factory)


def voi_myopic(data):
    """One-step myopic value of information with exact stopping."""
    def factory(tests, big_l, big_e, clock):
        def policy(b, avail):
            here = _stop(b, big_l, big_e)[0]
            best, choice = 0.0, "stop"
            for j in avail:
                cost, lik = tests[j]
                after = 0.0
                for o in range(len(lik[0])):
                    z, bo = _update(b, lik, o)
                    if bo is not None:
                        after += z * _stop(bo, big_l, big_e)[0]
                gain = here - after - cost
                if gain > best + 1e-12:
                    best, choice = gain, j
            return choice
        return policy
    return _arm(data, factory)


def ig_per_cost(data):
    """Greedy expected information gain per unit cost; stop at max posterior 0.9 or when no test is informative."""
    def factory(tests, big_l, big_e, clock):
        def policy(b, avail):
            if not avail or max(b) >= BASELINE_THRESHOLD:
                return "stop"
            best, choice = 0.0, "stop"
            hb = _entropy(b)
            for j in avail:
                cost, lik = tests[j]
                eh = 0.0
                for o in range(len(lik[0])):
                    z, bo = _update(b, lik, o)
                    if bo is not None:
                        eh += z * _entropy(bo)
                ig = hb - eh
                ratio = ig / max(cost, 1e-9)
                if ig > 1e-12 and ratio > best + 1e-15:
                    best, choice = ratio, j
            return choice
        return policy
    return _arm(data, factory)


def bayes_lookahead2(data):
    """Competitor: limited-lookahead Bayesian decision theory, horizon 2, pure expected loss (no epistemic term)."""
    def factory(tests, big_l, big_e, clock):
        lam = _lam(big_l)

        def policy(b, avail):
            return _plan_action(b, avail, tests, big_l, big_e, lam, 0.0, clock)[0]
        return policy
    return _arm(data, factory)


# =================================================================== independent enumeration (numpy, joint masses)
def _enumerate(data, tree):
    """Exact evaluation of a policy tree from joint masses. Returns (expected loss, problems list)."""
    import numpy as np
    prior, tests, big_l, big_e = _model(data)
    p0 = np.asarray(prior, dtype=float)
    liks = [np.asarray(lik, dtype=float) for _, lik in tests]
    costs = [c for c, _ in tests]
    problems, total = [], 0.0
    stack = [(tree, ())]                     # (node, path of (test, outcome))
    seen = 0
    while stack:
        node, path = stack.pop()
        seen += 1
        if seen > 20000:
            return math.inf, ["tree too large"]
        joint = p0.copy()
        for t, o in path:
            joint = joint * liks[t][:, o]
        mass = float(joint.sum())
        paid = sum(costs[t] for t, _ in path)
        if not isinstance(node, dict):
            problems.append(f"malformed node at {path}")
            continue
        if set(node) == {"test", "branches"}:
            t, br = node["test"], node["branches"]
            if type(t) is not int or not 0 <= t < len(tests):
                problems.append(f"unknown test at {path}")
                continue
            if any(t == u for u, _ in path):
                problems.append(f"test {t} repeated at {path}")
                continue
            k = liks[t].shape[1]
            if not isinstance(br, list) or len(br) != k:
                problems.append(f"branch list length at {path}")
                continue
            for o in range(k):
                m = float((joint * liks[t][:, o]).sum())
                if m > ZERO and br[o] is None:
                    problems.append(f"missing branch {o} at {path}")
                elif m <= ZERO and br[o] is not None:
                    problems.append(f"subtree on an impossible outcome {o} at {path}")
                elif br[o] is not None:
                    stack.append((br[o], path + ((t, o),)))
        elif set(node) == {"declare"}:
            h = node["declare"]
            if type(h) is not int or not 0 <= h < len(prior):
                problems.append(f"unknown hypothesis at {path}")
                continue
            if joint[h] <= ZERO:
                problems.append(f"declares hypothesis {h} with zero posterior at {path}")
                continue
            total += paid * mass + big_l * (mass - float(joint[h]))
        elif set(node) == {"escalate"} and node["escalate"] is True:
            total += (paid + big_e) * mass
        else:
            problems.append(f"malformed node at {path}")
    return total, problems


def _root_efe(data):
    """Separate vectorised evaluation of the root expected-free-energy table (horizon 2, epistemic weight 1)."""
    import numpy as np
    prior, tests, big_l, big_e = _model(data)
    lam = big_l / math.log(PREFERENCE_RATIO)
    liks = [np.asarray(lik, dtype=float) for _, lik in tests]
    costs = np.asarray([c for c, _ in tests], dtype=float)

    def risk(joint):                      # joint: rows are unnormalised beliefs; returns risk per row (per unit mass)
        mass = joint.sum(axis=1)
        post_max = joint.max(axis=1) / mass
        return np.minimum(big_l * (1 - post_max), big_e) / lam

    def ent(joint):
        mass = joint.sum(axis=1, keepdims=True)
        p = joint / mass
        with np.errstate(divide="ignore", invalid="ignore"):
            return -np.where(p > 0, p * np.log(np.where(p > 0, p, 1.0)), 0.0).sum(axis=1)

    def g_test(joint_row, j, avail, depth):
        """G of running test j from one unnormalised belief row, then planning depth-1 more steps."""
        mass = joint_row.sum()
        children = joint_row[None, :] * liks[j].T            # K x N unnormalised
        cm = children.sum(axis=1)
        live = cm > ZERO * mass
        child, z = children[live], cm[live] / mass
        rest = [x for x in avail if x != j]
        if depth - 1 == 0 or not rest:
            cont = risk(child)
        else:
            cont = np.array([min([float(risk(c[None, :])[0])]
                                 + [g_test(c, k, rest, depth - 1) for k in rest]) for c in child])
        ig = float(ent(joint_row[None, :])[0]) - float((z * ent(child)).sum())
        return float(costs[j] / lam + (z * cont).sum() - ig)

    root = np.asarray(prior, dtype=float)
    avail = list(range(len(tests)))
    table = {"stop": float(risk(root[None, :])[0])}
    for j in avail:
        table[f"test:{j}"] = g_test(root, j, avail, HORIZON)
    return table, lam


def verify(data, output, certificate):
    checks = {}
    if (not isinstance(output, dict) or set(output) != {"policy", "expected_loss"}
            or type(output["expected_loss"]) not in (int, float) or not math.isfinite(output["expected_loss"])):
        return {"output_shape": False}
    total, problems = _enumerate(data, output["policy"])
    checks["policy_legal_and_consistent"] = not problems
    claim = output["expected_loss"]
    checks["expected_loss_recomputed"] = (not problems and math.isfinite(total)
                                          and abs(total - claim) <= CLAIM_RTOL * max(1.0, abs(total)))
    cert = certificate if isinstance(certificate, dict) else {}
    checks["certificate_loss_matches"] = (type(cert.get("expected_loss")) in (int, float)
                                          and abs(cert["expected_loss"] - claim) <= CLAIM_RTOL * max(1.0, abs(claim)))
    table, lam = _root_efe(data)
    claimed = cert.get("root_efe")
    checks["declared_parameters"] = (cert.get("horizon") == HORIZON and cert.get("preference_ratio") == PREFERENCE_RATIO
                                     and type(cert.get("lambda")) is float
                                     and abs(cert["lambda"] - lam) <= 1e-9 * lam)
    checks["root_efe_recomputed"] = (isinstance(claimed, dict) and set(claimed) == set(table) and all(
        type(claimed[a]) in (int, float) and abs(claimed[a] - table[a]) <= 1e-7 * max(1.0, abs(table[a]))
        for a in table))
    best = min(table.values())
    root = output["policy"]
    if isinstance(root, dict) and "test" in root:
        root_name = f"test:{root['test']}"
    else:
        root_name = "stop"
    checks["root_action_is_efe_argmin"] = (cert.get("root_action") == root_name and root_name in table
                                           and table[root_name] <= best + 1e-9 * max(1.0, abs(best)))
    return checks


# =================================================================== benchmark
REGIMES = ("sharp", "noisy", "graded")


def instance(seed):
    """Synthetic. Regime by seed mod 3: ``sharp`` (binary tests, false-positive/negative 0.02-0.1, cost 1-10),
    ``noisy`` (ternary pass/fail/inconclusive, inconclusive 0.1-0.35, error 0.1-0.25, cost 1-10), ``graded`` (cheap
    noisy binary tests, cost 1-3 and error 0.15-0.3, beside expensive precise ternary tests, cost 6-15 and error
    0.01-0.05). N = 4-10 components, M = 4-6 tests, each probing a random subset of 1 to N/2 components; prior from
    Gamma(0.7) weights; L = 60-200, E = 0.25-0.6 L. Truth: the Bayes-optimal expected loss by exact DP."""
    r = random.Random(f"genome:{FAMILY}:{seed}")
    regime = REGIMES[seed % 3]
    n, m = r.randint(4, 10), r.randint(4, 6)
    w = [r.gammavariate(0.7, 1.0) + 1e-3 for _ in range(n)]
    s = sum(w)
    prior = [x / s for x in w]
    prior[-1] = 1.0 - sum(prior[:-1])
    tests = []
    for j in range(m):
        size = r.randint(1, max(1, n // 2))
        probe = set(r.sample(range(n), size))
        if regime == "sharp" or (regime == "graded" and j % 2 == 0):
            if regime == "sharp":
                cost, fp, fn = r.uniform(1, 10), r.uniform(0.02, 0.1), r.uniform(0.02, 0.1)
            else:
                cost, fp, fn = r.uniform(1, 3), r.uniform(0.15, 0.3), r.uniform(0.15, 0.3)
            lik = [[fn, 1 - fn] if h in probe else [1 - fp, fp] for h in range(n)]   # [pass, fail]
        else:
            if regime == "noisy":
                cost, q, err = r.uniform(1, 10), r.uniform(0.1, 0.35), r.uniform(0.1, 0.25)
            else:
                cost, q, err = r.uniform(6, 15), r.uniform(0.02, 0.1), r.uniform(0.01, 0.05)
            lik = [[(1 - q) * err, (1 - q) * (1 - err), q] if h in probe else [(1 - q) * (1 - err), (1 - q) * err, q]
                   for h in range(n)]                                                  # [pass, fail, inconclusive]
        lik = [[round(p, 12) for p in row] for row in lik]
        lik = [row[:-1] + [1.0 - sum(row[:-1])] for row in lik]
        tests.append({"name": f"probe-{j}", "cost": round(cost, 6), "likelihood": lik})
    big_l = round(r.uniform(60, 200), 6)
    big_e = round(r.uniform(0.25, 0.6) * big_l, 6)
    data = {"fault_prior": prior, "fault_tests": tests, "misdiagnosis_loss": big_l, "escalation_cost": big_e}
    return data, {"optimal_loss": optimal_loss(data), "regime": regime}


def optimal_loss(data):
    """Bayes-optimal expected loss by exact DP over partial outcome assignments, on unnormalised joints."""
    import numpy as np
    prior, tests, big_l, big_e = _model(data)
    liks = [np.asarray(lik, dtype=float) for _, lik in tests]
    costs = [c for c, _ in tests]
    m = len(tests)
    memo = {}

    def value(state, joint):
        if state in memo:
            return memo[state]
        mass = float(joint.sum())
        if mass <= 0:
            return 0.0
        best = min(big_l * (mass - float(joint.max())), big_e * mass)
        for j in range(m):
            if state[j] != -1:
                continue
            v = costs[j] * mass
            if v >= best:
                continue
            for o in range(liks[j].shape[1]):
                child = joint * liks[j][:, o]
                if float(child.sum()) > 0:
                    v += value(state[:j] + (o,) + state[j + 1:], child)
                if v >= best:
                    break
            best = min(best, v)
        memo[state] = best
        return best
    return value((-1,) * m, np.asarray(prior, dtype=float))


def score(data, truth, output):
    if not isinstance(output, dict) or "policy" not in output:
        return {"quality": -1e6, "category": "abstain"}
    big_l = data["misdiagnosis_loss"]
    claim = output.get("expected_loss")
    try:
        total, problems = _enumerate(data, output["policy"])
    except (GenomeError, TypeError, ValueError, KeyError):
        return {"quality": -2e6, "category": "wrong"}
    if (problems or type(claim) not in (int, float) or not math.isfinite(claim)
            or abs(total - claim) > CLAIM_RTOL * max(1.0, abs(total))):
        return {"quality": -2e6, "category": "wrong"}
    return {"quality": -(total - truth["optimal_loss"]) / big_l, "category": "correct"}


def subregion(data):
    ks = [len(t["likelihood"][0]) for t in data.get("fault_tests", [])]
    if all(k == 2 for k in ks):
        return "binary_tests"
    if all(k == 3 for k in ks):
        return "ternary_tests"
    return "mixed_tests"


_DEV = "seeds 0-9 dev, held-out seeds fixed by the admission freeze"

INTELLIGENCES = [
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="meta.active_inference.efe_diagnosis", version="1.0.0", family=FAMILY,
            layer=5, operation="active_infer_diagnose", epistemic_class="causal",
            subgeometry="sequential fault diagnosis: one true fault among N hypotheses, noisy costed tests run at "
                        "most once each, stop by declaring a fault (misdiagnosis loss) or escalating (fixed cost)",
            source_provenance="Friston et al. (2015, 2017) active inference and expected free energy (risk + "
                              "ambiguity / epistemic value); Parr, Pezzulo and Friston (2022) Active Inference; "
                              "Howard (1966) information value theory; exact Bayes-optimal truth by Bellman (1957) "
                              "dynamic programming over outcome assignments",
            buildability="BUILDABLE_NOW",
            native_representation="fault_prior [N]; fault_tests [M] of {cost, likelihood [N][K]}; misdiagnosis_loss; "
                                  "escalation_cost",
            required_inputs=("fault_prior", "fault_tests", "misdiagnosis_loss", "escalation_cost"),
            output_contract={"policy": "decision tree: {test, branches[K]} | {declare: h} | {escalate: true}",
                             "expected_loss": "exact expected test cost + terminal loss under the declared model"},
            algorithm_or_runtime="receding-horizon (H=2) minimisation of expected free energy G = risk (expected "
                                 "loss / lam, Boltzmann preferences) - expected information gain, expanded over every "
                                 "positive-probability outcome",
            parameters={"horizon": HORIZON, "preference_ratio": PREFERENCE_RATIO, "lambda": "L / ln 100",
                        "stop_rule": "stop when G(stop) <= min_j G(test j); declare MAP or escalate, lower loss"},
            memory_model="stateless (plans from the declared model on every call)",
            learning_rule="none (the generative model is declared per request; competence settles through GREG "
                          "outcomes)",
            composition_inputs=("a fault model from mission telemetry or a recovery playbook",),
            composition_outputs=("a complete diagnostic decision tree with its exact expected loss",),
            evidence_type="decision_analysis",
            verification_method="independent numpy enumeration of the tree from joint masses (prior x likelihood "
                                 "columns along each path): legality, branch coverage, declaration consistency and "
                                 "expected loss; root expected-free-energy table recomputed by a separate vectorised "
                                 "evaluation and the root action checked as its argmin",
            confidence_semantics="the expected loss is exact under the declared model; it says nothing about whether "
                                 "the model matches the real system",
            resource_profile="O(nodes x (M K)^H N) arithmetic; pure Python solver",
            latency_profile="milliseconds to about a second for M <= 7",
            known_strengths=("plans past one step: the epistemic term values tests whose payoff only shows after a "
                             "second test", "a complete, checkable policy tree rather than one next action",
                             "stopping, declaring and escalating decided in one objective"),
            known_failure_modes=(
                "the epistemic term double-counts information the risk term already values when the horizon reaches "
                "a stop, so it can over-test relative to Bayes-optimal stopping",
                "information gain is valued for its own sake: it buys tests even when escalating at once is cheaper "
                "than any test (pinned by a unit test)",
                "the preference precision (misdiagnosis 100x less preferred) converts loss to nats by fiat; a "
                "different precision changes the policy", "horizon 2 is myopic when three or more tests are needed "
                "jointly", "the declared likelihoods are trusted; a wrong model gives a confidently wrong policy",
                "single-fault assumption: exactly one hypothesis is true"),
            counterindications=("multiple simultaneous faults", "tests whose outcomes change the system (destructive "
                                "or state-altering probes)", "small problems where exact DP is affordable (DP is "
                                "optimal)", "likelihoods not elicited or estimated from data"),
            abstention_conditions=("planning exceeds the latency budget (UNKNOWN, no partial policy)",
                                   "inputs outside the declared bounds (refused: 2-12 hypotheses, 1-7 tests, 2-3 "
                                   "outcomes)"),
            benchmark_suite="synthetic fault-diagnosis instances, regimes by seed mod 3: sharp binary, noisy ternary "
                            "with inconclusive outcomes, graded (cheap noisy beside expensive precise tests); N 4-10, "
                            "M 4-6; quality minus the regret to the exact DP optimum over L; " + _DEV,
            baseline="cheapest-first fixed test order until max posterior >= 0.9, then declare or escalate",
            competitor="limited-lookahead Bayesian decision theory, horizon 2, pure expected loss (the active-"
                       "inference ablation without the epistemic term); selected over myopic VOI and greedy "
                       "information gain per cost by dev regret to the DP optimum",
            lineage=LINEAGE),
        solve=solve, verify=verify, instance=instance, score=score,
        baseline=baseline, competitor=bayes_lookahead2, subregion=subregion, tolerance=1e-9,
        notes={"competitor_selection": "rule declared before the first dev run: lowest mean dev regret among "
                                       "voi_myopic, ig_per_cost and bayes_lookahead2, measured on the competitors "
                                       "alone",
               "alternative_competitors": "voi_myopic and ig_per_cost are exported for diagnostics; never inputs "
                                          "to the rule",
               "truth": "exact Bayes-optimal expected loss (DP); the optimum is a reference, not a deployable arm "
                        "at larger M"}),
]
